"""Runtime configuration from environment variables (and an optional backend/.env file)."""
import os

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'mathvision.db')}")
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(BASE_DIR, "temp"))
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "10"))

# Comma-separated list of allowed origins. Localhost on any port is always allowed (dev).
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]

# Symbolic solving runs in separate processes (see solver_pool.py).
# 0 disables the pool and solves in the request thread, without time limit (debugging only).
SOLVER_WORKERS = int(os.environ.get("SOLVER_WORKERS", "2"))
SOLVE_TIMEOUT_SECONDS = float(os.environ.get("SOLVE_TIMEOUT_SECONDS", "20"))
# How long a request waits for a free worker before getting 503
SOLVER_QUEUE_TIMEOUT = float(os.environ.get("SOLVER_QUEUE_TIMEOUT", "15"))

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".pdf"}

# Fail closed: anything that is not explicitly "development" or "test" (missing, misspelled)
# is treated as production, which refuses to start with unsafe settings (production_problems).
ENV = os.environ.get("ENV", "production").strip().lower()
IS_DEV = ENV in ("development", "test")

# ── Accounts (Supabase Auth) ──────────────────────────────────────────────────
# https://<project>.supabase.co. Without it (local development only) every request
# runs as a single local user, so the app works without creating a Supabase project.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
AUTH_ENABLED = bool(SUPABASE_URL)
# Secret, backend only: lets "delete my account" also delete the login in Supabase.
# Without it the app data is deleted, but the Supabase user has to be removed by hand.
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# ── Plans and daily limits ────────────────────────────────────────────────────
FREE_EXERCISES_PER_DAY = int(os.environ.get("FREE_EXERCISES_PER_DAY", "15"))
FREE_AI_PER_DAY = int(os.environ.get("FREE_AI_PER_DAY", "3"))
# Pro is "unlimited" for a person; the caps only stop abuse (scripts, shared accounts)
PRO_EXERCISES_PER_DAY = int(os.environ.get("PRO_EXERCISES_PER_DAY", "500"))
PRO_AI_PER_DAY = int(os.environ.get("PRO_AI_PER_DAY", "100"))
PRO_PRICE_ARS = float(os.environ.get("PRO_PRICE_ARS", "5000"))
# Burst limit per account (exercises per minute), on top of the daily quota
USER_REQUESTS_PER_MINUTE = int(os.environ.get("USER_REQUESTS_PER_MINUTE", "20"))
# Days of Pro kept after the expected renewal date, in case the charge is delayed
PRO_GRACE_DAYS = int(os.environ.get("PRO_GRACE_DAYS", "3"))
# Daily limits reset at midnight of this UTC offset (Argentina: -3, no daylight saving)
USAGE_UTC_OFFSET_HOURS = int(os.environ.get("USAGE_UTC_OFFSET_HOURS", "-3"))

# ── AI cost tracking (USD per million tokens of GEMINI_MODEL) ────────────────
AI_PRICE_INPUT_PER_M = float(os.environ.get("AI_PRICE_INPUT_PER_M", "0.75"))
AI_PRICE_OUTPUT_PER_M = float(os.environ.get("AI_PRICE_OUTPUT_PER_M", "3.75"))

# ── Mercado Pago (subscriptions) ──────────────────────────────────────────────
MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN", "")
MP_WEBHOOK_SECRET = os.environ.get("MP_WEBHOOK_SECRET", "")
BILLING_ENABLED = bool(MP_ACCESS_TOKEN)
# Public URL of the web app (Mercado Pago sends the user back here after paying)
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173").rstrip("/")


def production_problems() -> list[str]:
    """Settings that are fine on a laptop and dangerous with real users and real money."""
    if IS_DEV:
        return []
    problems = []
    if not AUTH_ENABLED:
        problems.append("SUPABASE_URL is not set: everyone would share one account")
    if AUTH_ENABLED and not SUPABASE_SERVICE_ROLE_KEY:
        problems.append("SUPABASE_SERVICE_ROLE_KEY is not set: deleted accounts would keep their login")
    if DATABASE_URL.startswith("sqlite"):
        problems.append("DATABASE_URL is SQLite: use Postgres (Supabase) in production")
    if not CORS_ORIGINS:
        problems.append("CORS_ORIGINS is empty")
    if BILLING_ENABLED and not MP_WEBHOOK_SECRET:
        problems.append("MP_WEBHOOK_SECRET is not set: payment notifications could not be authenticated")
    if FRONTEND_URL.startswith("http://localhost"):
        problems.append("FRONTEND_URL points to localhost")
    return problems
