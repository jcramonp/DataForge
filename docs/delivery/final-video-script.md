# Guion de video final DataForge

Preparación: 9 de noviembre de 2026. Reparto y tiempos propuestos para ensayo,
no evidencia de que el video ya esté grabado. Duración objetivo 11:30; límite
12:00 incluyendo presentaciones y transiciones. Sin diapositivas. Todos los
integrantes deben aparecer mostrando una parte de la demostración.

## Estado previo y requisito pendiente

La PR #53 está abierta. El bloqueo de GitHub fue resuelto: CI #35
(run 42686987182) completó sus ocho jobs correctamente para el commit e819cba,
incluido el DAG Airflow de punta a punta.

Se agregó despliegue automático opcional de web/API, después del éxito de CI,
mediante S3 y SSM. Su primera verificación en AWS está pendiente de configurar
los secretos temporales y activar AWS_DEPLOY_ENABLED. Consultar
[el procedimiento](../operations/automatic-app-deployment.md).

Para grabar el requisito completo todavía debemos verificar un nuevo cambio real:
push, pruebas y despliegue exitosos del mismo SHA, y resultado visible. El primer
re-run sirve para comprobar la configuración, pero el video debe mostrar el
disparo automático por un nuevo push. No sustituir el despliegue por pruebas
locales, un badge de otro commit ni un comando manual.

## Preparación antes de grabar

1. Elegir un operador para compartir pantalla, con cámara/voz de cada integrante
   en su turno, o grabar segmentos con los tres. Ensayar las transiciones.
2. Abrir el túnel SSM desde el PC; verificar credenciales vigentes sin mostrarlas.
   Dejar la terminal del túnel abierta durante todo el ensayo.
3. Confirmar /api/ready, servicios y timer. La API debe devolver ready antes de
   hacer una prueba de interrupción. Mantener el visor a 100–125 % para leerlo.
4. Abrir pestañas: aplicación, PR/Actions, diagrama del repositorio, consola SSM
   y correo. No abrir archivos .env, credenciales o configuración con secretos.
   Los correos de SNS contienen enlaces de desuscripción: mostrar solo asunto y
   cuerpo pertinente, sin esos enlaces.
5. En la aplicación seleccionar demo-aws / entrega-final / tareas-rest y el
   contrato activo actual. No dejar seleccionado monitor-test.
6. Identificar el Gold más reciente. El ID 8 pertenece a una evidencia anterior;
   tras una nueva ejecución debe usarse el ID devuelto o seleccionado actualmente.
7. Preparar el prompt Copilot con nombre único si se desea generar una regla nueva.
   Mantener el proveedor real configurado. No introducir claves durante el video.
8. Ensayar una vez el flujo completo. No ejecutar pruebas destructivas, teardown
   ni nuevas copias de toda la infraestructura para grabar.
9. Grabar 1080p y audio claro. Se pueden recortar esperas conservando la continuidad
   del mismo commit/run y anunciando el recorte; no unir resultados de commits
   diferentes para aparentar éxito de una misma ejecución.

## Cronograma

| Tiempo | Responsable propuesto | Pantalla y acción | Evidencia que debe quedar |
|---|---|---|---|
| 0:00–1:00 | Juan Camilo | Presentación breve, aplicación y diagrama del repositorio | Caso simulado, usuarios y arquitectura real |
| 1:00–3:15 | Juan Camilo | Copilot, revisión/aprobación y ejecución del contrato | Proveedor real, contrato persistido y DAG que termina |
| 3:15–5:15 | Gabriela | Calidad, cuarentena, catálogo, linaje y certificación | Reglas, separación 160/40 y trazabilidad |
| 5:15–6:15 | Gabriela | Gold y API | Ocho grupos, datos reales y checksum |
| 6:15–8:15 | Felipe | Timer, monitor, prueba y correo | Detección/recuperación o evidencia histórica claramente identificada |
| 8:15–10:45 | Felipe | Cambio real, push, pruebas y despliegue automático | Mismo SHA, jobs ejecutados y cambio visible desplegado |
| 10:45–11:30 | Juan Camilo | Costos, recuperación y cierre | Supuestos, límites y conclusión |
| 11:30–12:00 | Equipo | Reserva | Transiciones; no agregar otra explicación |

El bloque CI/CD está condicionado a completar la implementación y la ejecución.
No se deben consumir sus minutos explicando una funcionalidad que aún no existe.
El tiempo real solo se confirma con un ensayo cronometrado.

## Narración y acciones

### Juan Camilo 0:00 a 1:00

Decir:
«Somos Juan Camilo Ramón, Felipe Castro Jaimes y Gabriela Sanabria.
DataForge es una plataforma académica para procesar fuentes mediante contratos
reutilizables. AI Solutions LATAM es el escenario ficticio que usamos para
plantear el problema. Mostraremos captura, calidad, transformación y consumo,
además de operación y automatización.»

Mostrar la aplicación conectada. Abrir brevemente el diagrama del repositorio:
«La aplicación y Airflow corren en EC2. RDS conserva metadatos de DataForge;
la base propia de Airflow está separada. Los archivos viven en S3 y entramos
por un túnel SSM.» Volver a la aplicación. No explicar cada servicio de AWS.

### Juan Camilo 1:00 a 3:15

Mostrar el contrato vigente y las reglas existentes. En Copilot, generar una
propuesta usando Groq. El siguiente prompt propone una regla adicional que no
cambia la regla crítica de la demostración; sustituir HHMMSS por una etiqueta
única y comprobar el resultado antes de aprobar:

```text
Agrega exactamente una regla nueva:
name: video_completed_presente_HHMMSS
rule: not_null
column: completed
severity: warning
mostly: 1
allow_null: false

No incluyas reglas existentes en la respuesta.
La aplicación conserva y combina las reglas actuales.
Devuelve transformations como una lista vacía.
```

La compatibilidad de completed/not_null se comprobará en el ensayo. No asegurar
PASS antes de ejecutar. Si la propuesta no es correcta, no aprobarla ni guardar
para mantener el ritmo del video. La alternativa es mostrar la propuesta Groq
ya verificada y su contrato persistido, indicando que pertenece al ensayo anterior.

Decir:
«El modelo propone configuración. El servidor valida columnas, operaciones y
duplicados. Revisamos el contrato completo y aprobamos explícitamente su guardado.
La ejecución es una acción separada.»

Tras guardar, seleccionar la nueva revisión activa, hacer un único Run Full
Pipeline y mostrar el identificador. Si se añadió una regla, habrá cuatro reglas
en vez de las tres del ensayo anterior; las capturas deben corresponder a esa
revisión. Esperar el resultado real. No ejecutar una vez por PowerShell y otra
por UI para la misma demostración.

Decir al terminar:
«Este DAG genérico tomó el contrato persistido y coordinó Bronze, profiling,
Silver, Gold y certificación. Ahora revisamos sus resultados.»

### Gabriela 3:15 a 5:15

Abrir Quality & Quarantine y seleccionar el dataset del ensayo.
Comprobar los valores antes de narrarlos. Si coinciden con la referencia:
«Recibimos 200 tareas. La regla crítica userId menor o igual a ocho separó
40 registros, y 160 quedaron en Silver validada. SUCCESS corresponde a la
ejecución del procesamiento; no significa que todas las filas cumplieron.»

Mostrar dos registros rechazados con userId 9 o 10. Mostrar las reglas warning
que efectivamente hayan pasado, incluida la nueva solo si está en esta corrida.

Abrir catálogo/linaje; seguir Bronze → Silver y sus salidas Gold/cuarentena.
Mostrar el estado de certificación disponible y explicar:
«La certificación es un estado de gobernanza distinto de la partición de filas.
Podemos relacionar los activos con las ejecuciones y la calidad que los produjo.»

No cambiar manualmente estados solo para conseguir un color verde en pantalla.

### Gabriela 5:15 a 6:15

En Data Assets seleccionar el Gold recién generado y View Gold data.
«Este archivo agrupa las tareas de los usuarios aceptados. Vemos ocho usuarios
con 20 tareas cada uno: el total de 160 coincide con Silver. La aplicación leyó
el Parquet real y verificó su SHA-256.»

Mostrar la respuesta API correspondiente al mismo activo. En PowerShell,
sustituir el ID por el actual:

```powershell
$gold = Invoke-RestMethod 'http://localhost:8081/api/assets/ID/gold-preview'
$gold | Select-Object asset_id, checksum_verified, total_rows, returned_rows
$gold.rows | Format-Table
```

Indicar que el analista puede inspeccionar el resultado. Es una vista previa
acotada, no un servicio de consulta masiva.

### Felipe 6:15 a 8:15

En EC2 mostrar:
```bash
sudo systemctl list-timers dataforge-monitor.timer --no-pager
sudo journalctl -u dataforge-monitor.service --no-pager -n 12
```

«Además de las tres alarmas de infraestructura, este monitor revisa disponibilidad
e historial de ejecuciones. Dos comprobaciones negativas generan avisos; después
de recuperar el servicio se envían las recuperaciones.»

Para una prueba nueva de extremo a extremo, usar el procedimiento controlado
del anexo: deja una recuperación de seguridad antes de detener únicamente web.
Mostrar el log de fallo y el correo asociado, recuperar y mostrar el nuevo estado
y aviso. No enviar un simple publish SNS y describirlo como detección de caída.

«Adelantamos manualmente las comprobaciones del monitor para esta demostración;
el timer normal comprueba aproximadamente cada minuto.» No atribuir al timer
la latencia de una prueba acelerada.

Si se utiliza evidencia previa, indicar su fecha y abrir el correo de ese mismo
ensayo; no afirmar que ocurrió durante la grabación. Para pipeline fallido se
puede mostrar monitor-test #5 y su email anterior, distinguiéndolo de las corridas
de negocio exitosas. El monitor comparte la EC2 y no es un detector independiente
de la caída de todo el host.

### Felipe 8:15 a 10:45

Este bloque se graba cuando existan CI y CD funcionales.

1. Mostrar un cambio pequeño, real y visible del código, revisado y compatible
   con las pruebas existentes; no usar solo un cambio de README para demostrar
   un despliegue de aplicación.
2. Mostrar diff, commit y push a la rama autorizada. Anotar el SHA.
3. Mostrar el evento automático de PR/push y las pruebas de ese SHA ejecutándose.
4. Mostrar su resultado y la etapa automática de despliegue posterior al éxito.
5. Mostrar la verificación de disponibilidad y el cambio visible en la aplicación.
   No sustituir esto por ejecutar manualmente start.sh o una orden SSM.
6. Si hay esperas largas, recortar el tiempo muerto sin cambiar el SHA ni omitir
   un fallo intermedio. No se requiere que ocho jobs duren menos de dos minutos:
   el segmento final debe documentar la misma secuencia real.

La rama feature se valida por el evento pull_request hacia main/develop; push
directo a la feature por sí solo no coincide con el filtro push del workflow,
pero la actualización de una PR abierta genera synchronize.
La etapa CD de web/API requiere AWS_DEPLOY_ENABLED=true y las credenciales temporales vigentes. Verificar su éxito real antes de narrar el resultado.

Narración solo cuando se haya demostrado:
«Este cambio disparó las pruebas. Tras su éxito, el flujo desplegó el mismo
commit y verificamos el resultado en la aplicación.»

Si el despliegue sigue pendiente, mostrar el estado real y decir:
«Las pruebas alojadas pasaron, pero aún no demostramos despliegue automático.» Eso documenta una
limitación y no cumple el criterio obligatorio. No existe una redacción que
convierta un intento fallido en una demostración exitosa.

### Juan Camilo 10:45 a 11:30

Mostrar brevemente la tabla de costos del repositorio y la evidencia de recuperación:
«En el escenario presupuestal base estimamos USD 55,35 al mes, sin créditos ni
impuestos; 10× y 100× dan USD 127,02 y 504,75. Son supuestos explícitos de
ingesta, retención y consumo, no capacidad demostrada. Verificamos recuperación
tras reinicio y restauración aislada de las bases.»

Cerrar:
«La evidencia muestra el recorrido desde la fuente hasta Gold con calidad y
trazabilidad. El prototipo conserva límites de host único, consumo acotado y
los pendientes que acabamos de identificar.» Si se resolvió CI/CD, actualizar
el informe y las limitaciones antes de grabar este cierre.

## Anexo Prueba de disponibilidad con recuperación de seguridad

Ejecutar primero en ensayo, dentro de una shell SSM de EC2, después de comprobar
que no hay otra operación de despliegue/prueba en curso. Grabar solo el segmento
pertinente. No modifica RDS, datos S3 ni contratos.

```bash
sudo bash <<'VIDEO_MONITOR_TEST'
set -euo pipefail
web_container=dataforge-web-1
test "$(docker inspect --format '{{.State.Running}}' "$web_container")" = true
curl --fail --silent --show-error --max-time 15   http://127.0.0.1:8081/api/ready >/dev/null
recovery_unit="dataforge-video-recovery-$(date +%s)"
trap 'docker start "$web_container" >/dev/null 2>&1 || true' EXIT
systemd-run --unit="$recovery_unit" --on-active=90s   /usr/bin/docker start "$web_container"
docker stop "$web_container" >/dev/null
systemctl start dataforge-monitor.service
systemctl start dataforge-monitor.service
docker start "$web_container" >/dev/null
for attempt in $(seq 1 30); do
  if curl --fail --silent --max-time 3     http://127.0.0.1:8081/api/ready >/dev/null; then
    break
  fi
  sleep 1
done
curl --fail --silent --show-error --max-time 10   http://127.0.0.1:8081/api/ready >/dev/null
systemctl start dataforge-monitor.service
systemctl stop "$recovery_unit.timer" || true
journalctl -u dataforge-monitor.service --since '3 minutes ago' --no-pager
VIDEO_MONITOR_TEST
```

Es una guía de ensayo basada en el mecanismo previamente verificado, no una
nueva prueba ejecutada por el editor al preparar este guion. Verificar recepción
real del correo. Un resultado de servicio fallido requiere revisar los logs;
no afirmar entrega por el solo hecho de haber iniciado systemctl.

## Revisión final del archivo y envío

- Máximo 12 minutos; objetivo 11:30. Sin diapositivas; las pantallas son el producto,
  el código/repositorio, la operación y las evidencias.
- Los tres aparecen y operan/explican una parte.
- El pipeline se dispara y llega a consumo. Datos, revisión y activo son coherentes.
- El bloque de CI/CD muestra el mismo cambio y despliegue, si se logró completar.
  Si no, la entrega debe declarar el incumplimiento.
- El monitoreo y sus correos corresponden al ensayo mostrado.
- No hay secretos ni enlaces de desuscripción visibles.
- Abrir el enlace de YouTube desde otra sesión para comprobar acceso.
  Debe ser público o no listado, no privado.
- Entrega indicada por el profesor: un único correo a jurest82@eafit.edu.co,
  con copia a todos los integrantes, enlace YouTube y PDF, a más tardar
  el 9 de noviembre a las 17:00 de Colombia. Este documento no envía ese correo.

