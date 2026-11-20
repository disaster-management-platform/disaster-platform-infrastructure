#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose config --quiet
docker compose --profile bootstrap pull bootstrap
# Credentials exist only in this explicit initial provisioning invocation.
docker compose -f compose.yaml -f compose.bootstrap.yaml up -d --wait identity-db keycloak ingress
docker compose --profile bootstrap run --rm --no-deps bootstrap
# Drop bootstrap administrator environment from the long-running identity server.
docker compose up -d --wait --force-recreate keycloak
