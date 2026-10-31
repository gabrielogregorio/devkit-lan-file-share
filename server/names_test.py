import pytest

from server.names import (
    FALLBACK_DEVICE_LABEL,
    FALLBACK_FILE_NAME,
    MAX_EXTENSION_BYTES,
    MAX_LABEL_CHARACTERS,
    MAX_STEM_BYTES,
    clean_device_label,
    sanitize_file_name,
)


@pytest.mark.parametrize(
    ("raw_name", "expected"),
    [
        ("../../etc/passwd", "passwd"),
        ("..\\..\\win.ini", "win.ini"),
        (".bashrc", "bashrc"),
        ("/absolute/report.pdf", "report.pdf"),
    ],
)
def test_folders_and_hidden_names_are_dropped(raw_name: str, expected: str) -> None:
    assert sanitize_file_name(raw_name) == expected


@pytest.mark.parametrize("raw_name", ["", "..", "/", "...", "\n\t", "folder/"])
def test_empty_names_get_the_fallback(raw_name: str) -> None:
    assert sanitize_file_name(raw_name) == FALLBACK_FILE_NAME


def test_accents_stay_and_control_characters_go() -> None:
    assert sanitize_file_name("relatório\x00\n final.pdf") == "relatório final.pdf"


def test_right_to_left_override_is_removed() -> None:
    assert sanitize_file_name("invoice\u202efdp.exe") == "invoicefdp.exe"


def test_long_stem_is_cut_on_a_character_and_keeps_the_extension() -> None:
    name = sanitize_file_name("á" * 400 + ".pdf")

    assert name.endswith(".pdf")
    assert len(name.encode()) <= MAX_STEM_BYTES + len(".pdf")


def test_long_extension_is_cut() -> None:
    name = sanitize_file_name("report." + "x" * 100)

    assert name == "report." + "x" * (MAX_EXTENSION_BYTES - 1)


def test_device_label_is_decoded_and_cleaned() -> None:
    assert clean_device_label("Pixel%20%C3%A9%208%00") == "Pixel é 8"


def test_device_label_has_a_limit() -> None:
    assert len(clean_device_label("x" * 100)) == MAX_LABEL_CHARACTERS


def test_empty_device_label_gets_the_fallback() -> None:
    assert clean_device_label("%00") == FALLBACK_DEVICE_LABEL
