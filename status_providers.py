"""Report live availability for every configured provider."""

import json
import urllib.error
import urllib.request

import config


def openai_status(key: str):
    request = urllib.request.Request("https://api.openai.com/v1/models")
    request.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return response.status, "credential works"
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        if exc.code == 429:
            return 429, "valid but no credits remaining"
        if exc.code in (401, 403):
            return exc.code, "credential rejected/incorrect"
        return exc.code, detail[:80]
    except Exception as exc:  # noqa: BLE001
        return -1, f"{type(exc).__name__}"


def _extract_text(payload: dict) -> str:
    """Pull plain text out of a candidate.

    Reasoning models can return a thought part before the answer, so parts[0]
    is not guaranteed to carry "text".
    """
    candidates = payload.get("candidates") or []
    if not candidates:
        return ""
    parts = (candidates[0].get("content") or {}).get("parts") or []
    texts = [
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and part.get("text")
    ]
    return " ".join(texts).strip()


def _gemini_status(key: str):
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.GEMINI_CHAT_MODEL}:generateContent?key={key}"
    )
    body = json.dumps(
        {
            "contents": [{"parts": [{"text": "ping"}]}],
            "generationConfig": {"maxOutputTokens": 8},
        }
    ).encode()
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.load(response)
            text = _extract_text(payload)
            return response.status, f"works, replied {text[:20]!r}"
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace").replace("\n", " ")
        if exc.code == 429:
            return 429, "valid but quota exhausted"
        if exc.code == 402:
            return 402, "valid but account balance exhausted"
        if exc.code == 404:
            return 404, "model retired for this credential; change GEMINI_CHAT_MODEL"
        if exc.code == 503:
            return 503, "model live but saturated (transient)"
        if exc.code in (401, 403):
            return exc.code, "credential rejected"
        return exc.code, detail[:80]
    except Exception as exc:  # noqa: BLE001
        return -1, f"{type(exc).__name__}: {exc}"


# Each probe is a real model call, so keep one per configured provider.
_PROBES = {
    "openai": lambda: openai_status(config.OPENAI_API_KEY),
    "gemini": lambda: _gemini_status(config.GEMINI_API_KEY),
}

print("enabled flags : " + ", ".join(
    f"{name}={'on' if on else 'off'}" for name, on in config.ENABLED_FLAGS.items()
))
print(f"chat order    : {config.chat_order()}")
print(f"embed order   : {config.embedding_order()}")
print()

results = {name: probe() for name, probe in _PROBES.items()}

for name, (status, detail) in results.items():
    usable = "USABLE" if status == 200 else "blocked"
    print(f"{name:9s} -> HTTP {status:<4} {usable:8s} {detail}")

print()
usable_now = [n for n, (s, _) in results.items() if s == 200]
if usable_now:
    print(f"RESULT: usable now: {', '.join(usable_now)}")
else:
    print("RESULT: no provider is usable right now.")