# Confirmed inputs for the final report

Operator confirmation: 2026-11-09. These notes support report preparation; they are
not the completed report or evidence of unexecuted work.

## Team and academic context

- Juan Camilo Ramón
- Felipe Castro Jaimes
- Gabriela Sanabria
- Professor: Juan Pablo Restrepo Lopera
- SI4002 Proyecto de Ingeniería de Datos, Universidad EAFIT

The operator confirmed that AI Solutions LATAM is fictional. Preserve it only as
an explicitly simulated consulting scenario. DataForge is an academic prototype,
not a deployed solution commissioned by a real client. Do not invent a company
supervisor, client interviews, adoption, economic savings or business KPIs.

## Learning confirmed by the team

The team confirmed prior unfamiliarity with Apache Airflow, MinIO and Groq.
They learned through documentation, AI assistance and video tutorials.
For AWS, the team specifically highlighted RDS, SSM and alerts as the relevant
new learning. Do not describe all AWS services as new to the team.
Individual contribution details and specific tutorial titles remain unconfirmed.

Distinguish outcomes:

- Airflow: generic pipeline orchestration used and verified.
- MinIO: S3-compatible object storage used in the local environment.
- AWS S3: cloud data assets in the Academy deployment.
- Groq: real model invocation and approved configuration proposal verified.
- Bedrock: explored through permission checks and an attempted invocation;
  tested Academy role denied ListFoundationModels and InvokeModel. No successful
  Bedrock model invocation is claimed.

## Alternatives section

The template requires at least three engineering alternatives and an explicit
comparison. No historical formal alternatives study has been confirmed.
A report may transparently present a retrospective design comparison, clearly
separating engineering judgments from measured prototype results.

Proposed comparison scope, not a record of prior team decisions:

1. Bespoke Python/SQL pipelines maintained independently for each client.
2. A reusable contract-driven platform with generic connectors, Airflow,
   PostgreSQL metadata and object storage: the implemented DataForge approach.
3. A managed AWS data platform, for example Glue and Step Functions with S3:
   a conceptual alternative whose IAM feasibility and cost require separate
   validation, especially in the Academy environment.

Compare reuse, traceability, operational complexity, cost, portability,
resource efficiency, security and usability. Do not invent benchmark results,
environmental savings, interviews or third-party deployment experience.
If a weighted matrix is used, label weights/scores as team engineering judgments,
not measurements or historical records. Do not imply all alternatives were built.

## Current delivery limitations

The complete retrospective design comparison, proposed weighted matrix,
sensitivity analysis and the template's required six-factor table are in
[design-alternatives.md](design-alternatives.md). Weights/scores are explicit
engineering judgments prepared with AI assistance for team review, not
historically agreed or experimentally measured values.

The operator has received no response to the GitHub billing-lock support request.
Do not mark hosted CI restored. The reviewed workflow validates code, services and
images but does not deploy automatically. Both a working test run and a genuine
automatic deployment demonstration remain required by the supplied instructions.

Latest screenshots supersede the earlier rubric's length/schedule instructions:
PDF follows the supplied professional report template with no page limit, remains
concise and includes the GitHub link; demo is a video of at most 12 minutes,
without slides, with every team member showing part of it. The operator-provided
instructions specify delivery 2026-11-09 at 17:00 Colombia time: one email with
YouTube link (public/unlisted) and PDF, copying the team. This note does not claim
the video was recorded/uploaded or the email sent.
