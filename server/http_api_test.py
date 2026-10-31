import hashlib
import http.client
import json
import os
import socket
import ssl
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest import mock

from conftest import PC_NAME, RunningServer
from server.config_store import DEFAULT_PASSWORD
from server.http_api import API_VERSION, FILES_PATH, HELLO_PATH, PAIR_PATH, FileShareServer
from server.keys import KeyRecord
from server.lockout import MAX_FAILURES
from server.proofs import CLIENT_ROLE, SERVER_ROLE, sign
from server.storage import MIN_FREE_BYTES, Inbox


def unverified_connection(port: int) -> http.client.HTTPSConnection:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    return http.client.HTTPSConnection("127.0.0.1", port, context=context, timeout=10)


def client_proof(running: RunningServer, secret: str = DEFAULT_PASSWORD) -> str:
    return sign(secret, CLIENT_ROLE, running.server.fingerprint)


def request(running: RunningServer, method: str, path: str, proof: str | None = None, body: Any = None,
            headers: dict[str, str] | None = None, **options: Any) -> tuple[int, dict[str, Any]]:
    connection = unverified_connection(running.port)
    auth_header = {"X-Auth": client_proof(running) if proof is None else proof}
    connection.request(method, path, body, {**auth_header, **(headers or {})}, **options)
    response = connection.getresponse()
    data = json.loads(response.read() or b"{}")
    connection.close()

    return response.status, data


def upload(running: RunningServer, name: str, body: bytes, proof: str | None = None) -> tuple[int, dict[str, Any]]:
    return request(running, "PUT", FILES_PATH, proof, body, {"X-File-Name": name})


def key_with_id(running: RunningServer, key_id: str) -> KeyRecord:
    return next(record for record in running.server.keys.all() if record["id"] == key_id)


def test_hello_proves_the_server_knows_the_password(running_server: RunningServer) -> None:
    status, data = request(running_server, "GET", HELLO_PATH)

    assert status == 200
    assert data == {"name": PC_NAME, "api": API_VERSION,
                    "proof": sign(DEFAULT_PASSWORD, SERVER_ROLE, running_server.server.fingerprint)}


def test_hello_writes_nothing(running_server: RunningServer) -> None:
    key = running_server.server.keys.current()
    keys_before = (running_server.config_dir / "keys.json").read_bytes()

    status, _ = request(running_server, "GET", HELLO_PATH, client_proof(running_server, key["secret"]))

    assert status == 200
    assert (running_server.config_dir / "keys.json").read_bytes() == keys_before


def test_wrong_proof_gets_the_uniform_error_and_saves_nothing(running_server: RunningServer) -> None:
    status, data = upload(running_server, "nope.txt", b"nope", proof="forged")

    assert status == 401
    assert (data["code"], data["detail"]) == ("wrong_secret", "wrong key or password")
    assert len(data["request_id"]) == 12
    assert not running_server.inbox.exists()


def test_missing_proof_is_refused(running_server: RunningServer) -> None:
    assert request(running_server, "GET", HELLO_PATH, proof="")[0] == 401


def test_too_many_wrong_proofs_lock_even_the_right_one_out(running_server: RunningServer) -> None:
    for _ in range(MAX_FAILURES):
        assert upload(running_server, "nope.txt", b"nope", proof="forged")[0] == 401

    status, data = upload(running_server, "nope.txt", b"nope")

    assert (status, data["code"]) == (429, "locked_out")
    assert not running_server.inbox.exists()


def test_a_right_proof_clears_the_wrong_ones_before_it(running_server: RunningServer) -> None:
    for _ in range(MAX_FAILURES - 1):
        request(running_server, "GET", HELLO_PATH, "forged")

    assert request(running_server, "GET", HELLO_PATH)[0] == 200

    for _ in range(MAX_FAILURES - 1):
        request(running_server, "GET", HELLO_PATH, "forged")
    assert request(running_server, "GET", HELLO_PATH)[0] == 200


def test_unknown_routes_are_not_found(running_server: RunningServer) -> None:
    for method, path in (("GET", "/"), ("POST", HELLO_PATH), ("PUT", PAIR_PATH), ("GET", f"{HELLO_PATH}?x=1")):
        status, data = request(running_server, method, path)

        assert (status, data["code"]) == (404, "not_found")


def test_unsupported_method_gets_the_uniform_error(running_server: RunningServer) -> None:
    status, data = request(running_server, "DELETE", FILES_PATH)

    assert (status, data["code"]) == (501, "bad_request")


def test_upload_lands_in_the_folder_with_its_hash(running_server: RunningServer) -> None:
    body = os.urandom(300_000)

    status, data = upload(running_server, "relat%C3%B3rio.pdf", body)

    assert status == 201
    assert data == {"name": "relatório.pdf", "size": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    assert (running_server.inbox / "relatório.pdf").read_bytes() == body


def test_chunked_upload_as_the_phone_sends_it(running_server: RunningServer) -> None:
    def chunks() -> Iterator[bytes]:
        yield b"hello "
        yield b"phone"

    status, data = request(running_server, "PUT", FILES_PATH, body=chunks(), encode_chunked=True,
                           headers={"X-File-Name": "note.txt", "Transfer-Encoding": "chunked"})

    assert (status, data["size"]) == (201, len(b"hello phone"))
    assert (running_server.inbox / "note.txt").read_bytes() == b"hello phone"


def test_traversal_stays_inside_the_folder(running_server: RunningServer) -> None:
    status, data = upload(running_server, "..%2F..%2Fevil.sh", b"data")

    assert (status, data["name"]) == (201, "evil.sh")
    assert (running_server.inbox / "evil.sh").exists()
    assert not (running_server.inbox.parent / "evil.sh").exists()


def test_same_name_never_overwrites(running_server: RunningServer) -> None:
    upload(running_server, "same.txt", b"first")

    _, data = upload(running_server, "same.txt", b"second")

    assert data["name"] == "same (1).txt"
    assert (running_server.inbox / "same.txt").read_bytes() == b"first"


def test_truncated_upload_leaves_nothing_and_the_server_survives(running_server: RunningServer) -> None:
    connection = unverified_connection(running_server.port)
    connection.putrequest("PUT", FILES_PATH)
    connection.putheader("X-Auth", client_proof(running_server))
    connection.putheader("X-File-Name", "cut.bin")
    connection.putheader("Content-Length", "1000")
    connection.endheaders()
    connection.send(b"only this")
    connection.close()

    assert upload(running_server, "after.txt", b"ok")[0] == 201
    assert [path.name for path in running_server.inbox.iterdir()] == ["after.txt"]


def test_upload_without_a_length_is_refused(running_server: RunningServer) -> None:
    connection = unverified_connection(running_server.port)
    connection.putrequest("PUT", FILES_PATH)
    connection.putheader("X-Auth", client_proof(running_server))
    connection.endheaders()
    response = connection.getresponse()

    assert (response.status, json.loads(response.read())["code"]) == (400, "upload_failed")
    connection.close()
    assert [path.name for path in running_server.inbox.iterdir()] == []


def test_full_disk_is_refused(running_server: RunningServer) -> None:
    running_server.server.inbox = Inbox(lambda _folder: MIN_FREE_BYTES - 1)

    status, data = upload(running_server, "big.bin", b"data")

    assert (status, data["code"]) == (507, "disk_almost_full")
    assert list(running_server.inbox.iterdir()) == []


def test_pairing_rotates_the_key_and_the_old_one_keeps_working(running_server: RunningServer) -> None:
    keys = running_server.server.keys
    first_key = keys.current()
    first_proof = client_proof(running_server, first_key["secret"])

    status, issued = request(running_server, "POST", PAIR_PATH, first_proof, headers={"X-Device": "S20%20FE"})

    assert status == 200
    assert issued["key"] != first_key["secret"]
    assert keys.current()["secret"] == issued["key"]
    assert keys.current()["label"] == "S20 FE"
    assert upload(running_server, "old.txt", b"data", proof=first_proof)[0] == 201
    new_proof = client_proof(running_server, issued["key"])
    _, hello = request(running_server, "GET", HELLO_PATH, new_proof)
    assert hello["proof"] == sign(issued["key"], SERVER_ROLE, running_server.server.fingerprint)


def test_pairing_with_a_wrong_proof_issues_nothing(running_server: RunningServer) -> None:
    keys_before = running_server.server.keys.all()

    assert request(running_server, "POST", PAIR_PATH, "forged")[0] == 401

    assert running_server.server.keys.all() == keys_before


def test_revoked_key_stops_working_at_once(running_server: RunningServer) -> None:
    key = running_server.server.keys.current()
    running_server.server.keys.revoke(key["id"])

    assert upload(running_server, "late.txt", b"data", client_proof(running_server, key["secret"]))[0] == 401


def test_upload_records_the_use_of_the_key(running_server: RunningServer) -> None:
    key = running_server.server.keys.current()

    upload(running_server, "used.txt", b"data", client_proof(running_server, key["secret"]))

    assert key_with_id(running_server, key["id"])["last_used"] is not None


def test_changed_password_applies_without_a_restart(running_server: RunningServer) -> None:
    (running_server.config_dir / "config.json").write_text(
        json.dumps({"folder": str(running_server.inbox), "password": "changed"}), encoding="utf-8")

    assert request(running_server, "GET", HELLO_PATH)[0] == 401
    assert request(running_server, "GET", HELLO_PATH, client_proof(running_server, "changed"))[0] == 200


def test_addresses_outside_the_local_network_are_dropped(tmp_path: Path) -> None:
    server = FileShareServer(("127.0.0.1", 0), tmp_path, PC_NAME)
    outsider: Any = mock.Mock(spec=socket.socket)

    assert not server.verify_request(outsider, ("8.8.8.8", 1234))
    server.server_close()


def test_connections_past_the_limit_are_dropped_until_one_ends(tmp_path: Path) -> None:
    server = FileShareServer(("127.0.0.1", 0), tmp_path, PC_NAME, max_connections=1)
    client: Any = mock.Mock(spec=socket.socket)

    assert server.verify_request(client, ("127.0.0.1", 1))
    assert not server.verify_request(client, ("127.0.0.1", 2))
    server.connection_slots.release()
    assert server.verify_request(client, ("127.0.0.1", 3))
    server.server_close()
