import fcntl
import json
import secrets
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict, TypeVar

from server.private_file import write_private

KEYS_FILE = "keys.json"
LOCK_FILE = "keys.lock"
QR_LABEL = "QR code"
ID_BYTES = 3
SECRET_BYTES = 32

Result = TypeVar("Result")


class KeyRecord(TypedDict):
    id: str
    secret: str
    label: str
    created: int
    last_used: int | None
    revoked: bool


class KeyStore:
    """keys.json, shared by the server and the tray icon, hence the file lock on every change."""

    def __init__(self, config_dir: Path, clock: Callable[[], float] = time.time) -> None:
        self.config_dir = config_dir
        self.path = config_dir / KEYS_FILE
        self.clock = clock

    def _read(self) -> list[KeyRecord]:
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

        return saved if isinstance(saved, list) else []

    def _change(self, edit: Callable[[list[KeyRecord]], Result]) -> Result:
        self.config_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        with open(self.config_dir / LOCK_FILE, "w", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            records = self._read()
            result = edit(records)
            write_private(self.path, json.dumps(records, indent=2) + "\n")

        return result

    def all(self) -> list[KeyRecord]:
        return self._read()

    def valid(self) -> list[KeyRecord]:
        return [record for record in self._read() if not record["revoked"]]

    def issue(self, label: str) -> KeyRecord:
        def add(records: list[KeyRecord]) -> KeyRecord:
            record: KeyRecord = {
                "id": secrets.token_hex(ID_BYTES),
                "secret": secrets.token_hex(SECRET_BYTES),
                "label": label,
                "created": int(self.clock()),
                "last_used": None,
                "revoked": False,
            }
            records.append(record)

            return record

        return self._change(add)

    def current(self) -> KeyRecord:
        """The newest key still valid, which is the one in the QR code."""
        valid_records = self.valid()

        return valid_records[-1] if valid_records else self.issue(QR_LABEL)

    def revoke(self, key_id: str) -> None:
        def mark_revoked(records: list[KeyRecord]) -> None:
            for record in records:
                if record["id"] == key_id:
                    record["revoked"] = True

        self._change(mark_revoked)

    def record_use(self, key_id: str) -> None:
        def mark_used(records: list[KeyRecord]) -> None:
            for record in records:
                if record["id"] == key_id:
                    record["last_used"] = int(self.clock())

        self._change(mark_used)
