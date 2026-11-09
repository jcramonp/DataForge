# Infrastructure monitoring and notification runbook

Terraform source: `infra/academy/monitoring.tf` and `notifications.tf`.
These resources monitor EC2 status, EC2 CPU and RDS free storage, with alarm
and recovery actions targeting the dedicated SNS topic. Existing RedshiftSNS
is not used or modified.

## Private configuration

The required `alert_email` variable is sensitive in Terraform output, but its
value is still stored in state and saved plans. Keep the recipient file, state
and plans private and outside Git. Sensitivity is display redaction, not encryption.
Do not commit a tfvars file containing the recipient.

From CloudShell/Bash, create the private variable file outside the checkout:

```bash
(
set -euo pipefail
umask 077
IFS= read -r -p "Notification email: " DATAFORGE_ALERT_EMAIL </dev/tty
export DATAFORGE_ALERT_EMAIL
python3 - <<'PY'
import json
import os
from pathlib import Path
Path.home().joinpath("dataforge-alerts.tfvars.json").write_text(
    json.dumps({"alert_email": os.environ["DATAFORGE_ALERT_EMAIL"].strip()})
)
PY
)
```

For every plan now include this file, even when reviewing another infrastructure
change. From `infra/academy` (or the existing state directory in CloudShell):

```bash
terraform fmt -check
terraform validate
terraform plan -var='operator_cidr=192.0.2.1/32' \
  -var-file="$HOME/dataforge-alerts.tfvars.json" -out=monitoring.tfplan
terraform apply monitoring.tfplan
```

Review additions, updates and deletions before applying. Keep using the existing
state for the deployed environment. The live deployment was incremental; a fresh
deployment includes the six monitoring/SNS resources in addition to the base
infrastructure. After apply, open the AWS email for the DataForge topic and click
Confirm subscription. Terraform completion alone does not demonstrate email
confirmation or delivery. Confirm PendingConfirmation=false in SNS.

All alarms treat missing metrics as missing, not as healthy. They can show
INSUFFICIENT_DATA during initialization or when metrics stop arriving. These
alarms do not replace an application availability check.

## Controlled notification test

Only after the intended recipient has confirmed, explicitly run the following
manual test in the demo account:

```bash
aws cloudwatch set-alarm-state --region us-east-1 \
  --alarm-name dataforge-academy-ec2_status --state-value ALARM \
  --state-reason "PRUEBA CONTROLADA DataForge: verificar entrega CloudWatch-SNS-correo; no representa un fallo real."
aws cloudwatch describe-alarm-history --region us-east-1 \
  --alarm-name dataforge-academy-ec2_status --history-item-type Action \
  --max-records 5 --query 'AlarmHistoryItems[].[Timestamp,HistorySummary]' --output table
aws cloudwatch describe-alarms --region us-east-1 \
  --alarm-name-prefix dataforge-academy- \
  --query 'MetricAlarms[].[AlarmName,StateValue,StateReason]' --output table
```

Record successful SNS action execution and independently confirm email receipt.
Wait for CloudWatch to reevaluate real metrics and return ec2_status to OK.
Do not manually force OK and call that automatic recovery. If ALARM persists,
inspect EC2 health and recent datapoints; if INSUFFICIENT_DATA persists, inspect
whether the instance is running and whether metrics are available. This test
does not stop EC2, corrupt data or reproduce a real incident.

The topic policy permits cloudwatch.amazonaws.com to publish only from the
account and DataForge-prefixed alarm ARNs. No IAM role or Academy SCP is changed.

## Reference cost and evidence

Reference standard-resolution alarm rate in US East: USD 0.10 per alarm-metric
per month, so three single-metric alarms are USD 0.30/month before free allowances,
prorated by hours. SNS reference email delivery is USD 2/100000 and standard
requests USD 0.50/million before allowances; actual charges depend on usage and
the account. EC2/RDS/EBS charges remain separate. No paid custom metric, detailed
EC2 monitoring or custom CloudWatch dashboard was enabled by these files.

Pricing references:
- https://aws.amazon.com/cloudwatch/pricing/
- https://aws.amazon.com/sns/faqs/

See [live alert evidence](../evidence/aws-monitoring-verification.md). Application
health checks, log shipping and pipeline/quality alerts remain pending.
