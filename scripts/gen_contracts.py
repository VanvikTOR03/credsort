#!/usr/bin/env python
"""Generates contracts/events/*.schema.json and contracts/openapi/<service>.json (ADR-0006, ADR-0023, ADR-0030).

CI fails when the committed files differ from the generated ones (tests/architecture/test_contracts.py).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libs" / "credsort-common"))
from credsort_common.config import SERVICES  # noqa: E402
from credsort_common.event_catalog import write_schemas  # noqa: E402

DUMP = """
import json, sys
from credsort_common.config import Settings
from app.main import create_service_app
app = create_service_app(settings=Settings('{svc}', 'dev', 'postgresql+psycopg://x@localhost/x', '', '', False))
print(json.dumps(app.openapi(), indent=2, sort_keys=True))
"""


def openapi(svc: str) -> str:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "services" / svc), "CREDSORT_KEY_DIR": tempfile.mkdtemp(), "CREDSORT_ENV": "dev", "CREDSORT_OPENAPI_ONLY": "1"}
    out = subprocess.run([sys.executable, "-c", DUMP.format(svc=svc)], cwd=ROOT / "services" / svc, env=env, capture_output=True, text=True, check=True)
    return out.stdout.strip() + "\n"


def main() -> None:
    write_schemas(ROOT / "contracts" / "events")
    (ROOT / "contracts" / "openapi").mkdir(parents=True, exist_ok=True)
    for svc in SERVICES:
        (ROOT / "contracts" / "openapi" / f"{svc}.json").write_text(openapi(svc))
        print(f"contracts/openapi/{svc}.json")


if __name__ == "__main__":
    main()
