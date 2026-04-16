from __future__ import annotations

import json
import os
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


def llm_available() -> bool:
    return OpenAI is not None and bool(os.getenv("OPENAI_API_KEY"))


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
    responses_error: Exception | None = None
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

    chat_model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
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
        client = OpenAI(timeout=timeout)
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
        client = OpenAI(timeout=timeout)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": schema, "strict": True},
            },
            max_completion_tokens=4000,
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
