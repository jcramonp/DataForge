# Metadata and Governance Verification

## Sprint 1 Alpha

DataForge metadata and governance capabilities were verified against the running
PostgreSQL metadata database.

## Metadata coverage

The Olist Alpha contains metadata for:

- customers
- orders
- order_items
- products
- order_items_gold

Each registered dataset includes its source, logical entity, classification and
owner.

Source datasets include schema hashes and source checksums.

## Lineage verification

The `dataset_lineage_summary` PostgreSQL view was created successfully.

A Gold lineage query returned:

- dataset: `order_items_gold`
- version: `gold-238b78d9d494`
- pipeline type: `silver_to_gold`
- layer: `gold`
- asset: `olist_order_items_gold`
- rows: 112642
- storage:
  `s3://dataforge-gold/olist/order_items/v1/olist_order_items_gold.parquet`

This verifies that the generated Gold asset can be traced through the DataForge
operational metadata model.

## Quality metadata verification

The `data_quality_summary` PostgreSQL view was created successfully.

The latest product quality run recorded:

- 32951 input products
- 32947 accepted products
- 4 quarantined products

The rule `product_weight_positive_when_present` detected 4 invalid records,
representing approximately 0.0121% of the product dataset.

The rule `product_category_present` detected 610 records without a product
category, approximately 1.8512% of the dataset. This rule operates with a
tolerance threshold and therefore does not quarantine these records.

## Conclusion

The Sprint 1 Alpha provides operational metadata for ownership, classification,
versioning, pipeline execution, quality results, storage assets and basic
lineage.

Dedicated catalog tooling and explicit asset-to-asset lineage remain part of the
target architecture rather than the Alpha scope.