# 6. End to end on an emulator, with Maestro

**Status:** accepted

The E2E has to run in CI, so it cannot depend on a phone. `e2e/run.py` drives the real APK on an emulator through
Maestro against the real server, and checks what the screen cannot show: files on disk by hash, keys issued, nothing
written after a refusal. The same script runs locally and in CI.

**Consequences:** the share sheet is tested with another app as the sender, because `adb shell` cannot grant read access
to a shared file. The emulator's UDP broadcast reaches the host, so the test server uses the real port and the
script refuses to start when that port is busy. The camera image is not covered: the emulator's virtual scene shows
the scanner working, but cannot aim at a QR code without its window.
