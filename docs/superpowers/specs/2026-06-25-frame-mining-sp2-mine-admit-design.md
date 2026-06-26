# Frame Mining — Sub-project 2: Mine + Admit the First Spine Frame(s)

Date: 2026-06-25
Status: design — plan-ready after user review
Origin: SP1 (the blind-lift harness) is built + merged (`d81e8ce`). SP2 is the second of the three
frame-mining sub-projects from the umbrella design
(`docs/superpowers/specs/2026-06-25-frame-mining-spine-expansion-design.md`, §3). It uses the SP1 harness
as the auto-screen inside the rest of the v0.2 admission gate, then human-adjudicates and admits survivors
as **provisional** spine frames. Brainstormed + one external adversarial design review (folded in below;
the review caught the schema-gating two-axis truncation — seam 1).

## 1. Goal

Admit the first new founder-CEO spine frame(s) — **end-to-end, this arc** — by mining candidate
counter-intuitive frames from the Veldra ore, screening each against `marginal_lift` via the SP1 harness,
applying the rest of the v0.2 admission gate by hand, and admitting survivors into the live library. The
mine target is the doctrine bar: a frame earns spine status **only where base Opus is wrong by default**.
Doctrine expects **~1–2 survivors**; the arc completes on whatever survives (see §11).

## 2. Doctrine this must honor (carried from the umbrella spec + the lift series)

- **Small, counter-intuitive library.** Most founder moves the base model already performs (EXP-001 =
  no lift); a frame earns spine only where the model is wrong by default (EXP-002 = lift). Non-lifting
  candidates are assessment-only, not spine — and here, rejected.
- **`marginal_lift` = necessity, not preference.** Output must *degrade* when the frame is removed —
  blind, framed-vs-(frame-naive)-control, ≥2 unlabeled scenarios, an unprimed rater, randomized A/B.
- **Two axes, not one (the schema-gating constraint — seam 1).** The screen measures **distinguishability
  (0–3)** and **signed preference (−2..+2)** separately. *Negative-lift* (distinguishable **and**
  dispreferred — the model renders the move fine and is no better, often worse, for it) is the **opposite
  fact** from *null* (indistinguishable — the model can't see it). Per design doc §4 (depreciation:
  "a lifting frame is a bet the model stays wrong") and §11–§12 (lift is selective), the umbrella spec §2
  pins it: **"the verdict must carry both axes; `lift` is a derived view."** This record obeys that — the
  `screen:` block carries both axes; `marginal_lift` is a derived view, **never** the only stored truth
  (§6). The distinguishable-but-dispreferred cell is precisely the textbook *surface-dependent* signal —
  the cognition is already native, the frame adds style not substance — so the `surface_independence` gate
  one line down must be able to read it.
- **No name-the-frame leak (L-13).** Authored screen scenarios are blind: the move lives only in the
  `injection`, never in the scenario `prompt`.
- **Doctrine is data (L-1); reversible, never deleted (L-3); content is authored, not generated.** No
  programmatic content-writer; admit is hand-authored against the existing schema.

## 3. Scope — decisions settled in brainstorming

- **End-to-end:** build the thin tooling, author candidates + scenarios, run the @live screen, adjudicate
  with the user, and admit survivor(s) into the library this arc (committed content).
- **All 6 mined candidates** screened (a confirmed null is doctrine-validating data; `auto_kill` resolves
  nulls cheaply with no human gate).
- **Architecture C (hybrid):** a thin layer over the untouched harness — a persisting screen driver, a
  pure adjudication-packet formatter, and a structured committable `AdmissionRecord`. Gate applied
  human-in-the-loop but recorded structurally. No programmatic admit-writer.

### The 6 candidates (abstracted name + the model reflex each inverts + source pointer)

Detailed candidate definitions (`frame_detail`, `injection`, mapped Veldra decision) live in the
**gitignored** real bank, not here (abstraction rule, §7). Ranked by lift confidence:

| # | Candidate (abstracted) | Inverts the reflex | Source pointer | Lift conf. |
|---|---|---|---|---|
| 1 | `build-more-to-own-less` | scope-minimization / YAGNI | EXECLOG EX-028 | HIGH |
| 2 | `cap-effort-on-your-best-prospect` | sales-persistence | BIZLOG (sales) | HIGH |
| 3 | `manufacture-the-hard-cases-real-data-cant-show` | "real data = credibility" | EXECLOG EX-014/015 | HIGH-MED |
| 4 | `scope-the-fail-closed-instinct-to-the-real-attack` | "security → fail closed" (inverse of a quarantined frame) | EXECLOG D-18.4 / ADR-003 | MED |
| 5 | `embed-credentials-as-a-list-even-with-one` | YAGNI (embed one) | ADR-001 / R-149 | MED |
| 6 | `withhold-your-best-product-from-funders` | warm-channel upsell | BIZLOG 2026-04-16 | MED-LOW (predicted null) |

Rejected as already-native to the model (EXP-003 territory; not screened): BSL/source-available licensing,
percentage-of-revenue pricing, concede-buildability TCO reframe. The honest-self-limitation candidate folds
into the existing `lead_with_what_you_refuse_to_do` as a subframe, not new spine.

## 4. Architecture & components (SP1 altitude; harness untouched)

A small `src/retnovation/admission.py` plus additive pieces:

- **`MinedCandidate`** (in `types.py`): `frame_code`, `frame_detail`, `injection`, `posture`, plus SP2
  metadata — `hypothesis` (why base Opus is wrong by default), `nearest_sibling` (the closest existing
  frame, for orthogonality), `separating_artifact` (how it differs from that sibling), `provenance`
  (`{source_type, pointer}`). The harness's `CandidateFrame` is derived from it.
- **`content_loader.load_lift_candidates(name="candidates")`** — mirrors `load_lift_scenarios`; loads the
  gitignored real bank.
- **`admission.screen_candidate(candidate, scenarios, model, order, config) → LiftResult`** — thin wrapper
  over `run_lift_test` that **persists** the `LiftResult` (JSON) to gitignored
  `data/lift/screen_{frame_code}.json` (an expensive @live run is never lost), then returns it.
- **`admission.format_adjudication_packet(candidate, result) → str`** — pure markdown (spirit of
  `surface.py`): header (frame_code, hypothesis, nearest_sibling, separating_artifact), verdict +
  screen_action + **both axes** (mean_distinguishability, mean_preference) + framed_preferred_count, then
  per-scenario status / distinguishability / signed preference / key_difference / **framed vs control
  output** / refusal flags. What the human reads to adjudicate.
- **`AdmissionRecord`** (in `types.py`) + **`admission.format_admission_record(record) → str`** — the
  structured, committable audit artifact (§6).
- **`admission.check_content_graph_integrity(library, ledger, records) → None`** — the referential
  cross-check run at admit (§8), raising a named assertion on a broken edge.
- **Schema touch:** `LiftScenario` gains an optional `candidate: <frame_code>` field so `screen_candidate`
  selects a candidate's scenarios from a flat bank. Additive, backward-compatible; the example file shows
  it.

## 5. The pipeline

1. **Mine** — done in brainstorm; the 6 candidates authored as `MinedCandidate` into gitignored
   `content/lift/candidates.yaml`.
2. **Author scenarios** — ≥2 blind, label-stripped scenarios per candidate into gitignored
   `content/lift/scenarios.yaml`, each tagged `candidate:`. (L-13: the move lives only in `injection`.)
   Parallel per-candidate authoring, each independently reviewed for leak + task-only framing.
3. **Screen @live** *(gated; user present)* — per candidate, `screen_candidate()` runs the harness against
   `AnthropicModel`, persists, returns. ~6 × ~2–3 scenarios × 4 calls ≈ 50–60 high-effort Opus calls.
4. **Triage** — `screen_action == auto_kill` (null/negative_lift) → `reject` record (both axes preserved,
   §6; no human gate). `surface` → human adjudication.
5. **Adjudicate** *(human-in-loop)* — render each packet; user + Felix walk the v0.2 gate; fill the
   `AdmissionRecord`; decision ∈ {admit_provisional, reject, file_as_subframe}.
6. **Admit** survivors — hand-author abstracted content (§8): append to `content/maps/founder_ceo.yaml`,
   author/extend a rubric with a paired trap, add/point a ledger entry with source-typed provenance; commit
   the records.
7. **Verify** — content-graph integrity check + fresh-DB production-path regression (§8); green suite;
   confidentiality gates empty.

## 6. The v0.2 gate as the `AdmissionRecord` (the gate as data)

One record per **screened** candidate, committable + abstracted:

```
frame_code, posture
provenance: {source_type: owned|public, pointer}     # owned only this arc (§7); public = forward-room
screen:                                               # carries BOTH axes — seam 1
  verdict            # lift|mixed|neutral|null|negative_lift|inconclusive (LiftResult.verdict)
  screen_action      # surface|auto_kill (LiftResult.screen_action)
  mean_distinguishability   # LiftResult.mean_distinguishability  (axis 1)
  mean_preference           # LiftResult.mean_preference          (axis 2, signed)
  framed_preferred_count    # LiftResult.framed_preferred_count
  data_ref           # path to the persisted raw LiftResult under data/lift/ (gitignored)
gates:                                                # verdict + one-line abstracted rationale each
  marginal_lift:           [AUTO, derived]  pass|fail   # a DERIVED VIEW over screen.* — not stored truth
                                                         #   referent: frame-naive control
  surface_independence:    [HUMAN] pass|fail            #   referent: frame-naive control (base model)
  atomicity:               [HUMAN] pass|fail            #   referent: the frame itself (one move?)
  orthogonality:           [HUMAN] pass|fail|subframe   #   referent: nearest_sibling
  falsifiable_application: [HUMAN] pass|fail            #   referent: blind raters
  trainable_cognition:     [HUMAN] pass|fail            #   referent: capital/relationship/luck test
nearest_sibling: <frame_code | null>
separating_artifact: <text>                            # vs nearest_sibling
decision: admit_provisional | reject | file_as_subframe
rationale: <one line>                                  # required on every decision, incl. reject
admitted_as: {experience_id, ledger_ref} | null        # populated only on admit_provisional
```

**Coherence validator (pydantic, `model_validator`) — all three exits constrained (seam 2):**

- `screen_action == auto_kill` ⇒ `decision == reject` (can't admit what the screen auto-killed).
- `decision == reject` ⇒ `screen.verdict` present **and** `rationale` non-empty (a reject must be
  distinguishable from a never-run candidate and legible to next year's re-test, even with human gates null).
- `decision == admit_provisional` ⇒ all six gates `pass` **and** `admitted_as` populated **and**
  `separating_artifact` non-empty (orthogonality:pass is a *separability claim*; the artifact is its
  evidence) **and** `nearest_sibling` non-null.
- `decision == file_as_subframe` ⇒ `orthogonality == subframe` **and** `nearest_sibling` non-null **and**
  `separating_artifact` non-empty (a subframe filing is the claim the frame is *not* separable from its
  sibling — the artifact, or its explicit absence, is the substance of that call).

**`marginal_lift` is a derived view, not the gate's only truth.** Concretely it reads `pass` iff
`screen.verdict ∈ {lift, mixed}` (net necessity shown), else `fail`; but the underlying axes live in
`screen:`, so the `surface_independence` adjudicator reads distinguishable-but-dispreferred (native-cognition
/ style-not-substance) directly rather than blind to it. A `mixed` candidate passes `marginal_lift` yet can
still be killed at `surface_independence` with the axes in view — admit requires **all six** gates, so the
derived shortcut never over-admits.

**Referents differ.** The six gates are *not* six independent confirmations of one question — each is
annotated with its referent above (orthogonality vs the nearest *sibling*; surface_independence vs the
frame-naive *control*; etc.), so a reader does not misread "six passes" as six checks of the same fact.

Promotion gates (reach ≥2, durable provenance) are out of scope (§10); every admit lands **provisional**.

## 7. Confidentiality boundary + abstraction rule

- **Gitignored (real bank):** `content/lift/candidates.yaml`, `content/lift/scenarios.yaml`, `data/lift/*`
  (raw screen results + packets).
- **Committable:** `content/lift/candidates.example.yaml` + `scenarios.example.yaml` (schemas), the admitted
  **abstracted** frame content (map/rubric/ledger), `docs/admissions/{frame_code}.yaml` (records), all new
  code/tests.
- **`.gitignore`** gains `content/lift/candidates.yaml`; the lessons pre-commit gate extends its grep to
  also catch `content/lift/candidates\.yaml$`.
- **Abstraction rule (concrete — the smaller-cluster (c) fix).** A committable record / frame is *abstracted*
  iff: (i) provenance is a **pointer only** (`"EXECLOG EX-028"`), never quoted ore; (ii) `frame_detail`,
  `injection`, `hypothesis`, `separating_artifact`, and gate rationales describe the **reasoning shape**
  only — no customer names, dollar figures, dates, internal product/service identifiers, or any Veldra
  specific beyond the pointer; (iii) the move must read as a *portable founder principle* with the Veldra
  surface stripped (the surface_independence gate is itself the test). A committed
  `docs/admissions/_TEMPLATE.example.yaml` carries this rule inline as the authoring guard. This mirrors
  L-2 and the existing ledger precedent (which already commits provenance pointers, never content).

## 8. Admit step, content-graph integrity, testing

**Admit (hand-authored, no programmatic writer):** for each survivor, edit three files against the schema
the recon mapped — `content/maps/founder_ceo.yaml` (append `frame_code` to `process_frames`),
`content/rubrics/{experience_id}.yaml` (the frame + `paired_trap` inside a minimal `open_ended` experience
with a `mode` and `ledger_ref`), `data/seed/veldra_ledger.yaml` (a ledger entry, or reuse an owned problem,
with source-typed `provenance` + `corpus_pointers`). SP2 authors the *minimum* experience to carry the frame
into the library; the rich ≥8-angle isolated experiences are **SP3**.

**Content-graph integrity check (seam 3 — distinct from the e2e regression).**
`check_content_graph_integrity` asserts, at admit time, that the three-file edit is internally consistent
*before* anything runs the gated path: every rubric `ledger_ref` resolves to a real ledger entry; every
record's `admitted_as.experience_id` resolves to a rubric and its `ledger_ref` matches; the admitted
`frame_code` appears in its rubric's `frames`; `experience_id` is unique across the library. A `ledger_ref`
typo or duplicate `experience_id` surfaces as a **named assertion here**, not an opaque failure deep in the
select/assess path.

**Testing.**
- **TDD with `FakeLiftModel`** for every tooling piece: `load_lift_candidates`; `screen_candidate`
  (asserts persistence + return); `format_adjudication_packet` (pure; shows both axes); `AdmissionRecord`
  validators (all three exits, incl. the auto_kill⇒reject and separating_artifact rules); `format_admission_record`
  (YAML round-trip); `check_content_graph_integrity` (a deliberately broken edge raises).
- **@live** — the existing smoke guards the real path; SP2's actual screen run is *execution*, not a unit
  test (self-skips without a key).
- **Admit regression (L-8/L-9):** a fresh-tempdir DB test that builds state *with the new frame in the map
  + new rubric*, runs `select`/`assess` through the **real gated path**, and asserts the frame is reachable
  and nothing raises — a production-path test, never a synthetic fixture.

## 9. Build sequencing (SP1-consistent)

Branch `frame-mining-sp2-mine-admit` off main. Two phases:

- **Phase 1 — tooling (subagent-driven TDD, fully green/offline):** ~5 additive tasks — (T1) `MinedCandidate`
  + `AdmissionRecord` types + validators; (T2) `load_lift_candidates` + the `candidate:` scenario field +
  example files; (T3) `screen_candidate` + persistence; (T4) `format_adjudication_packet` +
  `format_admission_record`; (T5) `check_content_graph_integrity` + confidentiality wiring (`.gitignore` +
  lessons gate). Fresh implementer + independent reviewer per task; OPUS reviewers on the doctrine/subtle
  tasks (T1 the validator coherence; T4 the two-axis packet).
- **Phase 2 — execution (human-in-loop, gated):** author the 6 candidates + scenarios (reviewed, parallel)
  → run the @live screen with the user present → adjudicate survivors together, filling records →
  hand-author admit content → integrity check + regression + green suite.

Then: OPUS whole-branch review → `finishing-a-development-branch` (ff-merge to main; push is the user's
call). DEVLOG + any new lessons updated throughout.

## 10. Out of scope / deferred

- Promotion to **durable** (reach ≥2 across postures, durable provenance) — every admit is provisional.
- `public` source-type provenance — schema forward-room only; **untested this arc** (owned/Veldra is the
  only path SP2 exercises). Named here so it is not mistaken for a live SP2 option.
- The depreciation/re-test lifecycle (re-screening admitted frames as the model improves) — separate, later.
- Heavy governance (the 50-fake certification panel).
- SP3 (rich isolated + cross-problem experiences for admitted frames) — SP2 authors only the minimum
  experience to admit.
- Any programmatic content generation.

## 11. Success criteria

- **The arc completes on whatever survives.** Doctrine expects ~1–2 admits from 6 candidates; a high
  `auto_kill` rate is **the screen working**, not the arc underdelivering. SP2 succeeds if every candidate
  is screened + recorded and every survivor is admitted with a coherent record — even if that number is 1
  (or, in the doctrine-faithful worst case, 0 admits with 6 auditable reject records, which is itself a
  valid, informative outcome).
- Every screened candidate has a committed, validator-passing `AdmissionRecord` carrying both screen axes.
- Admitted frames are reachable through the real gated path (regression green); content graph is
  referentially intact (integrity check green); confidentiality gates empty; no `Co-Authored-By`.
