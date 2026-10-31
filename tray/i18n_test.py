import ast
import re
from pathlib import Path

import pytest

from tray.app_info import ABOUT
from tray.i18n import PT_BR, tr

TRAY_FOLDER = Path(__file__).parent
LOOKED_UP_THROUGH_A_VARIABLE = {ABOUT, "current", "old", "revoked", "On the phone: {ip}:{port}", "Address: {ip}:{port}"}
PLACEHOLDER = re.compile(r"{\w{1,20}}")


def texts_passed_to_tr() -> set[str]:
    used: set[str] = set()
    for source_path in TRAY_FOLDER.glob("*.py"):
        for node in ast.walk(ast.parse(source_path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or getattr(node.func, "id", "") != "tr":
                continue
            first_argument = node.args[0] if node.args else None
            if isinstance(first_argument, ast.Constant) and isinstance(first_argument.value, str):
                used.add(first_argument.value)

    return used


def test_every_text_has_a_translation_and_no_translation_is_unused() -> None:
    assert texts_passed_to_tr() | LOOKED_UP_THROUGH_A_VARIABLE == set(PT_BR)


@pytest.mark.parametrize(("english", "portuguese"), PT_BR.items())
def test_placeholders_match(english: str, portuguese: str) -> None:
    assert sorted(PLACEHOLDER.findall(english)) == sorted(PLACEHOLDER.findall(portuguese))


def test_english_text_is_its_own_key() -> None:
    assert tr("Keys", language="en") == "Keys"


def test_portuguese_text_comes_from_the_table() -> None:
    assert tr("Keys", language="pt-BR") == "Chaves"


def test_values_fill_the_placeholders() -> None:
    assert tr("Folder: {folder}", language="pt-BR", folder="~/x") == "Pasta: ~/x"
