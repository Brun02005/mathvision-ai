"""
Accounts: the backend never sees passwords. Supabase Auth logs the user in (email,
Google) and gives the browser a signed JWT; every request sends it as
`Authorization: Bearer <token>` and here we only verify it.

Verification uses Supabase's public signing keys (JWKS, asymmetric ES256/RS256):
anyone can check a signature, only Supabase can produce one. Expired tokens,
another project's tokens and tokens for another audience are rejected.

Without SUPABASE_URL (local development) every request is the single user
"local", so the app runs without creating a Supabase project. config.ENV =
"production" refuses to start in that mode (see config.production_problems).
"""
import logging

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import config
import database
import models

logger = logging.getLogger(__name__)

LOCAL_USER_ID = "local"
ALGORITHMS = ["ES256", "RS256"]

_jwks_client: jwt.PyJWKClient | None = None


def _signing_key(token: str):
    """Public key matching the token's `kid`. Keys are cached briefly so a key rotation is picked up."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(f"{config.SUPABASE_URL}/auth/v1/.well-known/jwks.json",
                                       cache_jwk_set=True, lifespan=600, timeout=5)
    return _jwks_client.get_signing_key_from_jwt(token).key


def verify_token(token: str) -> dict:
    """Claims of a valid Supabase access token; raises HTTPException(401) otherwise."""
    try:
        return jwt.decode(
            token,
            _signing_key(token),
            algorithms=ALGORITHMS,
            audience="authenticated",
            issuer=f"{config.SUPABASE_URL}/auth/v1",
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Tu sesión expiró. Volvé a iniciar sesión.") from None
    except jwt.PyJWKClientError as e:
        # Could not reach Supabase or unknown key id: not the user's fault, but we cannot trust the token
        logger.warning(f"JWKS error: {e}")
        raise HTTPException(401, "No pudimos validar tu sesión. Volvé a iniciar sesión.") from None
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Sesión inválida. Volvé a iniciar sesión.") from None


def _get_or_create_user(db: Session, user_id: str, email: str | None) -> models.User:
    user = db.get(models.User, user_id)
    if user is not None:
        if email and user.email != email:
            user.email = email
            db.commit()
        return user
    user = models.User(id=user_id, email=email)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Two first requests of the same new user at once: the other one created it
        db.rollback()
        return db.get(models.User, user_id)
    if user_id == LOCAL_USER_ID:
        # Local development: adopt the exercises saved before accounts existed
        db.query(models.Exercise).filter(models.Exercise.user_id.is_(None)).update({"user_id": LOCAL_USER_ID})
        db.commit()
    return user


def current_user(request: Request, db: Session = Depends(database.get_db)) -> models.User:
    """FastAPI dependency: the authenticated user of this request."""
    if not config.AUTH_ENABLED:
        if not config.IS_DEV:
            # Second barrier behind production_problems(): never share one account outside development
            raise HTTPException(503, "El servicio no está configurado.")
        return _get_or_create_user(db, LOCAL_USER_ID, "local@localhost")
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Iniciá sesión para continuar.", headers={"WWW-Authenticate": "Bearer"})
    claims = verify_token(token)
    return _get_or_create_user(db, claims["sub"], claims.get("email"))
