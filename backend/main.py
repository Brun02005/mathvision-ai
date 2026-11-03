import logging
import time
import uuid
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

import config
import database
import solver_pool
from api import account, legal
from api import router as api_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# Fail fast: better not to start than to run with real users on unsafe settings
_problems = config.production_problems()
if _problems:
    raise RuntimeError(f"Unsafe configuration for ENV={config.ENV!r} (production unless ENV is "
                       "'development' or 'test'; for local work put ENV=development in backend/.env):\n- "
                       + "\n- ".join(_problems))


@asynccontextmanager
async def lifespan(app: FastAPI):
    if config.SOLVER_WORKERS > 0:
        solver_pool.get_pool()  # start the worker processes now so the first request doesn't wait for them
    yield
    solver_pool.shutdown()


app = FastAPI(
    lifespan=lifespan,
    title="MathVision AI",
    description="Resolución paso a paso de ejercicios de matemática y física.",
    version=api_router.API_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    # Any localhost port during development only
    allow_origin_regex=None if not config.IS_DEV else r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=False,  # the session travels in the Authorization header, not in cookies
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

database.migrate()

access_log = logging.getLogger("access")


@app.middleware("http")
async def request_id_and_access_log(request: Request, call_next):
    """
    Every response carries an X-Request-ID, and the same id is in the access log line:
    when a user reports "it failed", that id finds the exact request in the logs.
    Only method, path, status and time are logged: no query strings, bodies or tokens.
    """
    request_id = uuid.uuid4().hex[:12]
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        access_log.exception(f"{request_id} {request.method} {request.url.path} 500")
        raise
    response.headers["X-Request-ID"] = request_id
    elapsed_ms = (time.perf_counter() - start) * 1000
    access_log.info(f"{request_id} {request.method} {request.url.path} {response.status_code} {elapsed_ms:.0f}ms")
    return response


app.include_router(api_router.router, prefix="/api")
app.include_router(account.router, prefix="/api")
app.include_router(legal.router, prefix="/api")


@app.get("/")
def read_root():
    return {"message": "Welcome to MathVision AI API"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
