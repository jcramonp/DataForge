# Sprint 1 Alpha — Olist pilot dataset

Related issue: #1

## Selection

The pilot is the **Olist Brazilian E-Commerce Public Dataset**, published on
Kaggle by Olist. It represents orders placed in Brazilian marketplaces and
contains relational CSV files for customers, orders, order items, products,
sellers, payments, reviews and geolocation.

It is suitable for DataForge because it provides:

- several related sources instead of a single flat file;
- identifiers and relationships that can be validated;
- missing values, temporal fields and categorical values;
- records that can demonstrate acceptance and quarantine;
- enough volume to demonstrate the data lifecycle locally without requiring
  distributed processing.

Source: <https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce>

Before distributing any copy of the data, the team must verify the current
license and permitted academic use on the source page. Raw source files are not
committed to this repository.

## Alpha scope

Sprint 1 intentionally uses only four source tables:

| Logical table | Source file | Key | Purpose |
|---|---|---|---|
| customers | `olist_customers_dataset.csv` | `customer_id` | Customer/order relationship and location fields |
| orders | `olist_orders_dataset.csv` | `order_id` | Order lifecycle and timestamps |
| order_items | `olist_order_items_dataset.csv` | `order_id + order_item_id` | Products, sellers and monetary values per order |
| products | `olist_products_dataset.csv` | `product_id` | Product category and physical attributes |

Payments, reviews, sellers, category translation and geolocation remain outside
the Alpha vertical slice. They may be added later only when a target capability
requires them.

## Potentially sensitive fields

The public dataset is pseudonymized, but identifiers and coarse location fields
must still be handled conservatively:

- `customer_id` and `customer_unique_id`;
- `customer_zip_code_prefix`, `customer_city` and `customer_state`;
- `seller_id`.

The Alpha must not attempt re-identification. Reports should contain aggregate
metrics and a small number of non-sensitive examples, not complete records.
Secrets and local raw data remain excluded by `.gitignore`.

## Reproducible profiling

1. Download the dataset from the source.
2. Place the four CSV files under `data/raw/olist/` using their original names.
3. From the repository root, run:

```bash
python -m src.discovery.profile_olist
```

The command creates:

- `reports/generated/olist_profile.json`: machine-readable evidence;
- `reports/generated/olist_profile.md`: review-friendly summary.

Generated reports are local artifacts until the team reviews whether their
examples are safe to publish. The profiler records:

- file size, row and column counts;
- observed schema and schema differences;
- missing values and percentages;
- exact duplicate rows;
- duplicated or null primary keys;
- fields flagged as potentially sensitive;
- up to three example values per column.

Run the automated tests with:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

## Decision boundary

This change performs discovery only. It does **not** decide final quality
thresholds or implement Bronze, Silver, Quarantine or Gold. Those decisions
belong to issues #2 and #3 and must be based on the generated profile.

For the Sprint 1 Alpha, the intended execution remains a small reproducible
Python/Docker vertical slice. Kafka, PySpark, OpenMetadata, Prometheus, Grafana,
MLflow and production-scale orchestration belong to the broader target
architecture. Airflow, PostgreSQL and MinIO should only enter the Alpha when
they are needed by an implemented acceptance criterion, not merely because
they appear in the future architecture.
