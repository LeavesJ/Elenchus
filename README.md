# Retnovation

A retention-and-deployment engine. Not a tutor: it owns every encounter *after* you first meet the
material and makes the knowledge stay, and stay usable. **Rent capability, gate doctrine.**

The friction is the product. It never hands the answer, names the move, or grades the
conclusion — it presses you to take a real position and reason it out, and it only
registers progress on the rigor of that reasoning, never on whether you were "right."

Single-user dogfood across two assessment regimes through one pluggable interface:
open-ended judgment (graded on trajectory, not correctness) and checkable technical
(scored against explicit criteria).

## Status

**Dogfood MVP — not beta.** The full six-link engine (`aim → core → experience →
assessment → state → cadence`) is standing and green, wrapped by a conversational
**engaged-agent** web surface whose 3D world you now **land on** as your home — and whose
houses are now an accessible record of your own judgments (see below). Curated content
covers five open-ended decision territories; the content-expansion pass (more territories,
more role registers) is the gate before any external use. Suite: **579 passing / 30
skipped**; the graded engine core (`orchestration`, `assessment/`) is held byte-stable —
the surface work rides additive seams around it. The world's visual form is mid-redesign;
its *meaning* (below) is settled. See `docs/DEVLOG.md` and `docs/superpowers/` for the
narrative.

## The engaged agent

`python -m retnovation.web` serves a chat surface where you describe a real situation you
face; the engine forges a specific, unlabeled decision scenario around it, presses you on
it turn by turn, and lands when your reasoning converges. Staying in a sitting spins the
next *chapter* of the same story. The problem is never labeled and the doctrine is never
spoken — recognizing "what kind of decision this is" is the work, not a hint the product
gives away.

**Every convergence — every judgment you actually land — raises one house** in a cultivated
3D valley that is your **home**: you land on that world first, reading where your judgment
is deep and where it is thin, and start the next sitting from it. Each house stands in the
domain its judgment belongs to, and a domain brightens as your judgment there strengthens.
Nothing in the world is unearned: an empty valley renders empty, and a house exists only
because you landed a decision there.

Clicking a house opens its **memory** — the situation you faced, the position you committed
*in your own words*, and when. It recalls; it never grades, never names the move, and never
replays the conversation. The long-run bet is that judgments landed in different domains
become connectable — retention into innovation — which is what the world's geography is
built to make visible.

## Layout

- `src/retnovation/` — the engine: `orchestration`, `assessment/` (open-ended judgment loop
  + checkable scorer), `state`, `scheduler`, `persistence`, `types`, plus the generative
  seam (`model`, `forge`, `generator`) and the reward terrain (`terrain`).
- `src/retnovation/web/` — the engaged-agent surface: FastAPI app, the session runner
  (bounded engine sessions inside one continuous sitting), the voice/concierge authoring
  layer, durable sitting store, and a vendored WebGL valley renderer.
- `content/` — curated maps, curator rubrics, territories, and doctrine prompts: versioned
  doctrine-as-data, never hardcoded in `src/`. The model rents capability; the gates hold
  doctrine.
- `docs/` — lessons, DEVLOG, specs, plans (internal; not tracked).
- `data/` — runtime SQLite (gitignored; ledger + learner state).

## Develop

Python 3.14. This project runs on `PYTHONPATH=src`, not on the editable install (the
setuptools editable mode is unreliable on 3.14 — see `docs/lessons.md` L-19):

    python3 -m venv .venv
    .venv/bin/pip install -e ".[dev]"        # deps only; do not rely on `import retnovation`

    # tests (fully offline against a scripted fake model)
    PYTHONPATH=src .venv/bin/pytest -q

    # the web app  (needs ANTHROPIC_API_KEY in .env for live model calls)
    set -a && . ./.env && set +a
    PYTHONPATH=src .venv/bin/python -m retnovation.web   # → http://127.0.0.1:8000

Only the web app and the `@live` suite (`pytest -m live`) call the real model.
