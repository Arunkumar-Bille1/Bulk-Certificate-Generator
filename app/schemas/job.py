"""Pydantic schemas for certificate job requests and responses."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.core.config import get_settings

settings = get_settings()


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class RecipientIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Recipient full name")
    email: EmailStr = Field(..., description="Recipient email address")

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Recipient name must not be blank")
        return v.strip()


class CreateJobRequest(BaseModel):
    certificate_title: str = Field(
        ..., min_length=1, max_length=255,
        examples=["Certificate of Completion"]
    )
    course_name: str = Field(
        ..., min_length=1, max_length=255,
        examples=["Python Backend Development"]
    )
    event_name: str = Field(
        ..., min_length=1, max_length=255,
        examples=["Backend Development Bootcamp"]
    )
    issue_date: date = Field(..., examples=["2026-10-08"])
    issuer_name: str = Field(
        ..., min_length=1, max_length=255,
        examples=["ABC Organization"]
    )
    recipients: list[RecipientIn] = Field(
        ..., min_length=1,
        description=f"List of recipients (max {settings.MAX_RECIPIENTS_PER_JOB})"
    )

    @field_validator("recipients")
    @classmethod
    def validate_recipients(cls, v: list[RecipientIn]) -> list[RecipientIn]:
        if not v:
            raise ValueError("recipients must not be empty")

        max_size = settings.MAX_RECIPIENTS_PER_JOB
        if len(v) > max_size:
            raise ValueError(
                f"Too many recipients. Maximum allowed per job is {max_size}."
            )

        # Detect duplicate emails (case-insensitive)
        seen_emails: set[str] = set()
        duplicates: list[str] = []
        for recipient in v:
            normalized = recipient.email.lower()
            if normalized in seen_emails:
                duplicates.append(recipient.email)
            seen_emails.add(normalized)

        if duplicates:
            raise ValueError(
                f"Duplicate recipient emails found: {', '.join(set(duplicates))}. "
                "Each recipient must have a unique email address."
            )

        return v

    @field_validator("certificate_title", "course_name", "event_name", "issuer_name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field must not be blank")
        return stripped


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class CreateJobResponse(BaseModel):
    job_id: UUID
    status: str
    total: int
    message: str


class JobStatusResponse(BaseModel):
    job_id: UUID
    status: str
    total: int
    successful: int
    failed: int
    pending: int
    progress_percentage: float
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}
