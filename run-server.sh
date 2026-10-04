#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/llm-cp-server"

exec uv run llm-cp server start --host 0.0.0.0 --port "${API_PORT:-8040}" --reload
