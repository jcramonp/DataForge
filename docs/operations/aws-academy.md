# AWS Academy deployment

This is the deployment used for the final DataForge demonstration in `us-east-1`.
It complements the local Compose installation. The deployed account is
`919774751018`; the runtime start script and Gold check currently target that
specific account and demonstration dataset.

## Architecture and access

| Component | Implementation |
| --- | --- |
| Application | One EC2 t3.medium, Amazon Linux 2023, Docker Compose |
| Web | React production build served by Nginx; `/api/` proxies to FastAPI |
| Orchestration | Airflow API server, scheduler and DAG processor on EC2 |
| Airflow metadata | PostgreSQL container, persistent Docker volume on EBS |
| DataForge metadata | Private, encrypted RDS PostgreSQL 16, db.t4g.micro |
| Objects | Five private S3 buckets: input, bronze, silver, gold, quarantine |
| Credentials | EC2 LabInstanceProfile; RDS managed secret in Secrets Manager |
| Operator access | Systems Manager port forwarding to loopback port 8081 |

The public subnet has an Internet Gateway route and a public EC2 address for
outbound AWS/API/package access. RDS uses two private subnets and accepts port
5432 only from the application security group. This is a single-host demo,
without a load balancer, NAT Gateway or high availability. S3 holds data files;
RDS holds contracts, run records, quality evaluations, asset metadata and lineage.

The host exposes the web container only at `127.0.0.1:8081`. The Terraform ingress
rule for port 443 does not configure HTTPS or publish the application. The
existing plan used `operator_cidr=192.0.2.1/32` as an inactive placeholder.
An SSM tunnel provides access without opening application ports publicly.

## Provisioning

Use an active Academy session with AWS CLI credentials. Confirm the account
with `aws sts get-caller-identity`; never commit those temporary credentials.
The Academy role must permit EC2, VPC, RDS managed secrets, S3 and SSM operations.
`LabInstanceProfile` must already exist. Terraform does not create IAM roles.

First create the private notification variable file described in the
[monitoring runbook](aws-monitoring.md). It supplies the required alert_email.

Use Terraform 1.12.2 or later below 2.0, AWS CLI, Bash and Docker Compose 2.30+
(the bootstrap installs Compose 2.32.4). Run Terraform from Bash/CloudShell:

```bash
cd infra/academy
terraform init -lockfile=readonly
terraform fmt -check
terraform validate
terraform plan -var='operator_cidr=192.0.2.1/32' \
  -var-file="$HOME/dataforge-alerts.tfvars.json" -out=deploy.tfplan
terraform apply deploy.tfplan
terraform output
```

Review the plan and available credit before applying. These resources are
billable; no dollar estimate is established by this guide. Preserve the existing
Terraform state when managing the existing environment. Running a fresh state
against that account is not a way to adopt already-created EC2/RDS resources.
Keep state and private backups out of Git.

`bootstrap.sh` installs Docker, enables Docker and SSM, verifies the Compose
download checksum and prepares `/opt/dataforge`. Check that the instance is
Online in SSM before installing the application.

## Install application code and start services

From a clean checkout, package the source without runtime secrets or state:

```bash
git archive --format=tar.gz HEAD > /tmp/dataforge-app.tar.gz
aws s3 cp /tmp/dataforge-app.tar.gz \
  s3://dataforge-academy-919774751018-input/deployment/dataforge-app.tar.gz \
  --region us-east-1
sha256sum /tmp/dataforge-app.tar.gz
```

Open an SSM shell to the instance ID from Terraform:

```bash
aws ssm start-session --region us-east-1 --target INSTANCE_ID
```

On EC2, copy the archive to `/opt/dataforge-app.tar.gz`, verify the SHA-256 against
the value printed by the sender, then extract and run:

```bash
sudo install -d -m 0750 /opt/dataforge
sudo aws s3 cp \
  s3://dataforge-academy-919774751018-input/deployment/dataforge-app.tar.gz \
  /opt/dataforge-app.tar.gz --region us-east-1
# Before extraction: compare sha256sum output with the sender's digest.
sudo sha256sum /opt/dataforge-app.tar.gz
sudo tar -xzf /opt/dataforge-app.tar.gz -C /opt/dataforge
sudo bash /opt/dataforge/scripts/aws/start.sh
```

The start script obtains the RDS username/password from Secrets Manager and
generates persistent internal Airflow/signing secrets. It creates mode-600
`.env.aws`, `.env.compose` and `.internal-secrets.json` on EC2. It reuses internal
secrets on later starts. Compose loads `.env.aws` in raw format so dollar signs
in managed passwords are preserved. The script validates Compose, builds images,
applies metadata migrations and starts services. It does not register sources.
Do not print full `docker compose config` output, copy secrets into the source
archive, or delete the internal secret file when restarting an existing stack.

For long builds use a detached host job, as in the verified deployment:

```bash
sudo systemd-run --unit=dataforge-deploy --collect \
  /bin/bash /opt/dataforge/scripts/aws/start.sh
sudo journalctl -u dataforge-deploy --no-pager -n 80
cd /opt/dataforge
sudo docker compose --env-file .env.compose -f compose.aws.yml ps -a
```

`migrate` and `airflow-init` are expected to exit with code 0. Long-running API,
web and Airflow services must remain running. Unit success only confirms that
the startup command completed; verify health and execute a pipeline separately.

## Open the application and run a contract

On the operator's computer install AWS CLI and the Session Manager plugin, and
configure an Academy profile privately. Keep the following process running:

```powershell
aws ssm start-session `
  --profile dataforge-lab `
  --region us-east-1 `
  --target INSTANCE_ID `
  --document-name AWS-StartPortForwardingSession `
  --parameters 'portNumber=8081,localPortNumber=8081'
```

Open `http://localhost:8081`. That URL works on the computer running the tunnel;
it is not a public URL for the professor. Check `/api/health` and `/api/ready`.
Register a contract in Source Onboarding, select its persisted revision in
Pipelines & Runs and run it. Source credentials, if required, must remain private.

The verified demo contract uses JSONPlaceholder `/todos`, dataset `tareas`,
integer `userId` and `id`, string `title`, boolean `completed`, primary key `id`,
critical rule `userId <= 8`, warning rule `title not_null`, and Gold grouping
by `userId` with `count(id)` aliased to `total_tareas`. The complete registered
contract export is still pending; this description is not a substitute for it.

Review Data Assets, Quality & Quarantine and Lineage & Governance. Certification
is a persisted governance transition, separate from Silver row validation. The
demo's manual transitions were draft -> validated -> certified for both datasets.

To repeat the exact Gold file check, submit `scripts/aws/check-gold.ssm.json`
as the `--parameters file://...` argument of `aws ssm send-command` with document
`AWS-RunShellScript` and the target instance ID. Inspect the command invocation's
Status, StandardOutputContent and StandardErrorContent. This check is fixed to
the verified account, key and expected counts; update it for another contract.

## Academy S3 restriction

The lab SCP denies `s3:GetBucketObjectLockConfiguration`. The AWS provider's
ordinary bucket read requested that action after creation. The deployed solution
therefore uses `terraform_data.bucket` and `bucket.sh` for bucket creation,
ownership checks and tagging, with ordinary Terraform public-access-block
resources. This does not change the SCP or grant broader permissions.

The helper refuses a different account or bucket prefix and never empties a
bucket. AWS rejects deletion when objects remain. Unlike `aws_s3_bucket`, this
logical resource does not automatically detect missing buckets or tag drift on
every plan. Check actual buckets explicitly. The original state repair used
state removal only for the five bucket records, preserving the physical buckets;
do not repeat that repair on the working state.

## Persistence, costs and remaining work

Keep an external private backup of Terraform state and runtime recovery material.
The public source package intentionally excludes them. S3, RDS and EBS have
separate lifecycles; stopping compute is not deleting storage or eliminating all
charges. Destruction skips an RDS final snapshot and the EC2 root disk is deleted
on termination, so back up required data before any teardown. Do not destroy the
verified environment to test this guide before the demonstration.

This change versions the verified deployment. Infrastructure alarms and email delivery are verified in the
[monitoring evidence](../evidence/aws-monitoring-verification.md). CI/CD automatic
deployment, application health monitoring, a public authenticated URL, cloud Copilot access, a complete demo
contract export and the final report remain separate pending work. This guide
has not been re-executed from an empty account; evidence records the actual
manual deployment and live checks already performed.
