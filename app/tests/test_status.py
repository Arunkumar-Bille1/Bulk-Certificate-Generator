"""Tests for GET /api/v1/certificate-jobs/{job_id} — status and progress tracking."""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import CertificateJob, JobStatus
from app.tests.conftest import VALID_JOB_PAYLOAD, make_certificate, make_job


class TestJobStatus:
    def test_get_status_pending_job(self, client: TestClient, db: Session):
        job = make_job(db, total_recipients=2, status=JobStatus.PENDING)
        resp = client.get(f"/api/v1/certificate-jobs/{job.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "PENDING"
        assert data["total"] == 2
        assert data["successful"] == 0
        assert data["failed"] == 0
        assert data["pending"] == 2
        assert data["progress_percentage"] == 0.0

    def test_get_status_processing_job(self, client: TestClient, db: Session):
        job = make_job(
            db,
            total_recipients=10,
            status=JobStatus.PROCESSING,
            successful_count=6,
            failed_count=1,
        )
        resp = client.get(f"/api/v1/certificate-jobs/{job.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "PROCESSING"
        assert data["successful"] == 6
        assert data["failed"] == 1
        assert data["pending"] == 3
        assert data["progress_percentage"] == 70.0

    def test_get_status_completed_job(self, client: TestClient, db: Session):
        job = make_job(
            db,
            total_recipients=5,
            status=JobStatus.COMPLETED,
            successful_count=5,
            failed_count=0,
        )
        resp = client.get(f"/api/v1/certificate-jobs/{job.id}")
        data = resp.json()
        assert data["status"] == "COMPLETED"
        assert data["progress_percentage"] == 100.0
        assert data["pending"] == 0

    def test_get_status_partial_success(self, client: TestClient, db: Session):
        job = make_job(
            db,
            total_recipients=10,
            status=JobStatus.PARTIAL_SUCCESS,
            successful_count=8,
            failed_count=2,
        )
        resp = client.get(f"/api/v1/certificate-jobs/{job.id}")
        data = resp.json()
        assert data["status"] == "PARTIAL_SUCCESS"
        assert data["successful"] == 8
        assert data["failed"] == 2

    def test_get_status_nonexistent_job(self, client: TestClient):
        fake_id = uuid.uuid4()
        resp = client.get(f"/api/v1/certificate-jobs/{fake_id}")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_get_status_invalid_uuid(self, client: TestClient):
        resp = client.get("/api/v1/certificate-jobs/not-a-uuid")
        assert resp.status_code == 422

    def test_progress_percentage_calculation(self, client: TestClient, db: Session):
        """Verify progress = (successful + failed) / total * 100."""
        job = make_job(
            db,
            total_recipients=100,
            status=JobStatus.PROCESSING,
            successful_count=33,
            failed_count=7,
        )
        resp = client.get(f"/api/v1/certificate-jobs/{job.id}")
        data = resp.json()
        assert data["progress_percentage"] == 40.0
        assert data["pending"] == 60

    def test_job_timestamps_present(self, client: TestClient, db: Session):
        job = make_job(db)
        resp = client.get(f"/api/v1/certificate-jobs/{job.id}")
        data = resp.json()
        assert "created_at" in data
        assert data["started_at"] is None
        assert data["completed_at"] is None
