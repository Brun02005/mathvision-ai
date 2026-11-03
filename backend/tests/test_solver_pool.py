import math
import threading
import time

import pytest

from solver_pool import SolverBusy, SolverPool, SolverTimeout


@pytest.fixture
def pool():
    p = SolverPool(size=1, timeout=2, queue_timeout=60)
    assert p.wait_ready(60)
    yield p
    p.close()


def test_returns_result(pool):
    assert pool.run(math.factorial, 5) == 120


def test_propagates_value_error(pool):
    with pytest.raises(ValueError):
        pool.run(int, "no es un número")


def test_timeout_kills_the_job_and_the_pool_recovers(pool):
    start = time.monotonic()
    with pytest.raises(SolverTimeout):
        pool.run(time.sleep, 60)
    assert time.monotonic() - start < 10
    assert pool.run(abs, -3) == 3  # a fresh worker replaced the killed one


def test_rejects_instead_of_queueing_forever(pool):
    busy = threading.Thread(target=pool.run, args=(time.sleep, 1))
    busy.start()
    while pool._idle.qsize():  # wait until the background job holds the only worker
        time.sleep(0.01)
    pool.queue_timeout = 0.2
    with pytest.raises(SolverBusy):
        pool.run(abs, -1)
    busy.join()
