# Sprint 2 GitHub Project and Milestone Setup

## Milestone

Create one repository milestone:

**Title:** `Sprint 2 — Platform Generalization`

**Description:**

> Convert the Sprint 1 Olist Alpha into an almost-final, self-service, metadata-driven DataForge platform with heterogeneous-source support, generic profiling/transformation/quality, governance, LLM-assisted configuration, a web UI, AWS reference deployment and multi-source end-to-end validation.

Associate the following feature issues with the milestone:

- #19
- #20
- #21
- #22
- #23
- #24
- #25
- #26
- #27
- #28
- #29
- #31
- #32

The parent epic #30 may also be associated with the milestone for visibility.

A due date should be added once the official Sprint 2 delivery date is confirmed.

## GitHub Project

Create a repository/user Project named:

**`DataForge — Sprint 2`**

### Status values

Use these workflow states:

1. `Backlog`
2. `Ready`
3. `In Progress`
4. `In Review`
5. `Done`

### Recommended fields

#### Status

Single-select using the workflow values above.

#### Priority

Single-select:

- `P0 — Required`
- `P1 — Important`
- `P2 — Stretch`

#### Owner

Use the GitHub assignee field when possible.

#### Target environment

Single-select:

- `Local`
- `AWS`
- `Both`

#### Evidence required

Single-select:

- `Yes`
- `No`

#### Parent/Epic

Use parent/sub-issue relationships if available, or link all Sprint 2 issues to #30 in issue bodies/comments.

## Initial board population

### Ready

- #19 — Generic dataset contracts and configuration model

### Backlog

- #20 — Generic source connectors
- #21 — Generic schema discovery and profiling
- #22 — Generic Silver transformation and quality engine
- #31 — Configurable Gold transformation and serving engine
- #23 — Lineage and dataset certification
- #24 — Metadata-driven Airflow orchestration
- #25 — FastAPI control plane and self-service onboarding
- #26 — LLM-assisted configuration copilot
- #27 — Web interface
- #28 — AWS reference deployment
- #32 — CI/CD, observability and deployment hardening
- #29 — Multi-source final validation and evidence

#30 is the epic/sprint map rather than a normal implementation card.

## Initial priority proposal

### P0 — Required core/release work

- #19 contracts
- #20 connectors
- #21 profiling
- #22 Silver/quality
- #31 Gold
- #23 lineage/certification
- #24 Airflow
- #25 FastAPI
- #29 final validation

### P1 — Required product experience/deployment

- #26 LLM copilot
- #27 web UI
- #28 AWS
- #32 CI/CD/operations

All P1 items are part of the Sprint 2 target; the distinction indicates implementation dependency/sequence, not optionality.

## Board transition rules

### Backlog -> Ready

Move when dependencies and contracts are stable enough to begin.

### Ready -> In Progress

Move when an owner creates/starts the implementation branch.

### In Progress -> In Review

Move when the pull request to `develop` is open and implementation is ready for review.

### In Review -> Done

Move only after:

- PR merged into `develop`;
- acceptance criteria verified;
- required tests/evidence completed;
- relevant documentation updated.

## Release tracking

The Project is for Sprint 2 execution. `main` remains the stable release branch. Sprint 2 work integrates into `develop`, and only after the final release gate (#29) should a release PR be opened from `develop` to `main`.
