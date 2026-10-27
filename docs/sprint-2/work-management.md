# Sprint 2 GitHub Work Management

## Management hierarchy

Sprint 2 is organized using the following hierarchy:

```text
Milestone: Sprint 2 — Platform Generalization
        |
        v
Parent/Epic Issue: #30
        |
        v
Feature Issues: #19-#29, #31, #32
        |
        v
Feature branches
        |
        v
Pull Requests -> develop
        |
        v
Release PR -> main
```

## Branch strategy

- `main`: stable, demonstrable releases only.
- `develop`: integration branch for Sprint 2.
- `feature/<issue>-<short-description>`: implementation work.
- `fix/<issue>-<short-description>`: corrections.
- `docs/<short-description>`: documentation-only work.

Examples:

- `feature/19-config-contract`
- `feature/20-postgres-connector`
- `feature/21-generic-profiling`
- `feature/26-llm-copilot`
- `fix/24-airflow-run-state`

No direct feature work should be pushed to `main`.

## Issue ownership

Work is assigned by issue, not by permanent role silos.

Good:

- one contributor owns a connector feature;
- another owns profiling;
- another owns governance;
- ownership can change between features.

Avoid:

- one person only doing documentation;
- one person owning all backend work without review;
- team members being unable to explain components they did not implement.

Every issue owner is responsible for implementation, tests/evidence and keeping the issue status accurate.

## Project Board statuses

Recommended GitHub Project workflow:

1. **Backlog** — defined but not ready/selected for current work.
2. **Ready** — dependencies satisfied and ready to start.
3. **In Progress** — actively being implemented.
4. **In Review** — pull request open or acceptance review in progress.
5. **Done** — merged and acceptance criteria satisfied.

Recommended Project fields:

- Status.
- Assignee.
- Priority: P0/P1/P2.
- Feature/Epic: #30.
- Target environment: Local / AWS / Both.
- Evidence required: Yes/No.

## Suggested priorities

### P0 — platform foundations

- #19 contracts/configuration.
- #20 connectors.
- #21 profiling.
- #22 Silver/quality.
- #31 Gold engine.
- #23 lineage/certification.
- #24 orchestration.

### P1 — product experience and deployment

- #25 FastAPI.
- #26 LLM copilot.
- #27 UI.
- #28 AWS.
- #32 CI/CD and operations.

### P0 final gate

- #29 multi-source final validation.

#29 is the release proof and cannot be skipped.

## Pull request flow

```text
feature branch
      |
      v
PR -> develop
      |
      v
review + automated checks
      |
      v
merge
```

At the end of Sprint 2:

```text
develop
   |
   v
release PR
   |
   v
main
```

## Pull request requirements

Every implementation PR should contain:

### Summary

What capability was added or changed?

### Why

Which issue/problem does it solve?

### Changes

Main technical changes.

### Verification

Commands/tests/manual evidence used to validate the change.

### Compatibility/regression

Does Olist/Sprint 1 still work? What regression tests were run?

### Related issue

Use `Closes #N` only when the PR fully satisfies that issue. If it is partial work, use `Related to #N`.

## Issue decomposition

Feature issues may be split into child issues when execution begins.

A child issue should be independently reviewable and should usually fit in one focused PR.

Do not close the parent feature until all acceptance criteria of the parent are satisfied.

## Definition of Ready

An issue moves to Ready when:

- dependencies are available;
- expected input/output contract is understood;
- acceptance criteria are testable;
- the responsible contributor is known;
- there is no unresolved architecture decision blocking implementation.

## Definition of Done

An issue moves to Done when:

- implementation is merged to `develop`;
- tests pass;
- acceptance criteria are verified;
- relevant docs are updated;
- failure/error behavior was considered;
- no secrets were committed;
- Sprint 1 regression behavior remains intact where relevant;
- evidence exists for user-visible/architecture-critical behavior.

## Team review rule

Before final delivery, every team member should be able to explain:

- source onboarding and connectors;
- Bronze/Silver/Quality/Gold flow;
- control plane vs data plane;
- Airflow's role;
- LLM guardrails;
- lineage/certification;
- local Docker Compose vs AWS deployment.

The issue owner implements the feature, but knowledge must not remain isolated to that owner.
