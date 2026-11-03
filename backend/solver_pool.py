"""
Isolated, time-limited execution of the symbolic solver.

A Python thread cannot be killed: an input SymPy needs minutes for (a nasty
integral, a huge polynomial) would hold a server thread until it finished, and
a few of those would exhaust the server. Solving runs instead in a small pool
of worker processes. A worker that exceeds the time limit is killed and
replaced, and the request gets a clear error.

The pool also bounds concurrency (backpressure): at most `size` exercises are
solved at once. Extra requests wait up to `queue_timeout` seconds for a free
worker and are then rejected, instead of piling up until memory runs out.
"""
import importlib
import logging
import multiprocessing as mp
import os
import queue
import threading
import time

import config

logger = logging.getLogger(__name__)

STARTUP_TIMEOUT = 120

# spawn, not fork: forking a multithreaded server can copy a lock held by
# another thread into the child, which then deadlocks on it.
_ctx = mp.get_context("spawn")


class SolverTimeout(Exception):
    """The job exceeded the time limit; its worker was killed."""


class SolverBusy(Exception):
    """Every worker stayed busy for longer than the queue timeout."""


class SolverCrashed(Exception):
    """The worker process died while running the job."""


# The workers only do math on user input. They never need credentials, so they never
# get them: if a parsing bug were ever exploited, there would be no secret to steal.
SECRETS = ("GEMINI_API_KEY", "MP_ACCESS_TOKEN", "MP_WEBHOOK_SECRET", "SUPABASE_SERVICE_ROLE_KEY", "DATABASE_URL")


def _worker_main(conn, preload: tuple[str, ...]):
    for name in SECRETS:
        os.environ[name] = ""  # "" rather than deleted: load_dotenv would refill a missing one from .env
    for name in preload:
        importlib.import_module(name)
    conn.send(("ready", None))
    while True:
        try:
            func, args = conn.recv()
        except EOFError:
            return  # the server process is gone
        try:
            conn.send(("ok", func(*args)))
        except ValueError as e:
            conn.send(("value_error", str(e)))
        except Exception as e:
            conn.send(("error", f"{type(e).__name__}: {e}"))


class _Worker:
    def __init__(self, preload: tuple[str, ...]):
        self.conn, child = _ctx.Pipe()
        self.process = _ctx.Process(target=_worker_main, args=(child, preload), daemon=True)
        self.process.start()
        child.close()

    def wait_ready(self, timeout: float) -> bool:
        try:
            return self.conn.poll(timeout) and self.conn.recv()[0] == "ready"
        except (EOFError, OSError):
            return False

    def kill(self):
        self.process.kill()
        self.process.join(timeout=5)
        self.conn.close()


class SolverPool:
    def __init__(self, size: int, timeout: float, queue_timeout: float, preload: tuple[str, ...] = ()):
        self.size = size
        self.timeout = timeout
        self.queue_timeout = queue_timeout
        self.preload = preload
        self._idle: queue.Queue[_Worker] = queue.Queue()
        self._workers: set[_Worker] = set()
        self._lock = threading.Lock()
        self._closed = False
        for _ in range(size):
            self._spawn()

    def _spawn(self):
        """Start a worker in the background; it becomes available once its imports finish."""
        def start():
            worker = _Worker(self.preload)
            with self._lock:
                if self._closed:
                    worker.kill()
                    return
                self._workers.add(worker)
            if worker.wait_ready(STARTUP_TIMEOUT):
                self._idle.put(worker)
            else:
                # Not respawned: a worker that cannot start would fail the same way in a loop
                logger.error("Solver worker failed to start")
                self._discard(worker)
        threading.Thread(target=start, name="solver-spawn", daemon=True).start()

    def _discard(self, worker: _Worker):
        with self._lock:
            self._workers.discard(worker)
        worker.kill()

    def _replace(self, worker: _Worker):
        self._discard(worker)
        if not self._closed:
            self._spawn()

    def run(self, func, *args):
        """Run `func(*args)` in a worker. `func` must be a module-level (picklable) function."""
        if self._closed:
            raise SolverBusy()
        try:
            worker = self._idle.get(timeout=self.queue_timeout)
        except queue.Empty:
            raise SolverBusy() from None

        try:
            worker.conn.send((func, args))
            finished = worker.conn.poll(self.timeout)
            if finished:
                status, payload = worker.conn.recv()
        except (EOFError, OSError):
            self._replace(worker)
            raise SolverCrashed() from None
        except BaseException:
            # e.g. unpicklable args: the worker state is unknown, so don't reuse it
            self._replace(worker)
            raise
        if not finished:
            # No arguments at WARNING: they are user content (exercises, file paths)
            logger.warning(f"Solver job {getattr(func, '__name__', func)} exceeded {self.timeout}s; restarting its worker")
            logger.debug(f"Timed-out job args: {str(args)[:200]}")
            self._replace(worker)
            raise SolverTimeout()
        self._idle.put(worker)

        if status == "ok":
            return payload
        if status == "value_error":
            raise ValueError(payload)
        raise RuntimeError(payload)

    def wait_ready(self, timeout: float) -> bool:
        """Block until every worker is idle and ready (used by tests and startup checks)."""
        deadline = time.monotonic() + timeout
        while self._idle.qsize() < self.size:
            if time.monotonic() > deadline:
                return False
            time.sleep(0.05)
        return True

    def close(self):
        with self._lock:
            self._closed = True
            workers = list(self._workers)
            self._workers.clear()
        for worker in workers:
            worker.kill()


_pool: SolverPool | None = None
_pool_lock = threading.Lock()


def get_pool() -> SolverPool:
    """The process-wide pool, created on first use (or at startup by main.py)."""
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = SolverPool(config.SOLVER_WORKERS, config.SOLVE_TIMEOUT_SECONDS,
                               config.SOLVER_QUEUE_TIMEOUT, preload=("pipeline",))
        return _pool


def shutdown():
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.close()
            _pool = None
