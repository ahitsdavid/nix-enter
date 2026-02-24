"""Default command: build/create/attach flow."""

import os
from pathlib import Path

from nix_enter.project import Project
from nix_enter.config import Config
from nix_enter.podman import Podman
from nix_enter.log import log_event, build_log_path, session_log_path, rotate_logs
from nix_enter.containerfile import generate_containerfile
from nix_enter import output


def do_build(project: Project, config: Config, log_dir: Path) -> None:
    containerfile_path = project.dir / config.containerfile

    if not containerfile_path.exists():
        content = generate_containerfile(
            project.dir,
            user=config.container_user,
            uid=os.getuid(),
            containerfile_name=config.containerfile,
        )
        if content is not None:
            output.info(f"Generating default {config.containerfile}")
            containerfile_path.write_text(content)
            output.ok(f"Generated {config.containerfile}")

    blog = build_log_path(log_dir)
    log_event(log_dir, f"BUILD start image={project.image_name}")
    output.info(f"Building image: {project.image_name}")
    output.info(f"Build log: {blog}")

    result = Podman.build(
        tag=project.image_name,
        containerfile=containerfile_path,
        context=project.dir,
        build_args={"USER_NAME": config.container_user, "USER_UID": str(os.getuid())},
        labels=project.labels,
    )

    if result.returncode != 0:
        log_event(log_dir, f"BUILD failed rc={result.returncode} image={project.image_name}")
        output.die(f"Image build failed (see {blog})")

    log_event(log_dir, f"BUILD ok image={project.image_name}")
    rotate_logs(log_dir, "build-", keep=config.build_logs_keep)
    output.ok(f"Image built: {project.image_name}")


def do_create(project: Project, config: Config, log_dir: Path) -> None:
    output.info(f"Creating container: {project.container_name}")

    # Ensure volumes
    for vol in [project.volume_home, project.volume_claude]:
        if not Podman.volume_exists(vol):
            output.verbose(f"Creating volume: {vol}")
            Podman.volume_create(vol, labels=project.labels)

    args = [
        "--name", project.container_name,
        "--hostname", project.name,
    ]

    # Labels
    for key, val in project.labels.items():
        args.extend(["--label", f"{key}={val}"])

    # Security
    args.extend([
        "--userns=keep-id",
        f"--cap-drop={config.cap_drop}",
        "--security-opt", "no-new-privileges",
        "--network", config.network,
        "--interactive", "--tty",
    ])
    if config.read_only:
        args.append("--read-only")

    # Tmpfs
    args.extend([
        "--tmpfs", "/tmp:rw,nosuid,nodev",
        "--tmpfs", "/var/tmp:rw,nosuid,nodev",
        "--tmpfs", "/run:rw,nosuid,nodev",
    ])

    # Workspace
    args.extend([
        "--volume", f"{project.dir}:/workspace:rw",
        "--workdir", "/workspace",
    ])

    # Persistent volumes
    args.extend([
        "--volume", f"{project.volume_home}:/home/{config.container_user}:rw",
        "--volume", f"{project.volume_claude}:/home/{config.container_user}/.claude:rw",
    ])

    # Extra mounts from config
    for mount in config.extra_mounts:
        args.extend(["--volume", mount])

    # SSH agent
    if config.forward_ssh_agent:
        ssh_sock = os.environ.get("SSH_AUTH_SOCK", "")
        if ssh_sock:
            output.verbose(f"Forwarding SSH agent: {ssh_sock}")
            args.extend([
                "--volume", f"{ssh_sock}:/run/ssh-agent.sock:ro",
                "--env", "SSH_AUTH_SOCK=/run/ssh-agent.sock",
            ])
        else:
            output.warn("SSH_AUTH_SOCK not set -- SSH agent forwarding disabled")

    # Git config — check both traditional and XDG locations
    if config.forward_gitconfig:
        gitconfig = Path.home() / ".gitconfig"
        gitconfig_xdg = Path.home() / ".config" / "git" / "config"
        if gitconfig.exists():
            output.verbose("Mounting ~/.gitconfig read-only")
            # Resolve symlinks (home-manager links to /nix/store)
            args.extend(["--volume", f"{gitconfig.resolve()}:/home/{config.container_user}/.gitconfig:ro"])
        elif gitconfig_xdg.exists():
            output.verbose("Mounting ~/.config/git/config read-only")
            args.extend(["--volume", f"{gitconfig_xdg.resolve()}:/home/{config.container_user}/.config/git/config:ro"])

    # Claude Code global config (~/.config/claude/)
    if config.forward_claude_config:
        claude_config = Path.home() / ".config" / "claude"
        if claude_config.is_dir():
            output.verbose("Mounting ~/.config/claude read-only")
            args.extend(["--volume", f"{claude_config.resolve()}:/home/{config.container_user}/.config/claude:ro"])

    # Wayland
    if config.forward_wayland:
        wayland = os.environ.get("WAYLAND_DISPLAY", "")
        xdg_runtime = os.environ.get("XDG_RUNTIME_DIR", "")
        if wayland and xdg_runtime:
            sock = Path(xdg_runtime) / wayland
            if sock.exists():
                output.verbose(f"Forwarding Wayland display: {wayland}")
                args.extend([
                    "--volume", f"{sock}:/tmp/{wayland}:rw",
                    "--env", f"WAYLAND_DISPLAY={wayland}",
                    "--env", "XDG_RUNTIME_DIR=/tmp",
                ])

    # X11
    if config.forward_x11:
        display = os.environ.get("DISPLAY", "")
        if display and Path("/tmp/.X11-unix").is_dir():
            output.verbose(f"Forwarding X11 display: {display}")
            args.extend([
                "--volume", "/tmp/.X11-unix:/tmp/.X11-unix:ro",
                "--env", f"DISPLAY={display}",
            ])

    Podman.create(args, project.image_name)
    log_event(log_dir, f"CREATE container={project.container_name} image={project.image_name}")
    output.ok(f"Container created: {project.container_name}")


def do_attach(project: Project, config: Config, log_dir: Path) -> None:
    output.info(f"Attaching to container: {project.container_name}")
    log_event(log_dir, f"ATTACH container={project.container_name}")

    slog = session_log_path(log_dir)
    rotate_logs(log_dir, "session-", keep=config.session_logs_keep)

    os.execvp("podman", ["podman", "start", "-ai", project.container_name])


def run(
    project: Project,
    config: Config,
    log_dir: Path,
    rebuild: bool = False,
    force: bool = False,
) -> None:
    # --force: remove existing container
    if force and Podman.container_exists(project.container_name):
        output.info("Removing existing container (--force)")
        Podman.rm(project.container_name, force=True)
        log_event(log_dir, f"REMOVE container={project.container_name} reason=force")

    # --rebuild: remove container, rebuild image
    if rebuild:
        if Podman.container_exists(project.container_name):
            output.info("Removing existing container (--rebuild)")
            Podman.rm(project.container_name, force=True)
            log_event(log_dir, f"REMOVE container={project.container_name} reason=rebuild")
        do_build(project, config, log_dir)

    # Container running? Attach.
    if Podman.container_running(project.container_name):
        output.verbose("Container already running")
        do_attach(project, config, log_dir)
        return

    # Container exists but stopped? Attach (starts it).
    if Podman.container_exists(project.container_name):
        output.verbose("Container exists but stopped, starting")
        do_attach(project, config, log_dir)
        return

    # No container -- ensure image exists
    if not Podman.image_exists(project.image_name):
        do_build(project, config, log_dir)

    # Create and attach
    do_create(project, config, log_dir)
    do_attach(project, config, log_dir)
