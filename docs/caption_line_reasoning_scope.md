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

---

## 8. Build record (2026-11-06)

Branch `claude/why-queue`. Not merged, not deployed. Every number below was
measured in this session; where a run is still going the count of games it
covers is stated.

**Commits**

| Commit | What |
|---|---|
| `1e181273` | Fix 1: a relation claim about the better move is proved on that move's board |
| `a9b707ae` | Fix 2: the exchange ledger replaces the one-ply capture sentence; the ledger's two wording defects |
| `e07b3c15` | Fix 1 corrected by its hand grade: the relation must survive the reply; the floor names what the move took |
| `6876dcad`, `1171da3b`, `14e0b157` | Fix 3: the check-first family, the card wiring, and three rounds of tightening from the fire-rate pass |
| `16271b64` | V5 v241, the single bump |
| `bbe75903` | Fix 2 corrected by its dry run: the ledger sentence reaches the card |
| next commit | Fix 2 corrected by its hand grade: "nothing can take back" only when nothing can |

**The Rxe7 card, rendered by the final code from both stored copies of the game
(3628ebef and 98360122), through every verifier gate:**

```
Rxe7 ends with their king taking back on e7. Re6+ was better — it makes their
king step away first, and then Rxe7 wins the knight with nothing to take back.
Check first, take second.

[Why?]  Both Rxe7 and Re6+ go for the knight on e7. After Rxe7, the pieces
        come off on e7 and their king on f6 takes back last. Re6+ first makes
        their king step away to g5. Then Rxe7 takes the knight and the king
        cannot take back.
```

Not yet read from a stored row or on screen: that needs the deploy.

**Fix 3, measured on the whole corpus (20,259 games, read-only scan)**

| | User cards | Opponent cards |
|---|---|---|
| Played move is a capture, better move is a check | 4,834 | 2,494 |
| Full shape (the check is not a capture; the better line takes the same piece on the same square with its next move) | 524 | 331 |
| Family fires | 32 | 21 |
| Fires on a mistake or worse | 28 | 17 |
| Silent: the recapture in the played line is not the king's | 466 | 297 |
| Silent: the king still guards the square after the check | 13 | 6 |
| Silent: other (reply not a king move, reply takes material, no gain after a sacrifice, checker lost later, still recaptured) | 13 | 7 |

All 32 fired user cards were read against their two lines; each sentence matches
its line. The first passes fired on 60 and then 36 cards; the hand grades of
those are what set the conditions (see the commit messages). The answer to open
question 2: V1 is the king's recapture, 6% of the shape. The other 89% is a
recapture by another piece, which this family does not explain.

Why-engine regression set (42 positions with `mohit_rxe7` added): 24 of the
original 41 found before and after, no position moved from found to silent, no
fire on the 8 good moves. Two sentences changed, both the series wording fix
("a piece down" to "two pawns down" on dev_qf8, "two pawns up" to "a pawn up" on
mohit_f3; both match the ledger's net for that line).

**Fix 2**

- Probe on the 38 current-version mistake-or-worse cards that carried the old
  sentence: the ledger speaks on 27; the 11 silences are 8 even trades, 2 the
  Rxe7 card, 1 a forced mate. The old sentence had framed each of those trades
  as a loss.
- The first build passed 498 tests and put the ledger sentence on no card: the
  stage read the tier from a field that does not exist. A 347-game dry run
  showed 309 old sentences removed and 0 ledger sentences in their place.
  Fixed in `bbe75903`, with tests that go through the render function.
- First final-code render (139 games): 0 cards carry the old sentence; 104
  carry a ledger sentence (70 user, 34 opponent); on 27 a sentence existed and
  the word cap or the final verifier stopped it. Every "simply takes" sentence
  was checked on the board: 9 of the 29 that said "and nothing can take back"
  sat where a recapture was legal (157fead3 m18: Rxb7 with Qxb7 on the board;
  the line does not play it). The ledger now records whether each capture
  could be answered on its square and says "simply", "nothing can take back"
  and "for free" only when it could not. The same sentence is the Why
  button's, so the live button has this defect until the deploy.
- Of the 19,371 stored cards with the old sentence, 11,022 are inaccuracies.
  Those lose the sentence and get nothing in its place, by the ledger's own
  rule (no material claim on an inaccuracy). That is a deliberate loss of
  coverage on inaccuracies and it is Mohit's to accept or not.

**Fix 1**

- First bulk render (before the survival rule), 2,717 games, 4,409 emptied
  cards: 461 kept a sentence (10.5%), 3,818 were still emptied (86.6%).
- The hand grade of 30 found two sentences that should not have shipped; both
  are fixed in `e07b3c15`. It also found three that come from other paths and
  are not fixed here (see "Found, not fixed").
- So fix 1 as scoped rescues about one emptied card in ten. It is not the main
  cause.

**The main cause, found by tracing 60 games (99 replaced captions)**

58 of the 99 are one sentence on opponent cards: "lets you play A, and B then
takes their P on S". The piece reaches S a move or two into the stored line, and
the first verifier gate judges it on the current board. All 58 replay true at
the ply B is played. That gate already has the proof for this
(`_clear_best_move_capture_claims` accepts the played line); it is never given
the played line. Passing it through is on the branch
`claude/caption-line-claims` with an added check of the owner word. It is
outside the text of fix 1 above and is not part of what was signed.

**Found, not fixed**

- The skewer clause is computed on the board before the move: "Bd6 allows Bxd6,
  skewering your bishop on f4" when Bd6 is the bishop that left f4. The verifier
  rejects these, correctly. 7 of the first 30 still-replaced captions after both
  verifier changes.
- "leaves your bishop with nothing guarding it — they take it back on f7" on
  f1b9e955 m5, where the knight on g5 guards f7.
- "Play Bxe5 — it wins a pawn" / "Play hxg6 — it wins a pawn" on recaptures
  (7dd9ce00 m24, 62c9bb00 m22).
- f00eef29 m47: the stored best move tells the player not to take a free rook
  (Kxd5, best Kc4). Stored-analysis defect.
- Phase 2 (`_verify_phase2_attack_claims`) is alive, not dead as section 0
  implies: it rejected 12 of 99 captions in the trace. Some are misfires: it
  reads "Nxc2 lets Rac1 attack the knight on c2", a sentence about the played
  line, as a claim about the better move.
- Prod runs `DISTILLED_CAPTIONS_ENABLED=1` in the backend container and unset
  in both analysis workers, so stored captions are a mix of two render paths.

**Measurement runs still going (final code `bbe75903`, throwaway containers,
read-only login, capped at 600 MB each, stopped by a watchdog under 800 MB
free)**: the 9,496 games holding an emptied card, and the 2,000-game sample.
The shared box has no swap and fell to 446 MB free once during the day.
