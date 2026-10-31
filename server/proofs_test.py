from pathlib import Path

from server.proofs import CLIENT_ROLE, SERVER_ROLE, Credential, find_credential, sign

VECTORS_PATH = Path(__file__).resolve().parent.parent / "tests" / "vectors.txt"
FINGERPRINT = "ab" * 32


def test_vectors_shared_with_the_phone() -> None:
    lines = VECTORS_PATH.read_text(encoding="utf-8").splitlines()
    rows = [line.split("\t") for line in lines if line and not line.startswith("#")]

    assert len(rows) == 4
    assert [sign(secret, role, fingerprint) for secret, role, fingerprint, _ in rows] == [row[3] for row in rows]


def test_a_proof_for_one_role_does_not_serve_the_other() -> None:
    assert sign("secret", CLIENT_ROLE, FINGERPRINT) != sign("secret", SERVER_ROLE, FINGERPRINT)


def test_a_proof_for_one_certificate_does_not_serve_another() -> None:
    assert sign("secret", CLIENT_ROLE, FINGERPRINT) != sign("secret", CLIENT_ROLE, "cd" * 32)


def test_finds_the_credential_that_signed_the_proof() -> None:
    credentials = [Credential("first", "key-1"), Credential("second", "key-2"), Credential("password", None)]
    proof = sign("second", CLIENT_ROLE, FINGERPRINT)

    assert find_credential(proof, credentials, FINGERPRINT) == credentials[1]


def test_unknown_proof_finds_nothing() -> None:
    assert find_credential("forged", [Credential("first", "key-1")], FINGERPRINT) is None


def test_non_ascii_proof_is_refused_without_an_error() -> None:
    assert find_credential("prova-ção", [Credential("first", "key-1")], FINGERPRINT) is None
