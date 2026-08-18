from __future__ import annotations

from pathlib import Path

import yaml

from .types import (
    CheckableQuestion,
    CheckableSet,
    Experience,
    Frame,
    LiftScenario,
    MinedCandidate,
    Mode,
    Regime,
    Rubric,
    Trap,
)

CONTENT_ROOT = Path(__file__).resolve().parents[2] / "content"


def _root(root: Path | None) -> Path:
    return root if root is not None else CONTENT_ROOT


def load_map(posture: str, root: Path | None = None) -> tuple[list[str], list[str]]:
    data = yaml.safe_load((_root(root) / "maps" / f"{posture}.yaml").read_text())
    return list(data["process_frames"]), list(data["declarative_seed"])


def load_rubric(name: str, root: Path | None = None) -> Rubric:
    data = yaml.safe_load((_root(root) / "rubrics" / f"{name}.yaml").read_text())
    return Rubric(
        frames=[Frame(**f) for f in data["frames"]],
        traps=[Trap(**t) for t in data["traps"]],
        mode=data["mode"],
        binding_constraint=data.get("binding_constraint"),
        decision_frame=data.get("decision_frame"),
        display_title=data.get("display_title"),
    )


def load_experience_meta(name: str, root: Path | None = None) -> dict:
    data = yaml.safe_load((_root(root) / "rubrics" / f"{name}.yaml").read_text())
    return {
        "experience_id": data["experience_id"],
        "prompt": data["prompt"],
        "ledger_ref": data["ledger_ref"],
        "regime": data["regime"],
    }


def load_prompt(name: str, root: Path | None = None) -> str:
    """Load a doctrine prompt template (system-prompt text) from content/prompts/."""
    return (_root(root) / "prompts" / f"{name}.md").read_text()


def load_spike_prompt(name: str, root: Path | None = None) -> str:
    """A spike-experiment doctrine prompt from content/spike/ (L-1)."""
    return (_root(root) / "spike" / f"{name}.md").read_text()


def load_mush_frames(root: Path | None = None) -> list[dict]:
    """The Arm-2 control set (deliberately-shallow frames) for the frame-gen spike."""
    return yaml.safe_load((_root(root) / "spike" / "mush_frames.yaml").read_text())["frames"]


def load_steer_fixtures(root: Path | None = None) -> dict:
    """The F1 regression baseline (user-steered chapters spec §4): labeled post-landing turns +
    the recorded false-non-empty threshold. Loaded structurally offline (L-22); exercised by the
    key-gated test_live_steer_f1."""
    return yaml.safe_load((_root(root) / "steer" / "f1_fixtures.yaml").read_text())


def load_min_angle_count(root: Path | None = None) -> int:
    data = yaml.safe_load((_root(root) / "gate" / "depth.yaml").read_text())
    return int(data["min_angle_count"])


def validate_phrase_shape(phrase: str, *, source: str) -> None:
    """Enforce the precondition `generator._contains_phrase`'s boundary depends on: every phrase it
    scans must be non-empty and begin and end with an alphanumeric character. `_contains_phrase`
    rejects `[0-9a-z]` as a boundary char instead of `\\w` (so a leading/trailing `_` can't destroy
    the boundary the way it used to); that only ever matches MORE than the old boundary if the
    phrase itself doesn't start or end on a non-alphanumeric character. A phrase that does (e.g. a
    frame code with a leading `_`, which turns into a leading space in its derived spaced form) can
    make the new boundary stricter than the old one at that end and silently drop a match the old
    one would have caught.

    Two callers, both places a phrase enters the anti-label gate: `load_denylist` below (denylist
    entries authored in content/gate/*.yaml) and `generator.frame_trap_phrases` (frame/trap codes
    authored in content/rubrics/*.yaml, which never pass through a denylist load)."""
    if not phrase or not phrase[0].isalnum() or not phrase[-1].isalnum():
        raise ValueError(
            f"phrase {phrase!r} from {source} must be non-empty and begin and end with an "
            "alphanumeric character (generator._contains_phrase's boundary treats only "
            "alphanumerics as a match boundary)"
        )


def load_denylist(name: str, root: Path | None = None) -> list[str]:
    data = yaml.safe_load((_root(root) / "gate" / f"{name}.yaml").read_text())
    if not isinstance(data, list):
        raise ValueError(f"denylist {name} must be a YAML list")
    entries = [str(x).lower() for x in data]
    for entry in entries:
        validate_phrase_shape(entry, source=f"{name}.yaml")
    return entries


def load_experience(name: str, root: Path | None = None) -> Experience:
    data = yaml.safe_load((_root(root) / "rubrics" / f"{name}.yaml").read_text())
    rubric = Rubric(
        frames=[Frame(**f) for f in data["frames"]],
        traps=[Trap(**t) for t in data["traps"]],
        mode=Mode(data["mode"]),
        binding_constraint=data.get("binding_constraint"),
        decision_frame=data.get("decision_frame"),
        display_title=data.get("display_title"),
    )
    return Experience(
        experience_id=data["experience_id"],
        prompt=data["prompt"],
        rubric=rubric,
        ledger_ref=data["ledger_ref"],
        regime=Regime(data["regime"]),
        role=data.get("role"),
    )


def load_library(root: Path | None = None) -> list[Experience]:
    rubrics = sorted((_root(root) / "rubrics").glob("*.yaml"))
    library = [load_experience(p.stem, root=root) for p in rubrics]
    _reject_duplicate_ledger_refs(library)
    return library


def _reject_duplicate_ledger_refs(library: list[Experience]) -> None:
    """A `ledger_ref` is the identity of an OWNED PROBLEM, so two experiences may not share one.

    This is enforced HERE, at the chokepoint every serving path loads content through, and not in
    `admission.py`. That module has a `valid_ledger_refs` check with **no caller anywhere in `src/`
    or `tests/`** -- a parameter nothing passes -- so it is documentation wearing the costume of
    enforcement. An invariant that cannot fail is not an invariant.

    Failing CLOSED is deliberate and it is the cheaper error. `continuity_lock_in` and
    `license_continuity` shipped sharing `veldra:license_fork_risk`, and nothing broke loudly:
    `display_titles()` silently dropped one title, `problem_menu()` silently made one problem
    unofferable, and `experience._attach_scene` silently served one problem's authored scene while
    the other problem's rubric did the grading. A learner read one situation and was scored against
    another. Refusing to load beats shipping that again, and a content author sees the collision the
    moment they introduce it rather than after it has corrupted durable state.

    If two experiences ever legitimately belong to one owned problem, say so with an explicit field
    rather than by duplicating a string: the accidental encoding is exactly what made this
    undetectable. See `src/elenchus/ledger_ref_migration.py` for the split that this guard exists to
    prevent a repeat of."""
    seen: dict[str, str] = {}
    for e in library:
        prior = seen.get(e.ledger_ref)
        if prior is not None:
            raise ValueError(
                f"duplicate ledger_ref {e.ledger_ref!r}: {prior!r} and {e.experience_id!r}. "
                "A ledger_ref is the identity of one owned problem; two experiences sharing one "
                "collapses them for the problem menu, the display title, the corpus scene and "
                "transfer breadth. Give the second its own ref."
            )
        seen[e.ledger_ref] = e.experience_id


def load_path_type(name: str, root: Path | None = None) -> str:
    data = yaml.safe_load((_root(root) / "maps" / f"{name}.yaml").read_text())
    return str(data.get("path_type", "posture"))


def load_content_map(name: str, root: Path | None = None) -> list[str]:
    data = yaml.safe_load((_root(root) / "maps" / f"{name}.yaml").read_text())
    return list(data["content_core"])


def load_spacing(root: Path | None = None) -> dict:
    data = yaml.safe_load((_root(root) / "cadence" / "spacing.yaml").read_text())
    return {
        "initial_interval_days": int(data["initial_interval_days"]),
        "ease_factor": float(data["ease_factor"]),
        "min_interval_days": int(data["min_interval_days"]),
    }


def load_progression(root: Path | None = None) -> dict:
    data = yaml.safe_load((_root(root) / "cadence" / "progression.yaml").read_text())
    w = data["weights"]
    return {
        "wU": float(w["wU"]),
        "wR": float(w["wR"]),
        "wT": float(w["wT"]),
        "wL": float(w["wL"]),
        "theta_located": float(data["theta_located"]),
        "theta_ledger_refs": int(data["theta_ledger_refs"]),
    }


def load_checkable_experience(name: str, root: Path | None = None) -> Experience:
    data = yaml.safe_load((_root(root) / "checkables" / f"{name}.yaml").read_text())
    questions = [CheckableQuestion(**q) for q in data["checkable"]["questions"]]
    return Experience(
        experience_id=data["experience_id"],
        prompt=data["prompt"],
        ledger_ref=data["ledger_ref"],
        regime=Regime(data["regime"]),
        checkable=CheckableSet(questions=questions),
    )


def load_checkable_library(root: Path | None = None) -> list[Experience]:
    files = sorted((_root(root) / "checkables").glob("*.yaml"))
    return [load_checkable_experience(p.stem, root=root) for p in files]


def load_lift_config(root: Path | None = None) -> dict:
    data = yaml.safe_load((_root(root) / "lift" / "lift.yaml").read_text())
    return {
        "theta_dist": int(data["theta_dist"]),
        "min_scenarios": int(data["min_scenarios"]),
    }


def load_lift_scenarios(name: str = "scenarios", root: Path | None = None) -> list[LiftScenario]:
    data = yaml.safe_load((_root(root) / "lift" / f"{name}.yaml").read_text())
    return [LiftScenario(**s) for s in data["scenarios"]]


def load_lift_candidates(
    name: str = "candidates", root: Path | None = None
) -> list[MinedCandidate]:
    data = yaml.safe_load((_root(root) / "lift" / f"{name}.yaml").read_text())
    return [MinedCandidate(**c) for c in data["candidates"]]


def load_persona_text(name: str, root: Path | None = None) -> str:
    return (_root(root) / "personas" / f"{name}.md").read_text()


def load_role_text(name: str, root: Path | None = None) -> str:
    return (_root(root) / "voice" / f"role_{name}.md").read_text()


def load_territory_text(experience_id: str, root: Path | None = None) -> str:
    """The learner-facing territory description (living sitting §2a): STIMULUS-level by rule —
    the kind of decision, never the response shape. Guarded by three teeth (code checks + egress
    shape in tests/test_forge.py; the behavioral intake-shift probe is @live)."""
    return (_root(root) / "territories" / f"{experience_id}.md").read_text()


def load_theme(subdir: str, name: str, root: Path | None = None) -> dict:
    p = _root(root) / subdir / f"{name}.theme.yaml"
    return yaml.safe_load(p.read_text()) if p.exists() else {}


def persona_for_posture(posture: str | None, root: Path | None = None) -> str:
    """The persona declared on the posture map (L-1); 'vera' is the floor for unknown/missing postures."""
    if not posture:
        return "vera"
    p = _root(root) / "maps" / f"{posture}.yaml"
    if not p.exists():
        return "vera"
    return str(yaml.safe_load(p.read_text()).get("persona", "vera"))


def load_jargon_terms(root: Path | None = None) -> list[tuple[str, list[str]]]:
    """The jargon gate's term list as (term, COMPACTED variants) pairs (spec §4.3).

    Variants are compacted once here rather than on every match. A missing, unreadable, or
    malformed file returns [] — the gate goes INERT rather than rejecting every generation, which
    is the difference between a degraded feature and a silently broken product."""
    from .jargon import compact  # local: keeps the pure matcher free of content-path knowledge

    path = _root(root) / "gate" / "jargon.yaml"
    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError):
        return []
    if not isinstance(data, list):
        return []
    out: list[tuple[str, list[str]]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        term = str(entry.get("term", "")).strip()
        variants = entry.get("variants") or []
        if not term or not isinstance(variants, list):
            continue
        compacted = [c for c in (compact(str(v)) for v in variants) if c]
        if compacted:
            out.append((term, compacted))
    return out
