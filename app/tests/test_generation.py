"""Tests for PDF certificate generation service (no database, no FastAPI)."""

import tempfile
from pathlib import Path

import pytest

from app.services.certificate_generator import CertificateData, generate_certificate_pdf


@pytest.fixture
def sample_data() -> CertificateData:
    return CertificateData(
        recipient_name="Jane Doe",
        recipient_email="jane@example.com",
        certificate_title="Certificate of Completion",
        course_name="Python Backend Development",
        event_name="Backend Bootcamp 2026",
        issue_date="October 08, 2026",
        issuer_name="ABC Organization",
        certificate_number="CERT-2026-000001",
    )


class TestCertificateGeneration:
    def test_generates_pdf_file(self, sample_data: CertificateData, tmp_path: Path):
        output = tmp_path / "test_cert.pdf"
        generate_certificate_pdf(sample_data, output)
        assert output.exists()

    def test_pdf_has_content(self, sample_data: CertificateData, tmp_path: Path):
        output = tmp_path / "test_cert.pdf"
        generate_certificate_pdf(sample_data, output)
        # PDF files start with "%PDF"
        with open(output, "rb") as f:
            header = f.read(4)
        assert header == b"%PDF"

    def test_pdf_has_reasonable_size(self, sample_data: CertificateData, tmp_path: Path):
        output = tmp_path / "test_cert.pdf"
        generate_certificate_pdf(sample_data, output)
        # A valid PDF should be at least 1 KB
        assert output.stat().st_size > 1024

    def test_creates_parent_directory(self, sample_data: CertificateData, tmp_path: Path):
        nested = tmp_path / "deep" / "nested" / "dir" / "cert.pdf"
        generate_certificate_pdf(sample_data, nested)
        assert nested.exists()

    def test_generates_unique_files_per_recipient(self, tmp_path: Path):
        data1 = CertificateData(
            recipient_name="Alice",
            recipient_email="alice@example.com",
            certificate_title="Cert",
            course_name="Course",
            event_name="Event",
            issue_date="2026-10-08",
            issuer_name="Org",
            certificate_number="CERT-2026-000001",
        )
        data2 = CertificateData(
            recipient_name="Bob",
            recipient_email="bob@example.com",
            certificate_title="Cert",
            course_name="Course",
            event_name="Event",
            issue_date="2026-10-08",
            issuer_name="Org",
            certificate_number="CERT-2026-000002",
        )
        path1 = tmp_path / "alice.pdf"
        path2 = tmp_path / "bob.pdf"
        generate_certificate_pdf(data1, path1)
        generate_certificate_pdf(data2, path2)
        assert path1.read_bytes() != path2.read_bytes()
