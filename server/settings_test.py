from pathlib import Path

import pytest

from server.settings import APP_SLUG, DEFAULT_PORT, detect_language, load_settings


def test_defaults_live_under_the_home_folder() -> None:
    settings = load_settings({"HOME": "/home/person"})

    assert settings.port == DEFAULT_PORT
    assert settings.config_dir == Path("/home/person/.config") / APP_SLUG
    assert settings.cache_dir == Path("/home/person/.cache") / APP_SLUG
    assert settings.applications_dir == Path("/home/person/.local/share/applications")
    assert settings.autostart_dir == Path("/home/person/.config/autostart")


def test_variables_override_the_defaults() -> None:
    settings = load_settings({"HOME": "/h", "LFS_PORT": "9000", "LFS_CONFIG_DIR": "/c", "LFS_NAME": "office"})

    assert (settings.port, settings.config_dir, settings.pc_name) == (9000, Path("/c"), "office")


def test_xdg_folders_are_respected() -> None:
    settings = load_settings({"HOME": "/h", "XDG_CONFIG_HOME": "/x/config", "XDG_CACHE_HOME": "/x/cache"})

    assert settings.config_dir == Path("/x/config") / APP_SLUG
    assert settings.cache_dir == Path("/x/cache") / APP_SLUG


@pytest.mark.parametrize(
    ("environment", "expected"),
    [
        ({"LANG": "pt_BR.UTF-8"}, "pt-BR"),
        ({"LANGUAGE": "pt_BR:en"}, "pt-BR"),
        ({"LFS_LANG": "en", "LANG": "pt_BR.UTF-8"}, "en"),
        ({"LANG": "de_DE.UTF-8"}, "en"),
        ({}, "en"),
    ],
)
def test_language_follows_the_first_variable_set(environment: dict[str, str], expected: str) -> None:
    assert detect_language(environment) == expected
