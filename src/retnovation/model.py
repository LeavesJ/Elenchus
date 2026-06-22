from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel

from .types import Experience, FrameState, TrapState


class IntakeClassification(BaseModel):
    frame_states: dict[str, FrameState]
    trap_states: dict[str, TrapState]


class ResponseClassification(BaseModel):
    outcome: Literal["closed", "unchanged", "regressed"]
    mechanism_supplied: bool
    hard_wrong: bool


@runtime_checkable
class Model(Protocol):
    def classify_intake(self, exp: Experience, opening: str) -> IntakeClassification: ...
    def generate_push(self, exp: Experience, kind: str, code: str) -> str: ...
    def classify_response(
        self, exp: Experience, kind: str, code: str, push: str, response: str
    ) -> ResponseClassification: ...


class FakeModel:
    """Deterministic, scripted model for tests. Pops one response per (code) call."""

    def __init__(
        self, intake: IntakeClassification, responses: dict[str, list[ResponseClassification]]
    ):
        self._intake = intake
        self._responses = responses

    def classify_intake(self, exp: Experience, opening: str) -> IntakeClassification:
        return self._intake

    def generate_push(self, exp: Experience, kind: str, code: str) -> str:
        return f"[push:{kind}:{code}]"

    def classify_response(
        self, exp: Experience, kind: str, code: str, push: str, response: str
    ) -> ResponseClassification:
        return self._responses[code].pop(0)


class AnthropicModel:
    """Real adapter over Claude Opus 4.8. NOT exercised by the dry run.

    Before fleshing out the prompts, consult the claude-api reference for SDK usage.
    The system prompt MUST encode the disband rules: never name the frame, never hand
    the answer, never grade the conclusion; classify only frame/trap deltas + mechanism.
    """

    def __init__(self, api_key: str | None = None, model: str = "claude-opus-4-8"):
        self._model = model
        self._api_key = api_key
        # Lazy import so tests never need the SDK or network.

    def classify_intake(self, exp: Experience, opening: str) -> IntakeClassification:
        raise NotImplementedError("AnthropicModel.classify_intake: wire in step 1 interactive path")

    def generate_push(self, exp: Experience, kind: str, code: str) -> str:
        raise NotImplementedError("AnthropicModel.generate_push: wire in step 1 interactive path")

    def classify_response(self, exp, kind, code, push, response) -> ResponseClassification:
        raise NotImplementedError(
            "AnthropicModel.classify_response: wire in step 1 interactive path"
        )
