"""CLI entry point for nix-enter."""

import argparse

from nix_enter.project import Project
from nix_enter.config import load_config, init_config
from nix_enter.log import init_logging
from nix_enter import output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nix-enter",
        description="Manage hardened per-project podman containers for AI coding agents.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--init", action="store_true", help="Initialize nix-enter in current directory")
    group.add_argument("--status", action="store_true", help="Show container/image/volume state")
    group.add_argument("--rebuild", action="store_true", help="Rebuild image and recreate container")
    group.add_argument("--force", action="store_true", help="Force-recreate container (keep image)")
    group.add_argument("--clean", action="store_true", help="Remove container + home volume")
    group.add_argument("--list", action="store_true", help="Show all nix-enter projects system-wide")
    group.add_argument("--purge", action="store_true", help="Remove orphaned resources")
    parser.add_argument("--all", action="store_true", help="With --clean: also remove claude volume")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.all and not args.clean:
        output.die("--all can only be used with --clean")

    output.set_verbose(args.verbose)

    # --list and --purge don't need project context
    if args.list:
        from nix_enter.commands import list_projects
        list_projects.run()
        return

    if args.purge:
        from nix_enter.commands import purge
        purge.run()
        return

    # All other commands need project context
    project = Project.from_cwd()
    config_path = project.nixenter_dir / "config.toml"

    # --init: create config and exit
    if args.init:
        if config_path.exists():
            output.warn(f"Already initialized: {config_path}")
        else:
            init_config(config_path)
            output.ok(f"Initialized: {config_path}")
            output.info("Edit the config, then run 'nix-enter' to start")
        return

    # Gate: require --init before any other command
    if not config_path.exists():
        output.die(f"Not a nix-enter project. Run 'nix-enter --init' first.")

    config = load_config(config_path)
    log_dir = init_logging(project.dir)

    if args.status:
        from nix_enter.commands import status
        status.run(project)
        return

    if args.clean:
        from nix_enter.commands import clean
        clean.run(project, log_dir, clean_all=args.all)
        return

    # Default: enter (with optional --rebuild or --force)
    from nix_enter.commands import enter
    enter.run(project, config, log_dir, rebuild=args.rebuild, force=args.force)
