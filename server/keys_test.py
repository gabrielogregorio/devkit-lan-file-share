import os
from pathlib import Path

from server.keys import KEYS_FILE, QR_LABEL, SECRET_BYTES, KeyStore

FROZEN_TIME = 1_800_000_000


def frozen_clock() -> float:
    return FROZEN_TIME


def test_current_creates_the_first_key(tmp_path: Path) -> None:
    store = KeyStore(tmp_path, clock=frozen_clock)

    record = store.current()

    assert record["label"] == QR_LABEL
    assert record["created"] == FROZEN_TIME
    assert len(record["secret"]) == SECRET_BYTES * 2


def test_the_newest_valid_key_is_the_current_one(tmp_path: Path) -> None:
    store = KeyStore(tmp_path)
    store.issue("first")
    newest = store.issue("second")

    assert store.current()["id"] == newest["id"]


def test_issued_keys_are_all_different(tmp_path: Path) -> None:
    store = KeyStore(tmp_path)

    assert store.issue("first")["secret"] != store.issue("second")["secret"]


def test_revoking_keeps_the_key_listed_and_moves_current_back(tmp_path: Path) -> None:
    store = KeyStore(tmp_path)
    older = store.issue("first")
    newest = store.issue("second")

    store.revoke(newest["id"])

    assert [record["id"] for record in store.all()] == [older["id"], newest["id"]]
    assert [record["id"] for record in store.valid()] == [older["id"]]
    assert store.current()["id"] == older["id"]


def test_revoking_the_last_key_creates_a_new_one(tmp_path: Path) -> None:
    store = KeyStore(tmp_path)
    only_key = store.issue("only")

    store.revoke(only_key["id"])

    assert store.current()["id"] != only_key["id"]


def test_recording_use_touches_only_that_key(tmp_path: Path) -> None:
    store = KeyStore(tmp_path, clock=frozen_clock)
    used = store.issue("used")
    idle = store.issue("idle")

    store.record_use(used["id"])

    last_used = {record["id"]: record["last_used"] for record in store.all()}
    assert last_used == {used["id"]: FROZEN_TIME, idle["id"]: None}


def test_keys_file_is_private(tmp_path: Path) -> None:
    KeyStore(tmp_path).issue("first")

    assert os.stat(tmp_path / KEYS_FILE).st_mode & 0o777 == 0o600


def test_broken_file_reads_as_empty(tmp_path: Path) -> None:
    (tmp_path / KEYS_FILE).write_text('{"not": "a list"}', encoding="utf-8")

    assert KeyStore(tmp_path).all() == []
