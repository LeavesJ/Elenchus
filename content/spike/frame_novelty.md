You are given a candidate decision-MOVE and a numbered list of existing curated moves. Your job is to
judge whether the candidate makes the same underlying judgment move as its nearest curated
counterpart, or a genuinely different one — and how sure you are of that call.

Judge the MOVE, not the surface topic. Two moves about pricing can be different moves; a move about
pricing and a move about hiring can be the same move. A candidate that merely applies an existing
move to a new subject is a restatement, not a new move.

The same-move test. Two moves are the SAME move when applying one, correctly, already makes a
reasoner perform the other — they share the operative judgment lever, differing only in subject or
wording. They are DIFFERENT when a reasoner could fully apply one and still MISS the other.
Procedure: (1) name the single nearest curated move and state the one judgment it forces; (2) state
the one judgment the candidate forces; (3) ask — does performing the nearest move already get you
the candidate's judgment? If yes, it restates; if you can construct a decision where the nearest
move is applied but the candidate's judgment is still missed, it is different.

Altitude. A curated PRINCIPLE applied to a specific situation is a RESTATEMENT if it forces nothing
the principle did not already force; it is DISTINCT only if the specific version adds a judgment the
general one omits.

The necessity bar (for a DISTINCT call). To call the candidate distinct you must name an operation
it adds that is necessary — the decision goes wrong without it — not merely an operation that is
present (any plausible frame has some nameable surface operation). Your distinctness claim must
survive the WHOLE curated list, not just the nearest: assert that no curated move performs the added
operation. If the candidate is only a topic-specialization of a curated move, it is NOT distinct.
When you cannot cleanly name a necessary added operation, answer confidence "low" — bias the
boundary toward the human.

Return:
- `nearest`: the frame_code (the bracketed code) of the SINGLE closest curated move. Always name one
  — even if it is far. Naming `nearest` is a REFERENCE ANCHOR for the reviewer, not a claim of
  similarity; similarity is judged only by `restates_nearest`. It is normal for `nearest` to be
  named AND `restates_nearest` to be false at high confidence.
- `restates_nearest`: true iff the candidate makes the SAME underlying judgment move as `nearest`
  (per the same-move test); false iff it makes a move `nearest` does not make.
- `confidence`: how sure you are of the `restates_nearest` call, in EITHER direction. Answer "high"
  when the candidate CLEARLY restates `nearest` OR when it CLEARLY makes a move `nearest` (and every
  curated move) does not make. Answer "low" ONLY when you genuinely cannot tell which — a true
  boundary case. Being sure it is DIFFERENT is a high-confidence answer, not a low one.
- `rationale`: the ONE distinguishing judgment, stated against `nearest` — never a paraphrase of the
  candidate's topic. If `restates_nearest=true`: name the shared judgment lever in `nearest`'s terms.
  If false: name the specific NECESSARY operation this move forces that `nearest` (and every curated
  move) does not. If `confidence=low`: name exactly what you cannot resolve — the specific ambiguity
  that keeps it a boundary case — so the human knows what to adjudicate.

Worked examples.

HIGH — restatement. Candidate: "Losing your biggest customer to a botched integration may be
unrecoverable; a slipped launch is almost always recoverable. Default to protecting against the
irreversible failure even at the cost of the reversible one." Nearest:
choose_the_failure_default_deliberately ("State which way it fails if you are wrong, and justify
defaulting to the reversible direction"). restates_nearest=true, confidence=high. Rationale: both
force the same lever — identify which way is irreversible and default to the reversible direction;
the candidate only names the subject (a customer vs a launch).

HIGH — distinct. Candidate: "An integration that exposes your data and know-how isn't distribution —
it's a paid training program teaching your only defensible advantage to the party best positioned to
replace you. Distinguish deals that rent your OUTPUT from deals that transfer your CAPABILITY."
Nearest: protect_the_core_lane. restates_nearest=false, confidence=high. Rationale: the necessary
added operation is classifying the counterparty relationship as capability-transfer vs
output-rental — without it you cannot see the deal is training your replacement. This survives the
WHOLE list: protect_the_core_lane keeps a promise intact but never asks what the deal transfers;
choose_the_failure_default_deliberately picks the reversible direction but does not classify what
capability leaves; embed_credentials_as_a_list provisions optionality but says nothing about
output-vs-capability; lead_with_what_you_refuse_to_do sets a boundary without diagnosing why this
deal is the boundary; commit_under_the_deadline forces a dated commitment but not the transfer
classification. No curated move forces it — that is what makes it distinct, not its distance from
nearest.

LOW — genuine boundary. Candidate: "Sequence your commitments so the reversible ones happen first
and the irreversible ones last, buying time to learn before you lock in." Nearest:
choose_the_failure_default_deliberately. restates_nearest — unclear; confidence=low. Rationale:
cannot cleanly separate whether "sequence irreversible-last" adds a necessary new judgment or is just
the conjunction of choose_the_failure_default_deliberately (favor the reversible direction) and
embed_credentials_as_a_list (provision cheap optionality now). If the sequencing forces nothing those
two don't already force, it is a restatement of their conjunction; that is the ambiguity to
adjudicate.
