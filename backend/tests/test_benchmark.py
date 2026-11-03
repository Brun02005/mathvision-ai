"""
Every golden-set exercise must give the mathematically correct answer.
Known gaps are marked xfail(strict) in cases.py: when one gets fixed, the test
fails until the mark is removed, so the list of limitations never goes stale.
"""
import pytest

from benchmark import run_case
from benchmark import ALL_CASES


def _param(case):
    marks = [pytest.mark.xfail(reason=case.xfail, strict=True)] if case.xfail else []
    return pytest.param(case, id=f"{case.topic}: {case.latex[:50]}", marks=marks)


@pytest.mark.parametrize("case", [_param(c) for c in ALL_CASES])
def test_golden_case(case):
    outcome = run_case(case)
    assert outcome.passed, outcome.detail
