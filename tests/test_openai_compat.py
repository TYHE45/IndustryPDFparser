from __future__ import annotations

import json
import os
import sys
import unittest
from unittest import mock

from src.openai_compat import (
    _get_llm_api_key,
    _get_llm_base_url,
    _is_openai_backend,
    _is_disabled_loopback_proxy,
    _api_call_with_retry,
    _sanitized_proxy_env,
    _request_with_responses_api,
    _request_with_chat_completions,
    request_structured_json,
    llm_available,
    _PROXY_ENV_KEYS,
)


# ---------------------------------------------------------------------------
#  helpers
# ---------------------------------------------------------------------------

def _make_exc(status_code):
    """创建一个携带 status_code 的 Exception，用于模拟 openai API 错误。"""
    exc = Exception(f"HTTP {status_code}")
    exc.status_code = status_code
    return exc


# ---------------------------------------------------------------------------
#  TestCase 1  EnvFuncsTests
# ---------------------------------------------------------------------------

class EnvFuncsTests(unittest.TestCase):
    """测试 _get_llm_api_key, _get_llm_base_url, _is_openai_backend。"""

    def test_llm_api_key_priority(self):
        """LLM_API_KEY 和 OPENAI_API_KEY 同时设置时优先返回 LLM_API_KEY。"""
        with mock.patch.dict(
            os.environ,
            {"LLM_API_KEY": "sk-llm", "OPENAI_API_KEY": "sk-openai"},
            clear=True,
        ):
            self.assertEqual(_get_llm_api_key(), "sk-llm")

    def test_falls_back_to_openai_api_key(self):
        """仅设置 OPENAI_API_KEY 时返回该值。"""
        with mock.patch.dict(
            os.environ, {"OPENAI_API_KEY": "sk-fallback"}, clear=True
        ):
            self.assertEqual(_get_llm_api_key(), "sk-fallback")

    def test_returns_empty_when_neither_set(self):
        """两个环境变量均未设置时返回空字符串。"""
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_get_llm_api_key(), "")

    def test_empty_llm_api_key_falls_through(self):
        """LLM_API_KEY 为空字符串时穿透到 OPENAI_API_KEY。"""
        with mock.patch.dict(
            os.environ,
            {"LLM_API_KEY": "", "OPENAI_API_KEY": "sk-foo"},
            clear=True,
        ):
            self.assertEqual(_get_llm_api_key(), "sk-foo")

    def test_base_url_when_set(self):
        """LLM_BASE_URL 已设置时返回其值。"""
        with mock.patch.dict(
            os.environ, {"LLM_BASE_URL": "https://api.openai.com"}, clear=True
        ):
            self.assertEqual(_get_llm_base_url(), "https://api.openai.com")

    def test_base_url_defaults_empty(self):
        """未设置 LLM_BASE_URL 时返回空字符串。"""
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_get_llm_base_url(), "")

    def test_is_openai_backend_true_for_empty_or_openai_com(self):
        """base_url 为空或包含 'openai.com' 时返回 True。"""
        # 空 base_url → 默认 OpenAI
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertTrue(_is_openai_backend())
        # 包含 api.openai.com
        with mock.patch.dict(
            os.environ, {"LLM_BASE_URL": "https://api.openai.com/v1"}, clear=True
        ):
            self.assertTrue(_is_openai_backend())
        # 大小写不敏感
        with mock.patch.dict(
            os.environ, {"LLM_BASE_URL": "https://OPENAI.COM"}, clear=True
        ):
            self.assertTrue(_is_openai_backend())

    def test_is_openai_backend_false_for_other_provider(self):
        """非 OpenAI 后端返回 False；同时记录 substring 误判限制。"""
        with mock.patch.dict(
            os.environ, {"LLM_BASE_URL": "https://api.deepseek.com"}, clear=True
        ):
            self.assertFalse(_is_openai_backend())
        # 已知限制: 简单的 substring 匹配会被 'not-openai.com.evil.com' 欺骗
        with mock.patch.dict(
            os.environ,
            {"LLM_BASE_URL": "https://not-openai.com.evil.com"},
            clear=True,
        ):
            self.assertTrue(
                _is_openai_backend(),
                "已知限制 — 简单 substring 匹配产生误判",
            )


# ---------------------------------------------------------------------------
#  TestCase 2  LLMAvailableTests
# ---------------------------------------------------------------------------

class LLMAvailableTests(unittest.TestCase):
    """测试 llm_available() 的各种状态。"""

    def test_available_when_import_ok_and_key_set(self):
        """OpenAI SDK 可用且 LLM_API_KEY 已设置 → True。"""
        sentinel = object()
        with mock.patch("src.openai_compat.OpenAI", sentinel), mock.patch.dict(
            os.environ, {"LLM_API_KEY": "sk-test"}, clear=True
        ):
            self.assertTrue(llm_available())

    def test_unavailable_when_openai_is_none(self):
        """OpenAI SDK 不可用（None）→ False。"""
        with mock.patch("src.openai_compat.OpenAI", None), mock.patch.dict(
            os.environ, {"LLM_API_KEY": "sk-test"}, clear=True
        ):
            self.assertFalse(llm_available())

    def test_unavailable_when_api_key_empty(self):
        """OpenAI 可用但没有 API key → False。"""
        sentinel = object()
        with mock.patch("src.openai_compat.OpenAI", sentinel), mock.patch.dict(
            os.environ, {}, clear=True
        ):
            self.assertFalse(llm_available())

    def test_openai_api_key_used_as_fallback(self):
        """OPENAI_API_KEY 作为 LLM_API_KEY 的后备。"""
        sentinel = object()
        with mock.patch("src.openai_compat.OpenAI", sentinel), mock.patch.dict(
            os.environ, {"OPENAI_API_KEY": "sk-foo"}, clear=True
        ):
            self.assertTrue(llm_available())


# ---------------------------------------------------------------------------
#  TestCase 3  LoopbackProxyTests
# ---------------------------------------------------------------------------

class LoopbackProxyTests(unittest.TestCase):
    """测试 _is_disabled_loopback_proxy() 纯函数。"""

    def test_localhost_9_disabled(self):
        """127.0.0.1:9 和 localhost:9 均被识别为禁用的回环代理。"""
        self.assertTrue(_is_disabled_loopback_proxy("http://127.0.0.1:9"))
        self.assertTrue(_is_disabled_loopback_proxy("http://localhost:9"))

    def test_wrong_port_not_disabled(self):
        """回环地址但端口非 9 → 不禁用。"""
        self.assertFalse(_is_disabled_loopback_proxy("http://127.0.0.1:8080"))

    def test_wrong_host_not_disabled(self):
        """端口为 9 但非回环地址 → 不禁用。"""
        self.assertFalse(_is_disabled_loopback_proxy("http://192.168.1.1:9"))

    def test_no_port_not_disabled(self):
        """回环地址但没有显式端口 → 不禁用（port 为 None）。"""
        self.assertFalse(_is_disabled_loopback_proxy("http://127.0.0.1"))

    def test_non_url_string(self):
        """非 URL 字符串安全返回 False（urlparse 解析后 hostname 为 None）。"""
        self.assertFalse(_is_disabled_loopback_proxy("not-a-url"))

    def test_ipv6_loopback_not_disabled(self):
        """IPv6 回环地址 ::1 当前不被识别 —— 已知限制。"""
        self.assertFalse(
            _is_disabled_loopback_proxy("http://[::1]:9"),
            "已知限制 — IPv6 loopback 未被检测",
        )


# ---------------------------------------------------------------------------
#  TestCase 4  RetryLogicTests
# ---------------------------------------------------------------------------

class RetryLogicTests(unittest.TestCase):
    """测试 _api_call_with_retry() 重试和指数退避逻辑。

    _api_call_with_retry 在函数体内 ``import openai``，因此需要 patch
    ``sys.modules["openai"]`` 来提供 RateLimitError / APIStatusError 异常类。
    """

    def setUp(self):
        self.mock_openai_mod = mock.MagicMock()
        self.mock_openai_mod.RateLimitError = Exception
        self.mock_openai_mod.APIStatusError = Exception

    # ------------------------------------------------------------------
    def test_success_on_first_attempt(self):
        """第一次调用成功 → 直接返回结果，不调用 sleep。"""
        client_call = mock.MagicMock(return_value="result")
        with mock.patch.dict("sys.modules", {"openai": self.mock_openai_mod}), \
             mock.patch("src.openai_compat.time.sleep") as mock_sleep, \
             mock.patch("src.openai_compat.random.uniform", return_value=0.0):
            result = _api_call_with_retry(client_call)
        self.assertEqual(result, "result")
        mock_sleep.assert_not_called()

    def test_retries_on_429_and_succeeds(self):
        """429 触发重试，最终成功。"""
        client_call = mock.MagicMock(side_effect=[
            _make_exc(429),
            _make_exc(429),
            "result",
        ])
        with mock.patch.dict("sys.modules", {"openai": self.mock_openai_mod}), \
             mock.patch("src.openai_compat.time.sleep") as mock_sleep, \
             mock.patch("src.openai_compat.random.uniform", return_value=0.0):
            result = _api_call_with_retry(client_call)
        self.assertEqual(result, "result")
        self.assertEqual(mock_sleep.call_count, 2)
        self.assertEqual(client_call.call_count, 3)

    def test_retries_on_500_and_succeeds(self):
        """500 触发重试并最终成功。"""
        client_call = mock.MagicMock(side_effect=[
            _make_exc(500),
            "result",
        ])
        with mock.patch.dict("sys.modules", {"openai": self.mock_openai_mod}), \
             mock.patch("src.openai_compat.time.sleep") as mock_sleep, \
             mock.patch("src.openai_compat.random.uniform", return_value=0.0):
            result = _api_call_with_retry(client_call)
        self.assertEqual(result, "result")
        self.assertEqual(mock_sleep.call_count, 1)

    def test_retries_on_502(self):
        """502 Bad Gateway 可重试。"""
        client_call = mock.MagicMock(side_effect=[
            _make_exc(502),
            "result",
        ])
        with mock.patch.dict("sys.modules", {"openai": self.mock_openai_mod}), \
             mock.patch("src.openai_compat.time.sleep") as mock_sleep, \
             mock.patch("src.openai_compat.random.uniform", return_value=0.0):
            result = _api_call_with_retry(client_call)
        self.assertEqual(result, "result")
        self.assertEqual(mock_sleep.call_count, 1)

    def test_retries_on_503(self):
        """503 Service Unavailable 可重试。"""
        client_call = mock.MagicMock(side_effect=[
            _make_exc(503),
            "result",
        ])
        with mock.patch.dict("sys.modules", {"openai": self.mock_openai_mod}), \
             mock.patch("src.openai_compat.time.sleep") as mock_sleep, \
             mock.patch("src.openai_compat.random.uniform", return_value=0.0):
            result = _api_call_with_retry(client_call)
        self.assertEqual(result, "result")
        self.assertEqual(mock_sleep.call_count, 1)

    def test_exceeds_max_retries_raises(self):
        """连续 6 次 429（超过 max_retries=5）→ 最终异常传播，call_count == 6。"""
        client_call = mock.MagicMock(side_effect=[
            _make_exc(429),  # attempt 0
            _make_exc(429),  # attempt 1
            _make_exc(429),  # attempt 2
            _make_exc(429),  # attempt 3
            _make_exc(429),  # attempt 4
            _make_exc(429),  # attempt 5 — >= max_retries, raises
        ])
        with mock.patch.dict("sys.modules", {"openai": self.mock_openai_mod}), \
             mock.patch("src.openai_compat.time.sleep") as mock_sleep, \
             mock.patch("src.openai_compat.random.uniform", return_value=0.0):
            with self.assertRaises(Exception) as ctx:
                _api_call_with_retry(client_call)
            self.assertIn("HTTP 429", str(ctx.exception))
        self.assertEqual(client_call.call_count, 6)
        self.assertEqual(mock_sleep.call_count, 5)

    def test_non_retryable_status_raises_immediately(self):
        """400 Bad Request → 不重试，立即传播异常，sleep 不被调用。"""
        client_call = mock.MagicMock(side_effect=_make_exc(400))
        with mock.patch.dict("sys.modules", {"openai": self.mock_openai_mod}), \
             mock.patch("src.openai_compat.time.sleep") as mock_sleep, \
             mock.patch("src.openai_compat.random.uniform", return_value=0.0):
            with self.assertRaises(Exception) as ctx:
                _api_call_with_retry(client_call)
            self.assertIn("HTTP 400", str(ctx.exception))
        self.assertEqual(client_call.call_count, 1)
        mock_sleep.assert_not_called()

    def test_non_api_exception_raises_immediately(self):
        """非 API 异常（例如 ValueError）→ 立即传播。"""
        client_call = mock.MagicMock(side_effect=ValueError("boom"))
        with mock.patch.dict("sys.modules", {"openai": self.mock_openai_mod}), \
             mock.patch("src.openai_compat.time.sleep") as mock_sleep, \
             mock.patch("src.openai_compat.random.uniform", return_value=0.0):
            with self.assertRaises(ValueError):
                _api_call_with_retry(client_call)
        mock_sleep.assert_not_called()

    def test_backoff_delay_values(self):
        """验证指数退避延迟值: 1.0, 1.5, 2.25（jitter=0 时 base_delay = 1.5^attempt）。"""
        client_call = mock.MagicMock(side_effect=[
            _make_exc(429),  # attempt 0
            _make_exc(429),  # attempt 1
            _make_exc(429),  # attempt 2
            "result",        # attempt 3 — success
        ])
        with mock.patch.dict("sys.modules", {"openai": self.mock_openai_mod}), \
             mock.patch("src.openai_compat.time.sleep") as mock_sleep, \
             mock.patch("src.openai_compat.random.uniform", return_value=0.0):
            _api_call_with_retry(client_call)
        expected_calls = [mock.call(1.0), mock.call(1.5), mock.call(2.25)]
        self.assertEqual(mock_sleep.call_args_list, expected_calls)


# ---------------------------------------------------------------------------
#  TestCase 5  RequestPathsTests
# ---------------------------------------------------------------------------

class RequestPathsTests(unittest.TestCase):
    """测试 _request_with_responses_api 和 _request_with_chat_completions。"""

    def setUp(self):
        self.mock_cm = mock.MagicMock()
        self.mock_client = mock.MagicMock()

        # ----- 供 chat completions 测试使用的 create 返回对象 -----
        self._chat_create_response = mock.MagicMock()
        self._chat_create_response.choices = [mock.MagicMock()]
        self._chat_create_response.choices[0].message.content = '{"x":1}'
        self.mock_client.chat.completions.create.return_value = (
            self._chat_create_response
        )

    # ── _request_with_responses_api ──────────────────────────────────

    def test_responses_api_returns_parsed_json(self):
        """Mock responses.create 返回 output_text='{"a":1}' → 正确解析。"""
        self.mock_client.responses.create.return_value.output_text = '{"a":1}'

        with mock.patch(
            "src.openai_compat._sanitized_proxy_env", return_value=self.mock_cm
        ), mock.patch("src.openai_compat.OpenAI", return_value=self.mock_client), \
           mock.patch("src.openai_compat._get_llm_base_url", return_value="https://api.test.com"), \
           mock.patch("src.openai_compat._get_llm_api_key", return_value="sk-key"):
            result, label = _request_with_responses_api(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "hello"},
                    {"role": "user", "content": '{"q":"test"}'},
                ],
                schema_name="test_schema",
                schema={"type": "object", "properties": {"a": {"type": "integer"}}},
                timeout=30,
            )

        self.assertEqual(result, {"a": 1})
        self.assertEqual(label, "responses")

    def test_responses_api_passes_json_schema_format(self):
        """验证 client.responses.create 传入的 text format 参数正确。"""
        self.mock_client.responses.create.return_value.output_text = '{"a":1}'

        with mock.patch(
            "src.openai_compat._sanitized_proxy_env", return_value=self.mock_cm
        ), mock.patch("src.openai_compat.OpenAI", return_value=self.mock_client), \
           mock.patch("src.openai_compat._get_llm_base_url", return_value=""), \
           mock.patch("src.openai_compat._get_llm_api_key", return_value="sk-key"):
            schema_def = {"type": "object", "properties": {"x": {"type": "number"}}}
            _request_with_responses_api(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "hello"},
                    {"role": "user", "content": "{}"},
                ],
                schema_name="my_schema",
                schema=schema_def,
                timeout=45,
            )

        self.mock_client.responses.create.assert_called_once()
        call_kwargs = self.mock_client.responses.create.call_args.kwargs
        self.assertEqual(call_kwargs["model"], "gpt-4o")
        expected_text = {
            "format": {
                "type": "json_schema",
                "name": "my_schema",
                "schema": schema_def,
                "strict": True,
            }
        }
        self.assertEqual(call_kwargs["text"], expected_text)

    def test_responses_api_uses_sanitized_proxy(self):
        """验证 _sanitized_proxy_env 在 OpenAI() 构造之前被进入。"""
        self.mock_client.responses.create.return_value.output_text = '{"ok":true}'

        call_order = []
        mock_sanitize_cm = mock.MagicMock()

        def _enter_sanitize():
            call_order.append("sanitize_entered")
            return mock_sanitize_cm

        mock_sanitize_patch = mock.patch(
            "src.openai_compat._sanitized_proxy_env", side_effect=_enter_sanitize
        )

        def _construct_openai(*args, **kwargs):
            call_order.append("OpenAI_constructed")
            return self.mock_client

        mock_openai_patch = mock.patch(
            "src.openai_compat.OpenAI", side_effect=_construct_openai
        )

        with mock_sanitize_patch, mock_openai_patch, \
             mock.patch("src.openai_compat._get_llm_base_url", return_value=""), \
             mock.patch("src.openai_compat._get_llm_api_key", return_value="sk-key"):
            _request_with_responses_api(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "hello"},
                    {"role": "user", "content": "{}"},
                ],
                schema_name="s",
                schema={"type": "object"},
                timeout=10,
            )

        self.assertEqual(
            call_order,
            ["sanitize_entered", "OpenAI_constructed"],
            "_sanitized_proxy_env should be entered before OpenAI()",
        )

    # ── _request_with_chat_completions ───────────────────────────────

    def test_json_schema_path_succeeds(self):
        """json_schema 路径成功，返回解析后的 JSON 和标签。"""
        def _fake_retry(client_call, *, max_retries=5):
            return client_call()

        with mock.patch(
            "src.openai_compat._sanitized_proxy_env", return_value=self.mock_cm
        ), mock.patch("src.openai_compat.OpenAI", return_value=self.mock_client), \
           mock.patch("src.openai_compat._get_llm_base_url", return_value=""), \
           mock.patch("src.openai_compat._get_llm_api_key", return_value="sk-key"), \
           mock.patch(
               "src.openai_compat._api_call_with_retry", side_effect=_fake_retry
           ) as mock_retry:
            result, label = _request_with_chat_completions(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "sys prompt"},
                    {"role": "user", "content": "user msg"},
                ],
                schema_name="test",
                schema={"type": "object"},
                timeout=30,
            )

        self.assertEqual(result, {"x": 1})
        self.assertEqual(label, "chat_completions:gpt-4")
        # 验证 response_format 使用了 json_schema
        self.mock_client.chat.completions.create.assert_called_once()
        call_kwargs = self.mock_client.chat.completions.create.call_args.kwargs
        rf = call_kwargs["response_format"]
        self.assertEqual(rf["type"], "json_schema")
        self.assertIn("json_schema", rf)
        self.assertEqual(rf["json_schema"]["name"], "test")

    def test_falls_back_to_json_object_on_failure(self):
        """json_schema 首次调用失败 → 回退到 json_object。"""
        call_counter = [0]

        def _fake_retry(client_call, *, max_retries=5):
            call_counter[0] += 1
            if call_counter[0] == 1:
                raise Exception("json_schema not supported")
            return client_call()

        with mock.patch(
            "src.openai_compat._sanitized_proxy_env", return_value=self.mock_cm
        ), mock.patch("src.openai_compat.OpenAI", return_value=self.mock_client), \
           mock.patch("src.openai_compat._get_llm_base_url", return_value=""), \
           mock.patch("src.openai_compat._get_llm_api_key", return_value="sk-key"), \
           mock.patch(
               "src.openai_compat._api_call_with_retry", side_effect=_fake_retry
           ) as mock_retry:
            result, label = _request_with_chat_completions(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "sys prompt"},
                    {"role": "user", "content": "user msg"},
                ],
                schema_name="test",
                schema={"type": "object"},
                timeout=30,
            )

        self.assertEqual(result, {"x": 1})
        self.assertEqual(mock_retry.call_count, 2)
        # 第二次调用（回退）的 lambda 使用了 json_object
        create_calls = self.mock_client.chat.completions.create.call_args_list
        self.assertEqual(len(create_calls), 1)  # 只有回退路径成功调用了 create
        fallback_rf = create_calls[0].kwargs["response_format"]
        self.assertEqual(fallback_rf, {"type": "json_object"})

    def test_fallback_injects_schema_into_system_message(self):
        """回退时将 schema JSON 注入了 system message。"""
        call_counter = [0]
        schema_def = {"type": "object", "properties": {"k": {"type": "string"}}}

        def _fake_retry(client_call, *, max_retries=5):
            call_counter[0] += 1
            if call_counter[0] == 1:
                raise Exception("json_schema not supported")
            return client_call()

        with mock.patch(
            "src.openai_compat._sanitized_proxy_env", return_value=self.mock_cm
        ), mock.patch("src.openai_compat.OpenAI", return_value=self.mock_client), \
           mock.patch("src.openai_compat._get_llm_base_url", return_value=""), \
           mock.patch("src.openai_compat._get_llm_api_key", return_value="sk-key"), \
           mock.patch(
               "src.openai_compat._api_call_with_retry", side_effect=_fake_retry
           ):
            _request_with_chat_completions(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "original system prompt"},
                    {"role": "user", "content": "user input"},
                ],
                schema_name="my_schema",
                schema=schema_def,
                timeout=30,
            )

        # 回退路径调用了 create
        create_kwargs = self.mock_client.chat.completions.create.call_args.kwargs
        fallback_messages = create_kwargs["messages"]
        sys_content = fallback_messages[0]["content"]
        self.assertIn("original system prompt", sys_content)
        self.assertIn(json.dumps(schema_def, ensure_ascii=False), sys_content)
        self.assertEqual(fallback_messages[1]["content"], "user input")

    def test_json_decode_error_on_empty_content(self):
        """response.choices[0].message.content 为空 → json.JSONDecodeError（函数无保护）。"""
        # 返回 content 为空的响应
        empty_response = mock.MagicMock()
        empty_response.choices = [mock.MagicMock()]
        empty_response.choices[0].message.content = ""  # 使得 content or "" 为 ""

        with mock.patch(
            "src.openai_compat._sanitized_proxy_env", return_value=self.mock_cm
        ), mock.patch("src.openai_compat.OpenAI", return_value=self.mock_client), \
           mock.patch("src.openai_compat._get_llm_base_url", return_value=""), \
           mock.patch("src.openai_compat._get_llm_api_key", return_value="sk-key"), \
           mock.patch(
               "src.openai_compat._api_call_with_retry", return_value=empty_response
           ):
            with self.assertRaises(json.JSONDecodeError):
                _request_with_chat_completions(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "sys"},
                        {"role": "user", "content": "user"},
                    ],
                    schema_name="s",
                    schema={"type": "object"},
                    timeout=30,
                )


# ---------------------------------------------------------------------------
#  TestCase 6  OrchestratorTests
# ---------------------------------------------------------------------------

class OrchestratorTests(unittest.TestCase):
    """测试 request_structured_json() 编排逻辑。"""

    _DEFAULT_KWARGS = dict(
        model="gpt-4o",
        system_prompt="test system prompt",
        user_payload={"key": "value"},
        schema_name="test_schema",
        schema={"type": "object"},
        timeout=30.0,
    )

    def _call_orchestrator(self, **overrides):
        kwargs = {**self._DEFAULT_KWARGS, **overrides}
        return request_structured_json(**kwargs)

    # ------------------------------------------------------------------

    def test_raises_runtime_error_when_openai_is_none(self):
        """OpenAI 为 None 时直接抛出 RuntimeError。"""
        with mock.patch("src.openai_compat.OpenAI", None):
            with self.assertRaises(RuntimeError) as ctx:
                self._call_orchestrator()
            self.assertIn("OpenAI SDK is unavailable", str(ctx.exception))

    def test_openai_backend_responses_succeeds(self):
        """OpenAI 后端 + responses API 成功 → 返回 responses 结果。"""
        expected = ({"a": 1}, "responses")
        with mock.patch("src.openai_compat.OpenAI", object()), \
             mock.patch("src.openai_compat._is_openai_backend", return_value=True), \
             mock.patch(
                 "src.openai_compat._request_with_responses_api",
                 return_value=expected,
             ) as mock_responses, \
             mock.patch(
                 "src.openai_compat._request_with_chat_completions"
             ) as mock_chat, \
             mock.patch.dict(os.environ, {"OPENAI_CHAT_MODEL": "gpt-4-chat"}):
            result, label = self._call_orchestrator()
        self.assertEqual((result, label), expected)
        mock_responses.assert_called_once()
        mock_chat.assert_not_called()

    def test_openai_backend_responses_fails_falls_back_to_chat(self):
        """responses API 失败 → 回退到 chat completions。"""
        chat_result = ({"b": 2}, "chat_completions:gpt-4-chat")
        with mock.patch("src.openai_compat.OpenAI", object()), \
             mock.patch("src.openai_compat._is_openai_backend", return_value=True), \
             mock.patch(
                 "src.openai_compat._request_with_responses_api",
                 side_effect=Exception("responses failed"),
             ) as mock_responses, \
             mock.patch(
                 "src.openai_compat._request_with_chat_completions",
                 return_value=chat_result,
             ) as mock_chat, \
             mock.patch.dict(os.environ, {"OPENAI_CHAT_MODEL": "gpt-4-chat"}):
            result, label = self._call_orchestrator()
        self.assertEqual((result, label), chat_result)
        mock_responses.assert_called_once()
        mock_chat.assert_called_once()
        # 验证 chat 使用了正确的 model
        chat_call_kwargs = mock_chat.call_args.kwargs
        self.assertEqual(chat_call_kwargs["model"], "gpt-4-chat")

    def test_non_openai_backend_skips_responses(self):
        """非 OpenAI 后端 → 跳过 responses API，直接走 chat completions。"""
        chat_result = ({"c": 3}, "chat_completions:gpt-4o")
        with mock.patch("src.openai_compat.OpenAI", object()), \
             mock.patch("src.openai_compat._is_openai_backend", return_value=False), \
             mock.patch(
                 "src.openai_compat._request_with_responses_api"
             ) as mock_responses, \
             mock.patch(
                 "src.openai_compat._request_with_chat_completions",
                 return_value=chat_result,
             ) as mock_chat, \
             mock.patch.dict(os.environ, {}, clear=True):  # OPENAI_CHAT_MODEL not set → fallback to model
            result, label = self._call_orchestrator()
        self.assertEqual((result, label), chat_result)
        mock_responses.assert_not_called()
        mock_chat.assert_called_once()

    def test_both_paths_fail_raises_combined_error(self):
        """responses 和 chat 均失败 → 抛出合并的 RuntimeError。"""
        responses_exc = Exception("responses boom")
        chat_exc = Exception("chat boom")
        with mock.patch("src.openai_compat.OpenAI", object()), \
             mock.patch("src.openai_compat._is_openai_backend", return_value=True), \
             mock.patch(
                 "src.openai_compat._request_with_responses_api",
                 side_effect=responses_exc,
             ), \
             mock.patch(
                 "src.openai_compat._request_with_chat_completions",
                 side_effect=chat_exc,
             ), \
             mock.patch.dict(os.environ, {"OPENAI_CHAT_MODEL": "gpt-4-chat"}):
            with self.assertRaises(RuntimeError) as ctx:
                self._call_orchestrator()
        msg = str(ctx.exception)
        self.assertIn("structured request failed for schema=test_schema", msg)
        self.assertIn("responses backend failed:", msg)
        self.assertIn("chat backend failed:", msg)
        self.assertIn("responses boom", msg)
        self.assertIn("chat boom", msg)
        self.assertIn("responses_model=gpt-4o", msg)
        self.assertIn("chat_model=gpt-4-chat", msg)


# ---------------------------------------------------------------------------
#  TestCase 7  ProxySanitizeTests
# ---------------------------------------------------------------------------

class ProxySanitizeTests(unittest.TestCase):
    """测试 _sanitized_proxy_env() 上下文管理器。

    注意：Windows 上 os.environ 大小写不敏感，HTTP_PROXY 和 http_proxy 可能冲突。
    """

    def test_no_proxy_keys_yields_unchanged(self):
        """没有任何代理环境变量 → enter/exit 无变化。"""
        with mock.patch.dict(os.environ, {}, clear=True):
            with _sanitized_proxy_env():
                pass
            # environment should still be empty
            self.assertEqual(os.getenv("HTTP_PROXY"), None)

    def test_disabled_loopback_removed_and_restored(self):
        """禁用的回环代理在内部被移除，退出后恢复。"""
        with mock.patch.dict(
            os.environ, {"HTTP_PROXY": "http://127.0.0.1:9"}, clear=True
        ):
            self.assertEqual(os.getenv("HTTP_PROXY"), "http://127.0.0.1:9")
            with _sanitized_proxy_env():
                self.assertIsNone(
                    os.getenv("HTTP_PROXY"),
                    "disabled loopback proxy should be removed inside the context",
                )
            self.assertEqual(
                os.getenv("HTTP_PROXY"),
                "http://127.0.0.1:9",
                "proxy should be restored after the context exits",
            )

    def test_non_disabled_proxy_preserved(self):
        """非禁用代理在上下文内保持不变。"""
        with mock.patch.dict(
            os.environ, {"HTTPS_PROXY": "http://proxy.corp.com:8080"}, clear=True
        ):
            with _sanitized_proxy_env():
                self.assertEqual(
                    os.getenv("HTTPS_PROXY"), "http://proxy.corp.com:8080"
                )
            self.assertEqual(os.getenv("HTTPS_PROXY"), "http://proxy.corp.com:8080")

    def test_mixed_only_disabled_removed(self):
        """混合场景中仅禁用代理被移除。"""
        with mock.patch.dict(
            os.environ,
            {
                "HTTP_PROXY": "http://127.0.0.1:9",          # disabled
                "HTTPS_PROXY": "http://proxy.corp.com:8080",  # valid
            },
            clear=True,
        ):
            with _sanitized_proxy_env():
                self.assertIsNone(os.getenv("HTTP_PROXY"))
                self.assertEqual(
                    os.getenv("HTTPS_PROXY"), "http://proxy.corp.com:8080"
                )
            # 退出后均恢复
            self.assertEqual(os.getenv("HTTP_PROXY"), "http://127.0.0.1:9")
            self.assertEqual(
                os.getenv("HTTPS_PROXY"), "http://proxy.corp.com:8080"
            )

    def test_restore_on_exception(self):
        """上下文内抛出异常时 finally 仍会恢复代理。"""
        with mock.patch.dict(
            os.environ, {"ALL_PROXY": "http://127.0.0.1:9"}, clear=True
        ):
            try:
                with _sanitized_proxy_env():
                    self.assertIsNone(os.getenv("ALL_PROXY"))
                    raise ValueError("simulated error")
            except ValueError:
                pass
            self.assertEqual(
                os.getenv("ALL_PROXY"),
                "http://127.0.0.1:9",
                "proxy should be restored even after an exception",
            )


# ---------------------------------------------------------------------------
#  entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
