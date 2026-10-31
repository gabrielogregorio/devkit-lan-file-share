from pathlib import Path

from server.settings import APP_SLUG
from tray.icons import icon_svg, write_icons

BRAND_COLOR = "#2f80ed"


def test_icon_is_colored_on_air() -> None:
    assert BRAND_COLOR in icon_svg("on")


def test_icon_is_gray_when_off() -> None:
    assert BRAND_COLOR not in icon_svg("off")
    assert "#9a9a9a" in icon_svg("off")


def test_both_states_are_written(tmp_path: Path) -> None:
    write_icons(tmp_path / "icons")

    written = sorted(path.name for path in (tmp_path / "icons").iterdir())
    assert written == [f"{APP_SLUG}-off.svg", f"{APP_SLUG}-on.svg"]
