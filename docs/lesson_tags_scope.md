# Lesson tags — scope

Status: **DRAFT, awaiting Mohit signoff.** No code until signed.
Written 2026-11-19.

---

## 0. Existing surfaces audit — decision: **the blocker is review, not code**

> **Rewritten 2026-11-19 after the audit below was traced to its cause.** The
> first draft of this section said the tag was missing and three gaps needed
> building. That was wrong, and the correction matters more than the original
> plan: **nothing is missing. Every principle detector is switched off on
> purpose, and switching one on is a review job with a locked bar, not a
> code change.**
>
> Verified 2026-11-19, in this order:
>
> 1. `caption_pipeline.py:8558` passes every detected principle through
>    `detector_quality.can_influence(quality_id, CAPTION)`, and line 8597
>    overwrites `caption_facts["principles_violated"]` with whatever survives.
> 2. Nothing survives. `grade_for("principle:<id>")` returns **shadow for all
>    41 ids in use** — only 3 `principle:` ids are registered at all, and
>    unregistered ids fail closed to shadow by design
>    (`detector_quality.py` `_UNKNOWN`). So the list is emptied on every card,
>    which is the 0% measured below.
> 3. Promotion out of shadow needs a human-reviewed evidence packet:
>    **≥50 reviewed fires, precision Wilson-95 lower bound ≥85%, ≥20 true
>    negatives.** That bar is not advisory — on 2026-09-19 Mohit reverted a
>    promotion that stood at 49 reviewed fires, hours after making it.
> 4. The queue that makes that evidence already exists and is live:
>    `/admin/detector-review` auto-generates **one queue per principle** from
>    `caption_principles.PRINCIPLES`, so no principle can silently miss it.
> 5. Rulings stored in production today: **267 in total, of which 2 are on
>    principles** — one `unsure` on `DEF_MOST_ATTACKED`, one `false` on
>    `DEF_WALK_KING`. Against a bar of 50 each.
>
> So V1 is not "author maxims and wire them up". V1 is: **rule enough fires to
> promote the first principle, then render it.** The authoring and the render
> are small; the review is the project. At roughly the pace of the
> `discovered_attack` review (64 rulings over three sittings) one principle is
> about one sitting's work.
>
> Worth stating plainly, because it reframes the whole feature: the lesson
> layer has been correct and silent since May 2026 — the newest
> `user_teaching_memory` row is **2026-05-18** — and nobody noticed, because
> no screen has ever consumed it. The missing artefact was never the detector
> or the sentence. It was a reader.
>
> **Proof the path works end to end, same day:**
> `tactic:discovered_attack_with_stored_payoff` was the one detector already
> over its bar — 53 clean rulings, 52/52 precision, Wilson 93.1% — and sat at
> shadow for two months because nobody re-checked the gate after seven late
> rulings landed. Promoting it (commit `a7b126bd`) changed **20 real captions**
> on Mohit's own ruled positions. That is the exact loop every principle has to
> walk, now walked once.

### Original audit (kept; its measurements stand, its conclusion did not)

What already exists for "something to remember":

| surface | rows | what it already provides |
|---|---|---|
| `move_observations` | 736,202 | per-move mechanism flags, **both sides**: `destination_safety_exact`, `ignored_opponent_threat` (mistake side), `missed_free_piece`, `missed_opponent_blunder`, `missed_pattern` (opportunity side), plus `execution_quality`, `found_best_in_critical` |
| `user_pattern_events` | 165,204 | cross-game events keyed on `pattern_id`, with cp_loss, fen, outcome, detector and catalog versions |
| `user_teaching_memory` | 28,333 | per-move teaching record, already carrying `principle_id`, `anchor_name`, `behavioral_tags`, `focal_squares` |
| `principle_bank.json` + `caption_principles.py` | 6 buckets × 3 lines | the current selector: bucket key `{phase}_{severity}`, then **pick by FEN hash** |
| card fields `principle_id_used`, `concept_id`, `concept_type`, `concept_applied` | — | the slots a lesson tag goes in |

**Measured 2026-11-19, prod, cards at v249 (702 games, 2,033 user-mistake cards):**

```
principle_id_used : None on 2,031 of 2,033   (2 carry TAC_TRAPPED_PIECE)
concept_id        : None on all 2,033
tactic_trigger    : present on ~5%
```

**Overlap, stated honestly.** Mechanism detection exists. Cross-game aggregation exists.
A principle slot exists on both the card and the teaching memory. Nearly the whole
machine is built.

**The lesson library already exists** (measured 2026-11-19). `user_teaching_memory.principle_id`
is populated on **24,749 of 28,333 rows (87%)**, across **41 distinct ids**, and it is
already the vocabulary this feature wanted:

```
TAC_CHANGED_AFTER_MOVE        3,360  13.6%   cum  13.6%
TAC_CHECKS_CAPTURES_THREATS   2,957  11.9%   cum  25.5%
TAC_HANGING_PIECE             2,704  10.9%   cum  36.4%
TAC_DISCOVERED_PATTERN        1,759   7.1%   cum  43.6%
TAC_PIN_PATTERN               1,685   6.8%   cum  50.4%
OP_SAME_PIECE_TWICE           1,414   5.7%   cum  56.1%
OP_FINISH_DEVELOPMENT           947   3.8%   cum  59.9%
...                                          cum ~95% by id 22
tail: TRAP:<name> ids, 1–21 rows each
```

Five ids cover half of all tagged moves; roughly twenty cover 95%. That sets the library
size from the data rather than from taste.

`pattern_catalog.json` additionally maps **76 detectors** to `human_name`, `short_description`,
`family` and `canonical_concept_id` — authored 2026-05-23 for, in its own words, *"user-facing
memory ('you understand X', 'you missed Y again')"*. It was built for this and never surfaced.

**Genuine differentiation — three gaps, and only three:**

1. **No imperative maxim.** The catalog gives a name ("Free piece win") and a description,
   never the rule — *"Loose pieces drop off."* That sentence is the missing artefact, and
   it is needed for ~20 ids, not 76.
2. **Nothing writes the card slot.** Four tag fields on every card; all empty. The tag
   exists one table away, joinable on `(game_id, move_number)`.
3. **Nothing reads the aggregate back.** 24,749 tagged moves and 165,204 pattern events,
   and no screen anywhere says "this is the 4th time."

**Vocabulary drift, found during this audit:** `pattern_catalog.json` defines **10**
`canonical_concept_id` values (58 of its 76 detectors have none), while
`user_teaching_memory` uses **41**. Six of the top eight in-use ids appear in the catalog;
`MID_ROOK_OPEN_FILE` and `OP_FINISH_DEVELOPMENT` do not. Two vocabularies, partly agreeing.
Reconciling them to one list is a pre-code gate, not a V1 feature.

The existing bank is the only thing that tried to fill the slot, and it is keyed on
phase, severity and a hash of the position — i.e. on nothing that happened in the game.
It is not extended. It is switched off.

**Decision as first written: EXTEND.** ~~This is a mapping table plus two pieces
of wiring, not a new system.~~ Superseded by the block at the top of this
section: the wiring is already there and the gate is a human-review bar. The
correct decision is **promote one principle through the existing review queue,
render it, then repeat** — and the first V1 task is a review sitting, not a
file.

---

## 1. What it is

Every coaching moment ends with one named thing to remember — a short sentence like
*"Before you move a piece, check what it was guarding"* — and it is chosen because of
what actually happened on that board, never because of the phase of the game or how bad
the move was. The same named lesson covers both sides of the same idea: it fires when
you walked into something, and when you missed the chance to do it to someone else.
Because the lesson is named and there are only a dozen or so of them, it accumulates:
the player stops seeing a number and starts seeing *"this is the fourth time, and here
are the games."*

---

## 2. What the user sees

### On a card, mistake side

```
  Qh4 · move 16

  Your queen on d8 is the second defender of the rook on f8, and the
  knight on e6 is already hitting it. Once she leaves d8, the rook has
  only the king left, and White takes it.

  ┌────────────────────────────────────────────────────────────┐
  │  REMEMBER                                                  │
  │  Before you move a piece, check what it was guarding.      │
  │                                                            │
  │  4th time — vs Titanit1, vs KPCA-IND_136, and twice here.  │
  └────────────────────────────────────────────────────────────┘
```

### On a card, opportunity side (NOT in V1 — shown here so the shape is agreed)

```
  ┌────────────────────────────────────────────────────────────┐
  │  REMEMBER                                                  │
  │  Loose pieces drop off.                                    │
  │                                                            │
  │  Same lesson as your game vs pelapasion — there you were    │
  │  the one who lost the piece.                               │
  └────────────────────────────────────────────────────────────┘
```

### What is never shown

- percentages ("you breached this in 60% of games")
- month buckets ("October vs November")
- a lesson on a card whose mechanism was not proved on the board

The count is expressed as **named games the player can open**, never as a rate.

---

## 3. In scope (V1)

- **One imperative maxim authored per principle id**, for the ids covering ~95% of tagged
  moves (about 20 of the 41 in use). Not a new taxonomy — a sentence added to the one that
  already exists.
- The card writer fills `principle_id_used` by joining the move to
  `user_teaching_memory` on `(game_id, move_number)`. The tag is read, not re-derived.
- The maxim renders on the card as its own block, under the explanation.
- The repeat line — "Nth time" plus the named games — read from `user_pattern_events`.
- **Mistake side only.**
- `principle_bank.json` and its phase+severity+hash selector are switched off, and the
  file is deleted rather than left to rot.
- A guard test: a card may not carry a maxim unless the move carries a proved mechanism.

## 4. Explicitly out of scope (V1)

- **The opportunity side.** The mirror detectors measured 2 of 16 and 3 of 80 fires true.
  A memorable sentence on a false claim is worse than filler, because the player remembers
  it and it is wrong. It enters when each detector earns it, one at a time.
- **The "normally players at your level play this" framing.** That depends on the Maia
  likely-moves work, which is a separate scope and currently produces ~1.2 positions per
  game with a depth-fragile threshold.
- **A lessons page or player profile of maxims.** V1 puts the tag on the card. Reading
  all of a player's maxims in one place is the obvious next surface, not this one.
- **Backfilling historical cards.** New and re-rendered cards only.
- **Teaching a lesson.** The tag names the thing to remember; it does not open a drill,
  a puzzle set or a curriculum item.
- **Per-rating rewording.** One sentence per mechanism, same at every level, in V1.

## 5. Success criteria

1. **Correctness before coverage.** On a hand audit of 50 tagged cards, the maxim matches
   the mechanism that was actually proved on the board in **50 of 50**. One mismatch
   fails V1 — a wrong memorable sentence is the thing this is meant to prevent.
2. **No generic fallback ever fires.** Count of cards carrying a maxim without a proved
   mechanism is **0**, enforced by the guard test, not by inspection.
3. **The repeat line is real.** For cards showing "Nth time", every named game opens and
   contains the same mechanism. Spot-checked on 20.
4. **It reaches the screen.** The maxim is visible on the rendered card at
   `/game/:gameId` — verified by opening the page, not by reading the database.
5. Coverage target is deliberately **not** a V1 criterion. Tagging more cards is easy and
   is the wrong thing to optimise first.

## 6. Open questions

**Q1. ANSWERED 2026-11-19.** `user_teaching_memory.principle_id` is populated on 24,749 of
28,333 rows (87%), across 41 ids. The library exists and is assigned at scale. This is why
V1 authors sentences rather than a taxonomy.

**Q1b. Which of the two vocabularies is the source of truth?**
`pattern_catalog.json` defines 10 `canonical_concept_id` values; `user_teaching_memory` uses
41; they agree on 6 of the top 8.
Why unresolved: product call, and it decides what the maxims are keyed on.
Unblocking step: Mohit picks one. Recommendation: the 41 in use, because it is what is
actually assigned to moves — and the catalog's names and families then hang off it.

**Q1c. How is `principle_id` assigned — by proved mechanism, or by category?**
PARTLY ANSWERED 2026-11-19. It is assigned by a **coded board predicate**, not by
category: each of the 41 ids has a `_p_*` function in `caption_facts.py` that
reads the position, and `_principles_violated(facts, board_before)` runs them in
registration order. So this is not a second, larger principle bank — the old
bank picked by `{phase}_{severity}` and a FEN hash, these read the board. What
is still unmeasured is whether each predicate is *right*, and that is exactly
what the review queue measures, one fire at a time.
Unblocking step: no longer a hand-check — it is the review sitting itself. The
precision figure the queue produces *is* the answer to this question, which is
why the bar exists.

**Q1d. Which principle is reviewed first?**
Why unresolved: product call, and it decides where the first sitting goes.
Recommendation: `TAC_HANGING_PIECE`. It is the most-fired id in the corpus
measurement (78 of 1,108 fires over 1,878 moves), it is one of only three
`principle:` ids already carrying an evidence reference, and its stated
limitation is recall — which Caption grade does not require, because a caption
detector may safely stay silent.
Unblocking step: Mohit picks, then rules at `/admin/detector-review`.

**Q2. Do `move_observations` flags agree with the v249 detectors?**
Why unresolved: the observations layer and the card detectors were built at different
times, and the local container's code is at v238 while prod cards are at v249.
Unblocking step: sample 100 moves, compare the flag against the live detector result.

**Q3. PARTLY ANSWERED 2026-11-19.** The distribution is measured: 5 ids cover 50% of tagged
moves, ~20 cover 95%, and the tail is `TRAP:<name>` ids with 1–21 rows each. The remaining
call is where exactly to cut — at 95%, or lower to keep the library smaller.
Unblocking step: `/lock-via-data` on that cut.

**Q4. What repeat count earns the "Nth time" line?**
Why unresolved: same reason — threshold before distribution is the recurring sin here.
Unblocking step: distribution of per-user repeats per mechanism, then `/lock-via-data`.

**Q5. Does the maxim replace the caption's closing sentence, or sit in its own block?**
Why unresolved: product call. The existing rule is that the caption keeps an explicit
principle ending, which may now be the maxim itself rather than a second sentence.
Unblocking step: Mohit.

## 6b. One principle is currently unreviewable — found 2026-11-19

`/admin/detector-review`'s principle producer calls `extract_facts` with
`move_history_san=[]`, and says so in its own docstring. `extract_facts`
replays the history onto `board_before` so the predicates can read
`board_before.move_stack`; with no history there is no stack.

Measured, with a positive control, because a zero on its own proves nothing:

* Over 60 real games / 1,878 user moves, replaying the full history (opponent
  plies recovered by matching each legal move against the next stored
  `fen_before`) changed **0 of 27 principles' fire counts**. So the empty
  history is harmless for 26 of them.
* The positive control fires: on `1.e4 e5 2.Nf3 Nc6 3.Ng5?!`,
  `OP_SAME_PIECE_TWICE` appears **only** when the history is supplied. It is
  the 6th most-assigned id in `user_teaching_memory` (1,414 rows) and it fired
  **0 times in both arms** of the corpus run.

So `OP_SAME_PIECE_TWICE` cannot be served by the queue, cannot be ruled, and
therefore can never be promoted. The history is reconstructable exactly — the
probe did it for 60 of 60 games — so this is a contained fix to the producer,
not a redesign. It is listed here rather than fixed silently because it changes
which principles are reachable at all.

(The first version of that probe reported a false zero: it never supplied
White's opening ply for games where the user is Black, so every such game fell
back to a FEN-only board and matched the empty arm. The control is what caught
it.)

## 7. Pre-code requirements

Each is a hard gate.

1. **Mohit has explicitly signed off on this document.**
1b. **One principle has reached Caption grade through `/admin/detector-review`.**
   Nothing renders before that, and no amount of code changes it. The bar is
   ≥50 reviewed fires with a Wilson-95 lower bound ≥85%; today the whole
   principle family has 2 rulings. Run
   `scripts/replay_detector_rulings.py <queue>` before changing any grade, so
   rulings on claims the code has since withdrawn are not counted — that is
   the step whose absence caused the 2026-09-19 revert.
2. The mechanism→maxim table is authored and reviewed, one maxim per mechanism, no
   mechanism with two possible sentences.
3. Q3 and Q4 thresholds locked via `/lock-via-data` from the actual distributions.
4. Q2 answered, and **Q1c answered** — the writer of `principle_id` has been read and 30
   assignments hand-checked against the board. If assignment is by category rather than by
   proved mechanism, V1 stops and the problem changes.
5. Q1b decided: one vocabulary, not two. The catalog's 10 `canonical_concept_id` values and
   the 41 ids in use are reconciled to a single list before any maxim is written against them.
5. The local container is rebuilt to current code — it reports `V5_COACHING_VERSION = 238`
   while prod cards are at v249, so anything measured locally today is measured against
   stale rules.
6. The render path is confirmed to the screen: which field the card component actually
   displays, verified by opening a game page, not by grepping.
7. `/audit-pre-code` run before the first file.
