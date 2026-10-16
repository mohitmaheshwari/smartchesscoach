# Game review: repair + timeline — implementation scope

Status: SCOPE for sign-off. No code written. Two contained parts, one
deliverable. Acceptance is judged on the same four games used throughout
([three_review_services_compared.md](three_review_services_compared.md)).

Target: **`services/game_coach_review.compose_story()`**, extended to read
`game_moments_service` rather than duplicating it. No fourth service.

**Revision 3, 2026-10-15** — decision taken: **verified causal explanations
where supported, board facts and game context elsewhere. No backfill in this
scope.** Three corrections follow from it: PV availability is not explanation
coverage (§2.2a); `best_move: bxc5` does **not** establish that the queen could
not be saved, and the licensed wording is weaker (§0.2a); and coverage means
selected moments, not a sentence per move (§2.6).

**Revision 2, 2026-10-15** — four amendments. The governing distinction is now
§0.3; the timeline is halfmove-level (§2.1); the claim that the four
computations need no engine analysis is **withdrawn** (§2.2); the thresholds are
marked proposed with the distribution attached (§2.4); and the shadow corpus
gains four move classes beyond the illustrative games (§3.2). Sequencing is
§6: repairs first and tested, timeline in shadow, evidence reviewed before any
player-facing explanation.

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

## 0.3 The governing distinction

Two kinds of statement, and they need different evidence. Conflating them is
the mistake this scope exists to avoid, and I have now made it twice.

| | Example | What verifies it |
|---|---|---|
| **Board fact** | "The bishop on e6 now attacks the queen on c4." | the position alone, legally, with python-chess. No engine |
| **Causal explanation** | "This move made losing material unavoidable." | **verified continuations and alternatives** — the lines, not the geometry |

**"The evaluation worsened" is not a sufficient gate.** It establishes that the
engine disliked the move. It does not establish that *my stated reason* is why.
A move can drop 300cp for a reason entirely unrelated to the loose piece I
happen to have spotted — which is exactly how the hanging-rook reading and the
six-safe-squares reading both went wrong.

So every timeline row carries its evidence class, and a causal sentence may
only be rendered when a continuation supports it. Where it cannot be
supported, the row says **unverified** and the board fact is shown alone.

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

### 2.1 Shape — every halfmove, not every one of his moves

Amendment 1, and it changes the structure. In Game A **`11.b4` does not attack
the queen; `11…Be6` does.** A timeline with one row per *his* move cannot
express that, and would wrongly attach the attack to b4. So the unit is the
**halfmove**, both colours, in order.

```
timeline[]            # one row per halfmove, in play order
  ply, move_number, side, san, phase
  # engine columns: HIS halfmoves only -- move_evaluations stores no
  # opponent evaluations at all, so these are absent, not zero, on
  # opponent rows
  eval_before, eval_after, cp_loss, engine_best, pv_after_played,
  pv_after_best                                      (stored, his rows only)
  mate_state                                         (separate, never cp)
  # board columns: computable on EVERY halfmove, either colour
  material_balance
  became_loose[]        pieces attacked-and-undefended after, not before
  line_unblocked[]      a line from an enemy piece to one of his that this
                        move cleared, by the mover's own piece leaving it
  defender_left[]       a square that lost its last defender
  newly_attacks[]       what this halfmove newly attacks (either side)
  # answer columns
  answered_previous_threat | did_not                 (computed)
  opponent_error_offered, he_punished_it             (move_observations, or
                                                      NOT RECORDED)
  # see 2.2
  explanation[]         each with its evidence class and status
```

Opponent halfmoves therefore carry board facts and no engine facts. That is a
statement of what we have, not a gap to paper over: `move_evaluations` holds
zero opponent evaluations.

### 2.2 The computations, reclassified — and the no-engine promise withdrawn

Revision 1 claimed all four were board-verifiable with no engine call. **That
was wrong for the fourth**, and the fourth is the one that mattered in Game A.

| Computation | Class | Verified by |
|---|---|---|
| **a piece became loose** — attacked and undefended after, not before | **board fact** | position only |
| **a line was unblocked** — the mover's own piece left a line from an enemy piece to one of his (the Rh6+/Nxf7 mechanism) | **board fact** | position only |
| **a defender left** — a square lost its last defender | **board fact** | position only |
| **"the piece now has no square that holds"** | **causal / evaluation claim** | *not* geometry. Needs every retreat evaluated |

The fourth is an evaluation claim wearing geometry's clothes. Counting attackers
and defenders told me Game A's queen had six safe squares; the engine says each
of them is ~100cp worse than conceding the queen. So:

**Rule: the fourth claim may be rendered only from already-verified evidence,
and otherwise is marked unverified and not shown.**

What already-verified evidence exists, measured over 638,222 stored user-move
rows:

| Stored evidence | Present on |
|---|---|
| `best_move` / `best_move_uci` | effectively all rows |
| **`pv_after_played`** non-empty | **207,053 (32.4%)** |
| **`pv_after_best`** non-empty | **206,564 (32.4%)** |
| `threat` non-null | 197,687 (31.0%) |

### 2.2a PV availability is not explanation coverage

The 32.4% is an upper bound on one kind of evidence, and it is the wrong number
to plan with, in **both** directions:

- **A stored PV does not establish a proposed cause.** `pv_after_played` is one
  line. It shows what the engine expects next; it never shows that every
  alternative was worse. So the whole "unavoidable" family of claims is
  **unverifiable from stored data at any coverage level** — not 32.4%, zero.
- **Some claims need no PV at all.** "The bishop on e6 attacks the queen on c4",
  "this move left the knight on e6 attacked and undefended", "his own piece
  left the f6–h4 line" are each decided by the position, legally, and are
  available on **every** halfmove.

So the decision is **claim by claim**, not coverage-wide:

| Claim | Evidence it needs | PV required | Availability |
|---|---|---|---|
| X now attacks Y | position | no | every halfmove |
| a piece became loose | position, before/after | no | every halfmove |
| a line was unblocked | position, before/after | no | every halfmove |
| a defender left | position, before/after | no | every halfmove |
| he answered the previous threat | position + the move played | no | every halfmove |
| material changed by N | position | no | every halfmove |
| the engine's line after this move gives up the queen | `pv_after_played` / `pv_after_best` must actually contain it | **yes** | where the PV exists **and** contains the event |
| this move was a turning point | stored evals + state change | no | every one of his moves |
| **"losing material was unavoidable"** | **every alternative evaluated** | PV is insufficient | **not available** |

The third column is the gate, and the last row is the one to remember.

**Game A, and what the stored evidence actually licenses.** Revision 2 said
`best_move: bxc5` showed the queen could not be saved. **It does not.** It
identifies the engine's preferred continuation; it says nothing about why every
alternative is worse. One best move is one data point, not a ranking.

What I may write from stored evidence:

> "The engine's continuation after b4 gives up the queen for material."

What I may **not** write from stored evidence:

> ~~"After b4 the queen could not be saved."~~
> ~~"Every retreat loses more."~~

I did establish the stronger claim earlier — a depth-20 run ranked all 38
legal moves and put `bxc5` at −374 against the best queen move `Qxe6` at
−482. **But that was a new engine call, which this scope forbids.** So it is
true, and the shipped product cannot say it. That gap between what I verified
ad hoc and what the product may claim is the distinction worth holding onto.

**No new engine analysis is in scope.** Where existing evidence is insufficient,
the answer is silence on the causal claim, not a new Stockfish pass.

### 2.2b What to say when the cause is unsupported

Not a hedged guess. An invented cause with a softener in front of it is still
an invented cause. Where no verified cause is available, the row reports what
is known and nothing more:

- **the threat created** — what the opponent's halfmove newly attacks (board)
- **the response played** — and whether it answered that threat (board)
- **the verified continuation** — the stored PV where one exists, quoted as the
  engine's expectation rather than as a consequence
- **how the game developed** — the eval and material path around the moment
- **the remaining uncertainty**, stated where it matters: which of these we
  could not establish, and that his intention is unknown unless asked

Game A's move 11 under this rule reads as: level before it, −363 after it, the
engine preferred `d4`; `11…Be6` attacks the queen on c4; the engine's
continuation gives up the queen for material. No sentence claims b4 *made* the
loss unavoidable, because nothing stored shows that.

### 2.3 Three columns, kept apart

Per your instruction, every timeline row is labelled:

| Column | Source | Example from Game A |
|---|---|---|
| **what happened** | board + stored engine facts | "after b4, the queen on c4 was attacked and every retreat was worse than conceding it" |
| **what was avoidable** | engine comparison only | "`d4` instead of `b4` kept the game level (−11 vs −363)" |
| **what he intended** | **unknown unless asked** | left blank, with the position flagged as a question candidate |

The third column is never inferred. A row with no recorded intention says so,
and move 11 becomes a candidate for the threat-assessment question.

### 2.4 Turning point, replaced — with PROPOSED thresholds

Not `max(cp_loss)`. A move qualifies when it both costs enough **and** changes
the game's state (level→losing, winning→level, losing→lost). A game may have
none, one, or several — Game D has several, and saying so is the point.

**The numbers are proposals, not settled.** 150cp and the 200cp recovery
threshold in §2.5 were picked before I looked at anything, which is the error
this project keeps paying for. The distribution over all 638,222 user moves:

| cp_loss | Share |
|---|---|
| 0–1 | 47.1% |
| 1–25 | 13.9% |
| 25–50 | 10.3% |
| 50–100 | 11.2% |
| 100–150 | 5.5% |
| **150–200** | **3.2%** |
| 200–300 | 3.2% |
| 300–500 | 2.7% |
| 500–1000 | 1.3% |
| 1000+ | 1.5% |

≥150cp is **11.9%** of moves, so at ~30 of his moves per game that is roughly
3.6 candidates per game before the state-change conjunction narrows it.

**Gate: both thresholds are chosen from this distribution plus worked examples
AND counterexamples before either is locked.** The counterexample that matters
most is a move above the threshold that changed no state and taught nothing —
if those are common, the threshold is wrong, not the move.

### 2.5 Recovery, which is currently invisible

A recovery segment is a run of his moves over which the eval improves by
≥200cp. It is reported with **who caused it**: his own moves' cp_loss, and the
opponent errors in the same window (or `NOT RECORDED`). Game C and Game B both
contain one and neither is currently mentioned.

---

### 2.6 Coverage means selected moments, not a sentence per move

Coverage here is **useful, trustworthy reviews** — not an explanation attached
to every move. 47.1% of his moves cost under 1cp; an ordinary developing move
needs no causal account and saying something about it would be filler.

So the timeline computes every halfmove and the review **selects**: the
connected moments that carry the game's shape, plus the demonstrated strengths.
A review of six moments where five carry verified causes is a better review
than thirty moments where eight do.

The measurement that follows from this is in §5 step 4: after shadow
validation, count the **important** moments — the selected ones — that remain
unexplained. That number, not PV availability, is what could later justify
targeted engine enrichment. It does not justify any now, and it must not delay
§1.


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

### 3.2 The shadow corpus — four classes beyond the illustrative games

Amendment 4. Four games cannot validate an explanation generator, and the four
chosen all end badly or messily. The shadow run must include move classes where
**the evaluation falls or the geometry fires but the explanation would be
false**. All four are samplable from flags already stored:

| Class | How it is sampled | Available |
|---|---|---|
| **sacrifices** — material given up on purpose | `is_sacrifice: true` | **38,714 (6.1%)** |
| **sound exchanges** — a capture recaptured, eval unchanged | `evaluation: best` plus a capture with a legal recapture | `is_best` on 335,106 (52.5%) |
| **harmless attacks** — a piece becomes "loose" and nothing comes of it | `became_loose` fires and `cp_loss` is 0 | the 300,561 moves at 0–1cp |
| **successful counterplay** — the eval falls and he goes on to win anyway | a recovery segment followed by a win | Games B and C already qualify |

**The validation question is whether the explanation is TRUE, not whether the
evaluation fell.** For each shadow row carrying an explanation, the check is:
does a verified continuation show the stated mechanism actually operating? A
row where the eval fell and the stated reason is wrong counts as a **failure**,
not a success — which is the opposite of how a cp_loss-driven check would score
it.

Target to agree before enabling anything: the share of rendered explanations
that survive that check. I will not propose a number before the shadow data
exists.

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

## 5. Sequencing

As directed: verification built in from the start, timeline in shadow until
validated.

1. **The six repairs (§1), implemented and tested, shipped on their own.** None
   needs the timeline, all six are defects in live output, and the
   `evaluation`-key fix alone makes strengths appear for the first time.
2. **The timeline developed in shadow** — written to its own field, rendered to
   nobody, with every row carrying its evidence class and status.
3. **The shadow evidence reviewed** against §3.2, including the counterexample
   classes, before any player-facing explanation is enabled. The flag gates the
   render only, never the computation, so the shadow series keeps accumulating.
4. **Then, and only then, measure the unexplained important moments** (§2.6).
   If selected moments routinely lack a verified cause, that is the evidence
   for targeted engine enrichment — a later, separately scoped piece of work.
   It is not part of this implementation and does not gate steps 1 to 3.

## 6. The decision, recorded

**Decided: verified causal explanations where supported; board facts and game
context everywhere else. No hedged causes. No backfill in this scope.**

The qualifications that came with it are now in the body rather than here:
PV availability is not explanation coverage and the decision is claim by claim
(§2.2a); unsupported moments report the threat, the response, the verified
continuation and the game's development, with the uncertainty stated, rather
than a softened guess (§2.2b); coverage means selected moments (§2.6); and the
count of unexplained *important* moments after shadow validation is what could
justify targeted enrichment later (§5 step 4).

Nothing is open. The scope is ready for implementation in the §5 order.
