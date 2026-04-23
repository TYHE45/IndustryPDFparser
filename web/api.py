"""FastAPI 路由。"""
from __future__ import annotations

import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from web.progress import (
    EVENT_心跳,
    EVENT_批次完成,
    EVENT_批次失败,
    EVENT_批次开始,
    encode_sse,
    make_event,
)
from web.runner import run_single_file
from web.schemas import BatchCreateResponse, BatchFileStatus, BatchStatus, FileInfo, StartBatchRequest
from web.task_manager import (
    _LOCK,
    _new_batch_id,
    create_batch,
    generate_batch_report,
    get_batch,
    publish_event,
    subscribe,
    unsubscribe,
)

router = APIRouter(prefix="/api")

UPLOAD_ROOT = Path("input/uploads")
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="batch-worker")


def _sanitize_filename(name: str) -> str:
    base = Path(name).name
    cleaned = re.sub(r"[^\w\u4e00-\u9fff.\-]+", "_", base)
    return cleaned or "upload.pdf"


def _sanitize_path_part(value: str | None, fallback: str) -> str:
    raw = (value or "").strip().replace("\\", "/").strip("/")
    cleaned = re.sub(r"[^\w\u4e00-\u9fff.\-]+", "_", raw)
    if cleaned in {"", ".", ".."}:
        return fallback
    return cleaned


def _normalize_relative_parts(raw_parts: Any) -> tuple[str, ...]:
    if isinstance(raw_parts, list):
        values = raw_parts
    elif isinstance(raw_parts, str):
        values = [part for part in raw_parts.replace("\\", "/").split("/") if part]
    else:
        return ()
    parts: list[str] = []
    for idx, item in enumerate(values):
        normalized = _sanitize_path_part(str(item), f"目录{idx + 1}")
        if normalized in {"", ".", ".."}:
            continue
        parts.append(normalized)
    return tuple(parts)


def _normalize_output_root(value: str | None) -> str:
    candidate = (value or "output").strip() or "output"
    path = Path(candidate)
    if path.is_absolute():
        raise HTTPException(status_code=400, detail="输出根目录必须为相对路径")
    if any(part == ".." for part in path.parts):
        raise HTTPException(status_code=400, detail="输出根目录不能包含上级路径")
    if not path.parts:
        return "output"
    if path.parts[0].lower() != "output":
        path = Path("output") / path
    return str(path)


def _load_manifest(manifest_json: str | None) -> Any:
    if not manifest_json:
        return []
    try:
        payload = json.loads(manifest_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"上传清单解析失败: {exc}") from exc
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return payload
    raise HTTPException(status_code=400, detail="上传清单必须是数组或对象")


def _summarize_batch_source(files_info: list[dict[str, Any]]) -> tuple[str, str]:
    source_types = sorted({str(info.get("来源类型") or "本地上传") for info in files_info})
    source_labels = sorted({
        "/".join(info.get("来源层级") or ()) or "本地上传"
        for info in files_info
    })
    batch_source_type = source_types[0] if len(source_types) == 1 else "混合来源"
    batch_source_label = source_labels[0] if len(source_labels) == 1 else "混合来源"
    return batch_source_type, batch_source_label


@router.post("/batches", response_model=BatchCreateResponse)
async def create_batch_endpoint(
    files: list[UploadFile] = File(...),
    manifest: str | None = Form(default=None),
    manifest_json: str | None = Form(default=None),
) -> BatchCreateResponse:
    if not files:
        raise HTTPException(status_code=400, detail="未上传任何文件")

    raw_manifest = _load_manifest(manifest or manifest_json)
    batch_manifest = raw_manifest if isinstance(raw_manifest, dict) else {}
    manifest_items = raw_manifest.get("文件", []) if isinstance(raw_manifest, dict) else raw_manifest
    if not isinstance(manifest_items, list):
        raise HTTPException(status_code=400, detail="上传清单中的文件列表格式不正确")

    batch_source_type = str(batch_manifest.get("来源类型") or "").strip() or None
    batch_source_label = str(batch_manifest.get("来源说明") or "").strip() or None
    batch_source_layers = _normalize_relative_parts(batch_manifest.get("来源层"))
    batch_id = _new_batch_id()
    upload_dir = UPLOAD_ROOT / batch_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    files_info: list[dict[str, Any]] = []
    response_files: list[FileInfo] = []

    for idx, upload in enumerate(files):
        meta = manifest_items[idx] if idx < len(manifest_items) else {}
        original_name = upload.filename or str(meta.get("original_name") or f"upload_{idx}.pdf")
        safe_name = _sanitize_filename(original_name)
        if not safe_name.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"仅支持 PDF: {original_name}")

        if "相对路径" in meta or "来源层" in meta:
            raw_relative_parts = _normalize_relative_parts(meta.get("相对路径") or original_name)
            explicit_source_layers = _normalize_relative_parts(meta.get("来源层"))
            if len(raw_relative_parts) > 1:
                source_layers = explicit_source_layers or raw_relative_parts[:1] or batch_source_layers or ("web_uploads",)
                relative_parts = raw_relative_parts[1:-1] if explicit_source_layers else raw_relative_parts[1:-1]
                logical_relative_parts = raw_relative_parts[1:] if explicit_source_layers else raw_relative_parts[1:]
            else:
                source_layers = explicit_source_layers or batch_source_layers or ("web_uploads",)
                relative_parts = ()
                logical_relative_parts = (safe_name,)
            source_type = str(meta.get("来源类型") or batch_source_type or "本地上传").strip() or "本地上传"
            acquisition_mode = "folder_picker" if len(raw_relative_parts) > 1 else "file_picker"
        else:
            source_type = str(meta.get("source_type") or batch_source_type or "本地上传").strip() or "本地上传"
            source_layers = (_sanitize_path_part(str(meta.get("source_label") or batch_source_label or ""), "本地上传"),)
            relative_parts = _normalize_relative_parts(meta.get("relative_dir_parts"))
            logical_relative_parts = (*relative_parts, original_name) if relative_parts else (original_name,)
            acquisition_mode = str(meta.get("acquisition_mode") or "file_picker").strip() or "file_picker"

        logical_relative_path = "/".join(logical_relative_parts) if logical_relative_parts else original_name
        dst_dir = upload_dir.joinpath(*source_layers, *relative_parts)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / f"f{idx:03d}_{safe_name}"

        content = await upload.read()
        dst.write_bytes(content)
        files_info.append({
            "name": original_name,
            "size": len(content),
            "uploaded_path": dst,
            "safe_name": safe_name,
            "来源类型": source_type,
            "来源层级": tuple(source_layers),
            "相对路径": logical_relative_path,
            "采集方式": acquisition_mode,
        })

    auto_source_type, auto_source_label = _summarize_batch_source(files_info)
    # 优先采用 manifest 顶层显式提供的来源字段，缺省才回落到根据文件列表自动汇总。
    # 注：前端（web/static/app.js:19 manifest()）只会发送 "文件夹来源"/"拖拽上传"/"本地文件"，
    # 不使用字符串 "auto" 作为特殊 sentinel；因此这里的 or 短路回退是安全的。
    resolved_source_type = batch_source_type or auto_source_type
    resolved_source_label = batch_source_label or auto_source_label
    batch = create_batch(
        files_info,
        batch_id=batch_id,
        来源类型=resolved_source_type,
        来源说明=resolved_source_label,
    )

    for file_task in batch.files:
        response_files.append(
            FileInfo(
                file_id=file_task.file_id,
                name=file_task.name,
                size=file_task.size,
                source_label="/".join(file_task.来源层级) or None,
                relative_path=file_task.相对路径 or None,
            )
        )

    return BatchCreateResponse(
        batch_id=batch.batch_id,
        source_type=batch.来源类型,
        source_label=batch.来源说明,
        files=response_files,
    )


def _process_batch(batch_id: str, output_root: str) -> None:
    batch = get_batch(batch_id)
    if batch is None:
        return

    with _LOCK:
        batch.started_at = datetime.now().isoformat(timespec="seconds")
    batch_error: str | None = None
    report_path: Path | None = None

    try:
        for file_task in batch.files:
            run_single_file(file_task, batch, output_root, publish_event)
    except Exception as exc:
        batch_error = str(exc)
    finally:
        成功数 = sum(1 for file_task in batch.files if file_task.status == "已完成")
        失败数 = sum(1 for file_task in batch.files if file_task.status == "失败")
        # 按各文件实际结果推导批次状态（排除外层异常覆盖的场景）。
        if batch_error is None:
            if 失败数 == 0:
                derived_status = "已完成"
            elif 成功数 == 0:
                derived_status = "失败"
            else:
                derived_status = "部分完成"
        else:
            derived_status = "失败"

        with _LOCK:
            batch.status = derived_status
            batch.finished_at = datetime.now().isoformat(timespec="seconds")

        try:
            report_path = generate_batch_report(batch_id, output_root)
        except Exception as report_exc:
            with _LOCK:
                batch.status = "失败"
            if batch_error:
                batch_error = f"{batch_error}; 批次报告生成失败: {report_exc}"
            else:
                batch_error = f"批次报告生成失败: {report_exc}"

    成功数 = sum(1 for file_task in batch.files if file_task.status == "已完成")
    失败数 = sum(1 for file_task in batch.files if file_task.status == "失败")

    if batch_error:
        publish_event(
            batch_id,
            make_event(
                EVENT_批次失败,
                batch_id,
                成功数=成功数,
                失败数=失败数,
                报告路径=str(report_path) if report_path else None,
                错误=batch_error,
            ),
        )
        return

    publish_event(
        batch_id,
        make_event(
            EVENT_批次完成,
            batch_id,
            批次状态=batch.status,
            成功数=成功数,
            失败数=失败数,
            报告路径=str(report_path) if report_path else None,
        ),
    )


@router.post("/batches/{batch_id}/start")
async def start_batch(batch_id: str, req: StartBatchRequest | None = None) -> dict[str, str]:
    batch = get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="批次不存在")
    if batch.status not in {"待开始"}:
        raise HTTPException(status_code=400, detail=f"批次状态无法启动: {batch.status}")

    output_root = _normalize_output_root(req.output_root if req else "output")
    with _LOCK:
        batch.output_root = output_root
        batch.status = "处理中"

    publish_event(
        batch_id,
        make_event(
            EVENT_批次开始,
            batch_id,
            总文件数=len(batch.files),
            输出根目录=output_root,
            来源类型=batch.来源类型,
            来源说明=batch.来源说明,
        ),
    )

    _EXECUTOR.submit(_process_batch, batch_id, output_root)
    return {"batch_id": batch_id, "status": batch.status}


@router.get("/batches/{batch_id}", response_model=BatchStatus)
async def get_batch_status(batch_id: str) -> BatchStatus:
    batch = get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="批次不存在")

    files = [
        BatchFileStatus(
            file_id=file_task.file_id,
            name=file_task.name,
            size=file_task.size,
            status=file_task.status,
            progress=file_task.progress,
            phase=file_task.phase,
            source_type=file_task.来源类型,
            source_layers=list(file_task.来源层级),
            source_relative_path=file_task.相对路径,
            acquisition_mode=file_task.采集方式,
            总分=file_task.总分,
            是否通过=file_task.是否通过,
            红线触发=file_task.红线触发,
            未通过原因=list(file_task.未通过原因),
            评审轮次数=file_task.评审轮次数,
            error=file_task.error,
            error_traceback=file_task.error_traceback,
            output_dir=str(file_task.output_dir) if file_task.output_dir else None,
        )
        for file_task in batch.files
    ]

    return BatchStatus(
        batch_id=batch.batch_id,
        status=batch.status,
        created_at=batch.created_at,
        started_at=batch.started_at,
        finished_at=batch.finished_at,
        output_root=batch.output_root,
        source_type=batch.来源类型,
        source_label=batch.来源说明,
        report_ready=bool(batch.batch_report_path and batch.batch_report_path.exists()),
        batch_report_path=str(batch.batch_report_path) if batch.batch_report_path else None,
        files=files,
    )


@router.get("/batches/{batch_id}/events")
async def stream_events(batch_id: str) -> StreamingResponse:
    batch = get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="批次不存在")

    async def gen() -> AsyncIterator[str]:
        queue = subscribe(batch_id)
        if queue is None:
            return
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield encode_sse(event)
                except asyncio.TimeoutError:
                    yield encode_sse(make_event(EVENT_心跳, batch_id))
        except asyncio.CancelledError:
            raise
        finally:
            unsubscribe(batch_id, queue)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _list_outputs(output_dir: Path) -> list[dict[str, Any]]:
    if not output_dir.exists() or not output_dir.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file():
            items.append({
                "name": path.name,
                "size": path.stat().st_size,
                "rel_path": str(path.relative_to(output_dir)).replace("\\", "/"),
            })
    return items


@router.get("/batches/{batch_id}/files/{file_id}/outputs")
async def list_file_outputs(batch_id: str, file_id: str) -> dict[str, Any]:
    batch = get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="批次不存在")
    file_task = batch.file_by_id(file_id)
    if file_task is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    if file_task.output_dir is None:
        return {"file_id": file_id, "outputs": []}
    return {"file_id": file_id, "outputs": _list_outputs(file_task.output_dir)}


@router.get("/batches/{batch_id}/files/{file_id}/download/{filename:path}")
async def download_output(batch_id: str, file_id: str, filename: str) -> FileResponse:
    batch = get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="批次不存在")
    file_task = batch.file_by_id(file_id)
    if file_task is None or file_task.output_dir is None:
        raise HTTPException(status_code=404, detail="文件不存在")

    outputs = _list_outputs(file_task.output_dir)
    valid_rel_paths = {item["rel_path"] for item in outputs}
    normalized = filename.replace("\\", "/")
    if normalized not in valid_rel_paths:
        raise HTTPException(status_code=404, detail="输出文件不存在或不允许访问")

    target = file_task.output_dir / normalized
    try:
        target.resolve().relative_to(file_task.output_dir.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="非法路径") from exc

    return FileResponse(path=target, filename=target.name)


@router.get("/batches/{batch_id}/report")
async def download_report(batch_id: str) -> FileResponse:
    batch = get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="批次不存在")
    if batch.batch_report_path is None or not batch.batch_report_path.exists():
        raise HTTPException(status_code=404, detail="批次报告尚未生成")
    return FileResponse(
        path=batch.batch_report_path,
        filename=f"batch_report_{batch_id}.json",
        media_type="application/json",
    )
