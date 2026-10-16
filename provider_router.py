"""Quota-aware provider fallback shared by the worker and the MCP server.

Both the chat model and the embedding model are routed through this module so a
single exhausted provider never takes the Digital FTE offline.

Behavior:
- Providers are tried in priority order on every call.
- A provider that reports quota exhaustion is put into a cooldown (honoring a
  server supplied retry delay when one is present) and the next provider is used.
- Cooldowns expire on their own, so a recovered provider is automatically retried
  and returns to its original priority position. This gives bidirectional
  recovery: OpenAI -> Gemini when Gemini's quota resets, and Gemini -> OpenAI
  when Gemini runs out.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Sequence

DEFAULT_COOLDOWN_SECONDS = 900.0
# Floor applied only when an upstream supplies its own (possibly tiny) hint, so a
# server-suggested retry is never ignored but hot loops are still prevented.
MIN_COOLDOWN_SECONDS = 1.0

# Quota/balance signals that should trigger a provider rotation rather than a
# hard failure. Matched case-insensitively against the error text.
_QUOTA_MARKERS = (
    "insufficient_quota",
    "credit_balance_exhausted",
    "no credits remaining",
    "insufficient balance",
    "insufficient_balance",
    "payment required",
    "resource_exhausted",
    "quota",
    "rate limit",
    "rate_limit",
    "too many requests",
    "429",
    "402",
)

# Upstreams report an exhausted allowance as either 429 (rate limited) or
# 402 (account out of credit/balance). Both mean "try the next provider".
_QUOTA_STATUS_CODES = {402, 429}

_RETRY_DELAY_RE = re.compile(r"retryDelay\"?[:=]\s*\"?(\d+(?:\.\d+)?)", re.IGNORECASE)
_RETRY_AFTER_RE = re.compile(r"retry-after\"?[:=]\s*\"?(\d+(?:\.\d+)?)", re.IGNORECASE)


class AllProvidersExhausted(RuntimeError):
    """Every configured provider is currently in quota cooldown."""


def is_quota_error(exc: BaseException) -> bool:
    """True when an exception indicates quota, balance, or rate-limit exhaustion."""
    if exc.__class__.__name__ in {
        "RateLimitError",
        "ResourceExhausted",
        "TooManyRequests",
    }:
        return True
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status in _QUOTA_STATUS_CODES:
        return True
    response = getattr(exc, "response", None)
    if getattr(response, "status_code", None) in _QUOTA_STATUS_CODES:
        return True
    text = f"{exc}".lower()
    code = str(getattr(exc, "code", "") or "").lower()
    haystack = f"{code} {text}"
    return any(marker in haystack for marker in _QUOTA_MARKERS)


def retry_delay_seconds(exc: BaseException) -> float | None:
    """Extract a server-provided cooldown hint, if the error carries one."""
    blob = f"{getattr(exc, 'body', '')} {getattr(exc, 'response', '')} {exc}"
    for pattern in (_RETRY_DELAY_RE, _RETRY_AFTER_RE):
        match = pattern.search(blob)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue
    headers = getattr(getattr(exc, "response", None), "headers", None)
    if headers:
        value = headers.get("retry-after") or headers.get("Retry-After")
        if value:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return None


@dataclass
class Provider:
    """One upstream endpoint plus its live availability state."""

    name: str
    cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS
    cooldown_until: float = 0.0
    last_error: str = ""
    total_calls: int = 0
    total_failures: int = 0
    failure_streak: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def available(self, now: float | None = None) -> bool:
        return (now if now is not None else time.monotonic()) >= self.cooldown_until

    def cooldown_remaining(self, now: float | None = None) -> float:
        return max(0.0, self.cooldown_until - (now if now is not None else time.monotonic()))


class ProviderRouter:
    """Round-robins across providers, cooling down only the ones that failed."""

    def __init__(
        self,
        providers: Sequence[Provider],
        *,
        cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
        on_event: Callable[[str], None] | None = None,
    ) -> None:
        if not providers:
            raise ValueError("at least one provider is required")
        self._providers = list(providers)
        self._cooldown_seconds = cooldown_seconds
        self._on_event = on_event
        self._lock = asyncio.Lock()

    @property
    def providers(self) -> list[Provider]:
        return list(self._providers)

    def get(self, name: str) -> Provider | None:
        return next((p for p in self._providers if p.name == name), None)

    def status(self) -> dict[str, Any]:
        now = time.monotonic()
        return {
            "active": next((p.name for p in self._providers if p.available(now)), None),
            "providers": [
                {
                    "name": p.name,
                    "available": p.available(now),
                    "cooldown_remaining_s": round(p.cooldown_remaining(now), 1),
                    "calls": p.total_calls,
                    "failures": p.total_failures,
                    "last_error": p.last_error,
                }
                for p in self._providers
            ],
        }

    def _emit(self, message: str) -> None:
        if self._on_event:
            try:
                self._on_event(message)
            except Exception:  # noqa: BLE001 - logging must never break a call
                pass

    def _mark_exhausted(self, provider: Provider, exc: BaseException) -> None:
        """Cool the provider down, honoring a server hint and backing off on repeats."""
        provider.failure_streak += 1
        hint = retry_delay_seconds(exc)
        if hint is None or hint < 0:
            base = provider.cooldown_seconds
        else:
            # The upstream told us exactly when to come back; trust it.
            base = max(hint, MIN_COOLDOWN_SECONDS)
        # Repeated failures lengthen the wait so a dead quota is not hammered,
        # while the ceiling keeps recovery prompt once quota returns.
        backoff = min(2 ** min(provider.failure_streak - 1, 5), 16)
        ceiling = max(provider.cooldown_seconds * 8, base)
        delay = min(base * backoff, ceiling)

        provider.cooldown_until = time.monotonic() + delay
        provider.last_error = f"{type(exc).__name__}: {exc}"[:300]
        provider.total_failures += 1
        self._emit(
            f"[provider-router] {provider.name} quota exhausted; "
            f"cooling down {delay:.0f}s (streak {provider.failure_streak})"
        )

    async def run(self, fn: Callable[[Provider], Awaitable[Any]]) -> tuple[Any, Provider]:
        """Call `fn` with the first healthy provider, rotating on quota errors.

        Returns the result together with the provider that produced it, so
        callers can tag stored artifacts with their real origin.
        """
        async with self._lock:
            now = time.monotonic()
            candidates = [p for p in self._providers if p.available(now)]
            if not candidates:
                soonest = min(self._providers, key=lambda p: p.cooldown_until)
                wait = soonest.cooldown_remaining()
                self._emit(
                    f"[provider-router] all providers exhausted; "
                    f"next retry in {wait:.0f}s ({soonest.name})"
                )
                raise AllProvidersExhausted(
                    "every configured provider is in quota cooldown; "
                    f"next retry in {wait:.0f}s ({soonest.name})"
                )

            last_error: BaseException | None = None
            for provider in candidates:
                provider.total_calls += 1
                try:
                    result = await fn(provider)
                except Exception as exc:  # noqa: BLE001 - inspected below
                    if not is_quota_error(exc):
                        # Real bugs must surface immediately; only quota issues
                        # are worth routing around.
                        raise
                    last_error = exc
                    self._mark_exhausted(provider, exc)
                    continue
                if provider.last_error:
                    # Recovered: clear the sticky error and reset backoff so the
                    # provider immediately returns to its priority position.
                    self._emit(f"[provider-router] {provider.name} recovered")
                    provider.last_error = ""
                provider.failure_streak = 0
                return result, provider
            soonest = min(self._providers, key=lambda p: p.cooldown_until)
            raise AllProvidersExhausted(
                f"every configured provider is in quota cooldown "
                f"(next retry in {soonest.cooldown_remaining():.0f}s on "
                f"{soonest.name}); last error: {last_error}"
            )