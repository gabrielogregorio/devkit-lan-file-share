#!/usr/bin/env bash
# Builds the APK with the SDK tools alone, no gradle.
#   ./build.sh           APK in build/, with its signature checked and its SHA-256 alongside
#   ./build.sh install   also installs it over adb, after re-checking both
# Debug key by default. With ANDROID_KEYSTORE, ANDROID_KEYSTORE_PASSWORD and ANDROID_KEY_ALIAS set it
# is a release build signed with that key, which is what the release workflow does.
set -euo pipefail
cd "$(dirname "$0")"
SDK=${ANDROID_HOME:-$HOME/Android/Sdk}
BUILD_TOOLS=$SDK/build-tools/36.0.0
ANDROID_JAR=$SDK/platforms/android-36/android.jar
JDK=${JDK_BIN:-/snap/android-studio/current/jbr/bin}
VERSION=$(tr -d '[:space:]' < ../VERSION)
VERSION_CODE=$(awk -F. '{print $1*10000 + $2*100 + $3}' <<< "${VERSION%%-*}")
PACKAGE=com.devkit.lanfileshare
ZXING=libs/zxing-core-3.5.3.jar
APK=build/lan-file-share.apk

DEBUG_FLAG=()
if [ -n "${ANDROID_KEYSTORE:-}" ]; then
  KEYSTORE=$ANDROID_KEYSTORE
  KEYSTORE_PASSWORD=${ANDROID_KEYSTORE_PASSWORD:?needs ANDROID_KEYSTORE_PASSWORD}
  KEY_ALIAS=${ANDROID_KEY_ALIAS:?needs ANDROID_KEY_ALIAS}
else
  DEBUG_FLAG=(--debug-mode)
  KEYSTORE=$HOME/.android/debug.keystore
  KEYSTORE_PASSWORD=android
  KEY_ALIAS=androiddebugkey
  if [ ! -f "$KEYSTORE" ]; then
    mkdir -p "$HOME/.android"
    "$JDK/keytool" -genkeypair -keystore "$KEYSTORE" -storepass android -keypass android -alias "$KEY_ALIAS" \
      -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Android Debug,O=Android,C=US"
  fi
fi

./fetch-libs.sh
rm -rf build && mkdir -p build/res build/classes build/dex build/gen
"$BUILD_TOOLS/aapt2" compile --dir res -o build/res/res.zip
"$BUILD_TOOLS/aapt2" link -I "$ANDROID_JAR" --manifest AndroidManifest.xml "${DEBUG_FLAG[@]}" \
  --version-code "$VERSION_CODE" --version-name "$VERSION" --java build/gen -o build/base.apk build/res/res.zip
# shellcheck disable=SC2046
"$JDK/javac" --release 11 -nowarn -classpath "$ANDROID_JAR:$ZXING" -d build/classes $(find src build/gen -name '*.java')
# shellcheck disable=SC2046
"$BUILD_TOOLS/d8" --release --lib "$ANDROID_JAR" --min-api 24 --output build/dex "$ZXING" \
  $(find build/classes -name '*.class')
cp build/base.apk build/unsigned.apk
(cd build/dex && zip -q ../unsigned.apk classes.dex)
"$BUILD_TOOLS/zipalign" -f 4 build/unsigned.apk build/aligned.apk
"$BUILD_TOOLS/apksigner" sign --ks "$KEYSTORE" --ks-key-alias "$KEY_ALIAS" --ks-pass "pass:$KEYSTORE_PASSWORD" \
  --key-pass "pass:$KEYSTORE_PASSWORD" --out "$APK" build/aligned.apk
"$BUILD_TOOLS/apksigner" verify "$APK"
(cd build && sha256sum "$(basename "$APK")" > "$(basename "$APK").sha256")
echo "APK: $(pwd)/$APK"
cat "$APK.sha256"
if [ "${1:-}" = install ]; then
  (cd build && sha256sum -c --quiet "$(basename "$APK").sha256")
  "$BUILD_TOOLS/apksigner" verify "$APK"
  adb install -r "$APK"
  adb shell am start -n "$PACKAGE/.MainActivity"
fi
