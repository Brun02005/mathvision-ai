"""
Daily limits per plan and AI cost metering.

Quotas are taken with a conditional UPDATE ("add one if still under the limit")
instead of read-then-write: with a SELECT followed by an UPDATE, two requests of
the same user arriving together would both read "1 left" and both pass. The
database applies the conditional UPDATE atomically, so exactly one of them wins.

A unit is reserved before solving and released if the exercise ends up unsolved,
so users only spend quota on answers they actually got.
"""
import datetime
from dataclasses import dataclass

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import config
import models

EXERCISES = "exercises"
AI = "ai_calls"


@dataclass(frozen=True)
class Limits:
    exercises: int
    ai_calls: int


def today() -> datetime.date:
    """The usage day, in the configured local time (limits reset at local midnight)."""
    offset = datetime.timedelta(hours=config.USAGE_UTC_OFFSET_HOURS)
    return (datetime.datetime.now(datetime.timezone.utc) + offset).date()


def limits_for(user: models.User) -> Limits:
    if config.IS_DEV and not config.AUTH_ENABLED:
        # Local development (single local user): limits would only get in the way of testing
        return Limits(10**9, 10**9)
    if user.is_pro():
        return Limits(config.PRO_EXERCISES_PER_DAY, config.PRO_AI_PER_DAY)
    return Limits(config.FREE_EXERCISES_PER_DAY, config.FREE_AI_PER_DAY)


def _ensure_row(db: Session, user_id: str, day: datetime.date):
    if db.get(models.DailyUsage, (user_id, day)) is None:
        db.add(models.DailyUsage(user_id=user_id, day=day, exercises=0, ai_calls=0,
                                 ai_input_tokens=0, ai_output_tokens=0, ai_cost_micro_usd=0))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()  # created by a concurrent request of the same user


def reserve(db: Session, user: models.User, kind: str) -> datetime.date | None:
    """Take one unit of today's quota. Returns the day it was taken from, or None at the limit."""
    day = today()
    _ensure_row(db, user.id, day)
    limit = getattr(limits_for(user), kind)
    column = getattr(models.DailyUsage, kind)
    result = db.execute(
        update(models.DailyUsage)
        .where(models.DailyUsage.user_id == user.id, models.DailyUsage.day == day, column < limit)
        .values({kind: column + 1})
    )
    db.commit()
    return day if result.rowcount == 1 else None


def release(db: Session, user: models.User, kind: str, day: datetime.date):
    """
    Give back a reserved unit to the day it was taken from: a request that started before
    midnight must not refund tomorrow's counter.
    """
    column = getattr(models.DailyUsage, kind)
    db.execute(
        update(models.DailyUsage)
        .where(models.DailyUsage.user_id == user.id, models.DailyUsage.day == day, column > 0)
        .values({kind: column - 1})
    )
    db.commit()


def ai_cost_micro_usd(input_tokens: int, output_tokens: int) -> int:
    # USD per million tokens is numerically the same as micro-dollars per token
    return round(input_tokens * config.AI_PRICE_INPUT_PER_M + output_tokens * config.AI_PRICE_OUTPUT_PER_M)


def record_ai_tokens(db: Session, user: models.User, input_tokens: int, output_tokens: int):
    """Add the tokens (and their cost) this request spent. Atomic increments, like the quotas."""
    if not input_tokens and not output_tokens:
        return
    day = today()
    _ensure_row(db, user.id, day)
    usage = models.DailyUsage
    db.execute(
        update(usage).where(usage.user_id == user.id, usage.day == day).values(
            ai_input_tokens=usage.ai_input_tokens + input_tokens,
            ai_output_tokens=usage.ai_output_tokens + output_tokens,
            ai_cost_micro_usd=usage.ai_cost_micro_usd + ai_cost_micro_usd(input_tokens, output_tokens),
        )
    )
    db.commit()


def summary(db: Session, user: models.User) -> dict:
    row = db.get(models.DailyUsage, (user.id, today()))
    limits = limits_for(user)
    return {
        "exercises": {"used": row.exercises if row else 0, "limit": limits.exercises},
        "ai": {"used": row.ai_calls if row else 0, "limit": limits.ai_calls},
    }
