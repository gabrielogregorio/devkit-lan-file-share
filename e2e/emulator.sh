#!/usr/bin/env bash
# Local emulator for the E2E, headless and capped in memory. CI has its own action for this.
#   e2e/emulator.sh        creates the AVD if needed, boots it and waits until Android is ready
#   e2e/emulator.sh stop   shuts it down
# E2E_EMULATOR_PORT picks the console port when another emulator already uses 5554. Only this project's
# AVD is ever stopped.
set -euo pipefail
SDK=${ANDROID_HOME:-$HOME/Android/Sdk}
AVD=lan-file-share-api34
IMAGE="system-images;android-34;google_apis;x86_64"
CONSOLE_PORT=${E2E_EMULATOR_PORT:-5554}
SERIAL=emulator-$CONSOLE_PORT
ADB="$SDK/platform-tools/adb -s $SERIAL"
RAM_MB=${E2E_EMULATOR_RAM_MB:-3072}
LOG=$(dirname "$0")/out/emulator.log

running_avd() {
  $ADB emu avd name 2>/dev/null | head -1 | tr -d '\r'
}

if [ "${1:-}" = stop ]; then
  if [ "$(running_avd)" != "$AVD" ]; then
    echo "$SERIAL is not $AVD: left alone" >&2
    exit 1
  fi
  $ADB emu kill
  exit 0
fi

current=$(running_avd || true)
if [ -n "$current" ]; then
  echo "$SERIAL already runs $current. Pick another port with E2E_EMULATOR_PORT=5556" >&2
  exit 1
fi
if ! "$SDK/emulator/emulator" -list-avds | grep -qx "$AVD"; then
  echo "n" | "$SDK/cmdline-tools/latest/bin/avdmanager" create avd --name "$AVD" --package "$IMAGE" --device pixel_6
fi
limit=()
if command -v systemd-run > /dev/null && systemctl --user is-active default.target > /dev/null 2>&1; then
  limit=(systemd-run --user --scope --quiet -p "MemoryMax=$((RAM_MB + 1024))M")
fi
mkdir -p "$(dirname "$LOG")"
# shellcheck disable=SC2086
setsid nohup "${limit[@]}" "$SDK/emulator/emulator" -avd "$AVD" -port "$CONSOLE_PORT" -no-window \
  -gpu swiftshader_indirect -no-audio -no-boot-anim -no-metrics -no-snapshot -cores "${E2E_EMULATOR_CORES:-3}" \
  -memory "$RAM_MB" -partition-size 3072 ${E2E_EMULATOR_ARGS:-} > "$LOG" 2>&1 < /dev/null &
echo "booting $AVD on $SERIAL ($RAM_MB MB)"
for second in $(seq 1 300); do
  if [ "$($ADB shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = 1 ]; then
    echo "ready in ${second}s"
    exit 0
  fi
  if [ $((second % 30)) = 0 ]; then
    echo "still booting, ${second}s"
  fi
  sleep 1
done
echo "emulator did not boot, see $LOG" >&2
exit 1
