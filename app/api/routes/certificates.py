"""API routes for individual certificate retrieval and download."""

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.database import get_db
from app.db.models import Certificate, CertificateStatus
from app.schemas.certificate import CertificateResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/certificates", tags=["Certificates"])


@router.get(
    "/{certificate_id}",
    response_model=CertificateResponse,
    summary="Get certificate details",
    description="Returns the metadata and status of a specific certificate.",
    responses={
        200: {"description": "Certificate details returned"},
        404: {"description": "Certificate not found"},
    },
)
def get_certificate(
    certificate_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> CertificateResponse:
    cert = db.get(Certificate, certificate_id)
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate '{certificate_id}' not found",
        )
    return _to_response(cert)


@router.get(
    "/{certificate_id}/download",
    summary="Download a certificate PDF",
    description=(
        "Streams the generated PDF file to the client. "
        "Returns 404 if the certificate has not been generated yet or generation failed."
    ),
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF file"},
        404: {"description": "Certificate or PDF not found"},
        409: {"description": "Certificate has not been generated yet"},
    },
)
def download_certificate(
    certificate_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    cert = db.get(Certificate, certificate_id)
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate '{certificate_id}' not found",
        )

    if cert.status != CertificateStatus.GENERATED or not cert.file_path:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Certificate PDF is not available. "
                f"Current status: {cert.status}. "
                + (f"Reason: {cert.error_message}" if cert.error_message else "")
            ),
        )

    pdf_path = Path(cert.file_path)
    if not pdf_path.exists():
        logger.error("PDF file missing on disk: %s", pdf_path)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate PDF file not found on server",
        )

    filename = f"certificate_{cert.certificate_number}.pdf"
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _to_response(cert: Certificate) -> CertificateResponse:
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
