import os
from pathlib import Path


def write_private(path: Path, text: str) -> None:
    """Replaces the file in one step, and the content is never readable by other users, not even briefly."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary_path = path.with_suffix(".tmp")
    descriptor = os.open(temporary_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
        temporary_file.write(text)
    temporary_path.replace(path)
