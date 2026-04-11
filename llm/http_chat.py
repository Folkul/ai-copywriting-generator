"""OpenAI 兼容的 Chat Completions HTTP 调用。"""
from __future__ import annotations

import json
from typing import Any, Optional

import requests

from config import CAPTION_MAX_TOKENS, LLM_REQUEST_TIMEOUT


def extract_openai_error_message(response: requests.Response) -> str:
    try:
        payload: dict[str, Any] = response.json()
        err = payload.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
        if isinstance(err, str):
            return err
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    text = response.text or ""
    return text[:800] if text else f"HTTP {response.status_code}"


def post_chat_completion(
    url: str,
    api_key: str,
    model: str,
    user_message: str,
    temperature: float,
    *,
    max_tokens: Optional[int] = None,
    verbose: bool = True,
) -> Optional[str]:
    """发送单条 user 消息，返回 assistant 文本。"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    mt = max_tokens if max_tokens is not None else CAPTION_MAX_TOKENS
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": user_message}],
        "temperature": temperature,
        "max_tokens": mt,
    }
    try:
        response = requests.post(
            url,
            headers=headers,
            json=body,
            timeout=LLM_REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        if verbose:
            print(f"文案生成失败：网络错误 — {e}")
        return None

    if response.status_code != 200:
        detail = extract_openai_error_message(response)
        if verbose:
            print(f"文案生成失败：HTTP {response.status_code} — {detail}")
        return None

    try:
        payload = response.json()
        return str(payload["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
        if verbose:
            print(f"文案生成失败：返回格式异常 — {e}")
        return None
