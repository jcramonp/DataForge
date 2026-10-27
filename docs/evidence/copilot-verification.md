# Issue #26: LLM configuration copilot — verification

## Status and scope

Implementation is present in the Work checkout on develop, based on 2c99ddb
(merge of PR #48). It has not been committed, pushed or merged.
Functional validation is complete according to the previous-session handoff,
with the final UI-generated quality rule independently rechecked on 2026-10-26.
Administrative completion still requires transfer to the primary checkout,
regression there, a PR targeting develop, green CI, review and merge.

Historical evidence below was supplied in the continuation handoff on 2026-10-26.
It is distinguished from checks repeated in this continuation session.

## Automated verification recorded before handoff

- Python unittest discovery: 348 tests total, 35 integration tests skipped,
  313 executed without failures.
- Frontend: 12 tests passed; Vite build passed.
- Ruff passed.
- Negative tests cover invalid output, unsupported operations, nonexistent columns,
  approved=false, altered/expired tokens, stale contracts and provider errors.
- API tests cover proposals without persistence, explicit approval and persistence,
  409 concurrency conflicts, 422 validation errors and 503 provider failures.
- After the final concurrency fix, the 24 API/copilot tests and frontend tests/build
  were repeated successfully.

These historical counts do not claim that the skipped integration suite ran.

## Live environment and provider validation (handoff)

- Local API: http://localhost:8001; /api/ready reported READY.
- PostgreSQL connected; migration 0007.
- MinIO and Airflow reachable.
- Amazon Bedrock region: us-east-2.
- Model: qwen.qwen3-235b-a22b-2507-v1:0.
- Direct boto3 bedrock-runtime Converse returned a JSON status of ok and message
  "bedrock works".
- Credentials and the proposal signing key were supplied through process
  environment variables. No credential values are part of this evidence.

## Real API workflow: Bedrock to persisted quality result (handoff)

Target: client ci-retail, project ci-retail-e2e, source ci-retail-csv,
dataset orders.

Initial active contract: #2, revision 2.
Profiling #7: 7 rows, 5 columns; amount minimum -3, maximum 20,
one negative value; order_id had one null (14.29%).
Profiling source_asset_id=67 and run_id=68.

The requirement requested a NEW warning rule named demo_amount_reasonable:
amount must be less than or equal to 1000, preserving existing rules and
using supported operations without generated code.

POST /api/copilot/suggest, mode=llm, returned:
- provider=bedrock, mode=llm, profile_id=7, approval_required=true;
- name=demo_amount_reasonable, rule=less_than_or_equal, column=amount,
  severity=warning, value=1000;
- transformations=[];
- a validated full contract and signed approval token.

After suggestion, the active contract was still #2, revision 2.
Suggestion therefore did not persist a configuration change.

POST /api/copilot/approve with that token and approved=true returned:
contract_id=5, revision=3, status=active, created=true.

POST /api/pipelines/trigger then used contract_id=5, datasets=["orders"],
gold=["orders_by_status"], stages=["bronze","profiling","silver","gold","certification"],
and certification="evaluate".

Airflow run manual__2026-10-26T15:18:52.574151+00:00 completed SUCCESS.
It resolved contract_id=5 and contract_path=db://configuration_contract/5.
resolve_plan, dataset_targets, gold_targets, start_run, dataset.bronze,
dataset.profiling, dataset.silver, gold, certification and finalize succeeded.

Silver quality run #76 persisted result #137:
demo_amount_reasonable, less_than_or_equal, amount, warning, pass,
failed_rows=0, failure_percentage=0, gx_success=true.

This validates natural-language intent → Bedrock → validated configuration →
human approval → persisted revision → Airflow → Silver quality evaluation.

## Real browser workflow (handoff)

The browser selected ci-retail / ci-retail-e2e / ci-retail-csv, dataset orders,
provider Real LLM — Amazon Bedrock.

Requirement:
"Add a new warning quality rule named demo_ui_amount_limit_lower for the amount column.
Values must be less than or equal to 400.
Do not remove or modify existing rules or transformations.
Use only supported DataForge operations."

The UI displayed Review proposal — bedrock, profiling #10, and the rule
demo_ui_amount_limit_lower / less_than_or_equal / amount / warning / value=400.
After checking explicit review approval and clicking Approve and save revision,
the UI reported Saved contract #7, revision 5.

Pipelines & Runs displayed contract #7 rev 5 for the same source.
Run Full Pipeline completed with Live Airflow State SUCCESS, every displayed
task successful, and durable orchestration run #7: success, 5/5 tasks, 0 failed.

## Independent continuation check: 2026-10-26

GET http://localhost:8001/api/datasets/orders/quality-rules?client_code=ci-retail&project_code=ci-retail-e2e&source_code=ci-retail-csv

The live API returned:
- quality_result_id=152;
- run_id=84;
- name=demo_ui_amount_limit_lower;
- rule_type=less_than_or_equal;
- column=amount;
- severity=warning;
- status=pass;
- failed_rows=0;
- failure_percentage=0.0;
- gx_success=true;
- evaluated_at=2026-10-26T16:04:07.966827Z.

The same response retained existing critical-rule failures and the email warning.
The new passing warning rule does not imply that all dataset quality rules pass.

## Reproducible demo

1. Use an environment with requirements-dev.txt installed and the existing
   local services configured; do not overwrite an existing .env.
2. Verify migrations and /api/ready. In the API process set AWS_DEFAULT_REGION,
   DATAFORGE_COPILOT_MODEL_ID and credentials through the approved environment
   credential mechanism. Set a shared DATAFORGE_COPILOT_SIGNING_KEY of at least
   32 random characters when using multiple workers.
3. Start the API on port 8001 and point the frontend API proxy at that port.
   The current Compose API environment does not automatically forward copilot
   variables; pass them explicitly when using the containerized API.
4. Select the existing ci-retail source and orders dataset.
   Olist metadata currently has no active configuration_contract, so it correctly
   requires onboarding before Copilot use.
5. Generate a new, uniquely named warning amount limit, inspect the structured
   proposal and full contract, explicitly approve and save the revision.
6. Trigger a pipeline separately using the saved revision; inspect Airflow,
   Quality, Quarantine, Assets, Lineage and Certification.

Fallback must be explicitly selected as Deterministic fallback. It only proposes
not_null candidates from declared non-nullable columns, does not interpret natural
language and is not an LLM demonstration. Provider errors do not silently enable it.

## Guardrails and deployment limits

The LLM proposes only supported quality rules and Silver transformations.
All proposals pass strict schema and reference validation before approval.
It cannot generate executable Python/SQL/shell, change source identity or
connections, or trigger pipelines during approval.

Signed review tokens expire after 15 minutes and bind the proposed contract to
the current base. Approval rechecks concurrency under the existing transactional
source lock. Altered, expired and stale tokens are rejected.

Only the target dataset configuration/schema and profiling summaries are sent,
not raw data samples, credentials or other-source contracts.
Approval retains the application's existing authentication model; it is a review
confirmation, not a new per-user authorization system.

The Bedrock demo validates external LLM invocation with the local data platform.
It does not satisfy #28 cloud hosting or #29 final multi-source cloud validation.
After the demo, deactivate/delete the temporary access key and reduce the demo
principal's permissions to the required model invocation scope.

## Implementation files (13)

- .env.example
- docs/sprint-2/llm-copilot.md
- docs/evidence/copilot-verification.md
- frontend/src/services/api.js
- frontend/src/views/CopilotView.jsx
- frontend/tests/copilot.test.js
- frontend/tests/copilot-view.test.js
- src/api/control_plane.py
- src/api/main.py
- src/copilot/__init__.py
- src/copilot/service.py
- tests/test_api_control_plane.py
- tests/test_copilot.py

No pipeline-engine changes, migrations or new dependencies are introduced by #26.
Do not transfer .env, logs, credentials, caches or temporary files.

## Regression repeated in the continuation session

On 2026-10-26, in the Work checkout using the primary checkout's existing Python
virtual environment (with bytecode writes disabled):
- unittest discovery: 348 tests, OK, 35 skipped;
- Ruff: All checks passed;
- git diff --check: passed.

Frontend rerun: 8 tests passed; two test files could not load because esbuild
reported Access is denied while scanning an ancestor directory. The Vite build
was also blocked while resolving vite.config.js with the same directory access
error. These reruns did not reproduce the historical frontend success and must
be repeated from the user's unrestricted PowerShell session before merge.

The primary checkout was clean on develop at 2c99ddb when inspected.
git fetch origin was blocked by permission denied writing .git/FETCH_HEAD.
No files were transferred to that checkout and no commit/push/merge was made.

## Final verification in the primary checkout — 2026-10-26

Branch: feature/26-llm-copilot.

- Python: 348 tests, OK; 35 skipped, 313 executed successfully.
  Integration tests were disabled with DATAFORGE_INTEGRATION=0.
- Ruff and git diff --check passed.
- npm ci completed; frontend tests: 12 passed, 0 failed.
- Vite production build passed.
- Earlier frontend installation locks were resolved by stopping the
  existing DataForge Vite/esbuild processes.

Primary-checkout API on port 8002 reported READY.
Bedrock returned a real proposal using profiling #11:
demo_main_repo_amount_limit, amount <= 500, severity warning.
Explicit approval persisted active contract #8, revision 6.

Airflow run:
manual__2026-10-26T17:10:38.068392+00:00

The API confirmed state=success, all tasks successful,
end_date=2026-10-26T17:12:24.777626Z.
The resolved configuration was db://configuration_contract/8.

The quality API returned result #161, Silver run #88:
demo_main_repo_amount_limit, less_than_or_equal, amount,
warning, pass, failed_rows=0, failure_percentage=0,
gx_success=true.

This supersedes the earlier pending primary-checkout regression and
frontend rerun notes. PR, CI review and merge remain pending.
