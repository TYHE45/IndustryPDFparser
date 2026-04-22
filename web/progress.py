"""进度事件定义与 SSE 编码工具。"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

# 事件类型常量（中文）
EVENT_批次开始 = "批次开始"
EVENT_文件开始 = "文件开始"
EVENT_阶段进度 = "阶段进度"
EVENT_评审轮次 = "评审轮次"
EVENT_文件完成 = "文件完成"
EVENT_文件失败 = "文件失败"
EVENT_批次完成 = "批次完成"
EVENT_批次失败 = "批次失败"
EVENT_心跳 = "心跳"


def make_event(event_type: str, batch_id: str, **payload: Any) -> dict[str, Any]:
    """构造一个标准事件字典，自动附加事件类型、批次ID、时间三个字段。"""
    event: dict[str, Any] = {
        "事件类型": event_type,
        "批次ID": batch_id,
        "时间": datetime.now().isoformat(timespec="seconds"),
    }
    event.update(payload)
    return event


def encode_sse(event: dict[str, Any]) -> str:
    """将事件字典编码为 SSE 传输格式。"""
    data = json.dumps(event, ensure_ascii=False)
    return f"event: progress\ndata: {data}\n\n"
