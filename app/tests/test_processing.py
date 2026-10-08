"""Tests for background job processing — failure isolation, counters, and final status."""

import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.db.models import Certificate, CertificateJob, CertificateStatus, JobStatus
from app.services.job_processor import _process_single_certificate, process_job
from app.tests.conftest import TestingSessionLocal, make_certificate, make_job


class TestFailureIsolation:
    """One certificate failure must not stop processing of remaining certificates."""

    def test_one_failure_does_not_stop_bulk_job(self, db: Session, tmp_path: Path):
        """If certificate #2 fails, certificates #1 and #3 should still be generated."""
        job = make_job(db, total_recipients=3, status=JobStatus.PROCESSING)
        cert1 = make_certificate(db, job, recipient_name="Alice", recipient_email="alice@t.com")
        cert2 = make_certificate(db, job, recipient_name="Bad", recipient_email="bad@t.com")
        cert3 = make_certificate(db, job, recipient_name="Carol", recipient_email="carol@t.com")

        call_count = 0

        def side_effect(data, path):
            nonlocal call_count
            call_count += 1
            if data.recipient_name == "Bad":
                raise RuntimeError("Simulated generation failure")
            # Create a minimal valid file
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"%PDF-fake")

        with patch("app.services.job_processor.generate_certificate_pdf", side_effect=side_effect):
            with patch("app.services.job_processor.settings") as mock_settings:
                mock_settings.certificates_path = tmp_path
                _process_single_certificate(db, job, cert1)
                _process_single_certificate(db, job, cert2)
                _process_single_certificate(db, job, cert3)

        db.refresh(cert1)
        db.refresh(cert2)
        db.refresh(cert3)
        db.refresh(job)

        assert cert1.status == CertificateStatus.GENERATED
        assert cert2.status == CertificateStatus.FAILED
        assert cert3.status == CertificateStatus.GENERATED

    def test_failed_certificate_stores_error_message(self, db: Session, tmp_path: Path):
        job = make_job(db, total_recipients=1, status=JobStatus.PROCESSING)
        cert = make_certificate(db, job)

        with patch(
            "app.services.job_processor.generate_certificate_pdf",
            side_effect=RuntimeError("Disk full"),
        ):
            with patch("app.services.job_processor.settings") as mock_settings:
                mock_settings.certificates_path = tmp_path
                _process_single_certificate(db, job, cert)

        db.refresh(cert)
        assert cert.status == CertificateStatus.FAILED
        assert "Disk full" in cert.error_message

    def test_job_counters_updated_correctly(self, db: Session, tmp_path: Path):
        job = make_job(db, total_recipients=4, status=JobStatus.PROCESSING)
        certs = [
            make_certificate(db, job, recipient_name=f"User{i}", recipient_email=f"u{i}@t.com")
            for i in range(4)
        ]

        def side_effect(data, path):
            # Fail every other certificate
            idx = int(data.recipient_name[-1])
            if idx % 2 == 1:
                raise RuntimeError("Fail")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"%PDF-fake")

        with patch("app.services.job_processor.generate_certificate_pdf", side_effect=side_effect):
            with patch("app.services.job_processor.settings") as mock_settings:
                mock_settings.certificates_path = tmp_path
                for cert in certs:
                    _process_single_certificate(db, job, cert)

        db.refresh(job)
        assert job.successful_count == 2
        assert job.failed_count == 2


class TestJobFinalStatus:
    """
    These tests call process_job() which internally opens a new SessionLocal().
    We mock SessionLocal to return the SQLite test session so no PostgreSQL connection is needed.
    """

    def _patch_session(self, db: Session):
        """
        Makes SessionLocal() return the test session.
        We also make db.close() a no-op so the test fixture retains session ownership.
        """
        from contextlib import contextmanager

        @contextmanager
        def _ctx():
            original_close = db.close
            db.close = lambda: None  # temporarily disable close
            with patch("app.services.job_processor.SessionLocal", return_value=db):
                try:
                    yield db
                finally:
                    db.close = original_close

        return _ctx()

    def test_all_success_sets_completed_status(self, db: Session, tmp_path: Path):
        job = make_job(db, total_recipients=2)
        make_certificate(db, job, recipient_name="A", recipient_email="a@t.com")
        make_certificate(db, job, recipient_name="B", recipient_email="b@t.com")

        def mock_gen(data, path):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"%PDF-fake")

        with patch("app.services.job_processor.generate_certificate_pdf", side_effect=mock_gen):
            with patch("app.services.job_processor.settings") as mock_settings:
                mock_settings.certificates_path = tmp_path
                with self._patch_session(db):
                    process_job(job.id)

        db.refresh(job)
        assert job.status == JobStatus.COMPLETED

    def test_all_fail_sets_failed_status(self, db: Session, tmp_path: Path):
        job = make_job(db, total_recipients=2)
        make_certificate(db, job, recipient_name="A", recipient_email="a@t.com")
        make_certificate(db, job, recipient_name="B", recipient_email="b@t.com")

        with patch(
            "app.services.job_processor.generate_certificate_pdf",
            side_effect=RuntimeError("always fails"),
        ):
            with patch("app.services.job_processor.settings") as mock_settings:
                mock_settings.certificates_path = tmp_path
                with self._patch_session(db):
                    process_job(job.id)

        db.refresh(job)
        assert job.status == JobStatus.FAILED

    def test_partial_failure_sets_partial_success_status(self, db: Session, tmp_path: Path):
        job = make_job(db, total_recipients=2)
        make_certificate(db, job, recipient_name="Good", recipient_email="good@t.com")
        make_certificate(db, job, recipient_name="Bad", recipient_email="bad@t.com")

        def side_effect(data, path):
            if data.recipient_name == "Bad":
                raise RuntimeError("Bad fails")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"%PDF-fake")

        with patch("app.services.job_processor.generate_certificate_pdf", side_effect=side_effect):
            with patch("app.services.job_processor.settings") as mock_settings:
                mock_settings.certificates_path = tmp_path
                with self._patch_session(db):
                    process_job(job.id)

        db.refresh(job)
        assert job.status == JobStatus.PARTIAL_SUCCESS
        assert job.successful_count == 1
        assert job.failed_count == 1
