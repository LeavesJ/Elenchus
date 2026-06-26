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


def load_min_angle_count(root: Path | None = None) -> int:
    data = yaml.safe_load((_root(root) / "gate" / "depth.yaml").read_text())
    return int(data["min_angle_count"])


def load_denylist(name: str, root: Path | None = None) -> list[str]:
    data = yaml.safe_load((_root(root) / "gate" / f"{name}.yaml").read_text())
    if not isinstance(data, list):
        raise ValueError(f"denylist {name} must be a YAML list")
    return [str(x).lower() for x in data]


def load_experience(name: str, root: Path | None = None) -> Experience:
    data = yaml.safe_load((_root(root) / "rubrics" / f"{name}.yaml").read_text())
    rubric = Rubric(
        frames=[Frame(**f) for f in data["frames"]],
        traps=[Trap(**t) for t in data["traps"]],
        mode=Mode(data["mode"]),
        binding_constraint=data.get("binding_constraint"),
        decision_frame=data.get("decision_frame"),
    )
    return Experience(
        experience_id=data["experience_id"],
        prompt=data["prompt"],
        rubric=rubric,
        ledger_ref=data["ledger_ref"],
        regime=Regime(data["regime"]),
    )


def load_library(root: Path | None = None) -> list[Experience]:
    rubrics = sorted((_root(root) / "rubrics").glob("*.yaml"))
    return [load_experience(p.stem, root=root) for p in rubrics]


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
