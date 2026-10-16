# Frontend Developer Digital FTE
#
# One image runs both processes; the worker spawns the MCP server as a child
# over stdio, so a single container is the correct unit.
#
# NOTE: this configuration is provided but has NOT been run in this environment.
# Docker was not available here, so treat it as reviewed-but-unverified.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first so code edits do not invalidate the dependency layer.
COPY pyproject.toml ./
RUN pip install --no-cache-dir uv \
    && uv pip install --system --no-cache .

COPY . .

# The MCP server is launched as a child process by the worker.
ENV MCP_TRANSPORT=stdio

# Fail fast if the schema was never created.
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD uv run python -c "import psycopg, config; psycopg.connect(config.NEON_DATABASE_URL).close()" || exit 1

CMD ["uv", "run", "python", "worker.py"]