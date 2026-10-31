#!/usr/bin/env python3
"""Records the README GIFs and screenshots: one session with the app on the emulator and the panel on Xvfb.

Everything runs on a throwaway home folder, so the QR code and the keys in the images open nothing.
Needs e2e/emulator.sh running, port 8908 free, ffmpeg, Xvfb and python3-segno.
"""

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import run
from run import ROOT, adb, flow, open_files_app, push_file, say, wait_for

from server.certificate import certificate_fingerprint, ensure_certificate
from server.config_store import save_config
from server.keys import KeyStore
from server.settings import APP_SLUG

DEMO_ROOT = run.OUT / "demo"
DEMO_HOME = DEMO_ROOT / "home"
DOCS = ROOT / "docs"
DISPLAY = ":77"
SCREEN = "680x790"
PC_NAME = "my-pc"
SHARED_FILE = "quarterly report.pdf"
SHARED_FILE_BYTES = 2_400_000
PHONE_VIDEO = "/sdcard/demo.mp4"
SYSTEM_PYTHON = "/usr/bin/python3"
GIF_FPS = 8
PHONE_SPEED = 1.6
PANEL_SPEED = 3.0
PHONE_IDLE_SECONDS = 11
PANEL_IDLE_SECONDS = 8
GIF_COLORS = 64


def segno_folder() -> str:
    code = "import os, segno; print(os.path.dirname(os.path.dirname(segno.__file__)))"

    return subprocess.run([SYSTEM_PYTHON, "-c", code], capture_output=True, text=True, check=True).stdout.strip()


def demo_environment() -> dict[str, str]:
    return dict(os.environ, HOME=str(DEMO_HOME), LFS_NAME=PC_NAME, LFS_LANG="en", DISPLAY=DISPLAY,
                PYTHONPATH=segno_folder(), XDG_CONFIG_HOME="", XDG_CACHE_HOME="", XDG_DATA_HOME="")


def to_gif(video: Path, target: Path, width: int, speed: float, start_seconds: int = 0) -> None:
    filters = (f"setpts=PTS/{speed},fps={GIF_FPS},scale={width}:-1:flags=lanczos,split[first][second];"
               f"[first]palettegen=max_colors={GIF_COLORS}:stats_mode=diff[palette];"
               "[second][palette]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(start_seconds), "-i", str(video),
                    "-filter_complex", filters, str(target)], check=True)
    say(f'{target.name}: {target.stat().st_size // 1024} KB')


def stop_group(process: subprocess.Popen[bytes], signal_number: int = signal.SIGTERM) -> None:
    os.killpg(process.pid, signal_number)
    process.wait(timeout=15)


def main() -> None:
    run.refuse_other_devices()
    run.refuse_real_server()
    shutil.rmtree(DEMO_ROOT, ignore_errors=True)
    config_dir = DEMO_HOME / ".config" / APP_SLUG
    save_config(config_dir, folder=str(DEMO_HOME / APP_SLUG), password=os.urandom(8).hex())
    certificate_path, _ = ensure_certificate(config_dir)
    link = (f"lanfileshare://pair?host={run.HOST_FROM_EMULATOR}&port={run.PORT}"
            f"&fp={certificate_fingerprint(certificate_path)}&k={KeyStore(config_dir).current()['secret']}")
    environment = demo_environment()
    background: dict[str, Any] = {"cwd": ROOT, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
                                  "start_new_session": True}

    run.clear_app()
    adb("shell", "input keyevent KEYCODE_HOME")
    body = push_file(SHARED_FILE, SHARED_FILE_BYTES)
    screen = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", f"{SCREEN}x24"], **background)
    server = subprocess.Popen([sys.executable, "-u", "-m", "server.main"], env=environment, **background)
    tray = subprocess.Popen(["dbus-run-session", "--", SYSTEM_PYTHON, "tray_icon.py", "--panel"], env=environment,
                            **background)
    time.sleep(4)
    panel_video = DEMO_ROOT / "panel.mp4"
    panel_recorder = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "x11grab", "-draw_mouse", "0", "-framerate", "10",
         "-video_size", SCREEN,
         "-i", DISPLAY, "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(panel_video)],
        cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)
    phone_recorder = subprocess.Popen(
        ["adb", "-s", run.SERIAL, "shell", "screenrecord", "--size", "540x1200", "--bit-rate", "1500000",
         PHONE_VIDEO],
        start_new_session=True)
    try:
        time.sleep(2)
        flow("demo/pair", PAIR_LINK=link)
        time.sleep(3)
        open_files_app()
        flow("demo/share", FILE=SHARED_FILE)
        target = DEMO_HOME / APP_SLUG / SHARED_FILE
        wait_for(lambda: target.exists() and target.stat().st_size == len(body), "the shared file", 60)
        flow("demo/result", FILE=SHARED_FILE)
        time.sleep(3)
    finally:
        adb("shell", "pkill -INT screenrecord", check=False)
        phone_recorder.wait(timeout=20)
        assert panel_recorder.stdin is not None
        panel_recorder.stdin.write(b"q")
        panel_recorder.stdin.close()
        panel_recorder.wait(timeout=20)
        for process in (tray, server, screen):
            stop_group(process)
    time.sleep(2)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.5", "-i", str(panel_video), "-frames:v", "1",
                    "-update", "1", str(DOCS / "pc-panel.png")], check=True)
    adb("pull", PHONE_VIDEO, str(DEMO_ROOT / "phone.mp4"), timeout=60)
    (DOCS / "app-main.png").write_bytes(subprocess.run(
        ["adb", "-s", run.SERIAL, "exec-out", "screencap", "-p"], capture_output=True, check=True).stdout)
    to_gif(DEMO_ROOT / "phone.mp4", DOCS / "demo-phone.gif", 300, PHONE_SPEED, PHONE_IDLE_SECONDS)
    to_gif(panel_video, DOCS / "demo-panel.gif", 520, PANEL_SPEED, PANEL_IDLE_SECONDS)


if __name__ == "__main__":
    main()
