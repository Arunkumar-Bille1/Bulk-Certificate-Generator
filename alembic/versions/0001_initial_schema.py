"""Initial schema: certificate_jobs and certificates tables.

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enums first
    job_status_enum = postgresql.ENUM(
        "PENDING", "PROCESSING", "COMPLETED", "PARTIAL_SUCCESS", "FAILED",
        name="job_status_enum",
    )
    job_status_enum.create(op.get_bind())

    certificate_status_enum = postgresql.ENUM(
        "PENDING", "GENERATED", "FAILED",
        name="certificate_status_enum",
    )
    certificate_status_enum.create(op.get_bind())

    # certificate_jobs table
    op.create_table(
        "certificate_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("certificate_title", sa.String(255), nullable=False),
        sa.Column("course_name", sa.String(255), nullable=False),
        sa.Column("event_name", sa.String(255), nullable=False),
        sa.Column("issue_date", sa.String(20), nullable=False),
        sa.Column("issuer_name", sa.String(255), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "PROCESSING", "COMPLETED", "PARTIAL_SUCCESS", "FAILED", name="job_status_enum"), nullable=False, server_default="PENDING"),
        sa.Column("total_recipients", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("successful_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_certificate_jobs_status", "certificate_jobs", ["status"])
    op.create_index("ix_certificate_jobs_created_at", "certificate_jobs", ["created_at"])

    # certificates table
    op.create_table(
        "certificates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("certificate_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipient_name", sa.String(255), nullable=False),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("certificate_number", sa.String(50), unique=True, nullable=True),
        sa.Column("status", sa.Enum("PENDING", "GENERATED", "FAILED", name="certificate_status_enum"), nullable=False, server_default="PENDING"),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_certificates_job_id", "certificates", ["job_id"])
    op.create_index("ix_certificates_status", "certificates", ["status"])
    op.create_index("ix_certificates_certificate_number", "certificates", ["certificate_number"])


def downgrade() -> None:
    op.drop_table("certificates")
    op.drop_table("certificate_jobs")

    op.execute("DROP TYPE IF EXISTS certificate_status_enum")
    op.execute("DROP TYPE IF EXISTS job_status_enum")
