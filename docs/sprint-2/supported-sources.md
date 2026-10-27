# Sprint 2 Supported Sources and Boundaries

## Purpose

DataForge does not attempt to support every possible data source or semantic business rule in Sprint 2. The platform generalizes a defined set of technical source families through connectors and contracts.

## Supported source families

### Files

Target formats:

- CSV
- JSON
- Parquet

Expected capabilities:

- configurable path/upload/source reference;
- schema inference;
- version/checksum where applicable;
- ingestion to Bronze;
- generic profiling.

### PostgreSQL

Target capabilities:

- connection test;
- table extraction;
- configurable query extraction where safely supported;
- schema discovery;
- batch ingestion to Bronze;
- traceable connection/extraction errors.

### REST APIs returning JSON

Target capabilities:

- configurable endpoint;
- HTTP method limited to supported read/extraction operations;
- request parameters/headers through configuration;
- JSON response extraction;
- configurable pagination strategies where implemented;
- scheduled/polled batch ingestion.

REST support in Sprint 2 is not equivalent to continuous event streaming.

## Not guaranteed in Sprint 2

Examples that remain outside the guaranteed source contract:

- Kafka/event streams with continuous processing;
- Oracle, SQL Server, MongoDB or arbitrary databases without a connector;
- SOAP/XML pipelines;
- binary media processing;
- arbitrary nested/unbounded API behavior that is not covered by the REST connector contract;
- proprietary vendor protocols.

These can be future connector implementations without changing the core DataForge architecture.

## Heterogeneous schemas

DataForge handles schema variability through:

1. generic source connectors;
2. schema inference/discovery;
3. normalized internal data types;
4. dataset configuration contracts;
5. declarative transformations;
6. declarative quality rules.

The engine should not need to understand the business meaning of every possible column name in order to ingest, profile, version and validate technical constraints.

## Initial normalized type model

The configuration contract should support at least:

- string;
- integer;
- float/decimal-compatible numeric;
- boolean;
- date;
- datetime;
- JSON/object where supported;
- nullability metadata.

Exact physical mappings depend on the source/processing library and are defined by the implementation issue #19/#22.

## Business semantics boundary

Technical profiling can detect observations such as:

- null percentage;
- negative values;
- unusual ranges;
- high/low cardinality;
- duplicate keys;
- parsing problems.

It cannot reliably decide whether every observation is a business error.

Example:

- a negative value may be invalid for product weight;
- a negative value may be valid for a financial balance/change.

Therefore business-quality decisions must come from explicit configuration, user confirmation, or LLM-assisted proposals that are reviewed and validated before execution.

## Streaming boundary

A REST endpoint that is polled every N minutes is treated as scheduled batch ingestion.

True event streaming requires a different execution model such as Kafka + stream processing and is a future extension unless later course requirements explicitly move it into scope.
