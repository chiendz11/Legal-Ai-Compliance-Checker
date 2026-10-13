"""Src layout must work through an installed package, independent of working directory."""

import subprocess
import sys

from legal_checker.core.config import PROJECT_ROOT


def test_installed_backend_starts_outside_repository(tmp_path):
    program = """
from pathlib import Path
from fastapi.testclient import TestClient
from legal_checker.core.config import Settings
from legal_checker.main import create_app
from legal_checker.modules.legal_knowledge.repository import Knowledge

settings = Settings.from_env()
assert settings.knowledge_path.is_file()
assert Knowledge().sha256 == Knowledge(settings.knowledge_path).sha256
settings = Settings(settings.knowledge_path, Path('runtime.sqlite3'))
client = TestClient(create_app(settings=settings))
assert client.get('/health').json()['status'] == 'ok'
assert client.get('/api/v1/knowledge').json()['counts']['tieu_chi_danh_gia'] == 356
assert Path('runtime.sqlite3').is_file()
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", program], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert not (PROJECT_ROOT / "app").exists()
