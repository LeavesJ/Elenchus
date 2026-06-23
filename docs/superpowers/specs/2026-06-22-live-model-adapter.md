# Live Model Adapter (`AnthropicModel`) — Design Spec

- **Date:** 2026-06-22
- **Status:** Approved (brainstorming). Inline TDD.
- **Sources:** `claude-api` reference (Opus 4.8 SDK usage); the approved harness spec; JudgmentLoop v0.1; Berkeley Operating Guidebook §5–6.

## 1. Goal
Implement `AnthropicModel`'s three `Model` methods against `claude-opus-4-8` so the
judgment loop runs against the live model instead of the scripted `FakeModel` — with the
doctrine kept as versioned content, not hardcoded in `src/`.

## 2. Scope
**In:** doctrine prompt templates in `content/prompts/`; `content_loader.load_prompt`;
`AnthropicModel.{classify_intake, generate_push, classify_response}`; mock-based unit
tests; a gated live smoke test.
**Out:** any change to the `Model` interface, `judgment_loop`, the harness, or the
`FakeModel` dry run. No new build-order steps.

## 3. Doctrine as data — `content/prompts/`
Three Markdown templates, each the system-prompt text for one call type. They encode the
**disband rules** verbatim (never name the frame; never hand the answer; never grade the
conclusion; *sharper* = a gap closed with a supplied mechanism; presence is
conclusion-agnostic). The per-experience rubric and the student's work are injected by the
adapter at call time — the templates contain no experience-specific content.
- `content/prompts/intake.md` — classify each rubric frame/trap's initial state from the opening.
- `content/prompts/push.md` — produce one angle-only push for a target, without naming it.
- `content/prompts/response.md` — classify the student's reply: outcome, mechanism, hard-wrong.

`content_loader.load_prompt(name: str, root: Path | None = None) -> str` reads
`content/prompts/{name}.md`.

## 4. `AnthropicModel` (`src/retnovation/model.py`)
`__init__(self, api_key: str | None = None, model: str = "claude-opus-4-8", client=None)` —
the optional `client` is a test seam; when `None`, the adapter lazy-imports `anthropic` and
constructs `anthropic.Anthropic(api_key=api_key)` on first use (tests never need the SDK).

Shared request params (per the `claude-api` reference for Opus 4.8): `model="claude-opus-4-8"`,
`thinking={"type": "adaptive"}`, `output_config={"effort": "high"}`, **no** `temperature`/
`top_p`/`top_k`, modest `max_tokens` (1024 push / 2048 classify). The doctrine+rubric system
block carries `cache_control={"type": "ephemeral"}` (stable across the three calls).

- **`classify_intake(exp, opening)`** — system = `load_prompt("intake")` + rendered rubric
  (each frame: `frame_code`, `frame_detail`, `paired_trap`; each trap: `trap_code`,
  `trap_detail`; plus `mode`, `binding_constraint`); user = the opening. Calls
  `client.messages.parse(output_format=_IntakeWire, ...)`; converts the wire object into
  `IntakeClassification(frame_states={...}, trap_states={...})`. Any rubric code absent from
  the model's output defaults to `FrameState.absent` / `TrapState.not_tripped`.
- **`generate_push(exp, kind, code)`** — looks up the target's detail (`frame_detail` or
  `trap_detail`) by `code` in the rubric; system = `load_prompt("push")`; user = the experience
  prompt + that angle detail (the `code` itself is **never** sent in a way the model is asked
  to echo). Calls `client.messages.create(...)`; returns the first text block.
- **`classify_response(exp, kind, code, push, response)`** — system = `load_prompt("response")`
  + the target detail; user = the push + the student response; `client.messages.parse(
  output_format=ResponseClassification, ...)` → returns it directly (already flat).

**Refusal / empty:** if a parse yields no result or `stop_reason == "refusal"`, raise
`ModelError` (a new exception) — these are doctrine-critical calls; never silently default.

## 5. Wire schema (internal, not exported)
Anthropic strict structured outputs cannot express an open-keyed `dict[str, FrameState]`, so
intake uses a list-of-pairs shape with fixed item schemas:
```
class _FrameStateItem(BaseModel): code: str; state: FrameState
class _TrapStateItem(BaseModel):  code: str; state: TrapState
class _IntakeWire(BaseModel):     frames: list[_FrameStateItem]; traps: list[_TrapStateItem]
```
`ResponseClassification` is already flat (`outcome`/`mechanism_supplied`/`hard_wrong`) and is
the `output_format` directly.

## 6. Testing (`tests/test_anthropic_model.py`)
Inject a fake client via `AnthropicModel(client=fake)`. The fake exposes `.messages.parse(...)`
(returns an object with `.parsed_output` + `.stop_reason`) and `.messages.create(...)` (returns
an object with `.content=[text block]` + `.stop_reason`). Assert:
1. `classify_intake` maps the wire list into `frame_states`/`trap_states` dicts; a rubric code
   missing from the model output defaults to `absent` / `not_tripped`.
2. The system text sent to the client contains the disband-rule template **and** the rubric's
   frame details; the user contains the opening.
3. `generate_push` returns the model's text, and that text does not contain the `frame_code`.
4. `classify_response` parses `outcome`/`mechanism_supplied`/`hard_wrong`.
5. A refusal (`stop_reason="refusal"` / `parsed_output=None`) raises `ModelError`.

Plus `tests/test_live_model.py::test_live_intake` marked `@pytest.mark.live`, which **skips
unless `ANTHROPIC_API_KEY` is set**, constructs a real `AnthropicModel`, runs `classify_intake`
on the fixed experience, and asserts a well-formed `IntakeClassification` over the rubric codes.
Register the `live` marker in `pyproject.toml` (`[tool.pytest.ini_options] markers`).

## 7. Acceptance
- New unit tests pass; the full suite stays green (28 existing + new).
- The live test skips cleanly with no key (and, given a key, passes a real Opus 4.8 call).
- `ruff check` / `ruff format` clean.

## 8. Guardrails (must not contradict)
- Doctrine lives in `content/prompts/`, never as literals in `src/`.
- The push never emits the `frame_code` (asserted in tests).
- Only frame/trap deltas + mechanism + hard-wrong are returned; the conclusion is never graded.
- No sampling params; `model="claude-opus-4-8"`; adaptive thinking + `effort="high"`.
