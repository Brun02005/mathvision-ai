"""
Consumer-law endpoints (Argentina).

"Botón de arrepentimiento" (Res. SCI 424/2020): a purchase can be revoked within 10
days; the request must not require registration or any other step, and the
consumer gets an identification code. The code is returned immediately; the
request is then processed by a person (refund + cancellation in Mercado Pago).
"""
import logging
import re
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import database
import models
from ratelimit import RateLimiter

router = APIRouter()
logger = logging.getLogger(__name__)

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Public form: a few requests per address per hour is plenty for a person, too few for a flood
_limiter = RateLimiter(limit=5, window_seconds=3600)


class RevocationIn(BaseModel):
    email: str = Field(max_length=320)
    name: str = Field(default="", max_length=200)
    details: str = Field(default="", max_length=2000)


@router.post("/legal/arrepentimiento", status_code=201)
def request_revocation(body: RevocationIn, request: Request, db: Session = Depends(database.get_db)):
    if not _limiter.allow(request.client.host if request.client else "unknown"):
        raise HTTPException(429, "Recibimos varias solicitudes desde tu conexión. Probá de nuevo en una hora.")
    email = body.email.strip().lower()
    if not _EMAIL.match(email):
        raise HTTPException(422, "Ingresá un email válido: es el de la cuenta con la que pagaste.")
    for _ in range(5):
        code = f"ARR-{secrets.token_hex(4).upper()}"
        db.add(models.RevocationRequest(code=code, email=email, name=body.name.strip() or None,
                                        details=body.details.strip() or None))
        try:
            db.commit()
            break
        except IntegrityError:
            db.rollback()  # code collision (1 in 4 billion): draw another
    else:
        raise HTTPException(500, "No pudimos registrar la solicitud. Escribinos por email.")
    # Operators watch for this line until there is an email notification
    logger.warning(f"Withdrawal request {code} received")
    return {
        "code": code,
        "message": "Recibimos tu solicitud de arrepentimiento. Guardá este código: te vamos a contactar por email "
                   "para confirmar la cancelación y el reintegro.",
    }
