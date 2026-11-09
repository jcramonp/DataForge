# Groq Copilot live verification — 2026-11-09

The operator supplied screenshots of the deployed application, full validated
contract, persisted revision, Airflow run, quality results and asset catalog.
The real-provider selector reported `Review proposal — groq`. No API key was
shared in the evidence.

The initial proposal was rejected for duplicate rule names; no change was saved.
An additions-only request then produced exactly one warning rule:
`groq_demo_id_max_200_v2`, `less_than_or_equal`, column `id`, value `200`,
mostly `1`, allow_null `false`. Transformations were empty. The combined
contract retained `demo_user_id_limit` (critical userId <= 8),
`titulo_presente` (warning not-null title), the REST source and Gold aggregation.

The operator approved saving contract #2, revision 2, then explicitly triggered
the full pipeline. DAG `dataforge_pipeline` run
`manual__2026-11-09T06:54:42.859522+00:00` succeeded. The persisted orchestration
history #2 reported five successful tasks, no failures/retries and 21.54 seconds.
All ten displayed Airflow task nodes were successful (a different task count
from the five processing tasks in the durable control-plane history).

Silver processing run #7 evaluated three rules: the original critical rule
failed for 40 rows (20%), while title presence and the new Groq rule passed
with zero failed rows. The quarantine inspector showed 40 isolated records,
IDs 161–200, userId 9 or 10. This is the intended quality partition.

The latest S3-backed Parquet assets registered in the catalog were:

| Asset | Layer | Rows |
|---|---|---:|
| #5 | Bronze | 200 |
| #6 | Validated Silver | 160 |
| #7 | Quarantine | 40 |
| #8 | Gold | 8 |

This verifies real Groq proposal generation, server validation, explicit human
approval, persisted configuration and downstream execution. These counts are
observed catalog results. Gold #8 was subsequently read through the consumption
API and web view, with verified checksum and eight users with 20 tasks each;
see [Gold consumption evidence](aws-gold-consumption-verification.md).
Bedrock remains unavailable to the tested Academy role;
Groq is an external provider, not an AWS Bedrock deployment. GitHub-hosted CI is
still blocked by the separate account billing issue.
