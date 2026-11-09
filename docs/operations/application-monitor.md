# Application and persisted pipeline monitor

The host-side monitor reads `/api/ready` and `/api/runs?limit=200` through
localhost:8081. A systemd timer runs the oneshot service 60 seconds after the
previous check finishes, starting 90 seconds after boot. It uses the EC2 role
and AWS CLI to publish to the existing `dataforge-academy-alerts` SNS topic.
No user AWS keys or Groq key are copied into the monitor configuration.

Two consecutive failed checks produce an application or history-unavailable
alert. A passing check after an acknowledged alert produces a recovery message.
A first successful history read establishes a baseline without alerting on
old failed runs. Thereafter newly observed persisted `failed` orchestrations
produce one grouped alert. Running-to-failed transitions are detected. Critical
quality rejections that successfully enter quarantine are not failed pipelines.

State lives in `/var/lib/dataforge-monitor/state.json` with private permissions
and atomic writes. SNS acknowledgement precedes delivery bookkeeping; a publish
failure leaves that event eligible for retry. Checkpoints after acknowledged
messages avoid resending those when a later channel fails. Delivery is best
effort at-least-once: a crash between SNS acknowledgement and checkpoint can
still cause a duplicate. No exactly-once delivery guarantee is made.

Only the latest 200 persisted runs are examined, with 2,000 recent failure IDs
retained. More than 200 arrivals between checks or missing persisted failure
metadata can escape observation. It does not independently inspect live Airflow
tasks, alert on stuck runs, measure LLM availability or monitor detailed quality
thresholds. The monitor runs on the same EC2 and cannot announce its own host's
shutdown; independent host/dead-man monitoring remains a separate concern.

Install the release built by `python scripts/aws/build_monitor_release.py`:
verify its archive SHA-256, extract into a private root-owned staging directory
and run `bash install.sh` as root. Installation verifies member hashes, backs up
previous monitor files under `/opt/dataforge-deploy-backups`, installs the script,
config and units, enables the timer and runs an initial check. It does not rebuild
or restart application containers. Installation, controlled web-outage/recovery
emails and a new persisted failed-run email were verified live; see
[observed monitor evidence](../evidence/aws-application-monitor-verification.md).

Inspect on EC2:

```bash
sudo systemctl list-timers dataforge-monitor.timer --no-pager
sudo journalctl -u dataforge-monitor.service --no-pager -n 20
sudo systemctl start dataforge-monitor.service
```

Expected successful log: `monitor_check`, ready=true, history_ok=true,
runs_checked matching current persisted history, notifications=0.
`monitor_error` and a failed systemd result indicate an internal/publish failure;
logs reveal only the exception type, not raw API/AWS error payloads.

Explicit delivery test, without changing production monitoring state:

```bash
sudo python3 /usr/local/libexec/dataforge-monitor.py --test-notification
```

The email is labeled PRUEBA CONTROLADA and does not imply a real failure.
Unit tests exercise readiness outage/recovery, malformed/timeout responses,
baseline/deduplication, running-to-failed transitions, grouped alerts, SNS
failure/retry bookkeeping and private atomic state. Live tests used a deliberately
stopped web container and a separate missing-file source. Their expected failures
remain visible in history, labeled as controlled monitoring tests.

Disable/rollback: `sudo systemctl disable --now dataforge-monitor.timer`.
Restore any previous files from the installer's source backup and run
`sudo systemctl daemon-reload` before enabling the timer again. Stopping this
timer does not stop DataForge or remove its persisted state.

The timer is installed by a versioned SSM/manual script; it is not represented
as a Terraform resource. SNS email charges follow actual published messages.
