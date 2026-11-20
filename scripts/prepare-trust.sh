#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Public CA bundle plus the supplied deployment CA; no certificates or private keys are generated.
# A trusted public-CA certificate can use its CA chain as config/tls/deployment-ca.crt.
damage_image=$(docker compose config --images damage)
bootstrap_image=$(docker compose --profile bootstrap config --images bootstrap)
docker run --rm --user 0 \
  -v "$PWD/config/trust:/output" -v "$PWD/config/tls:/certificates:ro" \
  --entrypoint bash "$damage_image" -ec '
    test -r /certificates/deployment-ca.crt
    cp "$JAVA_HOME/lib/security/cacerts" /output/trust.jks
    keytool -importcert -noprompt -alias reconecta-deployment \
      -file /certificates/deployment-ca.crt -keystore /output/trust.jks -storepass changeit
    chmod 644 /output/trust.jks
  '
docker run --rm \
  -v "$PWD/config/trust:/output" -v "$PWD/config/tls:/certificates:ro" \
  --entrypoint python "$bootstrap_image" -c '
import pathlib,ssl
p=pathlib.Path(ssl.get_default_verify_paths().cafile)
pathlib.Path("/output/ca-bundle.crt").write_bytes(p.read_bytes()+pathlib.Path("/certificates/deployment-ca.crt").read_bytes())
'
