# Guion de demostracion - Sprint 2

## Preparacion

- Repositorio en la revision de entrega, Docker Desktop y servicios activos.
- Aplicar migraciones y revisar readiness: python -m src.ops.migrate y
  python -m src.ops.health. API de la demo en 127.0.0.1:8002 y frontend en :3000.
- Si el puerto esta ocupado, usar la instancia correcta o detenerla en su terminal
  antes de reiniciar. No lanzar servidores repetidos.
- Confirmar Node/npm en PATH. La .venv de Python no instala Node. Si se usa el
  runtime local conocido, invocar node.exe por su ruta absoluta.
- Abrir PDF, interfaz, Airflow y evidence/metadata-performance-verification.md.
  Tener una corrida anterior visible como respaldo, identificandola como anterior.

## Secuencia sugerida (10-12 minutos)

1. Comparar Sprint 1 Olist especifico frente a plataforma por contratos Sprint 2.
   Separar PostgreSQL de metadatos y MinIO con Parquet de negocio.
2. Mostrar Source Onboarding: probar conexion, esquema declarado y registro de
   contrato. Para archivos, usar data/demo/ventas_demo.csv accesible al worker;
   no escribir una ruta exclusiva del equipo presentador si Airflow no la ve.
3. Seleccionar demo-profesor / multifuente / ventas-csv. Mostrar contrato #12
   (o la revision activa equivalente), cantidad > 0 y precio > 0, criticas,
   mostly=1 y allow_null=false. Disparar Run full pipeline UNA sola vez.
4. Esperar el mismo ID hasta SUCCESS; un error temporal de consulta no autoriza
   otra corrida. Si el monitoreo se agota, usar Refresh sobre ese ID.
5. Mostrar Bronze 6, Silver 4, Quarantine 2. Identificar venta 4 cantidad=0 y
   venta 5 precio=-3000. Inspeccionar URI de almacenamiento y linaje real.
6. Cambiar a tareas-rest. Explicar extraccion HTTP de /todos, 200 filas y regla
   userId <= 8: corrida demostrada Silver 160 y Quarantine 40. Si se reejecuta,
   verificar la fuente externa: sus datos/disponibilidad pueden cambiar.
7. Mostrar Olist completo: contrato #13, corrida #17 exitosa y Gold 112.642 filas.
   Products aislo 4 filas. Explicar que Gold reducido por joins no es cuarentena.
8. Copilot: proponer una regla sobre columnas existentes; revisar JSON y proveedor.
   Aprobar guarda una revision. Ejecutar esa revision es una accion posterior.
   Pedir materias sobre tareas no es posible: la columna no existe. No prometer
   SQL arbitrario, nuevas fuentes automaticas ni agregaciones Gold por el copilot.
9. Mostrar dos consultas PostgreSQL identicas antes/despues, muestras, planes,
   resultado igual y costo del refresco. Declarar volumen sintetico aislado.
10. Mostrar diccionario, catalogo, RACI, calidad y certificacion. Una evaluacion
    exitosa no es una promocion manual nueva a certified. Concluir con limites
    de entrega: AWS solo referencia; DataOps/consumo para Sprint Final.

## Problemas y resolucion

| Problema observado | Solucion / explicacion |
|---|---|
| npm no reconocido | Instalar/usar Node con npm en PATH; .venv solo cubre Python |
| API no inicia por puerto ocupado | Detener/reutilizar el proceso correcto y reiniciar codigo actualizado |
| UI parecia fallar aunque el pipeline siguiera | Reintentos de monitoreo sobre el mismo ID; resultado desconocido no se presenta como fallo de datos |
| LLM devuelve propuesta invalida | Validacion estricta, mensaje seguro y nueva propuesta; no se aplica JSON invalido |
| Solicitud de columna inexistente | Explicar ausencia; cambiar fuente/esquema o reformular requisito |
| Planes de optimizacion sin baseline | Benchmark controlado con SQL/resultados identicos y planes antes/despues |

## Conceptos a explicar entre todos

Del curso: ETL/ELT, calidad, modelado, almacenamiento por capas y optimizacion.
De otras materias de la trayectoria: bases de datos (indices/SQL), programacion
modular/pruebas, APIs y estadistica descriptiva del profiling. El equipo debe
reemplazar estas areas por los nombres oficiales de sus materias si son distintos.
Aprendizaje autonomo demostrado en el proyecto: contratos Pydantic, integracion
Airflow/FastAPI/React, almacenamiento compatible S3 y Bedrock con aprobacion humana.
Estas categorias describen tecnologias aplicadas; cada integrante prepara ejemplos
propios y no atribuye al curso contenidos que no haya cursado.
