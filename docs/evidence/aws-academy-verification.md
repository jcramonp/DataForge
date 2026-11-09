# AWS Academy live verification — 2026-11-08

Evidence source: command output and application screenshots supplied by the
operator during deployment. These checks ran in AWS, not in the editor's local
environment. This document does not claim a new deployment or regression run.

- Account: `919774751018`; region: `us-east-1`.
- EC2: `i-02ce56fe4c428d16a`, SSM Online.
- RDS: `dataforge-academy`, private PostgreSQL metadata database.
- Five S3 buckets: `dataforge-academy-919774751018-{input,bronze,silver,gold,quarantine}`.
- Terraform repair apply: 10 added, 0 changed, 0 destroyed. Subsequent plan:
  `No changes. Your infrastructure matches the configuration.`
- Deployment command completed successfully; API and Airflow PostgreSQL healthy,
  web and Airflow services running; migration/init services exited with code 0.
- Local Windows SSM tunnel accepted a connection; the application displayed
  FastAPI Connected. No public application endpoint was demonstrated.

## Pipeline and quality

Scope: `demo-aws / entrega-final / tareas-rest`; persisted contract #1, revision 1.
Airflow DAG: `dataforge_pipeline`.
External run: `manual__2026-11-08T22:54:02.430110+00:00`.
Orchestration #1: SUCCESS, 5 processing tasks succeeded, 0 failed, 0 retries,
recorded duration 25.16 seconds. Airflow technical tasks also displayed success.

| Asset | Layer | Rows | Observed result |
| --- | --- | ---: | --- |
| #1 | Bronze | 200 | Tasks received from REST API |
| #2 | Validated Silver | 160 | Rows passing critical rules |
| #3 | Quarantine | 40 | userId 9 or 10 violates userId <= 8 |
| #4 | Gold | 8 | Task count grouped by accepted user |

Silver processing run #3 persisted two quality results: critical
`demo_user_id_limit` failed for 40/200 rows (20%), and warning `titulo_presente`
passed with zero failed rows. Pipeline SUCCESS means processing and quarantine
routing completed; it does not mean every input row passed every quality rule.

Screenshots displayed lineage asset #1 -> #2 (`validated_from`), #1 -> #3
(`quarantined_from`) and #2 -> #4 (`derived_from`). The UI showed Gold certified
and the input dataset validated; the operator subsequently confirmed both
datasets certified. Certification completion is operator-confirmed, without a
fresh database query in this evidence.

## Actual Gold object read

Object: `s3://dataforge-academy-919774751018-gold/demo-aws/entrega-final/tareas_por_usuario/gold_v1/tareas_por_usuario.parquet`.

The operator ran the SSM payload now preserved at
`scripts/aws/check-gold.ssm.json`. It executed Python in the API container, read
the actual S3 object with boto3 and decoded Parquet with pandas. Assertions
checked exactly 8 rows, users 1 through 8, 20 tasks per user and sum 160.
The command returned Status Success, empty Error and this output:

```text
CONTENIDO REAL DE GOLD
 userId  total_tareas
      1            20
      2            20
      3            20
      4            20
      5            20
      6            20
      7            20
      8            20
VERIFICACION CORRECTA: 8 usuarios, 20 tareas cada uno, total 160.
```

This verifies the materialized Gold file. It does not demonstrate a separate
business-facing consumption API/dashboard, automatic deployment, alert delivery
or Bedrock access from Academy. Those remain pending.
