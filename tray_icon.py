#!/usr/bin/env python3
"""Top bar icon for LAN File Share: turns the receiving server on and off.

    ./tray_icon.py             show the icon (a 2nd run exits: one icon per app)
    ./tray_icon.py --panel     same, opening the panel right away
    ./tray_icon.py --install   start the icon at login + app menu shortcut
    ./tray_icon.py --remove    undo --install
"""

import sys

from tray.app_info import NAME
from tray.desktop_entry import install, remove
from tray.process import single_instance


def main(arguments: list[str]) -> int:
    if "--install" in arguments:
        install()

        return 0
    if "--remove" in arguments:
        remove()

        return 0

    instance_lock = single_instance()
    if instance_lock is None:
        print(f"{NAME}: the icon is already on the bar")

        return 0

    from tray.indicator import run_icon  # needs GTK: the tests and --install run without it

    run_icon("--panel" in arguments)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
