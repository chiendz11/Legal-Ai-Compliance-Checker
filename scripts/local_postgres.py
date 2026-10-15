"""Optional native PostgreSQL launcher for Linux/macOS machines without Docker."""

import argparse
import os
import subprocess
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("start", "stop", "status"))
    parser.add_argument("--port", type=int, default=5433)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data/private/postgres-local",
    )
    args = parser.parse_args()
    try:
        import celerp_postgres
    except ImportError:
        parser.error("Install optional binaries: pip install -e './backend[local-server]'")
    if not 1024 <= args.port <= 65535:
        parser.error("Use a port between 1024 and 65535")
    root = args.data_dir.resolve()
    cluster = root / "cluster"
    pg_ctl = str(celerp_postgres.tool("pg_ctl"))
    if args.command == "start" and not (cluster / "PG_VERSION").exists():
        root.mkdir(parents=True, exist_ok=True)
        # This password is for the loopback-only local dev server, matching compose defaults.
        password = os.environ.get("POSTGRES_PASSWORD", "legal_checker_local_only")
        with tempfile.NamedTemporaryFile(mode="w", dir=root) as password_file:
            password_file.write(password + "\n")
            password_file.flush()
            subprocess.run(
                [
                    str(celerp_postgres.tool("initdb")),
                    "-D",
                    str(cluster),
                    "--username=legal_checker",
                    "--encoding=UTF8",
                    "--no-locale",
                    "--auth=scram-sha-256",
                    "--pwfile",
                    password_file.name,
                ],
                check=True,
            )
        with (cluster / "postgresql.conf").open("a") as config:
            config.write(f"\nlisten_addresses = '127.0.0.1'\nport = {args.port}\n")
            config.write("unix_socket_directories = ''\n")
    if args.command == "start":
        if (
            subprocess.run([pg_ctl, "-D", str(cluster), "status"], capture_output=True).returncode
            == 0
        ):
            print("Local PostgreSQL already running")
            return
        subprocess.run(
            [
                pg_ctl,
                "-D",
                str(cluster),
                "-l",
                str(root / "server.log"),
                "-o",
                f"-p {args.port}",
                "-w",
                "start",
            ],
            check=True,
        )
    elif args.command == "stop":
        subprocess.run([pg_ctl, "-D", str(cluster), "-m", "fast", "-w", "stop"], check=True)
    else:
        subprocess.run([pg_ctl, "-D", str(cluster), "status"], check=True)


if __name__ == "__main__":
    main()
