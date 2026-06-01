"""Unified AI client — wraps Anthropic, OpenAI, DeepSeek and Gemini.

All agents call this client using the Anthropic-style interface:

    resp = await client.messages.create(
        model=model,
        max_tokens=512,
        system="...",
        messages=[{"role": "user", "content": "..."}],
    )
    text = resp.content[0].text

The wrapper translates that call to whichever provider is configured and
returns an object with the same `.content[0].text` shape.

Provider detection (in order of priority):
  1. Explicit AI_PROVIDER env var / settings field.
  2. Key prefix: "sk-ant-" → anthropic, "AIza" → gemini,
     other "sk-" → openai, anything else → deepseek.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


# ── Unified response shape ──────────────────────────────────────────────────

@dataclass
class _TextBlock:
    text: str


@dataclass
class _Response:
    content: list[_TextBlock]


# ── Provider implementations ────────────────────────────────────────────────

class _AnthropicMessages:
    def __init__(self, api_key: str) -> None:
        from anthropic import AsyncAnthropic  # lazy import
        self._client = AsyncAnthropic(api_key=api_key)

    async def create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict],
        system: str = "",
        **_: Any,
    ) -> _Response:
        resp = await self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        return _Response(content=[_TextBlock(text=resp.content[0].text)])


class _OpenAIMessages:
    """Works for OpenAI and DeepSeek (OpenAI-compatible API)."""

    def __init__(self, api_key: str, base_url: str | None = None) -> None:
        from openai import AsyncOpenAI  # lazy import
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict],
        system: str = "",
        **_: Any,
    ) -> _Response:
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        resp = await self._client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=all_messages,
        )
        text = resp.choices[0].message.content or ""
        return _Response(content=[_TextBlock(text=text)])


class _GeminiMessages:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict],
        system: str = "",
        **_: Any,
    ) -> _Response:
        import google.generativeai as genai  # lazy import
        import asyncio

        genai.configure(api_key=self._api_key)
        gemini = genai.GenerativeModel(
            model_name=model,
            system_instruction=system or None,
        )
        prompt = "\n".join(m["content"] for m in messages if m.get("role") == "user")
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: gemini.generate_content(
                prompt,
                generation_config={"max_output_tokens": max_tokens},
            ),
        )
        return _Response(content=[_TextBlock(text=resp.text)])


# ── Public AIClient ─────────────────────────────────────────────────────────

_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o-mini",
    "deepseek": "deepseek-chat",
    "gemini": "gemini-2.0-flash",
}


def _detect_provider(api_key: str) -> str:
    """Guess provider from API key prefix."""
    if api_key.startswith("sk-ant-"):
        return "anthropic"
    if api_key.startswith("AIza"):
        return "gemini"
    if api_key.startswith("sk-"):
        return "openai"
    return "deepseek"


class AIClient:
    """Drop-in replacement for AsyncAnthropic with multi-provider support.

    Usage:
        client = AIClient(api_key="sk-ant-...", provider="anthropic")
        resp = await client.messages.create(model=..., max_tokens=...,
                                             system=..., messages=[...])
        text = resp.content[0].text
    """

    def __init__(
        self,
        api_key: str,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        self.provider = (
            provider
            or os.getenv("AI_PROVIDER")
            or _detect_provider(api_key)
        ).lower()
        self.default_model = model or PROVIDER_DEFAULT_MODELS.get(self.provider, "")

        if self.provider == "anthropic":
            self.messages = _AnthropicMessages(api_key)
        elif self.provider == "openai":
            self.messages = _OpenAIMessages(api_key)
        elif self.provider == "deepseek":
            self.messages = _OpenAIMessages(api_key, base_url=_DEEPSEEK_BASE_URL)
        elif self.provider == "gemini":
            self.messages = _GeminiMessages(api_key)
        else:
            raise ValueError(
                f"Unknown AI provider '{self.provider}'. "
                "Choose: anthropic, openai, deepseek, gemini."
            )
