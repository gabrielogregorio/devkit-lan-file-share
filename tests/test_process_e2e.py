import hashlib
import http.client
import json
import os
import signal
import socket
import ssl
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from server.config_store import DEFAULT_PASSWORD, save_config
from server.discovery import APP_ID, DISCOVER_MESSAGE
from server.http_api import FILES_PATH, HELLO_PATH, PAIR_PATH
from server.keys import KeyStore
from server.proofs import CLIENT_ROLE, SERVER_ROLE, sign

ROOT = Path(__file__).resolve().parent.parent
PC_NAME = "e2e-pc"
UPLOAD_BYTES = 5_000_000
UPLOAD_BLOCK_BYTES = 256_000
STARTUP_ATTEMPTS = 100
DISCOVERY_ATTEMPTS = 10


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))

        return int(probe.getsockname()[1])


class ServerProcess:
    """The real server as a separate process, on its own port and config, driven like the phone drives it."""

    def __init__(self, root: Path) -> None:
        self.config_dir = root / "config"
        self.inbox = root / "inbox"
        self.port = free_port()
        self.process: subprocess.Popen[bytes] | None = None
        save_config(self.config_dir, folder=str(self.inbox))

    def start(self) -> None:
        environment = dict(os.environ, LFS_PORT=str(self.port), LFS_CONFIG_DIR=str(self.config_dir), LFS_NAME=PC_NAME)
        self.process = subprocess.Popen([sys.executable, "-m", "server.main"], cwd=ROOT, env=environment,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(STARTUP_ATTEMPTS):
            try:
                socket.create_connection(("127.0.0.1", self.port), 0.2).close()

                return
            except OSError:
                time.sleep(0.05)

        pytest.fail("server did not start")

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.kill()
            self.process.wait()

    def discover(self) -> dict[str, Any]:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
            udp_socket.settimeout(0.2)
            for _ in range(DISCOVERY_ATTEMPTS):  # UDP binds just after TCP, so the first message can go unheard
                udp_socket.sendto(DISCOVER_MESSAGE, ("127.0.0.1", self.port))
                try:
                    reply: dict[str, Any] = json.loads(udp_socket.recv(1024))

                    return reply
                except TimeoutError:
                    continue

        pytest.fail("no discovery reply")

    def pinned_connection(self, fingerprint: str) -> http.client.HTTPSConnection:
        """Pins the certificate as PcClient.java does: anything but this fingerprint is refused."""
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        connection = http.client.HTTPSConnection("127.0.0.1", self.port, context=context, timeout=10)
        connection.connect()
        tls_socket: ssl.SSLSocket = connection.sock
        peer_certificate = tls_socket.getpeercert(binary_form=True)
        assert peer_certificate is not None
        assert hashlib.sha256(peer_certificate).hexdigest() == fingerprint

        return connection

    def call(self, fingerprint: str, method: str, path: str, secret: str, body: Any = None,
             headers: dict[str, str] | None = None) -> tuple[int, dict[str, Any]]:
        connection = self.pinned_connection(fingerprint)
        all_headers = {"X-Auth": sign(secret, CLIENT_ROLE, fingerprint), **(headers or {})}
        connection.request(method, path, body, all_headers, encode_chunked="Transfer-Encoding" in all_headers)
        response = connection.getresponse()
        data = json.loads(response.read() or b"{}")
        connection.close()

        return response.status, data


@pytest.fixture
def server_process(tmp_path: Path) -> Iterator[ServerProcess]:
    process = ServerProcess(tmp_path)
    process.start()
    yield process
    process.stop()


def test_whole_journey_of_a_phone(server_process: ServerProcess) -> None:
    found = server_process.discover()
    assert (found["app"], found["name"], found["port"]) == (APP_ID, PC_NAME, server_process.port)
    fingerprint = found["fingerprint"]

    keys = KeyStore(server_process.config_dir)
    qr_key = keys.current()
    status, hello = server_process.call(fingerprint, "GET", HELLO_PATH, qr_key["secret"])
    assert (status, hello["proof"]) == (200, sign(qr_key["secret"], SERVER_ROLE, fingerprint))

    status, issued = server_process.call(fingerprint, "POST", PAIR_PATH, qr_key["secret"],
                                         headers={"X-Device": "Phone"})
    assert status == 200
    assert issued["key"] != qr_key["secret"]

    body = os.urandom(UPLOAD_BYTES)
    blocks = (body[start:start + UPLOAD_BLOCK_BYTES] for start in range(0, len(body), UPLOAD_BLOCK_BYTES))
    status, stored = server_process.call(fingerprint, "PUT", FILES_PATH, issued["key"], blocks,
                                         {"X-File-Name": "relat%C3%B3rio.pdf", "Transfer-Encoding": "chunked"})
    assert (status, stored["sha256"]) == (201, hashlib.sha256(body).hexdigest())
    assert (server_process.inbox / "relatório.pdf").read_bytes() == body

    old_key_upload = server_process.call(fingerprint, "PUT", FILES_PATH, qr_key["secret"], b"old",
                                         {"X-File-Name": "old.txt"})
    assert old_key_upload[0] == 201

    keys.revoke(qr_key["id"])
    refused = server_process.call(fingerprint, "PUT", FILES_PATH, qr_key["secret"], b"late", {"X-File-Name": "no.txt"})
    assert refused[0] == 401
    assert not (server_process.inbox / "no.txt").exists()


def test_keys_and_certificate_survive_a_restart(server_process: ServerProcess) -> None:
    fingerprint_before = server_process.discover()["fingerprint"]
    secret = KeyStore(server_process.config_dir).current()["secret"]

    server_process.stop()
    server_process.start()

    assert server_process.discover()["fingerprint"] == fingerprint_before
    assert server_process.call(fingerprint_before, "GET", HELLO_PATH, secret)[0] == 200


def test_killed_upload_leaves_no_trace_after_a_restart(server_process: ServerProcess) -> None:
    fingerprint = server_process.discover()["fingerprint"]
    connection = server_process.pinned_connection(fingerprint)
    connection.putrequest("PUT", FILES_PATH)
    connection.putheader("X-Auth", sign(DEFAULT_PASSWORD, CLIENT_ROLE, fingerprint))
    connection.putheader("X-File-Name", "cut.bin")
    connection.putheader("Content-Length", "100000000")
    connection.endheaders()
    connection.send(b"x" * 1_000_000)
    for _ in range(STARTUP_ATTEMPTS):
        if server_process.inbox.exists() and list(server_process.inbox.iterdir()):
            break
        time.sleep(0.02)

    assert server_process.process is not None
    server_process.process.send_signal(signal.SIGKILL)
    server_process.process.wait()
    connection.close()
    assert list(server_process.inbox.iterdir()), "the upload should have started"

    server_process.start()

    assert list(server_process.inbox.iterdir()) == []
