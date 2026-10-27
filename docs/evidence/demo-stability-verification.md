# Sprint 2 live demo verification - 2026-10-26

## Observed product behavior before the stability patch

- REST source: `demo-profesor / multifuente / tareas-rest`, dataset `tareas`.
  Onboarding persisted contract #9 revision 1. Bedrock proposal based on
  profiling #14 was approved as contract #10 revision 2.
  Orchestration #11 completed successfully; Silver run #98 evaluated
  `demo_user_id_limit` (`userId <= 8`, critical).
  Bronze asset #93 contains 200 rows; Silver #94 contains 160;
  quarantine #95 contains 40 rows (userId 9 and 10).
  Quality result #162 records 40 failures, 20 percent.
- CSV source: `demo-profesor / multifuente / ventas-csv`, dataset `ventas`.
  The user created `data/demo/ventas_demo.csv` with six rows.
  Initial contract #11 revision 1 completed orchestration #12 and profiling #16.
  Two approved Bedrock rules require `cantidad > 0` and `precio > 0`.
  Contract #12 revision 2 completed orchestration #13 in 24.375 seconds.
  Silver run #104 evaluated quality results #163 and #164.
  Bronze #98 contains 6 rows; Silver #99 contains 4; quarantine #100 contains 2.
  Sale 4 has quantity 0; sale 5 has price -3000.
- Both new datasets reached `certified` via separate frontend transitions
  from draft to validated and from validated to certified. API history confirms
  these transitions. Certification policy permits critical input violations
  when the quality gate successfully isolates the rejected records.
- Existing retail Gold dataset `orders_by_status`: asset #88 contains 3 rows,
  Gold run #89 succeeded, lineage links Silver #86 to Gold #88 (`derived_from`).
  Both retail datasets are certified.

## Problems and fixes

1. A live Airflow status request returned service unavailable while the accepted
   run continued successfully. The user submitted another execution. Both runs
   succeeded. The frontend now retries temporary status errors, preserves the
   accepted run, prevents another trigger for that selection while its outcome
   remains unresolved, and uses Refresh to inspect the same run.
   This guard applies to the mounted view; it is not server-side idempotency
   or persistence across browser reloads.
2. A valid natural-language Copilot requirement received a generic 422 rejection.
   The original rejected model output was not retained, so its exact validation
   cause is unconfirmed. An explicit supported configuration produced the expected
   proposal. New safe diagnostics distinguish invalid JSON, unsupported fields or
   enum values, invalid parameters, duplicate rule names and contract conflicts.
   The provider instruction now explains comparison fields and exact column case.
   No provider retry, automatic approval or silent fallback was introduced.

## Validation of the patch in an isolated checkout

- 25 Python tests passed (`tests.test_copilot`, `tests.test_api_control_plane`).
- Ruff passed for the three changed Python files.
- Three new monitor tests passed: transient recovery using one run ID,
  exhausted monitoring without a fabricated failed status, and terminal/permanent
  error handling.
- Frontend test run: 11 passed; two existing esbuild render-test files could not
  run because the restricted Windows subprocess cannot read a parent directory.
  These are unresolved environment failures, not a fully passing frontend suite.
- Vite production build passed using `--configLoader native`.

Application to the primary checkout, frontend render-test rerun, live UI smoke
test after application, commit, push, PR and CI remain pending.
AWS deployment, final Olist/PostgreSQL regression and issue acceptance review
are outside the completed validation described here.

## Primary checkout verification — 2026-10-26

Supersedes the pending primary-checkout test notes above.

- Patch applied to fix/sprint2-demo-stability.
- Python: 25 tests passed.
- Frontend: 15 tests passed, including existing render tests.
- Ruff passed.
- Vite production build passed with --configLoader native.
- API restarted.
- Live CSV orchestration #16 completed successfully using contract #12.
- The user confirmed that the UI displayed SUCCESS automatically.
- Bronze asset #107: 6 rows.
- Silver asset #108: 4 rows.
- Quarantine asset #109: 2 rows.
- Temporary monitoring failures are covered by automated tests;
  no service outage was deliberately introduced in this live run.

Commit, push, PR and CI remain pending.
