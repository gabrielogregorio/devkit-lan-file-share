import fcntl
import os
import signal
import subprocess
from pathlib import Path
from typing import TextIO

from tray.app_info import LOCK_PATH, NAME, REPO_ROOT


def parse_ss(output: str) -> list[int]:
    """PIDs in the output of `ss -ltnpH` (only the user's own processes show a pid)."""
    candidates = [chunk.split(",")[0] for chunk in output.split("pid=")[1:]]

    return [int(candidate) for candidate in candidates if candidate.isdigit()]


def pids_on_port(port: int) -> list[int]:
    try:
        done = subprocess.run(["ss", "-ltnpH", f"sport = :{port}"], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        return []

    return parse_ss(done.stdout)


def is_inside(path: str, folder: str) -> bool:
    return path == folder or path.startswith(folder + os.sep)


def belongs_to_app(pid: int, folder: str = str(REPO_ROOT), proc_root: str = "/proc") -> bool:
    """Is that process this app? Its cwd or its command line points into the folder."""
    try:
        if is_inside(os.readlink(f"{proc_root}/{pid}/cwd"), folder):
            return True

        return folder.encode() in Path(f"{proc_root}/{pid}/cmdline").read_bytes()
    except OSError:
        return False


def signal_group(group_id: int, signal_number: int = signal.SIGTERM) -> None:
    try:
        os.killpg(group_id, signal_number)
    except OSError:
        pass


def stop_process(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass


def single_instance(lock_path: Path = LOCK_PATH) -> TextIO | None:
    """Holds a lock for the whole run; None when another icon of this app is already up."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "w", encoding="utf-8")  # kept open on purpose: the lock lives with it
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()

        return None

    return handle


def notify(title: str, body: str = "") -> None:
    try:
        subprocess.Popen(["notify-send", "-a", NAME, title, body])
    except OSError:
        pass
