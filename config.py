"""Single source of truth for Digital FTE runtime configuration.

Both the worker (`worker.py`) and the scoped MCP server
(`frontend_workspace_mcp/server.py`) import from here so a credential can never
drift between the two processes.

Provider policy
---------------
Several provider credentials are configured so the FTE survives one running
out of quota. Two of them are Gemini credentials (a primary and a fallback
key on the same endpoint and models); the router treats each credential as its
own provider, so the preferred one is tried first, on quota exhaustion the
next is used, and control returns automatically once the preferred
credential's quota resets (see `provider_router.py`).

Only quota/rate-limit failures trigger a rotation. A misconfigured credential or
a genuine bug is surfaced instead of being silently routed around, so a broken
key can never look like a healthy system.

Secrets are read from the environment by `require_config()`; the gitignored
`.env` holds the live values for local runs. Nothing here hard-codes a
credential, and `test_config.py`'s planted-secret scanner enforces that.
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

# Gemini (fallback credential): chat + embeddings on a second key. Same
# endpoint and same models as the primary, so whichever credential serves, the
# model label is identical and stored vectors stay comparable. Free-tier quota
# is per key, so this is a real second path, not a cosmetic one. An empty key
# keeps the route disabled.
GEMINI_FALLBACK_API_KEY = os.getenv("GEMINI_FALLBACK_API_KEY", "")
GEMINI_FALLBACK_ENABLED = bool(GEMINI_FALLBACK_API_KEY) and os.getenv(
    "GEMINI_FALLBACK_ENABLED", "1"
) != "0"

# --- Embeddings --------------------------------------------------------------

# Every embedding provider must agree on dimensionality; pgvector columns are
# sized to it. Chat-only providers are deliberately absent from this mapping.
EMBEDDING_DIMENSIONS = 768
PREFERRED_EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "gemini").strip().lower()
EMBEDDING_MODELS = {
    "gemini": GEMINI_EMBEDDING_MODEL,
    "gemini-fallback": GEMINI_EMBEDDING_MODEL,
    "openai": OPENAI_EMBEDDING_MODEL,
}

# --- Runtime -----------------------------------------------------------------

PROVIDER_COOLDOWN_SECONDS = float(os.getenv("PROVIDER_COOLDOWN_SECONDS", "900"))

NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL", "")

# --- Runtime database credential ---------------------------------------------
#
# `NEON_DATABASE_URL` is the schema owner: `setup_neon.py` uses it to create and
# migrate the schema. The running worker and MCP server should not hold owner
# rights, so `setup_neon.py` can also provision a restricted `feds_app` role and
# its URL goes here. When set, the runtime uses the restricted role and a
# compromise of the app environment is no longer full database ownership.
#
# Unset keeps the owner URL so a single-credential deployment still works; the
# trade-off is recorded in deployment.md.
FEDS_APP_DATABASE_URL = os.getenv("FEDS_APP_DATABASE_URL", "")

# What the worker and MCP server actually connect with. Not a secret of its own:
# it resolves to the restricted role when provided, else the owner.
DATABASE_URL = FEDS_APP_DATABASE_URL or NEON_DATABASE_URL


# --- Operator authorization --------------------------------------------------
#
# Decision attribution answers "who decided"; this policy answers "who MAY
# decide". Read at call time so the environment is the single switch, testable
# without reimporting anything.
#
#   FEDS_ALLOWED_OPERATORS="alice,bob"
#
# Unset keeps single-operator local mode: only `operator-local` may decide.
# Once a list is set it is enforced exactly - `operator-local` itself must be
# listed to keep working, so a shared deployment can never be decided by the
# anonymous default.

DEFAULT_OPERATOR = "operator-local"


def allowed_operators() -> set[str] | None:
    """The configured allowlist, case-folded; None means local-only mode."""
    raw = os.getenv("FEDS_ALLOWED_OPERATORS", "")
    names = {part.strip().casefold() for part in raw.split(",") if part.strip()}
    return names or None


def operator_authorized(operator: str) -> bool:
    """Whether this operator may approve or reject a parked run.

    Fail-closed: an empty name is never authorized, and a configured list
    admits only its members.
    """
    name = (operator or "").strip().casefold()
    if not name:
        return False
    allowlist = allowed_operators()
    if allowlist is None:
        return name == DEFAULT_OPERATOR.casefold()
    return name in allowlist


# --- Cost accounting ----------------------------------------------------------
#
# List price in USD per one MILLION tokens as (input, output). This keeps the
# per-conversation token and cost rollup real instead of always null.
#
# These figures are the flash-tier list-price equivalents; the rollup reports
# them as estimates (see cost_cents_for), not as billing data. A model absent
# from this table gets cost_cents = NULL: no *known* price, never a fake zero.
# Override any figure from the environment, e.g.
# GEMINI_PRICING_USD_PER_M="0.25,2.00".


def _env_pricing(provider: str, default: str) -> tuple[float, float]:
    """Read "input,output" pricing from an env var, falling back to defaults."""
    raw = os.getenv(f"{provider.upper()}_PRICING_USD_PER_M", default)
    try:
        first, _, second = raw.partition(",")
        return float(first), float(second)
    except ValueError:
        return tuple(float(part) for part in default.split(","))


MODEL_PRICING_USD_PER_M_TOKENS = {
    "gemini-3.5-flash": _env_pricing("gemini", "0.30,2.50"),
    "gemini-3.5-flash-lite": _env_pricing("gemini-lite", "0.10,0.40"),
    "openai-gpt-5-mini": _env_pricing("openai", "0.25,2.00"),
}


def cost_cents_for(model: str, input_tokens: int, output_tokens: int) -> int | None:
    """Estimated cost in cents for one set of token counts, or None if unknown.

    Tokens and prices are per-model, so a call rotated to another provider must
    always be recorded under the model actually used - never averaged across
    models.
    """
    price = MODEL_PRICING_USD_PER_M_TOKENS.get(model)
    if price is None:
        return None
    per_m_input, per_m_output = price
    return round(
        (input_tokens * per_m_input + output_tokens * per_m_output) / 10_000
    )



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
    "gemini-fallback": {
        "enabled": GEMINI_FALLBACK_ENABLED,
        "model": GEMINI_CHAT_MODEL,
        "base_url": GEMINI_BASE_URL,
        "api_key": GEMINI_FALLBACK_API_KEY,
    },
    "openai": {
        "enabled": OPENAI_ENABLED,
        "model": OPENAI_CHAT_MODEL,
        "base_url": OPENAI_BASE_URL,
        "api_key": OPENAI_API_KEY,
    },
    }

# Preference order for chat. Gemini leads; the fallback key covers its quota
# gaps; anything else is ordered after them.
CHAT_PREFERENCE = ("gemini", "gemini-fallback", "openai")

CHAT_MODELS = {
    name: {"model": cfg["model"], "base_url": cfg["base_url"], "api_key": cfg["api_key"]}
    for name, cfg in _CHAT_PROVIDERS.items()
}

ENABLED_FLAGS = {name: bool(cfg["enabled"]) for name, cfg in _CHAT_PROVIDERS.items()}

# Credential per provider, for callers that build their own clients (the MCP
# server's embedding router). Keyed by provider name so a fallback credential
# can never be served with the primary's key by accident.
PROVIDER_API_KEYS = {name: str(cfg["api_key"]) for name, cfg in _CHAT_PROVIDERS.items()}


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
    if FEDS_APP_DATABASE_URL and FEDS_APP_DATABASE_URL == NEON_DATABASE_URL:
        problems.append(
            "FEDS_APP_DATABASE_URL is identical to NEON_DATABASE_URL, so the runtime "
            "still holds the schema owner credential. Point it at the restricted "
            "role created by setup_neon.py (FEDS_APP_DB_PASSWORD), or unset it."
        )
    if not chat_order():
        problems.append(
            "No chat provider is enabled. Set GEMINI_API_KEY (a second Gemini key "
            "can be added as GEMINI_FALLBACK_API_KEY) in .env or the environment."
        )
    if not problems and not embedding_order():
        problems.append(
            "No embedding provider is enabled. GEMINI_API_KEY (or "
            "GEMINI_FALLBACK_API_KEY) must be set, because embeddings need a "
            "provider of their own."
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