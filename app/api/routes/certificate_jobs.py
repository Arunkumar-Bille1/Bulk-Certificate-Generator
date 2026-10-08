"""API routes for certificate job creation and status."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.database import get_db
from app.db.models import Certificate, CertificateJob, JobStatus
from app.schemas.certificate import CertificateListResponse, CertificateResponse
from app.schemas.job import CreateJobRequest, CreateJobResponse, JobStatusResponse
from app.services.job_processor import process_job

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/certificate-jobs", tags=["Certificate Jobs"])


@router.post(
    "",
    response_model=CreateJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a bulk certificate generation job",
    description=(
        "Accepts a list of recipients and certificate details, persists a job record, "
        "and starts background generation. Returns a job ID immediately so the caller "
        f"can poll for progress. Maximum {settings.MAX_RECIPIENTS_PER_JOB} recipients per request."
    ),
    responses={
        202: {"description": "Job accepted and processing started"},
        422: {"description": "Validation error — invalid input"},
    },
)
def create_certificate_job(
    payload: CreateJobRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
) -> CreateJobResponse:
    """
    Create a new certificate generation job.

    1. Validate and de-duplicate recipients.
    2. Persist the job and placeholder certificate rows.
    3. Return immediately (HTTP 202).
    4. Generate PDFs in a background task.
    """
    # Create the parent job record
    job = CertificateJob(
        certificate_title=payload.certificate_title,
        course_name=payload.course_name,
        event_name=payload.event_name,
        issue_date=str(payload.issue_date),
        issuer_name=payload.issuer_name,
        status=JobStatus.PENDING,
        total_recipients=len(payload.recipients),
    )
    db.add(job)
    db.flush()  # flush to get job.id before creating certificates

    # Create one Certificate placeholder per recipient
    for recipient in payload.recipients:
        cert = Certificate(
            job_id=job.id,
            recipient_name=recipient.name,
            recipient_email=str(recipient.email),
        )
        db.add(cert)

    db.commit()
    db.refresh(job)

    logger.info(
        "Created job %s with %d recipients", job.id, job.total_recipients
    )

    # Schedule background processing — API responds immediately
    background_tasks.add_task(process_job, job.id)

    return CreateJobResponse(
        job_id=job.id,
        status=job.status,
        total=job.total_recipients,
        message="Certificate generation job created successfully",
    )


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get certificate job status",
    description="Returns the current status and progress of a certificate generation job.",
    responses={
        200: {"description": "Job status returned"},
        404: {"description": "Job not found"},
        422: {"description": "Invalid UUID format"},
    },
)
def get_job_status(
    job_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> JobStatusResponse:
    job = db.get(CertificateJob, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate job '{job_id}' not found",
        )

    processed = job.successful_count + job.failed_count
    pending = job.total_recipients - processed
    progress = (processed / job.total_recipients * 100) if job.total_recipients > 0 else 0.0

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        total=job.total_recipients,
        successful=job.successful_count,
        failed=job.failed_count,
        pending=pending,
        progress_percentage=round(progress, 2),
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.get(
    "/{job_id}/certificates",
    response_model=CertificateListResponse,
    summary="List certificates for a job",
    description="Returns all certificate records associated with a generation job.",
    responses={
        200: {"description": "Certificate list returned"},
        404: {"description": "Job not found"},
    },
)
def list_job_certificates(
    job_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> CertificateListResponse:
    job = db.get(CertificateJob, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate job '{job_id}' not found",
        )

    certs = (
        db.query(Certificate)
        .filter(Certificate.job_id == job_id)
        .order_by(Certificate.created_at)
        .all()
    )

    return CertificateListResponse(
        job_id=job_id,
        total=len(certs),
        certificates=[_to_cert_response(c) for c in certs],
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _to_cert_response(cert: Certificate) -> CertificateResponse:
    download_url = None
    if cert.file_path:
        download_url = f"/api/v1/certificates/{cert.id}/download"

    return CertificateResponse(
        id=cert.id,
        job_id=cert.job_id,
        recipient_name=cert.recipient_name,
        recipient_email=cert.recipient_email,
        certificate_number=cert.certificate_number,
        status=cert.status,
        download_url=download_url,
        error_message=cert.error_message,
        created_at=cert.created_at,
        generated_at=cert.generated_at,
    )
