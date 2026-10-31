#!/usr/bin/env bash
# Single runner for the LAN File Share test suite. Same commands the CI runs.
#
#   ./run-tests.sh            -> lint + types + PC tests + app tests (JUnit against the real server)
#   RUN_E2E=1 ./run-tests.sh  -> also the APK on the emulator (needs e2e/emulator.sh running)
#
# Without RUN_E2E it needs neither a phone nor an emulator, and touches neither port 8908 nor the real config.
set -u
cd "$(dirname "$0")" || exit

PY="${PY:-.venv/bin/python}"
FAILED=0
declare -a RESULTS

bar() { printf '%s\n' "------------------------------------------------------------"; }
run_layer() {  # run_layer <name> <command...>
  local name="$1"; shift
  bar; echo ">> $name"; bar
  if "$@"; then RESULTS+=("PASS  $name"); else RESULTS+=("FAIL  $name"); FAILED=1; fi
}

run_layer "lint     (ruff)" "$PY" -m ruff check .
run_layer "types    (mypy)" "$PY" -m mypy server tray tray_icon.py tests conftest.py
if command -v shellcheck > /dev/null; then
  run_layer "lint     (shellcheck)" shellcheck --severity=warning ./*.sh android/*.sh e2e/*.sh
else
  RESULTS+=("SKIP  lint (shellcheck) - sudo apt install shellcheck")
fi

run_layer "pc       (pytest)" "$PY" -m pytest -q
run_layer "app      (JUnit)" android/test.sh

if [ "${RUN_E2E:-0}" = "1" ]; then
  run_layer "e2e      (emulator, Maestro)" "$PY" e2e/run.py
else
  RESULTS+=("SKIP  e2e (emulator) - RUN_E2E=1 to run it")
fi

echo ""; bar; echo "SCOREBOARD"; bar
for result in "${RESULTS[@]}"; do echo "  $result"; done
bar
if [ "$FAILED" -eq 0 ]; then echo "ALL GREEN"; else echo "FAILURES"; fi
exit "$FAILED"
