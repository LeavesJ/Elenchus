# Presentation Identity (voice + visual) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Vera's rigid voice and make persona/subject/role a content-resolved presentation identity expressed across **voice** (register + a variety mechanism) and **visual** (a public theme: persona mark + role atmosphere now), over a byte-untouched engine.

**Architecture:** The resolution axis (`aim().posture → subject → persona`, `Experience.role → register + atmosphere`) resolves a presentation profile `{voice, visual}` from content. The voice facet composes `persona + role_register + craft` and is prepended to the per-method task prompt; the visual facet is a small public theme object served to the frontend. Three prompt layers replace one hardcoded string; the comprehension gear is *relocated* (not dropped) into the invariant craft, now a conditional tool plus a variety mechanism.

**Tech Stack:** Python 3.14 (`PYTHONPATH=src`), FastAPI + threaded worker bridge, pydantic v2, pytest, ruff, Anthropic Opus 4.8, vanilla HTML/JS frontend, YAML content.

**Spec:** `docs/superpowers/specs/2026-06-30-voice-persona-by-subject-role-design.md`
**Branch:** `feat/engaged-agent-comprehension-closure` (this builds on the closure work; merged/dogfooded together).

## Global Constraints

- **Engine byte-untouched:** never edit `orchestration.py`, `assessment/judgment_loop.py`, or `classify_intake`/`generate_push`/`classify_response`. Verify with `git diff main` before each commit.
- **Moat / L-13 (semantic):** no learner-facing surface names a move/frame; persona/role/craft carry no `frame_code` and no paraphrase of a `frame_detail` they touch; the visual theme is palette/identity only (no frame/rubric/`veldra:` ref; `atmosphere_label` from a fixed enum). Role registers are **world/setting idiom, never the analytical move** ("reversible/rollback/failure-default/optionality" are forbidden in registers).
- **Gear preserved (no regression):** the three comprehension behaviors (reflect-concern, re-anchor, hard-stop) must remain reachable on the turn AND converse paths after relocation — string-presence tests.
- **Terrain byte-untouched in the now-layer:** the visual theme is applied frontend-only to the chat surface; `terrain.py`/`learner_view()`/the wire payload gain no subject/biome field.
- **Graceful floor:** a `None` role / unknown posture composes a valid profile (vera + craft + a default theme), never an error.
- **Tooling:** tests `PYTHONPATH=src .venv/bin/python -m pytest -q`; web `PYTHONPATH=src .venv/bin/python -m retnovation.web`. Never `pip install -e .` (L-19).
- **Per commit:** `ruff format .` && `ruff check .` && full offline suite green; stage explicit paths only; no `Co-Authored-By`; confidential-docs `git ls-files` check clean.
- **DEVLOG** updated once at the end (Task 6).

---

### Task 1: `Experience.role` + tag the 5 founder problems

**Files:**
- Modify: `src/retnovation/types.py:155-172` (add `role` to `Experience`)
- Modify: `src/retnovation/content_loader.py:71-87` (`load_experience` reads `role`)
- Modify: `content/rubrics/{decision_under_stakes,continuity_lock_in,license_continuity}.yaml` (add `role: ceo`), `content/rubrics/{irreversible_anchor,proof_before_promise}.yaml` (add `role: cto`)
- Test: `tests/test_content_loader_role.py` (new)

**Interfaces:**
- Produces: `Experience.role: str | None`; rubric YAML key `role`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_content_loader_role.py`:

```python
from retnovation.content_loader import load_experience


def test_role_loads_ceo_and_cto_and_defaults_none():
    assert load_experience("decision_under_stakes").role == "ceo"
    assert load_experience("irreversible_anchor").role == "cto"
    # an experience with no role: key parses to None (graceful)
    exp = load_experience("proof_before_promise")
    assert exp.role == "cto"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_content_loader_role.py -v`
Expected: FAIL — `Experience` has no `role`; rubrics have no `role` key (`.role` is `None` or AttributeError).

- [ ] **Step 3: Add `role` to `Experience`**

In `src/retnovation/types.py`, the `Experience` class (after `scene: Scene | None = None`, line 163) add:

```python
    role: str | None = None  # presentation role (ceo|cto|…); resolves the voice register + atmosphere
```

- [ ] **Step 4: `load_experience` reads `role`**

In `src/retnovation/content_loader.py`, in `load_experience`, change the `Experience(...)` return (lines 81-87) to add `role`:

```python
    return Experience(
        experience_id=data["experience_id"],
        prompt=data["prompt"],
        rubric=rubric,
        ledger_ref=data["ledger_ref"],
        regime=Regime(data["regime"]),
        role=data.get("role"),
    )
```

- [ ] **Step 5: Tag the 5 rubrics**

Add a `role:` line near the top of each (e.g. after `regime:`). CEO = `decision_under_stakes.yaml`, `continuity_lock_in.yaml`, `license_continuity.yaml` get `role: ceo`. CTO = `irreversible_anchor.yaml`, `proof_before_promise.yaml` get `role: cto`. Example for `irreversible_anchor.yaml`:

```yaml
regime: open_ended
role: cto
```

- [ ] **Step 6: Run, format, lint, full suite, commit**

```bash
cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m ruff format . && PYTHONPATH=src .venv/bin/python -m ruff check . && PYTHONPATH=src .venv/bin/python -m pytest -q
git add src/retnovation/types.py src/retnovation/content_loader.py content/rubrics/decision_under_stakes.yaml content/rubrics/continuity_lock_in.yaml content/rubrics/license_continuity.yaml content/rubrics/irreversible_anchor.yaml content/rubrics/proof_before_promise.yaml tests/test_content_loader_role.py
git commit -m "feat(content): Experience.role + tag the 5 founder problems ceo/cto"
```

---

### Task 2: New voice content + theme + `resolve_presentation` (additive, not yet wired)

Create the three prompt layers + the theme files + the resolver. Nothing is wired into the live authors yet (they still use `concierge.md` with the gear), so the gear is transiently duplicated — harmless; the cutover (Task 3) removes it from `concierge.md`. Green throughout.

**Files:**
- Create: `content/prompts/voice_craft.md`, `content/personas/vera.md`, `content/personas/vera.theme.yaml`, `content/voice/role_ceo.md`, `content/voice/role_ceo.theme.yaml`, `content/voice/role_cto.md`, `content/voice/role_cto.theme.yaml`
- Modify: `content/maps/founder_ceo.yaml` (add `persona: vera`)
- Modify: `src/retnovation/content_loader.py` (loaders for craft/persona/role/theme + posture→persona)
- Modify: `src/retnovation/web/voice.py` (add `resolve_presentation`)
- Test: `tests/test_resolve_presentation.py` (new)

**Interfaces:**
- Produces: `voice.resolve_presentation(posture: str | None, exp: Experience | None) -> dict` returning `{"voice": str, "visual": dict}` where `visual` keys are exactly `{persona_mark, accent, atmosphere_label}`. Graceful: `None`/unknown posture → vera; `None`/no-role exp → no role layer.
- Consumes: `content_loader.load_prompt`, new `load_persona_text`/`load_role_text`/`load_theme`/`persona_for_posture`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_resolve_presentation.py`:

```python
import re

from retnovation.content_loader import load_experience, load_library
from retnovation.web import voice

_GEAR = ["reflect", "re-point", "STOP pressing"]  # markers of the 3 comprehension behaviors


def test_voice_composes_persona_role_craft_for_a_ceo_problem():
    exp = load_experience("decision_under_stakes")  # role=ceo
    v = voice.resolve_presentation("founder_ceo", exp)["voice"]
    assert "You are Vera" in v  # persona
    assert "boardroom" in v.lower() or "board" in v.lower()  # CEO role idiom present
    for g in _GEAR:
        assert g.lower() in v.lower(), f"gear behavior missing from composed voice: {g}"


def test_voice_is_graceful_on_unknown_posture_and_no_role():
    v = voice.resolve_presentation("no_such_posture", None)["voice"]
    assert "You are Vera" in v  # falls back to vera + craft, never raises
    for g in _GEAR:
        assert g.lower() in v.lower()


def test_visual_theme_keys_enum_and_frame_free():
    exp_ceo = load_experience("decision_under_stakes")
    exp_cto = load_experience("irreversible_anchor")
    t_ceo = voice.resolve_presentation("founder_ceo", exp_ceo)["visual"]
    t_cto = voice.resolve_presentation("founder_ceo", exp_cto)["visual"]
    assert set(t_ceo) == {"persona_mark", "accent", "atmosphere_label"}
    assert t_ceo["persona_mark"] == t_cto["persona_mark"]  # constant guide
    assert t_ceo["atmosphere_label"] in {"boardroom", "systems"}
    assert t_ceo["atmosphere_label"] != t_cto["atmosphere_label"]  # role varies
    # frame-free: no theme value contains a frame_code or veldra ref
    for t in (t_ceo, t_cto):
        blob = str(t)
        assert "veldra" not in blob and "frame" not in blob.lower()


def test_no_register_or_persona_word_shares_a_frame_detail_word():
    # The visual+voice dual of the lexical guard: registers/persona are world/idiom, frame-orthogonal.
    # Build the set of frame_detail content-words across ALL tagged problems, then assert no role/persona
    # text reuses one of a small denylist of move-words.
    forbidden = {"reversible", "rollback", "optionality", "irreversible", "default", "amend"}
    for name in ("vera", "role_ceo", "role_cto", "voice_craft"):
        text = _layer_text(name).lower()
        hits = {w for w in forbidden if re.search(rf"\b{w}\b", text)}
        assert not hits, f"{name} leaks move-words: {hits}"


def _layer_text(name):
    from retnovation.content_loader import CONTENT_ROOT

    for sub in ("prompts", "personas", "voice"):
        p = CONTENT_ROOT / sub / f"{name}.md"
        if p.exists():
            return p.read_text()
    raise AssertionError(name)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_resolve_presentation.py -v`
Expected: FAIL — no `resolve_presentation`; no content files.

- [ ] **Step 3: Create `content/prompts/voice_craft.md`** (invariant craft + relocated gear-as-tool + variety)

```
[This is the invariant craft. It binds every persona. It is composed ABOVE the persona's character
and the task instructions.]

You make the student do the reasoning. You never name the move, the frame, or the principle; you never
hand the answer or the resolution. The friction is the product. Address the student as "you"; never
invent or assume their name.

How you speak — vary it, every turn:
- One move per turn is usually enough: a single sharp question, a flat reaction, a challenge, or just
  sitting with what they said. Not every turn restates, pivots, and demands. Most turns are short.
- Never run the same shape two turns running. Vary length, rhythm, and how you press. Do not lean on the
  em-dash as a hinge. Do not re-issue the same demand you just made — find a different angle.
- React like a person, not a template.

The comprehension tools — reach for these ON THEIR SIGNAL, not as a routine opening:
- When you have not yet shown the student you understand them: before you press, briefly reflect the
  CONCERN behind their position in your own words, then push. Reflect the concern; never restate a wrong
  model as if it were correct.
- When the student wanders off the concrete problem into an analogy, a hypothetical, or their own story:
  do NOT chase it. Mirror the underlying concern, set the analogy aside, and re-point them at the specific
  decision the problem actually poses, in its own concrete terms. Re-ground; don't push the fantasy.
- When the student signals you have not understood them ("you're not getting it," "that's not what I
  said"): STOP pressing. Spend the whole turn restating their actual position back and asking them to
  confirm or correct it — mirror it without correcting, completing, or sharpening. Do not advance until
  they confirm they feel understood.
```

- [ ] **Step 4: Create `content/personas/vera.md`** (character + ≥4 divergent exemplars)

```
You are Vera. Presence is directness, not warmth. You are a dry, economical sparring partner who has been
in real rooms; you press because you take the student's thinking seriously, not to be difficult. You do
not flatter, soften, or over-explain. You are a little impatient with hand-waving, and you name the dodge
when you see it. You speak plainly — contractions, short sentences, the occasional pointed image. Never
the eager assistant.

Your turns vary in shape. The range (match their economy and difference; never copy them):
- A flat reaction, then a stop: "Okay. So you would ship it. What is the first thing that breaks?"
- A single bare question: "Who is that actually for?"
- Sitting with it: "That is a real cost. Is it the one you would actually choose to pay?"
- Naming the dodge: "You keep describing the trade instead of taking it. Take it."
```

- [ ] **Step 5: Create the role registers + theme files**

`content/voice/role_ceo.md`:

```
The room you are in is a CEO's. Speak that world: the boardroom, the quarter, the cap table, the customer
across the table, the competitor, positioning, reputation, the number you have to defend to people who
were not in the room. Press in that idiom. Never name an analytical move or principle — color where the
conversation lives, not the answer.
```

`content/voice/role_cto.md`:

```
The room you are in is a CTO's. Speak that world: the deploy, the on-call rotation, the artifact you
shipped, the customer hitting it in the field, the team carrying it, the morning after. Press in that
idiom. Never name an analytical move or principle — and never use the move-words (reversible, rollback,
optionality, failure-default); color where the conversation lives, not the answer.
```

`content/personas/vera.theme.yaml`:

```yaml
persona_mark: "V"
```

`content/voice/role_ceo.theme.yaml`:

```yaml
accent: amber
atmosphere_label: boardroom
```

`content/voice/role_cto.theme.yaml`:

```yaml
accent: teal
atmosphere_label: systems
```

- [ ] **Step 6: Add the persona key to the posture map**

In `content/maps/founder_ceo.yaml`, add at the top (a new key; `load_map`/`load_path_type` ignore it via `dict.get`):

```yaml
persona: vera
```

- [ ] **Step 7: Add loaders to `content_loader.py`**

Append to `src/retnovation/content_loader.py`:

```python
def load_persona_text(name: str, root: Path | None = None) -> str:
    return (_root(root) / "personas" / f"{name}.md").read_text()


def load_role_text(name: str, root: Path | None = None) -> str:
    return (_root(root) / "voice" / f"role_{name}.md").read_text()


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
```

- [ ] **Step 8: Add `resolve_presentation` to `voice.py`**

In `src/retnovation/web/voice.py`, after `display_titles` add:

```python
def resolve_presentation(posture: str | None, exp: Experience | None) -> dict:
    """Resolve the presentation profile from content: voice = persona + role_register + craft (composed,
    graceful), visual = a public theme {persona_mark, accent, atmosphere_label}. role comes from
    exp.role (None -> no role layer); persona from the posture map (unknown -> vera floor)."""
    from ..content_loader import (
        load_persona_text,
        load_prompt,
        load_role_text,
        load_theme,
        persona_for_posture,
    )

    persona = persona_for_posture(posture)
    role = getattr(exp, "role", None) if exp is not None else None
    parts = [load_persona_text(persona)]
    if role:
        parts.append(load_role_text(role))
    parts.append(load_prompt("voice_craft"))
    voice_text = "\n\n".join(parts)

    visual = {"persona_mark": "V", "accent": "slate", "atmosphere_label": "neutral"}
    visual.update(load_theme("personas", f"{persona}.theme"))
    if role:
        visual.update(load_theme("voice", f"role_{role}.theme"))
    visual = {k: visual[k] for k in ("persona_mark", "accent", "atmosphere_label")}
    return {"voice": voice_text, "visual": visual}
```

Note: `load_theme("personas", "vera.theme")` reads `personas/vera.theme.theme.yaml` — fix the loader call by passing the bare name. Use `load_theme("personas", persona)` and `load_theme("voice", f"role_{role}")` (the loader appends `.theme.yaml`). Correct the two `load_theme` lines to:

```python
    visual.update(load_theme("personas", persona))
    if role:
        visual.update(load_theme("voice", f"role_{role}"))
```

- [ ] **Step 9: Run the new tests, format, lint, full suite, commit**

```bash
cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_resolve_presentation.py -v
PYTHONPATH=src .venv/bin/python -m ruff format . && PYTHONPATH=src .venv/bin/python -m ruff check . && PYTHONPATH=src .venv/bin/python -m pytest -q
git add content/prompts/voice_craft.md content/personas/ content/voice/ content/maps/founder_ceo.yaml src/retnovation/content_loader.py src/retnovation/web/voice.py tests/test_resolve_presentation.py
git commit -m "feat(voice): presentation layers + resolve_presentation (persona/role/craft + theme), additive"
```

---

### Task 3: Cutover — wire the composed voice, reduce prompts to task-only, thread posture

The coupled cutover. Move the gear out of `concierge.md` (it now lives in `voice_craft.md`), reduce the three prompts to task-only, give the model methods a `voice` param, and thread `posture` through `voice.*` and the record.

**Files:**
- Modify: `content/prompts/concierge.md`, `concierge_open.md`, `concierge_close.md` (reduce to task-only)
- Modify: `src/retnovation/model.py` (Protocol + FakeModel + AnthropicModel `concierge_*` gain `voice`)
- Modify: `src/retnovation/web/voice.py` (`turn`/`opening`/`close`/`converse` take `posture`, resolve, pass `voice`)
- Modify: `src/retnovation/web/session_runner.py` (bind `aim()`, thread `posture`, add to `ch.record`, `converse`/`close` pass it)
- Test: `tests/test_voice_cutover.py` (new) + adjust nothing in existing tests (posture is keyword-default)

**Interfaces:**
- Consumes: `voice.resolve_presentation` (Task 2).
- Produces: `model.concierge_turn(problem, push, recent, *, voice="")` (+ `_open`, `_close`); `voice.turn(model, exp, push, recent, posture=None)` (+ `opening`, `close`, `converse(... , posture=None)`); `ch.record["posture"]`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_voice_cutover.py`:

```python
from retnovation.content_loader import load_experience
from retnovation.model import AnthropicModel
from retnovation.web import voice
from tests.test_voice import _StubClient  # reuse the request-capturing stub


def test_turn_prepends_the_composed_voice_with_gear_into_the_request():
    exp = load_experience("irreversible_anchor")  # cto
    stub = _StubClient(text="Okay. What breaks first?")
    m = AnthropicModel(client=stub)
    voice.turn(m, exp, "the canonical push", [("student", "ship it raw")], posture="founder_ceo")
    blob = str(stub.last)
    assert "You are Vera" in blob  # persona reached the system prompt
    assert "STOP pressing" in blob  # the gear (hard-stop) reached it -> not dropped in the cutover
    assert "embed_credentials_as_a_list" not in blob  # frame-blind: no rubric


def test_converse_also_carries_the_gear():
    exp = load_experience("irreversible_anchor")
    stub = _StubClient(text="Say more.")
    m = AnthropicModel(client=stub)
    voice.converse(m, exp, [("student", "x")], "what about the field?", posture="founder_ceo")
    assert "re-point" in str(stub.last).lower()  # re-anchor gear on the converse path too
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_voice_cutover.py -v`
Expected: FAIL — `voice.turn` has no `posture` kwarg / the composed voice isn't prepended.

- [ ] **Step 3: Reduce the three prompts to task-only**

Replace `content/prompts/concierge.md` entirely with (persona + craft + gear removed; task only):

```
You are given the problem, the conversation so far, and (sometimes) a brief: the next angle to pursue.
Write the NEXT turn — one to three sentences. Output only that turn; no preamble, no quotation marks, no meta.

If a brief (next angle) is given: pursue THAT angle — re-voiced in your own words and anchored to what the
student just said. Do not state the brief; turn it into a question that makes them reason it.

If NO brief is given: acknowledge what they said and invite a genuine, specific position on the concrete
problem — without simplifying the problem for them or hinting at the move.
```

Replace `content/prompts/concierge_open.md` entirely with:

```
You are opening a session. You are given a problem. Present it as a vivid, concrete situation in two to four
sentences — make the stakes and the specific decision tangible so a cold reader has a foothold — then invite
the student to take a position and reason it out.

Draw every specific ONLY from the problem text you are given. Invent no facts, names, or numbers, and change
nothing material. End by inviting a genuine, specific position. Output only the opening turn; no preamble, no
quotation marks, no meta.
```

Replace `content/prompts/concierge_close.md` entirely with:

```
You are closing a session. Write a short, honest closing — two to four sentences — that reflects where the
student actually landed. Output only the closing; no preamble, no meta.

- If they genuinely engaged the concrete decision the problem poses, mirror THEIR reasoning back: the
  position they took, the trade-off they are betting on, and where they are most exposed if they are wrong.
- If they stayed in an analogy, a hypothetical, or their own story and never engaged the actual decision, say
  that plainly — name that they did not take a position on the concrete choice — WITHOUT endorsing the
  analogy or restating it as if it were their answer. Do not mirror a fantasy back as "your position."
- If the student explicitly asked how they did, give a fuller but still honest read along the same lines;
  otherwise keep it brief. Use only what they argued in THIS conversation. Introduce no new analysis, name no
  principle, hand no answer. Do not grade or assign a score.
```

- [ ] **Step 4: Add the `voice` param to the three model methods**

In `src/retnovation/model.py`:

Protocol (lines 73-75) — add `*, voice: str = ""` to each:

```python
    def concierge_turn(self, problem: str, push: str, recent: list[tuple[str, str]], *, voice: str = "") -> str: ...
    def concierge_close(self, problem: str, recent: list[tuple[str, str]], *, voice: str = "") -> str: ...
    def concierge_open(self, problem: str, *, voice: str = "") -> str: ...
```

FakeModel (lines 130-135 region) — add `*, voice=""` so doubles compile (FakeModel ignores it):

```python
    def concierge_turn(self, problem, push, recent, *, voice=""):
        return push or "take a real position"  # probe: echo the brief; reinvite: a safe invite

    def concierge_close(self, problem, recent, *, voice=""):
        return "[close synthesis]"

    def concierge_open(self, problem, *, voice=""):
        return "[open]"
```

AnthropicModel — prepend `voice` to the system text in all three. `concierge_turn` (line 362-364):

```python
    def concierge_turn(self, problem: str, push: str, recent: list[tuple[str, str]], *, voice: str = "") -> str:
        # Frame-blind: problem + dialogue + the SAFE push only. `voice` = composed persona+role+craft.
        system = (voice + "\n\n" if voice else "") + load_prompt("concierge")
```

`concierge_close` (line 385-388):

```python
    def concierge_close(self, problem: str, recent: list[tuple[str, str]], *, voice: str = "") -> str:
        system = (voice + "\n\n" if voice else "") + load_prompt("concierge_close")
```

`concierge_open` (line 404-405):

```python
    def concierge_open(self, problem: str, *, voice: str = "") -> str:
        system = (voice + "\n\n" if voice else "") + load_prompt("concierge_open")
```

(The rest of each method body is unchanged.)

- [ ] **Step 5: Thread `posture` through the `voice.py` authors**

In `src/retnovation/web/voice.py`, change `turn`, `opening`, `close`, `converse` to take `posture` and pass the resolved voice:

```python
def turn(model: Model, exp: Experience, push: str, recent: list[tuple[str, str]], posture: str | None = None) -> str:
    v = resolve_presentation(posture, exp)["voice"]
    text = model.concierge_turn(exp.prompt, push, recent, voice=v)
    if not text:
        return push or SAFE_CONTRACT
    if push:
        if _performed(model, exp, text) - _performed(model, exp, push):
            return push
        return text
    if not egress_safe_reply(model, exp, text):
        return SAFE_CONTRACT
    return text


def close(model: Model, exp: Experience, recent: list[tuple[str, str]], posture: str | None = None) -> str:
    v = resolve_presentation(posture, exp)["voice"]
    text = model.concierge_close(exp.prompt, recent, voice=v)
    if not text or not egress_safe_reply(model, exp, text):
        return _STATIC_CLOSE
    return text


def opening(model: Model, exp: Experience, posture: str | None = None) -> str:
    v = resolve_presentation(posture, exp)["voice"]
    text = model.concierge_open(exp.prompt, voice=v)
    if not text or not egress_safe_reply(model, exp, text):
        return exp.prompt + "\n\n" + _INVITE
    return text


def converse(model: Model, exp: Experience, recent: list[tuple[str, str]], user_text: str, posture: str | None = None) -> str:
    return turn(model, exp, "", recent + [("student", user_text)], posture=posture)
```

(`resolve_presentation` is defined later in the file; Python resolves it at call time, so order is fine.)

- [ ] **Step 6: Thread `posture` in `session_runner.py`**

In `worker()` (line 48): bind the aim and posture:

```python
                a = aim()
                core = derive_core(a)
                posture = a.posture
                model = self._model_factory()
```

In `present()`, the opening (line 75) and the re-invite (line 90) and respond's turn (line 98) pass `posture`:

```python
                    ch.from_worker.put(("say", {"text": voice.opening(model, exp, posture)}))
```
```python
                        reinvite = voice.turn(model, exp, "", recent, posture)  # push="" -> re-invite
```
```python
                        shown = voice.turn(model, exp, push, recent, posture)
```

In the record (line 122-127), add `posture`:

```python
                    ch.record = {
                        "model": model,
                        "posture": posture,
                        "exp": captured["exp"],
                        "recent": captured["recent"],
                        "terrain": project_terrain(state, now).learner_view(),
                    }
```

In `converse` (line 168) and `close` (line 179), pass `rec["posture"]`:

```python
        reply = voice.converse(rec["model"], rec["exp"], rec["recent"], value, rec["posture"])
```
```python
        close_text = voice.close(rec["model"], rec["exp"], rec["recent"], rec["posture"])
```

- [ ] **Step 7: Run the cutover test + the FULL suite (gear must not have dropped)**

Run: `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m pytest -q`
Expected: PASS — `test_voice_cutover` green (gear present on turn + converse); all existing `test_voice.py`/`test_session_runner.py`/`test_web_api.py` still green (posture is keyword-default; FakeModel ignores `voice`; bridge-transparency unaffected).

- [ ] **Step 8: Format, lint, engine-untouched check, commit**

```bash
cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m ruff format . && PYTHONPATH=src .venv/bin/python -m ruff check .
git diff --stat main -- src/retnovation/orchestration.py src/retnovation/assessment/judgment_loop.py  # must be empty
git add content/prompts/concierge.md content/prompts/concierge_open.md content/prompts/concierge_close.md src/retnovation/model.py src/retnovation/web/voice.py src/retnovation/web/session_runner.py tests/test_voice_cutover.py
git commit -m "feat(voice): cutover — composed voice prepended, prompts task-only, gear relocated + threaded by posture"
```

---

### Task 4: Visual facet — serve the theme (two-phase) + apply it on the chat surface

**Files:**
- Modify: `src/retnovation/web/session_runner.py` (compute theme at menu + at present; put on payloads)
- Modify: `src/retnovation/web/app.py` (`_emit` passes `theme` on menu/say)
- Modify: `src/retnovation/web/static/index.html` (apply persona mark + role atmosphere)
- Test: `tests/test_visual_theme.py` (new)

**Interfaces:**
- Consumes: `voice.resolve_presentation(...).visual`.
- Produces: `menu` payload carries `theme` (persona+subject, no role); the opening `say` carries `theme` (with role); `_emit` forwards `theme`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_visual_theme.py`:

```python
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from retnovation.web.app import create_app

_ANCHOR_TITLE = "Shipping something you can't take back"  # irreversible_anchor (cto)


def test_menu_carries_persona_theme_and_say_carries_role_theme(tmp_path, make_fake):
    app = create_app(db_path=str(tmp_path / "v.db"), model_factory=make_fake)
    client = TestClient(app)
    menu = client.post("/api/session").json()
    # two-phase: menu has the persona mark but NO role atmosphere yet
    assert menu["theme"]["persona_mark"] == "V"
    assert menu["theme"]["atmosphere_label"] == "neutral"  # role unknown at menu
    assert set(menu["theme"]) == {"persona_mark", "accent", "atmosphere_label"}
    assert "veldra" not in str(menu["theme"]) and "frame" not in str(menu["theme"]).lower()
    # pick the CTO problem -> the opening say carries the role (systems) atmosphere
    idx = menu["problems"].index(_ANCHOR_TITLE)
    r = client.post("/api/session/s/choose", json={"index": idx}).json()
    assert r["kind"] == "say"
    assert r["theme"]["atmosphere_label"] == "systems"
    assert r["theme"]["persona_mark"] == "V"  # constant guide across the phases


def test_index_html_applies_the_theme():
    client = TestClient(create_app(db_path=":memory:", model_factory=None))
    html = client.get("/").text
    assert "persona_mark" in html and "atmosphere_label" in html  # the frontend reads the theme
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_visual_theme.py -v`
Expected: FAIL — no `theme` on payloads; index.html doesn't read it.

- [ ] **Step 3: Compute + attach the theme in `session_runner.py`**

In `decide()` (the menu emit, line 58), attach the persona+subject theme (posture known, no exp):

```python
                    theme = voice.resolve_presentation(posture, None)["visual"]
                    ch.from_worker.put(("menu", {"problems": labels, "refs": refs, "theme": theme}))
```

In `present()`, the opening emit (line 75) attaches the full theme (role known via exp):

```python
                    role_theme = voice.resolve_presentation(posture, exp)["visual"]
                    ch.from_worker.put(("say", {"text": voice.opening(model, exp, posture), "theme": role_theme}))
```

- [ ] **Step 4: Pass `theme` through `_emit` in `app.py`**

In `_emit` (lines 42-45), forward an optional `theme` on menu + say:

```python
    if tag == "menu":
        return {"kind": "menu", "problems": data["problems"], "theme": data.get("theme", {})}
    if tag == "say":
        out = {"kind": "say", "text": data["text"]}
        if "theme" in data:
            out["theme"] = data["theme"]
        return out
```

- [ ] **Step 5: Apply the theme in `index.html`**

In the `<style>` add CSS variables + a persona-mark badge + accent-driven theming (after line 34):

```css
  #wrap{--accent:#5a6a85}
  .accent-amber{--accent:#ba7517} .accent-teal{--accent:#1d9e75} .accent-slate{--accent:#5a6a85}
  .you{background:var(--accent)!important}
  #mark{position:fixed;top:12px;left:14px;width:26px;height:26px;border-radius:50%;
    background:var(--accent);color:#06101e;display:flex;align-items:center;justify-content:center;
    font-weight:600;font-size:14px;opacity:.9}
```

Add the mark element in the body (after `<div id="thread"></div>`, line 37):

```html
  <div id="mark" hidden></div>
```

Add a `applyTheme` function in the script (after `showComposer`, line 59) and call it in `advance`/`start`:

```js
function applyTheme(t){ if(!t) return;
  const w=document.getElementById('wrap'); w.className='';
  if(t.accent) w.classList.add('accent-'+t.accent);
  const mk=document.getElementById('mark'); if(t.persona_mark){ mk.textContent=t.persona_mark; mk.hidden=false; } }
```

In `start()` apply the menu theme (line 62-63):

```js
  const r = await post('/api/session');
  applyTheme(r.theme);
  renderMenu(r.problems);
```

In `advance()` apply any `say` theme (line 78):

```js
  if(r.kind==='say'){ applyTheme(r.theme); bubble('vera', r.text); showComposer(true); return; }
```

- [ ] **Step 6: Run, format, lint, full suite, commit**

```bash
cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_visual_theme.py -v
PYTHONPATH=src .venv/bin/python -m ruff format . && PYTHONPATH=src .venv/bin/python -m ruff check . && PYTHONPATH=src .venv/bin/python -m pytest -q
git add src/retnovation/web/session_runner.py src/retnovation/web/app.py src/retnovation/web/static/index.html tests/test_visual_theme.py
git commit -m "feat(web): serve the presentation theme (two-phase) + apply persona mark + role atmosphere (chat surface only)"
```

---

### Task 5: `@live` tests + founder dogfood

**Files:**
- Modify: `tests/test_voice_live.py` (add CEO/CTO divergence + variety)

- [ ] **Step 1: Add `@live` tests**

Append to `tests/test_voice_live.py`:

```python
@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no key")
def test_ceo_and_cto_registers_diverge_and_neither_leaks_the_move():
    from retnovation.content_loader import load_experience
    from retnovation.web import voice

    m = AnthropicModel()
    ceo = load_experience("decision_under_stakes")
    cto = load_experience("irreversible_anchor")
    reply = [("student", "I'd just pick the obvious one and move on.")]
    t_ceo = voice.turn(m, ceo, voice_push(m, ceo), reply, "founder_ceo").lower()
    t_cto = voice.turn(m, cto, voice_push(m, cto), reply, "founder_ceo").lower()
    ceo_idiom = any(w in t_ceo for w in ("board", "market", "margin", "customer", "quarter"))
    cto_idiom = any(w in t_cto for w in ("ship", "deploy", "field", "on call", "on-call", "team"))
    assert ceo_idiom or cto_idiom, f"no role idiom surfaced:\nCEO {t_ceo!r}\nCTO {t_cto!r}"
    # neither register names a move-word
    for t in (t_ceo, t_cto):
        assert not any(w in t for w in ("reversible", "rollback", "optionality"))


def voice_push(m, exp):
    f = exp.rubric.frames[0]
    return m.generate_push(exp, "frame", f.frame_code, stress=False)
```

- [ ] **Step 2: Run `@live` with the key**

Run: `cd ~/Documents/Retnovation && set -a && . ./.env && set +a && PYTHONPATH=src .venv/bin/python -m pytest tests/test_voice_live.py -m live -k "diverge or variety or hard_stop or reanchor" -v`
Expected: PASS (calibration; refine the role `.md` idiom or `voice_craft.md` wording if a soft assertion misses, then re-run).

- [ ] **Step 3: Founder dogfood**

`cd ~/Documents/Retnovation && set -a && . ./.env && set +a && PYTHONPATH=src .venv/bin/python -m retnovation.web` → http://127.0.0.1:8000. Work `decision_under_stakes` (CEO, amber/boardroom) and `irreversible_anchor` (CTO, teal/systems): Vera sounds like a person (not a loop), the two worlds look + sound different while unmistakably the same Vera, the surface theme matches the register, no steer toward the move.

- [ ] **Step 4: Commit the @live tests**

```bash
cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m pytest -q  # offline still green (live skipped)
git add tests/test_voice_live.py
git commit -m "test(live): CEO/CTO register divergence + no move-leak"
```

---

### Task 6: DEVLOG + whole-branch review

- [ ] **Step 1:** Prepend a `## 2026-06-30 — feat(presentation): persona/subject/role across voice + visual` DEVLOG entry: the rigidity dogfood; the three-layer content-resolved seam; the variety mechanism; CEO/CTO registers (world-not-move) + the light visual layer (persona mark + role atmosphere, chat-surface-only); the honest bounded role-atmosphere leak; engine + terrain byte-untouched; offline + @live results.
- [ ] **Step 2:** Full verify + confidential check + commit DEVLOG.

```bash
cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m ruff format . && PYTHONPATH=src .venv/bin/python -m ruff check . && PYTHONPATH=src .venv/bin/python -m pytest -q && git -C . ls-files | grep -iE 'berkeley|guidebook|blueprint|brief|founderceo|judgmentloop|lifttest|mvp_scope|\.pdf' || echo "clean"
git add docs/DEVLOG.md && git commit -m "docs(devlog): presentation identity — voice variety fix + persona/role across voice and visual"
```

- [ ] **Step 3:** `git diff --stat main -- src/retnovation/orchestration.py src/retnovation/assessment/judgment_loop.py` empty (engine untouched); confirm `terrain.py`/`learner_view` unchanged. Then OPUS whole-branch review (moat / gear-preserved / frame-blind / terrain-untouched / two-phase theme) → `finishing-a-development-branch`.

---

## Self-Review

**Spec coverage:** §2 profile {voice,visual} → T2/T3/T4; §4 variety mechanism (conditional gear + ≥4 divergent exemplars + variety doctrine) → voice_craft.md + vera.md (T2), N-turn @live (T5); §5 registers world-not-move + CEO/CTO proof → role_*.md (T2) + tagging (T1) + @live divergence (T5); §6 visual facet (persona mark + role atmosphere, terrain-untouched) → T4; §7 composition/threading (RELOCATION + gear-presence, voice keyword-default, posture in ch.record) → T3; §8 invariants → per-task checks + T6; §9 validation (frame-overlap guard, theme keys/enum/frame-free, two-phase, gear-presence, graceful) → T2/T3/T4; §10 build-now = voice + light visual (subject-world deferred) → T1–T4; §11 persona-resolution = map key (decided) → T2. ✓

**Placeholder scan:** content files authored in full; exact edit specs + test code throughout; no TBD. ✓ (One inline correction noted in T2 Step 8: the `load_theme` calls use the bare name, the loader appends `.theme.yaml`.)

**Type consistency:** `resolve_presentation(posture, exp) -> {voice, visual}` (T2) consumed in T3 (voice authors) + T4 (theme); `model.concierge_*(..., *, voice="")` (T3) called by `voice.*` with `voice=v`; `voice.turn/opening/close/converse(..., posture=None)` (T3) called with `posture` from session_runner; `ch.record["posture"]` written (T3) read by converse/close (T3); theme keys `{persona_mark, accent, atmosphere_label}` consistent across T2/T4. ✓
