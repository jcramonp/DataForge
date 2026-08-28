# Olist Alpha Data Assessment

## Pilot scope

For Sprint 1, DataForge will use four tables from the Brazilian E-Commerce Public Dataset by Olist as the first pilot source:

- `olist_customers_dataset.csv`
- `olist_orders_dataset.csv`
- `olist_order_items_dataset.csv`
- `olist_products_dataset.csv`

These four tables are sufficient to demonstrate relational discovery, data profiling, referential integrity, Bronze/Silver/Gold processing, quarantine rules, and the construction of an analytical Gold dataset.

## Source sizes

| File | Rows | Columns | Approx. CSV size |
|---|---:|---:|---:|
| customers | 99,441 | 5 | 8.62 MB |
| orders | 99,441 | 8 | 16.84 MB |
| order_items | 112,650 | 7 | 14.72 MB |
| products | 32,951 | 9 | 2.27 MB |

## Initial structural findings

### Customers

- `customer_id`: 99,441 unique values; candidate primary key.
- `customer_unique_id`: 96,096 unique values; repeated values represent the same logical customer across different orders.
- No null values were detected in the five columns.
- No fully duplicated rows were detected.
- 27 customer states are represented.

### Orders

- `order_id`: 99,441 unique values; candidate primary key.
- `customer_id`: 99,441 unique values in this table and every value exists in `customers`.
- No fully duplicated rows were detected.
- `order_approved_at`: 160 nulls (0.161%).
- `order_delivered_carrier_date`: 1,783 nulls (1.793%).
- `order_delivered_customer_date`: 2,965 nulls (2.982%).
- Eight order statuses are present: delivered, shipped, canceled, unavailable, invoiced, processing, created and approved.
- 96,478 orders have status `delivered`.

### Order items

- 112,650 rows.
- Composite key candidate: (`order_id`, `order_item_id`); no duplicates were found for this pair.
- Every referenced `order_id` exists in `orders`.
- Every referenced `product_id` exists in `products`.
- `price` contains no nulls, negative values, or zeros; observed range: 0.85 to 6,735.00.
- `freight_value` contains no negative values; 383 rows have zero freight.
- 98,666 distinct orders appear in this table.
- 9,803 orders contain more than one item; maximum observed number of items in one order is 21.

### Products

- `product_id`: 32,951 unique values; candidate primary key.
- No fully duplicated rows were detected.
- `product_category_name`: 610 nulls (1.851%).
- The product name length, description length, and photo quantity fields also contain 610 nulls each.
- Product weight and dimensions contain 2 nulls each.
- `product_weight_g` contains 4 zero values, which should be reviewed as a possible quality rule violation.
- 73 non-null product categories are present.

## Referential integrity

The four selected tables exhibit clean referential integrity for the primary relationships used in the Alpha pipeline:

- Orders with a `customer_id` missing from customers: **0**.
- Order items with an `order_id` missing from orders: **0**.
- Order items with a `product_id` missing from products: **0**.

However, 775 orders do not have rows in `order_items`. Their statuses are primarily `unavailable` (603) and `canceled` (164), with a few `created`, `invoiced`, and `shipped` records. This is likely business-state behavior rather than a referential-integrity error and should not be quarantined automatically without considering order status.

## Temporal findings

All non-null order date fields parsed successfully as timestamps.

Observed purchase timestamp range:

- Earliest: 2016-09-04 21:15:19
- Latest: 2018-10-17 17:30:18

Potential temporal anomalies requiring a business-rule decision:

- 166 rows have `order_delivered_carrier_date` earlier than `order_purchase_timestamp`.
- 23 rows have `order_delivered_customer_date` earlier than `order_delivered_carrier_date`.
- 7,827 delivered dates occur after the estimated delivery date. These are late deliveries and represent useful business information, not necessarily bad data.

## Initial quality-rule candidates

The profiling suggests the following first rules for DataForge:

1. Primary identifiers (`customer_id`, `order_id`, `product_id`) must not be null.
2. Primary identifiers must be unique in their entity tables.
3. (`order_id`, `order_item_id`) must be unique in order items.
4. Order-item `price` must be greater than zero.
5. `freight_value` must be greater than or equal to zero.
6. Product weight and dimensions should be positive when present.
7. Referential relationships between customers -> orders -> order_items -> products must be valid.
8. Timestamp fields must be parseable when present.
9. Temporal sequencing anomalies should be flagged for review rather than blindly deleted.
10. Missing product categories should be retained but explicitly classified as incomplete data for Silver transformation.

## Proposed Alpha flow

`CSV source -> Bronze -> profiling/quality validation -> Silver or Quarantine -> Gold`

### Bronze

Preserve the selected CSV datasets as immutable/raw ingested data, recording source, ingestion timestamp, and dataset version.

### Silver

- Parse timestamp columns.
- Standardize column types.
- Preserve valid business-status nulls where justified.
- Normalize incomplete product-category values.
- Apply referential-integrity and numeric-domain checks.
- Flag temporal inconsistencies.

### Quarantine

Only records that violate explicit technical or agreed business-quality rules should be separated. Business-valid states such as canceled orders without order items should not be quarantined solely because they lack line items.

### Gold

Construct an analytical order-item dataset by integrating customers, orders, order items, and products. The Gold dataset should include order/customer geography, purchase timestamp, order status, product category, item price, freight value and derived analytical fields.

## Governance notes

- The Olist dataset is anonymized; no direct names, emails, or phone numbers are present in the four selected tables.
- `customer_id` and `customer_unique_id` should still be treated as pseudonymous customer identifiers and documented accordingly.
- Each generated dataset should record source, owner, layer, version, quality result and lineage.

## Sprint 1 conclusion

The pilot data is suitable for the DataForge Alpha because it is relational, contains realistic missing values and temporal issues, supports meaningful data-quality decisions, and allows the team to demonstrate integration and analytical dataset creation without requiring an impractically large infrastructure footprint.
