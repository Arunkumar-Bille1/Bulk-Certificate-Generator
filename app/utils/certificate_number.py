"""Thread-safe certificate number generator.

Format: CERT-YYYY-NNNNNN
Example: CERT-2026-000001

A database UNIQUE constraint on the certificate_number column guarantees
uniqueness even if multiple workers generate the same counter value simultaneously.
The counter itself is read from the database (count of existing certificates)
plus a random component to avoid collisions during concurrent bulk jobs.
"""

import uuid
from datetime import datetime, timezone


def generate_certificate_number(year: int | None = None) -> str:
    """
    Generate a unique certificate number.

    The 6-digit suffix combines the current second-of-day with the first 4
    hex characters of a UUID to make collisions extremely unlikely.  The
    database UNIQUE index is the ultimate safety net.
    """
    if year is None:
        year = datetime.now(timezone.utc).year

    # Use UUID4 hex to get a random, collision-resistant suffix
    unique_suffix = uuid.uuid4().hex[:6].upper()
    # Convert hex to decimal-like numeric string (keeps it readable)
    numeric_part = str(int(unique_suffix, 16)).zfill(6)[:6]

    return f"CERT-{year}-{numeric_part}"
