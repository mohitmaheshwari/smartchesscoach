# Missed concepts — scope

Status: DRAFT, awaiting Mohit's sign-off. No code until then.
Plain English. 2026-09-19.

---

## Where this came from

Mohit asked whether our lessons actually catch the things a coach teaches —
rule of the square, opposition, king activation, opening principles.

They exist. `endgame_opposition.py`, `rule_of_the_square.py`,
`opening_principles.py`, `endgame_lucena.py` are all real, and they fire on
real games. Run through the production runner over 400 games / 12,365 moves:

**1,644 fires. 1,639 "applied". 5 "wrong."**

The cause is one line. Every one of these detectors gates on
`stored_best_matches(board, move, best_move_san, best_move_uci)` — **the move
played must BE the engine's best move.** So the detector only ever runs on
moves the player already got right, and is structurally incapable of saying
"you missed this."

A detector that can only say *you did it right* cannot find a weakness, cannot
drive a lesson, and cannot teach. That is why the curriculum feels absent when
all the code is present.

---

## The change, in one sentence

Where the detector today asks *"was the move the player made this concept?"*,
it should also ask *"was the move the player SHOULD have made this concept?"*

Same predicate. Applied to the engine's move instead of the player's.

---

## What the player sees

    ┌────────────────────────────────────────────────┐
    │  [ board: red arrow Nh5, green arrow O-O ]     │
    │                                                │
    │  Your king was still in the middle on move 11  │
    │  with both rooks asleep. Castling first is      │
    │  what makes every other plan safe to start.    │
    └────────────────────────────────────────────────┘

Same shape as the mate cards: the board carries the geometry, the words carry
the rule that transfers. One sentence of situation, one rule.

---

## The numbers, measured before designing anything

400 games, 11,890 user moves, 2,536 real mistakes (cp_loss >= 100 and not the
engine's move). Of those, how many are a missed concept — the engine's move
WAS the concept and the player played something else:

| concept | missed | per game | % of games | median cp lost |
|---|---|---|---|---|
| development | **160** | 0.40 | 28% | 164 |
| centre pawn | **77** | 0.19 | 16% | 138 |
| king centralization | **39** | 0.10 | 7% | 409 |
| castling | **33** | 0.08 | 7% | 160 |

**309 teachable moments in 400 games — 0.77 per game — where today there are
zero.** For comparison, `discovered_attack`, which consumed a full day of
review, fires 0.02 per game.

Development alone is 28% of games. That is a coaching surface, not a curiosity.

---

## What has to be true for a claim to fire

1. It is the player's move, and the engine says it lost **>= 100cp**.
2. The engine's own move satisfies the concept's existing predicate — the same
   function, unchanged, evaluated on `best_move` instead of `move`.
3. Opening concepts only inside move 15; endgame concepts only when the
   endgame test the detector already uses passes.
4. **Nothing bigger speaks first.** The precedence that every detector fixed
   this month now obeys: a mate on the board outranks a hung piece, which
   outranks a missed concept. The cp_loss distribution goes to 9,684, so some
   of these are mate swings wearing a development costume.
5. The claim never names the engine. It names the habit.

Note on 1: the floor is a real mistake, not an engine preference. p25 is 124cp
and p50 is 164cp, so the population is genuine errors, not rounding.

---

## How we know it worked

- **Precision** through `/admin/detector-review`, like every other detector.
  These enter at **shadow** and earn their grade on human rulings. Nothing
  about this scope promotes anything.
- **The measurement that matters is "wrong" counts.** Today: 5 in 12,365
  moves. If this ships and that number does not move into the hundreds, it
  did not work.
- **Regression pack:** a position where the player castled correctly must
  still read "applied" and must never produce a missed claim.

---

## Risks

- **Scolding a reasonable move.** The engine preferring O-O by 110cp does not
  make the player's move a blunder. Gate 1 is the whole defence, and 100cp is
  taken from the measured distribution rather than chosen.
- **Incidental attribution.** The engine's move being a developing move does
  not prove development was the *lesson* — it may be developing AND winning a
  piece. Gate 4 is the defence, and this is the same trap `tempo_loss` hit,
  where 3 of 4 candidates were about something else entirely.
- **Four concepts is not a curriculum.** This does not cover opposition,
  rule of the square, Lucena or Philidor, which fire too rarely to review.
  It covers the four that actually occur.

---

## Not in this scope

- Promoting anything to caption or plan grade.
- `rule_of_square`, which is DISABLED and exists three times over
  (`concept:endgame_rule_of_square`, `legacy_endgame:rule_of_square`,
  `principle:END_RULE_OF_SQUARE`). Deduplicating that is its own job.
- Lessons, puzzles or the skill tree. This produces evidence; what consumes it
  is a separate decision.
