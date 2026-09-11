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
normalised — see finding 5):

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

### 3. The caption and its explanation disagreed about whether the move was a mistake

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

### 4. Game chronology was decided by a field that stopped updating

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
8). Every consumer was checked first for equality-on-a-bare-date-string; none
does, so widening the field to a full timestamp is safe for ordering and range
queries.

---

## Found, not yet fixed

Ranked by what they cost a real user.

### 5. Stored evaluations are in two different units, inside the same field

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

### 6. Half of every game is never analysed

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
measurement question — the pilot already answered it (finding 10) and the
compute is better spent elsewhere. Do analyse both sides **going forward**, for
the coaching category. The pilot script shows the shape; depth 12 (the
codebase's `QUICK_DEPTH`) is adequate for a blunder rate.

### 7. 13% of blunders carry no cognitive gap

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

### 8. 261 games have no usable date at all

Left behind by the migration. They cannot be ordered, so they are invisible to
every before/after measurement and to "your recent games." 1.7% of the corpus.

**The fix.** They still have PGNs. Re-parse the PGN `[Date]`/`[UTCDate]` tags
directly; where the PGN has none either, fall back to the import timestamp and
mark the row as approximate rather than leaving it unsortable.

### 9. The material-claim verifier lets two classes through

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

### 10. Rating change mostly cannot be attributed, and that is the finding

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

### 11. The evidence a coaching claim would need does not exist yet

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

The caption suite is green: 455 passed, 0 failed. Separately, 53 API and
integration tests fail in a plain checkout because they need a live server and
database; that is unchanged by this work and verified against the pre-change
tree.

---

## Deliberately not done

- **Backfilling opponent analysis across 14,839 games.** The measurement
  question it would answer is already answered (finding 10). Analyse both
  sides going forward instead.
- **Picking a threshold for the material-claim verifier** (finding 9). Not
  measured yet, and a threshold chosen before the distribution is a guess.
- **Fixing the 53 integration-test failures.** They need a running stack; that
  is an environment task, not a correctness one.
