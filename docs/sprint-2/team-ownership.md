# Sprint 2 Team Ownership Plan

Operational responsibilities are formalized in [RACI](../governance/raci.md).
The initial plan below is historical planning, not evidence of individual authorship.

## Principle

Ownership is assigned by feature, not by permanent role silos. The owner coordinates implementation, tests, documentation and PR completion for the issue, but all team members must understand the full platform before final delivery.

The allocation below is an initial balanced plan and can be adjusted as workload becomes clearer.

## Initial feature ownership

### Juan Camilo Ramón

Primary ownership:

- **#19 — Generic dataset contracts and configuration model**
- **#24 — Metadata-driven Airflow orchestration**
- **#26 — LLM-assisted configuration copilot**

Rationale:

These issues define the common contract, orchestration model and LLM/configuration boundary, which are tightly related to the end-to-end architecture established in Sprint 1.

### Felipe Castro Jaimes

Primary ownership:

- **#20 — Generic source connectors**
- **#25 — FastAPI control plane and self-service onboarding**
- **#28 — AWS reference deployment**

Rationale:

These issues form a coherent path from source connectivity to the external control-plane API and final cloud deployment.

### Gabriela Sanabria

Primary ownership:

- **#21 — Generic schema discovery and profiling**
- **#23 — Lineage and dataset certification**
- **#27 — DataForge web interface**

Rationale:

These issues connect discovery/governance metadata with how users inspect and operate that information from the product interface.

## Shared/core review issues

The following features should have one coordinating owner selected when implementation begins, but require explicit review/participation from the full team:

- **#22 — Generic Silver transformation and quality engine**
- **#31 — Configurable Gold transformation and serving engine**
- **#32 — CI/CD, observability and deployment hardening**
- **#29 — Multi-source end-to-end validation and final evidence**

These are cross-cutting or release-critical and should not become knowledge silos.

## Recommended first parallel wave

After #19 has a stable contract, the team can work in parallel:

```text
Juan       -> finish/stabilize #19, then orchestration design
Felipe     -> #20 connectors
Gabriela   -> #21 profiling and #23 governance design
```

Do not start deep UI, LLM or AWS implementation before their underlying API/contracts are stable.

## Review rotation

Recommended rule:

- PR author cannot be the only person validating the change.
- At least one other team member reviews architecture-critical PRs.
- Cross-cutting issues (#22, #31, #24, #25, #26, #28, #29, #32) should receive review from a contributor outside the primary ownership path.

## Final knowledge requirement

Before the final presentation, every member should be able to explain:

1. why DataForge uses generic contracts/connectors;
2. how schema discovery/profiling works;
3. Bronze -> Silver -> Quality -> Quarantine/Validated -> Gold;
4. PostgreSQL control plane vs object-storage data plane;
5. how Airflow orchestrates reusable stages;
6. why the LLM proposes but does not execute arbitrary code;
7. lineage and certification;
8. Docker Compose local development vs AWS reference deployment;
9. how the second source proves platform generalization.
