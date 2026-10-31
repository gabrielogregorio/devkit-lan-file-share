from pathlib import Path

from server.settings import APP_SLUG

ICON_STATES = ("on", "off")
GRADIENT = ('<defs><linearGradient id="brand" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2f80ed"/>'
            '<stop offset="1" stop-color="#14b8a6"/></linearGradient></defs>')
FOLDER_PATH = "M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8z"
ARROW_PATH = "M11 9.5h2v4.3h2.6L12 17.6 8.4 13.8H11z"


def icon_svg(state: str) -> str:
    """The same mark as the phone app: gray when off, the brand gradient when on air."""
    is_on = state == "on"
    fill = "url(#brand)" if is_on else "#9a9a9a"
    detail = "#ffffff" if is_on else "#3a3a3a"
    definitions = GRADIENT if is_on else ""

    return ('<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24">'
            f'{definitions}<path d="{FOLDER_PATH}" fill="{fill}"/><path d="{ARROW_PATH}" fill="{detail}"/></svg>')


def write_icons(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for state in ICON_STATES:
        (folder / f"{APP_SLUG}-{state}.svg").write_text(icon_svg(state), encoding="utf-8")
