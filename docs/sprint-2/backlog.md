# Sprint 2 Backlog and Dependencies

## Parent epic

**#30 — Sprint 2: Final platform generalization and cloud delivery**

This issue is the sprint map. It is not an implementation task owned by one developer; it tracks the full Sprint 2 Definition of Done.

## Feature issues

| Order | Issue | Feature | Primary outcome |
|---:|---:|---|---|
| 1 | #19 | Generic dataset contracts/configuration | Common metadata/config schema for heterogeneous datasets |
| 2 | #20 | Generic source connectors | CSV/JSON/Parquet/PostgreSQL/REST ingestion interface |
| 3 | #21 | Generic schema discovery/profiling | Unknown datasets can be profiled without Olist assumptions |
| 4 | #22 | Generic Silver + Quality engine | Transformations/rules driven by configuration |
| 5 | #31 | Configurable Gold engine | Curated outputs defined by validated transformation plans |
| 6 | #23 | Lineage + certification | Explicit lineage and Draft/Validated/Certified governance |
| 7 | #24 | Metadata-driven Airflow | Reusable orchestration instead of dataset-specific DAGs |
| 8 | #25 | FastAPI control plane | Self-service API for platform operations |
| 9 | #26 | LLM configuration copilot | Natural-language assistance mapped to valid configuration |
| 10 | #27 | Web interface | Browser-based onboarding, monitoring and governance |
| 11 | #28 | AWS deployment | Cloud-hosted reference environment |
| 12 | #32 | CI/CD + observability | Reproducible validation, logs, health and deployment hardening |
| 13 | #29 | Multi-source final validation | Proof that the generalized platform works end-to-end |

## Dependency graph

```text
                         #19 Contracts
                              |
             +----------------+----------------+
             |                |                |
             v                v                v
      #20 Connectors     #21 Profiling     #23 Metadata/
             |                |            Governance
             +--------+-------+                |
                      v                        |
              #22 Silver + Quality             |
                      |                        |
                      v                        |
                 #31 Gold Engine <-------------+
                      |
                      v
                 #24 Airflow
                      |
                      v
                 #25 FastAPI
                    /     \
                   v       v
              #26 LLM    #27 Web UI
                   \       /
                    \     /
                      v
                   #28 AWS
                      |
                      v
             #32 CI/CD + Operations
                      |
                      v
             #29 Final Validation
```

The diagram expresses the dominant dependency order, not a rule that all work must be serial. Tasks can run in parallel when their contracts are stable.

## Recommended team parallelization

After #19 reaches a stable contract:

- Contributor A can advance #20 connectors.
- Contributor B can advance #21 profiling.
- Contributor C can advance #23 metadata/governance design.

Once those foundations are stable, work can move into #22/#31/#24 and then API/LLM/UI.

Avoid starting deep UI/LLM/cloud implementation before the configuration contracts and core service interfaces are stable.

## Issue decomposition rule

The feature issues above are intentionally feature-sized. If an issue becomes too large for one contributor/PR, split it into child implementation issues.

Example for #20:

- connector base interface;
- file connector;
- PostgreSQL connector;
- REST connector;
- connector integration tests.

Create child issues only when the team is ready to execute that feature. Do not create dozens of speculative issues before the implementation contract is understood.

## Completion rule

An issue is not Done because code exists. It is Done only when:

1. acceptance criteria are satisfied;
2. tests/evidence are included;
3. documentation is updated when behavior changes;
4. regression behavior remains valid;
5. the PR is reviewed and merged into `develop`;
6. the parent issue/checklist can truthfully be updated.
