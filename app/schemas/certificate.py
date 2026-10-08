"""Pydantic schemas for individual certificate responses."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class CertificateResponse(BaseModel):
    """Response schema for a single certificate."""

    id: UUID
    job_id: UUID
    recipient_name: str
    recipient_email: str
    certificate_number: Optional[str]
    status: str
    download_url: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    generated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class CertificateListResponse(BaseModel):
    """Paginated list of certificates for a job."""

    job_id: UUID
    total: int
    certificates: list[CertificateResponse]
