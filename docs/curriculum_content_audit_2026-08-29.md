# Curriculum Content Audit — 2026-08-29

Status: **automated truth-and-delivery gate implemented; external coach/player
validation is the final stage.**

This audit covers the content a 600–1500 player can actually open. It does not
count a name, ECO label, legal move list, or hidden card as a finished lesson.

## Player-visible inventory

| Subject | Canonical records | Chess/content verified | Player lesson ready |
| --- | ---: | ---: | ---: |
| Openings | 79 | 37 | 37 |
| Traps | 55 | 22 | 22 defense-first lessons |
| Endgames | 20 | 20 | 20 |

The opening catalog now contains 37 authored lessons. The 12 previously
legal-but-unexplained lines now include move-by-move coaching and are restored.
The remaining 42 records are imported recognition labels, many of them aliases
or named move-order fragments rather than distinct lessons. They continue to
identify a player's games and route to a taught family; they are not padded
into duplicate catalog cards. Every visible primary line is legal and every
move has its own authored explanation.

All 22 chess-verified trap records are now defense-first lessons. Each names
the danger, starts at the actual decision point, offers engine-checked safe
moves, and explains why the defense works. The product still does not replace
a missing defense lesson with “learn how to spring this trick.”

The complete 20-lesson endgame catalog is now verified:

- Mate with Queen
- Mate with Rook

- Kings Face Off (Opposition)
- The Squares Your King Needs
- Rule of the Square
- Pawn Breakthrough
- King to the Center
- Shield the King from Checks (Lucena)
- Philidor — Third Rank Defense
- Rook Activity
- Stopping Promotion
- Stalemate Traps
- Good Bishop vs Bad Bishop
- Opposite-Color Bishop Draws
- Knight vs Bishop
- Knight Blockade
- Creating a Passed Pawn
- Make Them Move (Zugzwang)
- Outside Passed Pawn
- Two Pawns vs One

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

## Completion backlog exposed by the gate

### Openings

- 42 records can recognize a name but contain no playable lesson.
- Some quarantined records also contain unexplained specialist wording.

The 12 legal lines are complete. The remaining job is to map every imported
recognition label to a taught family where it is an alias, and author a new
lesson only where the record represents a genuinely different player need.

### Traps

- 33 records fail chess truth, explanation, or evidence requirements.
- The 22 chess-verified lines are complete defense-first lessons.

The 500-game corpus shows the existing library covers the recurring named
traps. Remaining trap records must first have their illegal or unsupported
winning lines repaired; they must not be counted merely because they have a
famous name.

### Endgames

- No completion backlog remains in the canonical endgame catalog.
- All 20 lessons and all 60 positions are legal, answer-hidden at runtime, and
  backed by exact Syzygy evidence or pinned Stockfish 18 evidence.
- The repair replaced false breakthrough and passed-pawn examples, corrected
  the Philidor, opposite-bishop, stalemate, and two-versus-one answers, and
  replaced every illegal FEN instead of hiding its lesson.

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

Manual sessions are the final coaching-quality audit, not a reason to leave the
automated completion backlog unfinished. Pre-launch analytics are still not
used as an engagement baseline.
