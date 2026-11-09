# Reboot and backup evidence — 2026-11-09

The operator verified Docker enabled at EC2 boot and `unless-stopped` restart
policies for web, API, scheduler, DAG processor, Airflow API and Airflow DB.
Initialization and migration containers had exited with code 0 and no restart
policy, as expected for one-time tasks. Airflow DB used the named
`dataforge_airflow_database` volume; scheduler logs used `dataforge_airflow_logs`.

Following `sudo reboot`, `/api/ready` returned HTTP 200 at
2026-11-09T07:36:33.076533+00:00: configuration AWS, PostgreSQL schema 0008,
four processing buckets reachable and two installed example contracts valid.
Gold #8 remained checksum-verified with eight users and 20 tasks each. The web
history retained runs #1 and #2; all six permanent containers were running,
API and Airflow DB healthy.

The operator then executed contract #2 revision 2 again. DAG
`manual__2026-11-09T07:49:08.968002+00:00` succeeded after reboot. Persisted
orchestration #3 reported five successful tasks, no failed tasks/retries and
19.91 seconds. All ten displayed Airflow task nodes succeeded. This is evidence
of post-reboot processing, not empty-environment redeployment or backup restore.

Private backups were produced and downloaded to the operator's Windows PC:

- Terraform state pulled from the active working directory, plus Terraform
  sources/scripts and provider lock: SHA-256
  `953175f11492907579a42affed255c67c6ec6b191ed3b7359d402da5e3c299d6`.
- Custom-format RDS dump: 91,875 bytes; Airflow dump: 188,818 bytes. Each dump's
  table of contents was readable with pg_restore. Both were created using the
  existing PostgreSQL container client; no source DB was restored or replaced.
- Bronze/Silver/Gold/Quarantine objects were copied to the private backup folder.
  Code and runtime configuration, including private environment files, were
  archived with the dumps and object copies. Input deployment objects were not
  copied as a bucket backup. The Terraform archive remains a separate file.
- A first streaming encryption attempt failed to read the interactive password.
  The operator then used a private archive file and standalone OpenSSL commands.
  AES-256-CBC/PBKDF2 with 200,000 iterations encrypted the archive; decrypting a
  verification copy matched the plaintext byte-for-byte and tar could list it.
- The encrypted archive was transferred via the input bucket and downloaded
  outside AWS. Its SHA-256 matched on Windows:
  `1fab8d5764d38245da2b3c985e0f4f3aef8b1e19b0ce7e0a1c683381e0945abd`.

No archive or password is versioned. Dump readability, encryption round-trip
and download integrity were tested. Restoration into isolated databases also
passed; see the results below. These sequential DB/object snapshots do not establish a global
transactionally consistent snapshot under concurrent writes. Private plaintext
staging remains under root-controlled EC2 directories pending cleanup; neither
the plaintext staging nor the passphrase should be shared.

EC2-to-SNS delivery was independently verified using a labeled controlled test.
SNS returned MessageId `c4f2bf55-dee8-5f33-8884-dc3e096c75ac`, and the operator's
email screenshot showed the matching test subject/body. This establishes role
permission and delivery. Subsequent periodic-monitor verification is linked below.

## Isolated database restoration — passed

The operator executed scripts/aws/check_restore.sh against the saved dumps.
Both SHA-256 checks passed; pg_isready reported accepting connections.
pg_restore completed with --exit-on-error in a temporary networkless PostgreSQL
16 container, separate from the running databases. Reported counts:

| Restored database | Table/count |
|---|---|
| DataForge RDS dump | contracts 2; orchestrations 3; assets 12 |
| Airflow dump | dag_runs 3; task_instances 30 |

The script ended with RESTORE_CHECK_PASSED. These are the earlier backup's
counts, not the later live environment containing monitor-test runs #4/#5.
No production database was replaced. This validates actual restoration of both
database dumps, not a full fresh AWS rebuild or S3 object restoration exercise.
The backup predates monitor installation; reinstall the versioned monitor
separately when recovering that snapshot.

Periodic monitor installation, outage/recovery detection and email delivery
were subsequently verified. See aws-application-monitor-verification.md.
