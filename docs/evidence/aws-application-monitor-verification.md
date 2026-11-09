# Application and pipeline alerts — live verification 2026-11-09

The operator installed the reviewed monitor archive on EC2; all archive and
member hashes passed. `DATAFORGE_MONITOR_INSTALLED` was emitted. At
14:29:35.047895 UTC the first real check reported readiness/history true,
three persisted runs and zero notifications. The enabled timer subsequently
ran at approximately 65-second intervals.

## Controlled web interruption and recovery

The operator stopped only `dataforge-web-1`, with a trap to restart it and an
additional systemd safety-start timer. Three checks were invoked manually
through the same installed systemd service. The periodic timer remained enabled.

| Timestamp UTC | ready | history_ok | Notifications |
|---|---|---|---:|
| 14:35:55.860396 | false | false | 0 |
| 14:35:57.173354 | false | false | 2 |
| 14:35:57.363719 | false | false | 0 |
| 14:36:02.711962 | true | true | 2 |

The first failure was suppressed, the second alerted on application and
history availability, and the third did not duplicate those alerts. After
web restart and successful readiness, two recovery notifications were sent.
The operator explicitly confirmed all four emails arrived. This proves the
two-check threshold, deduplication and recovery paths. Checks were accelerated
manually for this test; the few-second detection time is not the normal timer SLA.
Both channels depended on the same web proxy; this test did not induce a separate
database or S3 outage.

## Failed persisted orchestration

A separate configuration was registered: client `monitor-test`, project
`alertas-controladas`, source `archivo-ausente`, contract #3 revision 1, dataset
`probe_missing_file`. Its CSV path deliberately did not exist. The API-triggered
request selected only Bronze; the demo contract #2 was not modified.

Two distinct runs were ultimately launched, not one duplicated notification:

| Orchestration | External run | Duration | Failed tasks | Retries |
|---|---|---:|---:|---:|
| #4 | manual__2026-11-09T14:48:33.141752+00:00 | 116.65s | 1 | 2 |
| #5 | manual__2026-11-09T14:49:33.840017+00:00 | 115.84s | 1 | 2 |

The second run was triggered from the UI with its full stage selection. Bronze
failed and dependent tasks showed upstream_failed; finalization marked the
orchestration failed. The durable history retained demo runs #1–#3 as success.

The operator supplied an SNS email screenshot whose body identified
`orchestration_run_id=5`, the exact second external run ID, client `monitor-test`
and project `alertas-controladas`. This proves a newly persisted failure was
detected and delivered. No email for #4 was supplied, so separate delivery for
that run is not claimed. These are deliberately induced test failures, not
unexplained failures of the business demonstration. No duplicate-delivery test
for failed runs beyond the local unit tests is claimed.

The email screenshot contains an unsubscribe link and is intentionally not
versioned; only the relevant identifiers and observed result are recorded.

Known scope: the monitor reads recent persisted status on the same EC2 host.
It is not an external availability check and does not cover missing failure
metadata, stuck runs, or quality-threshold alerts. See the operations runbook.
