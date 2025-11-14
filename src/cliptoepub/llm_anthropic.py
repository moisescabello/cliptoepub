#!/usr/bin/env python3
"""
Anthropic LLM integration with retries and simple backoff.

Provides a minimal API to process clipboard text through Anthropic and
return Markdown suitable for the converter.
"""

from __future__ import annotations

import os
import time
import random
from typing import Optional


class AnthropicRecoverableError(Exception):
    pass


class AnthropicAuthOrConfigError(Exception):
    pass


def _sleep_backoff(attempt: int) -> None:
    # Exponential backoff with jitter: base 0.5s doubling, capped ~10s
    base = min(0.5 * (2 ** attempt), 10.0)
    time.sleep(base + random.uniform(0, 0.25))


def _extract_text_from_sdk_message(message) -> str:
    try:
        parts = []
        for block in getattr(message, "content", []) or []:
            if getattr(block, "type", None) == "text":
                parts.append(getattr(block, "text", ""))
        return "".join(parts).strip()
    except Exception:
        # Conservative fallback
        try:
            return str(getattr(message, "content", "")).strip()
        except Exception:
            return ""


def _extract_text_from_rest_response(data: dict) -> str:
    try:
        items = data.get("content") or []
        parts = []
        for block in items:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts).strip()
    except Exception:
        return ""


def _is_recoverable(exc: Exception, status_code: Optional[int] = None) -> bool:
    if status_code is not None:
        if status_code in (429, 408, 409, 425, 500, 502, 503, 504):
            return True
        if 500 <= status_code <= 599:
            return True
        return False
    # Heuristic if SDK exceptions don't expose status
    text = str(exc).lower()
    recoverable_tokens = [
        "rate limit", "overloaded", "timeout", "temporarily", "try again", "retry",
    ]
    return any(tok in text for tok in recoverable_tokens)


def _process_via_openrouter(
    text: str,
    *,
    api_key: Optional[str],
    model: str,
    system_prompt: str,
    max_tokens: int = 2048,
    temperature: float = 0.2,
    timeout_s: int = 60,
    retries: int = 10,
) -> str:
    """Send text via OpenRouter Chat Completions API.

    Notes:
    - Supports Anthropic models available through OpenRouter such as
      'anthropic/claude-sonnet-4.5' (1M context window, provider-dependent access).
    - Uses OPENROUTER_API_KEY from environment if api_key is None/empty.
    - Expects OpenAI-compatible response with choices[0].message.content.
    """
    key = (api_key or "").strip() or os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise AnthropicAuthOrConfigError("Missing OPENROUTER_API_KEY for OpenRouter request")

    import httpx

    # Build OpenAI-compatible chat request
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": text})

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        # Optional but recommended for some providers
        "HTTP-Referer": os.environ.get("OPENROUTER_REFERRER", "https://github.com/"),
        "X-Title": os.environ.get("OPENROUTER_TITLE", "Clipboard to ePub"),
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
    }

    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=timeout_s) as client:
                resp = client.post(url, headers=headers, json=payload)
            if resp.status_code in (401, 403):
                raise AnthropicAuthOrConfigError("OpenRouter authentication failed or access denied")
            if resp.status_code >= 400:
                detail = None
                try:
                    err = resp.json()
                    if isinstance(err, dict):
                        detail = err.get("error") or err.get("message") or None
                except Exception:
                    if resp.text:
                        detail = resp.text.strip()
                # Surface model not found / access issues clearly
                if detail and ("model" in str(detail).lower()) and ("not" in str(detail).lower() and "found" in str(detail).lower()):
                    raise RuntimeError(
                        f"OpenRouter model not found: '{model}'. Example: 'anthropic/claude-sonnet-4.5'"
                    )
                # Retry transient HTTP errors
                if _is_recoverable(Exception(detail or resp.text), status_code=resp.status_code):
                    raise AnthropicRecoverableError(f"HTTP {resp.status_code}")
                raise RuntimeError(f"OpenRouter error: HTTP {resp.status_code}{(' – ' + str(detail)) if detail else ''}")
            data = resp.json()
            try:
                content = data["choices"][0]["message"]["content"]
            except Exception:  # noqa: BLE001
                content = ""
            return (content or "").strip()
        except AnthropicAuthOrConfigError:
            raise
        except Exception as e:  # noqa: BLE001
            last_exc = e
            if isinstance(e, AnthropicRecoverableError) or _is_recoverable(e):
                if attempt < retries:
                    _sleep_backoff(attempt)
                    continue
                raise AnthropicRecoverableError("Exhausted retries for OpenRouter request")
            raise

    if last_exc:
        raise last_exc
    return ""


def process_text(
    text: str,
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    max_tokens: int = 2048,
    temperature: float = 0.2,
    timeout_s: int = 60,
    retries: int = 10,
) -> str:
    """
    Send text to Anthropic Messages API and return Markdown.

    Raises AnthropicAuthOrConfigError on 401/403 and AnthropicRecoverableError
    after all retries are exhausted for transient errors.
    """
    if not model or not system_prompt:
        raise AnthropicAuthOrConfigError("Missing model or system prompt")

    if not api_key:
        raise AnthropicAuthOrConfigError("Missing Anthropic API key")

    # Try SDK first; fallback to REST if SDK not installed
    try:
        from anthropic import Anthropic
        from anthropic._exceptions import APIStatusError  # type: ignore
        have_sdk = True
    except Exception:
        Anthropic = None  # type: ignore
        APIStatusError = Exception  # type: ignore
        have_sdk = False

    last_exc: Optional[Exception] = None

    for attempt in range(retries + 1):
        try:
            if have_sdk:
                client = Anthropic(api_key=api_key)
                message = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": text}],
                    timeout=timeout_s,
                )
                md = _extract_text_from_sdk_message(message)
                if not md.strip():
                    md = ""
                return md
            else:
                import httpx

                headers = {
                    "content-type": "application/json",
                    "x-api-key": api_key,
                }
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "user", "content": text},
                    ],
                    "system": system_prompt,
                    "max_tokens": int(max_tokens),
                    "temperature": float(temperature),
                }
                url = "https://api.anthropic.com/v1/messages"
                with httpx.Client(timeout=timeout_s) as client:
                    resp = client.post(url, headers=headers, json=payload)
                if resp.status_code in (401, 403):
                    raise AnthropicAuthOrConfigError("Anthropic authentication failed or access denied")
                if resp.status_code >= 400:
                    detail = None
                    try:
                        err = resp.json()
                        if isinstance(err, dict):
                            detail = err.get("error") or err.get("message") or None
                    except Exception:
                        if resp.text:
                            detail = resp.text.strip()
                    if _is_recoverable(Exception(detail or resp.text), status_code=resp.status_code):
                        raise AnthropicRecoverableError(f"HTTP {resp.status_code}")
                    raise RuntimeError(f"Anthropic error: HTTP {resp.status_code}{(' – ' + str(detail)) if detail else ''}")
                data = resp.json()
                md = _extract_text_from_rest_response(data)
                return md
        except (AnthropicAuthOrConfigError, RuntimeError) as e:
            # Non-recoverable
            raise
        except Exception as e:  # noqa: BLE001
            last_exc = e
            # Try again on recoverables
            if isinstance(e, AnthropicRecoverableError) or _is_recoverable(e):
                if attempt < retries:
                    _sleep_backoff(attempt)
                    continue
                raise AnthropicRecoverableError("Exhausted retries for Anthropic request")
            raise

    if last_exc:
        raise last_exc
    return ""


def sanitize_first_line(text: str) -> str:
    """Utility to build a good ePub title from LLM output's first line."""
    first = (text or "").strip().splitlines()[0:1]
    if not first:
        return "Untitled"
    title = first[0].strip("# -* ")[:120]
    return title or "Untitled"
