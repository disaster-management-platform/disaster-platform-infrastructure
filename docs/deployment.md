# Despliegue reproducible de RECONECTA

Solo se requiere Git, Docker Engine con Compose v2 reciente/v5 y Bash en el destino; no .NET, Java, Maven ni los repositorios de aplicaciones. Supabase PostgreSQL y Storage siguen siendo externos, con sus esquemas, migraciones, buckets privados y credenciales de dominio existentes. El DAL está incorporado en las imágenes .NET como NuGet. Android se instala por separado.

## 1. Imágenes y distribución

`.env.example` fija imágenes publicadas por digest; `images.lock.json` registra su procedencia. No usar etiquetas locales Task 10. Para paquetes GHCR privados, autenticar previamente Docker con una credencial autorizada de lectura de paquetes, mediante `docker login ghcr.io --password-stdin`.

Los Dockerfiles de los repositorios de aplicaciones continúan siendo los contratos de construcción. Razor tiene ahora un Dockerfile multietapa y contexto filtrado. Disaster Management y Reconstrucción requieren `--secret id=nuget_credentials,src=<archivo-privado>` de BuildKit. Nunca pasar el token como ARG, ENV o COPY. La imagen publicada de Eden incorpora la plantilla `platform`, sus adaptaciones y el runtime validado, sin montar código de otro repositorio en el destino.

## 2. Preparación y arranque

```bash
git clone https://github.com/disaster-management-platform/disaster-platform-infrastructure.git
cd disaster-platform-infrastructure
cp .env.example .env
cp -r config.example config
```

Completar [los contratos de configuración](../config.example/README.md). El DNS de `PORTAL_HOST`, `IDENTITY_HOST` y `EDEN_HOST` debe resolver al ingreso desde navegadores y Android. Dentro de Docker, los alias resuelven esos mismos nombres al ingreso; el issuer no cambia al pasar entre navegador y contenedor. Los valores `*.localtest.me` son exclusivamente la demostración de loopback; para teléfonos físicos/servidores usar DNS y certificados autorizados del despliegue. Confiar explícitamente en la CA privada de desarrollo, nunca desactivar verificación TLS.

Preparar los bundles de confianza antes del arranque. Con las imágenes descargadas, `./scripts/prepare-trust.sh` puede construir ambos bundles a partir de `config/tls/deployment-ca.crt`; conserva las CA públicas necesarias para Storage. El certificado/clave y `ingress.pem` deben ser suministrados por el operador, fuera de Git.

Si se preservan datos locales existentes, establecer los nombres reales de `IDENTITY_VOLUME` y `EDEN_VOLUME` en `.env`, detener sus anteriores propietarios y usar un solo escritor de Eden. No ejecutar dos PostgreSQL contra el mismo volumen. Para una instalación nueva, conservar los nombres independientes de `.env.example`. No borrar ni recrear volúmenes para aprovisionar.

Tras suministrar la configuración autorizada:

```bash
docker compose config --quiet
docker compose pull
./scripts/bootstrap.sh
docker compose up -d --wait
./scripts/smoke-test.sh
```

El bootstrap usa una utilidad Python en contenedor, reconcilia clientes/roles/mappers/callbacks, conserva identidades y concesiones, deshabilita OTP obligatorio y prepara el volumen privado de tickets/claves de Razor. El administrador temporal solo se inyecta durante esa invocación; el contenedor final se recrea sin esas variables. La administración Keycloak pasa por un listener privado sin puerto de host, bloqueada en el ingreso público. `grants.json=[]` conserva las concesiones existentes; un realm nuevo necesita concesiones de dominio explícitas.

Los siguientes inicios solo requieren:

```bash
docker compose up -d --wait
./scripts/smoke-test.sh
```

No se ejecutan migraciones de dominio automáticamente. La financiación existente sigue siendo **DEMO SIMULADA**, no dinero de un proveedor real. Por el contrato actual de ese adaptador, Reconstrucción usa `Development` con `Security__LocalDemo=false`, JWT obligatorio y URLs reales de Daños/Desastres. No considerar ese perfil una certificación de producción.

## 3. Red, persistencia y disponibilidad de procesos

Solo se publica HTTPS en `HTTPS_BIND:443`. APIs, PostgreSQL, AMQP, RabbitMQ Management, WildFly Management y el listener administrativo de identidad no tienen puertos de host. Las redes de servicios e identidad son privadas; una red de salida permite Supabase y dependencias externas.

El ingreso HAProxy verifica los certificados de Keycloak y Razor y consulta salud de cada destino. El Gateway conserva las rutas YARP y verifica JWT; sus destinos tienen sondeos activos y detección de errores de transporte. Las llamadas Java hacia Eden/Desastres usan HTTPS verificado por el ingreso, conforme a sus contratos originales.

Volúmenes: `identity-data`, `eden-data`, `rabbitmq-data`, `razor-data`. Los dos últimos subdirectorios privados de Razor contienen claves de Data Protection y tickets cifrados compartidos entre réplicas. Mantenerlos juntos al recrear contenedores. Reiniciar no elimina datos de Supabase, archivos de Room ni evidencias del dispositivo.

Todos los procesos de larga duración tienen reinicio `unless-stopped` y health checks. `up --wait` comprueba disponibilidad inicial; un estado Docker `unhealthy` por sí solo no reinicia un proceso. Ante un fallo de despliegue WildFly después de un error DNS/dependencia, revisar la causa y recrear únicamente ese servicio. No declarar un SLA por tener reinicios o réplicas.

## 4. Réplicas selectivas

```bash
docker compose -f compose.yaml -f compose.scale.yaml up -d --wait
```

El overlay escala únicamente Razor y Gateway a dos procesos. No fija `container_name` ni puertos de host en réplicas. HAProxy resuelve las IP mediante DNS de Docker, reparte round robin y retira destinos que no responden. `X-Deployment-Node` permite observar el destino elegido sin exponer credenciales.

No escalar Eden/SQLite ni multiplicar arbitrariamente pools de Supabase. Este perfil no prueba escalabilidad del negocio ni alta disponibilidad de PostgreSQL o RabbitMQ.

## 5. Validación y operación

`smoke-test.sh` usa únicamente Docker y valida TLS, issuer, readiness de propietarios, rutas públicas y rechazo 401 de una API protegida. No crea registros. Para comprobar usuario/contraseña, PKCE, páginas funcionales y logout con CSRF:

```bash
# Completar config/validation.json con un usuario funcional existente y desastre autorizado.
./scripts/verify-session.sh
```

Los resultados ejecutados y sus límites están en [validation.md](validation.md). Los registros sintéticos Task 11 se conservan para auditoría; no borrarlos para repetir pruebas. Nunca ejecutar `down -v`, reset de Supabase, purga de colas o `adb uninstall` para reiniciar el sistema.

Para recrear un servicio manteniendo datos:

```bash
docker compose up -d --wait --force-recreate damage
./scripts/smoke-test.sh
```

Con el overlay de réplicas activo, incluir también `-f compose.yaml -f compose.scale.yaml` en los comandos que modifiquen Razor/Gateway. Consultar `docker compose ps` y los logs del propietario del error; no imprimir `.env`, tokens ni claves.

## 6. Android e identidad

Ver [android.md](android.md) para el artefacto exacto, hash, configuración HTTPS y prueba offline. No instalar .NET/Java en el servidor para distribuirlo. La adquisición nativa OIDC del cliente Android sigue limitada por lo que ya implementa su repositorio; no se presenta una pantalla Debug de importación de token como un login móvil OIDC terminado.

La documentación detallada anterior de identidad se conserva en [identity.md](identity.md). Un administrador de Keycloak no adquiere por ello permisos funcionales. Los usuarios conservan roles, organización y concesiones de desastre; los workers usan el alcance del evento de dominio y no una identidad humana suplantada.


## Confianza del navegador en la demostración local

Este host no permite instalar la CA del sistema sin contraseña de sudo. Los contenedores y el APK ya usan su ancla autorizada. Antes del acceso desde el navegador, el administrador puede instalar **solo el certificado público**:

```bash
sudo install -m 644 config/tls/deployment-ca.crt /usr/local/share/ca-certificates/reconecta-task11.crt
sudo update-ca-certificates
```

Si el navegador mantiene un almacén propio, importar también `config/tls/deployment-ca.crt` como autoridad confiable. No importar `server.key` ni usar opciones que omitan la comprobación TLS. En un despliegue con certificado de una CA ya confiable, suministrar su cadena autorizada y no instalar esta CA de demostración.
