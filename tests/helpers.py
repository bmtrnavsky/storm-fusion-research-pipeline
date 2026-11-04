"""Fake LLM lane and fake OpenAI-compatible endpoint used by the tests."""

from __future__ import annotations

import json


class LLMResult:
    """Stand-in for the host's llm result object."""

    def __init__(
        self,
        text: str = "",
        parsed=None,
        finish_reason: str = "stop",
        provider: str = "fake",
        model: str = "fake-model",
        total_tokens: int = 10,
    ):
        self.text = text
        self.parsed = parsed
        self.finish_reason = finish_reason
        self.provider = provider
        self.model = model
        self.usage = type("Usage", (), {"total_tokens": total_tokens})()


class FakeLLM:
    """One fake lane with programmable seat and judge behavior."""

    def __init__(
        self,
        seat_text: str = "A grounded finding [S1].",
        seat_finish_reason: str = "stop",
        judge_text: str = "",
        judge_parsed=None,
        judge_finish_reason: str = "stop",
    ):
        self.seat_text = seat_text
        self.seat_finish_reason = seat_finish_reason
        self.judge_text = judge_text
        self.judge_parsed = judge_parsed
        self.judge_finish_reason = judge_finish_reason
        self.calls: list[dict] = []

    def complete(self, messages, **kwargs):
        self.calls.append({"kind": "seat", "messages": messages, **kwargs})
        return LLMResult(
            text=self.seat_text,
            finish_reason=self.seat_finish_reason,
        )

    def complete_structured(self, **kwargs):
        self.calls.append({"kind": "judge", **kwargs})
        return LLMResult(
            text=self.judge_text,
            parsed=self.judge_parsed,
            finish_reason=self.judge_finish_reason,
        )


class FakeCtx:
    def __init__(self, llm: FakeLLM):
        self.llm = llm


class _FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class RecordingOpener:
    """A stand-in urllib opener that records every request body."""

    def __init__(self, payload_factory):
        self.payload_factory = payload_factory
        self.bodies: list[dict] = []

    def open(self, req, timeout=None):
        self.bodies.append(json.loads(req.data.decode()))
        return _FakeResponse(self.payload_factory(self.bodies[-1]))
