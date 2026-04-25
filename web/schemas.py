"""Pydantic 数据模型定义。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class FileInfo(BaseModel):
    file_id: str
    name: str
    size: int
    source_label: str | None = None
    relative_path: str | None = None


class BatchCreateResponse(BaseModel):
    batch_id: str
    source_type: str | None = None
    source_label: str | None = None
    files: list[FileInfo]


class BatchFileStatus(BaseModel):
    file_id: str
    name: str
    size: int
    status: str
    progress: float
    phase: str
    source_type: str | None = None
    source_layers: list[str] = Field(default_factory=list)
    source_relative_path: str | None = None
    acquisition_mode: str | None = None
    总分: float | str | None = None
    是否通过: bool | None = None
    红线触发: bool | None = None
    未通过原因: list[str] = Field(default_factory=list)
    评审轮次数: int = 0
    error: str | None = None
    error_traceback: str | None = None
    output_dir: str | None = None


class BatchStatus(BaseModel):
    batch_id: str
    status: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    output_root: str = "output"
    source_type: str | None = None
    source_label: str | None = None
    report_ready: bool = False
    batch_report_path: str | None = None
    files: list[BatchFileStatus]


class StartBatchRequest(BaseModel):
    output_root: str = Field(default="output")
