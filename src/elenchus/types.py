from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator


class Strength(str, Enum):
    weak = "weak"
    forming = "forming"
    strong = "strong"


class Outcome(str, Enum):
    accepted = "accepted"
    redirected = "redirected"


class CoreKind(str, Enum):
    promote = "promote"
    demote = "demote"


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


class EntryClass(str, Enum):
    substantive = "substantive"
    greeting = "greeting"
    meta = "meta"
    confusion = "confusion"
    resistance = "resistance"
    low_signal = "low_signal"


class EntryClassification(BaseModel):
    entry_class: EntryClass
    reply: str


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


class CheckType(str, Enum):
    deterministic = "deterministic"
    model_graded = "model_graded"


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
    decision_frame: str | None = None
    display_title: str | None = None  # human picker label; never the ledger_ref / veldra: slug

    @model_validator(mode="after")
    def _decision_frame_in_frames(self) -> "Rubric":
        if self.decision_frame and self.decision_frame not in {f.frame_code for f in self.frames}:
            raise ValueError(f"decision_frame {self.decision_frame!r} is not a rubric frame")
        return self


class CheckableQuestion(BaseModel):
    question_id: str
    concept: str
    prompt: str
    check_type: CheckType
    choices: list[str] = Field(default_factory=list)
    answer_key: list[str] = Field(default_factory=list)
    criteria: str | None = None


class CheckableSet(BaseModel):
    questions: list[CheckableQuestion]


class ConceptResult(BaseModel):
    concept: str
    question_id: str
    correct: bool
    check_type: CheckType


class CheckableAssessment(BaseModel):
    results: list[ConceptResult]


class CheckableGrade(BaseModel):
    correct: bool


class Aim(BaseModel):
    posture: str
    process_dial: int
    content_core: list[str] | None = None


class Core(BaseModel):
    process_frames: list[str]
    declarative_seed: list[str]
    content_core: list[str] | None = None


class Experience(BaseModel):
    experience_id: str
    prompt: str
    ledger_ref: str
    regime: Regime
    rubric: Rubric | None = None
    checkable: CheckableSet | None = None
    scene: Scene | None = None
    role: str | None = (
        None  # presentation role (ceo|cto|…); resolves the voice register + atmosphere
    )

    @model_validator(mode="after")
    def _regime_payload_invariant(self) -> "Experience":
        if self.regime is Regime.open_ended:
            if self.rubric is None or self.checkable is not None:
                raise ValueError("open_ended experience requires a rubric and no checkable")
        elif self.regime is Regime.cs_technical:
            if self.checkable is None or self.rubric is not None:
                raise ValueError("cs_technical experience requires a checkable and no rubric")
        return self


def hidden_move_details(exp: "Experience") -> list[str]:
    """Every hidden 'move' a learner-facing surface must not perform (L-5: never name the move):
    the rubric's frame details AND trap details — naming a trap hands reasoning just as naming a
    frame does. (The unprompted-read signal is frames-only, so trap coverage hardens the doctrine
    backstop without affecting the signal.) Order is load-bearing: frames then traps, rubric
    order — the live echo-gate's move indices map onto it. Single source of truth; web.voice and
    forge delegate here (they duplicated it byte-for-byte until the 2026-07-03 triage fold —
    silent drift would have screened generated scenarios against a stale move list)."""
    if not exp.rubric:
        return []
    return [f.frame_detail for f in exp.rubric.frames] + [t.trap_detail for t in exp.rubric.traps]


class GateResult(BaseModel):
    passed: bool
    rejects: list[GateCode]
    downgrades: list[GateCode]
    angle_count: int


class Positions(NamedTuple):
    """The learner's own words, handed to the push author (spec 2026-07-30 §4.2).

    Two groups, because visibility without addressability does not deliver the claim:
    `push_stress.md` forbids making the student restate what they already argued ABOUT THIS
    ANGLE, and a flat list spanning several angles leaves the author guessing which position
    that was. NAMED fields rather than a positional pair — a swap at both the call site and the
    composition site cancels out and passes a naive test, and this rides a Protocol across
    three implementations."""

    on_angle: tuple[str, ...] = ()
    elsewhere: tuple[str, ...] = ()


class Push(BaseModel):
    target_code: str
    kind: str
    text: str
    response_classification: str
    response: str = ""
    # The loop's OWN per-push credit decision, and it outranks `response_classification` on the
    # question "did this push repair anything". That string is the grader's raw `outcome`:
    # `assessment/judgment_loop.py` credits a push only on `outcome == "closed" AND
    # mechanism_supplied`, so a `closed` carrying no mechanism -- including one
    # `AnthropicModel.classify_response` FLOORED for a fabricated evidence span -- leaves
    # `response_classification == "closed"` while the loop correctly refuses the repair.
    # `state.update_state` used to re-derive "repaired" from that string alone, a second and
    # weaker copy of the predicate, which let an inflated `closed` on a trap delete the trap's
    # durable gallery row. Defaults False because the fail-safe direction is to log the trap,
    # not to suppress it.
    #
    # TWO THINGS IT IS NOT, both found by a T2 review that ran them:
    #
    # 1. NOT a reason. `gap_closed=False` says credit was withheld, never why. The loop also
    #    withholds it at the `hard_wrong` and `regressed` early breaks, which append their
    #    `Push` before the credit branch is evaluated, so False is equally consistent with "no
    #    mechanism was supplied" and with "a mechanism was supplied, verified against the
    #    evidence anchor, and a bounded-error violation ended the sitting". Anything deriving a
    #    cause from this field alone is wrong; `state.update_state` shipped exactly that bug.
    #
    # 2. NOT the last word on a FRAME. `judgment_loop.assess` returns
    #    `sharper_grader.audit_sharper(...)`, and that blind audit revokes a disputed closure by
    #    stripping the code from `frames_closed_under_pressure` and dropping its `FrameDelta` --
    #    it never rewrites trajectory points, so a revoked frame push rides out still carrying
    #    `gap_closed=True`. On a frame this field is the INSTRUCTOR's pre-audit call; the audited
    #    answer is `frames_closed_under_pressure`, which is what `state.update_state` reads for
    #    frames. Nothing reads `gap_closed` for a frame today (the trap-gallery loop gates on
    #    `p.kind == "trap"`, and `audit_sharper` reads it strictly before it revokes anything),
    #    and a future frame-side reader must take the audited list, not this.
    gap_closed: bool = False


class FrameDelta(BaseModel):
    code: str
    before: FrameState
    after: FrameState


class SharperVerdict(BaseModel):
    sharper: bool
    reason: str
    # T2 CHANGE 2 (evidence anchor): `grade_sharper`'s analog of `ResponseClassification.
    # mechanism_span` (model.py) -- the verbatim span of the reply the grader claims supports
    # `sharper`. `grade_sharper` checks it against `response`; see `AnthropicModel.grade_sharper`'s
    # own comment for the T2 review fix that changed what a failed check does here (it no longer
    # floors `sharper` -- see `span_unverified` below). `audit_sharper`
    # (assessment/sharper_grader.py) reads `sharper` to decide whether an instructor's closure
    # survives the blind audit, so this field must exist here too, not only on
    # `ResponseClassification`, for that check to be possible at this site at all.
    mechanism_span: str = ""
    # T2 REVIEW FIX: set by `AnthropicModel.grade_sharper` when `mechanism_span` fails the
    # (normalized) substring check against `response` while `sharper` is True. Unlike
    # `ResponseClassification.mechanism_supplied`, `sharper` is NEVER floored on a failed span
    # check anymore -- reverting a learner's already-credited closure over a typographic mismatch
    # is a strictly worse failure than missing a fabricated span (see `grade_sharper`'s own
    # comment). `sharper_grader.audit_sharper` copies this straight onto
    # `SharperAuditItem.span_unverified` and never treats a span-only failure as a dispute.
    span_unverified: bool = False


class SharperAuditItem(BaseModel):
    code: str
    kind: str
    instructor_sharper: bool
    grader_sharper: bool
    confirmed: bool
    grader_reason: str
    # T2 REVIEW FIX: mirrors `SharperVerdict.span_unverified` (see its own comment) -- True when
    # `grade_sharper`'s evidence-anchor check could not find `mechanism_span` inside `response`
    # even after normalization, so the auditor's judgment could not be corroborated against a
    # verbatim quote. This is NOT a disagreement: `grader_sharper`/`confirmed` above still carry
    # the auditor's ACTUAL, unfloored verdict, and `audit_sharper` never adds a span-only failure
    # to `disputed` (sharper_grader.py). Surfaced purely for observability, so the span-failure
    # rate can be seen before it is trusted.
    span_unverified: bool = False


class Assessment(BaseModel):
    trajectory: list[Push]
    frame_deltas: list[FrameDelta]
    frames_closed_under_pressure: list[str]
    hard_wrong_flags: list[str]
    stop_reason: StopReason
    sharper_audit: list[SharperAuditItem] = Field(default_factory=list)
    reasoned_unprompted: list[str] = Field(default_factory=list)
    # (attempt, code, detail) per push rejected by the anti-label screen. The CALLER persists
    # these: assess() holds no store -- same seam as ForgeResult.rejections.
    push_rejections: tuple[tuple[int, str, str], ...] = ()


class FrameStrength(BaseModel):
    strength: Strength  # DERIVED on read (storage-keyed clock); kept settable for tests/back-compat
    last_seen: datetime
    due: datetime  # DERIVED on read
    last_evidence: str
    evidence_count: int = 0  # total mechanism-engagements (unprompted OR closed-under-pressure)
    breadth: set[str] = Field(
        default_factory=set
    )  # problems engaged with a mechanism (forming+; transfer uses this)
    unprompted_breadth: set[str] = Field(
        default_factory=set
    )  # subset: problems with an UNPROMPTED present_reasoned (the strong bar)


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


class Scene(BaseModel):
    prompt: str
    situation: str


class CorpusEntry(BaseModel):
    ledger_ref: str
    domain: str
    why_owned: str
    unlabeled: str
    provenance: str
    corpus_pointers: list[str] = Field(default_factory=list)
    scene: Scene | None = None


class NextExperienceSpec(BaseModel):
    # target codes for the next experience: process frames for open_ended, content concepts
    # for cs_technical. Overloaded by name (not renamed) to avoid a persisted-queue migration.
    target_frames: list[str]
    ledger_ref: str
    regime: Regime
    experience_id: str | None = (
        None  # the exact (frame, experience) the policy scored; None for the legacy seed
    )


class SelectionReceipt(BaseModel):
    frame: str
    problem: str
    experience_id: str
    drive: str
    scores: dict[str, float]
    runner_up_drive: str | None
    margin: (
        float  # cross-drive only (vs the best OTHER-drive candidate); NOT the rank-1-vs-rank-2 gap
    )
    content_gaps: list[str]
    created_at: datetime


class CandidateFrame(BaseModel):
    frame_code: str
    frame_detail: str  # carried for SP2/3; the screen never reads it
    injection: str


class LiftScenario(BaseModel):
    scenario_id: str
    prompt: str
    posture: str  # carried for SP2; not read by the screen
    candidate: str | None = None  # SP2: groups a scenario under a MinedCandidate.frame_code


class GeneratedOutput(BaseModel):
    text: str
    refused: bool = False


class PreferenceRating(BaseModel):
    distinguishability: int = Field(ge=0, le=3)  # 0..3
    preferred: Literal["A", "B", "tie"]
    magnitude: int = Field(ge=0, le=2)  # 0..2; 0 iff tie
    key_difference: str

    @model_validator(mode="after")
    def _magnitude_iff_tie(self) -> "PreferenceRating":
        if self.preferred == "tie" and self.magnitude != 0:
            raise ValueError("magnitude must be 0 when preferred is 'tie'")
        if self.preferred != "tie" and self.magnitude == 0:
            raise ValueError("magnitude must be >= 1 when preferred is not 'tie'")
        return self


class InjectionExpressed(BaseModel):
    expressed: bool
    evidence: str


class EgressScreen(BaseModel):
    # performed: 1-based indices of the screened moves the text PERFORMS. evidence: grounding
    # span(s) for each performed move, or what's missing if none — parity with the high-effort lift
    # gate (InjectionExpressed), so the cheaper backstop must justify itself, not flag/clear lazily.
    performed: list[int]
    evidence: str


class TerritoryMap(BaseModel):
    # The front-door mapper's wire shape (living sitting §2a + front-door conversion spec).
    # Server-side output: reflection/conversion are learner-facing ONLY after the caller
    # egress-screens them (gated reflection precedent).
    ranked: list[str]  # experience_ids, best first (returned on "topic" too — best stretch)
    confidence: str  # "high" | "low"
    reflection: str  # one line, HER words where possible
    verdict: Literal["decision", "topic"] = "decision"  # topic = question/curiosity/advice-ask
    conversion: str = ""  # on "topic": engage her subject + ask for the call inside it
    fit: str = ""  # the honest-fit beat's HER-words edge (a noun phrase naming the sharpest
    # pressable decision inside her own situation) — server-side until the caller egress-screens it
    # (gated like conversion/reflection); the generic territory description is the fallback


class ConvergenceCheck(BaseModel):
    # Frame-novelty gate (frame-gen spike, M2 honest 3-way): does a generated frame's MOVE restate a
    # curated frame? ADJUDICATOR-FACING ONLY — `nearest` is a frame_code and `rationale` names the
    # move (the exact L-13 content); NEVER serialize to a learner surface (cf. TerritoryMap.reflection,
    # server-side until egress-screened). The convergent/novel/uncertain VERDICT is DERIVED in
    # frame_gen_spike, never returned by the model. `nearest` on a novel row is a reference ANCHOR,
    # not a partial match — proximity is not convergence.
    nearest: str  # ALWAYS one of the curated frame_codes (validated non-empty)
    restates_nearest: bool  # symmetric directional call (replaces the overloaded maps_to_existing)
    confidence: Literal["high", "low"]  # symmetric — sure of the directional call, either way
    rationale: str  # the directional distinguishing judgment (EgressScreen.evidence precedent)

    @field_validator("nearest")
    @classmethod
    def _nearest_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("nearest must name a curated frame_code (reference anchor)")
        return v


class ConverseTurn(BaseModel):
    # The post-landing wind-down (user-steered chapters §2a). `reply` is authored exactly as the
    # freeform wind-down was. `next_pressure` is EMPTY-BY-DEFAULT (F1) — a distilled fresh decision
    # ONLY when the student unmistakably raises a NEW decision-frame she now faces (not a
    # re-argument of the call just landed), else "". Server-side: the distillation never reaches
    # the client (L-13/F2); the label echoes her raw words.
    reply: str
    next_pressure: str = ""


class FitCheck(BaseModel):
    # The forge's reject-only fit gate (living sitting §2b): does the scenario establish the
    # preconditions the rubric's meaning presumes? The reason speaks precondition /
    # situation-structure language ONLY — the stimulus, never the move.
    fits: bool
    reason: str


class ScenarioVerdict(BaseModel):
    scenario_id: str
    injection_expressed: bool  # the ONLY stored bool that gates aggregation
    distinguishability: int = 0
    preference: int = 0  # signed toward FRAMED after un-randomization; 0 = tie
    key_difference: str = ""
    framed_output: str = ""
    control_output: str = ""
    framed_refused: bool = False
    control_refused: bool = False

    def status(self, theta_dist: int) -> str:
        if not self.injection_expressed:
            return "inconclusive"
        if self.distinguishability < theta_dist:
            return "null"  # not distinguishable (incl. dist 0) — a wash / the model can't see it
        if self.preference > 0:
            return "lift"
        if self.preference < 0:
            return "negative"
        return "neutral"  # distinguishable but a tie


class LiftResult(BaseModel):
    frame_code: str
    scenarios: list[ScenarioVerdict]
    theta_dist: int = 1
    min_scenarios: int = 3

    def _valid(self) -> list[ScenarioVerdict]:
        return [s for s in self.scenarios if s.injection_expressed]

    def _statuses(self) -> list[str]:
        return [s.status(self.theta_dist) for s in self._valid()]

    @property
    def inconclusive_count(self) -> int:
        return sum(1 for s in self.scenarios if not s.injection_expressed)

    @property
    def framed_preferred_count(self) -> int:
        return sum(1 for s in self._valid() if s.preference > 0)  # excludes ties

    @property
    def mean_preference(self) -> float:
        v = self._valid()
        return sum(s.preference for s in v) / len(v) if v else 0.0

    @property
    def mean_distinguishability(self) -> float:
        v = self._valid()
        return sum(s.distinguishability for s in v) / len(v) if v else 0.0

    @property
    def verdict(self) -> str:
        st = self._statuses()
        if not st:
            return "inconclusive"
        if all(s == "lift" for s in st):
            return "lift"
        if any(s == "lift" for s in st):
            return "mixed"
        if any(s == "negative" for s in st):
            return "negative_lift"
        if any(s == "neutral" for s in st):
            return "neutral"
        return "null"

    @property
    def screen_action(self) -> str:
        if self._valid() and self.verdict in ("null", "negative_lift"):
            return "auto_kill"
        return "surface"

    @property
    def below_floor(self) -> bool:
        return len(self._valid()) < self.min_scenarios


class ProbeRun(BaseModel):
    experience_id: str
    run_index: int
    opening: str  # verbatim learner output — gitignored artifact only, never committed
    refused: bool = False
    frame_states: dict[str, FrameState] = Field(default_factory=dict)
    trap_states: dict[str, TrapState] = Field(default_factory=dict)


class ProbeSummary(BaseModel):
    experience_id: str
    total_runs: int
    refused_runs: int
    usable_runs: int  # total_runs - refused_runs; the present-reasoned-rate denominator
    target_present_reasoned: int
    target_present_asserted: int
    target_absent: int
    trap_trips: dict[str, int]  # trap_code -> tripped count across usable runs (first-class)


class ProbeResult(BaseModel):
    target_frame_code: str
    runs: list[ProbeRun]

    def summarize(self) -> list[ProbeSummary]:
        by_exp: dict[str, list[ProbeRun]] = {}
        for r in self.runs:
            by_exp.setdefault(r.experience_id, []).append(r)
        out: list[ProbeSummary] = []
        for eid, runs in by_exp.items():
            usable = [r for r in runs if not r.refused]
            trips: dict[str, int] = {}
            for r in usable:
                for code, st in r.trap_states.items():
                    if st is TrapState.tripped:
                        trips[code] = trips.get(code, 0) + 1
            tgt = self.target_frame_code
            out.append(
                ProbeSummary(
                    experience_id=eid,
                    total_runs=len(runs),
                    refused_runs=len(runs) - len(usable),
                    usable_runs=len(usable),
                    target_present_reasoned=sum(
                        1 for r in usable if r.frame_states.get(tgt) is FrameState.present_reasoned
                    ),
                    target_present_asserted=sum(
                        1 for r in usable if r.frame_states.get(tgt) is FrameState.present_asserted
                    ),
                    target_absent=sum(
                        1 for r in usable if r.frame_states.get(tgt) is FrameState.absent
                    ),
                    trap_trips=trips,
                )
            )
        return out


class RegionRender(str, Enum):
    seed = "seed"
    rendered = "rendered"


class Region(BaseModel):
    region_id: str
    frame_codes: list[str]  # author-side membership — STRIPPED from the learner-facing view (L-13)
    problems: list[str]
    vitality: float | None  # None when render == seed (sub-threshold; nothing to decode)
    accretion: (
        float | None
    )  # breadth-count axis (§4 two-axis; height); None for seeds. Rename-invariant.
    render: RegionRender


def _vitality_bucket(v: float | None) -> int | None:
    """Coarse 3-level wire bucket (None stays None for seeds). The exact mean would leak the strength
    distribution; the >=2-frame blend (not the bucket) is what makes vitality non-invertible (L-13)."""
    if v is None:
        return None
    if v < 0.5:
        return 1
    if v < 0.83:  # ~5/6: separates the 0.8 blend from the 0.867 blend over _VITALITY {0.2,0.6,1.0}
        return 2
    return 3


def _elevation_bucket(a: float | None) -> int | None:
    """Coarse 3-level accretion (height) bucket, gated by the same §4b guard as vitality (None for seeds).
    Derived from region breadth COUNT only, so it is rename-invariant; a bounded depth-location residual
    (Cartographer §4d family) — reveals 'how much ground', never 'which move'."""
    if a is None:
        return None
    if a <= 2:
        return 1
    if a <= 4:
        return 2
    return 3


class TerrainView(BaseModel):
    regions: list[Region]

    def learner_view(self) -> list[dict]:
        # L-13: never expose frame_codes; only an opaque POSITIONAL id + render + a COARSE vitality
        # bucket. region_id is assigned positionally in regions_to_view (never a function of frames).
        return [
            {
                "region_id": r.region_id,
                "render": r.render.value,
                "vitality": _vitality_bucket(r.vitality),
                "elevation": _elevation_bucket(r.accretion),
            }
            for r in self.regions
        ]


class Provenance(BaseModel):
    source_type: Literal["owned", "public"] = "owned"  # public = forward-room, untested this arc
    pointer: str


class MinedCandidate(BaseModel):
    frame_code: str
    frame_detail: str
    injection: str
    posture: str
    hypothesis: str  # why base Opus is wrong by default
    nearest_sibling: str | None = None
    separating_artifact: str = ""
    provenance: Provenance

    def to_candidate_frame(self) -> "CandidateFrame":
        return CandidateFrame(
            frame_code=self.frame_code, frame_detail=self.frame_detail, injection=self.injection
        )


class ScreenSummary(BaseModel):
    verdict: str
    screen_action: str
    mean_distinguishability: float
    mean_preference: float
    framed_preferred_count: int
    data_ref: str = ""

    @field_validator("mean_distinguishability", "mean_preference")
    @classmethod
    def _round_2dp(cls, v: float) -> float:
        # clean 2dp in the committable audit record; the raw LiftResult under data/lift/ keeps full precision
        return round(v, 2)

    @classmethod
    def from_result(cls, result: "LiftResult", data_ref: str = "") -> "ScreenSummary":
        return cls(
            verdict=result.verdict,
            screen_action=result.screen_action,
            mean_distinguishability=result.mean_distinguishability,
            mean_preference=result.mean_preference,
            framed_preferred_count=result.framed_preferred_count,
            data_ref=data_ref,
        )


class Gates(BaseModel):
    surface_independence: Literal["pass", "fail"]
    atomicity: Literal["pass", "fail"]
    orthogonality: Literal["pass", "fail", "subframe"]
    falsifiable_application: Literal["pass", "fail"]
    trainable_cognition: Literal["pass", "fail"]


class AdmittedAs(BaseModel):
    experience_id: str = Field(min_length=1)
    ledger_ref: str = Field(min_length=1)


class AdmissionRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")  # drop the derived marginal_lift on reload

    frame_code: str
    posture: str
    provenance: Provenance
    screen: ScreenSummary
    gates: Gates | None = None  # None for a screen-reject whose human gates were never walked
    nearest_sibling: str | None = None
    separating_artifact: str = ""
    decision: Literal["admit_provisional", "reject", "file_as_subframe"]
    rationale: str = ""
    admitted_as: AdmittedAs | None = None

    @computed_field  # DERIVED VIEW (spec §2, seam 1): not stored truth
    @property
    def marginal_lift(self) -> str:
        return "pass" if self.screen.verdict in ("lift", "mixed") else "fail"

    @model_validator(mode="after")
    def _coherence(self) -> "AdmissionRecord":
        if self.screen.screen_action == "auto_kill" and self.decision != "reject":
            raise ValueError("auto_kill screen requires decision == reject")
        if self.decision == "reject":
            if not self.screen.verdict or not self.rationale:
                raise ValueError("reject requires a screen verdict and a rationale")
        elif self.decision == "admit_provisional":
            if self.marginal_lift != "pass":
                raise ValueError(
                    "admit_provisional requires marginal_lift pass (verdict lift|mixed)"
                )
            if self.gates is None:
                raise ValueError("admit_provisional requires the human gates")
            human = (
                self.gates.surface_independence,
                self.gates.atomicity,
                self.gates.orthogonality,
                self.gates.falsifiable_application,
                self.gates.trainable_cognition,
            )
            if any(g != "pass" for g in human):
                raise ValueError("admit_provisional requires all human gates pass")
            if self.admitted_as is None:
                raise ValueError("admit_provisional requires admitted_as")
            if not self.separating_artifact:
                raise ValueError("admit_provisional requires a separating_artifact")
            if self.nearest_sibling is None:
                raise ValueError("admit_provisional requires nearest_sibling")
        elif self.decision == "file_as_subframe":
            if self.gates is None or self.gates.orthogonality != "subframe":
                raise ValueError("file_as_subframe requires orthogonality == subframe")
            if self.nearest_sibling is None:
                raise ValueError("file_as_subframe requires nearest_sibling")
            if not self.separating_artifact:
                raise ValueError("file_as_subframe requires a separating_artifact")
        return self


class CoreCandidate(BaseModel):
    kind: CoreKind
    target: str
    rationale: str


class CoreVerdict(BaseModel):
    candidate: CoreCandidate
    outcome: str  # "accepted" | "rejected"


@dataclass
class Proposal:
    # ranked best-first; each entry is the (spec, receipt) the policy scored
    candidates: list[tuple[NextExperienceSpec, SelectionReceipt]]

    @property
    def top(self) -> tuple[NextExperienceSpec, SelectionReceipt]:
        return self.candidates[0]

    def problem_menu(self) -> list[tuple[NextExperienceSpec, SelectionReceipt]]:
        # learner-facing projection: best-ranked candidate per owned problem, rank order preserved
        seen: set[str] = set()
        out: list[tuple[NextExperienceSpec, SelectionReceipt]] = []
        for spec, receipt in self.candidates:
            if spec.ledger_ref in seen:
                continue
            seen.add(spec.ledger_ref)
            out.append((spec, receipt))
        return out


@dataclass
class Selection:
    proposed_receipt: SelectionReceipt
    chosen_spec: NextExperienceSpec
    chosen_receipt: SelectionReceipt
    outcome: Outcome


@dataclass
class Work:
    opening: str
    respond: Callable[[str], str]
