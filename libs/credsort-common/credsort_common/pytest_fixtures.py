"""Shared pytest fixtures: an embedded PostgreSQL per test session."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from .testing import start_postgres


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists():
            return parent
    return Path.cwd()


@pytest.fixture(scope="session")
def pg():
    base = _repo_root() / ".dev" / "test-pg"
    base.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(dir=base))  # short path: unix socket paths are length-limited
    server, url = start_postgres(path / "pg")
    yield url
    server.cleanup()
    shutil.rmtree(path, ignore_errors=True)
