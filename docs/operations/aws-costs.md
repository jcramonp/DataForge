# Costos y sensibilidad — 2026-11-09

## Inventario observado y alcance

Región us-east-1; precios de lista USD, 730 horas/mes, sin impuestos,
descuentos ni créditos educativos. La captura de Academy mostraba USD 44,80
consumidos de 50 (5,20 disponibles en ese momento). Billing mostraba USD 3,48
del mes y una previsión de 7,51. Son ventanas y conceptos distintos; ninguno
representa el costo mensual continuo de esta arquitectura.

El operador confirmó la detención de i-0a6f55c8b94b2037d (t2.large).
DataForge i-02ce56fe4c428d16a (t3.medium) permanece running. No se eliminó su
disco antiguo gp2 de 30 GB: conservarlo cuesta aproximadamente USD 3/mes.
Revisar nuevamente su estado al iniciar otra sesión del laboratorio.

| Recurso activo DataForge | Cantidad/tarifa | USD/mes |
|---|---|---:|
| EC2 Linux t3.medium | 730 h × 0,0418 | 30,514 |
| EBS gp3 | 30 GB × 0,08 | 2,400 |
| RDS PostgreSQL db.t4g.micro Single-AZ | 730 h × 0,016 | 11,680 |
| RDS gp3 | 20 GB × 0,115 | 2,300 |
| IPv4 pública | 730 h × 0,005 | 3,650 |
| Alarmas CloudWatch estándar | 3 × 0,10 | 0,300 |
| Secrets Manager | 1 secreto × 0,40 | 0,400 |
| **Base fija** | Sin solicitudes, S3 ni Groq | **51,244** |

Aunque no haya Elastic IP, una IPv4 pública asignada por Amazon también tiene
tarifa. La base fija más el disco antiguo retenido es USD 54,24/mes.
Esta estimación no es una factura ni garantiza una duración del saldo Academy.

## Escenarios de planificación

La demostración real procesa 200 registros REST; no se ha medido su volumen
diario sostenido. Se define una carga de referencia hipotética y se multiplican
tanto ingesta como consumo. Los tamaños verticales son candidatos para
presupuesto, no recursos desplegados ni capacidad validada.

| Supuesto mensual salvo indicación | Base | 10× | 100× |
|---|---:|---:|---:|
| Ingesta, GB/día | 1 | 10 | 100 |
| Retención, días | 30 | 30 | 30 |
| Almacenamiento agregado entre capas, GB | 90 | 900 | 9000 |
| PUT/COPY/POST/LIST S3 | 1000 | 10000 | 100000 |
| GET S3 | 10000 | 100000 | 1000000 |
| Salida a Internet, GB | 10 | 100 | 1000 |
| Propuestas LLM | 100 | 1000 | 10000 |
| Publicaciones SNS con un correo cada una | 10 | 100 | 1000 |
| Solicitudes Secrets Manager | 30 | 300 | 3000 |
| EC2 | t3.medium | t3.large | t3.xlarge |
| EBS gp3, GB | 30 | 50 | 100 |
| RDS Single-AZ | db.t4g.micro | db.t4g.small | db.t4g.medium |
| Almacenamiento RDS gp3, GB | 20 | 20 | 100 |

El factor físico agregado de almacenamiento es 3: GB/día × 30 días × 3.
Es un supuesto que engloba capas/versiones, no una medición de compresión.
Se asume borrado al cumplir la retención; no se afirma que exista una regla
lifecycle desplegada que lo haga. Mantener versiones sin borrar aumenta el costo.
Las solicitudes S3 corresponden a operaciones/objetos agrupados; no equivalen
a una solicitud por registro. Se supone ingreso desde Internet y no se duplica
como egreso S3→EC2 dentro de la misma región.

Tarifas variables: S3 Standard 0,023/GB-mes, PUT/LIST 0,005/1000 y GET
0,0004/1000; salida Internet 0,09/GB; SNS 0,50/millón de publicaciones más
2/100000 entregas email; solicitudes de secretos 0,05/10000.
Se reserva USD 1/mes para solicitudes de sondeo/control adicionales: es una
provisión de planificación, no una cuota de AWS ni un consumo medido.
El monitor consulta cuatro buckets aproximadamente cada 65 segundos; esas
llamadas no se confunden con las solicitudes de datos de la tabla.

Groq usa como referencia pagada openai/gpt-oss-120b: 0,15/millón de tokens de
entrada y 0,60/millón de salida. Se suponen 6000 tokens de entrada y 600 de
salida facturable por propuesta: USD 0,00126/propuesta. No se han medido esos
tokens; incluir razonamiento facturable y reintentos cuando se mida el uso.
El nivel gratuito y sus límites no se presuponen suficientes para los escenarios.

| Estimación USD/mes | Base | 10× | 100× |
|---|---:|---:|---:|
| AWS, incluida reserva de sondeo | 55,22 | 125,76 | 492,15 |
| Groq | 0,13 | 1,26 | 12,60 |
| **Total aplicación** | **55,35** | **127,02** | **504,75** |
| Disco antiguo conservado | 3,00 | 3,00 | 3,00 |
| **Total con disco antiguo** | **58,35** | **130,02** | **507,75** |

Se suman valores sin redondear; las partidas mostradas redondeadas pueden
diferir un centavo. La sensibilidad resulta aproximadamente 2,29× y 9,12×
del costo base, porque infraestructura y carga no se multiplican igual.

## Fórmulas, validación y límites

Ejecutar desde la raíz del repositorio con Node:

```bash
node scripts/ops/cost-model.mjs
```

El archivo contiene supuestos y tarifas explícitos, sin credenciales ni llamadas
a AWS. Emite parámetros y resultados en JSON. Su cálculo se ejecutó en un
motor JavaScript y se contrastaron los totales 55,35 / 127,02 / 504,75; no se
afirma una ejecución local de Node en esta sesión.

Costo fijo = horas × (EC2/h + RDS/h + IPv4/h) + EBS + disco RDS + alarmas + secreto.
Costo total = fijo + S3 + egreso + solicitudes + reserva + tokens Groq.
Cada GB/día adicional retenido 30 días con factor 3 añade USD 2,07 de S3/mes;
cada 100 GB de egreso facturable añade USD 9; cada 1000 propuestas añade USD 1,26.

Estimación bruta antes de franquicias: la exención compartida de salida a
Internet de AWS puede reducirla según elegibilidad y consumo de la cuenta.
No incluye impuestos, soporte, transferencias entre AZ, copias adicionales y
snapshots fuera del almacenamiento supuesto, exceso de créditos CPU, escalado
de IOPS, servicios ajenos al inventario ni costes humanos. El costo real requiere
medir GB almacenados/transferidos, solicitudes, tokens y duración de cómputo.

No hay pruebas de carga que acrediten 10×/100×. Un único host, RDS Single-AZ,
créditos CPU y procesamiento en memoria limitan disponibilidad y throughput.
Antes de escalar: medir tiempos/picos RAM, limitar lotes, probar concurrencia,
consultas y tamaño del metadato. El visor Gold actual limita objetos a 10 MiB;
no es una interfaz de consumo masivo. Grandes consumos necesitan otra interfaz
y un presupuesto actualizado. No se desplegó un cambio de tamaño con este modelo.

## Fuentes primarias

Consultadas 2026-11-09. Los precios pueden cambiar; revalidar antes de contratar.

- EC2 T3 Linux us-east-1: https://aws.amazon.com/ec2/instance-types/t3/
  (0,0418 / 0,0835 / 0,1670 por hora). Esta tabla directa difiere de una guía
  prescriptiva que muestra 0,0416 para medium; se utiliza la tabla del producto.
- RDS PostgreSQL: https://aws.amazon.com/rds/postgresql/pricing/
- Catálogo regional RDS: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonRDS/current/us-east-1/index.json
  Publicación consultada 2026-10-29T07:06:35Z; PostgreSQL Single-AZ,
  InstanceUsage db.t4g.micro/small/medium = 0,016/0,032/0,065 USD/h.
  Micro SKU 9HPEGXQTDDGH53C9; gp3 SKU KYVYY29G957PKY3B = 0,115 USD/GB-mes.
  Se excluyen SKU de reservas de capacidad sin usar.
- EBS: https://aws.amazon.com/ebs/general-purpose/
- IPv4: https://aws.amazon.com/vpc/pricing/
- CloudWatch: https://aws.amazon.com/cloudwatch/pricing/
- Secretos: https://aws.amazon.com/secrets-manager/pricing/
- S3: https://aws.amazon.com/s3/pricing/
- Ejemplo oficial de tarifas S3/CloudWatch: https://docs.aws.amazon.com/solutions/latest/automated-security-response-on-aws/cost.html
- Transferencia: https://aws.amazon.com/ec2/pricing/on-demand/
- SNS: https://aws.amazon.com/sns/faqs/
- Groq: https://console.groq.com/docs/model/openai/gpt-oss-120b
