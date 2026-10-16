"""Verify quota-aware provider rotation without touching real upstreams.

These tests exercise the fallback contract directly:
- Gemini 429 -> OpenAI is used automatically.
- OpenAI 429 -> Gemini is used automatically.
- A provider recovers once its cooldown expires.
- Non-quota errors surface immediately instead of being routed around.
"""

from __future__ import annotations

import asyncio

from provider_router import (
    AllProvidersExhausted,
    Provider,
    ProviderRouter,
    is_quota_error,
    retry_delay_seconds,
)


class FakeRateLimit(Exception):
    """Mimics an upstream 429 closely enough for the detector."""

    status_code = 429

    def __init__(self, provider: str, retry_after: str | None = None):
        self.provider = provider
        self.code = "insufficient_quota"
        self.body = {"error": {"message": "You have no credits remaining."}}
        self.response = type(
            "R", (), {"status_code": 429, "headers": {}}
        )()
        if retry_after:
            self.response.headers = {"retry-after": retry_after}
        super().__init__(f"429 from {provider}")


class FakeBug(Exception):
    """A genuine defect that must never be silently routed around."""


def make_router(cooldown: float = 900.0) -> ProviderRouter:
    return ProviderRouter(
        [
            Provider(name="gemini", cooldown_seconds=cooldown),
            Provider(name="openai", cooldown_seconds=cooldown),
        ],
        cooldown_seconds=cooldown,
    )


async def scenario_gemini_down_uses_openai() -> list[str]:
    """Gemini is primary; when it is out of quota OpenAI must serve the call."""
    router = make_router()
    seen: list[str] = []

    async def attempt(provider: Provider):
        seen.append(provider.name)
        if provider.name == "gemini":
            raise FakeRateLimit("gemini", retry_after="120")
        return f"embedded-by-{provider.name}"

    result, used = await router.run(attempt)
    assert result == "embedded-by-openai", result
    assert used.name == "openai", used.name
    assert seen == ["gemini", "openai"], seen

    status = router.status()
    assert status["active"] == "openai", status
    assert status["providers"][0]["available"] is False
    assert 100 <= status["providers"][0]["cooldown_remaining_s"] <= 120
    return seen


async def scenario_openai_down_returns_to_gemini() -> list[str]:
    """If OpenAI runs out, a recovered Gemini must take over again."""
    router = ProviderRouter(
        [
            Provider(name="openai", cooldown_seconds=900),
            Provider(name="gemini", cooldown_seconds=900),
        ],
        cooldown_seconds=900,
    )
    seen: list[str] = []

    async def attempt(provider: Provider):
        seen.append(provider.name)
        if provider.name == "openai":
            raise FakeRateLimit("openai", retry_after="60")
        return f"embedded-by-{provider.name}"

    result, used = await router.run(attempt)
    assert result == "embedded-by-gemini", result
    assert used.name == "gemini"
    return seen


async def scenario_recovery_after_cooldown() -> str:
    """A cooled-down provider must be retried once its cooldown expires."""
    router = make_router(cooldown=60)
    state = {"gemini_fail": True}

    async def attempt(provider: Provider):
        if provider.name == "gemini" and state["gemini_fail"]:
            # Server hint of 1s: the router must honor it rather than force a
            # long default, which is what makes prompt recovery possible.
            raise FakeRateLimit("gemini", retry_after="1")
        return f"ok-{provider.name}"

    _, first = await router.run(attempt)
    assert first.name == "openai", first.name

    status = router.status()
    assert status["providers"][0]["cooldown_remaining_s"] <= 1.0, status

    state["gemini_fail"] = False
    await asyncio.sleep(1.1)  # let the server-requested cooldown lapse
    _, second = await router.run(attempt)
    assert second.name == "gemini", second.name
    assert second.last_error == "", second.last_error
    assert second.failure_streak == 0
    return "recovered to gemini after its cooldown expired"


async def scenario_all_exhausted() -> str:
    """With no healthy provider the caller gets one clear, actionable error."""
    router = make_router()

    async def attempt(provider: Provider):
        raise FakeRateLimit(provider.name, retry_after="45")

    try:
        await router.run(attempt)
    except AllProvidersExhausted as exc:
        return f"raised: {str(exc)[:40]}..."
    raise AssertionError("expected AllProvidersExhausted")


async def scenario_bug_not_routed() -> str:
    """Real defects must propagate instead of being retried elsewhere."""

    async def attempt(provider: Provider):
        if provider.name == "gemini":
            raise FakeBug("bad SQL in a tool")
        return "should never be reached"

    router = make_router()
    try:
        await router.run(attempt)
    except FakeBug:
        return "propagated"
    raise AssertionError("a real bug must not be routed around")


class FakePaymentRequired(Exception):
    """Mimics a 402 from a provider whose account balance is exhausted."""

    status_code = 402

    def __init__(self, provider: str = "primary"):
        self.provider = provider
        self.code = "invalid_request_error"
        super().__init__(
            "Insufficient Balance (request_id: 00000000-0000-0000-0000-000000000000)"
        )


async def scenario_payment_required_rotates() -> list[str]:
    """An exhausted balance (402) must rotate just like a rate limit (429).

    Providers report this differently: some hosts answer 429 insufficient_quota
    while others answer 402 Insufficient Balance. Both mean "use the next
    provider", so both must rotate.
    """
    router = ProviderRouter(
        [
            Provider(name="primary", cooldown_seconds=900),
            Provider(name="fallback", cooldown_seconds=900),
        ],
        cooldown_seconds=900,
    )
    seen: list[str] = []

    async def attempt(provider: Provider):
        seen.append(provider.name)
        if provider.name == "primary":
            raise FakePaymentRequired()
        return f"served-by-{provider.name}"

    result, used = await router.run(attempt)
    assert result == "served-by-fallback", result
    assert used.name == "fallback", used.name
    assert seen == ["primary", "fallback"], seen
    assert router.status()["providers"][0]["available"] is False
    return seen


def check_detectors() -> None:
    assert is_quota_error(FakeRateLimit("gemini"))
    assert not is_quota_error(FakeBug("nope"))
    assert not is_quota_error(ValueError("bad argument"))
    assert retry_delay_seconds(FakeRateLimit("x", retry_after="90")) == 90.0
    assert retry_delay_seconds(FakeRateLimit("x")) is None

    # Balance exhaustion must be detected as a routable quota condition.
    assert is_quota_error(FakePaymentRequired())
    assert is_quota_error(type("E", (Exception,), {"status_code": 402})("payment required"))
    assert is_quota_error(Exception("Insufficient Balance"))
    assert is_quota_error(Exception("credit_balance_exhausted"))
    # A rejected credential must still NOT be routed around.
    assert not is_quota_error(type("E", (Exception,), {"status_code": 401})("Incorrect API key"))
    assert not is_quota_error(FakeBug("bad SQL"))


async def main() -> None:
    check_detectors()
    seen = await scenario_gemini_down_uses_openai()
    print(f"[PASS] gemini down -> openai served it (tried {seen})")
    seen = await scenario_openai_down_returns_to_gemini()
    print(f"[PASS] openai down -> gemini served it (tried {seen})")
    seen = await scenario_payment_required_rotates()
    print(f"[PASS] 402 balance exhausted -> fallback served it (tried {seen})")
    print(f"[PASS] {await scenario_recovery_after_cooldown()}")
    print(f"[PASS] all exhausted -> {await scenario_all_exhausted()}")
    print(f"[PASS] real bug -> {await scenario_bug_not_routed()}")
    print(f"[PASS] error detectors (429, 402, 401, bugs)")


if __name__ == "__main__":
    asyncio.run(main())