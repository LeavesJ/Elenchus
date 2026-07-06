You are given a candidate decision-MOVE and a list of existing curated moves. Decide whether the
candidate RESTATES one of the existing moves (the same underlying judgment move under different
words) or is a genuinely DIFFERENT move.

Judge on the MOVE, not the surface topic: two moves about pricing can be different moves, and a
move about pricing and a move about hiring can be the SAME move. A candidate that merely applies an
existing move to a new subject is a restatement, not a new move.

Return:
- `maps_to_existing`: true if the candidate is the same underlying move as one of the existing ones.
- `nearest`: the id of the closest existing move (the bracketed code), or "" if none is close.
- `confidence`: "high" if the candidate plainly restates an existing move, else "low".

A high-confidence map means the candidate adds no new doctrine — it is convergent. Anything else is
a novelty candidate.
