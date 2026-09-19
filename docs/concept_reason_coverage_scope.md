# Concept-appropriate "why" for diagnostic puzzles — scope

**Status: DRAFT, awaiting sign-off. No code written.**
Written 2026-09-19 after tracing the existing pipeline, per
`/verify-detectors-first`.

---

## The problem, in one line

A player solving a **fork** puzzle is asked *"Before Bxc3+, what attacked your
bishop on b4?"* — a piece-safety question about a fork lesson.

## What I found, and why this is much smaller than "build detectors"

The instinct was to build concept detectors for fork, pin and skewer. **They
already exist, and they are already promoted to the caption surface with
reviewed evidence.**

`backend/services/detector_quality.py` registers **18** quality ids with
authorizations. `build_reason_bundle_for_move` — the function that turns a
position into a "why" question — dispatches on exactly **one** of them and
returns `None` for the other seventeen:

```python
if quality_id == DESTINATION_SAFETY_QUALITY_ID:
    return build_destination_safety_reason_bundle(fen_before, submitted_move)
return None
```

That single line is why all 3,311 generated questions are piece-safety
questions. It is not a missing-detector problem. It is a dispatcher with one
entry.

### Already built, already authorized, not reachable

| Concept | Existing proof | Entry point for "this move creates it" | Authorization |
|---|---|---|---|
| fork | `services/fork_puzzle_proof.py` | `verify_created_fork(board, move)` | **CAPTION** — 50/50 fires, 25/25 near-negative abstentions, **92.87% Wilson precision lower bound**, 709 candidates verified |
| pin | `services/aligned_tactic_puzzle_proof.py` | `verify_created_alignment(board, move, "pin")` | **CAPTION** — 25/25 fires, **86.68% Wilson lower bound** |
| skewer | same | `verify_created_alignment(board, move, "skewer")` | **CAPTION** — 25/25 fires, **86.68% Wilson lower bound** |

Both carry `DetectorProof` + `VerifierProof` and independent geometry, which is
the verifier-first shape our own rule demands. Both are already consumed by
`caption_facts.py`. Both have promotion-packet builders in `backend/scripts/`.
The verification work is done and reviewed; nobody has to redo it.

Critically, both expose a **"this move *creates* the tactic"** entry
(`verify_created_*`), which is the direction a diagnostic needs — "why is the
solution right" — rather than only the missed-opportunity direction.

---

## What is actually missing

**1. Registration.** Add fork and aligned providers to the
`build_reason_bundle_for_move` dispatcher. Small.

**2. Question authoring — this is the real work.** The proofs return geometry
and payoff facts. They do **not** return a question with choices. Something
has to turn *"this knight move attacks the king on g8 and the rook on a8"*
into a question whose correct answer is derivable from the proof and nothing
else.

This is where the exercise is usually broken, so it carries the existing rule:
**the set of moves that satisfy the printed question must equal the set the
grader accepts.** If a player can answer the printed question correctly while
playing a move the grader rejects, the exercise is broken and does not ship.

**3. Nothing else.** No new detector family. No grading-threshold change. No
authorization relaxation. No pool rebuild.

---

## What this will and will not cover

Measured on the real pool (60 positions, read-only, 2026-09-19):

| Concept | Positions | Covered by this scope? |
|---|---|---|
| fork, pin, skewer | 18 | **Yes** — detectors exist at CAPTION grade |
| mate_patterns | 6 | **Probably** — `tactic:forced_mate_exact` and `tactic:back_rank_mate_exact` exist, but I have **not** traced them. Must trace before scoping in. |
| opening | 6 | **Probably** — `gap:opening_knowledge:left_book_for_a_worse_move` exists, untraced. |
| piece_safety | 6 | Already correct today. |
| endgame | 6 | **No.** Reason coverage is **0/6** — a total blackout. `review:endgame_geometry_causal_proof` exists but nothing currently derives a reason for any endgame position. Needs its own investigation. |
| threat_response | 6 | **No.** Coverage is **2/6**. |
| calculation, winning_technique | 12 | Coverage is good (6/6, 5/6) but the mapping to a concept-appropriate proof is unclear. |

**Honest limit:** I traced fork, pin and skewer thoroughly — signatures,
authorization grade, evidence, and the created-vs-missed direction. The other
concepts I matched **by name only**. They get the same trace before anyone
commits to them.

So this scope delivers **fork + pin + skewer = 18 of 60 positions**, plus
piece_safety which is already right. That is 24 of 60. It does not fix endgame
or threat_response, and it should not claim to.

---

## Acceptance

Per concept shipped:

1. The printed question is answerable **only** from the proof's own facts —
   no inference the detector did not establish.
2. Moves satisfying the printed question **==** moves the grader accepts.
   Counted, not asserted.
3. The question names the concept's mechanism (the two forked targets; the
   pinned piece and what it shields), not the moved piece's safety.
4. Zero regression in the existing per-concept coverage numbers above.
5. A stratified hand-read of real rendered questions — the numbers do not
   establish that the wording teaches anything.

`ready_for_player_exposure` stays `false` until all five hold for a concept.
Concepts ship independently; fork can go live while endgame is still dark.

---

## One decision needed before code

Every generated question currently ends with a third option — *"I did not
notice that relationship before moving"* / *"I did not check the destination
square."*

That is the **generic attitude option** the other branch (`07b4632e`, item 4)
explicitly removed: *"Concept sessions without available exact questions no
longer require a generic attitude quiz."* One branch deletes it; this one
generates 3,311 of them.

**Decide once, for both:** keep the third option, or drop it. Whichever ships
second will otherwise look like a regression of the first.

---

## Explicitly not in scope

Endgame and threat_response coverage. Changed-position pairing. Hints and
assisted retries. Any mastery or transfer claim. Rebuilding the pool. Enabling
player exposure.
