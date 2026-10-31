import os
import re
from pathlib import Path

from server.certificate import certificate_fingerprint, ensure_certificate


def test_certificate_is_created_once_and_the_key_is_private(tmp_path: Path) -> None:
    certificate_path, private_key_path = ensure_certificate(tmp_path)
    first_fingerprint = certificate_fingerprint(certificate_path)

    ensure_certificate(tmp_path)

    assert certificate_fingerprint(certificate_path) == first_fingerprint
    assert os.stat(private_key_path).st_mode & 0o777 == 0o600


def test_fingerprint_is_lowercase_hex_sha256(tmp_path: Path) -> None:
    certificate_path, _ = ensure_certificate(tmp_path)

    assert re.fullmatch(r"[0-9a-f]{64}", certificate_fingerprint(certificate_path))
