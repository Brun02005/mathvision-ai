import os
import sys
import tempfile

# Isolated database and upload folder for the whole test session.
# Must be set before any app module reads config.
_tmp = tempfile.mkdtemp(prefix="mathvision-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_tmp, 'test.db')}"
os.environ["UPLOAD_DIR"] = os.path.join(_tmp, "uploads")
os.environ.pop("GEMINI_API_KEY", None)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
