#!/bin/sh
set -eu
case "$KC_DB_PASSWORD" in *[!A-Za-z0-9_-]*|'') exit 1;; esac
[ "${#KC_DB_PASSWORD}" -ge 32 ]
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=ON_ERROR_STOP=1 <<SQL
CREATE ROLE keycloak_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD '$KC_DB_PASSWORD';
ALTER DATABASE keycloak OWNER TO keycloak_runtime;
SQL
