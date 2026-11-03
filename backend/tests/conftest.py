import os
import sys
import tempfile

# Isolated database and upload folder for the whole test session.
# Must be set before any app module reads config.
_tmp = tempfile.mkdtemp(prefix="mathvision-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_tmp, 'test.db')}"
os.environ["UPLOAD_DIR"] = os.path.join(_tmp, "uploads")
# Set to "" rather than removed: load_dotenv only fills variables that are absent, so
# removing them would let backend/.env (real keys, real Mercado Pago) leak into the tests
os.environ["GEMINI_API_KEY"] = ""
# API tests go through a real solver process; one is enough and a cold start can be slow on CI
os.environ["SOLVER_WORKERS"] = "1"
os.environ["SOLVER_QUEUE_TIMEOUT"] = "120"
# Local mode (single user) and generous quotas: limits have their own tests
for name in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "MP_ACCESS_TOKEN", "MP_WEBHOOK_SECRET"):
    os.environ[name] = ""
os.environ["ENV"] = "test"
os.environ["FREE_EXERCISES_PER_DAY"] = "100000"
os.environ["FREE_AI_PER_DAY"] = "100000"
os.environ["USER_REQUESTS_PER_MINUTE"] = "100000"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
