# Automatic Academy application deployment

## Scope and status

CI run [#35](https://github.com/jcramonp/DataForge/actions/runs/42686987182)
completed all eight jobs successfully on 2026-11-09 for commit
`e819cbabfe2d616c44ebee14f66228ac06b40701`, including the real Airflow DAG test.
The earlier account billing lock is resolved for that run.

The new deployment implementation is pending its first live AWS verification.
Do not present this document as evidence that deployment has already succeeded.

After successful CI, the optional `Deploy web and API (Academy)` job packages
the exact tested head SHA, uploads a private S3 source archive, sends an SSM command
to the existing EC2, waits for completion and checks readiness and the live revision.
All CI jobs explicitly check out that head SHA instead of testing a PR merge SHA
and deploying a different commit. PR checks therefore do not certify the synthetic
merge result; review conflicts and base compatibility before merging.

EC2 builds separate API/web images tagged and labelled with the commit. Builds run
before replacing containers. A failed activation/readiness/revision check attempts
to restore both previous images and the previous Compose override. Recovery is an
attempt, not a guarantee if Docker/EC2 itself fails; inspect the SSM result.

Application scope: API and web only. Airflow services, host source bind mounts,
databases, schema migrations, object data, monitor installation and Terraform are
not deployed by this job. Changes to those require their documented operations
procedures. Do not use this job alone to release incompatible schema/DAG/config changes.
The host's current compose.aws.yml and private .env files supply runtime settings.
Groq credentials remain on EC2; they are not needed in GitHub.

## One-time setup by the repository owner

1. Start the Academy lab, confirm the application EC2 is running and RDS available.
   Check local readiness and ensure no business pipeline or manual deployment is
   in progress. No new IAM user/role, public port or SSH key is needed.
2. Open repository Settings > Secrets and variables > Actions > Secrets.
   Create or update repository secrets with the **current Academy session**:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `AWS_SESSION_TOKEN`
   Copy values privately from AWS Details. Never commit them or include screenshots.
3. Under Actions > Variables, create repository variable
   `AWS_DEPLOY_ENABLED` with value `true` when ready to activate automatic deployment.
   Missing/false leaves the deployment job skipped while CI still runs.
4. The Academy role must allow S3 upload to the input bucket deployment/cicd prefix,
   SSM SendCommand and GetCommandInvocation. The EC2 instance role must read that
   prefix, as it did for previous runtime packages. A denial is an unresolved
   permission issue, not a reason to disable checks or expose credentials.
5. Keep the repository private and restrict write access to trusted maintainers.
   Secrets are available only in the deploy job. Fork PRs never deploy. The current
   same-repository feature branch is an explicit trusted deployment branch; future
   PRs on other branches do not deploy. Push to main also deploys after CI.

Academy credentials expire. Refresh all three secrets each lab session as needed.
They are temporary LabRole credentials, not long-lived production credentials.
For a production account prefer a narrowly scoped GitHub OIDC role; this lab does
not assume permission to create such a role.

## Trigger and recording

For the first verification, enable the variable and use Re-run all jobs on the
workflow run of the commit that introduces this implementation (not old CI #35).
For the video, show a subsequent small, reviewed application code change and push
to the open PR. Its synchronize event automatically triggers CI and deployment.
No manual SSM deployment command belongs in that automatic sequence.

1. Show diff and commit SHA.
2. Show the corresponding Actions run with CI status and deployment successful.
3. Show the deployment summary containing the same full SHA and SSM command ID.
4. Through the SSM tunnel, query:

```powershell
curl.exe --fail --silent --show-error http://localhost:8081/api/ready
Invoke-RestMethod 'http://localhost:8081/release.json'
```

5. Refresh the browser. The header shows `Build` plus the first seven characters
   of the commit, providing a persistent way to identify the installed web version.
6. Verify the intended application behavior and the current Gold asset. HTTP 200
   readiness and revision identity do not replace checking business behavior.

Do not run `workflow_dispatch` to demonstrate an automatic push trigger: that is
a manual event and is intentionally not allowed to deploy by this gate. Re-running
the trusted PR event is a first-install diagnostic; the recorded demo uses a new push.

## Operations after the first deployment

The active image override is `/opt/dataforge/compose.cicd.yml` (root-only).
Use it with the base file for later manual Compose operations:

```bash
cd /opt/dataforge
sudo docker compose --env-file .env.compose -f compose.aws.yml -f compose.cicd.yml ps
```

Docker restart policies retain the assigned images after reboot. Running a later
`up` without this override can revert web/API to the old base image tags. Keep both
files in recovery documentation. Back up the override and deployment revision if
creating a new recovery package; the previous backup predates this change.

Root-only release folders and previous images are retained for investigation and
recovery. They consume disk; check `df -h /opt` and `sudo docker system df` before
repeated demos. Cleanup is a separate reviewed action; no automatic image prune runs.

Concurrent deploys use the existing host deployment lock. Workflow cancellation
does not guarantee a previously submitted SSM command stops. If GitHub polling
times out or is cancelled, inspect that command in Systems Manager before retrying.
CI serialization reduces overlapping runs; it does not provide transactional AWS
deployment or eliminate the single-host availability interruption.

The monitor can report a real availability interruption during recreation; do not
present deployment-related notifications as the separate controlled outage test.
