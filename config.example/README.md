# Configuración autorizada (fuera de Git)

Copiar este directorio a `config/`. Mantener el directorio privado (`chmod 700 config`) y los `.env` con modo 600. Los archivos montados deben ser legibles por los UID de los contenedores: Razor 1654, WildFly/Keycloak 1000 y HAProxy 99. En el despliegue local validado, los certificados y claves montados tienen modo 644 dentro de este directorio privado. Usar permisos de grupo equivalentes si el operador administra los UID/GID.

- `tls/server.crt`, `tls/server.key`: certificado PEM y clave autorizados, con SAN de los tres nombres públicos definidos en `.env`.
- `tls/ingress.pem`: concatenación de certificado/cadena y clave, legible por HAProxy.
- `tls/deployment-ca.crt`: CA/cadena pública de confianza; ninguna clave privada aquí.
- `trust/ca-bundle.crt`: CA públicas del sistema más la CA de despliegue para .NET/Python.
- `trust/trust.jks`: truststore Java con CA públicas **y** CA de despliegue; contraseña del almacén público `changeit`.
- `trust/supabase-ca.crt`: CA autorizada del PostgreSQL externo. Conservar `verify-full`/`VerifyFull`.
- `runtime/*.env`: contratos originales de cada servicio; completar únicamente con credenciales autorizadas. Compose interpola `${IDENTITY_HOST}`, `${EDEN_HOST}` desde `.env`. Contraseñas con `$` literal deben usar el escape `$$` del formato Compose.
- `bootstrap.env`: administrador de aprovisionamiento Keycloak existente/autorizado; exclusivamente para bootstrap. No es un administrador funcional ni credencial de aplicación.
- `eden/000_config.py`: configuración nativa existente de Eden (SQLite persistente); no ejecutar inicialización/reset de registros.
- `eden/delegations.json`, `eden/bindings.json`: conservar exactamente la estructura y concesiones administradas existentes. Las plantillas vacías **no conceden permisos**. Si cambia el issuer, reconciliar explícitamente los enlaces issuer+subject existentes conservando los mismos usuarios/ACL.
- `grants.json`: concesiones de cuentas de servicio autorizadas. `[]` conserva las actuales. Para un realm nuevo se requieren entradas con `clientId`, `organization_id`, `disaster_id` (array de enteros) y `roles` (array de roles mínimos). Nunca copiar organizaciones ficticias. `assessment-disasters`, `integration-disasters-read` y `reconstruction-disasters` usan `disasters.organization.read`; `reconstruction-damage` usa `damage.read`; `integration-disasters` usa `disasters.integration`.
- `validation.json`: usuario funcional autorizado y un desastre accesible para `verify-session.sh`; no se usa por las aplicaciones.

`ConnectionStrings__Disasters` conserva su nombre histórico en ambos servicios .NET, pero cada uno debe recibir su identidad/esquema de dominio propios. Incluir `SSL Mode=VerifyFull;Root Certificate=/run/supabase-ca.crt;Maximum Pool Size=20;Timeout=15;Command Timeout=30` según el contrato existente; no reemplazar el resto de la cadena. Java limita cada pool a 8. Considerar la suma de pools antes de escalar.

Las credenciales de `runtime/identity-db.env` y `runtime/keycloak.env` deben coincidir. Para una base existente, conservar los nombres/propiedad originales y el rol `keycloak_runtime`; el inicializador solo se ejecuta en volúmenes vacíos. La contraseña `KC_DB_PASSWORD` debe cumplir el contrato base64url de al menos 32 caracteres.

RabbitMQ: usar la misma cuenta dedicada en `runtime/rabbitmq.env`, `Ingestion__UserName/Password` y `Messaging__UserName/Password`. En un volumen existente, cambiar variables no rota usuarios; realizar esa operación de forma administrativa. La cuenta `guest` no se utiliza.

Los seis secretos de cliente de servicio/web se suministran en los perfiles respectivos. El bootstrap los reconcilia con esos valores explícitos, sin regenerarlos en cada inicio. No cambiar un secreto compartido con otros despliegues sin rotación coordinada.

El bootstrap no crea usuarios humanos, no deduce organizaciones ni concede permisos a un administrador técnico. Los roles y atributos de los usuarios de RECONECTA se mantienen administrados en Keycloak.
