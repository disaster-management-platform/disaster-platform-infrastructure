#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose config --quiet
docker compose --profile bootstrap pull bootstrap
cleanup() {
  result=$?
  trap - EXIT
  # Remove bootstrap credentials even when provisioning fails; preserve its exit status.
  if ! docker compose up -d --wait --force-recreate keycloak; then
    echo 'Failed to remove bootstrap environment from Keycloak; inspect the container configuration.' >&2
    exit 1
  fi
  exit "$result"
}
trap cleanup EXIT
# Credentials exist only in this explicit provisioning invocation.
docker compose -f compose.yaml -f compose.bootstrap.yaml up -d --wait identity-db keycloak ingress
docker compose --profile bootstrap run --rm --no-deps bootstrap
