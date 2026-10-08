"""Shared pytest fixtures for the test suite."""

import uuid
from datetime import date
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base, get_db
from app.db.models import Certificate, CertificateJob, CertificateStatus, JobStatus
from app.main import app

# ---------------------------------------------------------------------------
# In-memory SQLite database for tests — no PostgreSQL required
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    """Create all tables once for the test session."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_db():
    """Truncate all tables between tests to ensure isolation."""
    yield
    db = TestingSessionLocal()
    try:
        db.query(Certificate).delete()
        db.query(CertificateJob).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """Yield a test database session."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client with DB override."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

VALID_JOB_PAYLOAD = {
    "certificate_title": "Certificate of Completion",
    "course_name": "Python Backend Development",
    "event_name": "Backend Bootcamp 2026",
    "issue_date": "2026-10-08",
    "issuer_name": "ABC Organization",
    "recipients": [
        {"name": "Alice Smith", "email": "alice@example.com"},
        {"name": "Bob Jones", "email": "bob@example.com"},
    ],
}


def make_job(db: Session, **kwargs) -> CertificateJob:
    """Insert a CertificateJob directly into the database."""
    defaults = {
        "certificate_title": "Test Certificate",
        "course_name": "Test Course",
        "event_name": "Test Event",
        "issue_date": "2026-10-08",
        "issuer_name": "Test Org",
        "status": JobStatus.PENDING,
        "total_recipients": 0,
        "successful_count": 0,
        "failed_count": 0,
    }
    defaults.update(kwargs)
    job = CertificateJob(**defaults)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def make_certificate(db: Session, job: CertificateJob, **kwargs) -> Certificate:
    """Insert a Certificate directly into the database."""
    defaults = {
        "job_id": job.id,
        "recipient_name": "Test User",
        "recipient_email": "test@example.com",
        "status": CertificateStatus.PENDING,
    }
    defaults.update(kwargs)
    cert = Certificate(**defaults)
    db.add(cert)
    db.commit()
    db.refresh(cert)
    return cert
