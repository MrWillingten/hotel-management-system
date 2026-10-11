"""Command-line interface: `python -m hotel <command>`.

    run              start the web application (Waitress; --dev for Flask's debugger)
    init-db          create or upgrade the database
    create-manager   create the first manager account
    backup           write a backup now
    restore FILE     replace the database with a backup (application stopped)
    audit verify     check the audit log's hash chain
    version          print the version

The CLI uses the same services as the web interface, without Flask, which
shows that the business logic does not depend on the web layer.
"""

from __future__ import annotations

import argparse
import getpass
import ipaddress
import sys
from collections.abc import Sequence
from pathlib import Path

from hotel import __version__
from hotel.bootstrap import build_services
from hotel.config import ConfigurationError, Settings
from hotel.domain.actor import Actor
from hotel.domain.errors import HotelError, ValidationError
from hotel.persistence.backup import BackupError

# The CLI speaks English; the web interface translates the same codes.
_CLI_MESSAGES = {
    "auth.setup_already_done": "A manager account already exists. Sign in with it instead.",
    "username.invalid": "Username: use 3-32 letters, digits, dots, hyphens or underscores.",
    "full_name.invalid": "Full name: use 1 to 100 characters.",
    "password.too_short": "Password: use at least {min_length} characters.",
    "password.too_long": "Password: use at most {max_length} characters.",
    "password.too_repetitive": "Password: it repeats the same characters too much.",
    "password.contains_username": "Password: it must not contain the username.",
    "password.too_common": "Password: it is too common. Choose a less predictable one.",
}


def _explain(error: HotelError) -> str:
    template = _CLI_MESSAGES.get(error.code, error.code)
    try:
        return template.format(**error.params)
    except (KeyError, IndexError):
        return template


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def cmd_run(args: argparse.Namespace) -> int:
    from hotel.web import create_app

    settings = Settings.from_env(environment="development" if args.dev else None)
    app = create_app(settings)
    backup = app.extensions["hotel.services"].backups.auto_backup_if_due()
    if backup is not None:
        print(f"Daily backup written to {backup}")
    if not _is_loopback(args.host):
        print(
            "WARNING: listening on a network address. Without HTTPS, passwords travel in "
            "clear text over the network. See docs/deployment.md (HTTPS with Caddy).",
            file=sys.stderr,
        )
    print(f"{settings.hotel_name} is running on http://{args.host}:{args.port}  (Ctrl+C to stop)")
    if args.dev:
        app.run(host=args.host, port=args.port, debug=True)
    else:
        from waitress import serve

        serve(app, host=args.host, port=args.port, threads=8)
    return 0


def cmd_init_db(_: argparse.Namespace) -> int:
    services = build_services(Settings.from_env())
    print(
        f"Database ready at {services.settings.database_path} (schema v{services.schema_version})."
    )
    return 0


def _ask_password(username: str, policy_check) -> str:
    while True:
        password = getpass.getpass("Password (at least 12 characters): ")
        try:
            policy_check(password, username=username)
        except ValidationError as error:
            print(_explain(error), file=sys.stderr)
            continue
        if getpass.getpass("Repeat the password: ") != password:
            print("The two passwords are different. Try again.", file=sys.stderr)
            continue
        return password


def cmd_create_manager(args: argparse.Namespace) -> int:
    services = build_services(Settings.from_env())
    if services.auth.has_users():
        print(_CLI_MESSAGES["auth.setup_already_done"], file=sys.stderr)
        return 1
    username = args.username or input("Username: ")
    full_name = args.full_name or input("Full name: ")
    password = _ask_password(username, services.auth.check_password)
    try:
        user = services.auth.create_first_manager(username, full_name, password)
    except HotelError as error:
        print(_explain(error), file=sys.stderr)
        return 1
    print(f"Manager account '{user.username}' created. You can now sign in.")
    return 0


def cmd_backup(_: argparse.Namespace) -> int:
    services = build_services(Settings.from_env())
    path = services.backups.create(Actor.system())
    print(f"Backup written to {path}")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    services = build_services(Settings.from_env())
    backup = Path(args.file).expanduser().resolve()
    print(f"This replaces ALL current data with the contents of {backup.name}.")
    print("Stop the application (Ctrl+C in its window) before continuing.")
    if not args.yes and input("Type 'restore' to continue: ").strip() != "restore":
        print("Cancelled.")
        return 1
    try:
        safety_copy = services.backups.restore(Actor.system(), backup)
    except BackupError as error:
        print(f"Restore refused: {error}", file=sys.stderr)
        return 1
    print(f"Restored. The replaced data was kept in {safety_copy}")
    return 0


def cmd_audit_verify(_: argparse.Namespace) -> int:
    services = build_services(Settings.from_env())
    check = services.audit.verify(Actor.system())
    if check.ok:
        print(f"Audit log intact: {check.checked} entries verified.")
        print(f"Latest hash: {check.last_hash}")
        print("Keep a copy of this hash somewhere else: it proves today's history later.")
        return 0
    problem = "was edited" if check.reason == "content" else "follows a removed or replaced entry"
    print(f"AUDIT LOG ALTERED: entry #{check.broken_at} {problem}.", file=sys.stderr)
    return 1


def cmd_version(_: argparse.Namespace) -> int:
    print(f"hotel {__version__}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hotel", description="Hotel Reservation and Management System"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="start the web application")
    run.add_argument(
        "--host", default="127.0.0.1", help="address to listen on (default: 127.0.0.1)"
    )
    run.add_argument("--port", type=int, default=8000, help="port (default: 8000)")
    run.add_argument(
        "--dev", action="store_true", help="development mode with auto-reload and debugger"
    )
    run.set_defaults(handler=cmd_run)

    commands.add_parser("init-db", help="create or upgrade the database").set_defaults(
        handler=cmd_init_db
    )

    manager = commands.add_parser("create-manager", help="create the first manager account")
    manager.add_argument("--username")
    manager.add_argument("--full-name")
    manager.set_defaults(handler=cmd_create_manager)

    commands.add_parser("backup", help="write a backup of the database").set_defaults(
        handler=cmd_backup
    )
    restore = commands.add_parser("restore", help="replace the database with a backup")
    restore.add_argument("file", help="backup file (in the data folder's backups/)")
    restore.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    restore.set_defaults(handler=cmd_restore)

    audit = commands.add_parser("audit", help="audit log tools")
    audit_commands = audit.add_subparsers(dest="audit_command", required=True)
    audit_commands.add_parser(
        "verify", help="check that no entry was altered or removed"
    ).set_defaults(handler=cmd_audit_verify)

    commands.add_parser("version", help="print the version").set_defaults(handler=cmd_version)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except ConfigurationError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
