"""Guard against credential drift between the worker and the MCP server.

A transcription typo in a key is silent and expensive: the FTE only fails at the
moment it needs that provider. These checks assert both processes read the same
credential and that each configured key is actually accepted upstream.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

import config
import worker
from frontend_workspace_mcp import server as mcp_server


def check_shared_config() -> None:
    assert mcp_server.NEON_DATABASE_URL == config.NEON_DATABASE_URL
    assert worker.NEON_DATABASE_URL == config.NEON_DATABASE_URL
    # The runtime credential resolves from one place in both processes, so a
    # restricted role can never be active in one process and not the other.
    assert config.DATABASE_URL == (config.FEDS_APP_DATABASE_URL or config.NEON_DATABASE_URL)
    assert mcp_server.DATABASE_URL == config.DATABASE_URL
    assert worker.DATABASE_URL == config.DATABASE_URL
    if config.FEDS_APP_DATABASE_URL:
        assert config.FEDS_APP_DATABASE_URL != config.NEON_DATABASE_URL, (
            "FEDS_APP_DATABASE_URL duplicates the owner URL; the runtime would "
            "hold owner rights and the least-privilege role would be unused"
        )
        assert config.DATABASE_URL == config.FEDS_APP_DATABASE_URL
        print("[INFO] runtime uses the restricted FEDS_APP_DATABASE_URL credential")
    else:
        print("[WARN] FEDS_APP_DATABASE_URL is unset; the runtime holds the owner "
              "credential (see deployment.md)")
    assert mcp_server.OPENAI_API_KEY == config.OPENAI_API_KEY
    assert mcp_server.GEMINI_API_KEY == config.GEMINI_API_KEY
    assert mcp_server.GEMINI_EMBEDDING_MODEL == config.GEMINI_EMBEDDING_MODEL
    assert mcp_server.OPENAI_EMBEDDING_MODEL == config.OPENAI_EMBEDDING_MODEL
    assert worker.HARDCODED_API_KEY == config.OPENAI_API_KEY
    assert worker.GEMINI_API_KEY == config.GEMINI_API_KEY
    assert worker.GEMINI_FALLBACK_API_KEY == config.GEMINI_FALLBACK_API_KEY
    assert mcp_server._PROVIDER_API_KEYS.get("gemini-fallback") == (
        config.GEMINI_FALLBACK_API_KEY
    )
    assert mcp_server.EMBEDDING_DIMENSIONS == config.EMBEDDING_DIMENSIONS
    print("[PASS] worker and MCP server read identical configuration")


def check_shape() -> None:
    """Validate whatever credentials are present.

    Keys come from the environment, so a provider with no key is a legitimate
    state (it is simply disabled). What must hold is that any key that *is*
    configured looks like a real credential, free of stray whitespace or
    quoting from a bad copy-paste.
    """
    configured = []
    for name, key in (
        ("openai", config.OPENAI_API_KEY),
        ("gemini", config.GEMINI_API_KEY),
        ("gemini-fallback", config.GEMINI_FALLBACK_API_KEY),
        ("openrouter", config.OPENROUTER_API_KEY),
        ("ollama", config.OLLAMA_API_KEY),
    ):
        if not key:
            print(f"[SKIP] {name} has no key configured (provider disabled)")
            continue
        configured.append(name)
        assert not key.endswith(("'", '"')), f"{name} key looks malformed"
        assert key == key.strip(), f"{name} key has stray whitespace"
        assert " " not in key, f"{name} key contains whitespace"
        assert len(key) >= 20, f"{name} key is implausibly short"

    if config.OPENAI_API_KEY:
        assert config.OPENAI_API_KEY.startswith("sk-"), "openai key has unexpected prefix"
    if config.OPENROUTER_API_KEY:
        assert config.OPENROUTER_API_KEY.startswith("sk-or-"), "openrouter key has unexpected prefix"
    # Two identical Gemini keys would look like redundancy while sharing one
    # quota pool - the exact failure this fallback exists to prevent.
    if config.GEMINI_API_KEY and config.GEMINI_FALLBACK_API_KEY:
        assert config.GEMINI_FALLBACK_API_KEY != config.GEMINI_API_KEY, (
            "GEMINI_FALLBACK_API_KEY duplicates GEMINI_API_KEY; "
            "the fallback would exhaust with the primary"
        )
    assert config.EMBEDDING_DIMENSIONS == 768
    for provider in config.embedding_order():
        assert provider in config.EMBEDDING_MODELS

    # A provider with no credential must never be counted as enabled.
    for name, key, enabled in (
        ("openai", config.OPENAI_API_KEY, config.OPENAI_ENABLED),
        ("gemini", config.GEMINI_API_KEY, config.GEMINI_ENABLED),
        (
            "gemini-fallback",
            config.GEMINI_FALLBACK_API_KEY,
            config.ENABLED_FLAGS.get("gemini-fallback", False),
        ),
        ("openrouter", config.OPENROUTER_API_KEY, config.OPENROUTER_ENABLED),
        ("ollama", config.OLLAMA_API_KEY, config.OLLAMA_ENABLED),
    ):
        if not key:
            assert not enabled, f"{name} is enabled without a credential"

    print(
        "[PASS] credential shape and provider wiring look sane "
        f"(configured={configured or 'none'}, chat={config.chat_order()}, "
        f"embed={config.embedding_order()})"
    )


def check_no_secrets_in_source() -> None:
    """A committed credential is the one mistake that cannot be undone."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parent
    # This file holds the patterns themselves, so skip it to avoid self-matching.
    self_name = Path(__file__).name
    patterns = {
        "gemini-style key": re.compile(r"AQ\.[A-Za-z0-9_\-]{30,}"),
        "openai-style key": re.compile(r"sk-proj-[A-Za-z0-9_\-]{80,}"),
        "ollama-style key": re.compile(r"\b[0-9a-f]{32}\.[A-Za-z0-9_\-]{24,}"),
        "postgres password": re.compile(r"postgresql://[^:]+:([A-Za-z0-9_\-]{8,})@"),
    }
    # Obvious placeholders in documentation and .env.example are not credentials.
    placeholder_words = ("password", "user", "secret", "changeme", "example", "your")
    checked_suffixes = {".py", ".md", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".txt"}
    skip_names = {self_name}
    offenders: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in checked_suffixes and path.name != ".env.example":
            continue
        if path.name in skip_names:
            continue
        if any(part in {".venv", "__pycache__", ".git", ".agents"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in patterns.items():
            for match in pattern.finditer(text):
                if label == "postgres password":
                    secret = match.group(1).lower()
                    if any(word in secret for word in placeholder_words):
                        continue
                offenders.append(f"{path.relative_to(root)} ({label})")
                break

    if offenders:
        print("[FAIL] credentials appear in committed source:")
        for item in offenders:
            print(f"       {item}")
        raise AssertionError("secrets found in source")
    print("[PASS] no credentials in committed source")


def _openai_key_valid(key: str) -> tuple[bool, str]:
    request = urllib.request.Request("https://api.openai.com/v1/models")
    request.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status == 200, f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}"


def _gemini_key_valid(key: str) -> tuple[bool, str]:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.GEMINI_CHAT_MODEL}:generateContent?key={key}"
    )
    body = json.dumps(
        {"contents": [{"parts": [{"text": "ping"}]}],
         "generationConfig": {"maxOutputTokens": 4}}
    ).encode()
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status == 200, f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}"


def _openrouter_key_valid(key: str) -> tuple[bool, str]:
    """Validate an OpenRouter API key by making a lightweight models call."""
    request = urllib.request.Request("https://openrouter.ai/api/v1/models")
    request.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status == 200, f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}"


def _ollama_key_valid(key: str) -> tuple[bool, str]:
    """Validate an Ollama Cloud key with the official client (no chat quota).

    A catalog listing proves the credential; model entitlement is a separate
    concern and is reported by `status_providers.py`.
    """
    try:
        import ollama
    except ImportError:
        return False, "ollama package missing"
    try:
        client = ollama.Client(
            host=config.OLLAMA_HOST,
            headers={"Authorization": f"Bearer {key}"},
        )
        listing = client.list()
        return True, f"HTTP 200, {len(listing.get('models', []))} models"
    except Exception as exc:  # noqa: BLE001
        status = getattr(exc, "status_code", None)
        return False, f"HTTP {status}" if status else type(exc).__name__


def check_live_credentials(strict: bool) -> int:
    """Verify each configured key authenticates.

    A credential being rejected or out of quota is an environment fact, not a
    code defect, so it is reported but only fails the run in --strict mode.
    Pass --offline to skip the network probe entirely.
    """
    problems = 0
    for name, probe in (
        ("openai", lambda: _openai_key_valid(config.OPENAI_API_KEY)),
        ("gemini", lambda: _gemini_key_valid(config.GEMINI_API_KEY)),
        ("gemini-fallback", lambda: _gemini_key_valid(config.GEMINI_FALLBACK_API_KEY)),
        ("openrouter", lambda: _openrouter_key_valid(config.OPENROUTER_API_KEY)),
        ("ollama", lambda: _ollama_key_valid(config.OLLAMA_API_KEY)),
    ):
        valid, detail = probe()
        if valid:
            print(f"[PASS] {name} credential authenticates ({detail})")
        elif "429" in detail:
            print(f"[WARN] {name} credential is valid but out of quota ({detail})")
        elif name not in config.chat_order():
            print(f"[SKIP] {name} is disabled and its credential is unusable ({detail})")
        else:
            print(f"[FAIL] {name} credential rejected ({detail})")
            problems += 1
    return problems if strict else 0


def main() -> int:
    check_shared_config()
    check_shape()
    check_no_secrets_in_source()

    args = sys.argv[1:]
    if "--offline" in args:
        print("[SKIP] live credential probe (--offline)")
        return 0

    strict = "--strict" in args
    return 1 if check_live_credentials(strict) else 0


if __name__ == "__main__":
    sys.exit(main())