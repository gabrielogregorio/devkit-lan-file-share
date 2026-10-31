#!/usr/bin/env bash
# Installs the pinned Maestro in ~/.maestro. The download must match e2e/maestro.lock or nothing is unpacked.
set -euo pipefail
cd "$(dirname "$0")"
read -r VERSION HASH < <(grep -v '^#' maestro.lock)
TARGET="$HOME/.maestro/maestro/bin/maestro"
if [ -x "$TARGET" ] && [ "$("$TARGET" --version 2>/dev/null | tail -1)" = "$VERSION" ]; then
  echo "Maestro $VERSION already installed"
  exit 0
fi
ZIP=$(mktemp --suffix=.zip)
trap 'rm -f "$ZIP"' EXIT
curl -fsSL --proto '=https' -m 300 -o "$ZIP" \
  "https://github.com/mobile-dev-inc/maestro/releases/download/cli-$VERSION/maestro.zip"
if ! echo "$HASH  $ZIP" | sha256sum -c --quiet --status -; then
  echo "REFUSED: maestro.zip does not match e2e/maestro.lock" >&2
  exit 1
fi
mkdir -p "$HOME/.maestro"
unzip -q -o "$ZIP" -d "$HOME/.maestro"
echo "Maestro $VERSION installed"
