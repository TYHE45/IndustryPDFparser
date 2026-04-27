"""批次和文件任务状态管理。"""
from __future__ import annotations

import asyncio
import json
import threading
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass
class FileTask:
    file_id: str
    name: str
    size: int
    uploaded_path: Path
    safe_name: str
    来源类型: str
    来源层级: tuple[str, ...] = field(default_factory=tuple)
    相对路径: str = ""
    采集方式: str = "file_picker"
    status: str = "待处理"
    progress: float = 0.0
    phase: str = ""
    output_dir: Optional[Path] = None
    总分: Optional[float | str] = None
    是否通过: Optional[bool] = None
    红线触发: Optional[bool] = None
    未通过原因: list[str] = field(default_factory=list)
    评审轮次数: int = 0
    error: Optional[str] = None
    error_traceback: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

    @property
    def 逻辑父目录层级(self) -> tuple[str, ...]:
        relative_parts = tuple(part for part in self.相对路径.replace("\\", "/").split("/") if part)
        if len(relative_parts) <= 1:
            return self.来源层级
        return self.来源层级 + relative_parts[:-1]


@dataclass
class Subscriber:
    queue: asyncio.Queue
    loop: asyncio.AbstractEventLoop


@dataclass
class Batch:
    batch_id: str
    created_at: str
    files: list[FileTask] = field(default_factory=list)
    来源类型: str = "本地上传"
    来源说明: str = "web_uploads"
    status: str = "待开始"
    output_root: str = "output"
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    event_history: list[dict] = field(default_factory=list)
    subscribers: list[Subscriber] = field(default_factory=list)
    batch_report_path: Optional[Path] = None

    def file_by_id(self, file_id: str) -> Optional[FileTask]:
        for file_task in self.files:
            if file_task.file_id == file_id:
                return file_task
        return None


BATCHES: dict[str, Batch] = {}
_LOCK = threading.RLock()

# 单批次 event_history 上限，超过后按 FIFO 丢弃旧事件，防止长批次内存无限增长。
EVENT_HISTORY_MAX = 500


def _new_batch_id() -> str:
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    short = uuid.uuid4().hex[:6]
    return f"b_{ts}_{short}"


def _new_file_id() -> str:
    return f"f_{uuid.uuid4().hex[:10]}"


def _summarize_source(files_info: list[dict]) -> str:
    labels = sorted({
        "/".join(info.get("来源层级") or ()) or "web_uploads"
        for info in files_info
    })
    if not labels:
        return "web_uploads"
    if len(labels) == 1:
        return labels[0]
    return "混合来源"


def create_batch(
    files_info: list[dict],
    *,
    batch_id: str | None = None,
    来源类型: str = "本地上传",
    来源说明: str | None = None,
) -> Batch:
    """创建批次对象。"""
    with _LOCK:
        actual_batch_id = batch_id or _new_batch_id()
        tasks: list[FileTask] = []
        for info in files_info:
            tasks.append(
                FileTask(
                    file_id=_new_file_id(),
                    name=info["name"],
                    size=info["size"],
                    uploaded_path=info["uploaded_path"],
                    safe_name=info["safe_name"],
                    来源类型=info.get("来源类型", 来源类型),
                    来源层级=tuple(info.get("来源层级") or ()),
                    相对路径=info.get("相对路径", info["safe_name"]),
                    采集方式=info.get("采集方式", "file_picker"),
                )
            )
        batch = Batch(
            batch_id=actual_batch_id,
            created_at=datetime.now().isoformat(timespec="seconds"),
            files=tasks,
            来源类型=来源类型,
            来源说明=来源说明 or _summarize_source(files_info),
        )
        BATCHES[actual_batch_id] = batch
        return batch


def get_batch(batch_id: str) -> Optional[Batch]:
    with _LOCK:
        return BATCHES.get(batch_id)


def _push_event(queue: asyncio.Queue, event: dict) -> None:
    try:
        queue.put_nowait(event)
    except Exception:
        return


def _remove_subscribers(batch_id: str, subscribers: list[Subscriber]) -> None:
    if not subscribers:
        return
    with _LOCK:
        batch = BATCHES.get(batch_id)
        if batch is None:
            return
        for subscriber in subscribers:
            if subscriber in batch.subscribers:
                batch.subscribers.remove(subscriber)


def publish_event(batch_id: str, event: dict) -> None:
    """发布一个事件，兼容 worker 线程与 SSE 订阅者。"""
    with _LOCK:
        batch = BATCHES.get(batch_id)
        if batch is None:
            return
        batch.event_history.append(event)
        if len(batch.event_history) > EVENT_HISTORY_MAX:
            del batch.event_history[: len(batch.event_history) - EVENT_HISTORY_MAX]
        subscribers = list(batch.subscribers)

    dead: list[Subscriber] = []
    for subscriber in subscribers:
        if subscriber.loop.is_closed():
            dead.append(subscriber)
            continue
        try:
            subscriber.loop.call_soon_threadsafe(_push_event, subscriber.queue, event)
        except RuntimeError:
            dead.append(subscriber)

    _remove_subscribers(batch_id, dead)


def subscribe(batch_id: str) -> Optional[asyncio.Queue]:
    """订阅批次事件。新连接先回放历史。"""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    subscriber = Subscriber(queue=queue, loop=loop)
    with _LOCK:
        batch = BATCHES.get(batch_id)
        if batch is None:
            return None
        history = list(batch.event_history)
        batch.subscribers.append(subscriber)

    for event in history:
        queue.put_nowait(event)
    return queue


def unsubscribe(batch_id: str, queue: asyncio.Queue) -> None:
    with _LOCK:
        batch = BATCHES.get(batch_id)
        if batch is None:
            return
        batch.subscribers = [item for item in batch.subscribers if item.queue is not queue]


def _collect_output_files(output_dir: Path | None) -> list[str]:
    if output_dir is None or not output_dir.exists():
        return []
    return [
        str(path.relative_to(output_dir)).replace("\\", "/")
        for path in sorted(output_dir.rglob("*"))
        if path.is_file()
    ]


def _calc_rate(numerator: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(numerator / total * 100, 1)


def _top_n_failure_reasons(files: list[FileTask], n: int) -> list[dict[str, int | str]]:
    """统计全批最常见的未通过原因（不含空原因）。"""
    counter: Counter[str] = Counter()
    for ft in files:
        for reason in ft.未通过原因:
            if reason:
                counter[reason] += 1
    return [
        {"原因": reason, "出现次数": count}
        for reason, count in counter.most_common(n)
    ]


def generate_batch_report(batch_id: str, output_root: str) -> Path:
    """生成每批次独立的汇总报告 JSON。"""
    batch = get_batch(batch_id)
    if batch is None:
        raise KeyError(f"批次不存在: {batch_id}")

    report_root = Path(output_root) / "批次" / batch.batch_id
    report_root.mkdir(parents=True, exist_ok=True)
    report_path = report_root / "batch_report.json"

    成功数 = sum(1 for file_task in batch.files if file_task.status == "已完成")
    失败数 = sum(1 for file_task in batch.files if file_task.status == "失败")

    payload: dict[str, Any] = {
        "批次ID": batch.batch_id,
        "创建时间": batch.created_at,
        "开始时间": batch.started_at,
        "完成时间": batch.finished_at or datetime.now().isoformat(timespec="seconds"),
        "批次状态": batch.status,
        "来源类型": batch.来源类型,
        "来源说明": batch.来源说明,
        "输出根目录": str(Path(output_root)),
        "批次报告路径": str(report_path),
        "总文件数": len(batch.files),
        "成功数": 成功数,
        "失败数": 失败数,
        "通过数": sum(1 for f in batch.files if f.是否通过 is True),
        "未通过数": sum(1 for f in batch.files if f.是否通过 is False),
        "红线触发数": sum(1 for f in batch.files if f.红线触发 is True),
        "红线触发率": _calc_rate(sum(1 for f in batch.files if f.红线触发 is True), len(batch.files)),
        "最常见扣分项": _top_n_failure_reasons(batch.files, n=3),
        "文件列表": [
            {
                "文件ID": file_task.file_id,
                "原文件名": file_task.name,
                "来源类型": file_task.来源类型,
                "来源层级": list(file_task.来源层级),
                "相对路径": file_task.相对路径,
                "采集方式": file_task.采集方式,
                "状态": file_task.status,
                "进度": file_task.progress,
                "阶段": file_task.phase,
                "输出目录": str(file_task.output_dir) if file_task.output_dir else None,
                "总分": file_task.总分,
                "是否通过": file_task.是否通过,
                "红线触发": file_task.红线触发,
                "未通过原因": list(file_task.未通过原因),
                "评审轮次数": file_task.评审轮次数,
                "错误": file_task.error,
                "错误堆栈": file_task.error_traceback,
                "开始时间": file_task.started_at,
                "完成时间": file_task.finished_at,
                "主要输出文件": _collect_output_files(file_task.output_dir),
            }
            for file_task in batch.files
        ],
    }

    with report_path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)

    batch.batch_report_path = report_path
    return report_path
