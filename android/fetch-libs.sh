#!/usr/bin/env bash
# Puts the pinned jars in libs/. A jar whose SHA-256 differs from libs.lock is refused and removed,
# whether it was just downloaded or was already there.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p libs
grep -v '^#' libs.lock | while read -r hash file path; do
  if [ ! -f "libs/$file" ]; then
    curl -fsSL --proto '=https' --max-time 60 -o "libs/$file" "https://repo1.maven.org/maven2/$path"
  fi
  if ! echo "$hash  libs/$file" | sha256sum -c --quiet --status -; then
    rm -f "libs/$file"
    echo "REFUSED: libs/$file does not match libs.lock" >&2
    exit 1
  fi
done
