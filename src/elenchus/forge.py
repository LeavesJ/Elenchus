"""The forge (living sitting spec §2b): dynamic experiences over curated rubrics.

A forged experience clones one whole curated rubric byte-identically and swaps only the
prompt — a scenario generated around HER situation, authored in opening voice (it IS the
opening say; one generation, one screen). The byte-untouched engine grades it through the
`gen:` registry seam in `generator.select_open_ended`.

Two identities, two grains (spec §1): the forged experience's `ledger_ref` is
`gen:{sitting}` — ONE ref per world, so breadth and `unprompted_breadth` dedupe re-skins
automatically; the registry/store identity is `gen:{sitting}:{n}` — the instance the product
tracks (dedupe, resume, houses).

Gates run cheapest-first, all BEFORE registry insertion (review D12): code checks → the
reject-only fit gate → the union egress screen. One steered regen, then the honest fallback:
the CURATED base serves untouched and `_FALLBACK_BRIDGE` rides the payload (review P1 — a
fallback never poisons the sitting; the world row persists so the next Continue retries).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .content_loader import load_denylist, load_jargon_terms, load_library, load_territory_text
from .jargon import offending_terms
from .generator import GateError, validate_scene
from .model import Model
from .persistence import Store
from .prompt_text import bulleted, labelled
from .types import Experience, LedgerEntry, Rubric, Scene, hidden_move_details

# The bounded coarse difficulty enum (spec §2e): never a prose delta; one step per move.
LEVELS = ("base", "firm", "tight")

# Honest fallback bridge (spec §2b / review P1) — Vera's one line when the curated base serves.
_FALLBACK_BRIDGE = (
    "I'll hold your situation — first, work this one; it's the same pressure you're standing in."
)

# Process-local seam into the engine (spec §2b / review M1): the forge registers the served
# experience under the INSTANCE ref before the selection step; generator.select_open_ended's
# `gen:` branch pops it (late import there — this module imports validate_scene from generator).
forge_registry: dict[str, Experience] = {}

# Structural bounds on the generated scenario (gate 1). The floor catches degenerate/refused
# generations; the ceiling keeps the opening say one readable beat.
_MIN_LEN = 80
_MAX_LEN = 6000

_SECOND_PERSON = re.compile(r"\b(you|your|yours)\b", re.IGNORECASE)
_DECISION_WORDS = ("decide", "decision", "choose", "commit", "call")

# The world-widening doctrine pointer (spec §2b / review P9/D1) — rides every brief; the full
# doctrine lives in content/prompts/forge_scenario.md (L-1).
_WIDEN = (
    "The world may widen: move time forward or shift to an adjacent situation in the same "
    "company and role, carrying the committed positions forward as consequences — the world "
    "carries the situation and its outcomes; it never restates the reasoning as setup."
)


@dataclass
class ForgeResult:
    experience: Experience  # served: forged (world-grain ledger_ref, scene=None) or the base
    instance_ref: str  # "gen:{sitting}:{n}" — registry key + sitting-store identity
    fallback: bool  # True -> the CURATED base served; the bridge line rides the payload
    scenario: str  # the text actually served (== experience.prompt)
    # (attempt, code, detail) per rejected generation. The CALLER persists these: the forge holds
    # the ENGINE store, not the web SittingStore — same seam as the instance row (spec §4.4).
    rejections: tuple[tuple[int, str, str], ...] = ()


# The learner text boundary (task 3): situation, positions, and focus are her own words and
# cross the `prompt_text` seam -- `labelled` for situation/focus (each one blob under a
# heading), `bulleted` for positions (a list, one per converged segment). `story` does NOT cross
# it: it is the PRIOR chapter's forged scenario, authored by the model in an earlier turn of this
# same pipeline, never something she typed (spec §2b's sequel; `web/session_runner.py._story`
# reads it off a persisted `scenario`, not off a turn payload) -- capping or indenting it is a
# different task's job, not this one's.
#
# Each rendered blob is capped at `_BRIEF_BLOB_CAP` characters, measured AFTER bulleted/labelled
# render, never on the raw text handed to them -- the fix `model._cap_rendered_turn` makes to the
# mistake `judgment_loop._POSITION_CAP`'s own comment records: a cap measured before render does
# not bound what comes out, since a newline-heavy input can render to several times its own
# length once every continuation line gets its own indent. The cap is applied per BLOB, not once
# across the whole assembled brief, so the composer's own fixed lines that follow a learner blob
# in `lines` -- Role register, Level, `_WIDEN` -- can never be pushed out by a long one; the same
# reason `model._render_turns` caps each turn before its fixed "Recent exchange:" header is
# prepended, never the joined block after.
#
# 2000 reuses `model._TURN_RENDER_CAP`'s own number and reasoning: her situation and her focus
# are each one typed message, the same shape as a single dialogue turn (a sentence or two in the
# ordinary case; generous headroom for a real one). The positions block gets the same cap rather
# than a smaller one: it is the sum of one committed position per converged segment over a whole
# sitting, strictly larger than a single message, so the shared cap already bounds it at least as
# tightly as a per-position cap would, without a second number to justify separately.
_BRIEF_BLOB_CAP = 2000


def _cap_blob(rendered: str, cap: int = _BRIEF_BLOB_CAP) -> str:
    """Truncate an already-rendered learner blob at `cap` characters, marking the elision.

    Applied AFTER `prompt_text.bulleted`/`labelled`, never before -- see `_BRIEF_BLOB_CAP`."""
    if len(rendered) <= cap:
        return rendered
    return rendered[:cap] + "…[trimmed]"


def build_brief(
    territory: str,
    situation: str,
    positions: list[str],
    role: str | None,
    level: str,
    story: str | None = None,
    focus: str | None = None,
) -> str:
    """Assemble the forge brief — frame-blind and Vera-free (spec §2b / review D3).

    Inputs are EXACTLY: the territory description, her situation, her committed positions
    (her final substantive `you` turns — never landing or any Vera-authored text), the role
    register, and the bounded 3-value level line. Optionally a `story` (prior chapter's world) and
    a `focus` (her own next pressure, user-steered chapters §2e). Never frame/trap details, rubric
    text, or engine state (tests spy on this).

    Her situation, her positions, and her focus are learner text and cross the `prompt_text`
    boundary (see the module comment above); `story` does not. A single-line situation/focus now
    renders as a heading line plus an indented blob rather than the old bare `"Label: text"` --
    `labelled` is not byte-stable the way `bulleted` is, so this is a real prompt-shape change,
    not a no-op. Positions render with the seam's own bullet ("  - ", two spaces) rather than the
    ad hoc "- " this site used before -- also a real change, reported, not slipped in."""
    if level not in LEVELS:
        raise ValueError(f"level must be one of {LEVELS}, got {level!r}")
    lines = [
        f"Territory: {territory.strip()}",
        "",
        _cap_blob(labelled("Her situation:", situation.strip())),
    ]
    if story:
        # Sequel (spec §2b): the prior chapter's world to continue — decision-informed (the new
        # pressure is a consequence of the SPECIFIC call she made, never a generic development).
        lines += [
            "",
            "The story so far (the world to continue — her decision in it is made and standing; "
            "build the new pressure as a consequence of the SPECIFIC call she made, not a "
            "generic development):",
            story.strip(),
        ]
    if focus:
        # User-steered chapter (spec §2e): her own next decision, distilled and frame-blind, to be
        # posed IN this world under the mapped rubric. AFTER the story block (world first, then her
        # direction). Server-side (L-13): the scenario is union-screened on output like story.
        lines += [
            "",
            _cap_blob(
                labelled(
                    "The pressure she wants to press next (her own words — pose THIS decision, "
                    "in this world):",
                    focus.strip(),
                )
            ),
        ]
    if positions:
        lines += [
            "",
            "Her committed positions (her own words):",
            _cap_blob(bulleted(positions)),
        ]
    if role:
        lines += ["", f"Role register: {role}"]
    lines += ["", f"Level: {level}", "", _WIDEN]
    return "\n".join(lines)


def _structural_reason(scenario: str) -> str | None:
    """Gate 1a: is this a servable scenario at all? Reasons speak situation-structure language
    (they become the regen steer)."""
    s = scenario.strip()
    if not s:
        return "the generation is empty — write the scenario"
    if len(s) < _MIN_LEN:
        return "the scenario is too short to stand in — give the situation real stakes"
    if len(s) > _MAX_LEN:
        return "the scenario is too long for one opening — tighten it to the live decision"
    if not _SECOND_PERSON.search(s):
        return "the scenario must put her in the room — write it in the second person"
    last_sentence = re.split(r"(?<=[.!?])\s+", s)[-1].lower()
    if not (s.endswith("?") or any(w in last_sentence for w in _DECISION_WORDS)):
        return "the scenario must end by asking for her decision"
    return None


def _anti_label_reason(scenario: str, rubric: Rubric) -> str | None:
    """Gate 1b: validate_scene's own bar, reused verbatim against the BASE rubric (spec §2b /
    review M4): framework + scaffold denylists, frame/trap codes (snake and spaced), wrapper
    words. anti_label_gate is deliberately NOT used (review D4) — it gates authored library
    entries against corpus anchors, and a generated scenario has no corpus entry by design;
    ownedness is inherited from the honest-fit mapping (her real situation IS the owned
    problem), stated, not machine-checked."""
    try:
        validate_scene(
            Scene(prompt=scenario, situation=""),
            rubric,
            framework_denylist=load_denylist("framework_denylist"),
            scaffold_denylist=load_denylist("scaffold_denylist"),
        )
    except GateError as e:
        return str(e)
    return None


@dataclass(frozen=True)
class _JargonRejection:
    """A jargon-gate rejection, carried as a TYPE rather than a prefixed string (T2 review,
    Fix 1). `reason` in the generation loop also holds model-authored text (`fit.reason`), so a
    prefix-in-a-string control channel let a model that merely began its reason with "jargon:"
    write the accounting columns and truncate its own steer at the first "|" it typed. Model
    output can never be an instance of a private class — `isinstance` is not spoofable the way
    `str.startswith` is."""

    terms: tuple[str, ...]
    prose: str


def _jargon_reason(scenario: str, level: str) -> _JargonRejection | None:
    """Gate 4 (spec 2026-07-29-jargon-gate-design §4.2): listed vocabulary is banned at `base`.

    `LEVELS` is ours and not the model's, so the condition is fully deterministic. The stated
    cost is that this re-couples vocabulary to the PRESSURE ladder, which the spec's own §1
    argues are orthogonal: an experienced founder's first sitting therefore gets a jargon-free
    scenario. That is mildly wrong and harmless, and buying a real second axis is the register's
    job, not this gate's.

    The prose NAMES every offending term (T2 review, Fix 3 — not just the first) because it
    becomes `steer` for the one regen the loop already makes — a regen told only "you used
    jargon" is guessing, and a regen told about only one of two terms still fails the second."""
    if level != "base":
        return None
    terms = offending_terms(scenario, load_jargon_terms())
    if not terms:
        return None
    plural = len(terms) > 1
    names = ", ".join(repr(t) for t in terms)
    prose = (
        f"the scenario uses the term{'s' if plural else ''} {names}, which this reader does not "
        f"know — say the same thing in plain words, without {'them' if plural else 'it'}"
    )
    return _JargonRejection(terms=tuple(terms), prose=prose)


def _reason_code(reason: str | _JargonRejection) -> str:
    """The stable machine-facing code for a rejection (spec §4.4). Prose is for the model; this
    is for counting. `anti_label` and `structural` are the two pre-existing causes that used to
    be indistinguishable from a jargon rejection in aggregate. Keys on `isinstance`, not string
    content (T2 review, Fix 1): model-authored text can never BE a `_JargonRejection`."""
    if isinstance(reason, _JargonRejection):
        return "jargon"
    return "other"


def _reason_detail(reason: str | _JargonRejection) -> str:
    """For a jargon rejection, every offending term joined with ", "; empty otherwise."""
    if isinstance(reason, _JargonRejection):
        return ", ".join(reason.terms)
    return ""


def _fit_requirements(rubric: Rubric) -> str:
    """Server-side precondition text for the reject-only fit gate (spec §2b gate 2). Frame-AWARE
    is allowed HERE — this text never reaches the wire; only the FitCheck.reason (precondition /
    situation-structure language) travels onward, as the regen steer."""
    if rubric.binding_constraint:
        lines = [f"The situation must establish the binding premise: {rubric.binding_constraint}"]
    else:
        lines = [
            "The decision must be genuinely open: live, owned by the person addressed, and "
            "without a single verifiably correct answer baked into the situation."
        ]
    lines += [
        f"The situation must give natural occasion for: {f.frame_detail}" for f in rubric.frames
    ]
    return "\n".join(lines)


def _moves(exp: Experience) -> list[str]:
    """The L-5 hidden-move list — delegates to the single source of truth in types (which the
    content-layer forge may import; the web layer it must not). Name kept for its call sites."""
    return hidden_move_details(exp)


def _union_moves(base: Experience, engaged_frames: list[str]) -> list[str]:
    """Gate 3's move list (spec §2b / review D1): the base's moves ∪ the details of every frame
    she engaged this sitting, resolved from the curated library (gated at load in production) —
    the cross-segment echo is the common case. Order-stable, deduped by detail text."""
    moves = list(_moves(base))
    engaged = set(engaged_frames)
    if not engaged:
        return moves
    for exp in load_library():
        if not exp.rubric:
            continue
        for f in exp.rubric.frames:
            if f.frame_code in engaged and f.frame_detail not in moves:
                moves.append(f.frame_detail)
    return moves


def forge_experience(
    base: Experience,
    sitting_id: str,
    n: int,
    situation: str,
    positions: list[str],
    engaged_frames: list[str],
    level: str,
    model: Model,
    store: Store,
    story: str | None = None,
    focus: str | None = None,
) -> ForgeResult:
    """Forge one generated problem over the curated base (spec §2b).

    Gate order, cheapest first (review D12): (1) code checks — structural + validate_scene's
    anti-label bar against the base rubric; (2) the reject-only fit gate over server-assembled
    precondition text; (3) union egress over the base's moves ∪ her engaged frames. ONE steered
    regen (steer = the failing gate's reason), then the honest fallback: the CURATED base
    serves untouched with `_FALLBACK_BRIDGE` riding the payload (review P1).

    `store` is the ENGINE store (persistence.Store — the ledger owner; the forge runs in the
    worker thread and reuses its connection, review M9): a passing forge seeds the
    `gen:{sitting}` LedgerEntry once per world (add_ledger_entry upserts on id — idempotent;
    a fallback seeds nothing, since the curated base banks under its own curated ref). The
    CALLER persists the instance row (sitting_store.add_generated_problem). The served
    experience is registered under the instance ref for select_open_ended's `gen:` branch."""
    if base.rubric is None:
        raise ValueError("forge_experience requires an open_ended base with a rubric")
    world_ref = f"gen:{sitting_id}"
    instance_ref = f"gen:{sitting_id}:{n}"
    brief = build_brief(
        load_territory_text(base.experience_id),
        situation,
        positions,
        base.role,
        level,
        story,
        focus,
    )
    requirements = _fit_requirements(base.rubric)
    union = _union_moves(base, engaged_frames)

    steer = ""
    rejections: list[tuple[int, str, str]] = []
    for attempt in range(1, 3):  # one generation + ONE steered regen (spec §2b)
        scenario = model.forge_scenario(brief, steer=steer)
        reason: str | _JargonRejection | None = (
            _structural_reason(scenario)
            or _anti_label_reason(scenario, base.rubric)
            or _jargon_reason(scenario, level)
        )
        if reason is None:
            fit = model.fit_check(scenario, requirements)
            if not fit.fits:
                reason = fit.reason or "a required precondition is not established"
        if reason is None:
            performed = model.screen_moves(union, scenario).performed
            if any(1 <= i <= len(union) for i in performed):  # out-of-range dropped (voice parity)
                reason = (
                    "the scenario hands over part of the reasoning — describe the situation "
                    "and its stakes only, never how to work it"
                )
        if reason is None:
            forged = base.model_copy(
                update={"prompt": scenario, "ledger_ref": world_ref, "scene": None}
            )
            store.add_ledger_entry(LedgerEntry(id=world_ref, owned_problem=situation))
            forge_registry[instance_ref] = forged
            return ForgeResult(
                experience=forged,
                instance_ref=instance_ref,
                fallback=False,
                scenario=scenario,
                rejections=tuple(rejections),
            )
        rejections.append((attempt, _reason_code(reason), _reason_detail(reason)))
        steer = reason.prose if isinstance(reason, _JargonRejection) else reason

    # Honest fallback (review P1): the curated base, byte-untouched — its curated ledger_ref
    # keeps banking honest; the bridge line rides the payload; the world row (caller-owned)
    # persists so the NEXT Continue retries the forge. Registered under the instance ref so
    # the seam stays uniform for the worker.
    forge_registry[instance_ref] = base
    return ForgeResult(
        experience=base,
        instance_ref=instance_ref,
        fallback=True,
        scenario=base.prompt,
        rejections=tuple(rejections),
    )
