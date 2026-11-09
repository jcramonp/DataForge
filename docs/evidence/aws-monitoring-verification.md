# AWS infrastructure alerts verification

Evidence source: operator-provided AWS CLI output and explicit confirmation of
email receipt during the live Academy deployment. No AWS credentials were used
by the editor. Account: `919774751018`; region: `us-east-1`.

## Provisioning observed

- Terraform validation passed for monitoring.tf.
- First plan/apply: 3 added, 0 changed, 0 destroyed (CloudWatch alarms).
- Terraform validation passed for notifications.tf.
- Second plan/apply: 3 added, 3 changed, 0 destroyed (SNS topic, policy,
  email subscription; alarm/OK actions connected on the three alarms).
- Topic: `arn:aws:sns:us-east-1:919774751018:dataforge-academy-alerts`.
- Subscription PendingConfirmation changed from true to false after operator
  confirmation. The actual email is intentionally omitted from source control.

| Alarm | Metric | Condition |
| --- | --- | --- |
| dataforge-academy-ec2_status | AWS/EC2 StatusCheckFailed, Maximum | >=1 for 2 consecutive 60-second periods |
| dataforge-academy-ec2_cpu | AWS/EC2 CPUUtilization, Average | >80% for 3 consecutive 300-second periods |
| dataforge-academy-rds_storage | AWS/RDS FreeStorageSpace, Minimum | <2147483648 bytes for 3 consecutive 300-second periods |

## Notification and recovery observed

The operator used SetAlarmState to move only `ec2_status` to ALARM with reason:

```text
PRUEBA CONTROLADA DataForge: verificar entrega CloudWatch-SNS-correo; no representa un fallo real.
```

CloudWatch alarm action history recorded at `2026-11-09T04:08:48.600000+00:00`:

```text
Successfully executed action arn:aws:sns:us-east-1:919774751018:dataforge-academy-alerts
```

The operator explicitly confirmed receipt of the alarm email. A later
DescribeAlarms query showed all three alarms OK. The ec2_status reason showed
two real zero-valued status-check datapoints at 04:07 and 04:08 UTC, proving
automatic reevaluation after the manual test. The operator did not manually set
the alarm back to OK. CPU averages were approximately 6.16–6.27%, and RDS free
storage approximately 18.38 billion bytes, both below/above their respective
alarm thresholds.

This validates alarm action -> SNS -> email, plus automatic recovery using real
metrics. It does not prove detection of a real infrastructure incident: the
initial ALARM state was injected. Recovery email receipt was not separately
confirmed. API readiness, pipeline failures, application log aggregation and
business-data quality alerts are not covered by these infrastructure alarms.

## Separate CI limitation

GitHub Actions run `42543250904` could not start its jobs because the account was
locked due to a billing issue. No CI pass is claimed for this change. This
blockage is independent of the successful live AWS alarm test.
