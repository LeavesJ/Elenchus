from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .content_loader import load_experience
from .elicitation import DEFAULT_TARGET, run_elicitation_probe
from .types import ProbeResult

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "elicitation"
RUNS_BY_ID = {"irreversible_anchor": 8, "continuity_lock_in": 5}


def run(
    model=None,
    *,
    runs_by_id: dict[str, int] = RUNS_BY_ID,
    data_dir: Path = DATA_DIR,
    target_frame_code: str = DEFAULT_TARGET,
    now: datetime | None = None,
) -> tuple[Path, ProbeResult]:
    if model is None:
        from .model import AnthropicModel  # lazy: tests never need the SDK

        model = AnthropicModel()
    if now is None:
        now = datetime.now(timezone.utc)
    experiences = [load_experience(eid) for eid in runs_by_id]
    result = run_elicitation_probe(
        experiences, model, runs_by_id=runs_by_id, target_frame_code=target_frame_code
    )
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / f"{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(result.model_dump_json(indent=2))
    return path, result


def main() -> None:
    path, result = run()
    print(f"wrote {path}")
    for s in result.summarize():
        print(
            f"\n[{s.experience_id}] usable={s.usable_runs}/{s.total_runs} refused={s.refused_runs}"
        )
        print(
            f"  {result.target_frame_code}: present_reasoned={s.target_present_reasoned} "
            f"present_asserted={s.target_present_asserted} absent={s.target_absent}"
        )
        print(f"  trap trips: {s.trap_trips or '{}'}")


if __name__ == "__main__":
    main()
