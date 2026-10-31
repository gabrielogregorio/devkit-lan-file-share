import hashlib
import ssl
import subprocess
from pathlib import Path

CERTIFICATE_FILE = "cert.pem"
PRIVATE_KEY_FILE = "key.pem"
VALIDITY_DAYS = 3650


def ensure_certificate(config_dir: Path) -> tuple[Path, Path]:
    config_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    certificate_path = config_dir / CERTIFICATE_FILE
    private_key_path = config_dir / PRIVATE_KEY_FILE
    if certificate_path.exists() and private_key_path.exists():
        return certificate_path, private_key_path

    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
         "-keyout", str(private_key_path), "-out", str(certificate_path), "-days", str(VALIDITY_DAYS),
         "-subj", "/CN=lan-file-share"],
        check=True, capture_output=True)
    private_key_path.chmod(0o600)

    return certificate_path, private_key_path


def certificate_fingerprint(certificate_path: Path) -> str:
    """Lowercase hex SHA-256 of the certificate DER: the same value the phone computes and pins."""
    der_certificate = ssl.PEM_cert_to_DER_cert(certificate_path.read_text(encoding="ascii"))

    return hashlib.sha256(der_certificate).hexdigest()
