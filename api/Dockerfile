# =============================================================================
# ScholarGuard API — Multi-stage Dockerfile (Python 3.12 + uv)
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: builder — install dependencies with uv into a virtual-env
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy only dependency manifests first for layer caching
COPY pyproject.toml ./
COPY uv.lock* ./

# Create venv and install production dependencies
RUN uv venv /app/.venv \
    && uv sync --frozen --no-dev --no-install-project 2>/dev/null \
    || uv sync --no-dev --no-install-project

# ---------------------------------------------------------------------------
# Stage 2: development — hot-reload with source bind-mounted
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS development

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Bring in the pre-built virtualenv from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy source code (overridden by bind mount in docker-compose)
COPY . .

# Install the project itself (editable-style) so imports resolve
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---------------------------------------------------------------------------
# Stage 3: production — lean runtime image
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS production

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --create-home appuser

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY . .

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
