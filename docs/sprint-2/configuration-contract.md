# Sprint 2 Configuration Contract Design

## Goal

The configuration contract is the boundary between user/business intent and deterministic DataForge execution.

A new dataset should be describable through structured configuration rather than by adding client-specific branches to the core engine.

## Contract responsibilities

The contract should be able to describe:

- client/project identity;
- source type and connection reference;
- dataset identity;
- source object/table/path/endpoint;
- schema and normalized data types;
- Bronze ingestion options;
- Silver transformations;
- quality rules and severity;
- Gold transformation plans;
- ownership/classification metadata;
- scheduling/orchestration parameters where supported.

## Validation principle

All configuration is validated before execution.

Planned validation layers:

1. JSON/YAML syntax.
2. Pydantic/JSON Schema structure.
3. Supported enum/operation validation.
4. Source/dataset/column reference validation.
5. Cross-field semantic validation.
6. User review for LLM-generated proposals.

## Example conceptual structure

```yaml
client: retail-co
project: sales-analytics

source:
  type: postgresql
  connection_reference: retail-postgres
  object: public.sales

dataset:
  code: sales
  owner: analytics-team
  classification: internal

schema:
  sale_id:
    type: string
    nullable: false
  amount:
    type: float
    nullable: true
  created_at:
    type: datetime
    nullable: false

silver:
  transformations:
    - operation: trim
      column: sale_id
    - operation: cast
      column: created_at
      type: datetime

quality:
  rules:
    - column: sale_id
      rule: not_null
      severity: critical
    - column: amount
      rule: greater_than_or_equal
      value: 0
      severity: warning

gold:
  enabled: true
  plan:
    - operation: select
      columns: [sale_id, amount, created_at]
```

This is an architectural example, not the final implementation schema. Issue #19 owns the final versioned contract.

## Supported-operation principle

The contract must only permit operations implemented by DataForge.

Examples of supported operation families may include:

- cast;
- trim/lower/upper;
- rename;
- select/drop;
- filter using approved operators;
- not-null/range/regex/allowed-values/uniqueness quality rules;
- deterministic derived fields using an approved expression model;
- joins between registered datasets;
- grouping/common aggregations.

Unsupported operations fail validation instead of falling back to arbitrary generated code.

## Versioning

The contract should carry a version so DataForge can evolve configuration safely.

Example:

```yaml
contract_version: 1
```

Backward compatibility/migrations should be considered when the contract changes.

## LLM integration

The LLM does not bypass this contract.

```text
Natural-language request
       |
       v
LLM proposal
       |
       v
Structured configuration
       |
       v
Contract validation
       |
       v
User review
       |
       v
Persist + execute
```

Any LLM output that cannot be represented by the supported contract is rejected or returned to the user as an unsupported suggestion.

## Sprint 2 success criterion

Olist and at least one non-Olist dataset must be represented and processed through the same contract model without changing the contract engine for client-specific column names.
