# DataForge

[![CI](https://github.com/jcramonp/DataForge/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/jcramonp/DataForge/actions/workflows/ci.yml)

DataForge is an automated, scalable, and contract-driven data engineering platform designed to transform heterogeneous data sources into governed, validated, and analytics-ready datasets.

---

## Project Context

DataForge is developed as a modular data engineering solution for **AI Solutions LATAM**, a consulting company delivering data engineering, advanced analytics, and machine learning projects across diverse client environments.

The platform addresses a core operational bottleneck: each new client provides data in different formats (CSV, PostgreSQL, REST APIs) with custom schemas and quality criteria, forcing teams to write repetitive, ad-hoc pipelines. DataForge standardizes and automates this lifecycle using **declarative contracts**, generic connectors, automated quality gates with quarantine routing, and a modern control-plane web interface.

---

## Core Data Flow

```text
Source -> Ingestion -> Bronze -> Validation & Quality -> Silver -> Gold -> Certified Dataset -> Consumption
                                      |
                                      +--> Quarantine (Invalid Records)
```

- **Bronze**: Raw ingested data preserved in Parquet format with source checksums and lineage metadata.
- **Silver**: Standardized, clean data with validated data types and string normalizations.
- **Quarantine**: Records failing critical quality rules, isolated for investigation and auditable reprocessing.
- **Gold**: Integrated, aggregated, and curated analytical datasets assembled through declarative transformation plans.

---

## Getting Started: Running the Project

### 1. Prerequisites
- **Python**: 3.11+
- **Node.js & npm**: Node.js 18+ (for Web Interface)
- **Docker & Docker Compose**: For local PostgreSQL metadata and MinIO object storage

---

### 2. Infrastructure & Environment Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/jcramonp/DataForge.git
   cd DataForge
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```
   *(Ensure local database and MinIO credentials match `.env`)*

3. **Start local infrastructure (PostgreSQL & MinIO)**:
   ```bash
   docker compose up -d postgres minio minio-init
   ```
   - PostgreSQL bootstraps the control-plane schema from `database/migrations/` on first boot. Upgrade an existing database with `python -m src.ops.migrate`.
   - `minio-init` creates the storage buckets: `dataforge-bronze`, `dataforge-silver`, `dataforge-quarantine`, `dataforge-gold`.

4. **Install Python dependencies** (`requirements-dev.txt` adds lint tooling on top of `requirements.txt`):
   ```bash
   python -m pip install -r requirements-dev.txt
   ```

   Then apply migrations and check readiness:
   ```bash
   python -m src.ops.migrate
   python -m src.ops.health
   ```

5. **Install Frontend dependencies**:
   ```bash
   cd frontend
   npm install
   cd ..
   ```

---

### 3. Running the Control Plane & Web Interface

#### A. FastAPI Backend Control Plane
Start the API service from the repository root:
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Liveness**: [http://localhost:8000/api/health](http://localhost:8000/api/health)
- **Readiness** (database, migrations, buckets, contracts): [http://localhost:8000/api/ready](http://localhost:8000/api/ready)
- **Run metrics**: [http://localhost:8000/api/ops/summary](http://localhost:8000/api/ops/summary)
- Containerized alternative: `docker compose --profile api up -d --build`

#### B. React + Vite Web Interface
Start the development server from the `frontend/` directory:
```bash
cd frontend
npm run dev
```
- **Web Interface URL**: [http://localhost:3000](http://localhost:3000) (Vite proxies `/api` to `localhost:8000`)
- Features: Real-time project overview, source onboarding with connection tests, dataset schema and profiling views, quality gate review, pipeline triggers, quarantine inspection, asset lake explorer, and lineage graphs.

---

### 4. Running Contract-Driven Pipelines (CLI)

DataForge executes end-to-end pipelines driven by declarative YAML/JSON contracts (e.g., [`config/examples/olist.yaml`](config/examples/olist.yaml)):

#### A. Schema Discovery & Profiling
Analyze source data to discover schemas, candidate keys, nullability, and generate contract drafts:
```bash
python -m src.discovery.run_profiling --contract config/examples/olist.yaml
```

#### B. Generic Bronze Ingestion
Ingest configured datasets into the raw data lake layer with SHA-256 validation:
```bash
python -m src.ingestion.bronze_generic --contract config/examples/olist.yaml
```

#### C. Generic Silver Transformation & Quality Gate
Apply declarative transformations, evaluate Great Expectations quality rules, and partition invalid records:
```bash
python -m src.transformations.silver_runner --contract config/examples/olist.yaml
```

#### D. Configurable Gold Analytical Engine
Execute declarative transformation plans (joins, arithmetic derivations, aggregations) to produce Gold datasets (available once issue #31 / PR #41 is merged into `develop`):
```bash
python -m src.transformations.gold_runner --contract config/examples/olist.yaml
```

---

### 5. Running Automated Tests

Run the unit and regression suite (Sprint 1 Olist modules, Sprint 2 generic engine, API, operations tooling):
```bash
python -m unittest discover -s tests -t .
```

Run a single module or test:
```bash
python -m unittest tests.test_generic_silver_quality
python -m unittest tests.test_generic_silver_quality.GenericSilverTransformationTests.test_apply_trim
```

Lint, and verify the frontend production build:
```bash
ruff check .
cd frontend
npm run build
```

Integration tests against real PostgreSQL and MinIO (migrations plus an end-to-end generic pipeline) are opt-in; see [`docs/operations/runbook.md`](docs/operations/runbook.md#run-the-integration-suite-locally). GitHub Actions runs all of the above on every pull request ([`docs/operations/README.md`](docs/operations/README.md)).

---

### 6. Local Storage & Metadata Inspection

- **MinIO Console**: [http://localhost:9001](http://localhost:9001)  
  - User: `dataforge`  
  - Password: `change_me_minio`  
  - Inspect buckets: `dataforge-bronze`, `dataforge-silver`, `dataforge-quarantine`, `dataforge-gold`.

- **PostgreSQL Control Plane Database**: `localhost:5432`  
  - Database: `dataforge`  
  - User: `dataforge`  
  - Password: `change_me_postgres`  
  - Tables: `client`, `project`, `data_source`, `dataset`, `dataset_version`, `pipeline_run`, `data_asset`, `quality_result`.

---

## Operations

- [`docs/operations/configuration.md`](docs/operations/configuration.md): `local` / `test` / `aws` environments, runtime variables, secrets and AWS IAM permissions.
- [`docs/operations/migrations.md`](docs/operations/migrations.md): versioned control-plane migrations (`python -m src.ops.migrate`).
- [`docs/operations/observability.md`](docs/operations/observability.md): health/readiness, structured JSON logs with `run_id`/`dataset`, run metrics (`python -m src.ops.run_summary`).
- [`docs/operations/runbook.md`](docs/operations/runbook.md): rebuilding the demo from scratch, deployment, rollback and recovery.

---

## Technology Stack

- **Core & Transformations**: Python 3.11+, pandas, NumPy, PyArrow
- **Data Quality**: Great Expectations
- **Contracts & Validation**: Pydantic v2, PyYAML
- **Metadata & Control Plane**: PostgreSQL 16, psycopg v3, FastAPI, Uvicorn
- **Object Storage**: MinIO (S3-compatible API), Boto3
- **Frontend & UI**: React 18, Vite, Vanilla CSS with Geist typography and modern dark-mode aesthetics
- **Orchestration & Runtimes**: Docker Compose, Apache Airflow
- **CI**: GitHub Actions, ruff

---

## Engineering Principles

- **Declarative Contracts**: Platform behavior is configured via contracts, avoiding bespoke per-client code.
- **Data Quality as a First-Class Citizen**: Bad records are quarantined without halting ingestion.
- **Auditability & Traceability**: Every pipeline run, data asset, and quality evaluation is tracked in metadata.
- **Idempotency & Reproducibility**: Implements deterministic hashing and versioned data assets.
- **API-Driven Architecture**: Separation of control plane and storage.

---

## Course

**SI4002 — Proyecto de Ingeniería de Datos**  
Universidad EAFIT
