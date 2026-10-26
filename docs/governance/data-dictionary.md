# Diccionario de datos - Sprint 2

Esquema logico normalizado tomado de config/examples/olist.yaml. Los tipos y la
nulabilidad son declarados; su cumplimiento se verifica por transformaciones/reglas
explicitas. Una clave declarada documenta relaciones; no crea una FK fisica en Parquet.
Fechas se normalizan a datetime UTC por el motor; el origen no siempre declara zona.
Clasificacion es metadato, no un control de acceso. Valores personales no se incluyen.

## customers

Dueno declarado: DataForge. Clasificacion: internal.

| Campo | Significado | Tipo | Nulo | Clave | Clasificacion | Reglas implementadas |
|---|---|---|---|---|---|---|
| customer_id | Identificador del cliente asociado a un pedido. | string | no | PK logica | confidential | customer_id_not_null (critical) |
| customer_unique_id | Identificador que permite reconocer clientes recurrentes. | string | no | - | confidential | customer_unique_id_not_null (critical) |
| customer_zip_code_prefix | Prefijo postal de la direccion del cliente. | integer | no | - | confidential | Sin regla especifica |
| customer_city | Ciudad declarada del cliente. | string | no | - | confidential | Sin regla especifica |
| customer_state | Estado brasileño del cliente (sigla de dos letras). | string | no | - | internal | customer_state_format (critical) |

## orders

Dueno declarado: DataForge. Clasificacion: internal.

| Campo | Significado | Tipo | Nulo | Clave | Clasificacion | Reglas implementadas |
|---|---|---|---|---|---|---|
| order_id | Identificador del pedido. | string | no | PK logica | internal | order_id_not_null (critical) |
| customer_id | Identificador del cliente asociado a un pedido. | string | no | FK customers | confidential | order_customer_id_not_null (critical) |
| order_status | Estado del ciclo de vida del pedido. | string | no | - | internal | order_status_allowed (critical) |
| order_purchase_timestamp | Fecha y hora de compra. | datetime | no | - | internal | purchase_timestamp_not_null (critical) |
| order_approved_at | Fecha y hora de aprobacion del pago. | datetime | si | - | internal | Sin regla especifica |
| order_delivered_carrier_date | Fecha de entrega al transportista. | datetime | si | - | internal | Sin regla especifica |
| order_delivered_customer_date | Fecha de entrega al cliente. | datetime | si | - | internal | Sin regla especifica |
| order_estimated_delivery_date | Fecha estimada de entrega. | datetime | si | - | internal | Sin regla especifica |

## order_items

Dueno declarado: DataForge. Clasificacion: internal.

| Campo | Significado | Tipo | Nulo | Clave | Clasificacion | Reglas implementadas |
|---|---|---|---|---|---|---|
| order_id | Identificador del pedido. | string | no | PK logica, FK orders | internal | item_order_id_not_null (critical) |
| order_item_id | Secuencia del item dentro del pedido; clave compuesta con order_id. | integer | no | PK logica | internal | order_item_id_positive (critical) |
| product_id | Identificador del producto. | string | no | FK products | internal | item_product_id_not_null (critical) |
| seller_id | Identificador del vendedor. | string | no | - | confidential | Sin regla especifica |
| shipping_limit_date | Fecha limite de despacho del item. | datetime | no | - | internal | Sin regla especifica |
| price | Precio del item en la moneda del origen (Olist: BRL). | float | no | - | internal | price_positive (critical) |
| freight_value | Costo de flete del item (Olist: BRL). | float | no | - | internal | freight_nonnegative (critical) |

## products

Dueno declarado: DataForge. Clasificacion: internal.

| Campo | Significado | Tipo | Nulo | Clave | Clasificacion | Reglas implementadas |
|---|---|---|---|---|---|---|
| product_id | Identificador del producto. | string | no | PK logica | internal | product_id_not_null (critical) |
| product_category_name | Categoria del producto en el origen. | string | si | - | internal | product_category_present (warning) |
| product_name_length | Longitud del nombre del producto; corrige product_name_lenght del CSV. | integer | si | - | internal | Sin regla especifica |
| product_description_length | Longitud de descripcion; corrige product_description_lenght del CSV. | integer | si | - | internal | Sin regla especifica |
| product_photos_qty | Cantidad de fotos del producto. | integer | si | - | internal | Sin regla especifica |
| product_weight_g | Peso del producto en gramos. | integer | si | - | internal | product_weight_positive_when_present (critical) |
| product_length_cm | Longitud del producto en centimetros. | integer | si | - | internal | product_length_positive_when_present (critical) |
| product_height_cm | Altura del producto en centimetros. | integer | si | - | internal | product_height_positive_when_present (critical) |
| product_width_cm | Ancho del producto en centimetros. | integer | si | - | internal | product_width_positive_when_present (critical) |

## Salida Gold order_items_gold

Join interno de order_items con orders, customers y products. Hereda las columnas
order_id, order_item_id, customer_id, customer_state, order_status,
order_purchase_timestamp, product_id, product_category_name, price y freight_value.
item_total es numerico y se deriva como price + freight_value (BRL).
La clasificacion de identificadores sensibles se conserva como criterio de gobierno;
revisar la proyeccion antes de consumo. No sumar price tras joins sin verificar cardinalidad.

## Datasets de demostracion

| Dataset | Campo | Tipo observado/declarado | Significado | Calidad de la demo |
|---|---|---|---|---|
| ventas | venta_id | integer | Identificador de venta sintetica | Sin regla especifica |
| ventas | producto | string | Nombre del producto sintetico | Sin regla especifica |
| ventas | cantidad | integer | Unidades vendidas | > 0, critical, allow_null=false |
| ventas | precio | numeric | Precio sintetico; moneda no declarada | > 0, critical, allow_null=false |
| tareas | userId | integer | Usuario sintetico del servicio JSONPlaceholder | <= 8, critical, allow_null=false |
| tareas | id | integer | Identificador de tarea del origen | Revisar contrato activo |
| tareas | title | string | Titulo de tarea | Revisar contrato activo |
| tareas | completed | boolean | Estado de finalizacion | Revisar contrato activo |

La fuente REST no contiene materia ni categoria: no permite sumar tareas por materia.
El contrato activo de la API es autoritativo para la revision exacta de cada demo.

## Metadatos operativos

Las definiciones columna por columna, PK/FK, nulabilidad y checks del control plane
estan en database/migrations/0001 a 0008; el diagrama y relaciones se explican en
[modelo de datos](../data-model/alpha-data-model.md). El [catalogo](data-catalog.md)
mapea entidades a consultas y pantallas. Las claves terminadas en _id identifican
entidades internas; storage_uri ubica el objeto, row_count cuenta filas del activo,
checksum permite verificar integridad y details_json conserva evidencia por regla.
