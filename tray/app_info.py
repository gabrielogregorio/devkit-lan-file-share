from pathlib import Path

from server.settings import APP_SLUG, SETTINGS

NAME = "LAN File Share"
ABOUT = "phone to PC files"  # what it is, next to the name on the menu
REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER_COMMAND = ["./run.sh"]
ICONS_DIR = SETTINGS.cache_dir / "icons"
LOG_PATH = SETTINGS.cache_dir / "server.log"
LOCK_PATH = SETTINGS.cache_dir / "tray.lock"
ON_ICON = f"{APP_SLUG}-on"
OFF_ICON = f"{APP_SLUG}-off"
