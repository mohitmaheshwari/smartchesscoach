# Captions that read the whole line — scope

Date: 2026-11-06. Written after Mohit asked, on Rxe7 of his game against
ChessKingsFather (game 3628ebef, move 32), "why is this a mistake?", then "why
did the UI caption not show the right why?", then "how do I fix it for all?".

Status: DRAFT, awaiting Mohit's signoff. No code has been written.

---

## 0. Existing surfaces audit

What already touches "the card explains why the move was worse", at the level of
what each one produces today. Every line below was read in the code or the
stored data this session.

**A. The caption pipeline, `backend/services/caption_pipeline.py`.** One move's
caption passes through these stages in this order:

| Stage | Where | What it produces today |
|---|---|---|
| R12 rule cascade | `data/captions/R12_blunder.json` | A templated reason, e.g. "Re6+ was better — it also hits the knight on e7." |
| Verifier recovery | `_verify_and_recover_caption`, line 4257 | Checks every "the knight on e7" claim on the board AFTER the played move. A failed claim throws the whole sentence away and leaves "Rxe7 is a serious mistake. Re6+ was better." The only exemption, `_clear_best_move_capture_claims` (line 4185), proves claims about the better move on the board BEFORE the move, and only for the verbs takes, captures, wins, removes (line 4153). "Hits" is not covered, which is what emptied the Rxe7 card. |
| Floor principle | `_maybe_append_floor_principle`, line 204 | When the caption is the bare shell, appends one sentence from `data/captions/principle_bank.json`, picked by FEN hash. Mohit's standing judgment: filler. |
| Why-better append | step 11c, line 8647 | Puts the stored reason for the better move into "X was better — it …". For a check with no provable target the reason is "gives check, forcing your opponent to respond". |
| Reply gap | `caption_facts._reply_gap`, line 10771; `reply_gap_sentence`, line 4087 | Compares only the opponent's FIRST reply in each stored line and says "That lets them take the rook on e7 with Qxe7." One ply deep on purpose (diffing line ends measured 52–62%, a coin flip). Scoped in `docs/explain_the_move_you_played_scope.md`. |

Measured over every stored card in the production database, read through the
local read-only tunnel (20,229 games, 256,925 user mistake cards, 254,916
opponent mistake cards, census 2026-11-06):

| Layer | User cards | Opponent cards |
|---|---|---|
| Explanation thrown out by the verifier | 5,108 | 10,496 |
| Carry a reply-gap sentence | 18,070 | 9,582 |
| Carry a principle-bank sentence | 12,867 | — |
| Carry the generic "gives check, forcing…" phrase | 3,906 | 7,842 |
| Start with the bare verdict shell | 37,722 | not measured |
| Rxe7 shape (capture played, better move is a check, same capture follows) | 882 | not measured |

**B. The Why button, `backend/services/reasoning/differential.py`.** Runs the
engine on both moves and compares the lines. It already owns:
`exchange_ledger` (line 317: captures along a line grouped by square, needs a
board and a list of moves, no engine), `material_claim` (line 455: the rules
for when material is the story) and `exchange_sentence` (line 413: the words).
Family modules follow `reasoning/tempo.py`. Its shared-consequence rule ("the
better move allows the same thing, so it is not the difference") covers only
the opponent's punishing replies. On Rxe7 it said "Re6+ was the move: it leads
to Rxe7, picking up their knight on e7 for free", a wrong contrast, because the
played move takes that knight too.

**C. The Why queue, `backend/services/why_queue.py` and `why_study.py`.** A click
the button cannot answer is studied later by Claude under a replay gate. This is
the only surface that can say "the ending with knight against pawns is lost".

**D. Measurement and review tooling.** `/admin/captions` searches stored cards by
FEN. `docs/qa/why_engine_regression_set.json` (38 positions, 4 classes) with the
judge baseline in `docs/qa/why_engine_regression_baseline_2026_10_30.md`.
`scripts/audit_full_game_chess_facts.py` writes corpus snapshots to
`data/corpus_snapshots/`. `scripts/regen_specific_games.py` re-renders named
games and WRITES them; it has no dry-run.

**E. Tests that pin today's behaviour.** `tests/test_reply_gap.py`,
`tests/test_best_move_capture_claim_board.py`,
`tests/test_caption_verifier_telemetry.py`, `tests/test_abandoned_guard_reaches_the_card.py`.

**Overlap.** The reply gap (A) and the exchange ledger (B) both describe what a
capture leads to. The ledger reads the closed exchange; the reply gap reads one
ply. The R12 variant "same piece, better square" and the proposed check-first
family both speak when the better move is a check that keeps the same target.

**Differentiation.** Nothing today reads the two stored lines as lines. Every
caption stage reads one fact.

**Decision: EXTEND.** Three existing chokepoints change. No new page, no new
collection, no new rule file. One stage is REPLACED inside its own function:
the reply gap's capture branch gives way to the ledger; its check branch stays.

---

## 1. What it is

The card's explanation stops being four sentences from four stages that never
talk to each other, and starts reading the two engine lines the way a coach
does: what the capture led to, what the better move's check removed, and what
the material says at the end of the exchange. The sentence that proves the
better move's point is judged on the board that move is played from, so a true
sentence is no longer thrown away because the player's own piece is now standing
on the square. The Why button, the queue and the card draw their material
sentences from one place.

---

## 2. What the user sees

The Rxe7 card today (verified on the stored card, both copies of the game):

```
Rxe7 is a serious mistake. Re6+ was better — it gives check, forcing your
opponent to respond. When you spot a forcing move, check your opponent's
response three moves deep before playing. That lets them take the rook on e7
with Qxe7.

[Why?]  Re6+ was the move: it leads to Rxe7, picking up their knight on e7
        for free.
```

The Rxe7 card at the end. Every clause is a board fact the ledger or the new
family supplies; the words below are the deterministic sentence, and luna may
re-word them under the existing four guards.

```
Rxe7 is a serious mistake. Their queen takes back, your other rook takes the
queen, and their king takes that rook. Every piece comes off. Re6+ first makes
their king step away from e7, so after Rxe7 they cannot take back twice. Check
first, take second.

[Why?]  Rxe7 and Re6+ both take the knight on e7. After Rxe7 their king on
        f6 takes back the second rook. After Re6+ Kg5 Rxe7 the king is on g5
        and nothing takes back.
```

A card the verifier empties today (the sentence is true on the board the better
move is played from; the player's rook stands on e7 only because Rxe7 was
played). After fix 1 it survives, and fix 3 then improves on it:

```
today     Rxe7 is a serious mistake. Re6+ was better.            (sentence thrown away)
after 1   Rxe7 is a serious mistake. Re6+ was better — it also hits the knight on e7.
```

The shape of a card that carries the one-ply sentence today (wording shape, not
a verified position; the real words come from `exchange_sentence`):

```
before  Qd7 is a mistake. That lets them take the pawn on e5 with Bxe5.
after   Qd7 is a mistake. After Qd7, the exchange on e5 costs you a knight
        for a pawn.
```

What the user does NOT see: no new button, no new page. The same card, better
sentences.

---

## 3. In scope (V1)

**Fix 1 — the verifier judges a claim on the board it belongs to.**
- A piece claim inside the clause about the better move ("Re6+ was better — it
  hits the knight on e7") is checked on the board after the better move is
  played: the piece is on that square, and the better move's piece attacks it.
- Covers the relation verbs hits, attacks, threatens, targets, pins, defends,
  covers, in addition to the four capture verbs already covered.
- The existing survival check (Phase 2) still runs on the same claim.
- Done when: `test_best_move_capture_claim_board.py` extended with the Rxe7
  sentence passing and a false "hits" claim still failing; a dry-run re-render
  of the 15,604 recovered cards reports how many now keep a sentence; 30 of
  those hand-graded, zero false claims.

**Fix 2 — the exchange ledger replaces the one-ply capture sentence.**
- `_reply_gap`'s capture branch is replaced by `exchange_ledger` run on the two
  stored lines (played move plus `pv_after_played`; better move plus
  `pv_after_best`). The check branch of the reply gap stays as it is.
- The sentence comes from `material_claim` and `exchange_sentence`, so the card
  and the Why button say the same thing about the same exchange.
- Two known wording defects in those functions are fixed first, because 27,000
  cards would otherwise inherit them: the series sentence words the difference
  between the lines as if it were the total ("two pawns up" where the line
  nets one); and a group names only its dearest piece when a pawn fell on the
  same square too.
- Done when: `test_reply_gap.py` is rewritten to the new contract and passes;
  a dry-run re-render of a 2,000-game sample shows the "lets them take the
  [piece just captured with]" shape at zero; 30 changed cards hand-graded,
  zero misframed exchanges.

**Fix 3 — the check-first family.**
- Shape: the played move is a capture; the better move gives check; the
  engine's line then makes the same capture on the same square. The difference
  is what the check removed: the recapture (Rxe7: the king on f6 took back),
  or an escape square, read off the two lines.
- Built as a family module in `reasoning/`, after the material families, so the
  Why button and the queue packet get it. The caption reads the same facts
  through the R12 variant "same piece, better square", which today says only
  "attacks more things".
- Done when: the Rxe7 card and button both read as in section 2 on screen; the
  fire-rate pass over the 882 shape cards is reported (how many fire, what
  they say, how many are silent and why); zero fires on the 8 good moves of
  the regression set; no regression-set position moves from MATCH to MISS.

**Measurement, before and after each fix.**
- Snapshot every faulted card's caption and rule name before the first change.
- A dry-run render harness: the generator that `regen_specific_games.py`
  calls, run without the database write, so a sample can be rendered against
  new code and diffed against the snapshot.
- The why-engine regression set run at the baseline and after fix 3.

**Rollout.**
- `V5_COACHING_VERSION` bumped once, after all three fixes, so cards re-render
  on open. Deploy through `scripts/deploy.sh backend`, 8-check gate.
- The Rxe7 card re-rendered with `regen_specific_games.py` and read back from
  the database, both copies of the game.

---

## 4. Explicitly out of scope (V1)

- The endgame judgment ("knight against pawns is lost"). Stays with the queue.
- Removing the principle bank. Re-measured after fixes 1 and 2; fewer shells
  means it fires less, which is the fix rather than a deletion.
- A full regeneration pass over all 19,800 games (about 22 hours of load on the
  shared box, measured in October). Starting it is Mohit's call; the scope
  delivers the bump and the one-game proof.
- Running a live engine at render time. Everything here reads stored lines.
- The other pre-screen defects of the differential (mate worded as material,
  the button's budget missing deep mates, the stored-best defect on 5e68fc88
  m15). Filed in the baseline doc, untouched here.
- Luna wording changes. The deterministic sentence ships; luna re-words it
  under the existing guards where enabled.
- The opponent-side count of the check-first shape. Measured in the fire-rate
  pass, not a V1 gate.
- Backfilling `move_observations` badges. The badge is unchanged by this work.

---

## 5. Success criteria

- On the Rxe7 card, read from the stored row after re-render: the caption names
  the king's recapture and the check that removes it; the Why button's text
  names the same difference. Both verified on screen, not in the registry.
- Verifier: of the 15,604 recovered cards, the share that keeps a sentence
  after fix 1 is reported with the number; 30 hand-graded, zero false claims.
  A sentence let through that is false fails the fix.
- Ledger: on the 2,000-game dry-run sample, zero captions of the shape "lets
  them take the X on S with Y" where Y is a recapture of a piece that just
  captured; 30 changed cards graded, zero misframed exchanges.
- Family: the fire-rate report exists; zero fires on the 8 good moves; no
  regression-set MATCH turns MISS; the 882-card shape yields its distribution
  (how many are king recaptures, how many escape squares, how many something
  else) before any cutoff is locked.
- Deploy 8/8 and the Rxe7 card re-rendered and read back within the same day
  as the version bump.

---

## 6. Open questions

- **Question:** When R12 has a true fault clause and the ledger also has a
  sentence, which comes first on the card?
  **Why unresolved:** depends on how often both fire on the same card.
  **Unblocking step:** count it in the 2,000-game dry run; decide from the
  histogram.

- **Question:** Does V1 of the check-first family cover only "the check removes
  the recapture", or also "the check removes an escape square"?
  **Why unresolved:** the 882 shape cards have not been split by what the
  check removes.
  **Unblocking step:** the fire-rate pass reports the split; V1 covers the
  largest bucket at least.

- **Question:** Full regeneration pass, yes or no, and when?
  **Why unresolved:** Mohit's call; 22 hours of load on a shared box with an
  analysis worker prone to running out of memory.
  **Unblocking step:** Mohit decides after the bump is live.

- **Question:** Opponent cards: does the ledger sentence read right from the
  reader's side on every shape?
  **Why unresolved:** the series and exchange sentences were graded on user
  moves; the opponent-side pronoun defect was fixed on 2026-11-05 but not
  re-graded at scale.
  **Unblocking step:** 30 opponent cards in the hand grade of fix 2.

---

## 7. Pre-code requirements

- The caption snapshot of every faulted card exists in the session scratchpad
  (caption, rule name, game, move, side), with the row count recorded.
- The dry-run render harness exists and renders one known game identically to
  its stored card at the current version (positive control).
- The why-engine regression set has a baseline run recorded at the current
  commit.
- No open PR touches `caption_pipeline.py`, `caption_facts.py`,
  `narrator_claim_verifier.py` or `reasoning/differential.py`. Checked
  2026-11-06: the only open PR (#1, "Latest code") touches none of them.
- Mohit has signed off on this document.
