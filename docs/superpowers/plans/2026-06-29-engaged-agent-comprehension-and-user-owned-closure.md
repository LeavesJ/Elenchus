# Engaged Agent — Comprehension Gear + User-Owned Closure + Terrain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the engaged agent demonstrate understanding before it withholds, re-ground users who drift off-problem, and hand session pace + closure to the user — with a frame-blind terrain payoff at the close — all over a byte-untouched judgment engine.

**Architecture:** Three layers change, none of them the engine. (1) A *comprehension gear* in `content/prompts/concierge.md` plus a new `voice.opening` author for a concrete turn 0. (2) *User-owned closure*: the engine's `done` becomes an internal signal; post-convergence turns and the close are served engine-free from a persisted `SessionRecord` via registry methods that never touch the terminal-guarded `step()`. (3) A *terrain* element at the user's close, reusing the Cartographer projection with a hardened, non-invertible wire surface.

**Tech Stack:** Python 3.14 (`PYTHONPATH=src`), FastAPI + threaded worker bridge, pydantic v2, pytest, ruff, Anthropic Opus 4.8 (rented). Vanilla HTML/JS frontend.

**Spec:** `docs/superpowers/specs/2026-06-29-engaged-agent-comprehension-and-user-owned-closure-design.md`

**Branch:** create `feat/engaged-agent-comprehension-closure` off `main` before Task 1 (do not build on `main`).

## Global Constraints

Every task's requirements implicitly include this section.

- **Engine byte-untouched:** never edit `orchestration.py`, `assessment/judgment_loop.py`, or the Model methods `classify_intake` / `generate_push` / `classify_response`. Verify with `git diff` before each commit.
- **L-13 frame-blind:** no learner-facing surface (turn, opening, converse, close, terrain) may name a move/frame or expose a `frame_code`. Reflect only the user's own words. Terrain renders only `learner_view()` (opaque positional ids, public-vitality order, bucketed vitality).
- **Egress on every visible turn:** every authored turn routes through `voice.py`'s `_performed` / `egress_safe_reply`, fallback `SAFE_CONTRACT` / `_STATIC_CLOSE`.
- **L-20:** the gear adds no extra per-turn model call (it is prompt-doctrine only). `voice.opening` (once at start) and `voice.converse` (post-convergence) are new, inherent interactions.
- **Confidentiality:** no `veldra:` refs and no rubric on the wire. The `SessionRecord` holds the rubric server-side only.
- **Tooling:** tests `PYTHONPATH=src .venv/bin/python -m pytest -q`; web `PYTHONPATH=src .venv/bin/python -m retnovation.web`. Never `pip install -e .` (L-19).
- **Per commit:** `ruff format .` && `ruff check .` && full offline suite green; stage explicit paths only (never `git add -A`); no `Co-Authored-By` trailer; confidential-docs `git ls-files` check clean.
- **DEVLOG** is updated once at the end of the arc (Task 7), matching this repo's practice.

---

### Task 1: Terrain wire hardening (non-invertible learner_view)

Close the three on-wire leaks the adversarial review found: frame-derived `region_id`, frame-order-derived node position, and raw-float `vitality`. Order by public vitality, assign positional ids, bucket vitality. A frame-code *rename* must leave `learner_view()` byte-identical.

**Files:**
- Modify: `src/retnovation/terrain.py:59-72` (region_id + ordering)
- Modify: `src/retnovation/types.py:494-502` (bucketed `learner_view`)
- Test: `tests/test_terrain.py` (add two tests)

**Interfaces:**
- Consumes: `project_terrain(state, now, *, min_frames=2, min_problems=2) -> TerrainView`, `TerrainView.learner_view() -> list[dict]`, `Region`, `RegionRender` (existing).
- Produces: `learner_view()` rows are exactly `{"region_id": "r{i}", "render": str, "vitality": int|None}`; ordering rendered-first then vitality-descending; `region_id` positional, never frame-derived.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_terrain.py`:

```python
def test_learner_view_is_non_invertible_under_frame_rename():
    # A frame-code RENAME (strengths + problem structure fixed) must leave learner_view byte-identical:
    # the wire carries no frame identity. (Node COUNT remains an accepted coarse-shape residual, §6.)
    state = LearnerState(
        frames={
            "embed": _fs(Strength.strong, ["P1", "P2"]),
            "choose_failure": _fs(Strength.forming, ["P1"]),
        }
    )
    renamed = LearnerState(
        frames={
            "zzz_other": _fs(Strength.strong, ["P1", "P2"]),
            "aaa_renamed": _fs(Strength.forming, ["P1"]),
        }
    )
    v1 = project_terrain(state, NOW).learner_view()
    v2 = project_terrain(renamed, NOW).learner_view()
    assert v1 == v2  # rename invariant -> non-invertible wire

    row = v1[0]
    assert set(row) == {"region_id", "render", "vitality"}  # exactly the L-13-safe keys
    assert row["region_id"] == "r0"  # positional ordinal, not the old 5-digit frame hash
    assert "frame_codes" not in row
    assert row["vitality"] in (None, 1, 2, 3)  # coarse bucket, not the raw mean


def test_learner_view_orders_by_public_vitality_not_frame_order():
    # Two disjoint rendered regions of different vitality: the brighter sorts first (r0), by PUBLIC
    # vitality — independent of the frame codes' alphabetical order (a_weak* sorts before z_strong*).
    state = LearnerState(
        frames={
            "z_strong_a": _fs(Strength.strong, ["P1", "P2"]),
            "z_strong_b": _fs(Strength.strong, ["P1", "P2"]),  # region: vit 1.0 -> bucket 3
            "a_weak_a": _fs(Strength.weak, ["P8", "P9"]),
            "a_weak_b": _fs(Strength.weak, ["P8", "P9"]),  # region: vit 0.2 -> bucket 1
        }
    )
    rows = project_terrain(state, NOW).learner_view()
    assert [r["region_id"] for r in rows] == ["r0", "r1"]
    assert rows[0]["vitality"] == 3 and rows[1]["vitality"] == 1  # brighter first
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_terrain.py -k "non_invertible or orders_by_public" -v`
Expected: FAIL — `region_id` is currently `r#####` (hash), `vitality` is a float, order is by region_id.

- [ ] **Step 3: Bucket vitality in `learner_view` (`types.py`)**

Replace `types.py:494-502` (the `TerrainView` class body) with:

```python
def _vitality_bucket(v: float | None) -> int | None:
    """Coarse 3-level wire bucket (None stays None for seeds). The exact mean would leak the strength
    distribution; the >=2-frame blend (not the bucket) is what makes vitality non-invertible (L-13)."""
    if v is None:
        return None
    if v < 0.5:
        return 1
    if v < 0.83:
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
            }
            for r in self.regions
        ]
```

- [ ] **Step 4: Positional ids + public-vitality order (`terrain.py`)**

In `terrain.py`, replace the `Region(...)` construction at lines 59-67 — change only the `region_id` argument:

```python
                region_id="",  # assigned positionally in regions_to_view (L-13: never frame-derived)
```

Replace `regions_to_view` (lines 71-72) with:

```python
def regions_to_view(regions: list[Region]) -> TerrainView:
    # L-13 wire ordering: order by PUBLIC signal only — rendered before seed, then vitality
    # descending — so a node's POSITION carries no frame information (a frame-code rename leaves the
    # learner_view payload identical). region_id is then a positional ordinal, never a hash of the
    # frame set. Tied/seed order and the node COUNT remain an accepted coarse-shape residual (§6).
    ordered = sorted(
        regions, key=lambda r: (r.render is not RegionRender.rendered, -(r.vitality or 0.0))
    )
    return TerrainView(
        regions=[r.model_copy(update={"region_id": f"r{i}"}) for i, r in enumerate(ordered)]
    )
```

- [ ] **Step 5: Run the full terrain suite to verify green**

Run: `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_terrain.py -v`
Expected: PASS (the 2 new + all 7 existing — existing tests are order-independent or single-region).

- [ ] **Step 6: Format, lint, full suite, commit**

Run: `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m ruff format . && PYTHONPATH=src .venv/bin/python -m ruff check . && PYTHONPATH=src .venv/bin/python -m pytest -q`
Expected: all green, ruff clean.

```bash
git add src/retnovation/terrain.py src/retnovation/types.py tests/test_terrain.py
git commit -m "harden(terrain): non-invertible learner_view — positional ids, public-vitality order, bucketed vitality"
```

---

### Task 2: `voice.converse` (post-convergence, engine-free turn)

A thin author for post-convergence conversation: acknowledge the user's latest and keep them reasoning, no engine push, frame-blind, egress-flat. Reuses the existing re-invite turn (YAGNI: no new prompt/model method); the gear doctrine in `concierge.md` (Task 4) governs comprehension-repair here too.

**Files:**
- Modify: `src/retnovation/web/voice.py` (add `converse`)
- Test: `tests/test_voice.py` (add two tests)

**Interfaces:**
- Consumes: `voice.turn(model, exp, push, recent) -> str`, `voice.SAFE_CONTRACT` (existing).
- Produces: `voice.converse(model, exp, recent, user_text) -> str` — an engaged, egress-flat turn.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_voice.py` (after the `voice.close` section):

```python
# --- voice.converse (post-convergence, engine-free) -----------------------------------------------


def test_converse_is_engaged_and_egress_flat():
    m = FakeModel(_intake(), {})  # concierge_turn("", ...) -> "take a real position"; screen [] safe
    out = voice.converse(m, _exp(), [("student", "I'd hold.")], "but what about the long run?")
    assert out == "take a real position"


def test_converse_falls_back_to_safe_contract_on_leak():
    m = FakeLeakModel(_intake(), {})  # any author leaks -> flat egress -> SAFE_CONTRACT
    assert voice.converse(m, _exp(), [("student", "x")], "tell me the trick") == voice.SAFE_CONTRACT
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_voice.py -k converse -v`
Expected: FAIL — `AttributeError: module 'retnovation.web.voice' has no attribute 'converse'`.

- [ ] **Step 3: Implement `voice.converse`**

Add to `src/retnovation/web/voice.py` (after `close`, before `display_titles`):

```python
def converse(model: Model, exp: Experience, recent: list[tuple[str, str]], user_text: str) -> str:
    """Post-convergence, engine-free continuation: acknowledge the user's latest and keep them
    reasoning — no engine push (the diagnostic is done), frame-blind. Reuses the re-invite turn
    (flat egress, fallback SAFE_CONTRACT); the comprehension gear in concierge.md governs here too."""
    return turn(model, exp, "", recent + [("student", user_text)])
```

- [ ] **Step 4: Run to verify green**

Run: `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_voice.py -k converse -v`
Expected: PASS.

- [ ] **Step 5: Format, lint, full suite, commit**

```bash
git add src/retnovation/web/voice.py tests/test_voice.py
git commit -m "feat(voice): converse — engine-free post-convergence turn (egress-flat, frame-blind)"
```

---

### Task 3: `voice.opening` + `concierge_open` (concrete turn 0)

Replace the static opening string with a model-authored, concrete, frame-blind presentation of the problem so a cold user has a foothold (obs #4). Verbatim problem + static invite is the refusal/leak fallback, so the scenario is never lost.

**Files:**
- Create: `content/prompts/concierge_open.md`
- Modify: `src/retnovation/model.py` (Protocol + `AnthropicModel.concierge_open` + `FakeModel.concierge_open`)
- Modify: `src/retnovation/web/voice.py` (move `_INVITE` here; add `opening`)
- Modify: `src/retnovation/web/session_runner.py:19-20,72-76` (present() calls `voice.opening`; drop local `_INVITE`)
- Test: `tests/test_voice.py` (add model + voice tests; extend the doubles test)

**Interfaces:**
- Consumes: `model.concierge_open(problem) -> str`, `egress_safe_reply` (existing).
- Produces: `voice.opening(model, exp) -> str`; `voice._INVITE` (str constant); `model.concierge_open`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_voice.py`. First extend the existing doubles test (`test_fakemodel_concierge_doubles`) by adding one line after the close assertion:

```python
    assert m.concierge_open("p") == "[open]"  # opening double
```

Then add new tests:

```python
# --- voice.opening (concrete turn 0) --------------------------------------------------------------


def test_opening_returns_authored_text_when_safe():
    class _Open(FakeModel):
        def concierge_open(self, problem):
            return "Picture the contract on your desk, unsigned. What do you do, and why?"

    m = _Open(_intake(), {})
    assert voice.opening(m, _exp()).startswith("Picture the contract")


def test_opening_falls_back_to_problem_plus_invite_on_leak():
    class _LeakOpen(FakeLeakModel):
        def concierge_open(self, problem):
            return "LEAK the move in the opening"

    m = _LeakOpen(_intake(), {})
    assert voice.opening(m, _exp()) == _exp().prompt + "\n\n" + voice._INVITE


def test_opening_falls_back_on_empty():
    class _EmptyOpen(FakeModel):
        def concierge_open(self, problem):
            return ""

    m = _EmptyOpen(_intake(), {})
    assert voice.opening(m, _exp()) == _exp().prompt + "\n\n" + voice._INVITE


def test_concierge_open_is_frame_blind_and_returns_text():
    stub = _StubClient(text="The board wants an answer by Friday. What do you commit to, and why?")
    m = AnthropicModel(client=stub)
    out = m.concierge_open("The pricing problem text.")
    assert out.startswith("The board wants an answer")
    blob = str(stub.last)
    assert "frame_detail" not in blob and "Rubric" not in blob
    assert "The pricing problem text." in blob  # the problem IS the only input
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_voice.py -k "opening or concierge_open or doubles" -v`
Expected: FAIL — no `concierge_open` / no `voice.opening` / no `voice._INVITE`.

- [ ] **Step 3: Create the opening prompt**

Create `content/prompts/concierge_open.md`:

```
You are Vera, opening a Socratic session. You are given a problem. Present it to the student as a
vivid, concrete situation in two to four sentences — make the stakes and the specific decision
tangible so a cold reader has a foothold — then invite them to take a position and reason it out.

Always:
- Draw every specific ONLY from the problem text you are given. Invent no facts, names, or numbers,
  and change nothing material about the problem.
- Never name any move, frame, principle, or "right answer". Never hint at the lesson.
- Address the student as "you"; never invent or assume their name.
- End by inviting a genuine, specific position — you push, you do not hand it over.

Output only the opening turn; no preamble, no quotation marks, no meta.
```

- [ ] **Step 4: Add `concierge_open` to the Protocol, AnthropicModel, and FakeModel (`model.py`)**

In the `Model` Protocol (after `concierge_close`, line 74) add:

```python
    def concierge_open(self, problem: str) -> str: ...
```

In `FakeModel` (after `concierge_close`, line 134) add:

```python
    def concierge_open(self, problem):
        return "[open]"
```

In `AnthropicModel` (after `concierge_close`, before `grade_answer` at line 393) add:

```python
    def concierge_open(self, problem: str) -> str:
        system = load_prompt("concierge_open")  # frame-blind: the problem text only
        resp = self._get_client().messages.create(
            model=self._model,
            max_tokens=_ECHO_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": f"Problem:\n{problem}"}],
            **_PARAMS,
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            return ""
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                return block.text
        return ""
```

- [ ] **Step 5: Move `_INVITE` into `voice.py` and add `opening`**

In `src/retnovation/web/voice.py`, add after the `SAFE_CONTRACT` block (line 9):

```python
_INVITE = "The call's yours. Take a position and reason it out — I'll push, I won't hand it over."
```

Add (after `close`, before `display_titles`):

```python
def opening(model: Model, exp: Experience) -> str:
    """Author the concrete opening turn (turn 0 — no dialogue yet): present the problem vividly so a
    cold student has a foothold (obs #4), frame hidden, specifics from the problem text only. Flat
    egress; fallback to the verbatim problem + the static invite on refusal/empty/leak so the
    scenario is never lost. (Named `opening`, not `open`, to avoid shadowing the builtin.)"""
    text = model.concierge_open(exp.prompt)
    if not text or not egress_safe_reply(model, exp, text):
        return exp.prompt + "\n\n" + _INVITE
    return text
```

- [ ] **Step 6: Wire `present()` to `voice.opening` (`session_runner.py`)**

Delete the local `_INVITE` definition (lines 19-20):

```python
# The Concierge's opening invite (static — turn 0 has no dialogue to ground on).
_INVITE = "The call's yours. Take a position and reason it out — I'll push, I won't hand it over."
```

Replace the opening emit in `present` (line 76) — change only that line:

```python
                    ch.from_worker.put(("say", {"text": voice.opening(model, exp)}))
```

(Leave the surrounding comment; the gate loop and `voice.turn(model, exp, "", recent)` re-invite are unchanged.)

- [ ] **Step 7: Run to verify green**

Run: `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_voice.py tests/test_session_runner.py tests/test_web_api.py -v`
Expected: PASS — new opening/open tests pass; existing session/web tests still pass (the displayed opening is now `[open]` from the FakeModel double; no test asserts the old opening string).

- [ ] **Step 8: Format, lint, full suite, commit**

```bash
git add content/prompts/concierge_open.md src/retnovation/model.py src/retnovation/web/voice.py src/retnovation/web/session_runner.py tests/test_voice.py
git commit -m "feat(voice): concrete opening — voice.opening + concierge_open author turn 0 (foothold, frame-blind)"
```

---

### Task 4: Comprehension gear doctrine (`concierge.md`)

Add the gear to the Concierge's turn doctrine: demonstrate understanding before withholding; reflect the concern re-pointed to the concrete problem; re-anchor when the user drifts into an analogy; hard-stop and prove comprehension when the user says "you don't understand me." Prompt-only (no extra call, L-20). Offline fakes ignore prompts, so the gate is `@live` + the founder dogfood.

**Files:**
- Modify: `content/prompts/concierge.md` (full rewrite, additive doctrine)
- Test: `tests/test_voice_live.py` (add three `@live` calibration tests)

**Interfaces:** none changed (doctrine only; `concierge_turn` signature unchanged).

- [ ] **Step 1: Write the `@live` calibration tests**

Add to `tests/test_voice_live.py`:

```python
@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no key")
def test_gear_hard_stops_on_you_dont_understand(tmp_path):
    """Cardinal-sin fix: when the user says it has not understood them, the turn must STOP pressing
    and restate/confirm — distinct from the bare push, addressing their point."""
    exp = _first_open_exp(str(tmp_path / "gear1.db"))
    m = AnthropicModel()
    f = exp.rubric.frames[0]
    push = m.generate_push(exp, "frame", f.frame_code, stress=False)
    turn = m.concierge_turn(
        exp.prompt,
        push,
        [
            ("student", "My anchor is a fixed, baked-in property that cannot be changed."),
            ("Vera", push),
            ("student", "I don't think you're understanding my anchor at all."),
        ],
    )
    assert turn.strip() and turn.strip() != push.strip()  # it adapted, did not re-fire the push
    assert "you" in turn.lower()  # it engages THEM, not a fresh angle


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no key")
def test_gear_reanchors_an_off_track_analogy(tmp_path):
    """Re-ground, do not chase: when the user answers in an unrelated analogy, the turn must press on
    the concrete decision and not simply continue inside the analogy's own object."""
    exp = _first_open_exp(str(tmp_path / "gear2.db"))
    m = AnthropicModel()
    f = exp.rubric.frames[0]
    push = m.generate_push(exp, "frame", f.frame_code, stress=False)
    turn = m.concierge_turn(
        exp.prompt,
        push,
        [("student", "It's like gene editing — you splice the DNA and the cell just expresses it.")],
    )
    assert "?" in turn  # it presses
    # it does not merely echo the analogy's vocabulary back as the subject
    assert turn.lower().count("dna") == 0 or "you" in turn.lower()


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no key")
def test_gear_still_passes_egress_after_doctrine_change(tmp_path):
    """The added doctrine must not make a faithful engaged turn leak: no added revelation vs the push."""
    from retnovation.web import voice

    exp = _first_open_exp(str(tmp_path / "gear3.db"))
    m = AnthropicModel()
    f = exp.rubric.frames[0]
    push = m.generate_push(exp, "frame", f.frame_code, stress=False)
    turn = m.concierge_turn(exp.prompt, push, [("student", "I'd hold the line and not budge.")])
    assert bool(voice._performed(m, exp, turn) - voice._performed(m, exp, push)) is False
```

- [ ] **Step 2: Confirm they skip offline (no key)**

Run: `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_voice_live.py -v`
Expected: all `@live` tests SKIPPED (no `ANTHROPIC_API_KEY` in the offline shell). This task's real gate is Step 4.

- [ ] **Step 3: Rewrite `concierge.md` with the gear**

Replace the entire contents of `content/prompts/concierge.md` with:

```
You are Vera, a Socratic instructor. You never hand over the move, the principle, or
the answer — you make the student do the reasoning. You probe, press, and surface the
trade-offs; you do not name the lesson.

You are given the problem, the conversation so far, and (sometimes) a brief: the next
angle to pursue. Write Vera's NEXT turn — one to three sentences, in her voice. Output only
that turn; no preamble, no quotation marks, no meta.

Always:
- Engage with what the student ACTUALLY just said. If they pushed back ("this is
  irrelevant"), objected, or said they are confused, acknowledge that honestly and
  briefly before you press — do not ignore it and do not repeat yourself.
- Ground your turn in their own words; refer to what they actually argued.
- Never name the move, the frame, or the principle. Never hand the answer. Ask, do not tell.
- Never invent or assume the student's name. Address them as "you."

Demonstrate understanding before you withhold. Withholding only reads as teaching, not
dodging, once the student feels understood. Before you press for the first time, briefly
reflect back — in your own words — the CONCERN or intent behind their position, so they can
tell you got what they care about, and only then push. Reflect their concern; never restate a
wrong model as if it were correct.

If the student has wandered off the concrete problem into an analogy, a hypothetical, or a
story of their own, do NOT chase them deeper into it. Mirror the underlying concern, set the
analogy aside, and re-point them at the specific decision the problem actually poses — using
the problem's own concrete terms. Re-ground; do not Socratically push the fantasy.

If the student signals you have not understood them ("you're not getting my point," "that's
not what I said," "you don't understand"), STOP pressing. Spend this whole turn restating
their actual position back in your own words and ask them to confirm or correct it. Do not
advance to a new push until they confirm they feel understood — proving comprehension is the
only job of that turn.

If a brief (next angle) is given: pursue THAT angle — re-voiced in your words and anchored
to what they just said. Do not state the brief; turn it into a question that makes them
reason it.

If NO brief is given: acknowledge what they said and invite a genuine, specific position on
the concrete problem — without simplifying the problem for them or hinting at the move.
```

- [ ] **Step 4: Run the `@live` gear tests with the key (the real gate)**

Run: `cd ~/Documents/Retnovation && set -a && . ./.env && set +a && PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_voice_live.py -m live -v`
Expected: PASS — the three new gear tests + the existing 7 live tests green. If a gear test fails, refine `concierge.md` wording and re-run (this is calibration, not code).

- [ ] **Step 5: Format, lint, offline suite, commit**

Run: `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m ruff format . && PYTHONPATH=src .venv/bin/python -m ruff check . && PYTHONPATH=src .venv/bin/python -m pytest -q`
Expected: offline green (live skipped), ruff clean.

```bash
git add content/prompts/concierge.md tests/test_voice_live.py
git commit -m "feat(gear): comprehension/grounding doctrine — earn the withhold, re-anchor, hard-stop on challenge"
```

---

### Task 5: Closure scaffolding (additive — record, registry methods, endpoints)

Add the engine-free post-convergence machinery WITHOUT yet changing the `done` contract, so the suite stays green: persist a `SessionRecord` at convergence, add `reg.converse`/`reg.close` (which never call `step()`), the `/converse`/`/close` endpoints, and the `_emit` `close` branch.

**Files:**
- Modify: `src/retnovation/web/session_runner.py` (`_Channel.record`, persist record, `converse`, `close`)
- Modify: `src/retnovation/web/app.py` (`_emit` close branch, `/converse` + `/close` endpoints)
- Test: `tests/test_session_runner.py`, `tests/test_web_api.py` (add coexistence + endpoint tests)

**Interfaces:**
- Consumes: `voice.converse`, `voice.close`, `project_terrain(...).learner_view()`, `_BLANK_NUDGE` (existing).
- Produces: `SessionRegistry.converse(sid, value) -> ("say"|"error", dict)`; `SessionRegistry.close(sid) -> ("close"|"error", dict)`; `ch.record: dict|None` with keys `model, exp, recent, terrain`; `_emit` handles `tag == "close"`; routes `POST /api/session/{sid}/converse` and `/close`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_session_runner.py` (add `from retnovation.terrain import` is not needed; the record is internal):

```python
def test_converse_and_close_work_after_done_without_the_worker(tmp_path, make_fake):
    """Post-convergence is engine-free: the worker is terminal (step errors), yet converse — served
    from the persisted record — succeeds, and close returns the honest close + the frozen terrain."""
    reg = SessionRegistry(str(tmp_path / "cv.db"), model_factory=make_fake)
    tag, _ = reg.start("scv", now=NOW)
    menu_idx = reg.menu_index("scv", _ANCHOR)
    tag, _ = reg.step("scv", menu_idx)
    tag, data = reg.step("scv", "reasoning that already holds the move")
    while tag == "say":
        tag, data = reg.step("scv", "mechanism")
    assert tag == "done"

    # the worker is terminal: step errors, but converse (engine-free, from the record) succeeds
    assert reg.step("scv", "more")[0] == "error"
    tag_c, data_c = reg.converse("scv", "but what about the long run?")
    assert tag_c == "say" and isinstance(data_c["text"], str) and data_c["text"]

    # the user-owned close returns the honest close + the frozen, frame-blind terrain
    tag_cl, data_cl = reg.close("scv")
    assert tag_cl == "close" and "close" in data_cl and isinstance(data_cl["terrain"], list)
    for blob in (data_c["text"], data_cl["close"], str(data_cl["terrain"])):
        assert "embed_credentials_as_a_list" not in blob
        assert "choose_the_failure_default_deliberately" not in blob
```

Add to `tests/test_web_api.py`:

```python
def test_converse_and_close_endpoints(tmp_path, make_fake):
    app = create_app(db_path=str(tmp_path / "ce.db"), model_factory=make_fake)
    client = TestClient(app)
    _, r = _choose_anchor(client)
    r = client.post(
        "/api/session/s/say", json={"text": "reasoning that already holds the move"}
    ).json()
    while r["kind"] == "say":
        r = client.post("/api/session/s/say", json={"text": "mechanism"}).json()
    assert r["kind"] == "done"

    # blank converse is nudged (D1 guard), never reaches the model
    assert client.post("/api/session/s/converse", json={"text": ""}).json()["kind"] == "nudge"
    cv = client.post("/api/session/s/converse", json={"text": "what if I'm wrong?"}).json()
    assert cv["kind"] == "say" and cv["text"]

    cl = client.post("/api/session/s/close").json()
    assert cl["kind"] == "close" and isinstance(cl["close"], str)
    assert isinstance(cl["terrain"], list)
    for row in cl["terrain"]:
        assert set(row) == {"region_id", "render", "vitality"}  # L-13-safe wire shape
        assert "embed_credentials_as_a_list" not in str(row)
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_session_runner.py::test_converse_and_close_work_after_done_without_the_worker tests/test_web_api.py::test_converse_and_close_endpoints -v`
Expected: FAIL — no `reg.converse`/`reg.close`, no `/converse`/`/close` routes.

- [ ] **Step 3: Persist the record + add registry methods (`session_runner.py`)**

In `_Channel.__init__` (after line 29, the `self.terminal` line) add:

```python
        self.record: dict | None = None  # post-convergence: model+exp+recent+terrain (engine-free)
```

Add the import at the top (after line 10, the `from ..orchestration import run_session` line):

```python
from ..terrain import project_terrain
```

In the worker, replace the block at lines 118-123 (close authoring + done put) with — persist the record BEFORE queuing done (persist-before-exit), keeping the close in the done payload for now (additive; Task 6 removes it):

```python
                if captured:
                    ch.record = {
                        "model": model,
                        "exp": captured["exp"],
                        "recent": captured["recent"],
                        "terrain": project_terrain(state, now).learner_view(),
                    }
                close_text = (
                    voice.close(model, captured["exp"], captured["recent"]) if captured else ""
                )
                ch.from_worker.put(
                    ("done", {"state": state, "assessment": assessment, "close": close_text})
                )
```

Add the two registry methods after `menu_index` (end of class, after line 153):

```python
    def converse(self, session_id: str, value) -> tuple[str, dict]:
        """Post-convergence engaged turn — engine-free, served from the record; never touches the
        terminal-guarded worker queue. Appends both turns so the next converse sees the full thread."""
        rec = self._ch[session_id].record
        if rec is None:
            return ("error", {"message": "session has not converged"})
        reply = voice.converse(rec["model"], rec["exp"], rec["recent"], value)
        rec["recent"].append(("student", value))
        rec["recent"].append(("Vera", reply))
        return ("say", {"text": reply})

    def close(self, session_id: str) -> tuple[str, dict]:
        """User-owned close: author the honest close from the FULL dialogue (incl. post-convergence
        turns) and return it with the frozen-at-convergence terrain. Engine-free; no step()."""
        rec = self._ch[session_id].record
        if rec is None:
            return ("error", {"message": "session has not converged"})
        close_text = voice.close(rec["model"], rec["exp"], rec["recent"])
        return ("close", {"close": close_text, "terrain": rec["terrain"]})
```

- [ ] **Step 4: Add the `_emit` close branch + endpoints (`app.py`)**

In `_emit` (after the `"say"` branch, line 45) add:

```python
    if tag == "close":  # user-driven end: the honest close + the frozen-at-convergence terrain
        return {"kind": "close", "close": data.get("close", ""), "terrain": data.get("terrain", [])}
```

In `create_app`, after the `say` route (line 78) add:

```python
    @app.post("/api/session/{sid}/converse")
    def converse(sid: str, body: _Text):
        if not body.text.strip():
            return _BLANK_NUDGE  # blank never reaches the model (D1 guard); engine-free path
        return _emit(reg, *reg.converse(_SID, body.text))

    @app.post("/api/session/{sid}/close")
    def close_session(sid: str):
        return _emit(reg, *reg.close(_SID))
```

- [ ] **Step 5: Run to verify green (new + full suite)**

Run: `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m pytest -q`
Expected: PASS — the 2 new tests pass; ALL existing tests still pass (the `done` payload is unchanged in this task, so `test_runner_assessment_equals_direct_run_session` and `test_full_session_and_l13_surface` are untouched).

- [ ] **Step 6: Format, lint, commit**

```bash
git add src/retnovation/web/session_runner.py src/retnovation/web/app.py tests/test_session_runner.py tests/test_web_api.py
git commit -m "feat(web): post-convergence record + converse/close registry methods + endpoints (additive)"
```

---

### Task 6: Closure cutover (done→terminal, frontend converse-mode + terrain)

Flip the contract: the engine's `done` no longer closes the session. Drop the worker's close-in-`done`, return `{kind:done, terminal:true}`, and make the frontend stay open in converse mode with an "End session" affordance that renders the close + terrain. Update the two tests the contract change touches.

**Files:**
- Modify: `src/retnovation/web/session_runner.py:118-122` (drop close from `done`)
- Modify: `src/retnovation/web/app.py:46-47` (`done` → terminal)
- Modify: `src/retnovation/web/static/index.html` (converse mode, End session, terrain render)
- Modify: `tests/test_session_runner.py` (drop the `"close" in data` assertion)
- Modify: `tests/test_web_api.py` (`done` is terminal; close+terrain via `/close`; html-shell assertions)

**Interfaces:**
- Produces: `done` wire shape `{"kind":"done","terminal":true}` (no `close`); `reg.start`/`reg.step` `done` payload `{state, assessment}` (no `close_text`).

- [ ] **Step 1: Update the two contract tests (now-failing) + html-shell test**

In `tests/test_session_runner.py::test_runner_assessment_equals_direct_run_session`, replace the block at lines 67-69:

```python
    assert tag == "done"
    assert "close" in data  # the conversational close is authored on completion
    runner_assess = data["assessment"]
```

with:

```python
    assert tag == "done"
    # close moved to the user-owned /close path; the done payload still carries the assessment, and
    # bridge transparency (assessment byte-equality) is unchanged.
    runner_assess = data["assessment"]
```

In `tests/test_web_api.py::test_full_session_and_l13_surface`, replace lines 49-52:

```python
    assert r["kind"] == "done"
    assert "close" in r and isinstance(r["close"], str)
    assert "terrain" not in r  # deferred for the MVP
    seen.append(r["close"])
```

with:

```python
    assert r["kind"] == "done" and r.get("terminal") is True
    assert "close" not in r  # the engine's 'done' no longer closes — the user owns the exit
    # the user ends the session -> honest close + the (now SURFACED) frozen terrain
    cl = client.post("/api/session/s/close").json()
    assert cl["kind"] == "close" and isinstance(cl["close"], str)
    assert isinstance(cl["terrain"], list)
    seen.append(cl["close"])
    seen.append(str(cl["terrain"]))
```

In `tests/test_web_api.py::test_index_html_is_a_chat_shell`, add after the existing assertions:

```python
    assert "/converse" in html and "End session" in html  # user-owned closure surface
    assert "Your read is recorded" not in html  # the engine no longer stamps closure
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_session_runner.py::test_runner_assessment_equals_direct_run_session tests/test_web_api.py -v`
Expected: FAIL — `done` still carries `close`; html lacks `/converse`/`End session`.

- [ ] **Step 3: Drop close from the worker `done` (`session_runner.py`)**

Replace the block from Task 5 Step 3 (the `if captured: ... ch.from_worker.put(("done", {...close_text...}))`) with — record persisted before done, no close in the done payload:

```python
                if captured:
                    ch.record = {
                        "model": model,
                        "exp": captured["exp"],
                        "recent": captured["recent"],
                        "terrain": project_terrain(state, now).learner_view(),
                    }
                ch.from_worker.put(("done", {"state": state, "assessment": assessment}))
```

- [ ] **Step 4: `done` → terminal (`app.py`)**

Replace the `_emit` `done` branch (lines 46-47):

```python
    if tag == "done":  # the engine converged — but the SESSION does not end; the user owns closure
        return {"kind": "done", "terminal": True}
```

- [ ] **Step 5: Frontend converse-mode + terrain (`index.html`)**

In the `<style>` block, add before `</style>` (after line 27):

```css
  .terrain{align-self:center;display:flex;gap:10px;flex-wrap:wrap;justify-content:center;margin:10px 0 2px}
  .node{width:18px;height:18px;border-radius:50%;background:#0f3a3f;box-shadow:0 0 6px #155e63}
  .node.v2{background:#1d6f6f;box-shadow:0 0 12px #2bd4c4}
  .node.v3{background:#2bd4c4;box-shadow:0 0 18px #5eead4}
  .end{align-self:center;margin-top:8px;background:#0f1a2b;border:1px solid #2b4a6b;color:#cfe;
    border-radius:10px;padding:8px 16px;font:inherit;cursor:pointer}
  .end:disabled{opacity:.5;cursor:default}
```

In the `<script>`, add a mode flag after the `send` declaration (line 40):

```js
let mode='engine';  // 'engine' -> /say (gate + probes); 'converse' -> /converse (post-convergence)
```

Replace `advance(r)` (lines 69-74) with:

```js
function advance(r){
  if(r.kind==='say'){ bubble('vera', r.text); showComposer(true); return; }
  if(r.kind==='done'){ mode='converse'; showComposer(true); endButton(); return; }
  if(r.kind==='close'){ renderClose(r); return; }
  if(r.kind==='nudge'){ muted(r.message); showComposer(true); return; }
  muted('error: '+(r.message||'')); showComposer(true);
}
function endButton(){
  const b=document.createElement('button'); b.className='end'; b.type='button'; b.textContent='End session';
  b.onclick=async()=>{ b.disabled=true; const t=thinking();
    try{ const r=await post('/api/session/single/close'); t.remove(); renderClose(r); }
    catch(_){ t.remove(); b.disabled=false; muted('connection lost — try again.'); } };
  thread.appendChild(b); thread.scrollTop=thread.scrollHeight;
}
function renderClose(r){ if(r.close) bubble('vera', r.close); renderTerrain(r.terrain||[]); showComposer(false); }
function renderTerrain(regions){
  const rendered=regions.filter(x=>x.render==='rendered');
  const wrap=document.createElement('div'); wrap.className='terrain';
  rendered.forEach(x=>{ const n=document.createElement('span'); n.className='node v'+(x.vitality||1); wrap.appendChild(n); });
  if(rendered.length) thread.appendChild(wrap);
  muted(rendered.length ? (rendered.length+' area'+(rendered.length===1?'':'s')+' have taken shape.')
                        : 'A seed was planted — it grows as you work more.');
  thread.scrollTop=thread.scrollHeight;
}
```

Replace the composer submit handler's post URL (line 80) so it routes by mode:

```js
    const url = mode==='converse' ? '/api/session/single/converse' : '/api/session/single/say';
    const r=await post(url,{text}); t.remove(); advance(r);
```

- [ ] **Step 6: Run the full suite + node syntax check**

Run: `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m pytest -q`
Expected: PASS (all tests, including the updated two + the html-shell assertions).

Optionally sanity-check the inline script parses (extract is not needed — the html-shell test covers presence; a manual browser smoke is in Task 7).

- [ ] **Step 7: Format, lint, commit**

```bash
git add src/retnovation/web/session_runner.py src/retnovation/web/app.py src/retnovation/web/static/index.html tests/test_session_runner.py tests/test_web_api.py
git commit -m "feat(closure): user owns the exit — done is internal, converse-mode + terrain at the user-driven close"
```

---

### Task 7: DEVLOG + browser smoke + whole-branch review handoff

**Files:**
- Modify: `docs/DEVLOG.md` (prepend one entry)

- [ ] **Step 1: Browser smoke (manual, with the key)**

Run: `cd ~/Documents/Retnovation && set -a && . ./.env && set +a && PYTHONPATH=src .venv/bin/python -m retnovation.web`
Visit http://127.0.0.1:8000 — confirm: concrete opening; the gear reflects/re-anchors; on convergence the composer STAYS open with "End session"; clicking it shows the honest close + terrain nodes. (Founder dogfood: re-run the `irreversible_anchor` gene-editing analogy.)

- [ ] **Step 2: Prepend the DEVLOG entry**

Add a `## 2026-06-29 — feat(engaged-agent): comprehension gear + user-owned closure + terrain` entry to the top of `docs/DEVLOG.md`: the dogfood failure that started it (obs #1–#7), the layer-on-intact-engine decision, the six tasks, the L-13 terrain hardening (positional ids / public-vitality order / bucketed vitality / rename-invariance test), the engine-byte-untouched + transparency invariants held, and the offline suite + `@live` results. Note obs #6 is mitigated-not-cured and the node-count/accretion residual is accepted.

- [ ] **Step 3: Full verification + commit**

Run: `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m ruff format . && PYTHONPATH=src .venv/bin/python -m ruff check . && PYTHONPATH=src .venv/bin/python -m pytest -q && git -C . ls-files | grep -iE 'berkeley|guidebook|blueprint|brief|founderceo|judgmentloop|lifttest|mvp_scope|\.pdf' || echo "confidential clean"`
Expected: green, ruff clean, no confidential docs tracked.

```bash
git add docs/DEVLOG.md
git commit -m "docs(devlog): engaged-agent comprehension gear + user-owned closure + terrain"
```

- [ ] **Step 4: Engine-untouched proof + whole-branch review**

Run: `git -C ~/Documents/Retnovation diff --stat main -- src/retnovation/orchestration.py src/retnovation/assessment/judgment_loop.py`
Expected: EMPTY (engine byte-untouched). Confirm `generate_push`/`classify_intake`/`classify_response` in `model.py` are unchanged by the diff. Then hand to an OPUS whole-branch review (moat / transparency / frame-blindness / egress) before `finishing-a-development-branch`.

---

## Self-Review

**1. Spec coverage** (each spec section → task):
- §4 gear: concrete opening = Task 3 (`voice.opening` + `concierge_open`); front-load + re-anchor + hard-stop = Task 4 (`concierge.md`). ✓
- §5 closure: record + `step()`-free converse/close + endpoints + blank guard = Tasks 5–6; `voice.converse` = Task 2. ✓
- §6 terrain: hardened `learner_view` (opaque id, public order, bucketed vitality, rename-invariance test) = Task 1; render at user-close = Task 6; cumulative-state projection = Task 5/6 worker. ✓
- §7 invariants: engine-untouched proof = Task 7 Step 4; transparency test kept = Task 6 Step 1; egress on every turn = Tasks 2/3 use `voice` egress; L-20 = Task 4 prompt-only. ✓
- §8 obs #6: mitigation noted in DEVLOG (Task 7); the gear (Task 4) + freeze-at-convergence (Task 5/6) carry it. ✓
- §9 validation: terrain non-invertibility (T1), converse engine-free/coexistence (T5), flipped deferred-terrain assertion (T6), `@live` gear (T4), re-dogfood (T7). ✓

**2. Placeholder scan:** every code step shows full code; no TBD/TODO/"add error handling". ✓

**3. Type consistency:** `concierge_open(problem)->str` (Protocol/Anthropic/Fake all added in T3); `voice.opening(model,exp)->str`; `voice.converse(model,exp,recent,user_text)->str`; `reg.converse(sid,value)->(str,dict)`, `reg.close(sid)->(str,dict)`; `ch.record` keys `{model,exp,recent,terrain}` written in T5/T6 and read in `reg.converse`/`reg.close`; `_emit` `close` tag → `{kind:close,close,terrain}` produced by `reg.close` and consumed by `index.html renderClose`. Wire `done` → `{kind:done,terminal:true}` produced in T6, consumed by `advance`. Names align across tasks. ✓

**Note on the two "unchanged-green" tests:** the spec listed `test_runner_assessment_equals_direct_run_session` under unchanged-green, but it asserts `"close" in data`; since close moves to `/close`, Task 6 Step 1 removes that one line (the assessment byte-equality — the actual transparency guarantee — is unchanged). Honest correction folded in.
