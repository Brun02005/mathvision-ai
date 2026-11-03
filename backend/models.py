import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, String, Text

from database import Base


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


def as_utc(value: datetime.datetime | None) -> datetime.datetime | None:
    """SQLite returns naive datetimes: treat them as the UTC they were stored in."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=datetime.timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True)  # Supabase Auth user id (the token's "sub")
    email = Column(String(320), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    # Pro is an entitlement with an end date, not a flag: it lapses by itself if a
    # renewal never arrives, without any job having to turn it off.
    pro_until = Column(DateTime(timezone=True), nullable=True)
    mp_preapproval_id = Column(String(64), nullable=True, unique=True)
    mp_status = Column(String(20), nullable=True)

    def is_pro(self, now: datetime.datetime | None = None) -> bool:
        until = as_utc(self.pro_until)
        return until is not None and until > (now or _utcnow())


class DailyUsage(Base):
    """One row per user and day: what the limits are checked against and what the AI cost."""
    __tablename__ = "daily_usage"

    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    day = Column(Date, primary_key=True)
    exercises = Column(Integer, nullable=False, default=0)
    ai_calls = Column(Integer, nullable=False, default=0)
    ai_input_tokens = Column(Integer, nullable=False, default=0)
    ai_output_tokens = Column(Integer, nullable=False, default=0)
    # Money as integer micro-dollars: floats accumulate rounding errors
    ai_cost_micro_usd = Column(Integer, nullable=False, default=0)


class Payment(Base):
    """
    Ledger of subscription charges. Pro is derived from it: pro_until is the latest
    `grants_until` among APPROVED payments, so a refund or a chargeback (status change)
    takes the entitlement away by itself, and repeating a notification changes nothing.
    """
    __tablename__ = "payments"

    id = Column(String(40), primary_key=True)  # Mercado Pago payment id
    # Kept (anonymized: user_id NULL) when the account is deleted: payments are needed for
    # tax records and disputes, and hold no personal data by themselves
    user_id = Column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    preapproval_id = Column(String(64), nullable=True)
    status = Column(String(20), nullable=False)
    paid_at = Column(DateTime(timezone=True), nullable=False)
    grants_until = Column(DateTime(timezone=True), nullable=False)


class RevocationRequest(Base):
    """
    "Botón de arrepentimiento" (Res. SCI 424/2020): anyone can ask to revoke a purchase
    within 10 days, without logging in, and gets an identification code. Requests are
    then handled by a person (refund in Mercado Pago, cancel the subscription).
    """
    __tablename__ = "revocation_requests"

    id = Column(Integer, primary_key=True)
    code = Column(String(20), nullable=False, unique=True)
    email = Column(String(320), nullable=False)
    name = Column(String(200), nullable=True)
    details = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pendiente")
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)


class Exercise(Base):
    __tablename__ = "exercises"
    __table_args__ = (Index("ix_exercises_user_created", "user_id", "created_at"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    original_image_path = Column(String, nullable=True)
    extracted_latex = Column(Text, nullable=False)
    domain_classification = Column(String, nullable=True)  # e.g. "Cálculo Integral", "Física"
    symbolic_representation = Column(Text, nullable=True)
    solution_steps_json = Column(Text, nullable=True)  # JSON list of steps in Spanish
    final_result_latex = Column(Text, nullable=True)
    graph_data_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)
