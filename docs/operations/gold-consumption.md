# Gold consumption

In **Data Assets**, select the Gold layer and click **View Gold data #ID** on
the newest asset. The table displays actual values read from object storage,
the registered asset identity and URI, row count and checksum verification.
The viewer does not mutate data, execute a pipeline or change certification.

The intended user is a data analyst checking an aggregated data product. For
the Academy tasks demo, `userId` identifies the accepted user and `total_tareas`
counts accepted tasks. After the verified demo run, the expected result is
eight users (1–8), each with 20 tasks, total 160. Live UI validation is pending.

Example request through the existing SSM tunnel (PowerShell):

```powershell
$gold = Invoke-RestMethod 'http://localhost:8081/api/assets/8/gold-preview?limit=100'
$gold.rows | Format-Table
($gold.rows | Measure-Object -Property total_tareas -Sum).Sum
```

The JSON response includes `asset_id`, `asset_name`, `storage_uri`,
`checksum_verified`, `columns`, `total_rows`, `returned_rows`, `truncated` and
`rows`. It is read-only and marked `Cache-Control: no-store`.

Limits: 100 rows, 50 columns, 10 MiB stored object and 1 MiB serialized response.
This is a bounded preview for small products, not a distributed query engine.
Object bytes are checksum-checked and the first Arrow batch is converted to JSON;
compressed Parquet may expand in memory. Large products require a query service.
Only registered Gold Parquet assets in the configured Gold bucket are accepted;
callers cannot specify arbitrary URIs. Storage/DB failures return 503 without
upstream details. An overwritten or unverifiable object returns 409 rather than
misrepresenting an older asset's content. A missing ID returns 404.

Access uses the existing SSM-only application boundary; tenant authorization
and public authenticated access are not supplied by this feature.
