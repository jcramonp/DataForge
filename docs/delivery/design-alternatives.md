# Comparación retrospectiva de alternativas de diseño

Fecha: 9 de noviembre de 2026. Proyecto DataForge, SI4002, Universidad EAFIT.
Preparado con apoyo de IA para revisión del equipo.

## Alcance y trazabilidad de la evaluación

Esta evaluación complementa los apartados «Premisas del diseño»,
«Requerimientos y restricciones» y «Alternativas y criterios de selección» de la
plantilla del informe final. Es una comparación retrospectiva de tres diseños;
no documenta un proceso de selección realizado al inicio ni pruebas de tres
implementaciones. Solo la alternativa B tiene la evidencia de ejecución aquí
citada. Los pesos y puntuaciones son juicios de ingeniería propuestos para
revisión del equipo, no resultados experimentales ni consenso previamente
documentado.

AI Solutions LATAM es una consultora ficticia utilizada como escenario académico.
El problema de diseño consiste en reducir la necesidad de implementar lógica
independiente de ingesta, transformación y calidad para cada fuente, conservando
trazabilidad y un medio de consumir los datos aceptados. No se dispone de
entrevistas con clientes, mediciones de ahorro de trabajo ni adopción comercial.

Usuarios previstos: ingenieros que configuran/operan pipelines, responsables
de calidad que revisan reglas y cuarentena, y analistas que consultan Gold.
Estos roles explican el diseño; no constituyen una validación con usuarios reales.

## Premisas y restricciones

Se considera procesamiento por lotes de fuentes tabulares y REST, almacenamiento
de datos en objetos y metadatos operativos en una base relacional. La demostración
AWS trabaja con datos públicos de tareas; la evidencia Olist corresponde a otro
ensayo documentado y no se presenta como una ejecución reciente en Academy [1][2].
Se mantienen objetos rechazados separados de los aceptados; la cuarentena permite
continuar con la partición válida sin afirmar que toda la entrada tiene calidad.

El equipo dispone del entorno AWS Academy y de sus permisos y presupuesto.
Se observaron denegaciones para Bedrock; esto no demuestra que Glue o Step
Functions estén prohibidos. Sus permisos, cuotas y costos no fueron verificados.
El CI alojado no ha pasado para la entrega y el despliegue automático sigue
pendiente. El entorno existente fue desplegado incrementalmente y no acredita
reconstrucción completa en una cuenta vacía [3].

La instalación actual usa un host EC2 y RDS Single-AZ. No se asumen alta
disponibilidad, procesamiento distribuido ni escalado automático. Tampoco se
suponen objetivos contractuales de disponibilidad o latencia. No existen
mediciones comparables de consumo eléctrico, emisiones, costo humano o costo
total de las tres alternativas.

## Requerimientos y verificación

Los siguientes criterios hacen verificable la comparación sin inventar un SLA.
Las capacidades comunes podrían implementarse en cualquiera de las alternativas,
con distinto trabajo de integración. El estado corresponde únicamente a B.

| Requerimiento | Criterio de verificación | Estado y límite de la evidencia B |
|---|---|---|
| Ejecutar por configuración | Procesar un contrato persistido mediante el motor genérico | Contrato #2/revisión 2 ejecutado; evidencia REST y ensayo Olist documentados |
| Conservar y separar registros | Comprobar entrada = aceptados + cuarentena, en filas | Ensayo REST: 200 = 160 + 40; no se extrapola a toda fuente |
| Permitir consumo real | Leer un activo Gold registrado, verificar integridad y mostrar valores | Ocho usuarios × 20 tareas = 160; SHA-256 verificado |
| Mantener trazabilidad | Vincular contratos, ejecuciones, resultados de calidad y activos | Migraciones, repositorios y evidencia de catálogo/linaje [4] |
| Detectar fallos operativos | Evidenciar indisponibilidad/recuperación y fallo nuevo de ejecución | Correos de prueba recibidos; comprobaciones aceleradas, sin SLA periódico medido |
| Recuperar metadatos | Restaurar ambos dumps sin reemplazar producción | Restore aislado pasó; no es una restauración integral de AWS/S3 |
| Automatizar pruebas y despliegue | Un cambio dispara pruebas y despliegue comprobables | Pendiente: workflow de validación existente; sin despliegue automático |
| Controlar crecimiento económico | Explicitar tarifas, carga de entrada, consumo y retención | Modelo presupuestal disponible; carga 10×/100× sin prueba de capacidad |

El visor actual limita el objeto a 10 MiB, las columnas a 50, las filas devueltas
a 100 y el JSON a 1 MiB [5]. Esas son restricciones de la implementación, no
requerimientos universales de las alternativas.

## Alternativa A Pipelines independientes por cliente

**Principio de funcionamiento.** Programas Python/SQL específicos extraen cada
fuente, aplican reglas definidas en código y generan archivos o tablas de salida.
Un programador del sistema operativo puede ejecutar los lotes. Se considera una
línea base con registros de ejecución y credenciales separadas del código; no se
presupone ausencia de buenas prácticas de seguridad.

**Componentes principales.** Conectores por fuente, pandas/SQL, tareas
programadas, archivos Parquet o tablas de salida, almacenamiento, pruebas y
registros básicos. Un API o dashboard se añadiría si el consumo lo requiere.

**Complejidad.** Baja para pocos flujos simples; aumenta al mantener esquemas,
reglas, dependencias, historial, interfaz y alertas por separado.

**Ventajas.** Menor número inicial de componentes; libertad de bibliotecas y
entorno; ejecución local o en otro proveedor; adaptación directa a requisitos
particulares. Puede cumplir calidad y trazabilidad si se implementan explícitamente.

**Limitaciones.** Reutilizar reglas y centralizar contratos, linaje y operación
requiere disciplina o desarrollo adicional. El diseño base no ofrece una interfaz
unificada para responsables de calidad. No se ha medido si cuesta menos que B:
ahorrar infraestructura podría aumentar trabajo de mantenimiento. No se construyó
ni ensayó esta alternativa como implementación separada para la comparación.

## Alternativa B Plataforma reutilizable DataForge

**Principio de funcionamiento.** Contratos declarativos definen fuentes,
esquema, reglas y transformaciones. Un motor genérico ejecuta las etapas y
persiste resultados, calidad y linaje; el operador revisa propuestas y consume Gold.

**Componentes principales.** Python, conectores y validación de contratos,
Airflow, PostgreSQL de metadatos, almacenamiento Parquet, FastAPI y React.
En local se utiliza MinIO. En AWS: EC2/Compose, S3, RDS, acceso SSM y alertas
CloudWatch/SNS más el monitor de aplicación. La base de Airflow permanece en
un contenedor con volumen propio, separada del RDS del control plane [1].
Groq propone configuraciones sujetas a validación y aprobación humana;
Bedrock no quedó operativo.

**Complejidad.** Media-alta: coordina API, orquestador, bases, almacenamiento,
secretos, migraciones y monitoreo. Los contratos reducen código específico
cuando la necesidad se ajusta a las operaciones ya soportadas; nuevas capacidades
del motor aún requieren programación y pruebas.

**Ventajas.** Camino de punta a punta demostrado, interfaz de revisión, evidencia
persistida de calidad/cuarentena y uso común del motor. Separar almacenamiento y
metadatos facilita trazabilidad. Los componentes abiertos y el contrato propio
reducen algunas dependencias de proveedor, aunque migrar secretos, identidad,
red y servicios AWS todavía requeriría trabajo.

**Limitaciones.** Un host es un punto de falla y el monitor comparte ese host.
La configuración actual no implementa autorización multiusuario/RBAC en la
aplicación; el acceso de demostración se controla mediante SSM. No hay evidencia
de rendimiento 10×/100×, CI alojado exitoso ni despliegue automático. No alcanza
todos los requisitos finales por estar implementada. Su costo modelado no prueba
que sea la opción más barata.

## Alternativa C Plataforma administrada en AWS

**Principio de funcionamiento.** Trabajos de integración de AWS Glue procesan
los datos en S3, y Step Functions coordina las tareas, reintentos y errores.
Glue ofrece integración sin administrar los servidores del motor; Step Functions
permite definir manejo de errores en el flujo [6][7].

**Componentes propuestos.** S3, Glue/Glue Data Catalog, Step Functions, IAM,
CloudWatch/SNS, almacenamiento de metadatos y un API o medio de consulta para
el consumo. Las reglas, la cuarentena, la revisión de contratos y la interfaz
de usuario deben diseñarse: estos servicios no entregan automáticamente las
funciones específicas de DataForge.

**Complejidad.** Media-alta en integración, permisos y control de costos.
Disminuye la administración directa del cómputo ETL, pero siguen existiendo
responsabilidades sobre datos, IAM, redes, errores y despliegue.

**Ventajas potenciales.** Gestión del cómputo por el proveedor, integración con
servicios AWS y controles IAM centralizados. Tiene mecanismos para diseñar
flujos con reintentos y manejo de fallos; no se ha probado la capacidad de esta
propuesta con las cargas del proyecto.

**Limitaciones.** Mayor acoplamiento a APIs/configuración del proveedor y
necesidad de reimplementar partes del contrato/control plane. Viabilidad en
Academy, costo, rendimiento y seguridad de una configuración concreta no
verificados. El precio depende de recursos y duración de trabajos, almacenamiento,
solicitudes y orquestación; no se atribuye un precio equivalente al de B [8].
Es una alternativa conceptual, no una arquitectura ya desplegada por el equipo.

## Método multicriterio ponderado

Se emplean seis factores presentes en la plantilla. La puntuación va de 1 a 5:
1 = ajuste muy bajo; 2 = bajo; 3 = intermedio o neutral por falta de evidencia;
4 = favorable; 5 = muy favorable con pocas brechas para el alcance.
No es la nota del curso.

El resultado para la alternativa j es:

S(j) = suma de [peso(i) / 100 × puntuación(i,j)].

Los pesos suman 100 %. Son una propuesta explícita de prioridades del proyecto:
se da más importancia a funcionamiento/reutilización y viabilidad económica.
No se obtuvieron de encuestas ni de un proceso histórico de consenso.
El valor neutral 3 por falta de datos es un marcador de incertidumbre:
no demuestra igualdad de costos o de impactos ambientales.

| Factor y criterio | Peso | A Scripts | B DataForge | C AWS administrado |
|---|---:|---:|---:|---:|
| Técnico: reutilización, calidad, trazabilidad y operación | 30 % | 2 | 4 | 4 |
| Económico: costo total de operación e implementación | 25 % | 3 | 3 | 3 |
| Ambiental: eficiencia de recursos y retención | 10 % | 3 | 3 | 3 |
| Social: facilidad de revisión y transferencia de conocimiento | 10 % | 2 | 4 | 3 |
| Seguridad y bienestar: control de acceso y prevención de decisiones erróneas | 15 % | 3 | 3 | 4 |
| Contexto global: portabilidad, estándares y dependencia del proveedor | 10 % | 4 | 4 | 2 |
| **Resultado ponderado sobre 5** | **100 %** | **2,70** | **3,50** | **3,35** |

### Justificación de las puntuaciones

**Técnico.** A permite resolver flujos concretos, pero su diseño base requiere
trabajo adicional para uniformar contratos y trazabilidad: 2. B ofrece esas
funciones con evidencia, con brechas en automatización y resiliencia: 4.
C tiene capacidad de diseñarlas mediante integración, todavía sin implementación
equivalente: 4 como valoración del diseño, no como grado de verificación.

**Económico.** Se asigna 3 a todas: solo B tiene un modelo de costos detallado.
No se dispone de una cotización comparable de A/C ni de horas-persona.
No se concede ventaja económica a B por tener presupuesto calculado.
La evaluación económica relativa permanece abierta.

**Ambiental.** Se asigna 3 a todas: no existen mediciones de energía o emisiones.
Reducir copias y retención o apagar recursos inactivos puede mejorar cualquiera.
El carácter administrado de C no implica una reducción ambiental demostrada.

**Social.** A exige más interacción técnica para revisar reglas: 2.
B dispone de interfaz de revisión, calidad y consumo: 4. C necesita integrar una
experiencia equivalente: 3. Son valoraciones de diseño, sin ensayos de usabilidad,
entrevistas, mediciones de accesibilidad ni beneficios sociales cuantificados.

**Seguridad y bienestar.** A recibe 3: la línea base permite separar credenciales
y verificar calidad, pero necesita controles explícitos. B recibe 3: SSM, RDS
privado, buckets bloqueados, aprobación y cuarentena aportan controles; faltan
RBAC y separación de funciones en la aplicación. C recibe 4 por las posibilidades
de control IAM y operación administrada, condicionado a una correcta configuración.
No significa que una implementación inexistente haya superado una auditoría.
El bienestar se relaciona aquí con evitar decisiones apoyadas en datos defectuosos;
no se atribuyen resultados clínicos ni certificaciones de seguridad.

**Contexto global.** A y B reciben 4 por Python/SQL o componentes abiertos y
formatos Parquet; no reciben 5 porque toda migración requiere adaptación.
C recibe 2 por el mayor acoplamiento de sus flujos y permisos a AWS.
Ninguna puntuación demuestra cumplimiento normativo o soberanía de datos.

## Tabla obligatoria de factores del diseño seleccionado

| Tipo de factor | Consideración aplicada en el proyecto | Justificación técnica de la decisión | Impacto ético asociado |
|---|---|---|---|
| Técnico | Contratos validados; motor genérico; separación entre datos y metadatos; cuarentena | Reutilizar operaciones soportadas y conservar evidencia de resultados sin mezclar activos con el historial operativo | Evitar aceptar silenciosamente registros inválidos y mantener la posibilidad de revisar decisiones |
| Económico | Entorno acotado, inventario, costos por carga y detención de EC2 antigua | Ajustar el alcance al laboratorio; distinguir costo mensual teórico, crédito Academy y factura observada | No prometer ahorro comercial ni capacidad sin mediciones; reconocer que el disco retenido aún tiene costo |
| Ambiental | Detención de cómputo ajeno al servicio y reconocimiento del costo de copias/retención | Reducir recursos encendidos sin uso; retención y dimensionamiento deben revisarse con métricas | No declarar reducción de CO2 o energía no medida; no presentar el borrado por retención como automatización desplegada |
| Social | Interfaz para revisar configuración, resultados, cuarentena y Gold; RACI documentada | Hacer visibles los resultados y distribuir responsabilidades de operación | No atribuir adopción ni satisfacción de usuarios; documentar límites para evitar confianza excesiva |
| Seguridad y salud pública | Acceso SSM, RDS privado, buckets sin acceso público, secretos fuera de Git, validación y aprobación de propuestas | Limitar exposición y mantener intervención humana antes de persistir una configuración propuesta por IA | Proteger credenciales; minimizar información enviada al proveedor LLM; no usar el prototipo para decisiones críticas sin validación adicional |
| Contexto global | Formatos abiertos, componentes reutilizables y proveedor LLM externo declarado | Facilitar interoperabilidad sin negar dependencias de AWS/Groq e IAM | Considerar ubicación y tratamiento de datos antes de usar datos personales; no afirmar cumplimiento legal no evaluado |

La seguridad y salud pública no son un campo operativo validado del proyecto.
Esta fila explicita riesgos de datos y uso indebido, sin convertir el prototipo
en un sistema certificado para decisiones de salud o seguridad.

## Sensibilidad y decisión

La ventaja base de B sobre C es solo 0,15 puntos. Se recalcula manteniendo
puntuaciones y trasladando diez puntos porcentuales entre seguridad y
portabilidad; los demás pesos permanecen iguales.

| Escenario de prioridades | Seguridad | Contexto global | A | B | C | Mayor puntuación |
|---|---:|---:|---:|---:|---:|---|
| Base | 15 % | 10 % | 2,70 | 3,50 | 3,35 | B |
| Mayor peso a seguridad | 25 % | 0 % | 2,60 | 3,40 | 3,55 | C |
| Mayor peso a portabilidad | 5 % | 20 % | 2,80 | 3,60 | 3,15 | B |

El peso cero del segundo escenario es una perturbación de sensibilidad, no una
recomendación de ignorar portabilidad. También existe sensibilidad a las
puntuaciones: subir de 3 a 4 la evaluación económica de C, si una cotización
futura lo justifica, añade 0,25 y cambia el primer lugar. Reducir de 4 a 3 la puntuación técnica de B resta 0,30 y también invierte
el primer lugar del escenario base.

Por tanto, B es una elección coherente con la reutilización, interfaz y portabilidad
buscadas en el alcance académico y es la única implementación cuya factibilidad
en el entorno actual está demostrada. No se concluye que sea universalmente
mejor, más barata o ambientalmente superior. Para una organización que priorice
controles administrados e integración AWS, C merece un estudio y presupuesto real.
A puede resultar apropiada para pocos flujos estables que no necesiten el control
plane completo.

La continuidad de B debe condicionarse a cerrar CI/despliegue automático, ejecutar
pruebas de carga, completar la evaluación de acceso multiusuario y verificar
reconstrucción de la infraestructura. Estas brechas no desaparecen por obtener
la mayor puntuación de la matriz.

## Relación con el costo y próximos datos necesarios

El presupuesto de B se encuentra en [aws-costs.md](../operations/aws-costs.md):
USD 55,35 / 127,02 / 504,75 al mes para cargas hipotéticas base/10×/100×,
más USD 3/mes por el disco antiguo retenido. No son costos de A/C ni cargos
reales medidos para esas cargas. La sensibilidad de prioridades de esta sección
es distinta de la sensibilidad económica por volumen.

Para sustituir las valoraciones neutrales: cotizar A/C con el mismo volumen,
retención, egreso, disponibilidad y alcance de calidad/consumo; estimar horas de
implementación/operación; medir bytes, solicitudes, CPU/RAM y tokens; y realizar
una revisión de seguridad y usabilidad. No se requiere al operador un dato
inexistente para redactar esta comparación, siempre que se mantengan sus límites.

## Aprendizaje y declaración para el informe

El equipo confirmó aprendizaje mediante documentación, apoyo de IA y
videotutoriales. No había trabajado antes con Airflow, MinIO ni Groq.
Los aprendizajes nuevos de AWS que el equipo destacó fueron RDS, SSM y alertas;
no se atribuye novedad por igual a todos los servicios desplegados.
Se exploró Bedrock, pero no se logró invocar un modelo por las restricciones
de permisos observadas.

La IA apoyó investigación, programación, depuración y preparación de documentación
durante el proyecto. Esta comparación y sus puntuaciones se elaboraron con ese
apoyo y deben ser revisadas por los autores; no se declara una revisión humana
ya terminada. Documentación y videotutoriales se citan con títulos/enlaces concretos
solo si el equipo los identifica; no se inventan cursos ni fuentes consultadas.

## Referencias y soporte

[1] Repositorio DataForge, «Arquitectura AWS desplegada», docs/architecture/aws-academy.md;
«Verificación Groq» y «Consumo Gold», docs/evidence/aws-groq-verification.md y
docs/evidence/aws-gold-consumption-verification.md. https://github.com/jcramonp/DataForge

[2] Repositorio DataForge, «Olist final verification», docs/evidence/olist-final-verification.md.
Ensayo documentado del 26 de octubre de 2026, distinto de la demostración REST.

[3] Repositorio DataForge, «Final delivery checklist» y «Reboot and backup evidence»,
docs/operations/final-delivery-checklist.md y docs/evidence/aws-recovery-backup-verification.md.
Workflow: .github/workflows/ci.yml.

[4] Repositorio DataForge, database/migrations/0001_control_plane_schema.sql a
0008_metadata_performance.sql; docs/governance/data-dictionary.md,
data-catalog.md y raci.md.

[5] Repositorio DataForge, src/api/gold_preview.py; src/copilot/service.py;
src/contracts/models.py; compose.aws.yml; infra/academy/;
docs/evidence/aws-application-monitor-verification.md.

[6] Amazon Web Services, «What is AWS Glue?», documentación oficial.
https://docs.aws.amazon.com/glue/latest/dg/ Consultado 9 nov. 2026.

[7] Amazon Web Services, «Handling errors in Step Functions workflows»,
documentación oficial.
https://docs.aws.amazon.com/step-functions/latest/dg/concepts-error-handling.html
Consultado 9 nov. 2026.

[8] Amazon Web Services, «AWS Glue Pricing». https://aws.amazon.com/glue/pricing/
Consultado 9 nov. 2026. No se calculó una cotización equivalente de C.
