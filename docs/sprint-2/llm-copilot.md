# LLM Configuration Copilot

## Purpose

The LLM copilot helps bridge the gap between technical profiling and business intent. It is not part of the deterministic execution engine.

The core problem is that DataForge can automatically detect technical facts such as nulls, types and ranges, but it cannot infer every business-quality rule correctly from raw values alone.

## Example

Profiling may discover:

```text
column: product_weight_g
type: integer
nulls: 2
minimum: 0
```

DataForge can report this fact deterministically.

The LLM can then help a user express intent such as:

> Product weight may be missing in exceptional cases, but if present it must be greater than zero.

The assistant can propose a structured rule that the platform validates before it can be used.

## Inputs

The LLM service may receive a constrained context containing:

- dataset name/description;
- discovered schema;
- normalized types;
- profiling summaries;
- existing configuration;
- user natural-language requirements;
- list of operations/rules supported by DataForge.

The design should prefer profiling summaries/metadata over sending unnecessary raw dataset contents.

## Outputs

LLM outputs must be structured and map to the DataForge configuration contract.

Potential proposal types:

- quality rules;
- warning/critical severity;
- supported Silver transformations;
- supported Gold transformation plans;
- explanations of profiling findings.

## Required execution flow

```text
User request + profiling metadata
              |
              v
             LLM
              |
              v
Structured proposal
              |
              v
Pydantic / contract validation
              |
              v
Reference validation
(columns, datasets, operations)
              |
              v
User preview / approval
              |
              v
Persist configuration
              |
              v
Deterministic DataForge engine
```

## Hard guardrails

The LLM must not:

- execute generated Python/SQL/shell code as an unrestricted operation;
- create arbitrary transformation functions at runtime;
- bypass the supported-rule registry;
- invent columns/datasets and silently persist them;
- change production configuration without validation/approval;
- become a mandatory dependency for normal deterministic pipeline execution.

## Failure behavior

If a proposal is invalid or unsupported:

1. reject it during schema/semantic validation;
2. return a clear reason;
3. preserve the previous valid configuration;
4. allow the user to edit/retry the proposal.

## Provider abstraction

The application should use an internal LLM service interface so the rest of DataForge is not tightly coupled to one provider.

For the AWS reference deployment, Amazon Bedrock is a natural option, but the architecture should permit another provider/model without changing the data pipeline core.

## Why use an LLM here?

The LLM is useful because heterogeneous datasets create a semantic problem, not only a technical-format problem.

Contracts/connectors solve technical heterogeneity. The LLM helps users express domain intent in a structured form that the deterministic engine can validate.

## Sprint 2 success criteria

- Natural-language requirements can produce a valid structured proposal.
- Profiling findings can be included in suggestion context.
- Invalid suggestions are rejected safely.
- A user explicitly reviews the proposal before applying it.
- The pipeline remains functional when configuration is created manually without the LLM.

## Implementación #26

`src/copilot/service.py` define Protocol Provider, adaptador Bedrock Converse, modelos estrictos,
validación del contrato completo y tokens firmados de revisión. El LLM propone adiciones de reglas
(con severity explícita) y transformaciones Silver soportadas; no modifica identidad, schema ni conexiones.
No se genera ni ejecuta Python/SQL/shell. Outputs inválidos/unsupported se rechazan con 422 y el
proveedor no disponible devuelve 503. No hay fallback implícito.

`POST /api/copilot/suggest`: client_code, project_code, source_code, dataset_code, requirement,
mode (llm por defecto o deterministic explícito). Lee contrato activo y profiling desde PostgreSQL.
Devuelve proposal, contract, token, provider, profile_id y approval_required.

`POST /api/copilot/approve`: token y approved=true. Revalida firma, caducidad, contrato y hash
base actual; registra una revisión usando el servicio de onboarding, con control de concurrencia
bajo su bloqueo transaccional por fuente. No dispara pipelines. Conflictos devuelven 409.

La UI muestra reglas/transformaciones/contrato completo, exige revisión explícita, invalida previews
cuando cambia el contexto y sólo informa guardado tras respuesta exitosa del servidor.
Variables, preparación y guion: [Demo y verificación](../evidence/copilot-verification.md).
Adaptador basado en [Boto3 Converse](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html).
