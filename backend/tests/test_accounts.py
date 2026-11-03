"""
Accounts, per-user data, daily limits and Mercado Pago billing.
Tokens are signed with a key generated here (standing in for Supabase's) and the
Mercado Pago API is replaced by a mock transport: no network, no real money.
"""
import datetime
import hashlib
import hmac
import os
import subprocess
import sys
import threading
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

import auth
import config
import database
import models
from billing import mercadopago, usage
from main import app

SUPABASE = "https://test-project.supabase.co"
KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_KEY = ec.generate_private_key(ec.SECP256R1())

client = TestClient(app)


def token(sub="user-a", email="a@example.com", *, key=KEY, aud="authenticated", iss=f"{SUPABASE}/auth/v1",
          expires_in=3600, alg="ES256"):
    now = int(time.time())
    claims = {"sub": sub, "email": email, "aud": aud, "iss": iss, "iat": now, "exp": now + expires_in,
              "role": "authenticated"}
    return jwt.encode(claims, key, algorithm=alg)


def headers(**kwargs):
    return {"Authorization": f"Bearer {token(**kwargs)}"}


@pytest.fixture
def accounts(monkeypatch):
    """Turn accounts on, with our key as Supabase's signing key."""
    monkeypatch.setattr(config, "SUPABASE_URL", SUPABASE)
    monkeypatch.setattr(config, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth, "_signing_key", lambda _token: KEY.public_key())


# ── Authentication ────────────────────────────────────────────────────────────

def test_requests_without_session_are_rejected(accounts):
    assert client.get("/api/me").status_code == 401
    assert client.post("/api/solve-text", data={"latex_expression": "1+1"}).status_code == 401
    assert client.get("/api/health").status_code == 200  # public


def test_valid_session_creates_the_user(accounts):
    body = client.get("/api/me", headers=headers(sub="new-user", email="new@example.com")).json()
    assert body["email"] == "new@example.com" and body["plan"] == "free"


@pytest.mark.parametrize("bad", [
    {"expires_in": -10},                       # expired
    {"aud": "anon"},                           # another audience
    {"iss": "https://evil.supabase.co/auth/v1"},  # another project
    {"key": OTHER_KEY},                        # signed by someone else
])
def test_invalid_tokens_are_rejected(accounts, bad):
    assert client.get("/api/me", headers=headers(**bad)).status_code == 401


def test_shared_secret_tokens_are_rejected(accounts):
    # An HS256 token must never be accepted: whoever knows a shared secret could mint any user
    forged = jwt.encode({"sub": "user-a", "aud": "authenticated", "iss": f"{SUPABASE}/auth/v1",
                         "exp": int(time.time()) + 60}, "secret", algorithm="HS256")
    assert client.get("/api/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


# ── Each user only sees their own exercises ───────────────────────────────────

def test_history_is_private(accounts):
    a, b = headers(sub="alice"), headers(sub="bob")
    created = client.post("/api/solve-text", data={"latex_expression": "x + 1 = 3"}, headers=a).json()
    assert created["id"]

    assert client.get("/api/history", headers=b).json()["total"] == 0
    assert client.get(f"/api/history/{created['id']}", headers=b).status_code == 404
    assert client.delete(f"/api/history/{created['id']}", headers=b).status_code == 404
    client.delete("/api/history", headers=b)
    assert client.get(f"/api/history/{created['id']}", headers=a).status_code == 200


# ── Daily limits ──────────────────────────────────────────────────────────────

def test_daily_limit_and_unsolved_exercises_are_free(accounts, monkeypatch):
    monkeypatch.setattr(config, "FREE_EXERCISES_PER_DAY", 2)
    h = headers(sub="limited-user")
    assert client.post("/api/solve-text", data={"latex_expression": r"\frac{{"}, headers=h).json()["solved"] is False
    for _ in range(2):
        assert client.post("/api/solve-text", data={"latex_expression": "2 + 2"}, headers=h).status_code == 200
    blocked = client.post("/api/solve-text", data={"latex_expression": "2 + 2"}, headers=h)
    assert blocked.status_code == 429 and blocked.json()["detail"]["code"] == "daily_limit"
    assert client.get("/api/me", headers=h).json()["usage"]["exercises"] == {"used": 2, "limit": 2}


def test_quota_is_safe_under_concurrency(monkeypatch):
    """10 simultaneous requests with 3 units left: exactly 3 get through."""
    monkeypatch.setattr(config, "FREE_EXERCISES_PER_DAY", 3)
    monkeypatch.setattr(config, "AUTH_ENABLED", True)  # local dev mode has no limits
    db = database.SessionLocal()
    db.merge(models.User(id="racer"))
    db.commit()
    db.close()
    results, start = [], threading.Barrier(10)

    def worker():
        session = database.SessionLocal()
        try:
            user = session.get(models.User, "racer")
            session.commit()  # give the connection back to the pool while waiting
            start.wait(timeout=30)
            results.append(usage.reserve(session, user, usage.EXERCISES) is not None)
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(True) == 3


def test_ai_cost_is_recorded_in_micro_dollars(monkeypatch):
    monkeypatch.setattr(config, "AI_PRICE_INPUT_PER_M", 0.75)
    monkeypatch.setattr(config, "AI_PRICE_OUTPUT_PER_M", 3.75)
    assert usage.ai_cost_micro_usd(1500, 150) == 1688  # 1500·0.75 + 150·3.75 = 1687.5 µUSD


# ── Mercado Pago ──────────────────────────────────────────────────────────────

SECRET = "webhook-secret"


def signed_headers(data_id: str, request_id: str = "req-1", ts: str = "1742505638683"):
    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    v1 = hmac.new(SECRET.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return {"x-signature": f"ts={ts},v1={v1}", "x-request-id": request_id}


@pytest.fixture
def mp(monkeypatch, accounts):
    """Mercado Pago enabled, its API replaced by `responses` (path → JSON)."""
    monkeypatch.setattr(config, "MP_ACCESS_TOKEN", "TEST-token")
    monkeypatch.setattr(config, "MP_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    responses, calls = {}, []

    def handler(request: httpx.Request):
        calls.append((request.method, request.url.path))
        body = responses.get((request.method, request.url.path))
        return httpx.Response(200, json=body) if body is not None else httpx.Response(404, json={})

    monkeypatch.setattr(mercadopago, "_http", lambda: httpx.Client(
        base_url=mercadopago.API_URL, transport=httpx.MockTransport(handler)))
    return responses, calls


def test_subscribe_returns_checkout(mp):
    responses, _ = mp
    responses[("POST", "/preapproval")] = {"id": "pre-1", "init_point": "https://mp.test/checkout/pre-1"}
    r = client.post("/api/billing/subscribe", headers=headers(sub="buyer", email="buyer@example.com"))
    assert r.json() == {"checkout_url": "https://mp.test/checkout/pre-1"}


def test_subscribe_disabled_without_credentials(accounts):
    assert client.post("/api/billing/subscribe", headers=headers()).status_code == 503


def test_webhook_rejects_bad_signature(mp):
    r = client.post("/api/billing/webhook?type=subscription_authorized_payment&data.id=ap-1",
                    json={"type": "subscription_authorized_payment", "data": {"id": "ap-1"}},
                    headers={"x-signature": "ts=1,v1=deadbeef", "x-request-id": "req-1"})
    assert r.status_code == 401


def _payment_flow(responses, payment_status):
    client.get("/api/me", headers=headers(sub="payer", email="payer@example.com"))  # user exists
    responses[("GET", "/authorized_payments/ap-1")] = {"id": "ap-1", "preapproval_id": "pre-9",
                                                         "payment": {"id": 555, "status": "approved"}}
    responses[("GET", "/v1/payments/555")] = {"id": 555, "status": payment_status,
                                               "date_approved": "2026-10-26T12:00:00.000-03:00"}
    responses[("GET", "/preapproval/pre-9")] = {"id": "pre-9", "status": "authorized", "external_reference": "payer"}
    return client.post("/api/billing/webhook?type=subscription_authorized_payment&data.id=ap-1",
                       json={"type": "subscription_authorized_payment", "data": {"id": "ap-1"}},
                       headers=signed_headers("ap-1"))


def _user(user_id):
    db = database.SessionLocal()
    try:
        return db.get(models.User, user_id)
    finally:
        db.close()


def test_approved_payment_grants_pro_and_repeats_are_idempotent(mp):
    responses, _ = mp
    assert _payment_flow(responses, "approved").status_code == 200
    first = models.as_utc(_user("payer").pro_until)
    expected = datetime.datetime(2026, 10, 26, 15, 0, tzinfo=datetime.timezone.utc) + datetime.timedelta(days=31 + config.PRO_GRACE_DAYS)
    assert first == expected
    _payment_flow(responses, "approved")  # Mercado Pago delivers notifications at least once
    assert models.as_utc(_user("payer").pro_until) == first


def test_rejected_payment_does_not_grant_pro(mp):
    responses, _ = mp
    db = database.SessionLocal()
    db.merge(models.User(id="payer", email="payer@example.com", pro_until=None))
    db.commit()
    db.close()
    assert _payment_flow(responses, "rejected").status_code == 200
    assert _user("payer").pro_until is None


def test_cancelled_subscription_keeps_what_was_paid(mp):
    responses, _ = mp
    paid_until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=10)
    db = database.SessionLocal()
    db.merge(models.User(id="leaver", email="l@example.com", pro_until=paid_until,
                         mp_preapproval_id="pre-x", mp_status="authorized"))
    db.commit()
    db.close()
    responses[("PUT", "/preapproval/pre-x")] = {"id": "pre-x", "status": "cancelled"}
    body = client.post("/api/billing/cancel", headers=headers(sub="leaver", email="l@example.com")).json()
    assert body["plan"] == "pro"  # still paid for 10 more days
    assert _user("leaver").mp_status == "cancelled"


def test_mercadopago_api_failure_makes_it_retry(mp):
    responses, _ = mp
    r = client.post("/api/billing/webhook?type=subscription_preapproval&data.id=missing",
                    json={}, headers=signed_headers("missing"))
    assert r.status_code == 500  # the API answered 404: tell Mercado Pago to retry later


# ── Configuration and schema ──────────────────────────────────────────────────

def test_production_refuses_unsafe_settings(monkeypatch):
    monkeypatch.setattr(config, "ENV", "production")
    monkeypatch.setattr(config, "IS_DEV", False)
    monkeypatch.setattr(config, "AUTH_ENABLED", False)
    problems = " ".join(config.production_problems())
    assert "SUPABASE_URL" in problems and "SQLite" in problems


def test_migration_keeps_data_of_a_database_created_before_accounts(tmp_path):
    path = tmp_path / "old.db"
    import sqlite3
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE exercises (id INTEGER PRIMARY KEY, original_image_path VARCHAR, "
                "extracted_latex TEXT NOT NULL, domain_classification VARCHAR, symbolic_representation TEXT, "
                "solution_steps_json TEXT, final_result_latex TEXT, graph_data_json TEXT, created_at DATETIME)")
    old.execute("INSERT INTO exercises (extracted_latex, final_result_latex) VALUES ('x = 1', '1')")
    old.commit()
    old.close()
    backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{path.as_posix()}"}
    subprocess.run([sys.executable, "-c", "import database; database.migrate(); database.migrate()"],
                   cwd=backend, env=env, check=True)
    db = sqlite3.connect(path)
    assert db.execute("SELECT extracted_latex FROM exercises").fetchall() == [("x = 1",)]
    assert "user_id" in [r[1] for r in db.execute("PRAGMA table_info(exercises)")]
    assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("0004",)
    db.close()


def test_refund_takes_pro_back(mp):
    responses, _ = mp
    _payment_flow(responses, "approved")
    assert _user("payer").is_pro(now=datetime.datetime(2026, 11, 1, tzinfo=datetime.timezone.utc))
    responses[("GET", "/v1/payments/555")] = {"id": 555, "status": "refunded",
                                               "date_approved": "2026-10-26T12:00:00.000-03:00"}
    r = client.post("/api/billing/webhook?type=payment&data.id=555", json={}, headers=signed_headers("555"))
    assert r.status_code == 200
    assert _user("payer").pro_until is None


def test_unknown_payment_notifications_are_ignored(mp):
    r = client.post("/api/billing/webhook?type=payment&data.id=999", json={}, headers=signed_headers("999"))
    assert r.status_code == 200


def _save_user(**fields):
    db = database.SessionLocal()
    db.merge(models.User(**fields))
    db.commit()
    db.close()


def test_never_two_active_subscriptions(mp):
    responses, calls = mp
    _save_user(id="double", email="d@example.com", mp_preapproval_id="pre-old", mp_status="authorized")
    responses[("GET", "/preapproval/pre-old")] = {"id": "pre-old", "status": "authorized"}
    r = client.post("/api/billing/subscribe", headers=headers(sub="double", email="d@example.com"))
    assert r.status_code == 409
    assert ("POST", "/preapproval") not in calls


def test_pending_checkout_is_reused(mp):
    responses, calls = mp
    _save_user(id="hesitant", email="h@example.com", mp_preapproval_id="pre-p", mp_status="pending")
    responses[("GET", "/preapproval/pre-p")] = {"id": "pre-p", "status": "pending", "init_point": "https://mp.test/p"}
    r = client.post("/api/billing/subscribe", headers=headers(sub="hesitant", email="h@example.com"))
    assert r.json() == {"checkout_url": "https://mp.test/p"}
    assert ("POST", "/preapproval") not in calls


OLD, NEW = "2026-09-01T10:00:00.000-03:00", "2026-10-01T10:00:00.000-03:00"


def test_a_newer_authorized_subscription_replaces_the_old_one(mp):
    responses, calls = mp
    _save_user(id="switcher", email="s@example.com", mp_preapproval_id="pre-a", mp_status="authorized")
    responses[("GET", "/preapproval/pre-a")] = {"id": "pre-a", "status": "authorized", "date_created": OLD}
    responses[("GET", "/preapproval/pre-b")] = {"id": "pre-b", "status": "authorized", "date_created": NEW,
                                                 "external_reference": "switcher"}
    responses[("PUT", "/preapproval/pre-a")] = {"id": "pre-a", "status": "cancelled"}
    client.post("/api/billing/webhook?type=subscription_preapproval&data.id=pre-b", json={},
                headers=signed_headers("pre-b"))
    assert ("PUT", "/preapproval/pre-a") in calls
    assert _user("switcher").mp_preapproval_id == "pre-b"


def test_a_late_notice_of_an_older_subscription_cancels_that_one_not_the_current(mp):
    responses, calls = mp
    _save_user(id="current", email="c@example.com", mp_preapproval_id="pre-new", mp_status="authorized")
    responses[("GET", "/preapproval/pre-new")] = {"id": "pre-new", "status": "authorized", "date_created": NEW}
    responses[("GET", "/preapproval/pre-old")] = {"id": "pre-old", "status": "authorized", "date_created": OLD,
                                                   "external_reference": "current"}
    responses[("PUT", "/preapproval/pre-old")] = {"id": "pre-old", "status": "cancelled"}
    client.post("/api/billing/webhook?type=subscription_preapproval&data.id=pre-old", json={},
                headers=signed_headers("pre-old"))
    assert ("PUT", "/preapproval/pre-new") not in calls
    assert ("PUT", "/preapproval/pre-old") in calls
    assert _user("current").mp_preapproval_id == "pre-new"


def test_a_repeated_payment_of_an_old_subscription_never_cancels_the_current(mp):
    """Regression: a late or redelivered charge from a cancelled subscription used to cancel the active one."""
    responses, calls = mp
    _save_user(id="loyal", email="l@example.com", mp_preapproval_id="pre-loyal-new", mp_status="authorized")
    responses[("GET", "/authorized_payments/ap-old")] = {"id": "ap-old", "preapproval_id": "pre-loyal-old",
                                                           "payment": {"id": 777}}
    responses[("GET", "/v1/payments/777")] = {"id": 777, "status": "approved", "date_approved": OLD}
    responses[("GET", "/preapproval/pre-loyal-old")] = {"id": "pre-loyal-old", "status": "cancelled", "external_reference": "loyal"}
    r = client.post("/api/billing/webhook?type=subscription_authorized_payment&data.id=ap-old", json={},
                    headers=signed_headers("ap-old"))
    assert r.status_code == 200
    assert not [c for c in calls if c[0] == "PUT"]
    assert _user("loyal").mp_preapproval_id == "pre-loyal-new"


# ── Account deletion ──────────────────────────────────────────────────────────

class _FakeResponse:
    def __init__(self, status):
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)


def test_delete_account_order_and_what_is_kept(mp, monkeypatch):
    from api import account
    responses, _ = mp
    monkeypatch.setattr(config, "SUPABASE_SERVICE_ROLE_KEY", "service-key")
    login_status = {"code": 500}
    monkeypatch.setattr(account.httpx, "delete", lambda *a, **k: _FakeResponse(login_status["code"]))
    h = headers(sub="goodbye", email="g@example.com")
    client.post("/api/solve-text", data={"latex_expression": "1 + 1"}, headers=h)
    db = database.SessionLocal()
    user = db.get(models.User, "goodbye")
    user.mp_preapproval_id, user.mp_status = "pre-g", "authorized"
    now = datetime.datetime.now(datetime.timezone.utc)
    db.add(models.Payment(id="pay-g", user_id="goodbye", status="approved", paid_at=now, grants_until=now))
    db.commit()
    db.close()
    # 1. Mercado Pago fails: nothing may be deleted, or the user keeps paying with no account left
    assert client.delete("/api/me", headers=h).status_code == 502
    assert _user("goodbye") is not None
    # 2. The login cannot be deleted: nothing is deleted either (logging in again would recreate the account)
    responses[("PUT", "/preapproval/pre-g")] = {"id": "pre-g", "status": "cancelled"}
    assert client.delete("/api/me", headers=h).status_code == 502
    assert _user("goodbye") is not None
    # 3. Everything works: data deleted, payment kept without owner
    login_status["code"] = 204
    assert client.delete("/api/me", headers=h).status_code == 204
    assert _user("goodbye") is None
    db = database.SessionLocal()
    assert db.query(models.Exercise).filter(models.Exercise.user_id == "goodbye").count() == 0
    assert db.get(models.Payment, "pay-g").user_id is None
    db.close()


# ── Abuse ─────────────────────────────────────────────────────────────────────

def test_expensive_failures_are_charged(accounts, monkeypatch):
    """A failed attempt that held a worker for the whole time limit is not refunded."""
    from solver_pool import SolverTimeout

    def slow(*args, **kwargs):
        raise SolverTimeout()
    monkeypatch.setattr("api.router.solve", slow)
    h = headers(sub="slowpoke")
    assert client.post("/api/solve-text", data={"latex_expression": "x"}, headers=h).status_code == 422
    assert client.get("/api/me", headers=h).json()["usage"]["exercises"]["used"] == 1


def test_quota_released_on_the_day_it_was_reserved(monkeypatch):
    _save_user(id="night-owl")
    db = database.SessionLocal()
    user = db.get(models.User, "night-owl")
    day = usage.reserve(db, user, usage.EXERCISES)
    monkeypatch.setattr(usage, "today", lambda: day + datetime.timedelta(days=1))  # midnight passes
    usage.release(db, user, usage.EXERCISES, day)
    assert db.get(models.DailyUsage, ("night-owl", day)).exercises == 0
    db.close()


def test_burst_limit_per_user(accounts, monkeypatch):
    from api import router as api_router
    from ratelimit import RateLimiter
    monkeypatch.setattr(api_router, "_per_user", RateLimiter(limit=2, window_seconds=60))
    h = headers(sub="spammer")
    codes = [client.post("/api/solve-text", data={"latex_expression": "1 + 1"}, headers=h).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


# ── Consumer law ──────────────────────────────────────────────────────────────

def test_withdrawal_request_gives_a_code_without_login(accounts):
    r = client.post("/api/legal/arrepentimiento", json={"email": "Buyer@Example.com", "details": "Me arrepentí"})
    assert r.status_code == 201 and r.json()["code"].startswith("ARR-")
    db = database.SessionLocal()
    saved = db.query(models.RevocationRequest).filter_by(code=r.json()["code"]).one()
    assert saved.email == "buyer@example.com"
    db.close()


def test_withdrawal_form_is_rate_limited(accounts, monkeypatch):
    from api import legal
    from ratelimit import RateLimiter
    monkeypatch.setattr(legal, "_limiter", RateLimiter(limit=2, window_seconds=3600))
    codes = [client.post("/api/legal/arrepentimiento", json={"email": "x@example.com"}).status_code for _ in range(3)]
    assert codes == [201, 201, 429]
