import json
from dataclasses import dataclass
from pathlib import Path

from server.private_file import write_private

DEFAULT_PASSWORD = "1234"  # noqa: S105 - only bootstraps pairing; the README tells to change it
DEFAULT_FOLDER = "~/devkit-lan-file-share"
CONFIG_FILE = "config.json"


@dataclass(frozen=True)
class AppConfig:
    folder: str
    password: str

    @property
    def target_folder(self) -> Path:
        return Path(self.folder).expanduser()


def _read_saved(config_dir: Path) -> dict[str, str]:
    try:
        saved = json.loads((config_dir / CONFIG_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}

    return saved if isinstance(saved, dict) else {}


def load_config(config_dir: Path) -> AppConfig:
    saved = _read_saved(config_dir)

    return AppConfig(folder=saved.get("folder") or DEFAULT_FOLDER, password=saved.get("password") or DEFAULT_PASSWORD)


def save_config(config_dir: Path, **changes: str) -> None:
    current = load_config(config_dir)
    merged = {"folder": current.folder, "password": current.password, **changes}
    write_private(config_dir / CONFIG_FILE, json.dumps(merged, indent=2) + "\n")
