# Elenchus

Elenchus runs the case method on the business decision you are actually facing right now.

You describe a decision you are stuck on. It builds a concrete scenario around it, tells you
nothing about what kind of problem it is, and then argues with you. **Rent capability, gate
doctrine** — the model is rented; the gates, the rubrics and the doctrine are ours, versioned on
disk, and never handed to the model as taste.

The friction is the product. It never hands the answer, never names the move you are missing, and
never agrees to soften. What gets scored is how you reasoned, never what you concluded.

## How a sitting goes

1. **You describe a real decision.** Before anything is built, the door names back the decision it
   heard inside your words and waits for your yes. A correction re-maps on your words instead of
   forging a scenario you never agreed to; if your reply is a topic rather than a decision, it asks
   what the call inside it is instead of asserting one.

2. **It forges an unlabeled scenario.** Concrete, specific to your situation, and deliberately
   silent about its own structure. Recognizing what kind of decision this is *is* the skill being
   trained, so labeling the scenario would collapse the exercise into pattern matching. The
   generation gate rejects a scenario that names its own frame, trap, or framework
   (`forge.py`, `_anti_label_reason`), so a case solvable by naming its type never ships.

3. **It cross-examines.** Turn by turn, on the position you actually took. It stops when the holes
   in your reasoning close, which in our own sittings is two to four pushes.

4. **A gap counts as closed only when you supply the mechanism that closes it.** Not when you
   gesture at it, and not when you reach the right answer by another road
   (`assessment/judgment_loop.py` — `closed` requires `mechanism_supplied`). State moves on rigor
   and trajectory. The conclusion is never graded.

5. **A second grader audits the first.** It receives the push and your response and *not* the
   first verdict, and every credit it disputes is revoked from the record
   (`assessment/sharper_grader.py`). A verdict that survives a blind second reader is worth more
   than one that did not.

6. **The judgment is kept.** Every convergence becomes a permanent record: the situation you faced,
   the position you committed in your own words, when, and — once it has aged — what became of it.

## The world

Every judgment you land raises one **house** in a cultivated 3D valley that is your home. You land
on that world first, read where your judgment is deep and where it is thin, and start the next
sitting from it. Each house stands in the domain its judgment belongs to, and a domain brightens as
your judgment there strengthens. Nothing in the world is unearned: an empty valley renders empty,
and a house exists only because you landed a decision there.

Clicking a house opens its **memory** — the situation, your committed position, the date, and the
outcome record if you have added one. It recalls; it never grades, never names the move, and never
replays the conversation. Past judgments feed the next case, which is what makes the practice
first-person rather than generic.

The long-run bet is that judgments landed in different domains become connectable: retention into
innovation, which is what the world's geography exists to make visible.

## Status

**Single-user dogfood, on localhost. Not a beta.** That is deliberate: what is missing is content,
not infrastructure.

Everything a learner types is mapped onto one of **five decision territories**
(`content/territories/`). Five is enough for people whose sittings we watch and not enough for a
stranger; ten to twelve is the gate before any external use. The other two things between here and
a beta are ordinary: multi-user persistence and auth, and a care lane so that someone in real
distress mid-sitting meets care instead of pressure.

The honest gap in the product is that the world is built for many domains and ours has collapsed
into one, because all five territories currently share a domain. The plural geography is real code
with real tests and no second instance yet.

Suite: **1282 passing / 35 skipped**, measured from a fresh clone of this repository, which is what
you will see. Four of those skips need a corpus that is not tracked here. The graded engine core
(`orchestration`, `assessment/`) is held
byte-stable and surface work rides additive seams around it, so changing the rented model is a
config line that never touches what does the grading.

## Architecture

Thin is the architecture, not a stage we are passing through.

- **Rented:** generation, classification, and reasoning, through the Anthropic API
  (`claude-opus-5`, one config site in `model.py`). No fine-tuning, no adapters.
- **Owned:** the loop, the gates, and the context. Maps, rubrics, territories, and doctrine prompts
  are versioned content under `content/`, never hardcoded in `src/` and never left to the model's
  judgment.
- **Two assessment regimes** behind one interface: open-ended judgment (graded on rigor and
  trajectory, never correctness) and checkable technical (scored against explicit criteria).
- FastAPI, SQLite, and a vendored Three.js renderer. No orchestration framework, no vector
  database.

## Layout

- `src/elenchus/` — the engine: `orchestration`, `assessment/` (open-ended judgment loop +
  checkable scorer + sharper grader), `state`, `scheduler`, `persistence`, `types`, plus the
  generative seam (`model`, `forge`, `generator`) and the reward terrain (`terrain`).
- `src/elenchus/web/` — the surface: FastAPI app, the session runner (bounded engine sessions
  inside one continuous sitting), the voice/concierge authoring layer, the durable sitting store,
  and the WebGL valley renderer.
- `content/` — maps, rubrics, territories, and doctrine prompts: doctrine as data.
- `docs/` — lessons, DEVLOG, specs, plans (internal; not tracked).
- `data/` — runtime SQLite (gitignored; ledger + learner state).

## Develop

Python 3.14. This project runs on `PYTHONPATH=src`, not on the editable install (setuptools
editable mode is unreliable on 3.14 — see `docs/lessons.md` L-19):

    python3 -m venv .venv
    .venv/bin/pip install -e ".[dev,web]"    # deps only; do not rely on `import elenchus`

    # tests (fully offline against a scripted fake model)
    PYTHONPATH=src .venv/bin/pytest -q

    # the web app  (needs ANTHROPIC_API_KEY in .env for live model calls)
    set -a && . ./.env && set +a
    PYTHONPATH=src .venv/bin/python -m elenchus.web   # → http://127.0.0.1:8000

Only the web app and the `@live` suite (`pytest -m live`) call the real model; `-m live` spends
real tokens.
