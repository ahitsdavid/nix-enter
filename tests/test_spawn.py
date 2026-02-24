"""Tests for --spawn flag and do_spawn() function."""

import re
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from nix_enter.project import Project
from nix_enter.config import Config
from nix_enter.commands.enter import do_spawn, _build_container_args


def _make_project(tmp_path: Path | None = None) -> Project:
    path = tmp_path or Path("/home/user/projects/myapp")
    return Project.from_path(path)


def _make_config(**overrides) -> Config:
    cfg = Config()
    # Disable forwarding that checks filesystem to simplify tests
    cfg.forward_ssh_agent = False
    cfg.forward_gitconfig = False
    cfg.forward_claude_config = False
    cfg.forward_wayland = False
    cfg.forward_x11 = False
    # Disable shared cache by default to avoid Podman calls in unrelated tests
    cfg.shared_cache = False
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


class TestBuildContainerArgs:
    """Test the shared _build_container_args helper."""

    def test_includes_labels(self):
        project = _make_project()
        config = _make_config()
        args = _build_container_args(project, config)
        assert "--label" in args
        label_values = [args[i + 1] for i, v in enumerate(args) if v == "--label"]
        assert any("nix-enter.managed=true" in lv for lv in label_values)

    def test_includes_security(self):
        project = _make_project()
        config = _make_config()
        args = _build_container_args(project, config)
        assert "--userns=keep-id" in args
        assert "--cap-drop=all" in args
        assert "--read-only" in args

    def test_includes_tmpfs(self):
        project = _make_project()
        config = _make_config()
        args = _build_container_args(project, config)
        tmpfs_values = [args[i + 1] for i, v in enumerate(args) if v == "--tmpfs"]
        assert "/tmp:rw,nosuid,nodev" in tmpfs_values
        assert "/var/tmp:rw,nosuid,nodev" in tmpfs_values
        assert "/run:rw,nosuid,nodev" in tmpfs_values

    def test_includes_workspace(self):
        project = _make_project()
        config = _make_config()
        args = _build_container_args(project, config)
        assert "--workdir" in args
        assert "/workspace" in args

    def test_no_new_privileges_disabled(self):
        project = _make_project()
        config = _make_config(no_new_privileges=False)
        args = _build_container_args(project, config)
        assert "no-new-privileges" not in " ".join(args)

    def test_read_only_disabled(self):
        project = _make_project()
        config = _make_config(read_only=False)
        args = _build_container_args(project, config)
        assert "--read-only" not in args

    def test_resource_limits_included(self):
        project = _make_project()
        config = _make_config(cpu_limit="2.0", memory_limit="8g", pids_limit=1024)
        args = _build_container_args(project, config)
        assert "--cpus" in args
        assert args[args.index("--cpus") + 1] == "2.0"
        assert "--memory" in args
        assert args[args.index("--memory") + 1] == "8g"
        assert "--pids-limit" in args
        assert args[args.index("--pids-limit") + 1] == "1024"

    def test_resource_limits_omitted_by_default(self):
        project = _make_project()
        config = _make_config()
        args = _build_container_args(project, config)
        assert "--cpus" not in args
        assert "--memory" not in args
        assert "--pids-limit" not in args

    def test_resource_limits_partial(self):
        project = _make_project()
        config = _make_config(memory_limit="4g")
        args = _build_container_args(project, config)
        assert "--cpus" not in args
        assert "--memory" in args
        assert args[args.index("--memory") + 1] == "4g"
        assert "--pids-limit" not in args


class TestSharedCacheArgs:
    """Test shared package cache volume mount + env vars in _build_container_args."""

    def test_cache_volume_mount_when_enabled(self):
        project = _make_project()
        config = _make_config(shared_cache=True)
        args = _build_container_args(project, config)
        volume_args = [args[i + 1] for i, v in enumerate(args) if v == "--volume"]
        assert "nix-enter-cache-global:/cache:rw" in volume_args

    def test_cache_env_vars_when_enabled(self):
        project = _make_project()
        config = _make_config(shared_cache=True)
        args = _build_container_args(project, config)
        env_args = [args[i + 1] for i, v in enumerate(args) if v == "--env"]
        assert "PIP_CACHE_DIR=/cache/pip" in env_args
        assert "NPM_CONFIG_CACHE=/cache/npm" in env_args
        assert "CARGO_HOME=/cache/cargo" in env_args

    def test_cache_volume_absent_when_disabled(self):
        project = _make_project()
        config = _make_config(shared_cache=False)
        args = _build_container_args(project, config)
        volume_args = [args[i + 1] for i, v in enumerate(args) if v == "--volume"]
        assert not any("nix-enter-cache-global" in v for v in volume_args)

    def test_cache_env_vars_absent_when_disabled(self):
        project = _make_project()
        config = _make_config(shared_cache=False)
        args = _build_container_args(project, config)
        env_args = [args[i + 1] for i, v in enumerate(args) if v == "--env"]
        assert "PIP_CACHE_DIR=/cache/pip" not in env_args
        assert "NPM_CONFIG_CACHE=/cache/npm" not in env_args
        assert "CARGO_HOME=/cache/cargo" not in env_args

    @patch("nix_enter.commands.enter.Podman")
    @patch("nix_enter.commands.enter.log_event")
    @patch("nix_enter.commands.enter.secrets.token_hex", return_value="cccc")
    def test_cache_volume_created_if_missing_in_spawn(self, mock_hex, mock_log, mock_podman, tmp_path):
        project = _make_project(tmp_path)
        config = _make_config(shared_cache=True)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        mock_podman.image_exists.return_value = True
        mock_podman.volume_exists.return_value = False
        mock_podman.run_container.return_value = 0

        do_spawn(project, config, log_dir, command="echo hi")

        # Should create both claude volume and cache volume
        create_calls = mock_podman.volume_create.call_args_list
        cache_calls = [c for c in create_calls if c[0][0] == "nix-enter-cache-global"]
        assert len(cache_calls) == 1
        assert cache_calls[0] == call(
            "nix-enter-cache-global",
            labels={"nix-enter.managed": "true", "nix-enter.cache": "global"},
        )

    @patch("nix_enter.commands.enter.Podman")
    @patch("nix_enter.commands.enter.log_event")
    @patch("nix_enter.commands.enter.secrets.token_hex", return_value="dddd")
    def test_cache_volume_not_created_if_exists_in_spawn(self, mock_hex, mock_log, mock_podman, tmp_path):
        project = _make_project(tmp_path)
        config = _make_config(shared_cache=True)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        mock_podman.image_exists.return_value = True
        mock_podman.volume_exists.return_value = True
        mock_podman.run_container.return_value = 0

        do_spawn(project, config, log_dir, command="echo hi")

        # Cache volume should not be created since it already exists
        create_calls = mock_podman.volume_create.call_args_list
        cache_calls = [c for c in create_calls if c[0][0] == "nix-enter-cache-global"]
        assert len(cache_calls) == 0


class TestDoSpawn:
    """Test do_spawn() function."""

    @patch("nix_enter.commands.enter.Podman")
    @patch("nix_enter.commands.enter.log_event")
    @patch("nix_enter.commands.enter.secrets.token_hex", return_value="a1b2")
    def test_spawn_builds_correct_args(self, mock_hex, mock_log, mock_podman, tmp_path):
        project = _make_project(tmp_path)
        config = _make_config()
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        mock_podman.image_exists.return_value = True
        mock_podman.volume_exists.return_value = True
        mock_podman.run_container.return_value = 0

        do_spawn(project, config, log_dir, command="echo hello")

        # Check run_container was called
        mock_podman.run_container.assert_called_once()
        call_args = mock_podman.run_container.call_args
        args = call_args[0][0]  # first positional: the args list
        image = call_args[0][1]  # second positional: image name
        command = call_args[0][2]  # third positional: command

        assert image == project.image_name
        assert command == "echo hello"

        # --rm must be present (ephemeral)
        assert "--rm" in args
        # --interactive must be present
        assert "--interactive" in args
        # --tty must NOT be present (headless)
        assert "--tty" not in args

    @patch("nix_enter.commands.enter.Podman")
    @patch("nix_enter.commands.enter.log_event")
    @patch("nix_enter.commands.enter.secrets.token_hex", return_value="dead")
    def test_spawn_container_name_format(self, mock_hex, mock_log, mock_podman, tmp_path):
        project = _make_project(tmp_path)
        config = _make_config()
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        mock_podman.image_exists.return_value = True
        mock_podman.volume_exists.return_value = True
        mock_podman.run_container.return_value = 0

        do_spawn(project, config, log_dir, command="ls")

        args = mock_podman.run_container.call_args[0][0]
        # Container name follows --name
        name_idx = args.index("--name")
        container_name = args[name_idx + 1]
        assert "spawn" in container_name
        assert container_name.endswith("-dead")
        assert container_name == f"{project.container_name}-spawn-dead"

    @patch("nix_enter.commands.enter.Podman")
    @patch("nix_enter.commands.enter.log_event")
    @patch("nix_enter.commands.enter.secrets.token_hex", return_value="cafe")
    def test_spawn_returns_exit_code(self, mock_hex, mock_log, mock_podman, tmp_path):
        project = _make_project(tmp_path)
        config = _make_config()
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        mock_podman.image_exists.return_value = True
        mock_podman.volume_exists.return_value = True
        mock_podman.run_container.return_value = 42

        rc = do_spawn(project, config, log_dir, command="false")
        assert rc == 42

    @patch("nix_enter.commands.enter.Podman")
    @patch("nix_enter.commands.enter.log_event")
    @patch("nix_enter.commands.enter.secrets.token_hex", return_value="0000")
    def test_spawn_returns_zero_on_success(self, mock_hex, mock_log, mock_podman, tmp_path):
        project = _make_project(tmp_path)
        config = _make_config()
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        mock_podman.image_exists.return_value = True
        mock_podman.volume_exists.return_value = True
        mock_podman.run_container.return_value = 0

        rc = do_spawn(project, config, log_dir, command="true")
        assert rc == 0

    @patch("nix_enter.commands.enter.Podman")
    @patch("nix_enter.commands.enter.log_event")
    @patch("nix_enter.commands.enter.do_build")
    @patch("nix_enter.commands.enter.secrets.token_hex", return_value="1111")
    def test_spawn_builds_image_if_missing(self, mock_hex, mock_build, mock_log, mock_podman, tmp_path):
        project = _make_project(tmp_path)
        config = _make_config()
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        mock_podman.image_exists.return_value = False
        mock_podman.volume_exists.return_value = True
        mock_podman.run_container.return_value = 0

        do_spawn(project, config, log_dir, command="echo hi")

        mock_build.assert_called_once_with(project, config, log_dir)

    @patch("nix_enter.commands.enter.Podman")
    @patch("nix_enter.commands.enter.log_event")
    @patch("nix_enter.commands.enter.secrets.token_hex", return_value="2222")
    def test_spawn_skips_build_if_image_exists(self, mock_hex, mock_log, mock_podman, tmp_path):
        project = _make_project(tmp_path)
        config = _make_config()
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        mock_podman.image_exists.return_value = True
        mock_podman.volume_exists.return_value = True
        mock_podman.run_container.return_value = 0

        with patch("nix_enter.commands.enter.do_build") as mock_build:
            do_spawn(project, config, log_dir, command="echo hi")
            mock_build.assert_not_called()

    @patch("nix_enter.commands.enter.Podman")
    @patch("nix_enter.commands.enter.log_event")
    @patch("nix_enter.commands.enter.secrets.token_hex", return_value="3333")
    def test_spawn_creates_claude_volume_if_missing(self, mock_hex, mock_log, mock_podman, tmp_path):
        project = _make_project(tmp_path)
        config = _make_config()
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        mock_podman.image_exists.return_value = True
        mock_podman.volume_exists.return_value = False
        mock_podman.run_container.return_value = 0

        do_spawn(project, config, log_dir, command="echo hi")

        mock_podman.volume_create.assert_called_once_with(
            project.volume_claude, labels=project.labels
        )

    @patch("nix_enter.commands.enter.Podman")
    @patch("nix_enter.commands.enter.log_event")
    @patch("nix_enter.commands.enter.secrets.token_hex", return_value="4444")
    def test_spawn_mounts_claude_volume(self, mock_hex, mock_log, mock_podman, tmp_path):
        project = _make_project(tmp_path)
        config = _make_config()
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        mock_podman.image_exists.return_value = True
        mock_podman.volume_exists.return_value = True
        mock_podman.run_container.return_value = 0

        do_spawn(project, config, log_dir, command="echo hi")

        args = mock_podman.run_container.call_args[0][0]
        volume_args = [args[i + 1] for i, v in enumerate(args) if v == "--volume"]
        claude_mounts = [v for v in volume_args if project.volume_claude in v]
        assert len(claude_mounts) == 1
        assert ".claude:rw" in claude_mounts[0]

    @patch("nix_enter.commands.enter.Podman")
    @patch("nix_enter.commands.enter.log_event")
    @patch("nix_enter.commands.enter.secrets.token_hex", return_value="5555")
    def test_spawn_no_home_volume(self, mock_hex, mock_log, mock_podman, tmp_path):
        project = _make_project(tmp_path)
        config = _make_config()
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        mock_podman.image_exists.return_value = True
        mock_podman.volume_exists.return_value = True
        mock_podman.run_container.return_value = 0

        do_spawn(project, config, log_dir, command="echo hi")

        args = mock_podman.run_container.call_args[0][0]
        volume_args = [args[i + 1] for i, v in enumerate(args) if v == "--volume"]
        home_mounts = [v for v in volume_args if project.volume_home in v]
        assert len(home_mounts) == 0

    @patch("nix_enter.commands.enter.Podman")
    @patch("nix_enter.commands.enter.log_event")
    @patch("nix_enter.commands.enter.secrets.token_hex", return_value="6666")
    def test_spawn_logs_lifecycle(self, mock_hex, mock_log, mock_podman, tmp_path):
        project = _make_project(tmp_path)
        config = _make_config()
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        mock_podman.image_exists.return_value = True
        mock_podman.volume_exists.return_value = True
        mock_podman.run_container.return_value = 0

        do_spawn(project, config, log_dir, command="echo hi")

        log_calls = [c[0] for c in mock_log.call_args_list]
        assert any("SPAWN start" in c[1] for c in log_calls)
        assert any("SPAWN done" in c[1] for c in log_calls)


class TestCliSpawnFlag:
    """Test CLI --spawn argument parsing."""

    def test_spawn_in_parser(self):
        from nix_enter.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["--spawn", "echo hello"])
        assert args.spawn == "echo hello"

    def test_spawn_mutually_exclusive_with_rebuild(self):
        from nix_enter.cli import build_parser
        parser = build_parser()
        # argparse exits with error on mutually exclusive conflict
        import pytest
        with pytest.raises(SystemExit):
            parser.parse_args(["--spawn", "echo hi", "--rebuild"])

    def test_spawn_mutually_exclusive_with_force(self):
        from nix_enter.cli import build_parser
        parser = build_parser()
        import pytest
        with pytest.raises(SystemExit):
            parser.parse_args(["--spawn", "echo hi", "--force"])

    def test_spawn_mutually_exclusive_with_clean(self):
        from nix_enter.cli import build_parser
        parser = build_parser()
        import pytest
        with pytest.raises(SystemExit):
            parser.parse_args(["--spawn", "echo hi", "--clean"])

    def test_spawn_mutually_exclusive_with_init(self):
        from nix_enter.cli import build_parser
        parser = build_parser()
        import pytest
        with pytest.raises(SystemExit):
            parser.parse_args(["--spawn", "echo hi", "--init"])

    def test_no_spawn_defaults_to_none(self):
        from nix_enter.cli import build_parser
        parser = build_parser()
        args = parser.parse_args([])
        assert args.spawn is None


class TestPodmanRunContainer:
    """Test Podman.run_container method."""

    @patch("nix_enter.podman.subprocess.run")
    def test_run_container_returns_exit_code(self, mock_run):
        from nix_enter.podman import Podman
        mock_run.return_value = MagicMock(returncode=7)
        rc = Podman.run_container(["--rm"], "myimage:latest", "echo hello")
        assert rc == 7

    @patch("nix_enter.podman.subprocess.run")
    def test_run_container_passes_correct_command(self, mock_run):
        from nix_enter.podman import Podman
        mock_run.return_value = MagicMock(returncode=0)
        Podman.run_container(["--rm", "--interactive"], "myimage:latest", "echo hello world")
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "podman"
        assert cmd[1] == "run"
        assert "--rm" in cmd
        assert "--interactive" in cmd
        assert "myimage:latest" in cmd
        # shlex.split("echo hello world") = ["echo", "hello", "world"]
        assert cmd[-3:] == ["echo", "hello", "world"]

    @patch("nix_enter.podman.subprocess.run")
    def test_run_container_no_check(self, mock_run):
        from nix_enter.podman import Podman
        mock_run.return_value = MagicMock(returncode=1)
        Podman.run_container([], "img", "false")
        mock_run.assert_called_once()
        assert mock_run.call_args[1]["check"] is False
