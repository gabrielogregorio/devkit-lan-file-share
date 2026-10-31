import hashlib
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from server.body import BodyError
from server.storage import (
    FREE_CHECK_INTERVAL_BYTES,
    MIN_FREE_BYTES,
    RECEIVED_FILE_MODE,
    DiskAlmostFullError,
    Inbox,
    remove_leftovers,
    unique_path,
)

PART_NAME = f".{'a' * 32}.part"


def plenty_of_space(_folder: Path) -> int:
    return MIN_FREE_BYTES


def no_space(_folder: Path) -> int:
    return MIN_FREE_BYTES - 1


def test_unique_path_keeps_a_free_name(tmp_path: Path) -> None:
    assert unique_path(tmp_path, "report.pdf").name == "report.pdf"


def test_unique_path_numbers_a_taken_name(tmp_path: Path) -> None:
    (tmp_path / "report.pdf").touch()
    (tmp_path / "report (1).pdf").touch()

    assert unique_path(tmp_path, "report.pdf").name == "report (2).pdf"


def test_unique_path_treats_a_dangling_link_as_taken(tmp_path: Path) -> None:
    (tmp_path / "report.pdf").symlink_to(tmp_path / "gone")

    assert unique_path(tmp_path, "report.pdf").name == "report (1).pdf"


def test_store_writes_the_file_with_its_hash(tmp_path: Path) -> None:
    stored = Inbox(plenty_of_space).store(tmp_path, "report.pdf", [b"hello ", b"phone"])

    assert stored.name == "report.pdf"
    assert stored.size == len(b"hello phone")
    assert stored.sha256 == hashlib.sha256(b"hello phone").hexdigest()
    assert (tmp_path / "report.pdf").read_bytes() == b"hello phone"


def test_store_creates_the_folder(tmp_path: Path) -> None:
    folder = tmp_path / "new" / "folder"

    Inbox(plenty_of_space).store(folder, "report.pdf", [b"data"])

    assert (folder / "report.pdf").is_file()


def test_received_file_is_never_executable(tmp_path: Path) -> None:
    Inbox(plenty_of_space).store(tmp_path, "script.sh", [b"#!/bin/sh"])

    mode = os.stat(tmp_path / "script.sh").st_mode & 0o777
    assert mode & 0o111 == 0
    assert mode == RECEIVED_FILE_MODE & ~current_umask()


def current_umask() -> int:
    mask = os.umask(0)
    os.umask(mask)

    return mask


def test_store_refuses_when_the_disk_is_almost_full(tmp_path: Path) -> None:
    with pytest.raises(DiskAlmostFullError):
        Inbox(no_space).store(tmp_path, "big.bin", [b"data"])

    assert list(tmp_path.iterdir()) == []


def test_free_space_is_checked_again_during_a_long_upload(tmp_path: Path) -> None:
    measurements = iter([MIN_FREE_BYTES, MIN_FREE_BYTES - 1])
    blocks = [b"x" * FREE_CHECK_INTERVAL_BYTES, b"y"]

    with pytest.raises(DiskAlmostFullError):
        Inbox(lambda _folder: next(measurements)).store(tmp_path, "big.bin", blocks)

    assert list(tmp_path.iterdir()) == []


def test_free_space_is_not_measured_on_every_block(tmp_path: Path) -> None:
    measurements: list[Path] = []

    def measure(folder: Path) -> int:
        measurements.append(folder)

        return MIN_FREE_BYTES

    Inbox(measure).store(tmp_path, "small.bin", [b"a", b"b", b"c"])

    assert measurements == [tmp_path]


def test_interrupted_upload_leaves_nothing(tmp_path: Path) -> None:
    def interrupted_blocks() -> Iterator[bytes]:
        yield b"first block"
        raise BodyError("connection closed")

    with pytest.raises(BodyError):
        Inbox(plenty_of_space).store(tmp_path, "cut.bin", interrupted_blocks())

    assert list(tmp_path.iterdir()) == []


def test_leftovers_go_and_user_files_stay(tmp_path: Path) -> None:
    (tmp_path / PART_NAME).touch()
    (tmp_path / "keep.part").touch()

    remove_leftovers(tmp_path)

    assert [path.name for path in tmp_path.iterdir()] == ["keep.part"]


def test_removing_leftovers_of_a_missing_folder_does_nothing(tmp_path: Path) -> None:
    remove_leftovers(tmp_path / "missing")

    assert list(tmp_path.iterdir()) == []
