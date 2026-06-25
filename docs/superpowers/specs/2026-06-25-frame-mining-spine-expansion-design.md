# Frame Mining — Spine Expansion via Mined, Lift-Tested Frames

Date: 2026-06-25
Status: design — umbrella architecture + §4 pins **Sub-project 1 (the blind-lift harness)** plan-ready
Origin: the post-P3 content thread (memory `retnovation-project`, `retnovation-case-library-idea`). With the
diagnostic-progression engine landed through all three projects, the real unlock is content. The user's
direction: **expand the founder spine vocabulary** — and, against the doctrine that the frame library is
deliberately small + counter-intuitive, the doctrine-faithful reading is to **mine new spine frames** and
validate each against the `marginal_lift` bar (decided in a brainstorming pass + one external design review).

## 1. Goal

Expand the founder-CEO spine by **mining new counter-intuitive frames** — reasoning moves where the base
Opus is *wrong by default* — from real decision records, **validating each against `marginal_lift`** via an
automated **blind-lift screen** plus human adjudication, then **authoring isolated + cross-problem
experiences** so the value-function engine can locate each new frame (fire transfer, reach `strong`, enable
a series-dogfood). The mine is **source-agnostic**: Veldra's owned decision record now, public cases
(books, blogs, speeches, documentaries, biographies, interviews) later.

## 2. Doctrine constraints this must honor

From `Retnovation_FounderCEO_Design_v0.1.md` (§4–§9), the lift series `EXP-001/002/003`, and
`Retnovation_Complete_Picture.md` (§4, §10–§12):

- **The frame library is small and counter-intuitive, not a comprehensive mine.** Most founder moves the
  base model already performs (EXP-001 `choose_the_failure_default_deliberately` = no lift). A frame earns
  **spine** status only where the model is wrong by default — too abstract or too cautious (EXP-002
  `lead_with_what_you_refuse_to_do` = lift). Frames that don't lift are **assessment-only**, not spine.
- **`marginal_lift` = necessity, not preference.** The test is whether the output **degrades** when the
  frame is removed — blind, framed-vs-(frame-naive)-control, ≥2 **unlabeled** scenarios, an **unprimed**
  rater judging distinguishability + signed preference with **randomized A/B order**, free to call a tie.
- **Two axes, not one.** The rater measures **distinguishability (0–3)** and **signed preference (−2..+2)**
  separately. A *negative-lift* frame (distinguishable **and** dispreferred — the model expresses it
  clearly and is worse for it) is the opposite fact from a *null* frame (not distinguishable — the model
  can't see it) — distinct verdicts the screen must keep apart. The **depreciation clock** is a *separate,
  later* concern: it re-tests *already-admitted* frames over time and reads off **lift decaying to null**
  (necessity gone as the model improves, Complete Picture §4); it does **not** read off a *candidate's*
  negative result. The verdict must carry both axes; `lift` is a derived view.
- **Growth goes down.** The spine stays small and changes slowly; nuance accretes as **subframes** under
  stable parents. A new top-level frame clears the v0.2 admission gate (7 hard gates) + a **promotion
  track** (provisional on one posture/case → durable on a second).
- **Mine, don't invent** — take a real decision, strip its label, lift the tool that applies.
  **Source-agnostic, provenance source-typed:** `owned` (Veldra — `POSITIONING.md`/`BIZLOG.md`/`EXECLOG.md`/
  ADRs, confidential) now; `public` (citable) later. The owned→public arc is also the promotion track's
  second-case engine.
- **Heavy governance is deferred** (the 50-fake certification panel, deprecation lifecycle): the MVP runs on
  **directional validation**. Build only the small machinery that compounds.
- **Rent capability, gate doctrine.** The harness rents Opus for generation + rating; doctrine (the rater
  rules, the scenario bank, the thresholds) lives in `content/`. Testable with a scripted fake model;
  confidentiality (`data/` + the EXP/scenario material) never tracked. No `Co-Authored-By`.

## 3. Decomposition — three sub-projects (build #1 first)

1. **The blind-lift harness** (this spec, §4) — the reusable `marginal_lift` screen. Foundational
   (sub-project 2 needs it) and independently validatable (it must reproduce the documented EXP verdicts).
2. **Mine + admit the first spine frame(s)** — read the ore to surface ~3–6 candidates, run the harness as
   the auto-screen, apply the rest of the v0.2 gate (surface-independence, atomicity,
   orthogonality-with-separating-artifact, falsifiable-application), human adjudicates survivors; admitted
   frames enter the library as **provisional** spine with source-typed provenance.
3. **Author isolated + cross-problem experiences** for the admitted frames — single-frame experiences
   (clearing the ≥8-angle gate via ~3 traps) on ≥2 owned problems, so the engine locates them. The
   engine-lighting payoff.

This spec captures the umbrella; **writing-plans produces the Sub-project 1 plan only.** Sub-projects 2–3
get their own plan cycles (re-entering brainstorming where their details need refining).

## 4. Sub-project 1 scope detail (plan-ready) — the blind-lift harness

The harness runs `marginal_lift` for one candidate frame and returns a result that **automates the kill,
not the verdict**: it surfaces the verbatim outputs + the rater's named differences so the human adjudicates
survivors. Decided in brainstorming + two external reviews — which set the two-axis result type, made the
manipulation check a gating precondition via a **separate primed** checker, named the same-model bias as
directional → false positives, and (second pass) pinned the verdict truth table, the pydantic wire shapes,
the refusal-as-signal capture, the tie cell, and the scenario-bank confidentiality fix.

### 4.1 Types (both axes raw; `status`/`verdict`/`screen_action` are **derived**, never stored)

- `CandidateFrame`: `frame_code: str`, `frame_detail: str`, `injection: str` (the verbatim one-line frame
  statement injected into the framed condition). `frame_detail` is carried for SP2/3; the screen never reads
  it.
- `LiftScenario`: `scenario_id: str`, `prompt: str` (an **unlabeled** generation task), `posture: str`
  (carried for SP2; not read by the screen).
- **Wire models** (pydantic, returned via `messages.parse` + `_require`, mirroring `_IntakeWire` —
  doctrine-critical calls never silently default):
  - `PreferenceRating`: `distinguishability: int (0–3)`, `preferred: Literal["A","B","tie"]`,
    `magnitude: int (0–2)` (preference strength; 0 iff `tie`), `key_difference: str`.
  - `InjectionExpressed`: `expressed: bool`, `evidence: str` (a quoted span / named location where the move
    appears — load-bearing, not a bare yes; see the checker-bias note in §4.5).
- `ScenarioVerdict` (one per scenario). **Stored** (raw): `scenario_id`, `injection_expressed: bool` (the
  **only** stored bool), `distinguishability: int (0–3)`, `preference: int (−2..+2)` (signed toward
  **framed** after un-randomization; `0` = tie), `key_difference: str`, `framed_output: str`,
  `control_output: str`, `framed_refused: bool`, `control_refused: bool`. **Derived** `status` (computed,
  per the `Proposal`/`@property` precedent in types.py):
  - `inconclusive` — not `injection_expressed`.
  - `null` — expressed, `distinguishability == 0` (the model can't see it).
  - `neutral` — `distinguishability ≥ θ_dist` and `preference == 0` (a tie).
  - `lift` — `distinguishability ≥ θ_dist` and `preference > 0`.
  - `negative` — `distinguishability ≥ θ_dist` and `preference < 0` (the model is *worse* with the frame).
  - `θ_dist` is a config tie-band floor (default `1`) so "technically distinguishable but a wash" isn't
    forced into `lift`/`negative`.
- `LiftResult`: `frame_code`, `scenarios: list[ScenarioVerdict]`, and **derived aggregate views over the
  valid (`injection_expressed`) scenarios only** — `inconclusive_count`, `framed_preferred_count`
  (`preference > 0`, **excludes ties**), `mean_preference`, `mean_distinguishability`, a derived `verdict`
  (truth table, §4.5), and a derived `screen_action` ∈ {`surface`, `auto_kill`} (§4.5). **No stored `lift`
  bool** — a bool is a schema break once the validation test pins the shape.

### 4.2 Module map (rent-Opus / gate-doctrine, fits the existing architecture)

- `src/retnovation/lift_test.py` — `run_lift_test(candidate, scenarios, model, order, config) -> LiftResult`.
- `types.py` — the types above (`CandidateFrame`, `LiftScenario`, `PreferenceRating`, `InjectionExpressed`,
  `ScenarioVerdict`, `LiftResult`).
- `model.py` — three **additive** `Model` methods (impl in `AnthropicModel`; scripted in `FakeModel`):
  - `generate_output(scenario_prompt, injection: str | None) -> str` — framed if `injection` given, else
    control. Uses `_PARAMS` (adaptive thinking + high effort, like the other calls — "default sampling" is
    not a thing on Opus 4.8) via the `create` idiom. **Captures a refusal as its returned text and does NOT
    raise** — a *deliberate divergence* from `generate_push` (which raises, model.py:222), because a
    *control refusal is signal* (EXP-002 B2: the bare model refused, the frame converted it → that
    refusal-vs-not IS the lift). Sets `*_refused` on the verdict for the human surface.
  - `rate_preference(scenario_prompt, output_a, output_b) -> PreferenceRating` — **unprimed** (no frame
    text), `messages.parse` + `_require`.
  - `check_injection_expressed(injection, framed_output) -> InjectionExpressed` — **primed** with the
    injection, `messages.parse` + `_require`; kept separate from the blind rater to preserve blindness.
- `content/prompts/lift_rate.md` — unprimed preference rater (never names the frame / which output is framed;
  may call a tie).
- `content/prompts/lift_manipulation.md` — primed checker; **must cite evidence** (the span where the move
  appears), so a false-pass is harder.
- `content/lift/scenarios.example.yaml` — **committable** structural stub (the schema); the real bank
  `content/lift/scenarios.yaml` is **gitignored** (§4.7).
- `FakeModel` extension (the green tests ride on this): `generate_output` scripted by
  `(scenario_id, is_framed)`; `rate_preference` + `check_injection_expressed` scripted by `scenario_id`,
  each popping a scripted value per call (mirrors the existing `dict[code] -> list .pop(0)` convention,
  model.py:57-101).

### 4.3 Data flow

```
candidate frame + scenarios + order
  └─ per scenario:
       control_output  = generate_output(prompt, injection=None)          # refusal CAPTURED, not raised
       framed_output   = generate_output(prompt, injection=candidate.injection)
       ie              = check_injection_expressed(candidate.injection, framed_output)   # PRIMED gate
       if not ie.expressed: ScenarioVerdict(status=inconclusive)          # EXCLUDED from aggregation; surfaced
       else:
         (a, b)     = randomize(framed_output, control_output, order[scenario_id])   # order ∈ {"AB","BA"}
         pr         = rate_preference(prompt, a, b)                                   # UNPRIMED; may tie
         preference = un_randomize(pr.preferred, pr.magnitude, order[scenario_id])    # signed→framed; tie→0
         ScenarioVerdict(injection_expressed=True, distinguishability=pr.distinguishability,
                         preference, key_difference=pr.key_difference, outputs…, *_refused…)
  └─ aggregate over VALID scenarios → LiftResult (derived verdict + screen_action; §4.5)
```

### 4.4 Reproducibility & blindness

- **Injected A/B order** per scenario, typed `Literal["AB","BA"]` (`"AB"` = framed is `output_a`).
  `randomize(framed, control, order)` and `un_randomize(preferred, magnitude, order)` are **pure inverses**
  with one explicit sign convention — `un_randomize` maps `preferred`∈{A,B,tie} back to an integer signed
  **toward framed** (`tie → 0`). A sign error here silently inverts every preference, so §4.6 asserts the
  round-trip directly.
- **Preference rater unprimed** (no frame). **Manipulation check is a separate primed call** — it needs the
  injection to verify expression, so it can't be folded into the blind rater.

### 4.5 Aggregation: the verdict truth table, the screen action, the two same-model biases

**`verdict`** — derived by **precedence** over the **valid**-scenario `status` set (total — every case maps,
top-down, first match wins):
1. no valid scenarios → **`inconclusive`** (injection never landed — re-author it, not no-lift).
2. **all** valid are `lift` → **`lift`** (unanimous; e.g. EXP-002 2-of-2).
3. ≥1 `lift` but not all → **`mixed`** (some lift, some not; e.g. EXP-003's 1-of-2 — always surfaces).
4. (no `lift`) ≥1 `negative` → **`negative_lift`**.
5. (no `lift`/`negative`) ≥1 `neutral` → **`neutral`**.
6. else (all `null`) → **`null`**.

**`screen_action`** (automate only the unambiguous kill): `auto_kill` iff **≥1 valid scenario AND** the
verdict ∈ {`null`, `negative_lift`}. Everything else (`lift`, `mixed`, `neutral`, `inconclusive`) →
`surface`. An all-inconclusive run is never `auto_kill` (the vacuous-truth guard).

**Two directional same-model biases, both pointed at by the human review:**
1. `rate_preference` (one Opus rating two Opus outputs) skews **toward stylistically congenial framed
   outputs → inflated preference → false positives.** Mitigation: positives `surface`; the human
   **adjudicates preference** on survivors, not just confirms kills (preference is the inflated axis).
2. `check_injection_expressed` (same model, primed) skews toward **false-pass** (claiming a weak move is
   expressed) — which would let a null injection through as a real read. Mitigation: the checker **must cite
   evidence** (a quoted span); the human spot-checks `injection_expressed` against the verbatim framed
   output.

**Scenario count:** `min_scenarios` is config (default **3** for real mining), enforced as an **advisory
floor recorded on `LiftResult`**, not a hard reject — so the EXP-reproduction validation runs at the
documented **n = 2** without tripping it.

### 4.6 Validation (reproduces the documented EXP verdicts; n = 2)

- **Green (CI, scripted `FakeModel`):**
  - `lead_with_what_you_refuse_to_do` (EXP-002, 2/2): both scenarios distinguishable + framed-preferred —
    one via a **control refusal** the frame converts (B2) → assert `verdict == lift` **and** that the
    control refusal was captured (not raised).
  - `choose_the_failure_default_deliberately` (EXP-001, 0/2): both scenarios distinguishable (`dist 1`) +
    dispreferred → `status == negative` each → assert `verdict == negative_lift`. This is the documented
    "true null **of value**" — the frame *landed* but lost; it is the spec's `negative` cell, **not** the
    dist-0 `null` cell. (Deterministic from the scripted axes — no OR-hedge.)
  - **partial (EXP-003 shape):** one `lift` + one `neutral` (tie) → `verdict == mixed`, `screen_action ==
    surface`. Pins `mixed` and the tie cell.
  - **manipulation gate:** a scenario scripted `injection_expressed == False` → `status == inconclusive`,
    excluded; a frame whose injection lands on no scenario → `verdict == inconclusive` (not `null`/no-lift).
  - **null vs negative:** a `distinguishability == 0` scenario → `null`; a `dist ≥ θ_dist`, `pref < 0`
    scenario → `negative` (the two cells stay distinct).
  - **un-randomize round-trip:** a known-asymmetric pair (framed clearly stronger), framed placed as **B**
    (`order == "BA"`) → assert `preference` attributes to **framed** (positive), catching a sign flip.
- **Live (`@pytest.mark.live`, real Opus):** reproduces `choose` → not-lift, `lead` → `lift` directionally;
  self-skips without a key.

### 4.7 Config, confidentiality, scope

- **Config (`content/lift/`, doctrine-as-data, L-1):** `min_scenarios` (default 3), `θ_dist` (default 1),
  the verdict/screen thresholds. Versioned content.
- **Confidentiality (a real leak path — the fix is a required plan task).** Today `content/lift/` is **not**
  gitignored (`git check-ignore content/lift/scenarios.yaml` → not ignored) and the lessons.md
  confidential-docs grep (lessons.md:6) doesn't cover it. SP1 **must**: (a) add a scoped `.gitignore` line
  for the real bank — `/content/lift/scenarios.yaml` — while **committing** `scenarios.example.yaml` (the
  `.env`/`.env.example` pattern); (b) extend the lessons.md grep to include `lift.*scenario`. `LiftResult`
  logs (verbatim Veldra-derived generations) write to `data/lift/`, which **is** already gitignored
  (`/data/`). The green tests use the scripted fake (no real scenarios) → **CI stays clean**.
- **EXP-003 grounding caveat:** a low preference on a *concrete-specifics* injection may be a
  grounding/attribution artifact (true specifics read as fabricated — EXP-003 §4/§6), not a real no-lift —
  so such a result **surfaces** for human review, never auto-kills.
- **Out of scope (later / deferred):** the other v0.2 admission gates + mining + admission (SP2); authoring
  isolated experiences (SP3); heavy governance (the 50-fake panel, deprecation lifecycle, automated
  promotion track). The **depreciation clock** (re-testing *admitted* frames over time for lift decay) is
  SP2+/operational, not the harness.

**Status: umbrella pinned; Sub-project 1 (the blind-lift harness) plan-ready — revised after a five-lens
adversarial review (the "EXP-001 is a null" headline was refuted on verification: EXP-001 is `negative` —
distinguishable + dispreferred — not the dist-0 `null` cell). Awaiting user review before writing-plans.**
