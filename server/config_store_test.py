import os
from pathlib import Path

from server.config_store import CONFIG_FILE, DEFAULT_FOLDER, DEFAULT_PASSWORD, load_config, save_config


def test_missing_file_gives_the_defaults(tmp_path: Path) -> None:
    config = load_config(tmp_path)

    assert (config.folder, config.password) == (DEFAULT_FOLDER, DEFAULT_PASSWORD)


def test_broken_file_gives_the_defaults(tmp_path: Path) -> None:
    (tmp_path / CONFIG_FILE).write_text("[not json", encoding="utf-8")

    assert load_config(tmp_path).password == DEFAULT_PASSWORD


def test_saving_one_value_keeps_the_other(tmp_path: Path) -> None:
    save_config(tmp_path, folder="/somewhere")
    save_config(tmp_path, password="new-password")

    config = load_config(tmp_path)
    assert (config.folder, config.password) == ("/somewhere", "new-password")


def test_saved_file_is_private(tmp_path: Path) -> None:
    save_config(tmp_path, password="new-password")

    assert os.stat(tmp_path / CONFIG_FILE).st_mode & 0o777 == 0o600


def test_home_in_the_folder_is_expanded(tmp_path: Path) -> None:
    save_config(tmp_path, folder="~/received")

    assert load_config(tmp_path).target_folder == Path.home() / "received"
