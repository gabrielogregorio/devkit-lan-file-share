#!/usr/bin/env bash
# Prints the version a release branch publishes, or refuses the branch.
#
#   .github/scripts/release-version.sh release/1.2.3  -> 1.2.3
#
# Runs on the PR, to fail before the merge, and on the merge, right before publishing.
set -euo pipefail

BRANCH="${1:?usage: release-version.sh release/X.Y.Z}"
VERSION="${BRANCH#release/}"
SEMVER='^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$'

refuse() {
  echo "::error::$1" >&2
  exit 1
}

if [[ "$BRANCH" != release/* || ! "$VERSION" =~ $SEMVER ]]; then
  refuse "'$BRANCH' is not a release branch: name it release/X.Y.Z or release/X.Y.Z-rc.1"
fi

FILE_VERSION=$(tr -d '[:space:]' < VERSION)
if [[ "$FILE_VERSION" != "$VERSION" ]]; then
  refuse "VERSION says '$FILE_VERSION' but the branch says '$VERSION': the app takes its version from that file"
fi

if git ls-remote --exit-code --tags origin "refs/tags/v$VERSION" > /dev/null; then
  refuse "v$VERSION is already released: raise the version in the branch name and in VERSION"
fi

echo "$VERSION"
