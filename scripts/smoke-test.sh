#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose config --quiet
docker compose --profile bootstrap run --rm --no-deps bootstrap python scripts/smoke.py
