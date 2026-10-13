"""Shared SQLite connection creation; each module owns its queries and transactions."""

import sqlite3
from pathlib import Path


def connect_sqlite(path: Path, *, timeout: float = 5) -> sqlite3.Connection:
    return sqlite3.connect(path, timeout=timeout)
