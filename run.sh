#!/usr/bin/env bash
# LAN File Share launcher: starts the receiving server (Ctrl+C stops it).
# Standard library only, so there is no venv to set up.
set -e
cd "$(dirname "$0")"
exec python3 -u -m server.main
