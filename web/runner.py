"""单文件处理执行封装。"""
from __future__ import annotations

import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable

_REQUIRED_PIPELINE_KEYS = (
    "document",
    "markdown",
    "summary",
    "tags",
    "process_log",
    "review",
    "review_rounds",
)

from config import AppConfig
from src.exporter import export_all
from src.pipeline import collect_failure_reasons, run_iterative_pipeline
from src.utils import build_output_dir_from_parts, safe_write_json

from web.progress import (
    EVENT_阶段进度,
    EVENT_评审轮次,
    EVENT_文件完成,
    EVENT_文件失败,
    EVENT_文件开始,
    make_event,
)
from web.task_manager import Batch, FileTask


def _build_batch_output_dir(file_task: FileTask, batch: Batch, output_root: str) -> Path:
    source_name = Path(file_task.safe_name).stem or Path(file_task.name).stem or file_task.file_id
    return build_output_dir_from_parts(
        source_name,
        file_task.逻辑父目录层级,
        Path(output_root),
    )


def run_single_file(
    file_task: FileTask,
    batch: Batch,
    output_root: str,
    publish_event: Callable[[str, dict], None],
) -> bool:
    """执行单个文件的完整处理流程，返回是否成功。"""
    batch_id = batch.batch_id
    try:
        output_dir = _build_batch_output_dir(file_task, batch, output_root)
        file_task.output_dir = output_dir
        file_task.status = "处理中"
        file_task.started_at = datetime.now().isoformat(timespec="seconds")

        # 文件开始
        publish_event(
            batch_id,
            make_event(
                EVENT_文件开始,
                batch_id,
                file_id=file_task.file_id,
                文件名=file_task.name,
                来源类型=file_task.来源类型,
                来源层级=list(file_task.来源层级),
                相对路径=file_task.相对路径,
                采集方式=file_task.采集方式,
                输出目录=str(output_dir),
            ),
        )

        # 解析阶段
        file_task.progress = 5.0
        file_task.phase = "解析"
        publish_event(
            batch_id,
            make_event(
                EVENT_阶段进度,
                batch_id,
                file_id=file_task.file_id,
                阶段="解析",
                进度=5.0,
            ),
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        config = AppConfig(input_path=file_task.uploaded_path, output_dir=output_dir)
        result = run_iterative_pipeline(config)

        # 契约校验：pipeline 返回结果必须包含所有下游依赖的键。
        missing_keys = [k for k in _REQUIRED_PIPELINE_KEYS if k not in result]
        if missing_keys:
            raise RuntimeError(f"pipeline 返回结果缺少必需字段: {missing_keys}")

        # 评审轮次事件
        review_rounds = result.get("review_rounds", []) or []
        for idx, round_info in enumerate(review_rounds, start=1):
            publish_event(
                batch_id,
                make_event(
                    EVENT_评审轮次,
                    batch_id,
                    file_id=file_task.file_id,
                    轮次=idx,
                    信息=round_info if isinstance(round_info, dict) else {"数据": round_info},
                ),
            )
        file_task.评审轮次数 = len(review_rounds)

        # 导出阶段
        file_task.progress = 90.0
        file_task.phase = "导出"
        publish_event(
            batch_id,
            make_event(
                EVENT_阶段进度,
                batch_id,
                file_id=file_task.file_id,
                阶段="导出",
                进度=90.0,
            ),
        )

        export_all(
            output_dir,
            result["document"],
            result["markdown"],
            result["summary"],
            result["tags"],
            result["process_log"],
        )
        safe_write_json(output_dir / "review.json", result["review"])
        safe_write_json(output_dir / "review_rounds.json", result["review_rounds"])

        review = result.get("review") or {}
        file_task.总分 = review.get("总分")
        file_task.是否通过 = review.get("是否通过")
        file_task.红线触发 = review.get("红线触发")
        file_task.未通过原因 = collect_failure_reasons(review) if file_task.是否通过 is False else []
        file_task.status = "已完成"
        file_task.progress = 100.0
        file_task.phase = "完成"
        file_task.finished_at = datetime.now().isoformat(timespec="seconds")

        publish_event(
            batch_id,
            make_event(
                EVENT_文件完成,
                batch_id,
                file_id=file_task.file_id,
                文件名=file_task.name,
                总分=file_task.总分,
                是否通过=file_task.是否通过,
                红线触发=file_task.红线触发,
                未通过原因=list(file_task.未通过原因),
                评审轮次数=file_task.评审轮次数,
                输出目录=str(output_dir),
            ),
        )
        return True

    except Exception as exc:
        tb = traceback.format_exc()
        file_task.status = "失败"
        file_task.progress = 100.0
        file_task.phase = "失败"
        file_task.error = str(exc)
        file_task.error_traceback = tb
        file_task.finished_at = datetime.now().isoformat(timespec="seconds")
        publish_event(
            batch_id,
            make_event(
                EVENT_文件失败,
                batch_id,
                file_id=file_task.file_id,
                文件名=file_task.name,
                错误=str(exc),
                错误堆栈=tb,
            ),
        )
        return False
