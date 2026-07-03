# The Living Sitting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Read the spec first:** `docs/superpowers/specs/2026-07-02-living-sitting-design.md` (v2, review-folded) — every task cites its sections.

**Goal:** The user says what she's facing; the system forges a scenario around her situation over
a curated rubric; the byte-untouched engine grades it; Continue applies the next pressure to the
same world; End tells the sitting's story over one house per convergence.

**Architecture:** A forge (new module) clones a curated rubric, swaps the prompt (generated in
opening voice), and enters the engine through a `gen:` registry branch in
`generator.select_open_ended`. Two identities: `gen:{sitting}` (world grain — what the engine
grades/banks) and `gen:{sitting}:{n}` (instance grain — sitting store, dedupe, resume, houses).
The front door lives INSIDE the worker's `decide()` loop (queue handshake preserved).

**Tech Stack:** Python 3.14 (`PYTHONPATH=src .venv/bin/...`), FastAPI/TestClient, sqlite3, pytest, ruff.

## Global Constraints

- **Engine byte-untouched:** `orchestration.py`, `assessment/` — empty diff. `generator.py` and
  `experience.py` are DECLARED seams (spec §2b); `model.py` additions follow the L-17 budget rule.
- **Two grains everywhere (spec §1):** engine/ledger/breadth = `gen:{sitting}`; sitting store /
  selection_log / dedupe / houses = `gen:{sitting}:{n}` + `experience_id` (territory).
- **All forge gates run BEFORE registry insertion; order: code checks → fit gate → union egress;
  one steered regen → honest fallback with the Vera bridge line (spec §2b).**
- **The brief is frame-blind and Vera-free:** territory description + her situation + her final
  substantive `you` turns + role register + 3-value level enum. Never frame/trap details, rubric
  text, landing text, or engine state (spec §2b/§2e).
- **L-13:** `gen:` refs never reach the client; territory descriptions are stimulus-level with
  three teeth (spec §2a); houses positional, no codes/refs.
- Per commit: `.venv/bin/ruff format . && .venv/bin/ruff check .`, `PYTHONPATH=src
  .venv/bin/pytest -q` green with REAL exit codes (L-23); explicit paths; confidential-docs guard.
  Baseline: **372 passed / 25 skipped**. Repo `~/Documents/Retnovation`, branch `main`, hold push.

---

### Task L1: Model layer — four new methods + wire models + FakeModel

**Files:**
- Modify: `src/retnovation/model.py` (Model protocol, AnthropicModel, FakeModel)
- Modify: `src/retnovation/types.py` (wire models)
- Test: `tests/test_forge.py` (NEW — starts here with the wire/fake layer)

**Interfaces (Produces — every later task consumes these EXACTLY):**
```python
class TerritoryMap(BaseModel):          # types.py
    ranked: list[str]                   # experience_ids, best first
    confidence: str                     # "high" | "low"
    reflection: str                     # one line, HER words where possible

class FitCheck(BaseModel):              # types.py
    fits: bool
    reason: str                         # precondition/situation-structure language ONLY

# Model protocol + AnthropicModel + FakeModel:
def map_territories(self, situation: str, territories: list[tuple[str, str]]) -> TerritoryMap: ...
    # territories = [(experience_id, territory_description)]; ONE batched parse call,
    # _MED_PARAMS, _CLASSIFY_MAX_TOKENS, _require fails LOUD on truncation (L-17).
def forge_scenario(self, brief: str, steer: str = "") -> str: ...
    # returns the scenario IN OPENING VOICE (it IS the opening say — spec §2b/M6);
    # authored prompt content/prompts/forge_scenario.md; _PARAMS; 4096; steer = regen reason.
def fit_check(self, scenario: str, requirements: str) -> FitCheck: ...
    # reject-only server-side gate; requirements = precondition text assembled by the forge
    # (frame-aware, server-side); _MED_PARAMS, _CLASSIFY_MAX_TOKENS.
def concierge_sitting_close(self, situation: str, segments: list[list[tuple[str, str]]],
                            voice: str = "") -> str: ...
    # whole-sitting close; content/prompts/concierge_sitting_close.md; _PARAMS; 4096.
```
FakeModel: constant-return counterparts (`TerritoryMap(ranked=[...all ids...],
confidence="high", reflection="[reflect]")`, `"[forged scenario]"`, `FitCheck(fits=True,
reason="")`, `"[sitting close]"`) — the scripted-pop pattern stays untouched (review M12);
leak/reject test fakes subclass-override per the `_ConciergeFidelityModel` convention.

- [ ] **Step 1: failing tests** (`tests/test_forge.py`): FakeModel returns the four constants;
  wire models validate (`TerritoryMap(ranked=["a"], confidence="high", reflection="r")`);
  AnthropicModel methods exist on the protocol (attribute check — live behavior is @live-only).
- [ ] **Step 2: verify fail** (AttributeError).
- [ ] **Step 3: implement.** AnthropicModel methods follow `screen_moves`' shape exactly
  (numbered list assembly, `messages.parse`, `_require`). New authored prompt files are loaded
  via `load_prompt` (existing helper). `forge_scenario` user message = the brief verbatim +
  optional `Steer (fix exactly this): {steer}`.
- [ ] **Step 4: gate** (full suite; expect ~+4).
- [ ] **Step 5: commit** — `feat(model): map_territories, forge_scenario, fit_check, concierge_sitting_close (L-17 budgets, batched parse, loud truncation)`.

---

### Task L2: Content — territories, prompts, DF matrix, elicitation variants

**Files:**
- Create: `content/territories/{license_continuity,decision_under_stakes,irreversible_anchor,continuity_lock_in,proof_before_promise}.md`
- Create: `content/prompts/forge_scenario.md`, `content/prompts/concierge_sitting_close.md`
- Modify: `content/rubrics/{decision_under_stakes,irreversible_anchor,continuity_lock_in,proof_before_promise}.yaml` (add `decision_frame`)
- Create: `content/elicitation/` DF-free rubric variants (copies used ONLY by the elicitation harness)
- Modify: `src/retnovation/content_loader.py` (`load_territory_text(experience_id)`, mirror of `load_role_text`)
- Modify: `src/retnovation/elicitation.py` call sites / `run_elicitation.py` + `tests/test_elicitation*.py` (point at the DF-free variants)
- Test: `tests/test_forge.py` (+ existing suites)

**The DF matrix (spec §2d, pinned):** `license_continuity: commit_under_the_deadline` (already
present — no edit); `continuity_lock_in: embed_credentials_as_a_list` (FORCED — 1-frame rubric);
`irreversible_anchor: choose_the_failure_default_deliberately` (MUST NOT be embed — keeps the
spine frame's unprompted channel); `decision_under_stakes: choose_the_failure_default_deliberately`;
`proof_before_promise: protect_the_core_lane`. Rule check: no frame is DF everywhere it appears.

**Break-set analysis (spec §2d, review D7 — verify at the gate):** `probed` accumulates on EVERY
push of a code, so DF changes sequences ONLY for intakes where the DF frame is already
`present_reasoned` (it gets a stress press instead of silence). The shared `make_fake` intake has
`choose_the_failure_default_deliberately: absent` → normal push → probed → NO sequence change for
the web/session suites (loops drive to done regardless). `test_guard_passes_the_two_real_rubrics`
+ the key-gated acceptance test move to the DF-free variants IN THIS COMMIT (L-22). If the gate
shows other reds, fix in this commit (L-10) — do not defer.

**Territory descriptions — stimulus-level rule + code teeth:** each file is 2–3 sentences
describing the KIND of decision (what curated prompts already disclose), never the response
shape. Example (`irreversible_anchor.md`): *"Decisions you ship once and cannot reach again —
where whatever you fix now is fixed for every copy in the field, and the day it must change has
no lever."* Write `continuity_lock_in.md` LAST and hardest-reviewed (1-frame territory).

- [ ] **Step 1: failing tests:** `load_territory_text` returns non-empty for all five;
  a code-teeth test per description against its OWN rubric (no frame/trap codes, no
  `frame_detail` phrases verbatim >4 words, no scaffold/wrapper words — reuse `validate_scene`'s
  denylists); `screen_moves(moves(exp), description)` empty under FakeModel (structure) — the
  real teeth are @live; every rubric in the matrix has the pinned `decision_frame` and the rule
  holds (a test computing the matrix from content).
- [ ] **Step 2: verify fail.** **Step 3: write content + loader + rubric edits + harness
  repointing.** **Step 4: gate — FULL suite with real exit codes; expect the elicitation tests
  green on variants and zero unexplained reds.** **Step 5: commit** —
  `content: territories + forge/close prompts + decision_frame matrix (arc floor; DF-free elicitation variants keep the harness alive)`.

---

### Task L3: The forge + registry seam + store rows

**Files:**
- Create: `src/retnovation/forge.py`
- Modify: `src/retnovation/generator.py` (the `gen:` branch in `select_open_ended`)
- Modify: `src/retnovation/web/sitting_store.py` (`web_world`, `web_generated_problem`, `web_converged.experience_id`)
- Test: `tests/test_forge.py`, `tests/test_sitting_store.py`

**Interfaces (Produces):**
```python
# forge.py
LEVELS = ("base", "firm", "tight")
@dataclass
class ForgeResult:
    experience: Experience      # ledger_ref="gen:{sitting}" (WORLD grain), scene=None,
                                # rubric byte-equal to base, prompt = scenario-in-opening-voice
    instance_ref: str           # "gen:{sitting}:{n}" (registry key + store identity)
    fallback: bool              # True -> curated base served; bridge line rides the payload
    scenario: str

def forge_experience(base: Experience, sitting_id: str, n: int, situation: str,
                     positions: list[str], engaged_frames: list[str], level: str,
                     model, store) -> ForgeResult: ...
    # gates in order (spec §2b): code checks (structural + validate_scene-shape) ->
    # fit_check(scenario, requirements) -> screen_moves(union moves) ; one steered regen ->
    # fallback=True with the CURATED base experience (prompt untouched).
    # seeding: add_ledger_entry(gen:{sitting}) once per world (idempotent), and the caller
    #   persists the instance row (store.add_generated_problem).
_FALLBACK_BRIDGE = ("I'll hold your situation — first, work this one; "
                    "it's the same pressure you're standing in.")

# generator.py select_open_ended, FIRST branch:
#   if spec.ledger_ref and spec.ledger_ref.startswith("gen:"):
#       return forge_registry.pop(spec.ledger_ref)
# forge.py owns: forge_registry: dict[str, Experience]  (process-local; populated pre-selection)

# sitting_store.py additions:
def write_world(self, sitting_id: str, situation: str, now) -> None
def read_world(self, sitting_id: str) -> str | None
def add_generated_problem(self, ref, sitting_id, experience_id, scenario, now) -> None
def read_generated_problem(self, ref) -> dict | None      # {"experience_id","scenario"}
def log_converged(self, sitting_id, ref, now, experience_id: str = "") -> None   # NEW column
def territories_within(self, now, hours: int = 24) -> set[str]                    # experience_ids
```
Union moves: `voice._moves(base)` + the engaged frames' details resolved from the gated library
(frame-aware, server-side — the forge may see details; the BRIEF may not). The brief assembly
lives in `forge.py:build_brief(...) -> str` — territory description + situation + positions
(her `you` turns) + role + `Level: {level}` line + the world-widening doctrine pointer; NO other
inputs (test spies on this).

- [ ] **Step 1: failing tests:** happy path (FakeModel → ForgeResult with world-grain ref, scene
  None, rubric byte-equal via `model_dump` compare minus prompt/ledger_ref/scene); leak fake
  (screen flags once → regen with steer → clean → served; flags twice → `fallback=True`, prompt
  == curated); fit-reject fake (same shape); brief purity (build_brief output contains situation
  + positions, NOT `frame_detail` strings, NOT any "Vera"/landing text, level line exact);
  registry pop via `select_open_ended(NextExperienceSpec(ledger_ref="gen:x:1", ...))`; ledger
  seeded once per world (two forges, one ledger row); store row round-trips; `territories_within`
  windows by experience_id across sittings; `:memory:` inert paths return empties.
- [ ] **Step 2: verify fail.** **Step 3: implement.** **Step 4: gate.** **Step 5: commit** —
  `feat(forge): dynamic experiences over curated rubrics — gates, regen, honest fallback, registry seam, two-grain identity`.

---

### Task L4: Worker front door + same-world Continue + rebuild fidelity

**Files:**
- Modify: `src/retnovation/web/session_runner.py` (decide() front-door loop; continue targeting;
  window by experience_id; `_serialize_record`/`_rebuild`; new resume state; difficulty enum;
  return-visit line; reopen by experience_id)
- Modify: `src/retnovation/web/voice.py` (`sitting_close`, reflection screen helper)
- Modify: `src/retnovation/web/app.py` (`frontdoor` kind; bridge/subtitle passthroughs)
- Test: `tests/test_session_runner.py`, `tests/test_web_api.py`

**Design decisions bound here (spec §2c/§2e/§2f/§2g):**
- `decide(proposal)` front-door loop: emit `("say", {"text": _FRONTDOOR_ASK, "frontdoor": True,
  "menu": <small doors + nonce>, "theme": ...})`; collect text; "menu index" input → today's
  path (doors under composer); free text → `map_territories` → confidence branch (low → emit the
  honest-fit line, collect again; accept/decline) → emit the SCREENED heard-you bridge as a say →
  forge (level from store history) → register → return Selection with
  `chosen_spec.ledger_ref = instance_ref`. Selection `outcome=accepted` (she authored the ask).
- Continue: next territory = rank-based combination (mapper ranked ∩ not-in-`territories_within`,
  tie-broken by the policy's proposal order); `next_title` becomes the TERRITORY DESCRIPTION
  snippet (subtitled button, review P4); all-windowed → informed re-serve payload (the P3 copy),
  never a false fresh-situation door.
- `_serialize_record` adds `"ledger_ref": rec["exp"].ledger_ref`; `_rebuild` on `gen:` ref:
  `store.read_generated_problem` → `base.model_copy(update={"prompt": scenario, "ledger_ref":
  ref, "scene": None})`; missing row → `exp=None` statics (review M2).
- New resume state `mid-front-door`: live sitting + world row present + no inflight + no record
  + no pending menu → re-serve the static ask over her visible turns (cross-restart) or resume
  the live loop (same process — queues intact).
- Difficulty: `_level(sid) -> str` from the store's recent records (press counts/stop reasons);
  one step per move; snap-back on non-converged; new world opens "base" (review P8).
- Return visit: cold start with closed worlds → muted line "Your world so far: N houses, M
  regions alight." from the converged log (review P10).
- Sitting close: `voice.sitting_close(model, situation, segments, posture)` — kind-filtered
  turns per segment; union egress over the sitting's territories' moves; static fallback;
  measured (test asserts ONE screen call; live measures scale — review M13).
- Reopen/lost comparisons by `experience_id` (review M8); seam rules: seam attaches to the
  forged opening; front-door re-entry clears it.

- [ ] **Step 1: failing tests (the battery):** front-door flow end-to-end with FakeModel (ask →
  free text → bridge say → forged opening say; transcript persists ask/text/bridge); doors-path
  unchanged (menu click from the frontdoor payload); low-confidence branch; restart mid-front-door
  resumes honestly; restart after a forged convergence — converse/close author over the GENERATED
  prompt (spy on `concierge_converse` problem arg — review M2's test); territory window blocks a
  just-converged territory on Continue and the button subtitle is the next territory's
  description; all-windowed → informed re-serve copy; fallback forge → bridge line rides the
  payload and the NEXT continue retries the forge (no poisoning); level enum bounds (converged
  fast → +1 step; plateau → snap back; new world → base); reopen seam via experience_id after
  restart; return-visit line; sitting close receives all segments (spy) + falls back static on
  screen failure; L-13: no `gen:` refs in ANY payload or persisted turn (extend the no-leak
  helpers).
- [ ] **Step 2: verify fail.** **Step 3: implement.** **Step 4: gate.** **Step 5: commit** —
  `feat(web): the living sitting — front door in the worker, same-world continue, rebuild fidelity, bounded difficulty, sitting close`.

---

### Task L5: Terrain — houses are converged segments

**Files:**
- Modify: `src/retnovation/terrain.py` + `src/retnovation/types.py` (learner_view houses)
- Modify: `src/retnovation/web/session_runner.py` (compose houses from `web_converged` at close)
- Modify: `src/retnovation/web/static/terrain3d.js` (house clusters, layout rule, many-cue)
- Modify: `src/retnovation/web/static/index.html` (close copy counts houses)
- Test: `tests/test_terrain.py`, `tests/test_web_api.py`

Houses = `web_converged` rows (converged-only by construction), ordered by `converged_at`
(public time signal, append-stable), each bucketed by its territory's region (experience_id →
frames → region index computed server-side), positioned ordinally within the region cluster;
cap at 9 per region with a many-cue ("+N more" glow). Wire: `{"region": <ordinal>, "bucket":
<region bucket>}` per house — no refs, no codes, no timestamps (order carries time). The
learner_view Region payload keeps today's shape; houses ride beside it in the close/terrain
payload assembled at the WEB layer (terrain.py provides region membership; the store provides
the rows).

- [ ] **Step 1: failing tests:** the founder regression — two convergences (different
  territories) → TWO houses and the close copy says "2 houses" (geometry AND copy, review P12);
  same-territory re-serve convergence → house count grows; plateau → no house; house ordering
  stable across a restart; no `gen:`/codes in the payload; rename-invariant guard still green.
- [ ] **Step 2–5:** fail → implement → gate → commit —
  `feat(terrain): houses are converged segments — per-convergence reward, ordered by arrival, region-clustered`.

---

### Task L6: Shell

**Files:**
- Modify: `src/retnovation/web/static/index.html`
- Test: `tests/test_web_api.py` (served-shell asserts)

`kind:"frontdoor"`: render the ask as a Vera bubble, the doors SMALL beneath the composer
(existing `renderMenu` restyled compact + the composer emphasized/focused), composer active;
`say` payloads with `bridge`/`seam`/`subtitle` fields render as muted lines; the Continue button
renders `Continue — next pressure: {subtitle}`; the informed re-serve payload renders its copy +
both choices; the return-visit muted line renders before the ask.

- [ ] **Step 1: failing served-shell tests** (`kind==='frontdoor'` handling; compact doors
  block; subtitle in renderContinue; return-line hook). **Step 2–5:** fail → implement → gate →
  commit — `feat(web): front-door shell — composer-first with doors beneath, subtitled continue, return-visit line`.

---

### Task L7: Smoke, docs, batch review

- [ ] FakeModel real-browser smoke (the preview harness pattern from durable sittings): front
  door → free text → bridge → forged opening → converge → Continue (subtitled) → converge →
  End → sitting story + two houses. Count model calls per beat and record them in the DEVLOG
  (L-20; spec §2g claims 3/2).
- [ ] DEVLOG entry; SESSION_HANDOFF rewrite; memory update; lessons if any new pattern earned one.
- [ ] Batch 3-lens adversarial review (multi-agent, per-finding verification, worktree/commit
  isolation per L-21) over L1..L6; fold findings; re-gate.
- [ ] Founder gates: @live free-text sitting (generator quality, latency, intake-shift probe on
  territory descriptions) + felt dogfood + push.

## Self-Review (planner)

**Spec coverage:** §2a → L2 (territories+teeth) + L4 (mapper flow, heard-you, honest fit) + L6
(doors under composer); §2b → L1 (model methods) + L3 (forge, gates, seam, seeding) + L4 (level,
brief inputs from store); §2c → L4 (targeting, window, subtitle, informed re-serve, reopen);
§2d → L2 (matrix + variants + break set); §2e → L4 (`_level`); §2f → L3 (store rows) + L4
(rebuild fidelity, return line, sitting close) + L5 (houses); §2g → L4 (worker loop, resume
state, latency counts in L7) + L6 (shell); §3 → gates across L2/L3/L4 + L7's live probes; §4
content gate → documented in L7's DEVLOG/handoff; §5 tests distributed L1–L7 (each task's Step 1
names them). **Types:** `TerritoryMap`/`FitCheck`/`ForgeResult`/`forge_registry`/
`territories_within`/`read_generated_problem` names match across L1/L3/L4; `_FALLBACK_BRIDGE`
defined L3, asserted L4. **Placeholders:** none — copy strings, matrix, and gate order are
pinned; where code is not shown verbatim (L4's loop) the behavior contract and its tests are.
Suite-count expectations intentionally omitted; the gate is exit-0 + zero unexplained reds.
