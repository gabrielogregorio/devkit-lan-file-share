import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".github/scripts/release-version.sh"
RELEASE_WORKFLOW = ROOT / ".github/workflows/create-tag-and-release.yml"
PR_WORKFLOW = ROOT / ".github/workflows/auto-complete-fields.yml"
RELEASED_VERSION = "0.1.0"
NEXT_VERSION = "0.2.0"
TEST_IDENTITY = ["-c", "user.name=test", "-c", "user.email=test@example.com"]


def git(directory: Path, *arguments: str) -> None:
    subprocess.run(["git", *TEST_IDENTITY, *arguments], cwd=directory, capture_output=True, check=True)


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    origin.mkdir()
    work.mkdir()
    git(origin, "init", "--bare", "--quiet")
    git(work, "init", "--quiet")
    git(work, "remote", "add", "origin", str(origin))
    git(work, "commit", "--quiet", "--allow-empty", "-m", "first")
    git(work, "tag", f"v{RELEASED_VERSION}")
    git(work, "push", "--quiet", "origin", f"v{RELEASED_VERSION}")
    (work / "VERSION").write_text(f"{NEXT_VERSION}\n")

    return work


def release_version(checkout: Path, branch: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([SCRIPT, branch], cwd=checkout, capture_output=True, text=True, check=False)


@pytest.mark.parametrize("version", [NEXT_VERSION, "0.2.0-rc.1"])
def test_release_branch_gives_its_version(checkout: Path, version: str) -> None:
    (checkout / "VERSION").write_text(f"{version}\n")

    result = release_version(checkout, f"release/{version}")

    assert (result.returncode, result.stdout.strip()) == (0, version)


@pytest.mark.parametrize("branch", ["dev", "main", "release/", "release/next", "release/1.2", "release/v1.2.3",
                                    "release/1.2.3/extra", "hotfix/release/1.2.3"])
def test_any_other_branch_is_refused(checkout: Path, branch: str) -> None:
    result = release_version(checkout, branch)

    assert result.returncode == 1
    assert "is not a release branch" in result.stderr


def test_branch_must_agree_with_the_version_file(checkout: Path) -> None:
    result = release_version(checkout, "release/0.3.0")

    assert result.returncode == 1
    assert "VERSION says '0.2.0'" in result.stderr


def test_released_version_is_refused(checkout: Path) -> None:
    (checkout / "VERSION").write_text(f"{RELEASED_VERSION}\n")

    result = release_version(checkout, f"release/{RELEASED_VERSION}")

    assert result.returncode == 1
    assert "already released" in result.stderr


def test_only_a_merged_release_branch_publishes() -> None:
    workflow = RELEASE_WORKFLOW.read_text()

    assert "github.event.pull_request.merged == true" in workflow
    assert "startsWith(github.event.pull_request.head.ref, 'release/')" in workflow
    assert "github.event.pull_request.head.repo.full_name == github.repository" in workflow


def test_an_ordinary_pull_request_needs_no_new_version() -> None:
    workflow = PR_WORKFLOW.read_text()

    assert "if: startsWith(github.head_ref, 'release/')" in workflow
    assert "< VERSION" not in workflow
