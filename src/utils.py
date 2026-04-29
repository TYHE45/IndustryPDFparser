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
    """Check whether *pid* refers to a running process (best-effort, cross-platform).

    On POSIX systems, signal 0 is a null signal and is the standard idiom for
    probing process liveness without delivering anything.  On Windows, however,
    Python's ``os.kill(pid, 0)`` is mapped to ``CTRL_C_EVENT`` and would *actually*
    send Ctrl+C to the target process group — which is destructive and unsuitable
    for a liveness probe.  This function dispatches to a Win32 ``OpenProcess``
    based probe on Windows and keeps the POSIX null-signal idiom elsewhere.
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        return _pid_is_alive_windows(pid)
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _pid_is_alive_windows(pid: int) -> bool:
    """Windows-only PID liveness probe via ``OpenProcess``; never delivers signals.

    Returns ``True`` if the OS reports a still-running process for *pid*.
    Conservatively returns ``True`` on access-denied (the process exists but
    we cannot query its exit code) so we never steal a lock from a live owner.
    Returns ``False`` for non-existent PIDs and any other failure mode.
    """
    import ctypes
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    ERROR_ACCESS_DENIED = 5
    STILL_ACTIVE = 259

    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.GetLastError.restype = wintypes.DWORD

    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        err = kernel32.GetLastError()
        # PID gone → False; access-denied → conservatively assume alive so we
        # never break someone else's lock.  Any other error → treat as gone.
        if err == ERROR_ACCESS_DENIED:
            return True
        return False
    try:
        exit_code = wintypes.DWORD()
        if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return exit_code.value == STILL_ACTIVE
        return True  # query failed but handle was valid — be conservative
    finally:
        kernel32.CloseHandle(handle)
