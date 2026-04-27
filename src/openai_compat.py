from __future__ import annotations

import json
import os
import random
import time
from contextlib import contextmanager
from typing import Any
from urllib.parse import urlparse

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None  # type: ignore


_PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "http_proxy",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
)


def _get_llm_api_key() -> str:
    return os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""


def _get_llm_base_url() -> str:
    return os.getenv("LLM_BASE_URL", "")


def _api_call_with_retry(client_call, *, max_retries: int = 5) -> Any:
    """Call with exponential backoff + jitter for retryable errors (429, 5xx)."""
    import openai

    for attempt in range(max_retries + 1):
        try:
            return client_call()
        except (openai.RateLimitError, openai.APIStatusError) as exc:
            if attempt >= max_retries:
                raise
            status = getattr(exc, "status_code", 0)
            if status not in (429, 500, 502, 503):
                raise
            base_delay = 1.5 ** attempt
            jitter = random.uniform(0, base_delay * 0.5)
            delay = base_delay + jitter
            time.sleep(delay)


def _is_openai_backend() -> bool:
    """Check if we're using the real OpenAI API (vs an OpenAI-compatible provider like DeepSeek)."""
    base = _get_llm_base_url()
    if not base:
        return True  # default is OpenAI
    return "openai.com" in base.lower()


def llm_available() -> bool:
    return OpenAI is not None and bool(_get_llm_api_key())


def request_structured_json(
    *,
    model: str,
    system_prompt: str,
    user_payload: dict[str, Any],
    schema_name: str,
    schema: dict[str, Any],
    timeout: float = 60.0,
) -> tuple[dict[str, Any], str]:
    if OpenAI is None:
        raise RuntimeError("OpenAI SDK is unavailable.")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]

    # Responses API is OpenAI-only; skip straight to chat completions for other providers
    if _is_openai_backend():
        try:
            return _request_with_responses_api(
                model=model,
                messages=messages,
                schema_name=schema_name,
                schema=schema,
                timeout=timeout,
            )
        except Exception as exc:
            responses_error = exc
    else:
        responses_error = None

    chat_model = os.getenv("OPENAI_CHAT_MODEL") or model
    try:
        return _request_with_chat_completions(
            model=chat_model,
            messages=messages,
            schema_name=schema_name,
            schema=schema,
            timeout=timeout,
        )
    except Exception as exc:
        if responses_error is None:
            raise
        raise RuntimeError(
            f"structured request failed for schema={schema_name}, responses_model={model}, chat_model={chat_model}; "
            f"responses backend failed: {responses_error}; chat backend failed: {exc}"
        ) from exc


def _request_with_responses_api(
    *,
    model: str,
    messages: list[dict[str, str]],
    schema_name: str,
    schema: dict[str, Any],
    timeout: float,
) -> tuple[dict[str, Any], str]:
    with _sanitized_proxy_env():
        client = OpenAI(
            timeout=timeout,
            base_url=_get_llm_base_url() or None,
            api_key=_get_llm_api_key() or None,
        )
        response = client.responses.create(
            model=model,
            input=messages,
            text={"format": {"type": "json_schema", "name": schema_name, "schema": schema, "strict": True}},
        )
    return json.loads(response.output_text), "responses"


def _request_with_chat_completions(
    *,
    model: str,
    messages: list[dict[str, str]],
    schema_name: str,
    schema: dict[str, Any],
    timeout: float,
) -> tuple[dict[str, Any], str]:
    with _sanitized_proxy_env():
        client = OpenAI(
            timeout=timeout,
            base_url=_get_llm_base_url() or None,
            api_key=_get_llm_api_key() or None,
        )

        # Try strict json_schema first (OpenAI); fall back to json_object for
        # compatible providers (DeepSeek, etc.) that don't support json_schema.
        try:
            response = _api_call_with_retry(
                lambda: client.chat.completions.create(
                    model=model,
                    messages=messages,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {"name": schema_name, "schema": schema, "strict": True},
                    },
                    max_completion_tokens=4000,
                )
            )
        except Exception:
            schema_hint = (
                f"\n\nYour output must be valid JSON only, conforming to this schema: "
                f"{json.dumps(schema, ensure_ascii=False)}"
            )
            response = _api_call_with_retry(
                lambda: client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": messages[0]["content"] + schema_hint},
                        *messages[1:],
                    ],
                    response_format={"type": "json_object"},
                    max_completion_tokens=4000,
                )
            )
    content = response.choices[0].message.content or ""
    return json.loads(content), f"chat_completions:{model}"


@contextmanager
def _sanitized_proxy_env():
    removed: dict[str, str] = {}
    for key in _PROXY_ENV_KEYS:
        value = os.getenv(key)
        if value and _is_disabled_loopback_proxy(value):
            removed[key] = value
            os.environ.pop(key, None)
    try:
        yield
    finally:
        os.environ.update(removed)


def _is_disabled_loopback_proxy(value: str) -> bool:
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    port = parsed.port
    return host in {"127.0.0.1", "localhost"} and port == 9
