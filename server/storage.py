import hashlib
import logging
import os
import re
import shutil
import threading
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

MIN_FREE_BYTES = 1024 ** 3  # a full disk freezes the whole PC: this much stays free no matter what
FREE_CHECK_INTERVAL_BYTES = 16 * 1024 ** 2
PART_FILE_PATTERN = re.compile(r"^\.[0-9a-f]{32}\.part$")
RECEIVED_FILE_MODE = 0o640  # never executable, whatever the phone sent
CREATE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW


class DiskAlmostFullError(Exception):
    """Writing more would eat into MIN_FREE_BYTES."""


@dataclass(frozen=True)
class StoredFile:
    name: str
    size: int
    sha256: str


def free_bytes(folder: Path) -> int:
    return shutil.disk_usage(folder).free


def unique_path(folder: Path, name: str) -> Path:
    target = folder / name
    stem, extension = os.path.splitext(name)
    copy_number = 1
    while os.path.lexists(target):
        target = folder / f"{stem} ({copy_number}){extension}"
        copy_number += 1

    return target


def remove_leftovers(folder: Path) -> None:
    """.part files of an upload cut short when the server was stopped."""
    if not folder.is_dir():
        return

    for path in folder.iterdir():
        if PART_FILE_PATTERN.match(path.name):
            path.unlink(missing_ok=True)


class Inbox:
    """Writes each upload to a hidden .part file, and only a complete one gets its real name."""

    def __init__(self, measure_free_bytes: Callable[[Path], int] = free_bytes) -> None:
        self.measure_free_bytes = measure_free_bytes
        self.name_lock = threading.Lock()

    def _write_blocks(self, part_path: Path, blocks: Iterable[bytes]) -> tuple[int, str]:
        digest = hashlib.sha256()
        size = 0
        next_check = 0
        descriptor = os.open(part_path, CREATE_FLAGS, RECEIVED_FILE_MODE)
        with os.fdopen(descriptor, "wb") as part_file:
            for block in blocks:
                if size >= next_check:
                    if self.measure_free_bytes(part_path.parent) < MIN_FREE_BYTES:
                        raise DiskAlmostFullError
                    next_check = size + FREE_CHECK_INTERVAL_BYTES
                part_file.write(block)
                digest.update(block)
                size += len(block)

        return size, digest.hexdigest()

    def store(self, folder: Path, name: str, blocks: Iterable[bytes]) -> StoredFile:
        folder.mkdir(parents=True, exist_ok=True)
        part_path = folder / f".{uuid.uuid4().hex}.part"
        try:
            size, sha256 = self._write_blocks(part_path, blocks)
            with self.name_lock:
                target = unique_path(folder, name)
                os.replace(part_path, target)
        finally:
            part_path.unlink(missing_ok=True)

        return StoredFile(name=target.name, size=size, sha256=sha256)
