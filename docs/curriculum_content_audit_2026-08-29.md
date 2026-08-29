# Curriculum Content Audit — 2026-08-29

Status: **automated truth-and-delivery gate implemented; external coach/player
validation is the final stage.**

This audit covers the content a 600–1500 player can actually open. It does not
count a name, ECO label, legal move list, or hidden card as a finished lesson.

## Player-visible inventory

| Subject | Canonical records | Chess/content verified | Player lesson ready |
| --- | ---: | ---: | ---: |
| Openings | 79 | 25 | 25 |
| Traps | 55 | 22 | 1 defense-first lesson |
| Endgames | 18 | 5 | 5 |

The opening catalog now contains the 25 authored response-tree lessons. The 42
recognition-only labels and 12 legal-but-unexplained lines do not appear as
lessons. Every visible primary line is legal and every move has its own
authored explanation.

The 22 verified trap records are still useful for exact recognition and game
review. Only **Scholar's Mate Danger** is currently offered as a coaching
lesson because it is the only one with all three required pieces: the danger,
a legal safe defense, and an explanation of why the defense works. The product
does not silently replace a missing defense lesson with “learn how to spring
this trick.”

The five verified endgames are:

- Kings Face Off (Opposition)
- The Squares Your King Needs
- Rule of the Square
- Shield the King from Checks (Lucena)
- Make Them Move (Zugzwang)

Every visible endgame position has offline exact tablebase evidence when it is
eligible. The first attempts hide the answer, and the final position is an
independent proof attempt.

## What was repaired

- Four broken opening lines/positions were corrected (London, Italian as
  Black, Modern Defense move ambiguity, and French Advance evidence).
- Tree-authored openings now render the tree's own explanations instead of
  repeating one generic plan after every move.
- Ten defense records received an explicit player color.
- The false “never play Nc3” claim in the Modern Defense was corrected: c3 is
  this lesson's chosen setup; Nc3 is sound and leads to a different setup.
- Opening advice in strategic game review now comes from the same validated
  source used by Learn and Play with Coach.
- Scholar's Mate was migrated into the canonical trap source and made
  defense-first with the answer hidden.
- Legacy hardcoded trap and endgame lesson inventories were replaced by
  canonical adapters.
- Published coaching copy was rewritten to explain concrete squares, pieces,
  and threats instead of unexplained terms such as “tempo,” “counterplay,”
  “fianchetto,” “IQP,” or “space advantage.” The validator now blocks those
  regressions.

## What remains quarantined, and why

### Openings

- 42 records can recognize a name but contain no playable lesson.
- 12 records contain a legal line but no authored move-by-move teaching.
- Some quarantined records also contain unexplained specialist wording.

Do not add more opening names yet. The next useful opening work is to author
complete response trees for the openings the real-user repertoire data shows
are most common, then pass the same gate.

### Traps

- 33 records fail chess truth, explanation, or evidence requirements.
- Of the 22 chess-verified lines, 21 still lack a defense-first lesson.

The next trap content should be authored in this order after coach review:
Scholar's Mate (already ready), Legal's Mate danger, Blackburne Shilling,
Stafford Gambit, Elephant Trap, and Englund Gambit. Each needs a concrete
danger position, safe move(s), why the tempting move fails, and an independent
defense attempt. Popularity should be checked against real games before this
order is locked.

### Endgames

- Five positions have invalid FENs.
- Nine stored answers lose an exact win or draw in tablebase evidence.
- Ten positions outside tablebase coverage lack pinned Stockfish evidence.

For 600–1500 players, the next additions should be **mate with queen**, **mate
with rook**, **stop a pawn from promoting**, and **active rook defense**. Then
repair Philidor, stalemate tricks, and the remaining pawn/bishop lessons. These
are additions, not permission to re-expose the current broken records.

## Reproduce offline

```bash
cd backend
python scripts/audit_curriculum_content.py
python -m pytest tests/test_curriculum_content_validator.py \
  tests/test_canonical_trap_practice.py \
  tests/test_verified_opening_traps.py \
  tests/test_curriculum_runtime_gates.py -q
```

The Syzygy snapshot is versioned at
`backend/data/corpus_snapshots/curriculum_endgame_tablebase_2026-08-29.json`.
Runtime curriculum reads make no public tablebase request and need no database
or credential.

## Final external validation

Mohit and the invited coaches should test only after this automated gate is
green. The manual audit should answer:

1. Does the first sentence make the board idea obvious without prior jargon?
2. Can the player make the expected move without the UI revealing it?
3. Does a wrong move teach what changed on the board?
4. Does completion require a clean final attempt?
5. Does Learn still show one active plan and return the player to it?

Expansion remains deferred until those sessions are completed; pre-launch
analytics are not used as an engagement baseline.
