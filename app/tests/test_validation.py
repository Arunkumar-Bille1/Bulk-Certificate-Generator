"""Tests for input validation rules."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.tests.conftest import VALID_JOB_PAYLOAD


class TestEmptyRecipients:
    def test_empty_recipients_list(self, client: TestClient):
        payload = {**VALID_JOB_PAYLOAD, "recipients": []}
        resp = client.post("/api/v1/certificate-jobs", json=payload)
        assert resp.status_code == 422

    def test_missing_recipients_field(self, client: TestClient):
        payload = {k: v for k, v in VALID_JOB_PAYLOAD.items() if k != "recipients"}
        resp = client.post("/api/v1/certificate-jobs", json=payload)
        assert resp.status_code == 422


class TestInvalidEmail:
    def test_invalid_email_format(self, client: TestClient):
        payload = {
            **VALID_JOB_PAYLOAD,
            "recipients": [{"name": "Bad Email", "email": "not-an-email"}],
        }
        resp = client.post("/api/v1/certificate-jobs", json=payload)
        assert resp.status_code == 422

    def test_missing_email_field(self, client: TestClient):
        payload = {
            **VALID_JOB_PAYLOAD,
            "recipients": [{"name": "No Email"}],
        }
        resp = client.post("/api/v1/certificate-jobs", json=payload)
        assert resp.status_code == 422

    def test_valid_email_passes(self, client: TestClient):
        payload = {
            **VALID_JOB_PAYLOAD,
            "recipients": [{"name": "Valid User", "email": "valid@example.com"}],
        }
        with patch("app.api.routes.certificate_jobs.process_job"):
            resp = client.post("/api/v1/certificate-jobs", json=payload)
        assert resp.status_code == 202


class TestDuplicateRecipients:
    def test_duplicate_emails_rejected(self, client: TestClient):
        payload = {
            **VALID_JOB_PAYLOAD,
            "recipients": [
                {"name": "Alice", "email": "alice@example.com"},
                {"name": "Alice Again", "email": "alice@example.com"},
            ],
        }
        resp = client.post("/api/v1/certificate-jobs", json=payload)
        assert resp.status_code == 422
        assert "duplicate" in resp.json()["detail"][0]["msg"].lower()

    def test_case_insensitive_duplicate_emails_rejected(self, client: TestClient):
        payload = {
            **VALID_JOB_PAYLOAD,
            "recipients": [
                {"name": "Alice", "email": "Alice@Example.com"},
                {"name": "Alice2", "email": "alice@example.com"},
            ],
        }
        resp = client.post("/api/v1/certificate-jobs", json=payload)
        assert resp.status_code == 422


class TestRequiredFields:
    @pytest.mark.parametrize("field", ["certificate_title", "course_name", "event_name", "issuer_name"])
    def test_missing_required_string_field(self, client: TestClient, field: str):
        payload = {k: v for k, v in VALID_JOB_PAYLOAD.items() if k != field}
        resp = client.post("/api/v1/certificate-jobs", json=payload)
        assert resp.status_code == 422

    def test_blank_certificate_title_rejected(self, client: TestClient):
        payload = {**VALID_JOB_PAYLOAD, "certificate_title": "   "}
        resp = client.post("/api/v1/certificate-jobs", json=payload)
        assert resp.status_code == 422

    def test_blank_recipient_name_rejected(self, client: TestClient):
        payload = {
            **VALID_JOB_PAYLOAD,
            "recipients": [{"name": "   ", "email": "valid@example.com"}],
        }
        resp = client.post("/api/v1/certificate-jobs", json=payload)
        assert resp.status_code == 422

    def test_invalid_date_format(self, client: TestClient):
        payload = {**VALID_JOB_PAYLOAD, "issue_date": "not-a-date"}
        resp = client.post("/api/v1/certificate-jobs", json=payload)
        assert resp.status_code == 422


class TestBulkSizeLimit:
    def test_exceeding_max_recipients_rejected(self, client: TestClient):
        """501 recipients should be rejected (max is 500)."""
        recipients = [{"name": f"User {i}", "email": f"user{i}@test.com"} for i in range(501)]
        payload = {**VALID_JOB_PAYLOAD, "recipients": recipients}
        resp = client.post("/api/v1/certificate-jobs", json=payload)
        assert resp.status_code == 422
        assert "500" in resp.json()["detail"][0]["msg"] or "Too many" in resp.json()["detail"][0]["msg"]
