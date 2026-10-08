"""Background job processor.

Runs inside a FastAPI BackgroundTask so the API response is returned
immediately while certificates are generated asynchronously.

Design notes
------------
- Each certificate is processed independently; a failure in one does NOT
  stop the remaining recipients from being processed.
- The job status is updated atomically at the end of each certificate so
  that the GET /certificate-jobs/{id} endpoint always reflects real progress.
- We intentionally avoid Celery/Redis to keep the architecture simple and
  self-contained; this is an appropriate trade-off for the scale described
  in the assignment (≤500 recipients per job).
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.database import SessionLocal
from app.db.models import Certificate, CertificateJob, CertificateStatus, JobStatus
from app.services.certificate_generator import CertificateData, generate_certificate_pdf
from app.utils.certificate_number import generate_certificate_number

logger = get_logger(__name__)
settings = get_settings()


def process_job(job_id: uuid.UUID) -> None:
    """
    Entry point called by FastAPI BackgroundTasks.

    Opens its own database session (separate from the request session)
    so it can outlive the HTTP request lifecycle.
    """
    db: Session = SessionLocal()
    try:
        _run_job(db, job_id)
    except Exception:
        logger.exception("Unhandled error in background job processor for job_id=%s", job_id)
    finally:
        db.close()


def _run_job(db: Session, job_id: uuid.UUID) -> None:
    job = db.get(CertificateJob, job_id)
    if not job:
        logger.error("Job %s not found in database, skipping processing.", job_id)
        return

    # Mark job as PROCESSING
    job.status = JobStatus.PROCESSING
    job.started_at = datetime.now(timezone.utc)
    db.commit()

    logger.info("Started processing job %s with %d recipients", job_id, job.total_recipients)

    certificates = (
        db.query(Certificate)
        .filter(Certificate.job_id == job_id)
        .all()
    )

    for cert in certificates:
        _process_single_certificate(db, job, cert)

    # Determine final job status
    job.completed_at = datetime.now(timezone.utc)
    if job.failed_count == 0:
        job.status = JobStatus.COMPLETED
    elif job.successful_count == 0:
        job.status = JobStatus.FAILED
    else:
        job.status = JobStatus.PARTIAL_SUCCESS

    db.commit()
    logger.info(
        "Job %s finished: status=%s successful=%d failed=%d",
        job_id, job.status, job.successful_count, job.failed_count,
    )


def _process_single_certificate(
    db: Session, job: CertificateJob, cert: Certificate
) -> None:
    """Generate one PDF certificate, update counters, handle failures gracefully."""
    try:
        cert_number = _allocate_certificate_number(db)
        output_path = _build_output_path(job.id, cert.id)

        cert_data = CertificateData(
            recipient_name=cert.recipient_name,
            recipient_email=cert.recipient_email,
            certificate_title=job.certificate_title,
            course_name=job.course_name,
            event_name=job.event_name,
            issue_date=_format_date(job.issue_date),
            issuer_name=job.issuer_name,
            certificate_number=cert_number,
        )

        generate_certificate_pdf(cert_data, output_path)

        # Persist success
        cert.certificate_number = cert_number
        cert.file_path = str(output_path)
        cert.status = CertificateStatus.GENERATED
        cert.generated_at = datetime.now(timezone.utc)
        job.successful_count += 1

        logger.info(
            "Certificate generated: %s for %s (%s)",
            cert_number, cert.recipient_name, cert.recipient_email,
        )

    except Exception as exc:
        # Log and record failure WITHOUT stopping the loop
        error_msg = str(exc)
        logger.error(
            "Failed to generate certificate for %s (%s): %s",
            cert.recipient_name, cert.recipient_email, error_msg,
        )
        cert.status = CertificateStatus.FAILED
        cert.error_message = error_msg
        job.failed_count += 1

    finally:
        # Commit after each certificate so progress is visible in real time
        db.commit()


def _allocate_certificate_number(db: Session, max_retries: int = 5) -> str:
    """
    Generate a unique certificate number, retrying on the rare collision.
    The UNIQUE constraint on Certificate.certificate_number is the final guard.
    """
    for attempt in range(max_retries):
        number = generate_certificate_number()
        existing = (
            db.query(Certificate)
            .filter(Certificate.certificate_number == number)
            .first()
        )
        if existing is None:
            return number
        logger.warning("Certificate number collision on attempt %d: %s", attempt + 1, number)

    # Extremely unlikely, but fall back to a pure UUID-based number
    fallback = f"CERT-{datetime.now(timezone.utc).year}-{uuid.uuid4().hex[:8].upper()}"
    logger.warning("Using fallback certificate number: %s", fallback)
    return fallback


def _build_output_path(job_id: uuid.UUID, cert_id: uuid.UUID) -> Path:
    """Returns the absolute file path for a certificate PDF."""
    job_dir = settings.certificates_path / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir / f"{cert_id}.pdf"


def _format_date(date_str: str) -> str:
    """Convert ISO date string (YYYY-MM-DD) to human-readable form."""
    try:
        from datetime import date
        d = date.fromisoformat(date_str)
        return d.strftime("%B %d, %Y")
    except ValueError:
        return date_str
