"""Tests for POST /api/v1/certificate-jobs — job creation and bulk processing."""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.tests.conftest import VALID_JOB_PAYLOAD


class TestCreateJob:
    def test_create_job_success(self, client: TestClient):
        """A valid request returns 202 with a job ID."""
        with patch("app.api.routes.certificate_jobs.process_job"):
            resp = client.post("/api/v1/certificate-jobs", json=VALID_JOB_PAYLOAD)

        assert resp.status_code == 202
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "PENDING"
        assert data["total"] == 2
        assert "message" in data

    def test_job_id_is_valid_uuid(self, client: TestClient):
        with patch("app.api.routes.certificate_jobs.process_job"):
            resp = client.post("/api/v1/certificate-jobs", json=VALID_JOB_PAYLOAD)
        job_id = resp.json()["job_id"]
        # Should not raise
        uuid.UUID(job_id)

    def test_create_job_with_single_recipient(self, client: TestClient):
        payload = {**VALID_JOB_PAYLOAD, "recipients": [{"name": "Solo User", "email": "solo@test.com"}]}
        with patch("app.api.routes.certificate_jobs.process_job"):
            resp = client.post("/api/v1/certificate-jobs", json=payload)
        assert resp.status_code == 202
        assert resp.json()["total"] == 1

    def test_create_job_with_many_recipients(self, client: TestClient):
        recipients = [{"name": f"User {i}", "email": f"user{i}@test.com"} for i in range(50)]
        payload = {**VALID_JOB_PAYLOAD, "recipients": recipients}
        with patch("app.api.routes.certificate_jobs.process_job"):
            resp = client.post("/api/v1/certificate-jobs", json=payload)
        assert resp.status_code == 202
        assert resp.json()["total"] == 50
