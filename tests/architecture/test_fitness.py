"""Architecture fitness functions (docs/architecture/04 §5). Static checks that stop the design from drifting. Run from the repo root."""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "libs" / "credsort-common"))

from credsort_common.config import SERVICES  # noqa: E402
from credsort_common.event_catalog import CATALOG, FORBIDDEN_FIELDS, schema_files  # noqa: E402
from credsort_common.upstream import CALL_INVENTORY  # noqa: E402

APP_FILES = sorted(p for s in SERVICES for p in (ROOT / "services" / s / "app").rglob("*.py"))
DOMAIN_FILES = [p for p in APP_FILES if "domain" in p.parts]


def tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(), filename=str(path))


def imports(path: Path) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(tree(path)):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            out.add(n.module)
    return out


def top(mod: str) -> str:
    return mod.split(".")[0]


def service_of(path: Path) -> str:
    return path.relative_to(ROOT / "services").parts[0]


# ---- FF-E5/E7: independence and no hidden coupling --------------------------------------------------------
def test_services_never_import_each_other_or_tests():
    bad = [(str(p.relative_to(ROOT)), m) for p in APP_FILES for m in imports(p) if top(m) in ("services", "tests") or top(m).startswith("credsort_") and top(m) != "credsort_common"]
    assert bad == []


def test_shared_library_contains_no_domain_logic():
    banned = {"marketplace", "billing", "intelligence", "accounting", "advisory", "notification"}
    for p in (ROOT / "libs" / "credsort-common" / "credsort_common").rglob("*.py"):
        assert not [m for m in imports(p) if top(m) in banned], p
    words = "loan_offer|credit_score|price_book|fee_rule"
    for p in (ROOT / "libs" / "credsort-common" / "credsort_common").rglob("*.py"):
        if p.name == "event_catalog.py":
            continue  # the catalogue names every event, which is its job
        assert not re.search(rf"\b({words})\b", p.read_text()), f"domain term in shared library: {p.name}"


def test_domain_code_is_framework_free():
    forbidden = {"fastapi", "sqlalchemy", "httpx", "psycopg", "pika", "jwt", "starlette"}
    assert DOMAIN_FILES, "no domain folders found"
    bad = [(str(p.relative_to(ROOT)), m) for p in DOMAIN_FILES for m in imports(p) if top(m) in forbidden]
    assert bad == []


# ---- FF-I8: no floats in money logic -----------------------------------------------------------------------
def test_no_floats_in_domain_code():
    problems = []
    for p in DOMAIN_FILES:
        for n in ast.walk(tree(p)):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "float":
                problems.append(f"{p.name}:{n.lineno} float()")
            if isinstance(n, ast.Constant) and isinstance(n.value, float):
                problems.append(f"{p.name}:{n.lineno} float literal {n.value}")
            if isinstance(n, (ast.arg, ast.AnnAssign)) and isinstance(getattr(n, "annotation", None), ast.Name) and n.annotation.id == "float":
                problems.append(f"{p.name}:{n.lineno} float annotation")
    assert problems == []


# ---- FF-E6: the synchronous call inventory ------------------------------------------------------------------
def declared_clients() -> list[tuple[str, str, str]]:
    found = []
    for p in APP_FILES:
        for n in ast.walk(tree(p)):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "UpstreamClient" and len(n.args) >= 2 \
                    and all(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in n.args[:2]):
                found.append((n.args[0].value, n.args[1].value, str(p.relative_to(ROOT))))
    return found


def test_every_declared_client_is_in_the_call_inventory_and_belongs_to_its_service():
    clients = declared_clients()
    assert clients, "no upstream clients found"
    for caller, target, where in clients:
        assert (caller, target) in CALL_INVENTORY, f"{where}: {caller} -> {target} is not in the inventory"
        assert where.startswith(f"services/{caller}/"), f"{where} constructs a client for {caller}"


def test_call_graph_is_acyclic_and_shallow():
    edges: dict[str, set[str]] = {}
    for caller, target in CALL_INVENTORY:
        edges.setdefault(caller, set()).add(target)

    def depth(node: str, seen: tuple[str, ...] = ()) -> int:
        assert node not in seen, f"cycle through {node}"
        return 1 + max((depth(n, (*seen, node)) for n in edges.get(node, ())), default=0)

    assert max(depth(n) for n in edges) <= 3  # service -> upstream -> (at most one more); user requests add the BFF in front
    assert "identity" not in {t for _, t in CALL_INVENTORY} - {"billing"}  # Identity only serves keys; nobody calls it per request


def test_internal_endpoints_require_a_service_identity():
    problems = []
    for p in APP_FILES:
        for n in ast.walk(tree(p)):
            if not isinstance(n, ast.FunctionDef):
                continue
            routes = [d for d in n.decorator_list if isinstance(d, ast.Call) and d.args and isinstance(d.args[0], ast.Constant) and str(d.args[0].value).startswith("/internal")]
            if routes:
                params = {a.arg for a in n.args.args}
                if "caller" not in params:
                    problems.append(f"{p.relative_to(ROOT)}:{n.name} has no `caller` service-token dependency")
    assert problems == []


def test_only_plugins_call_external_hosts():
    allowed_dirs = {"plugins"}
    bad = [str(p.relative_to(ROOT)) for p in APP_FILES if "httpx" in {top(m) for m in imports(p)} and not allowed_dirs & set(p.parts)]
    assert bad == []


def test_nobody_publishes_to_the_broker_directly():
    for p in APP_FILES:
        src = p.read_text()
        assert "basic_publish" not in src and "import pika" not in src and not re.search(r"broker\w*\.publish\(", src), p  # only the outbox relay publishes (R-I13)


# ---- events are thin, catalogued and consistent -----------------------------------------------------------
def test_event_schemas_are_thin():
    for name, schema in CATALOG.items():
        assert schema["additionalProperties"] is False
        assert not set(schema["properties"]) & FORBIDDEN_FIELDS, name  # FF-C5


def test_every_emitted_event_exists_in_the_catalogue():
    emitted = set()
    for p in APP_FILES:
        for n in ast.walk(tree(p)):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "emit" and len(n.args) >= 3 and isinstance(n.args[2], ast.Constant):
                emitted.add(n.args[2].value)
    assert emitted and emitted <= set(CATALOG), emitted - set(CATALOG)


def test_every_consumer_binding_matches_a_catalogued_event():
    names = set(CATALOG)
    checked = 0
    for p in APP_FILES:
        for n in ast.walk(tree(p)):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "Consumer" and len(n.args) >= 2 and isinstance(n.args[1], ast.List):
                for el in n.args[1].elts:
                    if isinstance(el, ast.Constant):
                        pattern = el.value.removesuffix(".*")
                        regex = re.compile("^" + re.escape(pattern).replace(r"\*", "[^.]+") + "$")
                        assert any(regex.match(e) for e in names), f"{p.relative_to(ROOT)}: binding {el.value} matches no event"
                        checked += 1
    assert checked >= 15


def test_event_schema_files_are_committed_and_current():
    expected = schema_files()
    committed = {f.name: json.loads(f.read_text()) for f in (ROOT / "contracts" / "events").glob("*.json")}
    assert set(committed) == set(expected) and all(committed[k] == expected[k] for k in expected), "run scripts/gen_contracts.py"


@pytest.mark.parametrize("service", SERVICES)
def test_openapi_documents_are_committed_and_current(service):
    env = {**os.environ, "PYTHONPATH": str(ROOT / "services" / service), "CREDSORT_KEY_DIR": str(ROOT / ".dev" / "keys-contracts"), "CREDSORT_ENV": "dev", "CREDSORT_OPENAPI_ONLY": "1"}
    code = ("import json\nfrom credsort_common.config import Settings\nfrom app.main import create_service_app\n"
            f"app = create_service_app(settings=Settings('{service}', 'dev', 'postgresql+psycopg://x@localhost/x', '', '', False))\n"
            "print(json.dumps(app.openapi(), indent=2, sort_keys=True))")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT / "services" / service, env=env, capture_output=True, text=True, check=True).stdout.strip() + "\n"
    assert (ROOT / "contracts" / "openapi" / f"{service}.json").read_text() == out, "run scripts/gen_contracts.py"


def test_money_fields_in_openapi_are_strings():
    for svc in SERVICES:
        doc = json.loads((ROOT / "contracts" / "openapi" / f"{svc}.json").read_text())
        for name, schema in doc.get("components", {}).get("schemas", {}).items():
            for field, prop in schema.get("properties", {}).items():
                if any(k in field for k in ("amount", "rate", "fees", "basis")) and prop.get("type") == "number":
                    pytest.fail(f"{svc}.{name}.{field} is a JSON number; money must be a string")


# ---- confidentiality / neutrality ------------------------------------------------------------------------
def test_matching_cannot_import_commercial_data():
    matching = ROOT / "services" / "marketplace" / "app" / "domain" / "matching.py"
    assert not [m for m in imports(matching) if any(w in m.lower() for w in ("billing", "quote", "fee", "price"))]
    clients = (ROOT / "services" / "marketplace" / "app" / "clients.py").read_text()
    assert "billing" in clients and "matching" not in clients  # the quote client lives outside the matching module


def test_advisory_has_no_access_to_financial_databases():
    for p in (ROOT / "services" / "advisory" / "app").rglob("*.py"):
        src = p.read_text().lower()
        assert not re.search(r"\b(from|join|into|update)\s+(journal_entries|canonical_accounts|snapshots|assessments)\b", src), p  # FF-C8
    migrations = " ".join(m.read_text().lower() for m in (ROOT / "services" / "advisory" / "migrations").glob("*.sql"))
    assert not re.search(r"create table (journal_entries|snapshots|metrics|assessments)", migrations)


def test_each_service_has_its_own_database_and_credentials():
    from credsort_common.migrate import db_name
    assert len({db_name(s) for s in SERVICES}) == len(SERVICES)
    for s in SERVICES:
        assert not re.search(r"references\s+\w+\.", " ".join(m.read_text() for m in (ROOT / "services" / s / "migrations").glob("*.sql")))  # no cross-schema keys


def test_every_table_with_an_organization_column_has_row_level_security():
    for s in SERVICES:
        for m in (ROOT / "services" / s / "migrations").glob("*.sql"):
            sql = m.read_text()
            statements = [x for x in re.split(r";\s*\n", sql) if re.match(r"\s*(--[^\n]*\n\s*)*create table", x, re.I)]
            for stmt in statements:
                table, body = re.search(r"create table (\w+)\s*\((.*)", stmt, re.S | re.I).groups()
                if re.search(r"\b(org_id|sme_org_id|lender_org_id)\b", body):
                    enabled = re.search(rf"alter table {table}\s+enable row level security", sql, re.I) or re.search(rf"array\[[^\]]*'{table}'[^\]]*\]", sql)
                    assert enabled, f"{s}: table {table} has an organization column but no row-level security"


def test_dev_only_shortcuts_are_refused_in_production():
    from credsort_common.broker import PgDevBroker
    from credsort_common.security import ServiceAuth
    os.environ["CREDSORT_ENV"] = "prod"
    try:
        with pytest.raises(RuntimeError):
            PgDevBroker("postgresql+psycopg://x@localhost/x")
        with pytest.raises(RuntimeError):
            ServiceAuth("marketplace")  # HMAC service tokens are dev-only
        sys.path.insert(0, str(ROOT / "services" / "identity"))
    finally:
        os.environ.pop("CREDSORT_ENV", None)


def test_no_secrets_or_keys_are_committed():
    skip = {".venv", ".dev", "node_modules", ".git", ".next", "__pycache__", ".pytest_cache"}
    for p in ROOT.rglob("*"):
        if p.is_file() and not skip & set(p.relative_to(ROOT).parts) and p.suffix in {".py", ".json", ".yml", ".yaml", ".env", ".ts", ".tsx", ".md", ".sql", ".sh", ".pem"} and p.name != "test_fitness.py":
            text = p.read_text(errors="ignore")
            assert "-----BEGIN" not in text, f"private key material in {p}"
            assert not re.search(r"\bAKIA[0-9A-Z]{16}\b|sk-[A-Za-z0-9]{32,}", text), f"credential-like string in {p}"
    assert not list(ROOT.glob("**/.env")) or all(".venv" in str(x) or "node_modules" in str(x) for x in ROOT.glob("**/.env"))
