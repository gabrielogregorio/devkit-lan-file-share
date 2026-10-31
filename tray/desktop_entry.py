from pathlib import Path

from server.settings import APP_SLUG, SETTINGS, Settings
from tray.app_info import ABOUT, ICONS_DIR, NAME, ON_ICON, REPO_ROOT
from tray.icons import write_icons

DESKTOP_FILE = f"{APP_SLUG}-tray.desktop"


def desktop_paths(settings: Settings = SETTINGS) -> tuple[Path, Path]:
    return settings.applications_dir / DESKTOP_FILE, settings.autostart_dir / DESKTOP_FILE


def desktop_entry() -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={NAME}\n"
        f"Comment=Top bar icon that turns {NAME} on and off: {ABOUT}\n"
        f"Exec=/usr/bin/python3 {REPO_ROOT / 'tray_icon.py'}\n"
        f"Icon={ICONS_DIR / (ON_ICON + '.svg')}\n"
        "Terminal=false\n"
        "Categories=Utility;\n"
        "StartupNotify=false\n"
        "X-GNOME-Autostart-Delay=3\n"
    )


def install(settings: Settings = SETTINGS) -> None:
    write_icons(ICONS_DIR)
    for path in desktop_paths(settings):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(desktop_entry(), encoding="utf-8")
        print(f'written: "{path}"')


def remove(settings: Settings = SETTINGS) -> None:
    for path in desktop_paths(settings):
        if path.exists():
            path.unlink()
            print(f'removed: "{path}"')
