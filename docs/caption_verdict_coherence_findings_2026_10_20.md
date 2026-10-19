# Caption/verdict coherence — findings from the 2026-10-19 feedback batch

Six items flagged by Mohit on game review. One is fixed and shipped; the rest
resolve to **four distinct mechanisms**, each measured over 600 analysed games.

These are bug findings, not a feature scope — `/scope-driven-development`
explicitly excludes bug fixes. No code beyond the shipped mate guard until
the fix order below is agreed.

## The rule all four violate

> **No layer may assert something the move's own verdict contradicts.**

Every one of these is a later, more generic layer speaking over an earlier,
more specific one that was already right.

---

## 1. SHIPPED — a mating move is not an answerable check

`fb_6fc0dcba448f`. On `8/6p1/8/3R4/P2Pn2p/6kP/4r1P1/2B3K1 b` the card said
*"You have to answer it right now — move the king, block the line, or take the
piece that is checking. Nothing else is allowed. Look at all three."* The
position has **zero legal moves**.

`distilled_caption_service._good_caption` chose its check branch off
`b.gives_check(mv)`, true of mate as well; the capture branches ahead of it
never tested for check at all, so a mate delivered BY a capture would have
said *"take back to keep the material even."*

**Measured: 659 `distilled:opp_check` cards, 74 of them checkmate — 11%.**

Fixed in `f4d11dfc` (v225) by abstaining, not by writing a mate sentence: the
pipeline already had `R01_mate` underneath and the distilled layer was only
swapping text over it. Deployed, 8/8 gates. The 74 re-render on next view.

---

## 2. The largest one, and nobody flagged it directly — eval units are guessed

`fb_824d6b4f37a0` — *"the position was winning just before this move, why do
you say the spot was weak moves ago, wtf?"* He is right, and the cause is not
precedence.

`eval_trajectory._eval_to_cp` guesses which unit it was handed:

```python
if abs(v) > 100: return int(round(v))   # assume centipawns
return int(round(v * 100))              # else assume pawns
```

`move_evaluations.eval_before` **is** centipawns. So:

```
_eval_to_cp(  -4) = -400     dead equal, read as four pawns down
_eval_to_cp(  50) = 5000
_eval_to_cp(-149) = -149     only values past ±100 survive intact
```

**Every evaluation between −1.00 and +1.00 pawns is inflated 100×** — the most
common range in chess. On his game, move 31's `-4` became `-400`, completing a
three-move "losing run" and producing *"this spot got hard around move 26"* on
a position he was winning (+1.49).

**Measured: 196 cards carry the already-losing clause; 53 of them (27%) are
false** — the window only qualified because the heuristic inflated an eval.

**Why the heuristic exists, and why the fix is not a one-liner.**
`coach_sessions.evaluations` really does store pawns (`0.46`);
`move_evaluations` stores centipawns. Two collections, two units, one function
guessing between them. The same guess appears elsewhere —
`community_training_service.py:243` repeats it verbatim, and
`chess_brain.py:299`, `coach_puzzle_extractor.py:80` and
`board_geometry_service.py:729` all multiply by 100 on the assumption of
pawns. **Proposed fix: make units explicit at every caller and delete the
guess.** Blast radius beyond the already-losing clause is not yet measured —
that measurement is the first task, not the patch.

---

## 3. Praise stamped on a move the badge calls a blunder

`fb_dafde9f8478b` — *"but board says it's a mistake, why no arrow?"* The card
read *"You finally play Rd1 — taking the open file, the plan you had been
missing. Good."* with `severity=mistake` and `cp_loss=163`.

`game_decryption_v5_service.py:4772` fires on:

```python
if _missed_opp and move_san == _missed_opp.get("best_san"):
```

**String equality on the SAN and nothing else.** Rd1 was the engine's move
several moves earlier; he played that same SAN at move 39, when the best moves
were `b4 +2.10` / `a5 +2.07` and Rd1 scored `+0.95`. The layer congratulated
him for following advice that had expired, without rechecking the position.

**Measured: 109 `XMOVE_FINALLY` cards; 21 (19%) sit on a move the badge calls
inaccuracy or worse**, including *"You finally play Rg1 … Good."* on a
**blunder**.

Proposed fix: the branch must re-verify against the current verdict — require
the move to be at or near best **now**, not merely to match a remembered SAN.

Second, smaller defect on the same card: `caption_arrows` is empty while
`best_move_arrows` points `a4→a5`, a move the caption never mentions. That is
what he saw as "no arrow".

---

## 4. Filler occupies the why-slot and outranks the real reason

`fb_7e0a4084535e` (*"what is this pawn shelter bullshit, this is a clear
fork"*) and `fb_1ccd83c3ccbb` (*"it's not worst placed, it's actually very good
placed"*) are **one mechanism**.

`select_variant` rule `user_with_failure_and_alternative` requires only
`why_clause: "present"`. The board-state describer (`bs_king_shield_broken`,
`bs_worst_placed_piece`, `bs_open_file_owned_by_opp`) and
`principle_bank.json` always supply one. So generic text wins the slot against
position-specific truth.

On the fork card the caption had already said the right thing — *"Nb5 loses to
Qc5+"*, engine-confirmed (`25…Qc5+ 26.Qf2 Qxb5`, +3.63 → −2.41) with the red
`c7→c5` arrow correct — and then appended *"your king on g1 has lost 3 of its
pawn shelter"*, pointing at the wrong thing. On the bishop card the generic
principle also carried a **false premise**: *"when two opening moves look
equal"* on `Bb3 +1.06` vs `Be3 0.00`.

**Measured, and the number splits in two:**

| | cards |
|---|---|
| captions containing one of five filler clauses | **1,054** |
| of those, a concrete failure was ALSO named → filler won anyway | **90** |
| filler was the **only** thing said | **964** |

Only the 90 are this precedence bug. The 964 are the separate, older problem
in [memory/feedback_principle_bank_is_filler] — filler as the whole caption —
and must not be folded in, because the fixes differ: one is ordering, the
other is coverage.

I patched the ordering locally today for the own-side-alignment family
(`99f92bc0`) by inserting rules above `user_with_failure_and_alternative`. The
general fix is the same shape: **a `bs_*` or principle-bank clause may never
outrank a concrete failure clause.**

---

## 5. Minor — a recommendation without a why

`fb_1c2c39ad95c8`, *"why knight trade there?"* — *"Play Bxb6 — it trades their
knight."* The recommendation is **correct**: after `9…h5` the engine's own
first move is `10.Bxb6`. Only the reason is missing, per
[memory/feedback_explain_why_recommended_move_good].

Rating-band note: `cp_loss 35` against a band tolerance of 100 at his real
rating. This is not a precision quibble to dismiss — the caption is right and
incomplete — but it is the lowest-value item here.

---

## 6. Unflagged, and upstream of everything above

`resolve_coaching_rating` returns **912** for Mohit — `source:
recent_game_median`, **3 chess.com games**, `as_of 2026-09-24`. The game he was
reviewing is lichess at **1381**.

So the app coaches him as a sub-1000 player off three games a month old. That
moves his mistake tolerance from 100cp to 150cp and changes which caption tier
may fire ([memory/project_rating_band_decides_which_caption_tier]: below 1000,
`R12_blunder` never fires). Same failure already recorded in
[memory/project_coaching_rating_resolves_to_recent_game_median] (920 vs 1490),
still live, now on his own account.

---

## Proposed fix order

By damage per unit of risk, not by how loud the complaint was.

1. **Measure the units blast radius** (§2) before touching anything. The guess
   appears in at least five services and two collections genuinely differ.
   Deleting it blind would silently re-scale every comparison —
   [memory/feedback_changing_one_score_basis_changes_all_comparisons].
2. **XMOVE_FINALLY re-verification** (§3). Smallest, most self-contained, and
   it stops the product congratulating blunders. 21 cards per 600 games.
3. **Filler must not outrank a concrete failure** (§4, the 90). Generalises a
   fix already shipped and tested for one family.
4. **Stale coaching rating** (§6). Cheap to check, affects which tier fires
   everywhere, and he is personally mis-rated by ~470 points.
5. **Add the why to the trade recommendation** (§5).

Not proposed: touching the 964 filler-only cards. That is the coverage
question, and it needs its own measurement.
