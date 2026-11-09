# Groq Copilot on AWS Academy

The API supports explicit server selection with DATAFORGE_COPILOT_PROVIDER:
bedrock (default) or groq. Deterministic mode remains a separate explicit user
choice; transport/provider errors never silently fall back. API proposals report
the actual configured provider. The generic UI label no longer claims Bedrock
when another provider is selected.

## Why another provider

The operator's live Academy test from the API container confirmed that LabRole
cannot call bedrock:ListFoundationModels or bedrock:InvokeModel on Nova Micro in
us-east-1 because no identity policy allows those actions. No SCP denial was
observed. No IAM/SCP restriction is changed by this integration. Groq is an
external HTTPS service; this is not an LLM hosted by the Academy account.

## Configuration

- DATAFORGE_COPILOT_PROVIDER=groq
- GROQ_MODEL_ID=openai/gpt-oss-120b (default; another accessible model can be set)
- GROQ_API_KEY: private server-side key, never in frontend/Vite variables.

On EC2, use an interactive SSM shell and run:

```bash
sudo python3 /opt/dataforge/scripts/aws/configure_groq.py
```

The key is entered through a hidden prompt, validated against line injection and
written atomically to /opt/dataforge/.env.copilot with mode 600. Recreating the
API loads this file. Compose overrides the API env_file list to read .env.aws
then optional .env.copilot in raw format. Airflow and migration services receive
only .env.aws, so the Groq key is not shared with their container environments.
Do not print .env.copilot or full docker compose config, commit it, put it in an
SSM command body, or upload it to S3. Existing .env.* exclusions apply.

After installing the new code/image:

```bash
cd /opt/dataforge
sudo docker compose --env-file .env.compose -f compose.aws.yml config --quiet
sudo docker compose --env-file .env.compose -f compose.aws.yml up -d --no-deps --force-recreate api
```

No database migration, contract approval, data deletion or pipeline trigger is
performed by configuring a provider. Returning to Bedrock requires changing or
removing the Groq override and recreating the API with authorized Bedrock access.

## Proposal validation and live check

Groq is called at the fixed HTTPS chat-completions endpoint with redirects
disabled, connection/read timeouts, JSON object output and no automatic retries.
GPT-OSS models use low reasoning effort and exclude reasoning from the response.
Rate limits, authentication failures, transport failures, refusal, tool calls and
truncated/malformed responses are explicit errors. Provider response bodies and
keys are not exposed in client errors. JSON object mode does not enforce our
schema: the existing strict Pydantic proposal and complete-contract validation
still reject unsupported operations, unknown columns and invalid parameters.
The existing signed preview, revision conflict checks and explicit approval flow
remain in place. Only schema/configuration, requirement and restricted profiling
summaries are sent; source credentials and raw rows are excluded by the existing
context preparation.

For the tareas demo, request a new warning rule named groq_demo_id_max_200:
id <= 200, mostly=1, allow_null=false; preserve existing rules and transformations.
Verify the response says provider=groq and the complete contract retains the
critical userId <= 8 rule. Generation must not save a revision. Explicitly approve
only after review, then run the persisted revision separately and inspect the
latest quality results. Expected Bronze/Silver/quarantine/Gold counts remain
200/160/40/8 because all source ids already satisfy the new warning rule. These
are expected values, not new live observations.

## Validation status

Local targeted Python suite: 35 tests passed (existing Copilot/API plus 10 new
Groq transport/configuration tests). Ruff passed on changed Python. Frontend:
15 tests and production build passed. No real Groq key was used by the editor;
live key authorization, proposal generation and deployment remain to be verified
by the operator. GitHub CI is separately blocked by account billing.

Groq free plan availability/limits are account- and model-dependent. Confirm the
selected account remains on Free and inspect its limits. This code does not
purchase a subscription or upgrade the provider plan. A 429 is reported rather
than retried or replaced by fabricated/deterministic success.

References:
- https://console.groq.com/docs/structured-outputs
- https://console.groq.com/docs/models
- https://console.groq.com/docs/rate-limits
- https://console.groq.com/docs/reasoning
