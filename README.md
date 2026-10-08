<<<<<<< HEAD
# Bulk-Certificate-Generator
=======
# Bulk Certificate Generator API

A production-quality backend API built with **FastAPI + PostgreSQL** that accepts bulk certificate generation requests, processes them asynchronously in the background, and serves the generated PDF certificates.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Features](#features)
4. [Tech Stack](#tech-stack)
5. [Project Structure](#project-structure)
6. [Setup](#setup)
7. [Environment Variables](#environment-variables)
8. [Database Migrations](#database-migrations)
9. [Running the Application](#running-the-application)
10. [Running Tests](#running-tests)
11. [API Usage](#api-usage)
12. [Example Workflow](#example-workflow)
13. [Design Decisions](#design-decisions)

---

## Project Overview

This API allows clients to:

1. Submit a **bulk certificate generation job** with a list of recipients.
2. Immediately receive a **job ID** to track progress.
3. **Poll the job status** to see real-time progress (how many certificates succeeded/failed).
4. **Download individual PDF certificates** once generation completes.

Maximum recipients per job: **500** (configurable via `MAX_RECIPIENTS_PER_JOB`).

---

## Architecture

```
Client (curl / browser)
        │
        ▼
 ┌─────────────┐
 │   FastAPI   │  ← validates request, returns job_id immediately (HTTP 202)
 └──────┬──────┘
        │  saves job to DB
        ▼
 ┌─────────────┐
 │ PostgreSQL  │  ← stores jobs + certificate records
 └──────┬──────┘
        │  FastAPI BackgroundTasks triggers
        ▼
 ┌────────────────────┐
 │ Background Job     │  ← processes each recipient independently
 │ Processor          │
 └──────┬─────────────┘
        │  calls
        ▼
 ┌─────────────────────┐
 │ Certificate         │  ← generates PDF using ReportLab
 │ Generator Service   │
 └──────┬──────────────┘
        │  writes
        ▼
 ┌─────────────┐
 │ PDF Storage │  ← local filesystem (certificates/ directory)
 └─────────────┘
```

**Why background processing?**  
Certificate generation is I/O and CPU intensive. Making the client wait for 100+ PDFs would cause HTTP timeouts and a poor user experience. Instead, we return immediately (HTTP 202 Accepted) and process asynchronously, allowing the client to poll `/certificate-jobs/{id}` for progress.

---

## Features

- ✅ Bulk certificate generation (up to 500 recipients per request)
- ✅ Asynchronous background processing using FastAPI BackgroundTasks
- ✅ Real-time job progress tracking (pending / successful / failed counts)
- ✅ Individual failure isolation — one failed certificate does not stop others
- ✅ Professional PDF generation with decorative borders and gold accents
- ✅ Unique certificate number generation (`CERT-YYYY-NNNNNN`)
- ✅ PDF download endpoint
- ✅ Duplicate recipient email detection
- ✅ Input validation (email format, required fields, bulk size limit)
- ✅ Clear error messages for failed certificates
- ✅ Alembic database migrations
- ✅ Docker + Docker Compose support
- ✅ Full pytest test suite (no PostgreSQL required for tests)

---

## Tech Stack

| Technology | Version | Why |
|---|---|---|
| **Python** | 3.11+ | Modern type hints, performance improvements |
| **FastAPI** | 0.115 | Auto-generates OpenAPI docs, async support, dependency injection |
| **PostgreSQL** | 15 | Reliable relational DB with UUID support and ACID guarantees |
| **SQLAlchemy** | 2.0 | Type-safe ORM, prevents SQL injection, clean model definitions |
| **Alembic** | 1.13 | Schema version control alongside code |
| **Pydantic** | 2.9 | Request validation with descriptive error messages |
| **ReportLab** | 4.2 | Professional PDF generation from Python |
| **Uvicorn** | 0.30 | High-performance ASGI server |
| **pytest** | 8.3 | Standard Python testing with fixtures |
| **Docker** | — | Reproducible environment, easy deployment |

---

## Project Structure

```
.
├── app/
│   ├── main.py                  # FastAPI app, middleware, routers
│   ├── core/
│   │   ├── config.py            # Pydantic Settings (reads .env)
│   │   └── logging.py           # Centralized logging setup
│   ├── db/
│   │   ├── database.py          # SQLAlchemy engine, session, Base
│   │   └── models.py            # ORM models: CertificateJob, Certificate
│   ├── schemas/
│   │   ├── job.py               # Request/response Pydantic schemas for jobs
│   │   └── certificate.py       # Response schemas for certificates
│   ├── api/
│   │   └── routes/
│   │       ├── certificate_jobs.py  # POST /certificate-jobs, GET status/list
│   │       └── certificates.py     # GET certificate, GET download
│   ├── services/
│   │   ├── certificate_generator.py  # ReportLab PDF generation (pure function)
│   │   └── job_processor.py          # Background processing logic
│   ├── utils/
│   │   └── certificate_number.py     # CERT-YYYY-NNNNNN generator
│   └── tests/
│       ├── conftest.py          # Fixtures, SQLite test DB, factory helpers
│       ├── test_jobs.py         # Job creation tests
│       ├── test_validation.py   # Input validation tests
│       ├── test_generation.py   # PDF generation tests
│       ├── test_status.py       # Job status/progress tests
│       ├── test_certificates.py # Certificate retrieval/download tests
│       └── test_processing.py   # Background processor + failure isolation
├── alembic/
│   ├── env.py                   # Reads DATABASE_URL from environment
│   ├── script.py.mako           # Migration script template
│   └── versions/
│       └── 0001_initial_schema.py  # Initial tables migration
├── certificates/                # Generated PDFs (git-ignored)
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .env.example
├── .gitignore
├── requirements.txt
├── pytest.ini
├── alembic.ini
├── README.md
└── INTERVIEW_NOTES.md
```

---

## Setup

### Option A: Local Setup (requires Python 3.11+ and PostgreSQL)

```bash
# 1. Clone and enter directory
cd "Aereo Cloud"

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and configure environment
copy .env.example .env
# Edit .env: set DATABASE_URL to your PostgreSQL connection string

# 5. Create the database (in psql)
# CREATE DATABASE certificate_db;

# 6. Run migrations
alembic upgrade head

# 7. Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option B: Docker Compose (recommended — no local PostgreSQL needed)

```bash
# 1. Build and start all services
docker-compose up --build

# 2. The API will be available at http://localhost:8000
# 3. PostgreSQL will be available at localhost:5432
```

To stop:
```bash
docker-compose down
```

To stop and remove volumes (wipes data):
```bash
docker-compose down -v
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/certificate_db` | PostgreSQL connection string |
| `DEBUG` | `false` | Enable debug logging |
| `CERTIFICATES_DIR` | `certificates` | Directory where PDFs are stored |
| `MAX_RECIPIENTS_PER_JOB` | `500` | Maximum recipients per job request |

Copy `.env.example` to `.env` and adjust values for your environment.

---

## Database Migrations

```bash
# Apply all pending migrations (run this after first setup)
alembic upgrade head

# Check current migration state
alembic current

# Create a new migration (after changing models.py)
alembic revision --autogenerate -m "describe your change"

# Roll back one step
alembic downgrade -1

# Roll back all the way
alembic downgrade base
```

---

## Running the Application

**Local (development with auto-reload):**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Local (production-like):**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Docker:**
```bash
docker-compose up --build
```

**API Documentation (Swagger UI):**
```
http://localhost:8000/docs
```

**ReDoc:**
```
http://localhost:8000/redoc
```

---

## Running Tests

Tests use SQLite (in-memory) — **no PostgreSQL required**.

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest app/tests/test_validation.py -v

# Run a specific test class or function
pytest app/tests/test_processing.py::TestFailureIsolation -v

# Show print output (for debugging)
pytest -s
```

---

## API Usage

### 1. Create a Certificate Job

```bash
curl -X POST http://localhost:8000/api/v1/certificate-jobs \
  -H "Content-Type: application/json" \
  -d '{
    "certificate_title": "Certificate of Completion",
    "course_name": "Python Backend Development",
    "event_name": "Backend Development Bootcamp",
    "issue_date": "2026-10-08",
    "issuer_name": "ABC Organization",
    "recipients": [
      {"name": "John Doe", "email": "john@example.com"},
      {"name": "Jane Doe", "email": "jane@example.com"}
    ]
  }'
```

**Response (HTTP 202):**
```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "PENDING",
  "total": 2,
  "message": "Certificate generation job created successfully"
}
```

### 2. Check Job Status

```bash
curl http://localhost:8000/api/v1/certificate-jobs/3fa85f64-5717-4562-b3fc-2c963f66afa6
```

**Response:**
```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "COMPLETED",
  "total": 2,
  "successful": 2,
  "failed": 0,
  "pending": 0,
  "progress_percentage": 100.0,
  "created_at": "2026-10-08T08:00:00Z",
  "started_at": "2026-10-08T08:00:01Z",
  "completed_at": "2026-10-08T08:00:03Z"
}
```

### 3. List Certificates for a Job

```bash
curl http://localhost:8000/api/v1/certificate-jobs/3fa85f64-5717-4562-b3fc-2c963f66afa6/certificates
```

**Response:**
```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "total": 2,
  "certificates": [
    {
      "id": "cert-uuid-1",
      "job_id": "3fa85f64-...",
      "recipient_name": "John Doe",
      "recipient_email": "john@example.com",
      "certificate_number": "CERT-2026-483729",
      "status": "GENERATED",
      "download_url": "/api/v1/certificates/cert-uuid-1/download",
      "error_message": null,
      "created_at": "2026-10-08T08:00:00Z",
      "generated_at": "2026-10-08T08:00:02Z"
    }
  ]
}
```

### 4. Get Individual Certificate Details

```bash
curl http://localhost:8000/api/v1/certificates/{certificate_id}
```

### 5. Download Certificate PDF

```bash
curl -O -J http://localhost:8000/api/v1/certificates/{certificate_id}/download
```

Or open in browser:
```
http://localhost:8000/api/v1/certificates/{certificate_id}/download
```

---

## Example Workflow

```
1. POST /api/v1/certificate-jobs
   → Returns: { "job_id": "abc-123", "status": "PENDING", "total": 100 }

2. GET /api/v1/certificate-jobs/abc-123
   → Returns: { "status": "PROCESSING", "successful": 45, "pending": 55 }

3. GET /api/v1/certificate-jobs/abc-123  (poll again)
   → Returns: { "status": "COMPLETED", "successful": 98, "failed": 2 }
      (or PARTIAL_SUCCESS if some failed)

4. GET /api/v1/certificate-jobs/abc-123/certificates
   → Lists all 100 certificates with status and download URLs

5. GET /api/v1/certificates/{cert_id}/download
   → Streams the PDF file
```

**Job Statuses:**

| Status | Meaning |
|---|---|
| `PENDING` | Job created, not yet started |
| `PROCESSING` | Background task is running |
| `COMPLETED` | All certificates generated successfully |
| `PARTIAL_SUCCESS` | Some succeeded, some failed |
| `FAILED` | All certificates failed |

---

## Design Decisions

### Why FastAPI?
Auto-generates interactive API documentation (Swagger UI), has built-in dependency injection, Pydantic integration for validation, and BackgroundTasks for simple async processing. Much faster to build with than Django while being production-capable.

### Why PostgreSQL?
ACID compliance ensures job/certificate state is never corrupted. UUID primary keys, enum columns, and `UNIQUE` constraints on `certificate_number` are native features. SQLAlchemy ORM prevents SQL injection.

### Why BackgroundTasks instead of Celery/Redis?
For ≤500 recipients per job, FastAPI's built-in `BackgroundTasks` is sufficient. Adding Celery requires Redis or RabbitMQ, a separate worker process, and significantly more operational complexity — none of which is justified for this scale.

### Why ReportLab?
Pure Python, no external binaries (unlike wkhtmltopdf), precise layout control for professional certificate design, well-maintained library.

### How are failures isolated?
The `_process_single_certificate()` function wraps each PDF generation in a `try/except`. Any exception is caught, logged, and stored as the certificate's `error_message`. The loop continues to the next recipient regardless.

### How is progress calculated?
`progress_percentage = (successful_count + failed_count) / total_recipients * 100`  
Both successes and failures count as "processed". This accurately reflects work done.

### How are certificate numbers generated?
UUID4 hex provides randomness; the first 6 hex chars are converted to a decimal-like number. The database `UNIQUE` constraint on `certificate_number` is the ultimate safety net against collisions.

### How are file paths secured?
Paths are constructed programmatically using `pathlib.Path` from job/certificate UUIDs only — never from user input. This prevents path traversal attacks.
>>>>>>> d008e26 (feat: Bulk Certificate Generator backend with interactive dashboard, background jobs, test suite, and Docker setup)
