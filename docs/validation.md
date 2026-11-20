# Validación de despliegue — Task 11

Ejecución local del 19–20 de noviembre de 2026 (America/Bogota), Linux/amd64, Docker Compose 5.6.0. Pruebas dirigidas por impacto; no se ejecutó la batería aislada de seguridad contra las bases de entrega ni se borraron registros o volúmenes.

## Resultados ejecutados

| Prueba | Resultado observado |
| --- | --- |
| `docker compose config --quiet` | Pasa para base y overlay de réplicas. |
| Dockerfile Razor | Imagen multietapa construida; portal real ejecutado dentro de Docker. |
| Trust bundles | `prepare-trust.sh` ejecutado; conserva CA públicas y añade la CA de despliegue. |
| Readiness | Los once servicios base alcanzaron `healthy`; el overlay añade un segundo Razor y Gateway saludables. |
| Smoke por ingreso/Gateway | HTTPS `/health` y descubrimiento OIDC 200; catálogo Desastres 200; readiness Daños, Integración, Reconstrucción y Eden 200; API de desastres sin autenticación 401. |
| Usuario/contraseña y logout | Code/S256, sin OTP ni MFA; callback real y cookie segura; Desastres/Daños/Reconstrucción 200; logout sin CSRF 400 y logout válido completo. Ejecutado también con el script reproducible de biblioteca estándar `verify-session.sh`. |
| Daños/PostgreSQL | Creación 201, consulta persistida 200, replay de UUID 200 con el mismo `evaluationId`, edición Draft exitosa, versión obsoleta 409. |
| Evidencias de Daños | PDF real en Storage privado, hash, estado `Verified`, URL temporal autorizada y bytes descargados iguales. |
| Validación e historial | Evaluación `Validated`, historial real consultado; mapa/posición conservados en el registro con coordenadas. No se realizó una prueba visual del mapa. |
| Cadena de reconstrucción | Desastre autorizado 4 → evaluación Task 11 → propuesta `818b4bb5-0c91-4763-8250-8d938578c948` → proyecto `bf3f2cad-c2e7-4d17-82dd-c2d1f2501595` → formalización DEMO → monitoreo con imagen/PDF reales → `Closed` y reporte final 200. Reporte de actividad repetido conserva versión y efectos. |
| RabbitMQ Desastres | `Prefer: respond-async` devuelve 202; consumidor real crea el desastre sintético 12; repetición síncrona devuelve `AlreadyProcessed` con ID 12. No se simuló el broker. |
| RabbitMQ Reconstrucción | Evento de selección de propuesta consumido y `FormalizationRequest` persistido; eventos del ciclo hasta cierre procesados, con `ProjectClosed` consultable. |
| Corrección de workers | Dos pruebas dirigidas de `DisasterScopeAccessTests` pasan: ámbito de administrador funcional y ámbito de evento sin `HttpContext`, sin acceso global ni sustitución de claims HTTP. |
| Android offline | `OfflineAssessmentInstrumentedTest.offlineAssessmentEvidenceAndSessionRecovery`: **OK, 1 test**, 134.535 s. Room/borrador/PDF sin red → reconexión → batch/evidencia reales → replay `AlreadyProcessed`, archivo local, cursor y aislamiento entre dos identidades. APK exacto y firma verificados. |
| Persistencia/recovery | Tras recrear Daños, Integración, RabbitMQ, Reconstrucción, Razor e ingreso: evaluación `Validated`, evidencia `Verified`, proyecto y reporte `Closed`; misma cantidad de proyecciones del proyecto y mismo UUID de desastre `AlreadyProcessed`. |
| Sesión persistente | Recreadas ambas réplicas Razor: el mismo valor de cookie fue aceptado sin redirección de login en ambos destinos; claves/ticket permanecen en el volumen. |
| Bootstrap repetido | Ejecutado contra el realm persistente; login posterior conserva la identidad funcional; Keycloak final sin variables `KC_BOOTSTRAP_*`. Clientes, mappers y callbacks se reconcilian sin volver a crear usuarios. |
| Reparto real | 40 peticiones a Gateway: 20/20. 40 a Razor: 20/20. Gateway pausado: 20/20 solicitudes van al destino sano; recuperado: vuelve al reparto 20/20. Se ajustó el sondeo a timeout 1 s, fall/rise 2 para retirar procesos que no responden. |

## Incidencias encontradas y corregidas

- El ingreso necesitaba una red con salida para publicar el puerto; sus redes privadas por sí solas no lo hacían accesible.
- La clave TLS debía ser legible por los UID de los procesos. Permanece dentro de la configuración protegida, fuera de imágenes/Git.
- Los contratos Java exigen HTTPS fuera de loopback. Sus conexiones a Eden/Desastres usan el ingreso HTTPS verificado, sin activar una excepción de desarrollo para HTTP remoto.
- Al habilitar los workers de Reconstrucción, el filtro de acceso intentaba leer `HttpContext` ausente. Ahora cada scope de proyección queda limitado al desastre del evento; las peticiones conservan su alcance JWT y no reciben ese permiso.
- Las pruebas Android llamaban una firma antigua de Retrofit. Ahora usan el binding de sesión de la aplicación a través de un EntryPoint exclusivamente Debug.
- El emulador original no arrancaba por espacio en disco. La prueba utilizó un AVD aislado en memoria, sin vaciar ni modificar los datos del AVD existente. Su ruta de red usó un túnel CONNECT de prueba; no se deshabilitó TLS.
- Los primeros intentos de algunas pruebas fallaron por disponibilidad durante recreación o por expectativas incorrectas del propio harness (`evaluationId`, `ExpectedVersion`, recepción asíncrona). Los resultados positivos de la tabla corresponden a las ejecuciones corregidas, no a esos intentos.

## Datos conservados y límites

Se conservaron los volúmenes existentes de identidad/Eden y toda la persistencia externa de Supabase. Los datos sintéticos Task 11 se mantienen para auditoría. Los registros previos de demostración no fueron eliminados. Los mensajes históricos que fallaron antes de corregir el worker permanecen en DLQ (formalización 10, monitoreo 3, cierre 4); no se purgaron ni se declararon reprocesados desde DLQ. Las proyecciones se recuperaron desde la Outbox publicada al recrear Reconstrucción. Las colas de integración/eventos pendientes sin consumidor externo implementado conservan sus mensajes; no se afirma una integración externa inexistente.

La financiación continúa siendo simulada. El perfil de Reconstrucción conserva `Development` porque así lo exige ese adaptador, con `Security__LocalDemo=false` y JWT obligatorio. La adquisición OIDC nativa y un Release Android con firma de distribución no están implementados por esta tarea; el artefacto validado corresponde al flujo Debug existente con identidad externa vigente.

No se midieron disponibilidad porcentual, throughput, capacidad de usuarios ni objetivos ATAM. No se probó failover del host, base de identidad o broker. La prueba offline fue una prueba real instrumentada, no una certificación de todos los dispositivos Android.

## Distribución y clon independiente

El manifiesto final de imágenes y los resultados de `pull`/arranque desde el clon independiente se registran al completar la publicación. El arranque reutiliza las identidades y datos autorizados existentes; no implica restauración de un host vacío sin configuración ni respaldo de datos.
