import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SYSTEM_PYTHON = "/usr/bin/python3"
SECONDS_TO_OPEN = 3


def system_gtk_is_available() -> bool:
    probe = [SYSTEM_PYTHON, "-c", "import gi; gi.require_version('AyatanaAppIndicator3', '0.1')"]

    return subprocess.run(probe, capture_output=True, check=False).returncode == 0


@pytest.mark.skipif(not shutil.which("xvfb-run") or not system_gtk_is_available(), reason="needs xvfb and GTK")
def test_panel_opens_on_a_virtual_screen_without_errors(tmp_path: Path) -> None:
    environment = dict(os.environ, LFS_CONFIG_DIR=str(tmp_path), XDG_CACHE_HOME=str(tmp_path), LFS_PORT="18908")
    environment.pop("DBUS_SESSION_BUS_ADDRESS", None)
    process = subprocess.Popen(
        ["xvfb-run", "-a", "dbus-run-session", "--", SYSTEM_PYTHON, "tray_icon.py", "--panel"],
        cwd=ROOT, env=environment, stderr=subprocess.PIPE, text=True, start_new_session=True)

    time.sleep(SECONDS_TO_OPEN)
    still_running = process.poll() is None
    if still_running:
        os.killpg(process.pid, signal.SIGTERM)
    _, errors = process.communicate(timeout=10)

    assert still_running, errors
    assert "Traceback" not in errors
