# Runtime configuration and cloud permissions

DataForge runs the **same code** in every environment. Environment differences live only in environment variables, read by `src/common/settings.py`; storage and database clients are created by `src/common/clients.py`. There is no `if environment == ...` business logic in pipeline stages.

## Environments

| `DATAFORGE_ENV` | Used for | Object storage | Control plane | Variables come from |
|---|---|---|---|---|
| `local` (default) | Development on a laptop | MinIO container | PostgreSQL container | `.env` (copy of `.env.example`) |
| `test` | CI and local integration tests | Disposable MinIO | Disposable PostgreSQL | `config/environments/test.env` |
| `aws` | AWS reference deployment (#28) | Amazon S3 | Amazon RDS PostgreSQL | Task/container environment + AWS Secrets Manager; template `config/environments/aws.env.example` |

### How variables are loaded

1. Variables already in the process environment always win (container, ECS task, Airflow).
2. Otherwise the file named by `DATAFORGE_ENV_FILE` is loaded, falling back to the repository `.env`.
3. `python -m src.ops.health` (and `GET /api/ready`) reports every missing/invalid value at once.

## Variable reference

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DATAFORGE_ENV` | no | `local` | `local`, `test` or `aws` |
| `DATAFORGE_ENV_FILE` | no | `.env` | Alternative dotenv file |
| `DATAFORGE_LOG_LEVEL` | no | `INFO` | Standard logging levels |
| `DATAFORGE_LOG_FORMAT` | no | `text` locally, `json` elsewhere | See [`observability.md`](observability.md) |
| `POSTGRES_HOST`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | yes | — | Control-plane database |
| `POSTGRES_PORT` | no | `5432` | |
| `POSTGRES_SSLMODE` | no | — | Set `require` (or `verify-full`) on RDS |
| `POSTGRES_CONNECT_TIMEOUT` | no | `5` | Seconds; keeps readiness checks fast |
| `MINIO_ENDPOINT` / `DATAFORGE_STORAGE_ENDPOINT` | local/test | — | S3-compatible endpoint. **Leave unset on AWS** to use Amazon S3 |
| `MINIO_ROOT_USER` / `DATAFORGE_STORAGE_ACCESS_KEY_ID` | local/test | — | Static keys for MinIO. **Leave unset on AWS** (IAM role) |
| `MINIO_ROOT_PASSWORD` / `DATAFORGE_STORAGE_SECRET_ACCESS_KEY` | local/test | — | |
| `AWS_REGION` / `AWS_DEFAULT_REGION` | no | `us-east-1` | |
| `MINIO_BUCKET_BRONZE`, `_SILVER`, `_QUARANTINE`, `_GOLD` | no | `dataforge-<layer>` | Bucket per layer, on MinIO or S3 |
| `DATAFORGE_CONNECTION_<REF>` | per source | — | JSON credentials for a contract `connection_reference` (`src/connectors/credentials.py`) |

The `MINIO_*` names are kept for backwards compatibility with Sprint 1; they configure any S3-compatible store.

## Secrets handling

- Contracts never contain credentials, only a `connection_reference`; the secret is resolved at runtime from `DATAFORGE_CONNECTION_<REF>`.
- `.env` and `.env.*` are git-ignored; only `.env.example`, `config/environments/test.env` (throwaway CI values) and `config/environments/aws.env.example` (placeholders) are committed.
- In `aws`, readiness fails if a `change_me` placeholder is used as a password or if storage points at `localhost`.
- On AWS, inject `POSTGRES_PASSWORD` and every `DATAFORGE_CONNECTION_*` value from **Secrets Manager** (or SSM SecureString) through the ECS task definition `secrets` field; never bake them into images.
- Structured logs redact any field whose name contains `password`, `secret`, `token`, `authorization` or `api_key`. Do not log raw connection payloads.

## AWS permissions (least privilege)

Use separate IAM roles per service. Replace `<prefix>`, `<region>`, `<account>` and resource names.

### API / pipeline task role (runtime)

Used by the FastAPI container and the pipeline workers/Airflow. It needs object access to the four layer buckets only:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListLayerBuckets",
      "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": [
        "arn:aws:s3:::<prefix>-dataforge-bronze",
        "arn:aws:s3:::<prefix>-dataforge-silver",
        "arn:aws:s3:::<prefix>-dataforge-quarantine",
        "arn:aws:s3:::<prefix>-dataforge-gold"
      ]
    },
    {
      "Sid": "ReadWriteLayerObjects",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": [
        "arn:aws:s3:::<prefix>-dataforge-bronze/*",
        "arn:aws:s3:::<prefix>-dataforge-silver/*",
        "arn:aws:s3:::<prefix>-dataforge-quarantine/*",
        "arn:aws:s3:::<prefix>-dataforge-gold/*"
      ]
    }
  ]
}
```

- `s3:ListBucket` is what makes `HeadBucket` (readiness) and `HeadObject` work.
- No `s3:DeleteObject`: pipelines are append-only and asset keys are content-addressed (`source_checksum=...`). Add it only for an explicit retention job.
- The LLM copilot (#26) additionally needs `bedrock:InvokeModel` on the specific model ARN, attached to the API role only.

### Task execution role (ECS agent)

`AmazonECSTaskExecutionRolePolicy` (pull from ECR, write CloudWatch Logs) plus `secretsmanager:GetSecretValue` on the DataForge secrets only (e.g. `arn:aws:secretsmanager:<region>:<account>:secret:dataforge/*`).

### Database access

- RDS lives in private subnets, `PubliclyAccessible=false`.
- Its security group accepts `5432` only from the API/pipeline security groups.
- The application uses a dedicated `dataforge_app` role; the master user is reserved for migrations/administration.
- `POSTGRES_SSLMODE=require`.

### CI/CD deploy role (for #28)

When CI starts deploying, use GitHub OIDC (`token.actions.githubusercontent.com`) with a role restricted to `repo:jcramonp/DataForge:ref:refs/heads/main`, limited to `ecr:*Push*`/`ecr:GetAuthorizationToken` on the DataForge repository and `ecs:UpdateService`/`ecs:RegisterTaskDefinition` + `iam:PassRole` on the DataForge task roles. No long-lived AWS keys in GitHub secrets.

### Network baseline

- Only the load balancer (HTTPS) and the static frontend are public.
- API and pipeline tasks run in private subnets and reach S3 through a VPC gateway endpoint.
- Load balancer target health uses `GET /api/ready`; container health uses `GET /api/health`.
