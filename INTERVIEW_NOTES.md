# Interview Notes — Bulk Certificate Generator

This document is your personal reference for explaining and defending every
design decision in the system during an interview.

---

## Architecture Explanation (30-second elevator pitch)

> "This is a FastAPI backend that accepts bulk certificate requests and
> processes them asynchronously. The client POSTs a list of recipients and
> immediately gets back a job ID. In the background, we iterate through
> each recipient, generate a PDF using ReportLab, store it on disk, and
> record the result in PostgreSQL. The client can poll a status endpoint
> at any time to see how many certificates have been generated. Failed
> certificates are recorded with an error message but never stop the
> remaining recipients from being processed."

---

## Request Flow — What Happens After POST /certificate-jobs

1. **FastAPI receives the request** and Pydantic validates every field (email
   format, no blank names, no duplicate emails, size limit).
2. **A `CertificateJob` row** is inserted into PostgreSQL with `status=PENDING`.
3. **One `Certificate` row per recipient** is inserted (all with `status=PENDING`).
4. The **HTTP 202 response is returned immediately** with the job UUID.
5. **`BackgroundTasks.add_task(process_job, job_id)`** is registered — FastAPI
   runs this after the response is sent, inside the same process.
6. The background function opens **its own database session** (not the
   request-scoped one, which is already closed).
7. Job status is updated to `PROCESSING`, and `started_at` is recorded.
8. For each `Certificate` row: generate PDF → update row → commit. One commit
   per certificate means progress is visible in real time.
9. After all certificates: set job to `COMPLETED`, `PARTIAL_SUCCESS`, or `FAILED`.

---

## Database Explanation

### Tables

**`certificate_jobs`** — one row per API request
- `id` (UUID PK) — avoids sequential IDs being guessable
- `status` (enum) — PENDING → PROCESSING → COMPLETED/PARTIAL_SUCCESS/FAILED
- `total_recipients`, `successful_count`, `failed_count` — derived counters
  stored redundantly for fast O(1) progress queries (no COUNT every time)
- `created_at`, `started_at`, `completed_at` — full lifecycle timestamps

**`certificates`** — one row per recipient per job
- `job_id` (FK → certificate_jobs) — enables "list certs by job" query
- `certificate_number` (UNIQUE) — enforced at the DB level, final guard
  against race conditions
- `file_path` — absolute path to the PDF on disk
- `error_message` — populated if generation fails, exposed via API

### Indexes
- `ix_certificate_jobs_status` — fast filtering by status
- `ix_certificates_job_id` — fast "get all certs for a job" lookup
- `ix_certificates_certificate_number` — fast uniqueness check

---

## Background Processing

FastAPI's `BackgroundTasks` executes the callback **after the HTTP response
is sent**, in the same OS thread pool. This is appropriate for our scale
(≤500 PDFs per job, each taking ~100ms). The background function:

1. Opens a **new `SessionLocal()`** — the request session is already closed.
2. Processes certificates sequentially (simple, predictable, easy to debug).
3. Commits after **each certificate** — progress visible immediately.
4. Handles exceptions per-certificate in `try/except` — never re-raises.

---

## Failure Handling

**If certificate #5 fails:**
1. `generate_certificate_pdf()` raises an exception.
2. The `except` block catches it, logs it, sets `cert.status = FAILED`,
   stores the error message, increments `job.failed_count`.
3. `db.commit()` saves the failure state.
4. The `for` loop continues to certificate #6, #7, etc.
5. At the end, if `successful_count > 0` and `failed_count > 0`, the job
   becomes `PARTIAL_SUCCESS`.

The key is that **the exception never escapes `_process_single_certificate()`**.

---

## Scalability

Current design handles ~500 recipients × ~100ms per PDF = ~50 seconds per
job. That is fine for one job at a time but will block other jobs.

**How to scale to 10,000+ recipients:**

| Concern | Current | Improved |
|---|---|---|
| Job size limit | 500 | Raise limit, split into sub-batches |
| Processing | Sequential in one thread | Parallel with `ThreadPoolExecutor` |
| Background worker | In-process BackgroundTasks | Celery workers + Redis broker |
| PDF storage | Local filesystem | AWS S3 / GCS |
| DB bottleneck | One commit per cert | Batch commits every N certs |
| Multiple API instances | Would duplicate work | Celery claim-and-lock |

**Minimal path to Celery:**
- Replace `background_tasks.add_task(process_job, job.id)` with
  `process_job.delay(str(job.id))` (Celery task)
- Add Redis to `docker-compose.yml`
- The `job_processor.py` logic stays identical — only the invocation changes

---

## Possible Interview Questions & Answers

### 1. Why FastAPI instead of Django or Flask?
FastAPI has native async support, auto-generated Swagger docs, and Pydantic
validation built in. For an API-only backend, it is much lighter than Django.
Flask lacks async and validation without extensions.

### 2. Why PostgreSQL instead of MySQL or MongoDB?
PostgreSQL has native UUID types, robust enum support, and strong ACID
guarantees. The relational schema (jobs → certificates FK) is a natural fit.
MongoDB would add schemaless flexibility we don't need.

### 3. Why background processing instead of synchronous generation?
Generating 500 PDFs could take 50+ seconds. HTTP connections time out, and
the client gets a poor experience. Returning 202 immediately and polling is
the standard REST pattern for long-running operations.

### 4. Why not generate certificates synchronously for small jobs?
Consistency matters. The API contract (202 + job_id + poll) should be the
same regardless of size. Adding conditional synchronous paths creates two
code paths to maintain and test.

### 5. How do you track progress?
`successful_count + failed_count` both increment atomically as each
certificate finishes. Progress = `(successful + failed) / total * 100`.
The counters are committed to PostgreSQL after every certificate so GET
status always reflects real progress.

### 6. What happens if one certificate fails?
The `_process_single_certificate()` function wraps generation in `try/except`.
The exception is caught, logged, saved as `error_message`, and the loop
continues. Other certificates are not affected.

### 7. How do you prevent duplicate certificate numbers?
Two layers: (1) `generate_certificate_number()` uses UUID4 hex for
randomness, making collisions extremely unlikely. (2) The database has a
`UNIQUE` constraint on `certificate_number` as a hard guarantee. If a
collision does occur, the code retries up to 5 times.

### 8. How would you process 100,000 certificates?
Use Celery with a Redis broker. Split the job into batches of 100 and
dispatch each batch as a separate Celery task. Workers process batches in
parallel. Store PDFs in S3. Use database transactions carefully to avoid
counter drift.

### 9. How would you introduce Celery and Redis?
1. Add `celery` and `redis` to `requirements.txt`.
2. Create `app/worker.py` with `celery = Celery(broker="redis://...")`
3. Annotate `process_job` with `@celery.task`.
4. Replace `background_tasks.add_task(process_job, job.id)` with
   `process_job.delay(str(job.id))`.
5. Add Redis and a Celery worker service to `docker-compose.yml`.

### 10. How would you store PDFs in AWS S3?
Replace `generate_certificate_pdf(data, output_path)` with a version that
streams directly to S3 using `boto3`. Store the S3 key (e.g.
`jobs/{job_id}/{cert_id}.pdf`) as `file_path` in the database. The download
endpoint generates a presigned S3 URL instead of serving the file.

### 11. How would you secure the APIs?
Add JWT authentication middleware. FastAPI's `Depends` can inject a
`get_current_user` dependency on every route. Rate limiting via SlowAPI.
HTTPS via a reverse proxy (nginx/Caddy). Never expose stack traces (already
implemented via the global exception handler).

### 12. How would you handle retries for failed certificates?
Add a `retry_count` column to `certificates`. After a failure, if
`retry_count < MAX_RETRIES`, re-queue the certificate. In Celery, use
`task.retry(countdown=backoff)` for exponential backoff.

### 13. How would you make the system horizontally scalable?
Move to Celery so multiple worker processes can run on separate machines.
Use S3 for storage (shared across instances). Keep API stateless — any API
instance can serve any request since state is in PostgreSQL.

### 14. What database indexes did you use and why?
- `ix_certificate_jobs_status` — filter jobs by status efficiently
- `ix_certificates_job_id` — retrieve all certs for a job in O(log n)
- `ix_certificates_certificate_number` — fast uniqueness check before insert
- `ix_certificates_status` — filter certificates by status

### 15. What happens if the server crashes during processing?
Jobs that were `PROCESSING` when the server crashed remain in `PROCESSING`
state permanently (orphaned). **Production fix**: at startup, query for
jobs stuck in `PROCESSING` for more than N minutes and either requeue or
mark them `FAILED`. Alternatively, use Celery tasks that are claimed with
an ACK so they auto-retry on worker death.

### 16. How do you prevent path traversal in file serving?
File paths are constructed exclusively from job and certificate UUIDs
(auto-generated, never from user input). A UUID like
`3fa85f64-5717-4562-b3fc-2c963f66afa6` can never contain `../`.

### 17. Why SQLAlchemy instead of raw SQL?
ORM prevents SQL injection by design — parameters are always escaped.
It also provides type-safe model definitions, relationship management,
and easy migration integration with Alembic.

### 18. How do you avoid SQL injection?
By using SQLAlchemy ORM exclusively. All queries use parameterized
bindings, never string concatenation with user input.

### 19. Why Pydantic for validation?
FastAPI integrates natively with Pydantic v2. Validation rules are
declared as type annotations and `Field()` constraints. Invalid requests
return structured 422 errors automatically — no manual `if` checks needed.

### 20. How would you add email notifications when a job completes?
1. Add a `send_completion_email()` call at the end of `_run_job()`.
2. Use an async email library like `fastapi-mail`.
3. For reliability, push emails to a queue (Celery beat or AWS SES queue)
   rather than calling SMTP synchronously in the background task.

### 21. How does BackgroundTasks differ from a true task queue?
`BackgroundTasks` runs in the same process as the API server. If the server
restarts, the task is lost. A true task queue (Celery + Redis) persists
tasks and allows worker processes to pick them up independently. For this
scale, BackgroundTasks is the right trade-off.

### 22. Why commit after each certificate instead of one big commit?
One big commit at the end means zero progress visibility during processing.
By committing after each certificate, the GET /status endpoint always shows
accurate real-time progress. The downside is more DB round-trips, but at
≤500 certs this is negligible.
