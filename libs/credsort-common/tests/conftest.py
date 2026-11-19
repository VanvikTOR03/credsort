import shutil
import tempfile
from pathlib import Path

import pytest

from credsort_common.testing import start_postgres

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def pg():
    base = ROOT / ".dev" / "test-pg"
    base.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(dir=base))  # short path: unix socket paths are length-limited
    server, url = start_postgres(path / "pg")
    yield url
    server.cleanup()
    shutil.rmtree(path, ignore_errors=True)
