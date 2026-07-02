# Woven Stance Modulation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mid-session, Vera presses hard early, opens with an earned movement-acknowledgment when the user genuinely moves, and eases/narrows from push 3 on — so the session feels like a trajectory, not an interrogation.

**Architecture:** A stance-arc + craft doctrine in `content/prompts/concierge.md` (the PROBE-ONLY base prompt — NEVER `voice_craft.md`, which rides into every author); a free frame-blind arc hint `(n, MAX_PUSHES)` counted at the bridge's `respond` closure and threaded `voice.turn → model.concierge_turn` as a brief line. Engine byte-untouched.

**Tech Stack:** Python 3.14 (`PYTHONPATH=src .venv/bin/...`), pytest, ruff; doctrine as content (L-1).

## Global Constraints

- **Engine byte-untouched:** `orchestration.py`, `assessment/` — empty diff. `MAX_PUSHES` (judgment_loop.py:17, value 8) is imported read-only.
- **Doctrine home = `content/prompts/concierge.md` ONLY** (spec MF-2). `voice_craft.md` untouched. Sentinel header for tests: `The arc of the press`.
- **L-4/L-5 worked contrasts verbatim from spec §3a** (describe-never-rate; narrow-never-point). The ack's prescribed shape: a perfect-tense second-person opener ("You've …"), reserved for real movement — this makes the earned gate testable (MF-4).
- **The probe egress gate stays byte-unchanged** (MF-1): acks survive by being move-free by construction; the @live gate-compat test is the teeth.
- **All 5 frozen fakes gain the kwarg in the same commit** (MF-3, L-10): `tests/test_voice.py:55,75,146,255`, `tests/test_session_runner.py:101`.
- Per commit: `ruff format .`, `ruff check .`, `PYTHONPATH=src .venv/bin/pytest -q` green; confidential-docs `git ls-files` guard; explicit paths only; no Co-Authored-By. Baseline: 322 passed / 20 skipped. Repo: `~/Documents/Retnovation`, branch `main` (repo convention for post-merge follow-ups; hold push).

---

### Task 1: Arc plumbing — `concierge_turn(arc=None)` + `voice.turn` pass-through + the 5 fakes

**Files:**
- Modify: `src/retnovation/model.py` (Protocol ~:73; FakeModel ~:146; AnthropicModel `concierge_turn` ~:383)
- Modify: `src/retnovation/web/voice.py` (`turn` ~:60)
- Modify: `tests/test_voice.py:55,75,146,255`, `tests/test_session_runner.py:101` (add the kwarg to the frozen fakes)
- Test: `tests/test_voice.py`

**Interfaces:**
- Produces: `concierge_turn(self, problem, push, recent, *, arc: tuple[int, int] | None = None, voice="") -> str` (all definitions); `voice.turn(model, exp, push, recent, posture=None, arc=None)`. Brief line when `push` non-empty AND `arc`: `Arc: this is push {n}; the diagnostic never runs past {cap} pushes and usually resolves well before that.`

- [ ] **Step 1: Failing tests** — add to `tests/test_voice.py`:

```python
# --- arc threading (woven stance modulation) ------------------------------------------------------


def test_turn_threads_arc_to_the_author():
    class _Rec(FakeModel):
        def __init__(self, intake):
            super().__init__(intake, {})
            self.arc = "unset"

        def concierge_turn(self, problem, push, recent, *, arc=None, voice=""):
            self.arc = arc
            return push or "take a real position"

    m = _Rec(_intake())
    voice.turn(m, _exp(), "the push", [("student", "x")], None, (3, 8))
    assert m.arc == (3, 8)
    m2 = _Rec(_intake())
    voice.turn(m2, _exp(), "the push", [("student", "x")])  # default: no arc
    assert m2.arc is None


def test_concierge_turn_brief_carries_arc_line_only_on_probe():
    stub = _StubClient(text="A sharp probe?")
    m = AnthropicModel(client=stub)
    m.concierge_turn("P", "the angle", [("student", "x")], arc=(3, 8))
    blob = str(stub.last)
    assert "Arc: this is push 3" in blob and "8 pushes" in blob
    stub2 = _StubClient(text="A sharp probe?")
    m2 = AnthropicModel(client=stub2)
    m2.concierge_turn("P", "the angle", [("student", "x")])  # no arc -> no line
    assert "Arc:" not in str(stub2.last)
    stub3 = _StubClient(text="An invite.")
    m3 = AnthropicModel(client=stub3)
    m3.concierge_turn("P", "", [("student", "x")], arc=(3, 8))  # re-invite NEVER carries an arc
    assert "Arc:" not in str(stub3.last)
```

- [ ] **Step 2: Verify fail** — `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/pytest tests/test_voice.py -k arc -q` → TypeError (unexpected keyword `arc`).

- [ ] **Step 3: Implement.** Protocol (model.py ~:73): change to

```python
    def concierge_turn(
        self,
        problem: str,
        push: str,
        recent: list[tuple[str, str]],
        *,
        arc: tuple[int, int] | None = None,
        voice: str = "",
    ) -> str: ...
```

FakeModel (~:146): `def concierge_turn(self, problem, push, recent, *, arc=None, voice=""):` (body unchanged). AnthropicModel: same signature; after the existing `brief = (...)` assignment insert:

```python
        if push and arc:
            n, cap = arc
            brief += (
                f"\nArc: this is push {n}; the diagnostic never runs past {cap} pushes "
                "and usually resolves well before that."
            )
```

`voice.turn`: signature gains `arc: tuple[int, int] | None = None` (after `posture`); the call becomes `model.concierge_turn(exp.prompt, push, recent, arc=arc, voice=v)`. Docstring gains: `arc=(n, cap) is the frame-blind position hint (probe turns only).` Update the 5 frozen fakes' signatures to `def concierge_turn(self, problem, push, recent, *, arc=None, voice=""):` (bodies unchanged) at `tests/test_voice.py:55,75,146,255` and `tests/test_session_runner.py:101`.

- [ ] **Step 4: Verify pass** — same command → green; then full gate: `PYTHONPATH=src .venv/bin/ruff format . && PYTHONPATH=src .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q` → 324 passed / 20 skipped.

- [ ] **Step 5: Commit**

```bash
git -C ~/Documents/Retnovation add src/retnovation/model.py src/retnovation/web/voice.py tests/test_voice.py tests/test_session_runner.py
git -C ~/Documents/Retnovation commit -m "feat(voice): frame-blind arc hint threads voice.turn -> concierge_turn (probe brief only)"
```

---

### Task 2: The bridge counter — arc at the probe display call

**Files:**
- Modify: `src/retnovation/web/session_runner.py` (imports ~:10; the `respond` closure ~:105)
- Test: `tests/test_session_runner.py`

**Interfaces:**
- Consumes: `voice.turn(..., arc=(n, MAX_PUSHES))` (Task 1).
- Produces: every probe display call carries `arc=(n, MAX_PUSHES)`, n starting at 1 (pre-increment).

- [ ] **Step 1: Failing test** — add to `tests/test_session_runner.py` (uses its existing session-driving pattern with `make_fake`/`steer`, NOW = its module constant; adapt imports to the file's header):

```python
def test_probe_displays_carry_an_incrementing_arc(tmp_path, make_fake, steer):
    from retnovation.assessment.judgment_loop import MAX_PUSHES

    arcs = []

    def factory():
        m = make_fake()
        orig = m.concierge_turn

        def rec(problem, push, recent, *, arc=None, voice=""):
            if push:
                arcs.append(arc)
            return orig(problem, push, recent, arc=arc, voice=voice)

        m.concierge_turn = rec
        return m

    reg = SessionRegistry(str(tmp_path / "arc.db"), model_factory=factory)
    tag, _ = reg.start("s1", now=NOW)
    tag, _ = reg.step("s1", reg.menu_index("s1", _ANCHOR))
    tag, data = reg.step("s1", "reasoning that already holds the move")
    while tag == "say":
        tag, data = reg.step("s1", "mechanism")
    assert tag == "done"
    assert arcs == [(i + 1, MAX_PUSHES) for i in range(len(arcs))]  # 1-based, pre-incremented
    assert len(arcs) >= 1
```

- [ ] **Step 2: Verify fail** — `PYTHONPATH=src .venv/bin/pytest tests/test_session_runner.py -k arc -q` → arcs full of `None`.

- [ ] **Step 3: Implement.** In `session_runner.py` add `from ..assessment.judgment_loop import MAX_PUSHES` to the relative-import block; in `present(exp)` before `def respond(push):` add `pushes = 0` (alongside `recent`/`nonsubstantive`), and change `respond`:

```python
                    def respond(push):
                        # Display the engaged, dialogue-grounded turn; the engine still grades the
                        # CANONICAL push vs the RAW reply (bridge transparency preserved). The arc
                        # hint (pre-incremented: first probe = push 1) rides the DISPLAY path only.
                        nonlocal pushes
                        pushes += 1
                        shown = voice.turn(model, exp, push, recent, posture, (pushes, MAX_PUSHES))
                        ch.from_worker.put(("say", {"text": shown}))
                        recent.append(("Vera", shown))
                        student = ch.to_worker.get()
                        recent.append(("student", student))
                        return student  # RAW reply to the engine — canonical push is what it grades
```

(The door re-invite call `voice.turn(model, exp, "", recent, posture)` is untouched — no arc pre-engine.)

- [ ] **Step 4: Verify pass + moat** — focused test green; `PYTHONPATH=src .venv/bin/pytest tests/test_session_runner.py tests/test_web_api.py -q` green (bridge transparency untouched); `git -C ~/Documents/Retnovation diff main@{1} --stat -- src/retnovation/orchestration.py src/retnovation/assessment/` — use `git diff HEAD --stat -- ...` → empty; full gate → 325 passed / 20 skipped.

- [ ] **Step 5: Commit**

```bash
git -C ~/Documents/Retnovation add src/retnovation/web/session_runner.py tests/test_session_runner.py
git -C ~/Documents/Retnovation commit -m "feat(web): count pushes at the bridge and pass the arc hint to probe displays"
```

---

### Task 3: The doctrine — stance arc + craft in `concierge.md` + the no-leak sentinel

**Files:**
- Modify: `content/prompts/concierge.md` (append)
- Test: `tests/test_voice.py`

- [ ] **Step 1: Failing tests** — add to `tests/test_voice.py`:

```python
def test_arc_doctrine_lives_only_in_the_probe_prompt():
    """MF-2: voice_craft rides into EVERY author — the press/arc stance must live in concierge.md
    (probe-only). Sentinel: the section header. land/converse must never see it."""
    from retnovation.content_loader import load_prompt

    assert "The arc of the press" in load_prompt("concierge")
    assert "The arc of the press" not in load_prompt("voice_craft")
    stub = _StubClient(text="landing text")
    m = AnthropicModel(client=stub)
    m.concierge_land("P", [("student", "x")], "converged", voice=voice.resolve_presentation(None, None)["voice"])
    assert "The arc of the press" not in str(stub.last)
    stub2 = _StubClient(text="wind-down")
    m2 = AnthropicModel(client=stub2)
    m2.concierge_converse("P", [("student", "x")], voice=voice.resolve_presentation(None, None)["voice"])
    assert "The arc of the press" not in str(stub2.last)
```

- [ ] **Step 2: Verify fail** — `PYTHONPATH=src .venv/bin/pytest tests/test_voice.py -k doctrine -q` → sentinel missing from concierge.

- [ ] **Step 3: Append to `content/prompts/concierge.md`** (verbatim):

```
The arc of the press — the diagnostic has a shape; your manner follows it. (The brief may carry an
"Arc:" line: push N of a hard cap. Never state position to the student.)
- Early (pushes 1–2): full friction. Press hard and cold; no warmth owed; the contract is the press.
- EARNED movement only, anywhere in the arc: when the student's LATEST reply genuinely moved — conceded a
  cost, named a number, dropped a hedge, took the harder fork of their own dilemma — open with ONE
  perfect-tense clause naming that movement in THEIR concrete words ("You've stopped defending the number
  and started pricing its failure — so ..."), then press on. Reserve that "You've ..." opener for real
  movement: a reply that merely restates, defends, or decorates gets NO warmth and no such opener —
  silence on the progress channel is a signal too. Never acknowledge two turns running out of politeness.
  DESCRIBE the movement, never RATE it or the person or the conclusion: no "good", "exactly", "right",
  "well done", "now you're getting it". Mirror their words, never the principle behind them.
- Late (push 3 onward, easing progressively): shorter turns; open NO new fronts; drop settled threads and
  hold the ONE most alive tension in the student's own words as a single tight question. Ease the shape,
  never the honesty. Never resolve, synthesize, or point — "so the real question is X" hands direction;
  hold the tension open instead ("Forget the segments — the thing still open is what you do the morning
  the numbers disagree. So?").
- Craft, always: at most ONE question per turn — if two things burn, pick the sharper; the other keeps.
  No dismissive interjections ("Fine.", "Sure.") — engage what they said or move through it, never wave
  it off. Never re-press what your own previous turn just pressed: if they dodged it, come at the same
  ground through their newest words, or leave it for the close to name honestly.
```

- [ ] **Step 4: Verify pass** — focused green; full gate → 326 passed / 20 skipped.

- [ ] **Step 5: Commit**

```bash
git -C ~/Documents/Retnovation add content/prompts/concierge.md tests/test_voice.py
git -C ~/Documents/Retnovation commit -m "feat(doctrine): the arc of the press — earned acknowledgment, late-arc narrowing, hard craft rules (probe prompt only)"
```

---

### Task 4: `@live` behavioral suite

**Files:**
- Modify: `tests/test_voice_live.py` (append; reuse `_first_open_exp`, `_voice`, `_VERDICT_TOKENS`, `_CONVERGED`)

- [ ] **Step 1: Append the tests** (each `@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no key")`):

```python
# --- Woven stance modulation (live behavior) -------------------------------------------------------

_ACK_OPENERS = ("you've", "you have", "you just", "you stopped", "you started")

_MOVEMENT_REPLY = (
    "Fine — I'll say the part I was avoiding: locking this in costs me the next two quarters of "
    "flexibility, and I'd still do it. 12 for 12, and I own the downside if churn spikes."
)
_RESTATEMENT_REPLY = "Like I said, verifiable audits and data are what's essential. That's my answer."


def _probe_turn(m, exp, reply, arc):
    f = exp.rubric.frames[0]
    push = m.generate_push(exp, "frame", f.frame_code, stress=False)
    return m.concierge_turn(
        exp.prompt, push, [("Vera", "And the cost?"), ("student", reply)], arc=arc, voice=_voice(exp)
    ), push


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no key")
def test_movement_draws_an_earned_ack_without_verdict(tmp_path):
    exp = _first_open_exp(str(tmp_path / "ack.db"))
    m = AnthropicModel()
    turn, _ = _probe_turn(m, exp, _MOVEMENT_REPLY, (2, 8))
    low = turn.lower().lstrip()
    assert low.startswith(_ACK_OPENERS), f"no ack-shaped opener on real movement: {turn!r}"
    assert not any(t in low for t in _VERDICT_TOKENS), f"ack rated the conclusion: {turn!r}"


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no key")
def test_restatement_draws_no_ack_opener(tmp_path):
    exp = _first_open_exp(str(tmp_path / "noack.db"))
    m = AnthropicModel()
    turn, _ = _probe_turn(m, exp, _RESTATEMENT_REPLY, (2, 8))
    assert not turn.lower().lstrip().startswith(_ACK_OPENERS), (
        f"rhythmic flattery: ack opener on a pure restatement: {turn!r}"
    )


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no key")
def test_ack_on_settled_ground_survives_the_probe_gate(tmp_path):
    """MF-1 teeth: a GOOD ack naming movement on a PREVIOUSLY-settled thread must pass the real
    push-diff gate (else voice.turn silently discards the feature's output)."""
    from retnovation.web import voice

    exp = _first_open_exp(str(tmp_path / "gate.db"))
    m = AnthropicModel()
    t = exp.rubric.traps[0]
    push = m.generate_push(exp, "trap", t.trap_code, stress=False)  # press a DIFFERENT angle
    ack_turn = (
        "You've stopped hedging and owned what the lock-in costs you — so on this new front: "
        + push
    )
    added = bool(voice._performed(m, exp, ack_turn) - voice._performed(m, exp, push))
    assert added is False, "the probe gate eats a move-free ack — escalate to segment screening (spec §4)"


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no key")
def test_late_arc_is_shorter_and_single_question(tmp_path):
    exp = _first_open_exp(str(tmp_path / "late.db"))
    m = AnthropicModel()
    early, _ = _probe_turn(m, exp, _RESTATEMENT_REPLY, (1, 8))
    late, _ = _probe_turn(m, exp, _RESTATEMENT_REPLY, (5, 8))
    assert len(late) <= 0.85 * len(early), f"late arc not shorter: {len(late)} vs {len(early)}"
    assert late.count("?") <= 1, f"late turn stacks questions: {late!r}"


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no key")
def test_craft_one_question_no_dismissive_tics(tmp_path):
    exp = _first_open_exp(str(tmp_path / "craft.db"))
    m = AnthropicModel()
    turn, _ = _probe_turn(m, exp, _MOVEMENT_REPLY, (2, 8))
    assert turn.count("?") <= 1, f"stacked questions: {turn!r}"
    assert not any(turn.lstrip().startswith(t) for t in ("Fine.", "Sure.")), f"dismissive tic: {turn!r}"
```

- [ ] **Step 2: Offline safety** — `PYTHONPATH=src .venv/bin/pytest tests/test_voice_live.py --collect-only -q` → +5 collected; full offline suite → 326 passed / **25** skipped.

- [ ] **Step 3: Commit**

```bash
git -C ~/Documents/Retnovation add tests/test_voice_live.py
git -C ~/Documents/Retnovation commit -m "test(live): earned ack (no verdict), anti-flattery gate, gate-compat, late-arc easing, craft rules"
```

---

### Task 5: DEVLOG + whole-branch review + finish

- [ ] Prepend a DEVLOG entry (root cause → design decisions incl. MF-1/MF-2 → what shipped → invariants → @live founder-gated).
- [ ] Full gate: ruff both, suite 326/25, engine empty-diff (`git diff 13ab12f --stat -- src/retnovation/orchestration.py src/retnovation/assessment/` → empty), health smoke.
- [ ] Whole-batch adversarial review (2-lens OPUS Workflow over the 4 commits, repo pattern) → fold findings.
- [ ] Founder gates: `@live` run (`pytest -m live -q`, spends Opus), felt dogfood, push.

## Self-Review (planner)

**Spec coverage:** §3a doctrine → T3 (verbatim contrasts, ack shape, late-arc, position-never-stated); §3b plumbing → T1 (kwarg+brief line+re-invite-never, 5 fakes)+T2 (pre-increment counter, MAX_PUSHES import, door path untouched); §3c craft → T3; §3d 6-turn window is the existing default (no change needed); §4 gate resolution → T4 gate-compat test + doctrine "mirror their words never the principle"; §5 tests → T1/T2 offline, T3 sentinel, T4 the five @live; §7 files all covered. **Placeholders:** none. **Type consistency:** `arc: tuple[int, int] | None = None` keyword-only everywhere; `voice.turn(..., posture, arc)` positional-after-posture matches T2's call `(pushes, MAX_PUSHES)`; sentinel string identical in T3 test and doctrine text.
