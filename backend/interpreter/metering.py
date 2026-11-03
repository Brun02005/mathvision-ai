"""
Counts the AI tokens one request spends (OCR, translation, AI solving), so their
cost can be charged to the user who made the request.

A ContextVar instead of a parameter threaded through every function: the API
opens a meter around the request, and the code that calls Gemini, however deep,
adds to whichever meter is open in its context. Outside a request (tests,
benchmark) there is no meter and nothing is recorded.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass
class Meter:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    assistant_calls: int = 0  # translate / solve (they use the AI quota; OCR does not)


_current: ContextVar[Meter | None] = ContextVar("ai_meter", default=None)


@contextmanager
def metering():
    meter = Meter()
    token = _current.set(meter)
    try:
        yield meter
    finally:
        _current.reset(token)


def record(response, assistant: bool):
    """Add the usage of one Gemini response to the open meter, if any."""
    meter = _current.get()
    if meter is None:
        return
    usage = getattr(response, "usage_metadata", None)
    if usage is not None:
        meter.input_tokens += usage.prompt_token_count or 0
        # Thinking tokens are billed as output
        meter.output_tokens += (usage.candidates_token_count or 0) + (getattr(usage, "thoughts_token_count", 0) or 0)
    meter.calls += 1
    if assistant:
        meter.assistant_calls += 1
