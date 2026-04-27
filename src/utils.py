from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable


def normalize_line(line: str) -> str:
    line = line.replace("\u3000", " ")
    line = re.sub(r"\s+", " ", line).strip()
    return line


def normalize_cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def safe_write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_output_dir_from_parts(
    source_name: str,
    parent_parts: tuple[str, ...],
    base_output_dir: Path,
) -> Path:
    if parent_parts:
        return base_output_dir.joinpath(*parent_parts, source_name)
    return base_output_dir / source_name


def dedupe_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


import os


PIPELINE_LOCK_FILENAME = ".pipeline.lock"


def try_acquire_pipeline_lock(output_dir: Path) -> str | None:
    """Try to acquire a PID lock on *output_dir*.

    Returns ``None`` on success or an error message string if another process
    holds the lock.  The lock file contains the PID of the owning process and
    is cleaned up by :func:`release_pipeline_lock`.
    """
    lock_path = output_dir / PIPELINE_LOCK_FILENAME
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        if lock_path.exists():
            existing = lock_path.read_text(encoding="utf-8").strip()
            if existing and _pid_is_alive(int(existing)):
                return f"输出目录已被进程 {existing} 锁定：{lock_path}"
            lock_path.unlink(missing_ok=True)
        lock_path.write_text(str(os.getpid()), encoding="utf-8")
        return None
    except (OSError, ValueError) as exc:
        return f"无法操作管道锁文件：{exc}"


def release_pipeline_lock(output_dir: Path) -> None:
    """Release the PID lock on *output_dir* (no-op if not owned by us)."""
    lock_path = output_dir / PIPELINE_LOCK_FILENAME
    try:
        if lock_path.exists() and lock_path.read_text(encoding="utf-8").strip() == str(os.getpid()):
            lock_path.unlink(missing_ok=True)
    except OSError:
        pass


def _pid_is_alive(pid: int) -> bool:
    """Check whether *pid* refers to a running process (best-effort)."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False
