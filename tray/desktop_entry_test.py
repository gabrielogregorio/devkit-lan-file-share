from pathlib import Path

from server.settings import load_settings
from tray.app_info import NAME, REPO_ROOT
from tray.desktop_entry import DESKTOP_FILE, desktop_entry, install, remove


def test_entry_starts_the_icon_with_the_system_python() -> None:
    assert f"Exec=/usr/bin/python3 {REPO_ROOT / 'tray_icon.py'}\n" in desktop_entry()
    assert f"Name={NAME}\n" in desktop_entry()


def test_install_writes_the_shortcut_and_the_login_entry_and_remove_undoes_it(tmp_path: Path) -> None:
    settings = load_settings({"HOME": str(tmp_path)})
    shortcut = settings.applications_dir / DESKTOP_FILE
    login_entry = settings.autostart_dir / DESKTOP_FILE

    install(settings)

    assert shortcut.read_text(encoding="utf-8") == desktop_entry()
    assert login_entry.read_text(encoding="utf-8") == desktop_entry()

    remove(settings)

    assert not shortcut.exists()
    assert not login_entry.exists()
