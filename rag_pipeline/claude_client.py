"""
Claude API client wrapper.

Centralises authentication, retry logic, and message formatting so
the rest of the codebase only needs to call `ClaudeClient().complete(...)`.
"""
from __future__ import annotations

from typing import List, Sequence

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class ClaudeAPIError(RuntimeError):
    """Raised when the Anthropic API call fails after retries."""


class ClaudeClient:
    """Thin wrapper around the official `anthropic` SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> None:
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model or settings.claude_model
        self.max_tokens = max_tokens or settings.claude_max_tokens
        self.temperature = (
            temperature if temperature is not None else settings.claude_temperature
        )

        if not self.api_key:
            logger.warning(
                "ANTHROPIC_API_KEY is empty — Claude calls will fail until set."
            )

        # Defer import so the rest of the app works without the SDK.
        try:
            import anthropic  # type: ignore

            self._client = anthropic.Anthropic(api_key=self.api_key) if self.api_key else None
            self._anthropic = anthropic
        except ImportError:  # pragma: no cover
            self._client = None
            self._anthropic = None

    # ------------------------------------------------------------------
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def complete(
        self,
        *,
        system: str,
        user: str,
        history: Sequence[dict] | None = None,
    ) -> str:
        """
        Send a chat completion request and return the assistant text.

        `history` is a sequence of {"role": "user"|"assistant", "content": str}
        items that precede the current `user` message.
        """
        if self._client is None:
            raise ClaudeAPIError(
                "Anthropic SDK not installed or API key missing. "
                "Install with `pip install anthropic` and set ANTHROPIC_API_KEY."
            )

        messages: List[dict] = []
        for h in history or []:
            role = h.get("role")
            content = h.get("content", "")
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user})

        try:
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system,
                messages=messages,
            )
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise ClaudeAPIError(str(e)) from e

        # `resp.content` is a list of content blocks; concatenate text blocks.
        parts: list[str] = []
        for block in getattr(resp, "content", []) or []:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "".join(parts).strip()
