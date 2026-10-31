import os
from pathlib import Path

from tray.process import belongs_to_app, parse_ss, single_instance

FOLDER = "/repositories/devkit-lan-file-share"


def fake_process(proc_root: Path, pid: int, working_dir: str, command_line: bytes = b"") -> None:
    process_folder = proc_root / str(pid)
    process_folder.mkdir()
    (process_folder / "cwd").symlink_to(working_dir)
    (process_folder / "cmdline").write_bytes(command_line)


def test_parse_ss_reads_every_pid() -> None:
    output = 'LISTEN 0 5 0.0.0.0:8908 0.0.0.0:* users:(("python3",pid=1234,fd=3),("python3",pid=77,fd=3))'

    assert parse_ss(output) == [1234, 77]


def test_parse_ss_without_a_pid_is_empty() -> None:
    assert parse_ss("LISTEN 0 5 0.0.0.0:8908 0.0.0.0:*") == []


def test_process_running_from_the_folder_belongs(tmp_path: Path) -> None:
    fake_process(tmp_path, 10, f"{FOLDER}/android")

    assert belongs_to_app(10, FOLDER, str(tmp_path))


def test_process_with_the_folder_in_its_command_line_belongs(tmp_path: Path) -> None:
    fake_process(tmp_path, 10, "/elsewhere", f"python3\0{FOLDER}/tray_icon.py".encode())

    assert belongs_to_app(10, FOLDER, str(tmp_path))


def test_a_sibling_folder_with_the_same_prefix_does_not_belong(tmp_path: Path) -> None:
    fake_process(tmp_path, 10, f"{FOLDER}-old")

    assert not belongs_to_app(10, FOLDER, str(tmp_path))


def test_process_that_is_gone_does_not_belong(tmp_path: Path) -> None:
    assert not belongs_to_app(10, FOLDER, str(tmp_path))


def test_only_one_instance_holds_the_lock(tmp_path: Path) -> None:
    lock_path = tmp_path / "tray.lock"
    first_lock = single_instance(lock_path)

    assert first_lock is not None
    assert single_instance(lock_path) is None
    first_lock.close()
    second_lock = single_instance(lock_path)
    assert second_lock is not None
    second_lock.close()


def test_current_process_is_found_by_its_own_folder() -> None:
    assert belongs_to_app(os.getpid(), os.getcwd())
