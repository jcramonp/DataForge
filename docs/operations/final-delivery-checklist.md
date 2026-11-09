# Final delivery status — 2026-11-09

## Verified reference environment

- AWS runtime on EC2 with RDS metadata and S3 data assets.
- Generic REST pipeline: 200 Bronze, 160 Silver, 40 quarantine, 8 Gold rows.
- Real Groq proposal, server validation, explicit approval, contract #2/rev 2,
  successful Airflow orchestration #2, persisted quality results and lineage.
- Read-only Gold consumption API and web view: users 1–8, 20 tasks each,
  checksum verified. See `docs/evidence/aws-gold-consumption-verification.md`.
- Three infrastructure alarms and confirmed SNS email delivery/recovery.
- Historical Olist regression evidence in `docs/evidence/olist-final-verification.md`
  and `olist-final-live-run.json` (2026-10-26); this is not a fresh Academy run.

## Reproduce the demo configuration

`config/examples/academy-tareas-rest-groq.json` is a validated, secret-free
snapshot reconstructed from the complete approved contract supplied by the
operator. It includes all three quality rules and the Gold aggregation.
It is not a database dump, signed proposal or backup of contract identifiers.

On a fresh deployment, submit it through the existing onboarding endpoint:

```powershell
$body = Get-Content '.\config\examples\academy-tareas-rest-groq.json' -Raw
$registered = Invoke-RestMethod -Method Post `
  -Uri 'http://localhost:8081/api/onboarding/contracts' `
  -ContentType 'application/json' -Body $body
$registered | ConvertTo-Json -Depth 10
```

Use the returned contract ID/revision in the pipeline controls. IDs depend on
database history and must not be hardcoded. This registers the resulting
configuration directly; demonstrating LLM generation separately still requires
the configured Groq key and a fresh, uniquely named additions-only proposal.
Do not re-register the snapshot into the verified live environment merely to
collect evidence: it may reactivate a revision or affect active configuration.

## Remaining closure checks

1. Confirm `/api/ready` on the deployed API. It checks configuration, PostgreSQL
   and migrations, storage and shipped example contracts. It does not invoke
   Groq or check Airflow scheduler health. Infrastructure alarm health is also
   separate from application readiness.
2. Resolve GitHub account lock and rerun required validation. For commit
   `cf7ad0e`, CI run `42577236523` still reports failure on all eight jobs
   without steps/logs. This is consistent with the previously shown billing
   lock; this API response does not expose a fresh billing annotation.
   Never label the local checks or manual rollout as successful hosted CI/CD.
3. Finish application/pipeline monitoring as required by the final rubric;
   a successful CloudWatch/SNS infrastructure test does not prove those checks.
4. Verify from-scratch deployment and recovery instructions. Preserve actual
   Terraform state privately and back up required data; do not run a fresh
   Terraform state against the already-provisioned environment. Current
   reference deployments were repaired incrementally, not rebuilt empty.
5. Check current Academy credit and record cost assumptions, then calculate
   base/10x/100x ingress and consumption scenarios. Historical remaining credit
   must not be treated as current.
6. Complete the final report, architecture rationale, cost sensitivity and
   timed demo using the professor's actual rubric/template.
7. Review and merge PR #53 only after the agreed validation is available.
   Review issue #28 (deployment), #29 (multi-source evidence) and #32 (CI/ops)
   against their acceptance criteria before closing them.

The deployed UI uses the SSM tunnel. Public access, if required for evaluation,
needs a separately reviewed authenticated design; a public URL is not implied
by the existing deployment. No new public exposure is required to use the
current demonstration.
