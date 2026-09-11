# Correctness review — 11 September 2026

What is wrong, how each thing was found, what it costs, and what was done
about it. Every number here came from running something against production
data on the day; nothing is quoted from memory. Where a claim could not be
re-verified it is marked as such rather than repeated.

The scripts are in the repo so each number can be re-derived:

| Question | Script |
|---|---|
| Where should the loose-piece gates sit? | `backend/scripts/loose_piece_gate_distribution.py` |
| Are stored evals centipawns? | `backend/scripts/audit_stored_eval_units.py` |
| Why did a player's rating move? | `backend/scripts/rating_change_attribution.py` |
| Did their opponents get worse? | `backend/scripts/opponent_blunder_pilot.py` |
| Do players improve without us? | `backend/scripts/natural_drift_study.py` |
| Are game dates usable? | `backend/scripts/normalize_game_dates.py` |
| How far does the Socratic diagnosis reach? | `backend/scripts/socratic_diagnosis_reach.py` |
| Is a recommended capture really a trade? | `backend/scripts/trade_claim_distribution.py` |

---

## Fixed and deployed

### 1. The loose-piece card never checked that the move was a mistake

**v150, live.**

`caption_facts.build_legal_material_loss_cause` answers a board question:
after this move, is something of mine worth 150cp or more capturable for
free? That is a fact about the position, not a verdict on the move. The
review path used the answer as the verdict, with no other test at all, and
then wrote "Nc4 left your rook on d1 available" in the same voice it uses for
a real blunder.

Over 500 analysed games it produced 641 such cards. Cross-tabbed by what the
move actually cost against how decided the game already was (eval units
normalised — see finding 6):

```
cp_loss    close   one side better   decided 600-1499   over 1500+   row
  <30          5                14                 23            7    49
  <50          0                 7                  3            4    14
  <75          3                12                 16            2    33
 <100          2                15                 16            0    33
 <150         10                23                 23            5    61
 <300          8                53                 65            0   126
>=300         47               159                 77           42   325
```

Three gates come out of that, and nothing else does.

**Cost at least 50cp.** Below it the engine considers the move essentially
free, so the card contradicts the engine it is quoting. Real removals: a
recapture at cp_loss 0, and `Rxf8 ... Kxf8` — a trade — narrated as a rook
left available. 63 cards, 9.8%.

The floor is flat, not the rating-band inaccuracy floor from
`rating_resolver`. I tried the bands first. They are a volume control for
subtle engine preferences, and a piece hanging for free is not subtle — a 700
needs to hear about it more than an 1800 does, not less. The band version
removed 170 cards including a genuine free knight at cp_loss 142 for a
988-rated player. Wrong axis.

**Skip once |eval| reaches 1500cp.** Cards fired at +9880 and −9990: the game
is over and we are discussing a rook. 47 cards, 7.3%. 600 was tempting and
wrong — 223 cards (35%) are played while one side is already 600–1499 ahead,
and losing a rook while down 700 is still a real mistake worth teaching.

**Abstain when the punishment is checkmate.** 5 of the 641 narrated a mate as
a material loss: `Ne2` answered by `Qxe2#` at cp_loss 8742, `Rg7` by `Qxg7#`.
The card discusses a rook while the player is being mated. On this corpus all
5 are already caught by the two gates above, so it adds no coverage today; it
is there for the pawns-unit analyses where the eval gate fails open.

Net: **641 → 531 cards, 82.8% kept.** Tests:
`backend/tests/test_loose_piece_card_needs_a_mistake.py`,
`backend/tests/test_legal_material_loss_attribution.py`.

### 2. The Socratic surface never asked a question

**v151, live.**

`R18_socratic_user_mistake` is the rule that is supposed to put a question to
the player instead of handing them the answer. All 19 of its variants shipped
`question` and `hint` as empty strings from the day the rule was written.
`R17_coach_move` shipped `hint_for_user` empty on all 18 of its. Nothing ever
failed — the renderer reads the key, gets `""`, stores `""`.

Across 500 stored reviews, 29,302 move cards:

```
socratic_coaching   fired on  2,115 cards -- 2,115 narratives,  0 questions
coach_move_coaching fired on 14,635 cards --                    0 hints
```

16,750 coaching cards and the question field was empty on every one. The
frontend had already worked around it: `GameDecryptionV5` was changed on
2026-08-03 to stop gating on `.question` so the card would render at all, with
a comment saying the click-to-reveal UI could come back "once that content
exists."

All 37 fields are now authored — each question answerable from the board in
front of the player, using only placeholders its own variant already carries,
and each hint teaching the method rather than giving the answer. The review
card renders the question and a click-to-reveal hint again.
`scripts/pwc_coaching_lint.py` gained an R18 pass and now fails on an
unauthored field, or on a "question" that does not end in a question mark;
verified by sabotaging two variants and watching it fail. Test:
`backend/tests/test_socratic_surface_asks_a_question.py`.

### 3. Eighty-six per cent of Socratic cards said the same generic thing

**v153, live.**

Authoring the questions raised the obvious next question: which variant is
actually asking them? Classifying 8,405 stored Socratic cards back to their
template:

```
generic variants               7,230   86.0%
mistake_hanging                  423    5.0%
blunder_hanging_with_capture     412    4.9%
blunder_threat_fork              142    1.7%
blunder_threat_mate              116    1.4%
blunder_hanging_with_mate         81    1.0%
blunder_threat_capture              1    0.0%
```

Eleven of the nineteen variants had never fired. Review derived
`fundamental_violated` from exactly two board facts and fell to the generic
variant for everything else — while every analysed move already carried the
analyser's own `cognitive_gap`. Over 400 games, of the moves that reach this
surface:

```
<none>               30.8%
piece_safety         19.5%   -> hanging_pieces
king_safety          15.1%   -> king_safety
missed_tactic        12.8%   -> calculate
opening_knowledge     9.0%   (not mapped)
endgame_technique     6.8%   (not mapped)
tactical_oversight    6.0%   -> calculate
```

The mapping is deliberately partial. `opening_knowledge` is **not** mapped to
`development`: that variant says "you moved a developed piece instead of
bringing a new one out", and leaving known theory does not establish that.
`endgame_technique`, `pawn_structure`, `piece_activity` and `time_pressure`
have no variant that says anything they establish. A wrong name is worse than
no name.

The first attempt at this barely moved — 86.0% to 83.1% — and the wiring was
right while the ordering was wrong. The derivation proposes `hanging_pieces`
whenever `pieces_now_undefended` is truthy, which is far more often than a
piece genuinely hangs; the injector then refutes that label and set the
fundamental to None, straight to generic, having never reached the gap. On
396 real Socratic-eligible moves, 87 were being discarded at exactly that
point (king_safety 44, missed_tactic 21, piece_safety 19, tactical_oversight
3). The fallback now runs at the guard, where the board has just said what the
move is *not*. If the gap agrees with the label the board refuted, the board
wins.

Measured on the same 396 moves, before and after:

```
                        before    after
fundamental=None           187      119
king_safety                  9       53
calculate                    7       31
hanging_pieces              21       21   (board-proved, unchanged)
```

Re-rendering 20 real games end to end: **generic 86.0% → 59.2%**, variants
speaking 8 → 11, a question on 71 of 71 cards, zero leaks.

Making eleven silent variants speak exposed a defect latent in all of them.
Their narratives embedded `socratic_problem_facts`, inherited from
`smart_coaching` as notes written *about* the student, so a card rendered as:

> Your king position got weaker. Student's king is in danger

— the internal note, shown to the player, restating the sentence before it.
All seven narratives that embedded the joined string did nothing but repeat
themselves, so the embedding is gone and the evidence strings are written in
the voice we speak in. `pwc_coaching_lint` gained a *rendered* R18 pass (64
fields across every severity × fundamental) that fails on third-person prose
or an unrendered placeholder — the static pass could not have caught this,
because statically the narrative is just a placeholder.

### 4. The caption and its explanation disagreed about whether the move was a mistake

**v151, live.**

The unearned-verdict softener (v142) ran only at the composition boundary. The
board explanation was snapshotted before it, so the two surfaces diverged —
caption "f3 is playable", explanation "f3 is a mistake" — and the explanation
is exactly what the caption falls back to when the personalized text fails
verification, so a verification failure shipped the verdict the softener had
just refused.

Worse: the personalized path composes its caption *from* that snapshot, and
the composed text is long enough that the softener's template-shape guard then
declines to touch it. Prefixing a sentence about the player made an unearned
verdict permanent. Softening now happens once, before anything is built on top
of it — which is what `caption_pipeline`'s own docstring says it should do.

### 5. A piece sacrifice was being called a trade

**v154, live.** Reported from the product on 2026-09-11:

> Opponent's Bd6 is a mistake. Play Nxb5 — it trades his pawn.

`Nxb5` is the engine's best move at +263, and the reason is the opposite of a
trade. The a6 pawn guarding b5 is also the only thing keeping the a-file shut
in front of an undefended rook, so after `axb5 Rxa8` the rook falls outright —
Black has no recapture on a8 at all. The card replaced a tactic with a reason
that was false *and* boring.

`_recommended_move_why` described every recommended capture from the static
exchange value on the target square, and its last branch — labelled "equal-ish
exchange" — had no floor under it:

```
SEE >= 200     -> "wins material"
SEE >=  80     -> "wins a pawn" / "wins material"
anything else  -> "trades his {piece}"
```

Over 500 analysed games, 1,376 recommended captures get a why; 506 were called
trades, and **128 of those (25.3%) sat at SEE ≤ −50**, 110 of them below −100.
SEE on b5 in the flagged position is −200. One trade claim in four was not a
trade.

Two rules, both from that distribution. Below −50 the word is not used. When
*every* recapture on the square leaves something worth ≥150cp hanging, the card
names that instead — "costs him the rook on a8 if he takes back" — every
recapture, because the opponent picks which one. The rest fall through to the
branches the function already had, all board-verified. The 128 redistribute as:

```
costs him the X on Y if he takes back   30
attacks the X on Y                      25
takes the center                        21
gives check                              9
defends / takes the open file           12
develops / posts a knight                4
no why at all                           27
```

101 keep a true why and 27 lose it. That is the right way round. "wins
material" (870 cases) is untouched. Three of the new claims were hand-verified
against engine PVs before shipping: `Nxb5` (a8 rook, no recapture exists),
`Rxf2` (+205, `Kxf2`), `Qxa8` (+882, PV `17. Qxa8 Qxa8 18. Bxa8`).

The card now reads: *"Opponent's Bd6 is a mistake. Play Nxb5 — it costs him the
rook on a8 if he takes back."*

### 6. Game chronology was decided by a field that stopped updating

**Migrated; 14,809 of 15,517 games rewritten.**

`date_played` holds two formats (`2026-08-30T13:51:45+00:00` and
`2026.03.31`), and `"2026."` sorts after `"2026-"`, so a lexical sort
interleaves them. `date_played_iso` was meant to be the clean field but was
written by a one-off backfill: it froze at 2026-08-31 while games kept
arriving, and was absent on 964 rows, so a Mongo descending sort dropped the
newest games to the end. Both failures return wrong answers rather than
errors — which is how a time-management feature I shipped came to read a
stale "60 most recent games."

`services/game_dates.py` is the single parser. The migration converged: 14,809
correct, 447 already fine, **261 with no parseable date at all** (see finding
9). Every consumer was checked first for equality-on-a-bare-date-string; none
does, so widening the field to a full timestamp is safe for ordering and range
queries.

---

## Found, not yet fixed

Ranked by what they cost a real user.

### 7. Stored evaluations are in two different units, inside the same field

3.9% of analyses (78 of 2,000) store `eval_before` / `eval_after` in **pawns**;
the other 96.1% store centipawns. `cp_loss` is centipawns in both, so the two
fields disagree on units inside the same document. Spotted because a sampled
card printed "eval 4.5 → 3.96" next to cp_loss 54 — 0.54 pawns is 54cp.

Anything that compares a stored eval to a centipawn threshold silently
mis-reads those 3.9%: +4.5 reads as a level game when it is White up a bishop
and a half. The new loose-piece gate fails open on them deliberately, so they
keep their card rather than losing it wrongly, but that is containment, not a
fix.

**The fix.** Find the writer that emits pawns (`audit_stored_eval_units.py`
identifies the documents; the fractional value is the reliable discriminator,
not "the number is small"), correct it, then backfill the 3.9% by multiplying
by 100. Do the deploy before the migration — writing normalised values under
code that still expects pawns would invert the bug.

### 8. Half of every game is never analysed

3 of 14,839 stored analyses contain a single opponent move. We analyse the
user's moves and discard the opponent's.

That is not a small omission. A pilot that evaluated both sides of real games
found opponents blundering **2.6 to 4.0 times per game** at these ratings.
Every one of those is a chance the user did or did not take, and the product
cannot see any of it. "You had a winning move here and played something else"
is a whole coaching category that does not exist for us.

It also makes one question permanently unanswerable: whether a player's rating
rose because their opponents played worse. Opponent *rating* is the only proxy
available, and it cannot see a 1200 having a bad day.

**The fix, and what not to do.** Do not backfill 14,839 games to answer the
measurement question — the pilot already answered it (finding 11) and the
compute is better spent elsewhere. Do analyse both sides **going forward**, for
the coaching category. The pilot script shows the shape; depth 12 (the
codebase's `QUICK_DEPTH`) is adequate for a blunder rate.

### 9. 13% of blunders carry no cognitive gap

Over 2,000 analyses: 63,576 user moves, 8,658 blunders at 150cp or worse.
7,534 (87.0%) have a `cognitive_gap`; **1,124 (13.0%) have none**. A blunder
with no gap cannot be attributed to a weakness, so it cannot reach a focus, a
puzzle, or a progress card. It is a mistake the system saw and then forgot.

**The fix.** Take a stratified sample of the 1,124, classify by hand what kind
of mistake each is, and see whether they cluster into a category the detector
set does not have (the likely candidates are positional and endgame) or are
genuinely unclassifiable. Build the detector only if the sample says the
category exists — per the standing rule, verify the target exists before
building the detector.

### 10. 261 games have no usable date at all

Left behind by the migration. They cannot be ordered, so they are invisible to
every before/after measurement and to "your recent games." 1.7% of the corpus.

**The fix.** They still have PGNs. Re-parse the PGN `[Date]`/`[UTCDate]` tags
directly; where the PGN has none either, fall back to the import timestamp and
mark the row as approximate rather than leaving it unsortable.

### 11. The material-claim verifier lets two classes through

`narrator_claim_verifier._check_unsupported_material_loss` guards captions that
say "costs you material" / "hands material away" / "loses material".

- When the stored line cannot be fully replayed it returns no complaint at
  all — `if complete:` with no `else`. The claim ships unverified. (The
  `except` branch does fail closed; the incomplete-replay path does not.)
- It accepts the claim whenever the mover lost *more than* the opponent, with
  no floor. Its piece values are knight 320 and bishop 330, so a plain
  bishop-for-knight trade satisfies "loses material" by 10cp.

**The fix.** Require a real imbalance — at least a pawn, 100cp — before the
claim passes, and decide explicitly what an unreplayable line should do.
Measure first: count how many rendered captions carry the phrase and how many
take each path, then choose. Not yet measured, so no threshold is proposed
here.

### 12. The exchange evaluator does not see king recaptures

`static_exchange_eval` skips kings on every ply of the recapture sequence. The
code documents this as a deliberate Phase-1 limitation and predicts it is
"correct in middlegame positions and slightly too-cautious in some K+P
endgames."

The second half of that is wrong. Game `1d591f35` move 7 is an opening
position: `Rxf2` reads as −200 because SEE stops after `Rxf2 Bxf2+` and never
counts `Kxf2`. The engine says **+205** (`7. Rxf2 Bxf2+ 8. Kxf2`). A rook
landing in front of a castled king is one of the most common tactical shapes
there is, not an endgame curiosity.

This is why finding 5's proof is built on `legally_hanging_pieces`, which does
count `Kxf2`, rather than on SEE.

**Why it was not fixed here.** SEE feeds hanging-piece detection and every
"wins material" claim in the caption layer. Changing it would move far more
than the wording bug that exposed it, and the existing comment's caution is
legitimate — a king recapture is only legal when no other defender remains and
the destination is not attacked, so a naive fix would overclaim in the other
direction.

**The fix.** Measure first: re-run the caption corpus with a king-aware SEE
alongside the current one and count where the two disagree, split by whether
the king recapture is actually legal. Then decide. Do not change it behind an
unrelated wording change.

### 13. Rating change mostly cannot be attributed, and that is the finding

Across 18 users with 200+ analysed games each, split into halves:

- Among players whose own blunder rate did **not** materially change, rating
  moves ranged **−110 to +279**. Anything inside that band needs no
  explanation at all.
- 7 of 18 came back "unexplained" and are reported that way.
- An earlier version of this analysis labelled 5 users "stronger opponents."
  That inverted cause and effect — opponent rating rises *because* the player
  climbed and matchmaking followed. It is a consequence of the gain, not a
  competing cause, and is no longer reported as one.
- The pilot on three unexplained users found opponents blundering **less**,
  not more: 3.56→3.12, 4.04→3.32, 2.80→2.64. "My opponents got worse" does not
  explain these gains.

The separate natural-drift study (18 users, 200+ analysed games) found every
pattern within ±5% and improvement counts of 8–11 of 18 — a coin flip. Players
do not shed these patterns on their own, which is the premise the product
rests on, and it holds. The instrument was validated at the extremes: a +299
rating user showed −21.5% blunders, a −165 user +16.0%.

**What this means for measurement.** Rating is too noisy to be the outcome
metric at this sample size. Blunder rate within a user, against their own
baseline, is the measurable one.

### 14. The evidence a coaching claim would need does not exist yet

- `complete_coaching_journeys`: 113 documents, **1 distinct user**.
- `MASTERY_STRICT_EVIDENCE` must stay off, and must **never** be gated on
  `DETECTOR_QUALITY_GATE_ENFORCED` — that is already true in production and no
  events carry per-event proof, so tying them together empties mastery and
  progress for everyone.

No claim about coaching effect should be published from this data.

---

## Test suite

The branch we deploy from had **7 failing tests** in the caption suite. Nobody
had rebaselined them, so the suite had stopped protecting those paths.

Four were failing because the Socratic content was missing — they were right
and the product was wrong; authoring the content fixed them. One was a real
product bug (finding 3). Two were stale and are rebaselined with the reasoning
written into the test:

- `test_forced_recapture_downgrades_user_facing_to_good` asserted that a 400cp
  forced recapture is shown as "good". `compute_severity_for_move` deliberately
  refuses that now — the downgrade set `severity_override`, which gated the
  Socratic surface, and 0 of 12,328 analysed games carried `socratic_coaching`
  as a result. Its position also had no pawn on e6, so its "recapture" was an
  illegal move and the assertion never described real behaviour.
- `test_capture_free_piece_populates_correctly` kept the black queen on d8,
  which defends d5, so the pawn was not free and `coach_overreach` was the
  correct variant.

The caption suite is green: 526 passed, 0 failed. Separately, 53 API and
integration tests fail in a plain checkout because they need a live server and
database; that is unchanged by this work and verified against the pre-change
tree.

---

## Deliberately not done

- **Backfilling opponent analysis across 14,839 games.** The measurement
  question it would answer is already answered (finding 10). Analyse both
  sides going forward instead.
- **Picking a threshold for the material-claim verifier** (finding 10). Not
  measured yet, and a threshold chosen before the distribution is a guess.
- **Fixing the 53 integration-test failures.** They need a running stack; that
  is an environment task, not a correctness one.
