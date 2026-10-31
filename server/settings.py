"""The only module that reads the environment: everything else receives its values from here."""

import os
import socket
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

APP_SLUG = "devkit-lan-file-share"
DEFAULT_PORT = 8908
LANGUAGE_VARIABLES = ("LFS_LANG", "LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")


@dataclass(frozen=True)
class Settings:
    port: int
    config_dir: Path
    cache_dir: Path
    applications_dir: Path
    autostart_dir: Path
    pc_name: str
    language: str


def detect_language(environment: Mapping[str, str]) -> str:
    for variable in LANGUAGE_VARIABLES:
        value = environment.get(variable, "")
        if value:
            return "pt-BR" if value.split(":")[0].lower().startswith("pt") else "en"

    return "en"


def load_settings(environment: Mapping[str, str] = os.environ) -> Settings:
    home = Path(environment.get("HOME") or Path.home())
    config_home = Path(environment.get("XDG_CONFIG_HOME") or home / ".config")
    cache_home = Path(environment.get("XDG_CACHE_HOME") or home / ".cache")
    data_home = Path(environment.get("XDG_DATA_HOME") or home / ".local" / "share")

    return Settings(
        port=int(environment.get("LFS_PORT") or DEFAULT_PORT),
        config_dir=Path(environment.get("LFS_CONFIG_DIR") or config_home / APP_SLUG),
        cache_dir=cache_home / APP_SLUG,
        applications_dir=data_home / "applications",
        autostart_dir=config_home / "autostart",
        pc_name=environment.get("LFS_NAME") or socket.gethostname(),
        language=detect_language(environment),
    )


SETTINGS = load_settings()
