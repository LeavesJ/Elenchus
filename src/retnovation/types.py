from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Strength(str, Enum):
    weak = "weak"
    forming = "forming"
    strong = "strong"


class Regime(str, Enum):
    open_ended = "open_ended"
    cs_technical = "cs_technical"


class Mode(str, Enum):
    genuinely_open = "genuinely_open"
    bounded_error = "bounded_error"


class FrameState(str, Enum):
    absent = "absent"
    present_asserted = "present_asserted"
    present_reasoned = "present_reasoned"


class TrapState(str, Enum):
    not_tripped = "not_tripped"
    tripped = "tripped"
    repaired = "repaired"


class StopReason(str, Enum):
    converged = "converged"
    bounded_error_violation = "bounded_error_violation"
    plateau = "plateau"
    regression = "regression"
    budget = "budget"


class GateCode(str, Enum):
    recoverable_label = "recoverable_label"
    pre_named_framework = "pre_named_framework"
    type_hint_scaffold = "type_hint_scaffold"
    softened_ambiguity = "softened_ambiguity"
    cosmetic_engagement = "cosmetic_engagement"
    owned_or_real = "owned_or_real"
    process_layer_load = "process_layer_load"
    insufficient_interrogation_depth = "insufficient_interrogation_depth"


class Frame(BaseModel):
    frame_code: str
    frame_detail: str
    paired_trap: str | None = None


class Trap(BaseModel):
    trap_code: str
    trap_detail: str


class Rubric(BaseModel):
    frames: list[Frame]
    traps: list[Trap]
    mode: Mode
    binding_constraint: str | None = None


class Aim(BaseModel):
    posture: str
    process_dial: int
    content_core: None = None


class Core(BaseModel):
    process_frames: list[str]
    declarative_seed: list[str]
    content_core: None = None


class Experience(BaseModel):
    experience_id: str
    prompt: str
    rubric: Rubric
    ledger_ref: str
    regime: Regime


class GateResult(BaseModel):
    passed: bool
    rejects: list[GateCode]
    downgrades: list[GateCode]
    angle_count: int


class Push(BaseModel):
    target_code: str
    kind: str
    text: str
    response_classification: str


class FrameDelta(BaseModel):
    code: str
    before: FrameState
    after: FrameState


class Assessment(BaseModel):
    trajectory: list[Push]
    frame_deltas: list[FrameDelta]
    frames_closed_under_pressure: list[str]
    hard_wrong_flags: list[str]
    stop_reason: StopReason


class FrameStrength(BaseModel):
    strength: Strength
    last_seen: datetime
    due: datetime
    last_evidence: str


class TrapOccurrence(BaseModel):
    experience_id: str
    occurred_at: datetime
    detail: str


class SpacedItem(BaseModel):
    concept: str
    due: datetime
    interval_days: int


class LearnerState(BaseModel):
    frames: dict[str, FrameStrength] = Field(default_factory=dict)
    trap_gallery: dict[str, list[TrapOccurrence]] = Field(default_factory=dict)
    declarative_seed: dict[str, SpacedItem] = Field(default_factory=dict)


class LedgerEntry(BaseModel):
    id: str
    owned_problem: str
    links_to_experiences: list[str] = Field(default_factory=list)


class CorpusEntry(BaseModel):
    ledger_ref: str
    domain: str
    why_owned: str
    unlabeled: str
    provenance: str
    corpus_pointers: list[str] = Field(default_factory=list)


class NextExperienceSpec(BaseModel):
    target_frames: list[str]
    ledger_ref: str
    regime: Regime


@dataclass
class Work:
    opening: str
    respond: Callable[[str], str]
