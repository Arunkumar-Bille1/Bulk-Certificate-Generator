"""Tests for certificate retrieval and download endpoints."""

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import CertificateStatus, JobStatus
from app.tests.conftest import make_certificate, make_job


class TestGetCertificate:
    def test_get_certificate_details(self, client: TestClient, db: Session):
        job = make_job(db)
        cert = make_certificate(
            db, job,
            recipient_name="Alice Smith",
            recipient_email="alice@example.com",
            certificate_number="CERT-2026-000001",
            status=CertificateStatus.GENERATED,
        )
        resp = client.get(f"/api/v1/certificates/{cert.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["recipient_name"] == "Alice Smith"
        assert data["recipient_email"] == "alice@example.com"
        assert data["certificate_number"] == "CERT-2026-000001"
        assert data["status"] == "GENERATED"

    def test_get_nonexistent_certificate(self, client: TestClient):
        resp = client.get(f"/api/v1/certificates/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_get_certificate_invalid_uuid(self, client: TestClient):
        resp = client.get("/api/v1/certificates/not-a-uuid")
        assert resp.status_code == 422

    def test_failed_certificate_exposes_error_message(self, client: TestClient, db: Session):
        job = make_job(db)
        cert = make_certificate(
            db, job,
            status=CertificateStatus.FAILED,
            error_message="Disk write permission denied",
        )
        resp = client.get(f"/api/v1/certificates/{cert.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "FAILED"
        assert data["error_message"] == "Disk write permission denied"


class TestDownloadCertificate:
    def test_download_returns_conflict_if_not_generated(self, client: TestClient, db: Session):
        job = make_job(db)
        cert = make_certificate(db, job, status=CertificateStatus.PENDING)
        resp = client.get(f"/api/v1/certificates/{cert.id}/download")
        assert resp.status_code == 409

    def test_download_returns_conflict_if_failed(self, client: TestClient, db: Session):
        job = make_job(db)
        cert = make_certificate(
            db, job,
            status=CertificateStatus.FAILED,
            error_message="Test failure",
        )
        resp = client.get(f"/api/v1/certificates/{cert.id}/download")
        assert resp.status_code == 409

    def test_download_returns_404_if_file_missing(self, client: TestClient, db: Session, tmp_path: Path):
        job = make_job(db)
        cert = make_certificate(
            db, job,
            status=CertificateStatus.GENERATED,
            file_path=str(tmp_path / "nonexistent.pdf"),
        )
        resp = client.get(f"/api/v1/certificates/{cert.id}/download")
        assert resp.status_code == 404

    def test_download_returns_pdf(self, client: TestClient, db: Session, tmp_path: Path):
        """When a real PDF exists on disk, the download endpoint serves it."""
        from app.services.certificate_generator import CertificateData, generate_certificate_pdf

        # Generate an actual PDF
        pdf_path = tmp_path / "test.pdf"
        generate_certificate_pdf(
            CertificateData(
                recipient_name="Test User",
                recipient_email="test@example.com",
                certificate_title="Test Cert",
                course_name="Test Course",
                event_name="Test Event",
                issue_date="October 08, 2026",
                issuer_name="Test Org",
                certificate_number="CERT-2026-TEST01",
            ),
            pdf_path,
        )

        job = make_job(db)
        cert = make_certificate(
            db, job,
            status=CertificateStatus.GENERATED,
            certificate_number="CERT-2026-TEST01",
            file_path=str(pdf_path),
        )

        resp = client.get(f"/api/v1/certificates/{cert.id}/download")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:4] == b"%PDF"


class TestListJobCertificates:
    def test_list_certificates_for_job(self, client: TestClient, db: Session):
        job = make_job(db, total_recipients=3)
        make_certificate(db, job, recipient_name="A", recipient_email="a@test.com")
        make_certificate(db, job, recipient_name="B", recipient_email="b@test.com")
        make_certificate(db, job, recipient_name="C", recipient_email="c@test.com")

        resp = client.get(f"/api/v1/certificate-jobs/{job.id}/certificates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["certificates"]) == 3

    def test_list_certificates_nonexistent_job(self, client: TestClient):
        resp = client.get(f"/api/v1/certificate-jobs/{uuid.uuid4()}/certificates")
        assert resp.status_code == 404

    def test_generated_certificate_has_download_url(self, client: TestClient, db: Session):
        job = make_job(db)
        cert = make_certificate(
            db, job,
            status=CertificateStatus.GENERATED,
            file_path="/some/path/cert.pdf",
        )
        resp = client.get(f"/api/v1/certificate-jobs/{job.id}/certificates")
        certs = resp.json()["certificates"]
        assert certs[0]["download_url"] is not None
        assert str(cert.id) in certs[0]["download_url"]

    def test_pending_certificate_has_no_download_url(self, client: TestClient, db: Session):
        job = make_job(db)
        make_certificate(db, job, status=CertificateStatus.PENDING)
        resp = client.get(f"/api/v1/certificate-jobs/{job.id}/certificates")
        certs = resp.json()["certificates"]
        assert certs[0]["download_url"] is None
