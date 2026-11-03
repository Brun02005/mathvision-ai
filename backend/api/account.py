"""
Account and billing endpoints: who am I, my plan and usage, subscribe, cancel,
and the Mercado Pago webhook.
"""
import logging
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

import config
import database
import models
from auth import current_user
from billing import mercadopago, usage

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/me")
def me(user: models.User = Depends(current_user), db: Session = Depends(database.get_db)):
    return {
        "id": user.id,
        "email": user.email,
        "plan": "pro" if user.is_pro() else "free",
        "pro_until": models.as_utc(user.pro_until),
        "subscription_status": user.mp_status,
        "usage": usage.summary(db, user),
        "billing_enabled": config.BILLING_ENABLED,
        "price_ars": config.PRO_PRICE_ARS,
        "auth_enabled": config.AUTH_ENABLED,
    }


@router.delete("/me", status_code=204)
def delete_account(user: models.User = Depends(current_user), db: Session = Depends(database.get_db)):
    """
    Right to deletion (Ley 25.326). Order matters, and each step aborts the rest if it fails:
    1. cancel an active subscription (otherwise the user keeps paying with no account left);
    2. delete the Supabase login (otherwise logging in again would recreate the account,
       which would also reset the daily quota);
    3. delete exercises, usage and the user; payments are kept anonymized (tax records, disputes).
    """
    if user.mp_preapproval_id and user.mp_status in mercadopago.ACTIVE:
        try:
            mercadopago.cancel_subscription(user.mp_preapproval_id)
        except mercadopago.MercadoPagoError as e:
            logger.error(f"Account deletion of {user.id} stopped, subscription not cancelled: {e}")
            raise HTTPException(502, "No pudimos cancelar tu suscripción en Mercado Pago, así que no borramos nada. "
                                     "Probá de nuevo en unos minutos.") from None
    user_id = user.id
    if not _delete_login(user_id):
        raise HTTPException(502, "No pudimos eliminar tu acceso, así que no borramos nada. Probá de nuevo en unos minutos.")
    files = [p for (p,) in db.query(models.Exercise.original_image_path)
             .filter(models.Exercise.user_id == user_id, models.Exercise.original_image_path.isnot(None))]
    db.query(models.Payment).filter(models.Payment.user_id == user_id).update({"user_id": None})
    db.query(models.Exercise).filter(models.Exercise.user_id == user_id).delete(synchronize_session=False)
    db.query(models.DailyUsage).filter(models.DailyUsage.user_id == user_id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()
    for path in files:
        try:
            os.remove(path)
        except OSError:
            pass
    logger.info(f"Account {user_id} deleted")


def _delete_login(user_id: str) -> bool:
    """
    Remove the Supabase Auth user (needs the service role key, which never leaves the
    backend). True when there is nothing else to delete. Production requires the key.
    """
    if not config.AUTH_ENABLED:
        return True  # local development: there is no login
    if not config.SUPABASE_SERVICE_ROLE_KEY:
        logger.error(f"Supabase login of {user_id} not deleted: SUPABASE_SERVICE_ROLE_KEY is not set")
        return False
    key = config.SUPABASE_SERVICE_ROLE_KEY
    try:
        r = httpx.delete(f"{config.SUPABASE_URL}/auth/v1/admin/users/{user_id}", timeout=10,
                         headers={"apikey": key, "Authorization": f"Bearer {key}"})
        if r.status_code == 404:
            return True  # already gone
        r.raise_for_status()
    except httpx.HTTPError as e:
        logger.error(f"Supabase login of {user_id} could not be deleted: {e}")
        return False
    return True


@router.post("/billing/subscribe")
def subscribe(user: models.User = Depends(current_user), db: Session = Depends(database.get_db)):
    if not config.BILLING_ENABLED:
        raise HTTPException(503, "Los pagos todavía no están habilitados.")
    if not user.email:
        raise HTTPException(400, "Tu cuenta no tiene email: Mercado Pago lo necesita para la suscripción.")
    try:
        # Never two subscriptions at once: look at the real state of the current one first
        if user.mp_preapproval_id and user.mp_status in mercadopago.ACTIVE:
            current = mercadopago.get_subscription(user.mp_preapproval_id)
            user.mp_status = current.get("status")
            db.commit()
            if user.mp_status in ("authorized", "paused"):
                raise HTTPException(409, "Ya tenés una suscripción activa. Para cambiarla, cancelala primero.")
            if user.mp_status == "pending" and current.get("init_point"):
                return {"checkout_url": current["init_point"]}  # finish the checkout already started
        checkout_url, preapproval_id = mercadopago.create_subscription(user)
    except mercadopago.MercadoPagoError as e:
        logger.error(f"Subscription creation failed for {user.id}: {e}")
        raise HTTPException(502, "Mercado Pago no respondió. Probá de nuevo en unos minutos.") from None
    if preapproval_id:
        user.mp_preapproval_id, user.mp_status = preapproval_id, "pending"
        db.commit()
    return {"checkout_url": checkout_url}


@router.post("/billing/cancel")
def cancel(user: models.User = Depends(current_user), db: Session = Depends(database.get_db)):
    if not user.mp_preapproval_id or user.mp_status == "cancelled":
        raise HTTPException(409, "No tenés una suscripción activa.")
    try:
        mercadopago.cancel_subscription(user.mp_preapproval_id)
    except mercadopago.MercadoPagoError as e:
        logger.error(f"Cancel failed for {user.id}: {e}")
        raise HTTPException(502, "Mercado Pago no respondió. Probá de nuevo en unos minutos.") from None
    user.mp_status = "cancelled"
    db.commit()
    # What was already paid is kept: Pro lasts until pro_until
    return {"plan": "pro" if user.is_pro() else "free", "pro_until": models.as_utc(user.pro_until)}


@router.post("/billing/webhook")
async def webhook(request: Request, db: Session = Depends(database.get_db)):
    """
    Public endpoint called by Mercado Pago. 401 for a bad signature; 500 when the
    Mercado Pago API fails, so it retries later; 200 otherwise (including
    notifications we ignore, so it does not keep retrying them).
    """
    data_id = request.query_params.get("data.id") or request.query_params.get("id") or ""
    topic = request.query_params.get("type") or request.query_params.get("topic") or ""
    try:
        body = await request.json()
    except Exception:
        body = {}
    if isinstance(body, dict):
        topic = topic or body.get("type") or body.get("topic") or ""
        data_id = data_id or str((body.get("data") or {}).get("id") or "")

    if not mercadopago.signature_is_valid(request.headers.get("x-signature", ""),
                                          request.headers.get("x-request-id", ""), data_id):
        logger.warning(f"Rejected Mercado Pago notification with invalid signature ({topic}:{data_id})")
        raise HTTPException(401, "Invalid signature")
    if not data_id:
        return {"ok": True}
    try:
        # Sync DB + HTTP work: run it off the event loop
        await run_in_threadpool(mercadopago.handle_notification, db, topic, data_id)
    except mercadopago.MercadoPagoError as e:
        logger.error(f"Webhook {topic}:{data_id} failed, Mercado Pago will retry: {e}")
        raise HTTPException(500, "Temporary error") from None
    return {"ok": True}
