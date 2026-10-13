"""Installed package uses PostgreSQL outside the repository working directory."""

import os
import subprocess
import sys


def test_installed_backend_starts_outside_repository(tmp_path, database_url):
    program = """
from fastapi.testclient import TestClient
from legal_checker.main import create_app
client = TestClient(create_app())
assert client.get('/health').status_code == 200
assert client.get('/api/v1/knowledge').json()['counts']['tieu_chi_danh_gia'] == 9
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", program],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "DATABASE_URL": database_url, "KNOWLEDGE_SNAPSHOT_SHA256": ""},
    )
    assert result.returncode == 0, result.stderr
