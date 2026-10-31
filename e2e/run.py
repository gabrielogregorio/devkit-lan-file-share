#!/usr/bin/env python3
"""End to end on an Android EMULATOR: the real APK, the real server, Maestro on the screen.

The same script runs locally and in CI. Between flows it does what the phone cannot see: it checks
the files on disk by hash, revokes keys and stops the server. The server has a throwaway config, but
runs on the real port so discovery is tested too; the emulator reaches this PC at 10.0.2.2.

Three refusals protect real data. Anything that is not an emulator is refused, even with a phone plugged
in. An emulator of another project is refused, since this script installs an app and changes settings.
A server already on port 8908 is refused too: the emulator's broadcast would find it and pair with it.

    e2e/emulator.sh && e2e/run.py          all flows
    e2e/run.py pair-by-link share-sheet    only these steps
"""

import hashlib
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from server.certificate import CERTIFICATE_FILE, certificate_fingerprint  # noqa: E402
from server.config_store import save_config  # noqa: E402
from server.keys import KeyStore  # noqa: E402
from server.settings import DEFAULT_PORT  # noqa: E402

SERIAL = os.environ.get("E2E_DEVICE", "emulator-5554")
PACKAGE = "com.devkit.lanfileshare"
PORT = DEFAULT_PORT
AVD = "lan-file-share-api34"
PC_NAME = "e2e-pc"
PASSWORD = "e2e-password"
HOST_FROM_EMULATOR = "10.0.2.2"
LOCKOUT_SECONDS = 31
APK = ROOT / "android/build/lan-file-share.apk"
OUT = ROOT / "e2e/out"
MAESTRO = shutil.which("maestro") or str(Path.home() / ".maestro/maestro/bin/maestro")
DOWNLOADS = "/sdcard/Download"
SDK = Path(os.environ.get("ANDROID_HOME", Path.home() / "Android/Sdk"))
LAST_EMULATOR_WITH_DISCOVERY = 36
DOWNLOADS_URI = "content://com.android.externalstorage.documents/document/primary%3ADownload"


def say(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def adb(*args: str, timeout: int = 60, check: bool = True) -> str:
    done = subprocess.run(["adb", "-s", SERIAL, *args], capture_output=True, text=True, timeout=timeout)
    if check and done.returncode:
        raise RuntimeError(f'adb "{" ".join(args)}": {done.stderr or done.stdout}')

    return done.stdout


def wait_for(check: Callable[[], bool], what: str, seconds: int = 30) -> None:
    limit = time.monotonic() + seconds
    while time.monotonic() < limit:
        if check():
            return
        time.sleep(0.5)

    raise AssertionError(f'timed out waiting for "{what}"')


def refuse_real_server() -> None:
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex(("127.0.0.1", PORT)) == 0:
            sys.exit(f"refused: port {PORT} is in use. Turn off the LAN File Share icon first: "
                     "the emulator would find that server and pair with it.")


def refuse_emulator_without_discovery() -> None:
    properties = SDK / "emulator/source.properties"
    revision = re.search(r"Pkg\.Revision=(\d+)", properties.read_text()) if properties.exists() else None
    if revision and int(revision.group(1)) > LAST_EMULATOR_WITH_DISCOVERY:
        sys.exit(f"refused: on emulator {revision.group(1)} the server's reply to a broadcast never gets back to "
                 "the app, so discovery cannot pass. Install the build pinned in the README.")


def refuse_other_devices() -> None:
    if not SERIAL.startswith("emulator-"):
        sys.exit(f'refused: "{SERIAL}" is not an emulator')
    if adb("shell", "getprop", "ro.kernel.qemu").strip() != "1":
        sys.exit(f'refused: "{SERIAL}" does not report itself as an emulator')
    running_avd = adb("emu", "avd", "name").splitlines()[0].strip()
    if running_avd != AVD:
        sys.exit(f'refused: "{SERIAL}" runs "{running_avd}", not "{AVD}". Use E2E_DEVICE for this project\'s emulator.')


class Pc:
    """The server on the test port, with its own config and folder."""

    def __init__(self, root: Path) -> None:
        self.config = root / "config"
        self.inbox = root / "inbox"
        save_config(self.config, folder=str(self.inbox), password=PASSWORD)
        self.process: subprocess.Popen[bytes] | None = None
        self.start()
        self.keys = KeyStore(self.config)
        self.fingerprint = certificate_fingerprint(self.config / CERTIFICATE_FILE)

    def start(self) -> None:
        environment = dict(os.environ, LFS_PORT=str(PORT), LFS_CONFIG_DIR=str(self.config), LFS_NAME=PC_NAME)
        with open(OUT / "server.log", "a", encoding="utf-8") as log:
            self.process = subprocess.Popen([sys.executable, "-u", "-m", "server.main"], cwd=ROOT, env=environment,
                                            stdout=log, stderr=log)
        wait_for((self.config / CERTIFICATE_FILE).exists, "the server")
        time.sleep(0.5)

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process.wait()

    def link(self) -> str:
        return (f"lanfileshare://pair?host={HOST_FROM_EMULATOR}&port={PORT}&fp={self.fingerprint}"
                f"&k={self.keys.current()['secret']}")

    def expect_file(self, name: str, body: bytes) -> None:
        target = self.inbox / name
        wait_for(lambda: target.exists() and target.stat().st_size == len(body), f"{name} on the PC", 90)
        assert hashlib.sha256(target.read_bytes()).digest() == hashlib.sha256(body).digest(), f'"{name}" differs'


def flow(name: str, **variables: str) -> None:
    """Runs one Maestro flow; reports and screenshots go to e2e/out."""
    say(f"flow {name}")
    command = [MAESTRO, "--device", SERIAL, "test", f"e2e/flows/{name}.yaml",
               "--test-output-dir", str(OUT / "maestro"), "--debug-output", str(OUT / "debug" / name),
               "--flatten-debug-output"]
    for variable, value in variables.items():
        command += ["-e", f"{variable}={value}"]
    subprocess.run(command, cwd=ROOT, check=True, timeout=300)


def push_file(name: str, size: int) -> bytes:
    """A file in Downloads, indexed: adb push skips the media index that the pickers read."""
    body = os.urandom(size)
    with tempfile.NamedTemporaryFile() as local:
        local.write(body)
        local.flush()
        adb("push", local.name, f"{DOWNLOADS}/{name}", timeout=120)
    # am broadcast can hang on the reply, so it goes to the background
    adb("shell", "am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE "
                 f"-d file://{DOWNLOADS}/{name} >/dev/null 2>&1 &")
    where = f"\"_display_name='{name}'\""
    wait_for(lambda: name in adb("shell", f"content query --uri content://media/external/file --where {where}"),
             f"{name} in the media index")

    return body


def share_text(text: str, subject: str) -> None:
    adb("shell", f"am start -a android.intent.action.SEND -t text/plain --es android.intent.extra.TEXT '{text}' "
                 f"--es android.intent.extra.SUBJECT '{subject}' -n {PACKAGE}/.ShareActivity")


def open_files_app() -> None:
    adb("shell", "am force-stop com.google.android.documentsui")
    adb("shell", "am start -a android.intent.action.VIEW -t vnd.android.document/directory "
                 f"-d {DOWNLOADS_URI}")


def clear_app() -> None:
    adb("shell", f"pm clear {PACKAGE}")
    adb("shell", f"pm grant {PACKAGE} android.permission.POST_NOTIFICATIONS")


def wait_for_wifi() -> None:
    """Without the emulator's Wi-Fi the broadcast never leaves, and it connects a while after boot."""
    say("waiting for the emulator's Wi-Fi")
    adb("shell", "svc wifi enable")
    wait_for(lambda: "dev wlan0" in adb("shell", "ip route get 8.8.8.8", check=False), "the emulator's Wi-Fi", 180)


def prepare_emulator() -> None:
    wait_for_wifi()
    say("building the APK from the current code")
    subprocess.run(["android/build.sh"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    say("installing the APK")
    subprocess.run(["sha256sum", "-c", "--quiet", "lan-file-share.apk.sha256"], cwd=APK.parent, check=True)
    adb("install", "-r", str(APK), timeout=120)
    clear_app()
    # The system UI of a loaded emulator raises "isn't responding" over everything, and these two
    # sync right after boot. Neither has anything to do with the test.
    adb("shell", "settings put global hide_error_dialogs 1")
    for package in ("com.android.vending", "com.google.android.googlequicksearchbox"):
        adb("shell", f"pm disable-user --user 0 {package}", check=False)
    adb("logcat", "-c", check=False)


def step_pair_by_password(pc: Pc) -> None:
    flow("pair-by-password", PASSWORD=PASSWORD)
    assert len(pc.keys.all()) == 2, "pairing by password should issue a key"


def step_declined_link(pc: Pc) -> None:
    clear_app()
    before = len(pc.keys.all())
    flow("pair-link-declined", PAIR_LINK=pc.link())
    assert len(pc.keys.all()) == before, "a declined link must not pair"


def step_pair_by_link(pc: Pc) -> None:
    clear_app()
    before = len(pc.keys.all())
    flow("pair-by-link", PAIR_LINK=pc.link())
    assert len(pc.keys.all()) == before + 1, "pairing by link should rotate the key"


def step_share_sheet(pc: Pc) -> None:
    body = push_file("e2e relatório.pdf", 2_000_000)
    open_files_app()
    flow("share-sheet", FILE="e2e relatório.pdf")
    pc.expect_file("e2e relatório.pdf", body)


def step_share_text(pc: Pc) -> None:
    share_text("hello from the emulator", "e2e-note")
    pc.expect_file("e2e-note.txt", b"hello from the emulator")


def step_send_from_app(pc: Pc) -> None:
    body = push_file("e2e-big.bin", 30_000_000)
    flow("send-from-app", FILE="e2e-big.bin")
    pc.expect_file("e2e-big.bin", body)


def step_refused(pc: Pc) -> None:
    for record in pc.keys.all():
        pc.keys.revoke(record["id"])
    save_config(pc.config, password=os.urandom(8).hex())
    share_text("must not arrive", "e2e-refused")
    flow("refused")
    assert not (pc.inbox / "e2e-refused.txt").exists(), "a refused share reached the PC"
    save_config(pc.config, password=PASSWORD)
    time.sleep(LOCKOUT_SECONDS)  # the failed tries above may have locked this address out
    pc.keys.issue("e2e")


def step_offline_and_back(pc: Pc) -> None:
    clear_app()
    flow("pair-by-link", PAIR_LINK=pc.link())
    pc.stop()
    flow("pc-offline")
    pc.start()
    flow("pc-back")


STEPS: dict[str, Callable[[Pc], None]] = {
    "pair-by-password": step_pair_by_password,
    "declined-link": step_declined_link,
    "pair-by-link": step_pair_by_link,
    "share-sheet": step_share_sheet,
    "share-text": step_share_text,
    "send-from-app": step_send_from_app,
    "refused": step_refused,
    "offline-and-back": step_offline_and_back,
}


def main() -> None:
    refuse_emulator_without_discovery()
    refuse_other_devices()
    refuse_real_server()
    chosen = sys.argv[1:] or list(STEPS)
    unknown = set(chosen) - set(STEPS)
    if unknown:
        sys.exit(f"unknown steps: {sorted(unknown)}; available: {list(STEPS)}")
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    prepare_emulator()
    with tempfile.TemporaryDirectory() as tmp:
        pc = Pc(Path(tmp))
        passed = []
        try:
            for name in chosen:
                say(f"step {name}")
                STEPS[name](pc)
                passed.append(name)
            crashes = adb("logcat", "-d", "-b", "crash")
            assert "FATAL EXCEPTION" not in crashes, crashes
        except BaseException:
            (OUT / "logcat.txt").write_text(adb("logcat", "-d", check=False))
            (OUT / "logcat-crash.txt").write_text(adb("logcat", "-d", "-b", "crash", check=False))
            raise
        finally:
            pc.stop()
            say(f"passed {len(passed)} of {len(chosen)}: {', '.join(passed)}")


if __name__ == "__main__":
    main()
