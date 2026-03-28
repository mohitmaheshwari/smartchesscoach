"""Local runner and package manager wrapper for SmartChessCoach backend.

Usage examples:
  uv run python run.py serve --port 8002 --reload
  uv run python run.py sync
  uv run python run.py install pymongo==4.5.0
  uv run python run.py freeze
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import uvicorn


def run_uv_command(args: list[str]) -> int:
    """Run a uv command and stream output directly."""
    command = ["uv", *args]
    print(f"Running: {' '.join(command)}")
    completed = subprocess.run(command, check=False)
    return completed.returncode


def command_serve(args: argparse.Namespace) -> int:
    uvicorn.run(
        args.app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )
    return 0


def command_sync(args: argparse.Namespace) -> int:
    requirements_path = Path(args.requirements)
    if not requirements_path.exists():
        print(f"requirements file not found: {requirements_path}")
        return 1
    return run_uv_command(["pip", "sync", str(requirements_path)])


def command_install(args: argparse.Namespace) -> int:
    if not args.packages:
        print("no packages provided")
        return 1
    return run_uv_command(["pip", "install", *args.packages])


def command_freeze(args: argparse.Namespace) -> int:
    uv_args = ["pip", "freeze"]
    if args.output:
        uv_args.extend(["-o", args.output])
    return run_uv_command(uv_args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run backend server and manage Python packages with uv."
    )
    subparsers = parser.add_subparsers(dest="command", required=False)

    serve = subparsers.add_parser("serve", help="Start the Uvicorn server.")
    serve.add_argument("--app", default="server:app", help="ASGI app path.")
    serve.add_argument("--host", default="127.0.0.1", help="Bind host.")
    serve.add_argument("--port", type=int, default=8002, help="Bind port.")
    serve.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for local development.",
    )
    serve.add_argument(
        "--log-level",
        default="info",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="Uvicorn log level.",
    )
    serve.set_defaults(func=command_serve)

    sync = subparsers.add_parser(
        "sync", help="Sync environment from requirements via uv."
    )
    sync.add_argument(
        "--requirements",
        default="requirements.txt",
        help="Path to requirements file.",
    )
    sync.set_defaults(func=command_sync)

    install = subparsers.add_parser(
        "install", help="Install one or more packages via uv."
    )
    install.add_argument("packages", nargs="*", help="Package specs to install.")
    install.set_defaults(func=command_install)

    freeze = subparsers.add_parser("freeze", help="Freeze installed packages via uv.")
    freeze.add_argument(
        "--output",
        default="",
        help="Optional output file (for example requirements.txt).",
    )
    freeze.set_defaults(func=command_freeze)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Default behavior when no command is given: start the app.
    if args.command is None:
        args = parser.parse_args(["serve", *sys.argv[1:]])

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
