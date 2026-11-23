import json
import uuid

import httpx
import pytest
from sqlalchemy import text

from conftest import FakeBilling, FakeIntel, context

from credsort_common.background import process_event

from app.domain import text as T
from app.plugins.models import LlmApiModel, TemplateModel


# ---- the guard (pure) -----------------------------------------------------------------------------
def test_template_explanations_contain_only_numbers_from_the_verified_context():
    for ctx, fn in ((context(), T.explain_assessment), (context(scenario=True), T.explain_scenario)):
        out = fn(ctx)
        assert T.invented_numbers(out, ctx) == [], out
    out = T.explain_assessment(context())
    assert "18.0%" in json.dumps(out) and any("equity ratio" in c.lower() for c in out["concerns"]) and out["data_gaps"]


def test_invented_numbers_are_detected():
    ctx = context()
    assert T.invented_numbers({"summary": "Your margin of 42.5% is excellent"}, ctx) == [T.Decimal("42.5")]
    assert T.invented_numbers({"summary": "EBITDA margin of 18.0% and a score of 48"}, ctx) == []
    assert T.invented_numbers({"summary": "CHF 2'400'000 revenue"}, ctx) == []
    assert T.invented_numbers({"summary": "CHF 9'999'999 revenue"}, ctx) != []


def test_unavailable_metrics_are_described_as_missing_not_weak():
    out = T.explain_assessment(context())
    assert any("not enough data" in g for g in out["data_gaps"]) and "not available" == T.fmt("dscr", None)


# ---- the API ----------------------------------------------------------------------------------------
def test_assessment_explanation_with_template_model_and_audit(env):
    org, h = env.sme()
    r = env.client.get(f"/v1/assessments/{uuid.uuid4()}/explanation", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == {"name": "template", "version": "t1"} and body["fallback_used"] is False and "not a bank rating" in body["disclaimer"] and body["cached"] is False
    with env.db.system() as s:
        assert s.execute(text("select count(*) from outbox where event_type like '%audit.recorded%' and org_id = :o"), {"o": org}).scalar() == 1


def test_explanations_are_cached_per_organization_and_context(env):
    org, h = env.sme()
    aid = uuid.uuid4()
    first = env.client.get(f"/v1/assessments/{aid}/explanation", headers=h).json()
    second = env.client.get(f"/v1/assessments/{aid}/explanation", headers=h)
    assert second.json()["cached"] is True and second.json()["headline"] == first["headline"]


def test_scenarios_need_the_what_if_entitlement_and_fail_closed(env):
    org, h = env.sme()
    body = {"assessment_id": str(uuid.uuid4())}
    assert env.client.post(f"/v1/scenarios/{uuid.uuid4()}/explanation", json=body, headers=h).status_code == 200
    org2, h2 = env.sme()
    env.billing.entitlements = ["PROFILE", "APPLY", "ADVISOR"]
    r = env.client.post(f"/v1/scenarios/{uuid.uuid4()}/explanation", json=body, headers=h2)
    assert r.status_code == 403 and r.json()["code"] == "feature_not_included"
    org3, h3 = env.sme()
    env.billing.fail = True
    r = env.client.post(f"/v1/scenarios/{uuid.uuid4()}/explanation", json=body, headers=h3)
    assert r.status_code == 503 and r.json()["code"] == "entitlements_unavailable"
    env.billing.fail, env.billing.entitlements = False, ["PROFILE", "APPLY", "ADVISOR", "WHAT_IF"]


def test_an_intelligence_outage_is_reported_not_hidden(env):
    _, h = env.sme()
    env.intel.fail = True
    assert env.client.get(f"/v1/assessments/{uuid.uuid4()}/explanation", headers=h).status_code == 503
    env.intel.fail = False


def test_access_rules(env):
    assert env.client.get(f"/v1/assessments/{uuid.uuid4()}/explanation").status_code == 401
    assert env.client.get(f"/v1/assessments/{uuid.uuid4()}/explanation", headers=env.tokens.headers(org_type="LENDER", role="CREDIT_OFFICER")).status_code == 403


# ---- LLM plug-in + fallback ----------------------------------------------------------------------------
def llm(reply: dict | None, status=200):
    def handler(request: httpx.Request):
        if reply is None:
            return httpx.Response(500)
        return httpx.Response(status, json={"choices": [{"message": {"content": json.dumps(reply)}}]})
    return LlmApiModel("http://llm", "small-model", "key", transport=httpx.MockTransport(handler))


GOOD = {"headline": "Category C, score 48", "summary": "EBITDA margin of 18.0% is solid.", "strengths": ["Revenue growth of 12.0%."], "concerns": ["Equity ratio of 8.0% is thin."], "data_gaps": [], "suggestions": []}


def test_llm_output_is_used_when_it_only_uses_verified_numbers(env):
    env.chain[:] = [llm(GOOD), TemplateModel()]
    _, h = env.sme()
    body = env.client.get(f"/v1/assessments/{uuid.uuid4()}/explanation", headers=h).json()
    assert body["model"]["name"] == "llm:small-model" and body["fallback_used"] is False and body["headline"] == GOOD["headline"]


def test_llm_output_with_an_invented_number_is_discarded_for_the_template(env):
    env.chain[:] = [llm({**GOOD, "summary": "Your margin of 37.5% beats the market"}), TemplateModel()]
    _, h = env.sme()
    body = env.client.get(f"/v1/assessments/{uuid.uuid4()}/explanation", headers=h).json()
    assert body["model"]["name"] == "template" and body["fallback_used"] is True and "37.5" not in json.dumps(body)


def test_llm_outage_falls_back_to_the_template(env):
    env.chain[:] = [llm(None), TemplateModel()]
    _, h = env.sme()
    body = env.client.get(f"/v1/assessments/{uuid.uuid4()}/explanation", headers=h).json()
    assert body["model"]["name"] == "template" and body["fallback_used"] is True
    env.chain[:] = [TemplateModel()]


# ---- assistant chat ----------------------------------------------------------------------------------
def chat_llm(reply):
    def handler(request):
        if reply is None:
            return httpx.Response(503, json={"error": "down"})
        return httpx.Response(200, json={"choices": [{"message": {"content": reply}}]})
    return LlmApiModel("http://llm", "coach-model", "key", transport=httpx.MockTransport(handler))


def ask(env, text, h, history=()):
    return env.client.post("/v1/assistant/chat", json={"assessment_id": str(uuid.uuid4()), "messages": [*history, {"role": "user", "content": text}]}, headers=h)


def test_chat_template_answers_from_the_verified_context(env):
    env.chain[:] = [TemplateModel()]
    _, h = env.sme()
    r = ask(env, "How can I improve my rating?", h)
    assert r.status_code == 200 and r.json()["model"]["name"] == "template" and "equity" in r.json()["reply"].lower()
    from app.domain import text as T
    assert T.invented_numbers({"reply": r.json()["reply"]}, context()) == []


def test_chat_llm_reply_is_used_when_it_uses_only_known_numbers(env):
    env.chain[:] = [chat_llm("Your equity ratio of 8.0% is thin. Retaining profit would lift it."), TemplateModel()]
    _, h = env.sme()
    r = ask(env, "What is my weakest point?", h).json()
    assert r["model"]["name"] == "llm:coach-model" and r["fallback_used"] is False and "8.0%" in r["reply"]


def test_chat_reply_with_an_invented_number_is_discarded(env):
    env.chain[:] = [chat_llm("Raise your equity ratio to 42.5% and you will be approved."), TemplateModel()]
    _, h = env.sme()
    r = ask(env, "What should I do?", h).json()
    assert r["fallback_used"] is True and "42.5" not in r["reply"]


def test_chat_may_repeat_a_number_the_owner_typed_and_survives_an_llm_outage(env):
    env.chain[:] = [chat_llm("If your sales grew by 25% the picture would change, but I cannot promise a result."), TemplateModel()]
    _, h = env.sme()
    assert ask(env, "What if my sales grow 25%?", h).json()["fallback_used"] is False
    env.chain[:] = [chat_llm(None), TemplateModel()]
    r = ask(env, "How can I improve?", h).json()
    assert r["model"]["name"] == "template" and r["fallback_used"] is True
    env.chain[:] = [TemplateModel()]


def test_chat_allows_honest_rounding_but_not_invented_figures():
    from app.domain import text as T
    ctx = {"metrics": [{"code": "equity_ratio", "value": "0.31158311"}], "period_end": "2025-12-31"}
    assert T.invented_numbers({"reply": "Equity ratio is about 31 %"}, ctx, rounding=True) == []
    assert T.invented_numbers({"reply": "Equity ratio is about 31 %"}, ctx) != []  # explanations stay exact
    assert T.invented_numbers({"reply": "Equity ratio should reach 45 %"}, ctx, rounding=True) != []


def test_chat_replies_are_plain_text():
    from app.plugins.models import plain_text
    assert plain_text("**Equity ratio** is `31 %`.\n\n\n* Retain profit\n# Heading") == "Equity ratio is 31 %.\n\n- Retain profit\nHeading"


def test_chat_limits_and_access(env):
    env.chain[:] = [TemplateModel()]
    _, h = env.sme()
    assert env.client.post("/v1/assistant/chat", json={"assessment_id": str(uuid.uuid4()), "messages": [{"role": "assistant", "content": "hi"}]}, headers=h).status_code == 422
    assert ask(env, "x" * 601, h).status_code == 422
    lender = env.tokens.headers(org_type="LENDER", role="LENDER_ADMIN")
    assert ask(env, "hello", lender).status_code == 403
    env.billing.entitlements = ["PROFILE"]
    assert ask(env, "hello", h).json()["code"] == "feature_not_included"
    env.billing.entitlements = ["PROFILE", "APPLY", "ADVISOR", "WHAT_IF"]


# ---- lifecycle ---------------------------------------------------------------------------------------
def test_deletion_purges_the_cache(env):
    from app.main import create_service_app  # noqa: F401
    org, h = env.sme()
    env.client.get(f"/v1/assessments/{uuid.uuid4()}/explanation", headers=h)
    from credsort_common.background import Consumer
    from app import service as svc
    ev = {"id": str(uuid.uuid4()), "type": "credsort.identity.organization.deletion_requested.v1", "credsortorgid": str(org), "data": {"org_id": str(org), "requested_at": "x"}}
    assert process_event(env.db, Consumer("advisory-deletion", [], lambda s, e: svc.delete_org_data(s, e["credsortorgid"])), ev)
    with env.db.system() as s:
        assert s.execute(text("select count(*) from explanation_cache where org_id = :o"), {"o": org}).scalar() == 0


def test_advisory_has_no_financial_tables(env):
    with env.db.system() as s:
        tables = {r[0] for r in s.execute(text("select tablename from pg_tables where schemaname = 'public'")).all()}
    assert not tables & {"snapshots", "metrics", "assessments", "journal_entries", "canonical_accounts"}  # FF-C8
    with env.db.system() as s:
        rows = s.execute(text("select relname, relrowsecurity and relforcerowsecurity as ok from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'public' and c.relkind = 'r'")).all()
    assert [r.relname for r in rows if not r.ok and r.relname not in {"schema_migrations", "inbox", "denylist", "tombstones"}] == []
