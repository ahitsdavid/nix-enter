"""Tests for --worktree flag and worktree create/remove commands."""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

from nix_enter.commands.worktree import (
    create_worktree,
    remove_worktree,
    run,
    _worktree_parent,
    _check_git_repo,
    _check_branch_name,
)
from nix_enter.project import Project


def _mock_git_worktree_add(wt_path: Path):
    """Return a side_effect function that creates the worktree dir on the 3rd call
    (simulating git worktree add creating the directory)."""
    call_count = [0]

    def side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 3:
            # This is the git worktree add call — simulate git creating the dir
            wt_path.mkdir(parents=True, exist_ok=True)
        return MagicMock(returncode=0, stderr="")

    return side_effect


class TestWorktreeParent:
    """Test worktree parent directory convention."""

    def test_parent_is_sibling_to_project(self):
        project_dir = Path("/home/user/projects/myapp")
        assert _worktree_parent(project_dir) == Path("/home/user/projects/.nix-enter-worktrees")

    def test_parent_not_inside_project(self):
        project_dir = Path("/home/user/projects/myapp")
        parent = _worktree_parent(project_dir)
        assert not str(parent).startswith(str(project_dir))


class TestValidation:
    """Test git repo and branch name validation."""

    @patch("nix_enter.commands.worktree.subprocess.run")
    def test_check_git_repo_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        _check_git_repo(Path("/some/repo"))  # should not raise
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "rev-parse" in args
        assert "--git-dir" in args

    @patch("nix_enter.commands.worktree.subprocess.run")
    def test_check_git_repo_not_a_repo(self, mock_run):
        mock_run.return_value = MagicMock(returncode=128)
        with pytest.raises(SystemExit):
            _check_git_repo(Path("/not/a/repo"))

    @patch("nix_enter.commands.worktree.subprocess.run")
    def test_check_branch_name_valid(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        _check_branch_name("feature-auth")  # should not raise
        args = mock_run.call_args[0][0]
        assert "check-ref-format" in args
        assert "--branch" in args
        assert "feature-auth" in args

    @patch("nix_enter.commands.worktree.subprocess.run")
    def test_check_branch_name_invalid(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        with pytest.raises(SystemExit):
            _check_branch_name("bad..name")


class TestCreateWorktree:
    """Test create_worktree function."""

    @patch("nix_enter.commands.worktree.subprocess.run")
    def test_creates_new_branch(self, mock_run, tmp_path):
        project_dir = tmp_path / "myapp"
        project_dir.mkdir()

        wt_path = tmp_path / ".nix-enter-worktrees" / "feature-auth"
        mock_run.side_effect = _mock_git_worktree_add(wt_path)

        create_worktree(project_dir, "feature-auth")

        # Third call is the worktree add
        wt_add_args = mock_run.call_args_list[2][0][0]
        assert "worktree" in wt_add_args
        assert "add" in wt_add_args
        assert "-b" in wt_add_args
        assert "feature-auth" in wt_add_args

    @patch("nix_enter.commands.worktree.subprocess.run")
    def test_uses_existing_branch(self, mock_run, tmp_path):
        project_dir = tmp_path / "myapp"
        project_dir.mkdir()

        wt_path = tmp_path / ".nix-enter-worktrees" / "feature-auth"
        mock_run.side_effect = _mock_git_worktree_add(wt_path)

        create_worktree(project_dir, "feature-auth", branch="existing-branch")

        wt_add_args = mock_run.call_args_list[2][0][0]
        assert "worktree" in wt_add_args
        assert "add" in wt_add_args
        assert "-b" not in wt_add_args
        assert "existing-branch" in wt_add_args

    @patch("nix_enter.commands.worktree.subprocess.run")
    def test_copies_config_toml(self, mock_run, tmp_path):
        project_dir = tmp_path / "myapp"
        project_dir.mkdir()
        config_dir = project_dir / ".nix-enter"
        config_dir.mkdir()
        (config_dir / "config.toml").write_text('[container]\nuser = "dev"\n')

        wt_path = tmp_path / ".nix-enter-worktrees" / "feature-auth"
        mock_run.side_effect = _mock_git_worktree_add(wt_path)

        create_worktree(project_dir, "feature-auth")

        dst_config = wt_path / ".nix-enter" / "config.toml"
        assert dst_config.exists()
        assert 'user = "dev"' in dst_config.read_text()

    @patch("nix_enter.commands.worktree.subprocess.run")
    def test_copies_containerfile(self, mock_run, tmp_path):
        project_dir = tmp_path / "myapp"
        project_dir.mkdir()
        (project_dir / "Containerfile.dev").write_text("FROM fedora:latest\n")

        wt_path = tmp_path / ".nix-enter-worktrees" / "feature-auth"
        mock_run.side_effect = _mock_git_worktree_add(wt_path)

        create_worktree(project_dir, "feature-auth")

        dst_containerfile = wt_path / "Containerfile.dev"
        assert dst_containerfile.exists()
        assert "FROM fedora:latest" in dst_containerfile.read_text()

    @patch("nix_enter.commands.worktree.subprocess.run")
    def test_copies_custom_containerfile_name(self, mock_run, tmp_path):
        project_dir = tmp_path / "myapp"
        project_dir.mkdir()
        config_dir = project_dir / ".nix-enter"
        config_dir.mkdir()
        (config_dir / "config.toml").write_text(
            '[container]\ncontainerfile = "Containerfile.custom"\n'
        )
        (project_dir / "Containerfile.custom").write_text("FROM ubuntu:latest\n")

        wt_path = tmp_path / ".nix-enter-worktrees" / "feature-auth"
        mock_run.side_effect = _mock_git_worktree_add(wt_path)

        create_worktree(project_dir, "feature-auth")

        dst = wt_path / "Containerfile.custom"
        assert dst.exists()
        assert "FROM ubuntu:latest" in dst.read_text()

    @patch("nix_enter.commands.worktree.subprocess.run")
    def test_no_copy_when_no_config(self, mock_run, tmp_path):
        project_dir = tmp_path / "myapp"
        project_dir.mkdir()

        wt_path = tmp_path / ".nix-enter-worktrees" / "feature-auth"
        mock_run.side_effect = _mock_git_worktree_add(wt_path)

        create_worktree(project_dir, "feature-auth")

        assert not (wt_path / ".nix-enter" / "config.toml").exists()

    @patch("nix_enter.commands.worktree.subprocess.run")
    def test_creates_worktree_without_config(self, mock_run, tmp_path):
        """Worktree creation should not crash when project has no config.toml."""
        project_dir = tmp_path / "myapp"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()  # git repo marker

        wt_path = tmp_path / ".nix-enter-worktrees" / "feature"
        mock_run.side_effect = _mock_git_worktree_add(wt_path)

        create_worktree(project_dir, "feature")
        # Should not crash

    @patch("nix_enter.commands.worktree.subprocess.run")
    def test_worktree_already_exists(self, mock_run, tmp_path):
        project_dir = tmp_path / "myapp"
        project_dir.mkdir()

        mock_run.side_effect = [
            MagicMock(returncode=0),  # rev-parse
            MagicMock(returncode=0),  # check-ref-format
        ]

        # Pre-create the worktree dir so the "already exists" check fires
        wt_path = tmp_path / ".nix-enter-worktrees" / "feature-auth"
        wt_path.mkdir(parents=True)

        with pytest.raises(SystemExit):
            create_worktree(project_dir, "feature-auth")

    @patch("nix_enter.commands.worktree.subprocess.run")
    def test_git_worktree_add_failure(self, mock_run, tmp_path):
        project_dir = tmp_path / "myapp"
        project_dir.mkdir()

        mock_run.side_effect = [
            MagicMock(returncode=0),  # rev-parse
            MagicMock(returncode=0),  # check-ref-format
            MagicMock(returncode=128, stderr="fatal: branch already exists"),
        ]

        with pytest.raises(SystemExit):
            create_worktree(project_dir, "feature-auth")


class TestRemoveWorktree:
    """Test remove_worktree function."""

    @patch("nix_enter.commands.worktree.Podman")
    @patch("nix_enter.commands.worktree.subprocess.run")
    def test_removes_container_and_volumes(self, mock_run, mock_podman, tmp_path):
        project_dir = tmp_path / "myapp"
        project_dir.mkdir()

        wt_path = tmp_path / ".nix-enter-worktrees" / "feature-auth"
        wt_path.mkdir(parents=True)

        mock_run.side_effect = [
            MagicMock(returncode=0),  # rev-parse
            MagicMock(returncode=0),  # worktree remove
        ]

        mock_podman.container_exists.return_value = True
        mock_podman.volume_exists.return_value = True

        remove_worktree(project_dir, "feature-auth")

        # Container should be removed with force
        mock_podman.rm.assert_called_once()
        assert mock_podman.rm.call_args[1]["force"] is True

        # Both volumes should be removed
        assert mock_podman.volume_rm.call_count == 2

    @patch("nix_enter.commands.worktree.Podman")
    @patch("nix_enter.commands.worktree.subprocess.run")
    def test_skips_missing_container(self, mock_run, mock_podman, tmp_path):
        project_dir = tmp_path / "myapp"
        project_dir.mkdir()

        wt_path = tmp_path / ".nix-enter-worktrees" / "feature-auth"
        wt_path.mkdir(parents=True)

        mock_run.side_effect = [
            MagicMock(returncode=0),  # rev-parse
            MagicMock(returncode=0),  # worktree remove
        ]

        mock_podman.container_exists.return_value = False
        mock_podman.volume_exists.return_value = False

        remove_worktree(project_dir, "feature-auth")

        mock_podman.rm.assert_not_called()
        mock_podman.volume_rm.assert_not_called()

    @patch("nix_enter.commands.worktree.subprocess.run")
    def test_worktree_not_found(self, mock_run, tmp_path):
        project_dir = tmp_path / "myapp"
        project_dir.mkdir()

        mock_run.side_effect = [
            MagicMock(returncode=0),  # rev-parse
        ]

        with pytest.raises(SystemExit):
            remove_worktree(project_dir, "nonexistent")

    @patch("nix_enter.commands.worktree.Podman")
    @patch("nix_enter.commands.worktree.subprocess.run")
    def test_force_remove_on_failure(self, mock_run, mock_podman, tmp_path):
        project_dir = tmp_path / "myapp"
        project_dir.mkdir()

        wt_path = tmp_path / ".nix-enter-worktrees" / "feature-auth"
        wt_path.mkdir(parents=True)

        mock_run.side_effect = [
            MagicMock(returncode=0),  # rev-parse
            MagicMock(returncode=1, stderr="has changes"),  # worktree remove fails
            MagicMock(returncode=0),  # worktree remove --force
        ]

        mock_podman.container_exists.return_value = False
        mock_podman.volume_exists.return_value = False

        remove_worktree(project_dir, "feature-auth")

        # Should have tried regular remove then --force
        wt_calls = [c for c in mock_run.call_args_list if "worktree" in c[0][0]]
        assert len(wt_calls) == 2
        assert "--force" in wt_calls[1][0][0]

    @patch("nix_enter.commands.worktree.Podman")
    @patch("nix_enter.commands.worktree.subprocess.run")
    def test_uses_correct_project_identity(self, mock_run, mock_podman, tmp_path):
        project_dir = tmp_path / "myapp"
        project_dir.mkdir()

        wt_path = tmp_path / ".nix-enter-worktrees" / "feature-auth"
        wt_path.mkdir(parents=True)

        mock_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0),
        ]

        mock_podman.container_exists.return_value = True
        mock_podman.volume_exists.return_value = False

        remove_worktree(project_dir, "feature-auth")

        # Container name should be based on the worktree path, not the main project
        wt_project = Project.from_path(wt_path)
        mock_podman.container_exists.assert_called_with(wt_project.container_name)
        mock_podman.rm.assert_called_with(wt_project.container_name, force=True)


class TestRunDispatch:
    """Test the run() dispatch function."""

    @patch("nix_enter.commands.worktree.create_worktree")
    def test_dispatches_to_create(self, mock_create):
        run(Path("/some/project"), "feature-auth")
        mock_create.assert_called_once_with(Path("/some/project"), "feature-auth", branch=None)

    @patch("nix_enter.commands.worktree.create_worktree")
    def test_dispatches_to_create_with_branch(self, mock_create):
        run(Path("/some/project"), "feature-auth", branch="main")
        mock_create.assert_called_once_with(Path("/some/project"), "feature-auth", branch="main")

    @patch("nix_enter.commands.worktree.remove_worktree")
    def test_dispatches_to_remove(self, mock_remove):
        run(Path("/some/project"), "feature-auth", remove=True)
        mock_remove.assert_called_once_with(Path("/some/project"), "feature-auth")


class TestCliWorktreeFlag:
    """Test CLI --worktree argument parsing."""

    def test_worktree_in_parser(self):
        from nix_enter.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["--worktree", "feature-auth"])
        assert args.worktree == "feature-auth"

    def test_worktree_with_branch(self):
        from nix_enter.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["--worktree", "feature-auth", "--branch", "main"])
        assert args.worktree == "feature-auth"
        assert args.branch == "main"

    def test_worktree_with_remove(self):
        from nix_enter.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["--worktree", "feature-auth", "--remove"])
        assert args.worktree == "feature-auth"
        assert args.remove is True

    def test_worktree_mutually_exclusive_with_spawn(self):
        from nix_enter.cli import build_parser
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--worktree", "feat", "--spawn", "echo hi"])

    def test_worktree_mutually_exclusive_with_init(self):
        from nix_enter.cli import build_parser
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--worktree", "feat", "--init"])

    def test_worktree_mutually_exclusive_with_rebuild(self):
        from nix_enter.cli import build_parser
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--worktree", "feat", "--rebuild"])

    def test_worktree_mutually_exclusive_with_clean(self):
        from nix_enter.cli import build_parser
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--worktree", "feat", "--clean"])

    def test_worktree_mutually_exclusive_with_force(self):
        from nix_enter.cli import build_parser
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--worktree", "feat", "--force"])

    def test_worktree_mutually_exclusive_with_list(self):
        from nix_enter.cli import build_parser
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--worktree", "feat", "--list"])

    def test_worktree_mutually_exclusive_with_purge(self):
        from nix_enter.cli import build_parser
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--worktree", "feat", "--purge"])

    def test_worktree_mutually_exclusive_with_status(self):
        from nix_enter.cli import build_parser
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--worktree", "feat", "--status"])

    def test_no_worktree_defaults_to_none(self):
        from nix_enter.cli import build_parser
        parser = build_parser()
        args = parser.parse_args([])
        assert args.worktree is None

    def test_branch_defaults_to_none(self):
        from nix_enter.cli import build_parser
        parser = build_parser()
        args = parser.parse_args([])
        assert args.branch is None

    def test_remove_defaults_to_false(self):
        from nix_enter.cli import build_parser
        parser = build_parser()
        args = parser.parse_args([])
        assert args.remove is False


class TestCliBranchRemoveValidation:
    """Test that --branch and --remove require --worktree."""

    @patch("nix_enter.commands.worktree.run")
    @patch("nix_enter.project.Project.from_cwd")
    def test_branch_without_worktree_dies(self, mock_cwd, mock_wt_run):
        """--branch without --worktree should error."""
        from nix_enter.cli import main
        import sys

        mock_cwd.return_value = Project.from_path(Path("/tmp/fake"))

        with patch.object(sys, "argv", ["nix-enter", "--branch", "main"]):
            with pytest.raises(SystemExit):
                main()

        mock_wt_run.assert_not_called()

    @patch("nix_enter.commands.worktree.run")
    @patch("nix_enter.project.Project.from_cwd")
    def test_remove_without_worktree_dies(self, mock_cwd, mock_wt_run):
        """--remove without --worktree should error."""
        from nix_enter.cli import main
        import sys

        mock_cwd.return_value = Project.from_path(Path("/tmp/fake"))

        with patch.object(sys, "argv", ["nix-enter", "--remove"]):
            with pytest.raises(SystemExit):
                main()

        mock_wt_run.assert_not_called()


class TestWorktreeIsolation:
    """Test that worktrees get different container identities."""

    def test_different_paths_different_hashes(self, tmp_path):
        main_project = Project.from_path(tmp_path / "myapp")
        wt_project = Project.from_path(tmp_path / ".nix-enter-worktrees" / "feature-auth")

        assert main_project.hash != wt_project.hash
        assert main_project.container_name != wt_project.container_name
        assert main_project.volume_home != wt_project.volume_home
        assert main_project.volume_claude != wt_project.volume_claude
