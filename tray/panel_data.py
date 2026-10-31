"""What the panel and the menu show, free of GTK so the tests run anywhere."""

import os
import socket
import time
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlencode

from server.certificate import certificate_fingerprint, ensure_certificate
from server.keys import KeyRecord, KeyStore
from server.settings import SETTINGS
from tray.app_info import ABOUT, LOG_PATH, NAME
from tray.i18n import tr

RECENT_FILES_LIMIT = 8
MAX_KIND_CHARACTERS = 4
LOG_LINE_CHARACTERS = 200
SIZE_UNITS = ("B", "KB", "MB", "GB")
UNREACHABLE_ADDRESS = "10.255.255.255"


class RecentFile(TypedDict):
    name: str
    path: str
    size: int
    time: float


class KeyRow(KeyRecord):
    state: str


def lan_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect((UNREACHABLE_ADDRESS, 1))  # no packet is sent: it only picks the outgoing interface

            return str(probe.getsockname()[0])
        except OSError:
            return "127.0.0.1"


def pair_url(ip: str, port: int = SETTINGS.port, config_dir: Path = SETTINGS.config_dir) -> str:
    """Deep link in the QR code: address, the certificate to pin and the current key."""
    certificate_path, _ = ensure_certificate(config_dir)
    query = urlencode({"host": ip, "port": port, "fp": certificate_fingerprint(certificate_path),
                       "k": KeyStore(config_dir).current()["secret"]})

    return f"lanfileshare://pair?{query}"


def recent_files(folder: str, limit: int = RECENT_FILES_LIMIT) -> list[RecentFile]:
    """Newest first; hidden files are left out, which also hides uploads still in progress."""
    try:
        entries = [entry for entry in os.scandir(folder) if entry.is_file() and not entry.name.startswith(".")]
    except OSError:
        return []

    entries.sort(key=lambda entry: entry.stat().st_mtime, reverse=True)

    return [RecentFile(name=entry.name, path=entry.path, size=entry.stat().st_size, time=entry.stat().st_mtime)
            for entry in entries[:limit]]


def human_size(size: int) -> str:
    value = float(size)
    for unit in SIZE_UNITS[:-1]:
        if value < 1024:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024

    return f"{value:.1f} {SIZE_UNITS[-1]}"


def kind_label(name: str) -> str:
    extension = os.path.splitext(name)[1][1:].upper()

    return extension if 0 < len(extension) <= MAX_KIND_CHARACTERS else "FILE"


def key_state(record: KeyRecord, current_id: str | None) -> str:
    if record["revoked"]:
        return "revoked"
    if record["id"] == current_id:
        return "current"

    return "old"


def key_rows(records: list[KeyRecord]) -> list[KeyRow]:
    """Newest first, with its state: the newest valid key is the one in the QR code."""
    valid_ids = [record["id"] for record in records if not record["revoked"]]
    current_id = valid_ids[-1] if valid_ids else None

    return [KeyRow(**record, state=key_state(record, current_id)) for record in reversed(records)]


def format_moment(stamp: float | None) -> str:
    return time.strftime("%d/%m %H:%M", time.localtime(stamp)) if stamp else "-"


def short_path(path: str) -> str:
    home = str(Path.home())
    if path == home or path.startswith(home + os.sep):
        return "~" + path[len(home):]

    return path


def menu_title() -> str:
    return f"{NAME} ({tr(ABOUT)})"


def status_text(on_air: bool, starting: bool, port: int = SETTINGS.port) -> str:
    if on_air:
        return tr("{name}: on air (port {port})", name=menu_title(), port=port)
    if starting:
        return tr("{name}: starting…", name=menu_title())

    return tr("{name}: off", name=menu_title())


def last_log_line(path: Path = LOG_PATH) -> str:
    try:
        lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines()]
    except OSError:
        return ""
    filled_lines = [line for line in lines if line]

    return filled_lines[-1][-LOG_LINE_CHARACTERS:] if filled_lines else ""


def failure_note(exit_code: int | None, log_line: str) -> str:
    return log_line or tr("exited with code {code}; see the log", code=exit_code)
