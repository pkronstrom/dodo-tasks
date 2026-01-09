"""Tests for project detection."""

import subprocess
from pathlib import Path

from dodo.project import _make_project_id, detect_project, detect_project_root


class TestMakeProjectId:
    def test_format(self):
        path = Path("/home/user/projects/myapp")
        project_id = _make_project_id(path)

        # Should be dirname_6charhash
        assert project_id.startswith("myapp_")
        assert len(project_id) == len("myapp_") + 6

    def test_deterministic(self):
        path = Path("/home/user/projects/myapp")
        id1 = _make_project_id(path)
        id2 = _make_project_id(path)
        assert id1 == id2

    def test_different_paths_different_ids(self):
        id1 = _make_project_id(Path("/home/user/project1"))
        id2 = _make_project_id(Path("/home/user/project2"))
        assert id1 != id2


class TestDetectProject:
    def test_not_git_repo_returns_none(self, tmp_path: Path):
        result = detect_project(tmp_path)
        assert result is None

    def test_git_repo_returns_id(self, tmp_path: Path):
        # Init a git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)

        result = detect_project(tmp_path)

        assert result is not None
        assert result.startswith(f"{tmp_path.name}_")

    def test_subdirectory_of_repo(self, tmp_path: Path):
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subdir = tmp_path / "src" / "app"
        subdir.mkdir(parents=True)

        result = detect_project(subdir)

        assert result is not None
        assert result.startswith(f"{tmp_path.name}_")


class TestDetectProjectRoot:
    def test_returns_git_root(self, tmp_path: Path):
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subdir = tmp_path / "src"
        subdir.mkdir()

        result = detect_project_root(subdir)

        assert result == tmp_path

    def test_not_git_returns_none(self, tmp_path: Path):
        result = detect_project_root(tmp_path)
        assert result is None
