#!/usr/bin/env bash
# JUnit on the PC, no phone or emulator: unit tests of the classes free of the Android API, and an
# end to end suite that runs the app's real network code against the real server.
set -euo pipefail
cd "$(dirname "$0")"
if [ -n "${JDK_BIN:-}" ]; then
  JDK=$JDK_BIN/
elif [ -x /snap/android-studio/current/jbr/bin/javac ]; then
  JDK=/snap/android-studio/current/jbr/bin/
else
  JDK=""
fi
./fetch-libs.sh
LIBS=libs/junit-4.13.2.jar:libs/hamcrest-core-1.3.jar:libs/json-20240303.jar  # the phone has org.json built in
OUT=build/unit
rm -rf "$OUT" && mkdir -p "$OUT"
SOURCES=src/com/devkit/lanfileshare
PURE_CLASSES=(Protocol Names PairLink PairingPlan KeyRing PcClient Failure)
PURE_FILES=("${PURE_CLASSES[@]/#/$SOURCES/}")
PURE_FILES=("${PURE_FILES[@]/%/.java}")
"${JDK}javac" --release 11 -nowarn -classpath "$LIBS" -d "$OUT" "${PURE_FILES[@]}" test/com/devkit/lanfileshare/*.java
TESTS=$(cd test && find . -name '*Test.java' | sed 's|^\./||; s|\.java$||; s|/|.|g' | sort)
# shellcheck disable=SC2086
"${JDK}java" -classpath "$OUT:$LIBS" org.junit.runner.JUnitCore $TESTS
