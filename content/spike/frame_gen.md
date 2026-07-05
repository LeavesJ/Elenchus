You are given a real decision someone is facing. Produce candidate DECISION FRAMES — the hidden
judgment MOVES that separate a sharp decision here from a naive-but-smart one.

A real frame is a NON-OBVIOUS move a capable person routinely MISSES: a specific reframing, a
hidden cost, an asymmetry, a second-order consequence, a thing you must decide BEFORE the obvious
question. It is not a topic, not a category, not advice, not a checklist.

FORBIDDEN (these are mush, never emit them):
- Generic advice ("know your customers", "focus on value", "weigh the trade-offs").
- Recognize-the-type-and-run-a-procedure ("this is a pricing decision, use value-based pricing").
- Homework in a costume: a real-sounding label with no actual hidden move behind it.

For EACH candidate frame return:
- `frame_code`: a short snake_case slug.
- `frame_detail`: the hidden move stated as a sharp principle, in one or two sentences — the thing
  a naive-but-smart person misses.
- `injection`: the same move phrased as REASONING GUIDANCE — a short instruction that, given to
  someone reasoning about this decision, would make them apply the move.

Return 4 candidate frames, each a genuinely DIFFERENT move (not restatements of one another).

Here are examples of the STANDARD (real frames from a curated library) — match this depth, do not
copy them:
{exemplars}
