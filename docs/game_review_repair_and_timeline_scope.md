# Game review: repair + timeline — implementation scope

Status: SCOPE for sign-off. No code written. Two contained parts, one
deliverable. Acceptance is judged on the same four games used throughout
([three_review_services_compared.md](three_review_services_compared.md)).

Target: **`services/game_coach_review.compose_story()`**, extended to read
`game_moments_service` rather than duplicating it. No fourth service.

---

## 0. Two verifications first — both corrected me

### 0.1 `good_moves` is a one-word data-contract bug

You were right that population code exists. It is at
`game_coach_review.py:479`:

```python
good_candidates = [
    e for e in user_evals
    if (e.get("classification") in ("best", "excellent", "brilliant"))
    and (e.get("cp_loss") or 0) == 0
    and (e.get("move_number") or 0) >= 6
]
```

Counted on Game B's 50 user rows:

| Clause | Rows passing |
|---|---|
| carries a `classification` key | **0** |
| `classification` in (best/excellent/brilliant) | **0** |
| `cp_loss == 0` | 26 |
| `move_number >= 6` | 45 |
| all three | **0** |

**The field is called `evaluation`, not `classification`.** Its real values on
that game: `best` 26, `inaccuracy` 6, `blunder` 9, `good` 4, `mistake` 4,
`excellent` 1. With the correct key the filter yields **22 candidates** and
returns m49 `Bh4` and m48 `Bxe5`.

So my "nothing fills it" was wrong about the mechanism. The logic is sound; it
reads a key that does not exist. (`ev.get("move")` *is* correct — `move_san` is
absent on every row, which is why my own probes read `move_uci` throughout.)

### 0.2 Game A: the cp_loss attribution is correct, and my claim is withdrawn

I said the move that lost the queen was charged zero and therefore
mis-attributed. **Wrong.** Independent engine run, depth 20, against the stored
values:

| | Stored | Independent run |
|---|---|---|
| before his 11th | −14 cp, best `d4` | **−11 cp, best `d4`** |
| before his 12th | −345 cp, best `bxc5` | **−367 cp, best `bxc5`** |

Every legal move at move 12, ranked white-relative at depth 18:

| Move | cp | |
|---|---|---|
| **bxc5** | **−374** | he played this, and it is the **best of all legal moves** |
| Rb1 | −437 | |
| O-O | −444 | |
| … | | |
| **Qxe6** | **−482** | the best queen move |

**Saving the queen was 108cp worse than conceding it.** My "six safe squares"
was board geometry only; the engine says every retreat loses more. The 0cp on
move 12 is right, and the material timeline cannot overrule it.

**The verified story of Game A:** level through move 10 (−11 cp). **`11.b4` is
the error** — 352cp, −11 → −363, engine wanted `d4`. Its cost is only visible
one move later: after `11…Be6` the queen on c4 has no square that holds, so
conceding it for bishop-plus-pawn becomes the *best available* continuation.
The rooks at moves 16–17 are the tail of a position already assessed at −3.7.

That is a cross-move claim, and it is the shape §2 has to produce: **b4's real
cost is what it did to the queen's options.**

---

## 1. Part one — repair the existing review

Six defects, all in shipped code, none needing new analysis.

| # | Defect | Evidence | Fix |
|---|---|---|---|
| 1.1 | **Strengths never shown** | `good_moves: []` on all four games | Read `evaluation`, not `classification`. Add a contract test asserting the key exists on a real row, so a rename breaks the test rather than the output |
| 1.2 | **Mate scores render as centipawns** | `−9108cp`, `−1385cp`, *"Total material leaked: 99.3 pawns worth"*, `eval_before: 99.7` | Carry mate as a distinct state (`mate_in`, side) through to the text. Never divide a mate sentinel by 100 and never label it `cp` |
| 1.3 | **Missing data stated as fact** | *"Your opponent played clean — no mistakes to punish"* on Game A, which has **zero** `move_observations` rows | Three states, not two: errors offered / none offered / **not recorded**. The third says so |
| 1.4 | **Empty strings ship as teaching** | `"remedy": ""` twice in Game B's summary_table | Omit the row rather than render an empty remedy. Assert non-empty on every user-facing string before return |
| 1.5 | **Malformed opener** | *"You played the this game"* on all four lichess games | When the opening name is absent, change the sentence rather than interpolating nothing. Derive the opening from the moves where possible |
| 1.6 | **Title contradicts diagnosis** | Game D m51: *"King in the corner = mate"* against *"it runs into Bxg8, taking your bishop"* | The title must be generated from the same fact as the diagnosis, or dropped |

Also in scope because it is one line: the turning point is currently
`max(cp_loss)`, which on Game C selects a move made while already winning and
on Game D disagrees with `game_coach_summary` (move 4 vs move 51). §2.4 replaces
the selection; §1 keeps the current behaviour until then.

---

## 2. Part two — the evidence-backed timeline

One new structure, built only from facts already stored or computable from the
board. Nothing is a score.

### 2.1 Shape

For each of his moves, a row carrying what is **verified**:

```
timeline[]
  move_number, san, phase
  eval_before, eval_after, cp_loss, engine_best      (stored)
  mate_state                                         (separate, never cp)
  material_balance                                   (computed from the board)
  his_piece_now_attacked_undefended[]                (computed: square, piece)
  opponent_just_created[]                            (computed: what their last
                                                      move newly attacks)
  he_answered_it | he_did_not                        (computed)
  opponent_error_offered, he_punished_it             (move_observations, or
                                                      NOT RECORDED)
  what_this_move_changed[]                           (see 2.2)
```

### 2.2 The one genuinely new computation

`what_this_move_changed` — the cross-move link, and the only part that is new
analysis. Four board-verifiable facts, each a before/after comparison:

- **a piece of his became loose** (attacked and undefended after, not before)
- **he stopped blocking a line** (a line from an enemy piece to one of his
  became clear because his own piece left it) — the Rh6+/Nxf7 mechanism
- **a defender left** (a square he was defending lost its last defender)
- **the opponent's options changed** — specifically, whether a piece of his
  that was safe now has no square that holds, which is what `11.b4` did

Each is computed with python-chess from the stored `fen_before` pairs. No
engine call, no new score, no threshold.

### 2.3 Three columns, kept apart

Per your instruction, every timeline row is labelled:

| Column | Source | Example from Game A |
|---|---|---|
| **what happened** | board + stored engine facts | "after b4, the queen on c4 was attacked and every retreat was worse than conceding it" |
| **what was avoidable** | engine comparison only | "`d4` instead of `b4` kept the game level (−11 vs −363)" |
| **what he intended** | **unknown unless asked** | left blank, with the position flagged as a question candidate |

The third column is never inferred. A row with no recorded intention says so,
and move 11 becomes a candidate for the threat-assessment question.

### 2.4 Turning point, replaced

Not `max(cp_loss)`. A move qualifies as a turning point when it both costs
≥150cp **and** changes the game's state (level→losing, winning→level,
losing→lost). A game may have none, one, or several — Game D has several, and
saying so is the point. Where a game has no such move, the review says the
game was never decided by one, rather than naming the largest cp_loss.

### 2.5 Recovery, which is currently invisible

A recovery segment is a run of his moves over which the eval improves by
≥200cp. It is reported with **who caused it**: his own moves' cp_loss, and the
opponent errors in the same window (or `NOT RECORDED`). Game C and Game B both
contain one and neither is currently mentioned.

---

## 3. Acceptance — the same four games

| Game | Must produce | Must not |
|---|---|---|
| **A** | the queen-loss sequence: `11.b4` named as the error with `d4` as the alternative, and the move-12 concession explained as **best available** rather than a blunder | call move 12 a mistake; claim the queen could have been saved; claim the opponent "played clean" when no data exists |
| **B** | both halves: 11 blunders **and** the eight consecutive 0cp moves (m11–m20) that rebuilt −208 → +509, plus 7 opponent errors unpunished | call it a clean win; call it "demonstrates nothing"; render `remedy: ""` |
| **C** | won by checkmate **from a lost position**; the opponent's failure to convert at move 19 (eval −9970, his move was the engine's best); both opponent errors punished; the missed mate in 3 at move 20 | describe it only as a "messy win"; print `99.7` or `−1385cp` for a mate score |
| **D** | several state-changing moments, not one; and that the two existing services disagreed about which | name a single turning point; print "99.3 pawns worth" |

Plus, across all four: `good_moves` non-empty wherever candidates exist; no
empty user-facing string; no malformed opener; every intention column blank or
sourced; and a stated uncertainty line wherever observations are missing.

### Regression

`compose_story`'s current output is fingerprinted over 400 games before any
change and diffed per field, so a repair that silently alters unrelated games
is caught. `test_all_flows.py` green against a pre-change baseline.

---

## 4. Out of scope

No new scoring system. No new service. No change to stored analysis data — this
reads `move_evaluations` and `move_observations` and writes nothing. No LLM.
No homepage change. The import-idempotency work
([import_idempotency_scope.md](import_idempotency_scope.md)) is separate and
neither blocks the other, though the timeline should de-duplicate its game list
at read time.

## 5. One open question

§2.2's four computations are the new analysis, and they are the part most likely
to produce confident nonsense — my last two attempts to reason from board
geometry against the engine were both wrong (§0.2, and the earlier
hanging-rook reading). I would gate each of the four on an engine check before
it may appear in text: the claim is only rendered if the engine agrees the
position worsened. **Do you want that gate from the start, or should the four
fire freely in a shadow field first so we can measure how often they disagree
with the engine before anything is shown?**
