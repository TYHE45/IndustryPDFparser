from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest import mock

from src.utils import (
    _pid_is_alive,
    build_output_dir_from_parts,
    dedupe_keep_order,
    normalize_cell,
    normalize_line,
    safe_write_json,
)


class PidIsAliveTests(unittest.TestCase):
    """Cross-platform PID liveness probe.

    Phase 4.5 P0-1 fix: on Windows ``os.kill(pid, 0)`` actually delivers
    ``CTRL_C_EVENT``; the implementation must never reach that path on ``nt``.
    The remaining utility helpers in ``src/utils.py`` are covered by the
    Phase 5 P0 follow-up (``utils.py`` full unit-test backfill).
    """

    def test_zero_pid_returns_false(self):
        self.assertFalse(_pid_is_alive(0))

    def test_negative_pid_returns_false(self):
        self.assertFalse(_pid_is_alive(-1))

    def test_current_pid_returns_true(self):
        self.assertTrue(_pid_is_alive(os.getpid()))

    def test_unlikely_pid_returns_false(self):
        # A near-32-bit PID, almost certainly not running on any platform.
        self.assertFalse(_pid_is_alive(2_000_000_000))

    @unittest.skipIf(os.name == "nt", "POSIX-only: Windows takes the ctypes branch")
    def test_posix_uses_os_kill_signal_zero(self):
        """On POSIX, the function must call ``os.kill(pid, 0)`` and nothing else."""
        with mock.patch("src.utils.os.kill") as kill_mock:
            kill_mock.return_value = None
            self.assertTrue(_pid_is_alive(os.getpid()))
            kill_mock.assert_called_once_with(os.getpid(), 0)

    @unittest.skipIf(os.name == "nt", "POSIX-only: Windows takes the ctypes branch")
    def test_posix_translates_oserror_to_false(self):
        with mock.patch("src.utils.os.kill", side_effect=ProcessLookupError):
            self.assertFalse(_pid_is_alive(123456))


class UtilsPureFunctionsTests(unittest.TestCase):
    """单元测试：src/utils.py 纯函数（Phase 5 补充覆盖）。

    覆盖 normalize_line / normalize_cell / safe_write_json /
    build_output_dir_from_parts / dedupe_keep_order 五个函数，
    每条至少 2 例（正常 + 边界）。
    """

    # ═══════════════════════════════════════════════════════════════════
    # normalize_line
    # ═══════════════════════════════════════════════════════════════════

    def test_normalize_line_全角空格转半角(self):
        """全角空格 ``\\u3000`` 替换为半角空格 `` ``。"""
        self.assertEqual(normalize_line("a　b"), "a b")

    def test_normalize_line_连续空白压缩为单空格(self):
        """多个空白字符（空格 / Tab）折叠为单个空格。"""
        self.assertEqual(normalize_line("a   b\tc"), "a b c")

    def test_normalize_line_首尾trim(self):
        """首尾空白被移除。"""
        self.assertEqual(normalize_line("  hello  "), "hello")

    def test_normalize_line_综合场景(self):
        """全角空格 + 多空白 + 首尾空白同时出现。"""
        self.assertEqual(normalize_line(" 　 a  　 b \t "), "a b")

    def test_normalize_line_空字符串(self):
        """空字符串入参，返回空字符串。"""
        self.assertEqual(normalize_line(""), "")

    # ═══════════════════════════════════════════════════════════════════
    # normalize_cell
    # ═══════════════════════════════════════════════════════════════════

    def test_normalize_cell_None返回空字符串(self):
        """``None`` 统一转为空字符串。"""
        self.assertEqual(normalize_cell(None), "")

    def test_normalize_cell_换行替换为空格(self):
        """换行符 ``\\n`` 替换为空格。"""
        self.assertEqual(normalize_cell("a\nb"), "a b")

    def test_normalize_cell_全角空白压缩trim综合(self):
        """全角空格 + 换行 + 多空白 + 首尾空白同时出现。"""
        self.assertEqual(normalize_cell(" 　 a \n 　 b \t "), "a b")

    def test_normalize_cell_非字符串类型(self):
        """整型等非字符串值通过 ``str()`` 转为字符串。"""
        self.assertEqual(normalize_cell(123), "123")

    # ═══════════════════════════════════════════════════════════════════
    # safe_write_json
    # ═══════════════════════════════════════════════════════════════════

    def test_safe_write_json_基本写入(self):
        """mock Path.write_text，断言 encoding / indent / JSON 正确性。"""
        payload = {"key": "value", "num": 42}
        mock_path = mock.MagicMock(spec=Path)
        safe_write_json(mock_path, payload)

        mock_path.write_text.assert_called_once()
        call_args = mock_path.write_text.call_args
        # encoding 参数
        self.assertEqual(call_args[1]["encoding"], "utf-8")
        # JSON 内容可反序列化
        written: str = call_args[0][0]
        parsed = json.loads(written)
        self.assertEqual(parsed, payload)
        # indent=2 应产生换行 + 两空格缩进
        self.assertIn("\n  ", written)

    def test_safe_write_json_中文嵌套复杂payload(self):
        """含中文和嵌套结构的 payload，验证 ensure_ascii=False 生效。"""
        payload = {
            "姓名": "张三",
            "分数": [95, 87, 92],
            "信息": {"城市": "北京", "备注": "无"},
        }
        mock_path = mock.MagicMock(spec=Path)
        safe_write_json(mock_path, payload)

        mock_path.write_text.assert_called_once()
        call_args = mock_path.write_text.call_args
        self.assertEqual(call_args[1]["encoding"], "utf-8")
        written: str = call_args[0][0]
        parsed = json.loads(written)
        self.assertEqual(parsed, payload)
        # ensure_ascii=False：中文直接出现，没有 \uXXXX 转义
        self.assertIn("张三", written)
        self.assertIn("北京", written)
        self.assertNotIn("\\u", written)

    # ═══════════════════════════════════════════════════════════════════
    # build_output_dir_from_parts
    # ═══════════════════════════════════════════════════════════════════

    def test_build_output_dir_from_parts_有parent_parts(self):
        """parent_parts 非空时，拼接为 base/p1/p2/source。"""
        base = Path("/base/output")
        result = build_output_dir_from_parts("src_name", ("p1", "p2"), base)
        self.assertEqual(result, Path("/base/output/p1/p2/src_name"))

    def test_build_output_dir_from_parts_parent_parts为空元组(self):
        """parent_parts 为空元组时，返回 base/source。"""
        base = Path("/base/output")
        result = build_output_dir_from_parts("src_name", (), base)
        self.assertEqual(result, Path("/base/output/src_name"))

    # ═══════════════════════════════════════════════════════════════════
    # dedupe_keep_order
    # ═══════════════════════════════════════════════════════════════════

    def test_dedupe_keep_order_保持首次出现顺序(self):
        """重复元素只保留首次出现的，顺序不变。"""
        result = dedupe_keep_order(["c", "a", "b", "a", "c", "d"])
        self.assertEqual(result, ["c", "a", "b", "d"])

    def test_dedupe_keep_order_跳过空字符串(self):
        """空字符串 ``""`` 被过滤掉。"""
        result = dedupe_keep_order(["a", "", "b", "", "a", ""])
        self.assertEqual(result, ["a", "b"])

    def test_dedupe_keep_order_空可迭代对象(self):
        """空列表 / 空元组返回空列表。"""
        self.assertEqual(dedupe_keep_order([]), [])
        self.assertEqual(dedupe_keep_order(()), [])


if __name__ == "__main__":
    unittest.main()
