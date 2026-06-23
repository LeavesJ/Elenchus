from __future__ import annotations

from pathlib import Path

import yaml

from .types import Frame, Rubric, Trap

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
    )


def load_experience_meta(name: str, root: Path | None = None) -> dict:
    data = yaml.safe_load((_root(root) / "rubrics" / f"{name}.yaml").read_text())
    return {"prompt": data["prompt"], "ledger_ref": data["ledger_ref"], "regime": data["regime"]}


def load_prompt(name: str, root: Path | None = None) -> str:
    """Load a doctrine prompt template (system-prompt text) from content/prompts/."""
    return (_root(root) / "prompts" / f"{name}.md").read_text()
