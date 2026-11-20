# Android — artefacto de demostración validado

APK: [reconecta-task11-1.0-debug.apk](https://github.com/disaster-management-platform/disaster-mobile-client/releases/download/task11-20261119/reconecta-task11-1.0-debug.apk), paquete `co.edu.javeriana.disasterplatform.disaster_mobile_client`, versión 1.0 (1), firmado con la clave Debug existente del proyecto. No es un APK Release de producción ni incluye un login nativo OIDC terminado.

SHA-256: `86ac59845f570f16f85e0d796ba006adeea438059505aa211e2b581ef7b56c3e`.

Endpoint compilado: `https://reconecta.localtest.me/api/`. CA pública del despliegue local incorporada como ancla de confianza adicional; se conservan verificación TLS de cadena y hostname. No contiene JWT, contraseña ni clave privada. Para otro despliegue, construir el APK en CI/estación de desarrollo (no en el servidor) con su URL y, solo si usa CA privada, su certificado público:

```bash
./gradlew -PAPI_BASE_URL=https://<portal-autorizado>/api/ \
  -PDEPLOYMENT_CA_FILE=<ruta-al-certificado-publico-CA> assembleDebug
```

Sin la propiedad opcional, el contrato de confianza habitual del proyecto permanece vigente. Release conserva su configuración y no permite endpoints HTTP. La rama de evaluaciones offline sigue siendo la implementación Debug existente; no se presenta como funcionalidad Release ya terminada.

Instalar sin borrar Room ni evidencias:

```bash
curl -fLO https://github.com/disaster-management-platform/disaster-mobile-client/releases/download/task11-20261119/reconecta-task11-1.0-debug.apk
sha256sum reconecta-task11-1.0-debug.apk
adb install -r reconecta-task11-1.0-debug.apk
adb shell monkey -p co.edu.javeriana.disasterplatform.disaster_mobile_client 1
```

No ejecutar `adb uninstall`, `pm clear` ni reinicializar el AVD existente. Para actualizar una instalación, su firma debe coincidir; conservar la clave Debug de distribución o usar el proceso administrado de firma de la organización.

La prueba instrumentada `OfflineAssessmentInstrumentedTest.offlineAssessmentEvidenceAndSessionRecovery` pasó contra el Gateway HTTPS del nuevo Compose con dos identidades funcionales reales obtenidas por Authorization Code/S256. Confirmó almacenamiento local de borrador/PDF sin red, SHA-256, sincronización con PostgreSQL/Storage, referencia autorizada, reintento `AlreadyProcessed`, cursor, lectura local del PDF y aislamiento entre usuarios. La prueba duró 134.535 s; no es una medición de rendimiento.

Los datos del AVD original no se vaciaron ni se alteraron. Por falta de espacio en disco se creó un AVD aislado temporal en memoria con la imagen Android 36.1 instalada. Para alcanzar los nombres de loopback se usó un túnel HTTP CONNECT local de prueba; el HTTPS y la validación del certificado permanecieron de extremo a extremo. Esto no añade un servicio al despliegue. En dispositivos físicos, configurar DNS real hacia el ingreso y un certificado autorizado; `localtest.me` resuelve al propio dispositivo y no es una dirección de producción.

La importación Debug de un token externo vigente sigue siendo el mecanismo existente para pruebas de evaluación. No se incrusta el token en el APK ni se activa Password Grant. La adquisición OIDC nativa completa y la firma Release de distribución siguen pendientes en el cliente original, fuera del alcance de empaquetado de esta tarea.
