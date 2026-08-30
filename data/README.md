# Local data workspace

This directory represents the logical data zones used during local development:

- `raw/`: source files used for ingestion tests.
- `bronze/`: immutable/raw ingested data.
- `silver/`: validated, cleaned, and standardized data.
- `gold/`: curated datasets ready for analytical or ML consumption.
- `quarantine/`: records rejected by data-quality rules.

Dataset files and generated artifacts should not be committed unless they are deliberately included as small reproducible samples.
