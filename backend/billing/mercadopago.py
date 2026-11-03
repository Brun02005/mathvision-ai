"""
Monthly subscription with Mercado Pago (preapproval without an associated plan).

Flow:
1. subscribe: we create a "pending" preapproval whose external_reference is our
   user id, and send the user to its checkout (init_point) to enter a card.
2. Mercado Pago notifies our webhook: "subscription_preapproval" when the
   subscription changes (authorized, paused, cancelled) and
   "subscription_authorized_payment" for every monthly charge.
3. For every notification we verify the signature and then ask the Mercado Pago
   API for the real state. The notification body is never trusted.

Pro is granted by APPROVED PAYMENTS, not by an "authorized" subscription: a
subscription can be authorized with a card that is later declined. Each approved
charge moves `pro_until` to one month after the charge (plus grace days).
Processing the same payment twice gives the same date (max, not addition):
webhooks are delivered at least once and can repeat.

Field names follow Mercado Pago's API reference; test the whole flow in its
sandbox (test users and test cards) before charging real money.
"""
import datetime
import hashlib
import hmac
import logging

import httpx
from sqlalchemy.orm import Session

import config
import models

logger = logging.getLogger(__name__)

API_URL = "https://api.mercadopago.com"
MONTH = datetime.timedelta(days=31)


class MercadoPagoError(Exception):
    """The Mercado Pago API failed or answered something unexpected."""


def _http() -> httpx.Client:
    return httpx.Client(base_url=API_URL, timeout=10,
                        headers={"Authorization": f"Bearer {config.MP_ACCESS_TOKEN}"})


def _call(method: str, path: str, **kwargs) -> dict:
    try:
        with _http() as client:
            response = client.request(method, path, **kwargs)
    except httpx.HTTPError as e:
        raise MercadoPagoError(f"{method} {path}: {e}") from e
    if response.status_code >= 400:
        raise MercadoPagoError(f"{method} {path}: HTTP {response.status_code} {response.text[:300]}")
    return response.json()


def _parse_date(value: str | None) -> datetime.datetime | None:
    """Mercado Pago dates carry their own offset (-03:00). Converted to UTC: the database
    stores datetimes without offset, so anything not in UTC would be shifted when read back."""
    if not value:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


# ── Subscriptions ─────────────────────────────────────────────────────────────

def create_subscription(user: models.User) -> tuple[str, str | None]:
    """Create a pending subscription for the user; returns (checkout URL, preapproval id)."""
    # Same key for repeated clicks (Mercado Pago returns the same subscription instead of a
    # second one); a new key once the previous subscription changed.
    idempotency_key = f"sub-{user.id}-{user.mp_preapproval_id or 'first'}"
    data = _call("POST", "/preapproval", headers={"X-Idempotency-Key": idempotency_key}, json={
        "reason": "MathVision Pro (mensual)",
        "external_reference": user.id,
        "payer_email": user.email,
        "auto_recurring": {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": config.PRO_PRICE_ARS,
            "currency_id": "ARS",
        },
        "back_url": f"{config.FRONTEND_URL}/cuenta?pago=ok",
        "status": "pending",
    })
    if not data.get("init_point"):
        raise MercadoPagoError(f"preapproval without init_point: {data}")
    return data["init_point"], data.get("id")


def cancel_subscription(preapproval_id: str) -> dict:
    return _call("PUT", f"/preapproval/{preapproval_id}", json={"status": "cancelled"})


def get_subscription(preapproval_id: str) -> dict:
    return _call("GET", f"/preapproval/{preapproval_id}")


# ── Webhook ───────────────────────────────────────────────────────────────────

def signature_is_valid(x_signature: str, x_request_id: str, data_id: str) -> bool:
    """
    Mercado Pago signs "id:<data.id>;request-id:<x-request-id>;ts:<ts>;" with
    HMAC-SHA256 and the webhook secret; parts whose value is missing are omitted.
    """
    if not config.MP_WEBHOOK_SECRET or not x_signature:
        return False
    parts = dict(p.strip().split("=", 1) for p in x_signature.split(",") if "=" in p)
    ts, received = parts.get("ts"), parts.get("v1")
    if not ts or not received:
        return False
    data_id = data_id.lower() if data_id and data_id.isalnum() else data_id
    manifest = "".join(f"{key}:{value};" for key, value in
                       (("id", data_id), ("request-id", x_request_id), ("ts", ts)) if value)
    expected = hmac.new(config.MP_WEBHOOK_SECRET.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    # compare_digest: constant time, so the comparison does not leak how many characters matched
    return hmac.compare_digest(expected, received)


def _user_of(db: Session, preapproval: dict) -> models.User | None:
    user = db.get(models.User, preapproval.get("external_reference") or "")
    if user is None:
        logger.error(f"Mercado Pago preapproval {preapproval.get('id')} has no matching user "
                     f"(external_reference={preapproval.get('external_reference')!r})")
    return user


ACTIVE = ("pending", "authorized", "paused")


def _cancel_quietly(user: models.User, preapproval_id: str):
    try:
        cancel_subscription(preapproval_id)
        logger.warning(f"User {user.id} had two authorized subscriptions: cancelled {preapproval_id}")
    except MercadoPagoError as e:
        logger.error(f"User {user.id}: could not cancel duplicate subscription {preapproval_id}: {e}")


def _resolve_authorized(user: models.User, incoming: dict):
    """
    `incoming` is authorized. If the user's current subscription is a DIFFERENT one that is
    also authorized, one must go (a user must never be charged twice): the NEWER one is
    kept, decided by creation date and never by the order notifications arrive in,
    because Mercado Pago may deliver them late, repeated or out of order.
    """
    current_id = user.mp_preapproval_id
    if not current_id or current_id == incoming["id"]:
        user.mp_preapproval_id, user.mp_status = incoming["id"], "authorized"
        return
    current = get_subscription(current_id)
    if current.get("status") != "authorized":
        user.mp_preapproval_id, user.mp_status = incoming["id"], "authorized"
        return
    incoming_date = _parse_date(incoming.get("date_created"))
    current_date = _parse_date(current.get("date_created"))
    if incoming_date and current_date and incoming_date < current_date:
        _cancel_quietly(user, incoming["id"])  # the incoming one is the older duplicate
        return
    _cancel_quietly(user, current_id)
    user.mp_preapproval_id, user.mp_status = incoming["id"], "authorized"


def recompute_entitlement(db: Session, user: models.User):
    """pro_until = latest period paid by an approved payment (None if there is none left)."""
    approved = db.query(models.Payment).filter(models.Payment.user_id == user.id,
                                               models.Payment.status == "approved").all()
    user.pro_until = max((models.as_utc(p.grants_until) for p in approved), default=None)


def sync_subscription(db: Session, preapproval_id: str):
    """Record the subscription's current status. It never grants Pro by itself."""
    preapproval = get_subscription(preapproval_id)
    user = _user_of(db, preapproval)
    if user is None:
        return
    status = preapproval.get("status")
    if status == "authorized":
        _resolve_authorized(user, {**preapproval, "id": preapproval_id})
    elif user.mp_preapproval_id in (None, preapproval_id):
        # Status changes of the tracked subscription; changes of others are just logged
        user.mp_preapproval_id, user.mp_status = preapproval_id, status
    db.commit()
    logger.info(f"Subscription {preapproval_id} of user {user.id}: {status}")


def _record_payment(db: Session, user: models.User, payment: dict, preapproval_id: str | None):
    """Upsert the payment in the ledger and recompute Pro. Idempotent by payment id."""
    payment_id = str(payment["id"])
    paid_at = (_parse_date(payment.get("date_approved")) or _parse_date(payment.get("date_created"))
               or datetime.datetime.now(datetime.timezone.utc))
    row = db.get(models.Payment, payment_id)
    if row is None:
        row = models.Payment(id=payment_id, user_id=user.id, preapproval_id=preapproval_id, paid_at=paid_at,
                             grants_until=paid_at + MONTH + datetime.timedelta(days=config.PRO_GRACE_DAYS),
                             status=payment.get("status") or "unknown")
        db.add(row)
    else:
        row.status = payment.get("status") or row.status
    db.flush()
    recompute_entitlement(db, user)
    db.commit()
    logger.info(f"Payment {payment_id} of user {user.id}: {row.status}; Pro until {user.pro_until}")


def sync_payment(db: Session, authorized_payment_id: str):
    """A monthly charge of a subscription: record its payment (approved ones grant one month)."""
    invoice = _call("GET", f"/authorized_payments/{authorized_payment_id}")
    payment_id = (invoice.get("payment") or {}).get("id") or invoice.get("payment_id")
    preapproval_id = invoice.get("preapproval_id")
    if not payment_id or not preapproval_id:
        logger.info(f"Authorized payment {authorized_payment_id} has no payment yet (status {invoice.get('status')})")
        return
    payment = _call("GET", f"/v1/payments/{payment_id}")
    user = _user_of(db, get_subscription(preapproval_id))
    if user is None:
        return
    # The payment path only records money. It never adopts or cancels subscriptions: a
    # late or repeated charge of an OLD subscription must not touch the current one.
    if user.mp_preapproval_id is None:
        user.mp_preapproval_id, user.mp_status = preapproval_id, "authorized"
    _record_payment(db, user, payment, preapproval_id)


def sync_refund(db: Session, payment_id: str):
    """
    A payment changed (refund, chargeback, cancellation). Only payments already in our
    ledger matter: updating their status recomputes Pro, so a refunded month is taken back.
    """
    row = db.get(models.Payment, str(payment_id))
    if row is None:
        logger.info(f"Payment {payment_id} is not a subscription charge we know: ignored")
        return
    payment = _call("GET", f"/v1/payments/{payment_id}")
    user = db.get(models.User, row.user_id)
    if user is not None:
        _record_payment(db, user, payment, row.preapproval_id)


def handle_notification(db: Session, topic: str, data_id: str):
    if topic == "subscription_preapproval":
        sync_subscription(db, data_id)
    elif topic == "subscription_authorized_payment":
        sync_payment(db, data_id)
    elif topic == "payment":
        sync_refund(db, data_id)
    else:
        logger.info(f"Ignored Mercado Pago notification {topic}:{data_id}")
