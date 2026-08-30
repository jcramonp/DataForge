# Alpha Performance and Partitioning Verification

## Objective

Evaluate basic performance and physical-design decisions for the DataForge
Alpha data plane and control plane.

The goal is not to claim production-scale optimization from the Olist pilot,
but to verify empirically how partitioning and database indexes affect the
current workload.

## 1. Gold Parquet partitioning benchmark

The current Gold dataset contains 112,642 order-item-grain rows.

A benchmark compared:

1. Full read of the unpartitioned Gold Parquet file.
2. Filtered read of the unpartitioned Parquet file.
3. Filtered read of a temporary Parquet dataset partitioned by
   `customer_state`.

The benchmark used the most frequent state, `SP`, with 47,448 matching rows,
and five repetitions per execution.

### Execution 1

| Metric | Result |
|---|---:|
| Full Parquet read median | 92.040 ms |
| Filtered unpartitioned median | 56.889 ms |
| Filtered partitioned median | 9.238 ms |
| Filter speed ratio | 6.158x |
| Unpartitioned size | 9.658 MB |
| Partitioned size | 11.576 MB |

### Execution 2

| Metric | Result |
|---|---:|
| Full Parquet read median | 89.549 ms |
| Filtered unpartitioned median | 58.767 ms |
| Filtered partitioned median | 11.334 ms |
| Filter speed ratio | 5.185x |
| Unpartitioned size | 9.658 MB |
| Partitioned size | 11.576 MB |

### Interpretation

Across both benchmark executions, filtering the dataset partitioned by
`customer_state` was approximately 5.18x to 6.16x faster than filtering the
single unpartitioned Parquet file.

The partitioned representation increased storage from 9.658 MB to 11.576 MB,
approximately a 20% increase.

For the Alpha workload, this demonstrates a measurable trade-off between
storage overhead and filtered-query performance. The result applies
specifically to filters aligned with the selected partition column and should
not be generalized to every query pattern.

The benchmark creates the partitioned dataset only in a temporary local
directory. The production Alpha Gold asset in MinIO is not modified.

## 2. PostgreSQL control-plane optimization

A representative metadata query was analyzed using `EXPLAIN ANALYZE`.

The query traversed:

`dataset -> dataset_version -> pipeline_run -> data_asset`

and filtered the `products` dataset to successful pipeline runs.

### Observed plan

PostgreSQL used the following indexes:

- `idx_dataset_version_dataset_id`
- `idx_pipeline_run_dataset_version_id`
- `idx_data_asset_run_id_layer`

The observed execution time was:

```text
Execution Time: 3.752 ms