import json
import logging
import ssl
import threading
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socket import socket
from typing import Any, cast
from urllib.parse import unquote

from server.body import BodyError, read_body
from server.certificate import certificate_fingerprint, ensure_certificate
from server.config_store import AppConfig, load_config
from server.keys import KeyStore
from server.lockout import LoginGuard
from server.names import clean_device_label, sanitize_file_name
from server.network import is_lan_address
from server.proofs import SERVER_ROLE, Credential, find_credential, sign
from server.storage import DiskAlmostFullError, Inbox

logger = logging.getLogger(__name__)

API_VERSION = 1
HELLO_PATH = "/api/v1/hello"
PAIR_PATH = "/api/v1/pair"
FILES_PATH = "/api/v1/files"
SOCKET_TIMEOUT_SECONDS = 60  # also covers the TLS handshake, which runs on the client thread
MAX_CONNECTIONS = 32


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "LanFileShare/1"
    timeout = SOCKET_TIMEOUT_SECONDS

    @property
    def app(self) -> "FileShareServer":
        return cast(FileShareServer, self.server)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - name set by BaseHTTPRequestHandler
        pass

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        self._reply_error(HTTPStatus(code), "bad_request", message or HTTPStatus(code).phrase)

    def _reply(self, status: HTTPStatus, body: dict[str, Any]) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True

    def _reply_error(self, status: HTTPStatus, code: str, detail: str) -> None:
        request_id = uuid.uuid4().hex[:12]
        logger.info('refused request_id="%s" code="%s" address="%s"', request_id, code, self.client_address[0])
        self._reply(status, {"code": code, "detail": detail, "request_id": request_id})

    def _authenticate(self, config: AppConfig) -> Credential | None:
        address = self.client_address[0]
        guard = self.app.guard
        if guard.is_locked(address):
            self._reply_error(HTTPStatus.TOO_MANY_REQUESTS, "locked_out", "too many attempts")

            return None

        candidates = [Credential(record["secret"], record["id"]) for record in self.app.keys.valid()]
        candidates.append(Credential(config.password, None))
        credential = find_credential(self.headers.get("X-Auth", ""), candidates, self.app.fingerprint)
        if credential is None:
            guard.record_failure(address)
            self._reply_error(HTTPStatus.UNAUTHORIZED, "wrong_secret", "wrong key or password")

            return None

        guard.record_success(address)

        return credential

    def _record_use(self, credential: Credential) -> None:
        if credential.key_id:
            self.app.keys.record_use(credential.key_id)

    def do_GET(self) -> None:  # noqa: N802 - name set by BaseHTTPRequestHandler
        if self.path != HELLO_PATH:
            self._reply_error(HTTPStatus.NOT_FOUND, "not_found", "not found")

            return

        credential = self._authenticate(load_config(self.app.config_dir))
        if credential is None:
            return

        proof = sign(credential.secret, SERVER_ROLE, self.app.fingerprint)
        self._reply(HTTPStatus.OK, {"name": self.app.pc_name, "api": API_VERSION, "proof": proof})

    def do_POST(self) -> None:  # noqa: N802 - name set by BaseHTTPRequestHandler
        if self.path != PAIR_PATH:
            self._reply_error(HTTPStatus.NOT_FOUND, "not_found", "not found")

            return

        credential = self._authenticate(load_config(self.app.config_dir))
        if credential is None:
            return

        self._record_use(credential)
        record = self.app.keys.issue(clean_device_label(self.headers.get("X-Device", "")))
        logger.info('issued key id="%s" for "%s"', record["id"], record["label"])
        self._reply(HTTPStatus.OK, {"id": record["id"], "key": record["secret"], "created": record["created"]})

    def do_PUT(self) -> None:  # noqa: N802 - name set by BaseHTTPRequestHandler
        if self.path != FILES_PATH:
            self._reply_error(HTTPStatus.NOT_FOUND, "not_found", "not found")

            return

        config = load_config(self.app.config_dir)
        credential = self._authenticate(config)
        if credential is None:
            return

        self._record_use(credential)
        name = sanitize_file_name(unquote(self.headers.get("X-File-Name", "")))
        try:
            stored = self.app.inbox.store(config.target_folder, name, read_body(self.rfile, self.headers))
        except DiskAlmostFullError:
            self._reply_error(HTTPStatus.INSUFFICIENT_STORAGE, "disk_almost_full", "disk almost full")

            return
        except (OSError, BodyError) as error:
            logger.warning('upload of "%s" failed: %s', name, error)
            self._reply_error(HTTPStatus.BAD_REQUEST, "upload_failed", "upload failed")

            return

        logger.info('received "%s" (%d bytes) from "%s"', stored.name, stored.size, self.client_address[0])
        self._reply(HTTPStatus.CREATED, {"name": stored.name, "size": stored.size, "sha256": stored.sha256})


class FileShareServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], config_dir: Path, pc_name: str,
                 inbox: Inbox | None = None, max_connections: int = MAX_CONNECTIONS) -> None:
        super().__init__(address, Handler)
        self.config_dir = config_dir
        self.pc_name = pc_name
        certificate_path, private_key_path = ensure_certificate(config_dir)
        self.fingerprint = certificate_fingerprint(certificate_path)
        self.keys = KeyStore(config_dir)
        self.keys.current()
        self.guard = LoginGuard()
        self.inbox = inbox or Inbox()
        self.connection_slots = threading.BoundedSemaphore(max_connections)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(certificate_path, private_key_path)
        # the handshake runs on the client thread, so a stalled client cannot block accept()
        self.socket = context.wrap_socket(self.socket, server_side=True, do_handshake_on_connect=False)

    def verify_request(self, request: Any, client_address: Any) -> bool:
        return is_lan_address(client_address[0]) and self.connection_slots.acquire(blocking=False)

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.connection_slots.release()

    def handle_error(self, request: socket | tuple[bytes, socket], client_address: Any) -> None:
        pass  # clients come and go: dropped Wi-Fi and failed handshakes are not server errors
