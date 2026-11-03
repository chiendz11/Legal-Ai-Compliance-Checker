"""Manage local web accounts (AUTH_MODE=on). Run from repository root.

    python -m scripts.users add reviewer1 --tenant LOCAL_SOURCE_PDF360 --name "Chuyên viên A" \\
        --roles viewer,uploader,reviewer
    python -m scripts.users list
    python -m scripts.users passwd reviewer1
    python -m scripts.users disable reviewer1   # or: enable

Passwords are read from a hidden prompt (or APP_USER_PASSWORD for scripted setups),
never from command-line arguments, and stored as scrypt hashes.
"""

import argparse
import getpass
import os
from pathlib import Path

from dotenv import load_dotenv
from legal_checker.modules.accounts.repository import ROLES, UserRepository


def read_password() -> str:
    password = os.environ.get("APP_USER_PASSWORD")
    if password:
        return password
    first = getpass.getpass("Password (min 8 chars): ")
    if first != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords differ")
    return first


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add")
    add.add_argument("user_id")
    add.add_argument("--tenant", required=True)
    add.add_argument("--name", required=True)
    add.add_argument("--roles", default="viewer", help=f"comma-separated: {', '.join(ROLES)}")
    commands.add_parser("list")
    for name in ("passwd", "disable", "enable"):
        commands.add_parser(name).add_argument("user_id")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("Set DATABASE_URL in .env or pass --database-url")
    users = UserRepository(args.database_url)

    if args.command == "add":
        roles = [r.strip() for r in args.roles.split(",") if r.strip()]
        user = users.create(args.user_id, args.tenant, args.name, roles, read_password())
        print(f"Created {user.user_id} ({user.tenant_id}) roles={','.join(user.roles)}")
    elif args.command == "list":
        for user in users.list():
            state = "disabled" if user.disabled else "active"
            print(f"{user.user_id}\t{user.tenant_id}\t{','.join(user.roles)}\t{state}")
    elif args.command == "passwd":
        users.set_password(args.user_id, read_password())
        print(f"Password changed for {args.user_id}")
    else:
        users.set_disabled(args.user_id, args.command == "disable")
        print(f"{args.user_id}: {args.command}d")


if __name__ == "__main__":
    main()
