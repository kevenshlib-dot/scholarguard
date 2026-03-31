#!/bin/bash
set -e

# Install dependencies into the named volume on first run or when lockfile changes
MARKER="/app/.venv/.installed_hash"
LOCK_HASH=$(md5sum /app/pyproject.toml 2>/dev/null | cut -d' ' -f1)

if [ ! -f "$MARKER" ] || [ "$(cat $MARKER)" != "$LOCK_HASH" ]; then
    echo "[entrypoint] Installing Python dependencies..."
    UV_VENV_CLEAR=1 uv venv /app/.venv
    UV_LINK_MODE=copy uv sync --no-dev
    echo "$LOCK_HASH" > "$MARKER"
    echo "[entrypoint] Dependencies installed."
else
    echo "[entrypoint] Dependencies up to date."
fi

exec "$@"
