# Platform infrastructure

## Identity (08A/08B)

Keycloak 26.7 runs with HTTPS, a dedicated persistent PostgreSQL identity database, bounded pools and JDBC discovery for the Infinispan cluster. Identity persistence is independent of domain schemas; no domain database grants are given to Keycloak. These local containers are not a highly available database or a production SLA deployment.

Keep configuration and certificates outside Git. `KC_PUBLIC_URL` is the stable HTTPS origin. `KC_CERTIFICATE_DIR` contains `server.crt` and `server.key`, readable by container UID 1000. Supply a trusted deployment certificate; isolated development may use its own trusted CA, never disabled verification. `KC_DB_PASSWORD` is external (at least 32 base64url characters). The non-administrative `keycloak_runtime` owns only the identity database objects; the separate bootstrap database administrator uses `KC_DB_ADMIN_PASSWORD`. Domain services receive neither credential. PostgreSQL is reachable only inside the identity network.

Initial provisioning:

```sh
docker compose --env-file "$IDENTITY_ENV" -f security/compose.yaml -f security/bootstrap.yaml up -d
python3 security/configure.py
docker compose --env-file "$IDENTITY_ENV" -f security/compose.yaml up -d --force-recreate keycloak
```

The Python command reads exported variables, never executes an env file: `KC_PUBLIC_URL`, temporary `KC_BOOTSTRAP_ADMIN_USERNAME/PASSWORD`, `KC_CA_FILE` if needed, `KC_RAZOR_REDIRECT_URI` and `KC_ANDROID_REDIRECT_URI`. Bootstrap credentials are absent from the normal server configuration. Rotate/remove the temporary bootstrap account after establishing controlled administrator access. Never use it in a business service.

A second local replica can be started on the same network/database with `docker compose --env-file "$IDENTITY_ENV" -f security/compose.yaml run -d --name platform-identity-keycloak-b -p 127.0.0.1:18444:8443 keycloak`. Both nodes share the same issuer. Production needs one stable HTTPS ingress and a resilient identity database; client redirect URIs never depend on the selected replica. Do not expose database/JGroups ports publicly. No existing Docker installation, network or volumes are replaced.

### Contracts

- Realm `platform`; discovery at `/realms/platform/.well-known/openid-configuration`; JWKS from discovery. APIs validate signature, exact issuer, audience and lifetime locally, caching signing keys. A cold instance cannot obtain unknown keys during issuer outage. Login and token renewal require the issuer; already-issued unexpired JWTs remain locally verifiable.
- Roles stay in string-array `role`, user identity in `sub`, administrative organization in `organization_id`, integer-array grants in `disaster_id`. Organization and disaster attributes are administrator-editable only. No business roles or organizational grants are assigned by provisioning. Service accounts receive only explicitly approved role scope mappings and attributes. The test principal uses synthetic organization `security-test-A`, never a real domain grant.
- API audiences: `disasters-api`, `reconstruction-api`, `damage-assessment-api`, `integration-service`. Browser/mobile clients request only the relevant optional audience scopes. Owners still enforce organization, disaster and resource permissions. SSO does not repair Eden authorization.
- `razor-web`: confidential Authorization Code + S256 PKCE, exact external redirect URI, tokens stored on the server, secure HttpOnly SameSite cookies, CSRF protection, distributed encrypted ticket/key storage for replicas. No password grant or browser-held client secret. This iteration defines the presentation contract without implementing screens.
- `android`: public Authorization Code + S256 PKCE via system browser, exact application callback, state/nonce validation. No APK client secret. Keystore protects stored credentials; Room remains identity/organization-scoped. A previously validated offline session may access its local authorized data; synchronization requires a current token. No implicit/password grant. OIDC UI/client implementation is a consumer integration, not an identity bypass.
- Browser authentication requires OTP enrollment and uses native Keycloak OTP. Password reset and brute-force protection remain native. Do not configure service accounts for interactive login or MFA.
- Service clients: `assessment-disasters`, `integration-disasters` (report ingestion), `integration-disasters-read` (read-only), `reconstruction-damage`, `reconstruction-disasters`. Confidential Client Credentials; short-lived bearer tokens, no refresh tokens. Reacquire before expiry with bounded HTTP timeouts; never automatically replay an uncertain business mutation. Secrets must be externally rotated. Failure to renew returns a dependency failure, not an administrative identity or anonymous fallback.

### Existing consumer settings

.NET uses `Security__Authority=<issuer>` and its exact `Security__Audience`; preserve HTTPS metadata validation. Jakarta uses `JWT_ISSUER`, `JWT_AUDIENCE` and `JWT_PUBLIC_KEY_LOCATION=<discovery jwks_uri>`, with `role` mapped to MicroProfile groups. Configure the trust store externally for private development CAs. No public-key pin copied from a transient test issuer replaces JWKS rotation.

Eden's pinned runtime provides the native `gluon.contrib.login_methods.oauth20_account.OAuthAccount` extension base, not a configured Keycloak SSO provider. Linking verified Keycloak identities to existing Eden accounts and memberships must preserve Eden ACLs/realms; do not grant administrator privileges or derive resource authorization from SSO alone. Unvalidated logistics modifications are excluded from security publication.

### Validation

`security/test_identity.py` requires exported provisioning settings, `requests`, BeautifulSoup and PyJWT/cryptography. It tests real Client Credentials, scoped claims, browser OTP enrollment and rejection of invalid signatures, issuer, audience and expired real tokens. Synthetic user credentials are generated in memory. Certificates, service secrets and tokens must never be committed or logged. Both scripts require `SECURITY_ISOLATED_TESTS=1` and must run only against an isolated identity realm. Their synthetic principals must not be enabled for production; remove test clients/grants after validation.

JWT acceptance and audience/signature rejection were also checked in real WildFly 42 and YARP; role, disaster and foreign-resource denials used isolated PostgreSQL. Local failover was checked with two real Keycloak instances: the second issued same-issuer tokens while the first was stopped; cached-key validation continued with both stopped. These checks do not measure availability, throughput or domain authorization, nor certify every API consumer.

`security/test_consumers.py` uses `SECURITY_TEST_CLIENT_FILE` (private output outside Git), optional comma-separated `SECURITY_CONSUMER_URLS`, `SECURITY_DAMAGE_URL`, and `SECURITY_DISASTERS_URL`. Run only against isolated test databases: it creates synthetic test clients and a preliminary evaluation to verify ownership. The Java and .NET token-renewal checks use an isolated client with a five-second lifespan, restored after testing. Initial database bootstrap was also checked from an empty dedicated volume with the non-superuser runtime role.

YARP enables bearer verification with `Security__Authority` and `Security__Audiences__0` (and following indexes). Both issuer and token endpoint configuration require HTTPS. Invalid supplied Authorization headers receive 401 before forwarding. Anonymous routes remain governed by the owner; this creates no browser session and grants no permissions. Configure deployment CA trust externally.

Existing identity volumes must be migrated administratively before switching database usernames: create the separate runtime role, transfer only the identity database/schema/user-table ownership, and retire the previous runtime credential. Do not remove the volume. The local upgrade preserved the database and disabled login/password on the legacy bootstrap role; bootstrap initialization scripts run only for empty volumes.
