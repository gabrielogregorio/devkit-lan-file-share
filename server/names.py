import os
from urllib.parse import unquote

FALLBACK_FILE_NAME = "file"
FALLBACK_DEVICE_LABEL = "?"
MAX_STEM_BYTES = 200
MAX_EXTENSION_BYTES = 32
MAX_LABEL_CHARACTERS = 40


def _printable(text: str) -> str:
    return "".join(character for character in text if character.isprintable())


def sanitize_file_name(raw_name: str) -> str:
    """Plain file name from what the phone sent: no folders, no hidden files, fits the filesystem."""
    last_part = raw_name.replace("\\", "/").rsplit("/", 1)[-1]
    name = _printable(last_part).strip().lstrip(".").strip()
    if not name:
        return FALLBACK_FILE_NAME

    stem, extension = os.path.splitext(name)
    short_extension = extension.encode()[:MAX_EXTENSION_BYTES].decode(errors="ignore")

    return stem.encode()[:MAX_STEM_BYTES].decode(errors="ignore").rstrip() + short_extension


def clean_device_label(raw_label: str) -> str:
    return _printable(unquote(raw_label)).strip()[:MAX_LABEL_CHARACTERS] or FALLBACK_DEVICE_LABEL
