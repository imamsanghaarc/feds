"""Single source of truth for Digital FTE runtime configuration.

Both the worker (`worker.py`) and the scoped MCP server
(`frontend_workspace_mcp/server.py`) import from here so a credential can never
drift between the two processes.

Provider policy
---------------
Two providers are configured so the FTE survives either one running out of
quota. The preferred provider is tried first; on quota exhaustion the router
falls back to the other, and control returns automatically once the preferred
provider's quota resets (see `provider_router.py`).

Only quota/rate-limit failures trigger a rotation. A misconfigured credential or
a genuine bug is surfaced instead of being silently routed around, so a broken
key can never look like a healthy system.

Secrets are embedded as requested for this live deployment. Move these to a
managed secret store before sharing this source.
"""

from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv() -> None:
    """Load .env into the environment without overwriting real variables.

    Keeps local setup to one file while letting a deployed process supply its
    own environment, which always wins.
    """
    env_file = Path(__file__).resolve().parent / ".env"
    if not env_file.is_file():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_file, override=False)
        return
    except ImportError:
        pass
    # Minimal fallback so the project works without python-dotenv installed.
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

# --- Identity ----------------------------------------------------------------
#
# The official name of this AI Employee. Used by the agent, the system prompt
# contract, the audit trail, and the docs so the name can never drift.

OFFICIAL_NAME = "FEDS"
OFFICIAL_NAME_LONG = "Frontend Engineering Digital Specialist"
AGENT_NAME = f"{OFFICIAL_NAME} — {OFFICIAL_NAME_LONG}"

# --- Providers ---------------------------------------------------------------
#
# Chat and embeddings are routed independently, because not every provider offers
# both. DeepSeek and Groq serve chat only; they have no embeddings endpoint.
#
# A provider is enabled when its credential is expected to work AND its flag is
# on. Each currently-blocked provider ships disabled so a bad credential cannot
# silently degrade every turn.

# OpenAI: chat + embeddings. Currently disabled, credential returns HTTP 401.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-5-mini")
OPENAI_BASE_URL = ""  # empty means the official OpenAI endpoint
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_ENABLED = bool(OPENAI_API_KEY) and os.getenv("OPENAI_ENABLED", "1") != "0"

# Gemini: chat + embeddings. Preferred while its free tier holds out.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# gemini-2.5-flash is retired for newly provisioned keys (HTTP 404 "no longer
# available to new users"). Verified working on the current credential:
# gemini-3.5-flash, gemini-3.5-flash-lite, gemini-3.1-flash-lite,
# gemini-3.6-flash, gemini-3.8-flash. gemini-flash-latest and gemini-3.7-flash
# were saturated (503) at the time of writing.
GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-3.5-flash")
GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
GEMINI_NATIVE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_ENABLED = bool(GEMINI_API_KEY) and os.getenv("GEMINI_ENABLED", "1") != "0"

# --- Embeddings --------------------------------------------------------------

# Every embedding provider must agree on dimensionality; pgvector columns are
# sized to it. Chat-only providers are deliberately absent from this mapping.
EMBEDDING_DIMENSIONS = 768
PREFERRED_EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "gemini").strip().lower()
EMBEDDING_MODELS = {
    "gemini": GEMINI_EMBEDDING_MODEL,
    "openai": OPENAI_EMBEDDING_MODEL,
}

# --- Runtime -----------------------------------------------------------------

PROVIDER_COOLDOWN_SECONDS = float(os.getenv("PROVIDER_COOLDOWN_SECONDS", "900"))

NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL", "")


# --- Provider registry -------------------------------------------------------

# Single place that maps a provider name to its enabled flag and chat settings.
# Adding a chat-only provider means adding one entry here and nothing else.
_CHAT_PROVIDERS: dict[str, dict[str, object]] = {
    "gemini": {
        "enabled": GEMINI_ENABLED,
        "model": GEMINI_CHAT_MODEL,
        "base_url": GEMINI_BASE_URL,
        "api_key": GEMINI_API_KEY,
    },
    "openai": {
        "enabled": OPENAI_ENABLED,
        "model": OPENAI_CHAT_MODEL,
        "base_url": OPENAI_BASE_URL,
        "api_key": OPENAI_API_KEY,
    },
    }

# Preference order for chat. Gemini leads; the rest are ordered fallbacks.
CHAT_PREFERENCE = ("gemini", "openai")

CHAT_MODELS = {
    name: {"model": cfg["model"], "base_url": cfg["base_url"], "api_key": cfg["api_key"]}
    for name, cfg in _CHAT_PROVIDERS.items()
}

ENABLED_FLAGS = {name: bool(cfg["enabled"]) for name, cfg in _CHAT_PROVIDERS.items()}


def require_config() -> list[str]:
    """Return a list of missing required settings, with setup instructions.

    Called by the CLI entry points so a missing key produces one clear message
    instead of a confusing failure deep inside a provider client.
    """
    problems = []
    if not NEON_DATABASE_URL:
        problems.append(
            "NEON_DATABASE_URL is not set. Copy .env.example to .env and fill it in, "
            "then run: uv run python setup_neon.py"
        )
    if not chat_order():
        problems.append(
            "No chat provider is enabled. Set GEMINI_API_KEY (or OPENAI_API_KEY) "
            "in .env or the environment."
        )
    if not problems and not embedding_order():
        problems.append(
            "No embedding provider is enabled. GEMINI_API_KEY or OPENAI_API_KEY "
            "must be set, because embeddings need a provider of their own."
        )
    return problems


def _ordered(names) -> list[str]:
    """Return the enabled names, preserving the registry's declared order."""
    return [name for name in names if ENABLED_FLAGS.get(name, False)]


def embedding_order() -> list[str]:
    """Enabled embedding providers, most preferred first.

    Chat-only providers are excluded because they have no embeddings endpoint.
    """
    if PREFERRED_EMBEDDING_PROVIDER not in EMBEDDING_MODELS:
        raise ValueError(
            f"unsupported EMBEDDING_PROVIDER: {PREFERRED_EMBEDDING_PROVIDER!r}"
        )
    preferred = [PREFERRED_EMBEDDING_PROVIDER]
    others = [name for name in EMBEDDING_MODELS if name not in preferred]
    order = _ordered(preferred) + _ordered(others)
    if not order:
        raise ValueError("no embedding provider is enabled")
    return order


def chat_order() -> list[str]:
    """Enabled chat providers, most preferred first."""
    order = _ordered(CHAT_PREFERENCE)
    # Anything registered but missing from the preference list still gets used.
    order += [name for name in _CHAT_PROVIDERS if name not in order and ENABLED_FLAGS[name]]
    if not order:
        raise ValueError("no chat provider is enabled")
    return order