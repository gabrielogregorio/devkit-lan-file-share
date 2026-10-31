import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from server.certificate import certificate_fingerprint
from server.keys import KeyRecord, KeyStore
from tray.panel_data import (
    LOG_LINE_CHARACTERS,
    RECENT_FILES_LIMIT,
    failure_note,
    format_moment,
    human_size,
    key_rows,
    kind_label,
    last_log_line,
    pair_url,
    recent_files,
    short_path,
    status_text,
)


def key_record(key_id: str, revoked: bool = False) -> KeyRecord:
    return KeyRecord(id=key_id, secret="s", label="l", created=0, last_used=None, revoked=revoked)


def test_pair_url_carries_the_address_the_certificate_and_the_current_key(tmp_path: Path) -> None:
    url = urlparse(pair_url("10.0.0.5", 8908, tmp_path))

    query = parse_qs(url.query)
    assert (url.scheme, url.netloc) == ("lanfileshare", "pair")
    assert query["host"] == ["10.0.0.5"]
    assert query["port"] == ["8908"]
    assert query["fp"] == [certificate_fingerprint(tmp_path / "cert.pem")]
    assert query["k"] == [KeyStore(tmp_path).current()["secret"]]


def test_key_states_mark_the_newest_valid_key_as_current() -> None:
    records = [key_record("oldest"), key_record("newest-valid"), key_record("revoked", revoked=True)]

    rows = [(row["id"], row["state"]) for row in key_rows(records)]

    assert rows == [("revoked", "revoked"), ("newest-valid", "current"), ("oldest", "old")]


def test_with_every_key_revoked_none_is_current() -> None:
    assert [row["state"] for row in key_rows([key_record("gone", revoked=True)])] == ["revoked"]


def test_recent_files_are_newest_first_and_skip_hidden(tmp_path: Path) -> None:
    for modified_time, name in enumerate(("old.pdf", "new.pdf", ".upload.part")):
        path = tmp_path / name
        path.write_bytes(b"data")
        os.utime(path, (modified_time, modified_time))

    assert [recent_file["name"] for recent_file in recent_files(str(tmp_path))] == ["new.pdf", "old.pdf"]


def test_recent_files_have_a_limit(tmp_path: Path) -> None:
    for number in range(RECENT_FILES_LIMIT + 1):
        (tmp_path / f"file{number}.txt").touch()

    assert len(recent_files(str(tmp_path))) == RECENT_FILES_LIMIT


def test_recent_files_of_a_missing_folder_is_empty(tmp_path: Path) -> None:
    assert recent_files(str(tmp_path / "missing")) == []


@pytest.mark.parametrize(
    ("size", "expected"),
    [(512, "512 B"), (1023, "1023 B"), (1024, "1.0 KB"), (3 * 1024 ** 2, "3.0 MB"), (5 * 1024 ** 3, "5.0 GB"),
     (2048 * 1024 ** 3, "2048.0 GB")],
)
def test_human_size(size: int, expected: str) -> None:
    assert human_size(size) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [("report.pdf", "PDF"), ("photo.jpeg", "JPEG"), ("archive.backup", "FILE"), ("no-extension", "FILE")],
)
def test_kind_label(name: str, expected: str) -> None:
    assert kind_label(name) == expected


def test_moment_of_a_key_never_used_is_a_dash() -> None:
    assert format_moment(None) == "-"


def test_short_path_replaces_the_home_folder() -> None:
    assert short_path(str(Path.home() / "received")) == "~/received"


def test_short_path_leaves_other_paths_and_lookalikes() -> None:
    assert short_path("/opt/received") == "/opt/received"
    assert short_path(f"{Path.home()}-other/x") == f"{Path.home()}-other/x"


def test_status_on_air_shows_the_port() -> None:
    assert "8908" in status_text(True, False, 8908)


def test_status_starting_differs_from_off() -> None:
    assert status_text(False, True) != status_text(False, False)


def test_last_log_line_skips_blank_lines_and_is_cut(tmp_path: Path) -> None:
    log_path = tmp_path / "server.log"
    log_path.write_text("first\n" + "x" * (LOG_LINE_CHARACTERS + 5) + "\n\n", encoding="utf-8")

    assert last_log_line(log_path) == "x" * LOG_LINE_CHARACTERS


def test_last_log_line_of_a_missing_file_is_empty(tmp_path: Path) -> None:
    assert last_log_line(tmp_path / "missing.log") == ""


def test_failure_note_prefers_the_log() -> None:
    assert failure_note(1, "port in use") == "port in use"


def test_failure_note_falls_back_to_the_exit_code() -> None:
    assert "3" in failure_note(3, "")
