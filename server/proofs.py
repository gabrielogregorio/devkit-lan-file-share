"""HMAC proofs. Protocol.java computes the same ones, and tests/vectors.txt pins the two together."""

import hashlib
import hmac
from collections.abc import Iterable
from dataclasses import dataclass

CLIENT_ROLE = "client"
SERVER_ROLE = "server"


@dataclass(frozen=True)
class Credential:
    secret: str
    key_id: str | None  # None for the password, which has no entry in the key list


def sign(secret: str, role: str, fingerprint: str) -> str:
    return hmac.new(secret.encode(), f"{role}|{fingerprint}".encode(), hashlib.sha256).hexdigest()


def find_credential(proof: str, credentials: Iterable[Credential], fingerprint: str) -> Credential | None:
    """Compares against every credential, so the time taken does not reveal which one matched."""
    received = proof.encode()
    matched = None
    for credential in credentials:
        expected = sign(credential.secret, CLIENT_ROLE, fingerprint).encode()
        if hmac.compare_digest(received, expected):
            matched = credential

    return matched
