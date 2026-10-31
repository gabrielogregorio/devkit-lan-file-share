import re
import subprocess
import unicodedata
import xml.etree.ElementTree as ElementTree
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
STRINGS_PATH = ROOT / "android/res/values/strings.xml"
TRANSLATED_STRINGS_PATH = ROOT / "android/res/values-pt/strings.xml"
FLOWS_PATH = ROOT / "e2e/flows"
RESOURCES_PATH = ROOT / "android/res"
PLACEHOLDER = re.compile(r"%\d\$[sd]")
FLOW_ID = re.compile(r'id: "\.\*:id/(\w{1,60})"')
DECLARED_ID = re.compile(r'@\+id/(\w{1,60})')
EM_DASH = chr(0x2014)
HIDDEN_CHARACTER_CATEGORY = "Cf"
SETTINGS_MODULE = "server/settings.py"


def read_strings(path: Path) -> dict[str, str]:
    strings = ElementTree.parse(path).getroot().findall("string")

    return {entry.attrib["name"]: entry.text or "" for entry in strings
            if entry.attrib.get("translatable") != "false"}


def tracked_text_files() -> list[Path]:
    listed = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.splitlines()
    candidates = [ROOT / name for name in listed]

    return [path for path in candidates if path.is_file() and path.suffix not in {".png", ".gif", ".jar", ".lock"}]


def test_app_strings_exist_in_both_languages() -> None:
    assert set(read_strings(STRINGS_PATH)) == set(read_strings(TRANSLATED_STRINGS_PATH))


def test_app_string_placeholders_match() -> None:
    english = read_strings(STRINGS_PATH)
    portuguese = read_strings(TRANSLATED_STRINGS_PATH)

    mismatched = [name for name, text in english.items()
                  if sorted(PLACEHOLDER.findall(text)) != sorted(PLACEHOLDER.findall(portuguese[name]))]
    assert mismatched == []


@pytest.mark.parametrize("flow_path", sorted(FLOWS_PATH.glob("*.yaml")), ids=lambda path: path.stem)
def test_flows_only_use_ids_that_exist_in_the_layouts(flow_path: Path) -> None:
    declared = set()
    for layout_path in RESOURCES_PATH.glob("layout/*.xml"):
        declared.update(DECLARED_ID.findall(layout_path.read_text(encoding="utf-8")))

    assert set(FLOW_ID.findall(flow_path.read_text(encoding="utf-8"))) <= declared


def test_only_the_settings_module_reads_the_environment() -> None:
    sources = [*ROOT.glob("server/*.py"), *ROOT.glob("tray/*.py"), ROOT / "tray_icon.py"]
    readers = [str(path.relative_to(ROOT)) for path in sources
               if "os.environ" in path.read_text(encoding="utf-8") and not path.name.endswith("_test.py")]

    assert readers == [SETTINGS_MODULE]


def test_no_em_dash_anywhere() -> None:
    offenders = [str(path.relative_to(ROOT)) for path in tracked_text_files()
                 if EM_DASH in path.read_text(encoding="utf-8", errors="ignore")]

    assert offenders == []


def test_no_hidden_unicode_anywhere() -> None:
    offenders = [str(path.relative_to(ROOT)) for path in tracked_text_files()
                 if any(unicodedata.category(character) == HIDDEN_CHARACTER_CATEGORY
                        for character in path.read_text(encoding="utf-8", errors="ignore"))]

    assert offenders == []
