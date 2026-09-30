# The missing-why queue: what is actually wrong, measured

**Status:** measurement only. No code, no scope. Written because Mohit asked
(2026-09-30) to take every "missing the why" position off
`/admin/geometry-gaps` and work out *why* first, "so we can see what really to
build".

**Scale of the read:** all 17,346 `game_analyses` documents that carry stored V5
captions — 203,022 mistake/blunder captions. Measured against prod data through
the local container. Every number below is from that full pass, not a sample.

---

## 0. The short version

The queue is not a backlog of chess positions waiting for a human to explain
them. It is a measuring instrument pointed at the wrong number, sitting on top
of several separate code defects.

Every one of the 152,519 faulted cards was re-rendered through today's pipeline.
**Only 8.0% are merely stale** — the other 92% stay bare under deployed code, so
this is not a freshness problem that a regeneration would clear. The causes are
concentrated: opponent-side silence (36.2%), no punishment line to explain from
(26.9%), and one rule, `R12_blunder`, going bare on user moves that *do* have a
line (21.2%).

Hand-authoring was never going to reach the end of this. Since the queue
shipped on 2026-09-22 it has produced **8 rulings** — 4 authored, 4 skipped —
against a population of **25,795** by its own definition, and the endpoint
rescans all 17,346 caption-bearing games on every single request.

---

## 1. Why each card is bare, attributed

Every one of the 152,519 faulted cards was re-rendered through today's pipeline,
replaying the stored engine evidence (`allow_fresh_engine_verification=False`,
so no engine is launched — leaving it at its default spawns a Stockfish verifier
per call and one position took 95 minutes). Causes are first-match-wins:

| cause | cards | share |
|---|---:|---:|
| **opponent_side** — the opponent path states severity and stops | **55,164** | 36.2% |
| **no_line_stored** — no punishment line to explain from | **41,004** | 26.9% |
| **other_bare** — has a line, user-side, still renders bare | **32,340** | 21.2% |
| **stale_stored** — today's code DOES explain it; the row is old | **12,226** | **8.0%** |
| verifier_recovery — a why was built, the verifier rejected it, recovery went quiet | 6,199 | 4.1% |
| mate_path — `R01_mate`, a forced mate known and unnarrated | 4,647 | 3.0% |
| generic_stub — one fixed sentence for any position | 939 | 0.6% |

**Only 8.0% are stale.** Re-rendering the corpus fixes one card in twelve; 92%
stay bare under the code deployed today. That settles the question of whether
this is a data-freshness problem. It is not.

Structural class of the *re-rendered* text: NO_WHY 70.4%, ALT_WHY_ONLY 20.2%,
PLAYED_WHY 9.4% — the 9.4% being almost exactly the stale group recovering.

`R12_blunder` owns the largest single cell: 30,311 of the 32,340 `other_bare`
cards. That rule, on user moves with a line available, is the core gap.

**Limitation, stated because it inflates bareness by some unmeasured amount:**
the replay passes `move_history_san=[]`, since the V5 record does not carry the
move list. Any caption path that needs the history — opening naming, recurrence
framing — is starved in this pass and would render better in production. It does
not affect the cause split for `opponent_side` or `no_line_stored`, which turn on
fields the record does carry.

## 2. The instrument disagrees with itself

Two definitions of "does this caption have a why" live in this repo, and only
one of them feeds the queue.

| | what it is | used by |
|---|---|---|
| `services/caption_why_heuristics.has_why` | keyword scan — any square, any piece noun, or any of ~20 connector words | `/admin/geometry-gaps/no-why/next` |
| `scripts/caption_why_class.classify_caption_why` | structural — splits the caption at the "was better" boundary and asks what is said on each side | the audit scripts |

Run over the same 203,022 captions:

| | count | share |
|---|---:|---:|
| `has_why` says fine | 177,227 | 87.3% |
| structurally **PLAYED_WHY** — says what was wrong with the move played | 52,574 | 25.9% |
| structurally **ALT_WHY_ONLY** — only says why the *other* move was good | 34,267 | 16.9% |
| structurally **NO_WHY** | 116,181 | 57.2% |

The "~88% of cards already carry a position-specific why" figure is `has_why`
saying so. The structural classifier, on the same corpus, says 57.2% carry
nothing. Where they disagree:

| structural class | `has_why` verdict | count |
|---|---|---:|
| NO_WHY | passes | **92,457** |
| ALT_WHY_ONLY | passes | 34,267 |
| PLAYED_WHY | passes | 50,503 |
| NO_WHY | faulted | 23,724 |
| PLAYED_WHY | **faulted** | **2,071** |

The queue hides 92,457 bare cards and shows 2,071 clean ones.

### What it hides

Most common shapes among the 92,457, after collapsing move names:

| count | shape |
|---:|---|
| 4,455 | *"&lt;M&gt;. Their position collapses — you have a winning attack here. Look for the strongest continuation."* |
| 2,549 | *"Opponent's &lt;M&gt; is a mistake. Play &lt;M&gt;+ — it forces a reply."* |
| 1,940 | *"&lt;M&gt; — the position was already lost before this move."* |
| 1,900 | *"Opponent's &lt;M&gt; is a mistake. Play &lt;M&gt;."* |
| 1,177 | *"&lt;M&gt; is fine — you're still winning. &lt;M&gt; would have kept the pressure on."* |

The 1,940 "already lost before this move" cards break the undramatic-tone rule
outright. The 1,177 "is fine" cards are labelled mistake or blunder.

### A keyword scan cannot be fixed with more keywords

`has_why` misses `runs into` and `allows`, and its `SQUARE_RE = \b[a-h][1-8]\b`
cannot see a square inside a capture — `\b` fails between the `x` and the `d`
in `Qxd3`. Adding all three removes 8,818 cards from the queue, but only
**1,768 of them deserve removal**. The other 7,050 are genuinely bare and would
simply become invisible.

Of the 1,768, `runs into` explains 1,633 and the square regex explains 1 on its
own.

That is the argument for replacing the gate rather than patching it.

---

## 3. The evidence on screen is truncated — but the engine fix already shipped

`pv_after_played` is the punishment line — what a caption needs in order to say
what the move let happen.

**The code is already correct.** `PUNISHMENT_PV_PLIES = 12`
(`stockfish_service.py:60`), and its comment records two hand-checked cases lost
at ply 5–6. What is wrong is the stored corpus, which predates that change.
Stored line length by the day V5 was generated:

| day | no line | 4 plies | 12 plies |
|---|---:|---:|---:|
| 2026-09-22 | 222 | 1,679 | 0 |
| 2026-09-24 | 171 | 1,120 | 0 |
| **2026-09-25** | 460 | 1,094 | **535** |
| 2026-09-27 | 197 | 108 | 770 |
| 2026-09-30 | 57 | 38 | 262 |

The fix landed on **2026-09-25**, five days ago. 4-ply rows sit at
`decryption_v5_version` 133–166; 12-ply rows at 177–181.

So this is a regeneration job, not an engine change. Note also that the
**no-line** class does not improve across the crossover — it is still being
written daily, so it is a separate, live gap.

Pushing every stored line on the board and asking whether anything is settled
inside it:

| | count | share of the 152,519 faulted rows |
|---|---:|---:|
| no line stored at all | 42,132 | 27.6% |
| line stored, **never resolves** — no mate, no material change | **57,395** | 37.6% |
| resolves: material changes hands | 49,286 | 32.3% |
| resolves: mate inside the line | 3,575 | 2.3% |
| line illegal against the stored FEN | 131 | 0.1% |

**Of the 110,256 rows with a playable line, 52.1% never resolve inside it** —
102,652 rows are exactly 4 plies.

For those cards there is nothing to state. No template, no detector and no
human author can name a consequence the stored evidence does not contain.
Counting the rows with no line at all, **65.3% of faulted cards have no usable
consequence evidence** — which is what a player sees today, five days of new
rows aside.

---

## 4. Severity and caption text come from different classifiers

6,729 user cards are labelled `blunder` while losing under 100 centipawns —
2,265 of them under 1cp. `opp_blunder` has 4 such rows in 21,209, so this is
user-side only.

The label is **not** the bug. All 6,729 fire `walked_into_mate` in
`services/severity.py:127`, and resolving the sign per the user's colour from
`fen_before`, **all 6,729 are genuinely being mated**. Only 9 rows in the whole
corpus are the opposite, delivering-mate direction — so the known
WHITE-relative mate trap is not what is happening here.

The **caption** is the bug. `severity` comes from cp_loss plus the mate
sentinel; the caption text is built from cp_loss alone. They are computed by
different code and never reconciled, so 514 cards read like this:

> `[severity blunder, cp_loss 0, eval −9990]`
> **"Good move. You moved your king to a calm, safe spot with Kf4. From here it
> can do more later. Lesson: when the game is quiet, put each piece on a safe
> square where it can help you."**

The player is about to be mated. We call it a good move and tell them the
position is quiet.

This is live, not historical: such rows were written every day through
2026-09-30, at `decryption_v5_version` 171–175.

A human cannot write "why this was a blunder" for a card that first has to stop
contradicting itself. These belong in a correctness fix, not an authoring queue.

---

## 5. Self-contradiction is widespread, not confined to the mate case

Across the 152,519 faulted rows — comparing our own label to our own text, no
chess judgement involved:

| pattern | rows | user | opponent |
|---|---:|---:|---:|
| calls it "an inaccuracy" on a mistake/blunder card | 16,623 | 5,288 | 11,335 |
| "still winning" / "you have a winning attack" | 7,938 | 3,325 | 4,613 |
| "the position was already lost before this move" | 6,593 | 1,980 | 4,613 |
| "is fine" / "is playable" | 4,006 | 4,005 | 1 |
| "the real fix is earlier" — defers and never says where | 3,506 | 3,506 | 0 |
| praises the move outright | 2,580 | 857 | 1,723 |

---

## 6. The opponent side is the biggest block, and its evidence is already stored

85,394 of the 116,181 NO_WHY cards are opponent moves — **84.6% of all opponent
cards** say nothing about why the move was bad.

This is not a data gap. Of those 85,394:

| | count | share |
|---|---:|---:|
| have a best move **and** a punishment line | **52,468** | 61.4% |
| have cp_loss | 85,394 | 100% |

The "opponent moves have no engine truth" finding concerns
`stockfish_analysis.move_evaluations`, which stores user moves only. The V5
records are a different store, and they do carry opponent evidence.

So for 52,468 opponent cards the evidence is present and unread, and the
caption still says *"Opponent's Bxe5 is a mistake."*

---

## 7. The played-move reason is gated on the punishment line, not on branch order

**This section replaced its first version on 2026-09-30 after the fix for it
produced a zero delta.** The original claim was that
`caption_fallback_tiers.tier23_caption` tried the best-move why before the
played-move consequence, and that swapping two branches would convert ~8,500
cards. The ordering bug there is real and is fixed, but re-rendering 5,000 rows
before and after gave a byte-identical class distribution: `tier23_caption`
renders approximately none of this corpus. The original measurement read
`debug_facts` to see which facts were *available* and never checked which rule
actually produced the card — an availability count is not a producer count.

**`R12_blunder` produces 80.1% of ALT_WHY_ONLY**, and its template order is
already right: `user_with_failure_and_alternative` —
`{played_san} {failure_clause}. {best_move_san} was better — {why_clause}` —
ranks first among the user variants. It leads with the played move's failure
whenever `failure_clause` exists.

So the question is what makes `failure_clause` exist. All nine of R12's
`failure_mode_clauses_user` predicates key on `opp_reply_*`, which is **ply 1 of
the stored line and nothing else**. Walking 12,000 stored lines:

| the line first resolves at | rows | share |
|---|---:|---:|
| never | 4,460 | 37.2% |
| **ply 1** — the only ply any predicate reads | 3,221 | 26.8% |
| ply 2 | 1,325 | 11.0% |
| **ply 3** | 2,103 | **17.5%** |
| ply 4 | 762 | 6.3% |
| ply 5+ | 129 | 1.1% |

**36.0% resolve later than ply 1, where no predicate can see them.** And line
quality gates the outcome directly — the same rows, split on their stored line:

| stored line | n | PLAYED_WHY | ALT_WHY_ONLY | NO_WHY |
|---|---:|---:|---:|---:|
| resolves | 1,355 | 19.5% | 16.1% | 64.4% |
| unresolved | 1,530 | 10.2% | 34.7% | 55.1% |
| no line | 1,115 | 2.7% | 4.4% | 92.9% |

A predicate that walks the engine's own stored line and names the capture at
ply >= 2, firing only when the line *ends* with the mover down material so a
trade inside the line is not reported as a loss. It **ships for opponent moves
and is withdrawn for user moves**, and that difference is the lesson here.

`line_loss_*` is mover-relative, so on an opponent move it already names a
piece the OPPONENT loses -- which is the user's opportunity.

Measured by re-rendering ALL 152,519 faulted cards, not a sample:

| | firings | precision | cost |
|---|---:|---|---|
| opponent clause | **7,142** | **100.0000%** | none found |
| user predicate | 2,690 | 100% | **248 cards lost their R12 caption** |

The opponent side moved exactly one thing in the whole population: NO_WHY ->
PLAYED_WHY 7,142. Zero played-why losses, zero leakage onto user cards.

The user side was right about its claims and still withdrawn. It cost 248 user
cards their R12 caption -- the card fell through to a promoted tier rule with
weaker text, 179 of them ALT_WHY_ONLY -> NO_WHY -- plus 4 that lost a working
played-why and 14 that crossed the word cap. It is causal, not coincidental:
the fact is set on **14.0%** of random user cards and **100%** of those 248.
But the mechanism is not understood -- the first hypothesis (its
`teaching_principles` entry pulling variant selection toward a shape that drops
the best move) was measured and wrong, and R12's suppression does not reference
`failure_clause` -- so it does not ship on a 10:1 trade. The facts and glossary
remain; the predicate is unwired, and
`tests/test_line_material_loss_why.py` records why, so re-wiring is deliberate.

Position matters: mid-list the predicate pre-empted the ply-1 ones, and where
the verifier then rejected it, recovery dropped the failure clause altogether
-- 48 cards into recovery and 3 lost played-whys. Last, it can only add.

One precision gap, now closed: when a stored line goes illegal partway,
production judged "the line ends down material" on the truncated prefix. That
was the sole cause of 3 unprovable firings; the fact is now abandoned instead.

### The floor beneath it stopped going silent

Verifier recovery built its text from `severity_practical`, which reads "good"
on cards the canonical tier calls a mistake, so its severity phrase came out
empty and it fell through to `recovery = f"{played_san}."` -- a caption that
says nothing at all. **171 cards corpus-wide rendered as a lone SAN.** Recovery
now names the stronger move, which that function's own contract already lists
among the irreducibly-true claims it may make.

Bare-move captions **171 -> 0**. "Rxa7." now reads "Rxa7. Qc5+ was stronger
here." All 151 user-side text changes in the whole population are this.


## 7a. The original branch-order finding, kept because the bug is real

In `caption_fallback_tiers.tier23_caption`
(`caption_fallback_tiers.py:104-118`) the two candidate explanations were tried
in this order. This path renders almost nothing today, so fixing it changed no
measured card — but the ordering was wrong and a fallback that fires tomorrow
should not ship the bug:

```
if why and cp >= _INACCURACY_CP:          # the BEST move's why  -> ALT_WHY_ONLY
    return f"{who} played {played}; {best} was stronger — it {why}."
if cp >= _MISTAKE_CP:                     # the PLAYED move's consequence -> PLAYED_WHY
    return f"... {played} runs into {opp}, taking {whose} {cap_pt}."
```

The played-move consequence — the thing the student actually asked for — is
only reached when the best-move why is **absent**. Rendering 500 ALT_WHY_ONLY
cards and inspecting the facts each had available:

| | share |
|---|---:|
| only the best-move why was available | 65.6% |
| **both were available** — branch order alone decided | **24.8%** |
| neither | 9.0% |
| only the played consequence | 0.6% |

Rendering 500 ALT_WHY_ONLY cards showed 24.8% held both facts. That number is
what suggested a large win here, and it was misread: it measures fact
availability, not which rule rendered the card. The same reorder is applied, and
it also stops the best-move why pre-empting the forced-mate branch further down
the same function — a move allowing mate in two could render as "Qxh4+ was
stronger — it develops a piece". What the shape costs when it does fire:

> *"Your opponent played h4; Bh4 was stronger — it moves your bishop out of
> danger."* — while the available consequence was `hxg5 takes bishop`.

The card recommends rescuing the bishop and never says that the move played
loses it.

## 8. The card can name the wrong player as the mover

`is_user_move` is sound: checked against the side to move in `fen_before`, it is
self-consistent in **all 16,716 games** (user rows one colour, opponent rows the
other, no game mixed). The flag is right and the text is wrong.

| | count |
|---|---:|
| opponent's move, caption names the player as mover | **4,263** |
| player's move, caption names the opponent as mover | 359 |

> `side=opponent` → *"You played Qxd5; Nxd4 was stronger — it trades his pawn."*

Separately, the possessive inside the why clause is never re-owned. The sentence
frame was fixed with `_subject`/`_poss` (`caption_fallback_tiers.py:88-98`), but
`best_move_why` arrives pre-built as a string. Of the 238 correctly-subjected
opponent cards carrying such a clause, **47 (19.7%)** say "your":

> *"Your opponent played Qd2; Qd5 was stronger — it defends **your** pawn on
> b5."*

One more shipped-string defect visible while counting these: *"Your opponent
tidys up the king"*.

## 9. The gap is uniform across players

Of the 54 users with 50 or more faulted cards, the NO_WHY share of their cards
runs from 69.6% to 82.5%, median **76.3%**. No cohort is served notably better.

This answers the launch question directly: the defect is in the pipeline, not in
any particular player's data, so going live would explain equally poorly to
everybody.

## 10. The review prompt reads four fields off the wrong record

`/admin/geometry-gaps/no-why/next` passes `cognitive_gap`, `critical_reason`,
`threat` and `mate_info` into the "Copy for Claude" prompt, with a comment
stating the analyser already wrote all four and the page failed to pass them on.

Measured with a positive control on both sides (`caption` 17,347,
`best_move_san` 17,318 confirm the probe works):

| field | present on a V5 record | present in `stockfish_analysis.move_evaluations` |
|---|---:|---:|
| `cognitive_gap` | **0** | 16,064 |
| `critical_reason` | **0** | 16,686 |
| `threat` | **0** | 17,113 |
| `mate_info` | **0** | 9,631 |

The analyser did write all four — into `move_evaluations`. The V5 record never
receives them, and the endpoint reads them off the V5 record. So the prompt
Mohit and Farhan see has four empty slots, and the comment explaining why they
were added is wrong about where the data lives.

---

## 11. What this says to build, in order

Updated 2026-09-30 after verifying on all 152,519 cards. Items marked DONE were
measured, not assumed; two items shrank to nothing when dated.

**Done**

1. **Queue gates on `caption_why_class`, not `has_why`**
   (`admin_positional_reasons.py`). 2,071 clean cards leave the human queue,
   92,457 bare ones become visible, and `why_class` splits NO_WHY from
   ALT_WHY_ONLY because they want opposite fixes.
2. **Opponent moves read the punishment line past ply 1.** 7,142 cards, every
   claim proved on the board, nothing else in the population moved. This was
   the single biggest cause at 36.2%.
3. **Verifier recovery stops going silent.** Bare-move captions 171 -> 0.
4. **`_recommended_move_why` stops guessing the owner** -- three branches said
   "your" about the mover's pieces regardless of who moved.
5. ~~tier23 branch order.~~ Fixed; changed zero cards. Section 7a.

**Withdrawn, on evidence**

6. **The user-side deeper-line predicate.** Correct claims, 248 cards worse.
   Section 7. Re-wiring needs the mechanism understood first.

**Still open, but re-measure before starting**

7. **`R12_blunder` bare on user moves that have a line** -- 30,311 cards, the
   largest single rule/cause cell. The withdrawn predicate was one attempt at
   this; the cause table needs recomputing first.
8. **Reconcile severity with the caption text.** 514 cards say "Good move"
   where the engine says the player is being mated.
9. **Point the review prompt at `move_evaluations`** for `cognitive_gap`,
   `critical_reason`, `threat` and `mate_info` -- present on 0 V5 records and on
   16,064 / 16,686 / 17,113 / 9,631 analyses.
10. **Store a punishment line where there is none** -- 41,004 cards, and this
    does not improve across the 2026-09-25 crossover, so it is live.

**Shrank to nothing when dated**

11. ~~Mover attribution, 4,263 cards.~~ Games holding one fell from 104/day on
    2026-09-22 to 1 on 2026-09-30. ~95% already fixed; what is left is stale
    stored rows.
12. ~~Raise the PV length.~~ `PUNISHMENT_PV_PLIES` has been 12 since
    2026-09-25.

**The prerequisite for everything above**

13. **Re-render the corpus, then re-measure.** The stored corpus spans **40
    code versions**: 67.3% of games are at v135 and **0.4% at the current
    v182**. Items 11 and 12 both looked like live defects in that data and were
    not. `scripts/regen_v5_decryption.py` exists, needs no engine, and is
    resumable -- it re-renders captions from the stored `move_evaluations`.
    Deploy first, or it bakes the old code into fresh rows.

    It does NOT lengthen the lines: **98.2% of stored
    `move_evaluations[].pv_after_played` are exactly 4 plies**, so the short
    lines live in the analysis. The 34.8% of lines that resolve at ply 2-4 are
    already visible in today's data; only the **37.2% that never resolve inside
    4 plies** need a full Stockfish re-analysis of 17,346 games at depth 18.
    Sample what 12 plies actually buys before spending that.

Authoring whys by hand is still not on this list.


---

## 12. Corrections made while doing this

Recorded because each was a wrong answer that nearly shipped:

- The holes were first split using `explanation.confidence`. It reads
  `verified` even on *"Opponent's Qxf2 is a serious mistake."*, and
  `board_explanation` is a verbatim copy of the caption. Neither can tell a
  template hole from a detector hole, so both were discarded.
- The queue's false positives were first attributed to the square-in-capture
  regex. Measured, that bug explains **1** case on its own; `runs into`
  explains 1,633.
- The `severity` field was first called corrupt and `severity_canonical`
  correct. The label is defensible and the caption is what is wrong — the
  opposite reading.
- Two Mongo probes returned zeros that were nearly reported. `$nin` and
  `$ne: null` on a dotted array path do not mean what they look like, and both
  failed their own positive control (`pv_after_played` read 0 against 52,468
  known-populated rows). `$elemMatch`, with controls, gives the real answer.
- The PV truncation was first written up as a code fix at
  `stockfish_service.py:724,747`. Those lines are from a local checkout 71
  commits behind origin; the constant is already 12 and shipped 2026-09-25.
  The finding survived, the remedy changed from a one-line edit to a
  regeneration.
- The first mover-attribution count was inflated: the regex `^Your \w+ ` also
  matches "Your opponent played …", which is correct text. The "724 wrong-owner
  clauses" from that pass was the same contamination and is not a real number.
- **A 5,000-row sample (3.3%) reported three regressions as zero.** The full
  152,519-card pass found 44 cards collapsing to a bare move, 4 losing a
  played-why, and 23 crossing the word cap. Sample said 4 bare captions before
  and 4 after: no change. Anything that ships user-facing text gets the full
  pass, not a sample.
- **A 100%-of-affected-cards figure means nothing without the base rate.** "All
  120 of the degraded cards have this fact set" only became evidence once the
  base rate came back at 14.0% on random user cards. That control was skipped
  first time round.
- **A correct claim is not a safe change.** The withdrawn predicate was 100%
  precise on 2,690 firings and still made 248 cards worse, because setting a
  fact changes variant selection downstream. Precision of the claim and safety
  of the change are separate measurements.
- **Two "live bugs" were already fixed.** Mover attribution (~95% gone by
  2026-09-26) and PV truncation (fixed 2026-09-25) both looked live in the
  stored data. Date the defect before costing the fix.

- Sampling caught nothing that the full pass contradicted on direction, but it
  was wrong on magnitude twice: a 47-row first sample put "stale" at 68%, a
  500-row queue sample at 17%.
- The branch-order fix was sized from a fact-availability count and shipped
  against the wrong file. The re-render net came back byte-identical to
  baseline, which is the only reason it was caught: `tier23_caption` renders
  almost none of this corpus and `R12_blunder` produces 80.1% of the class. An
  availability count is not a producer count — always check `rule_name`.
- The new R12 predicate was first inserted mid-list, where it pre-empted the
  ply-1 predicates and cost 3 cards a working played-why when the verifier
  rejected it. Moved last, it can only add.
- Two probes read field names that do not exist. `failure_clause`/`why_clause`
  are not in `debug_facts` (both read 0%, which would have "proved" the clause
  was never produced), and an earlier pass read `v5_coaching_version` when the
  field is `decryption_v5_version`. A 0% that agrees with your hypothesis
  deserves the same positive control as a 0% that does not.

## 13. Two things found in the test setup

Neither is caption work, both cost time here and will cost it again:

- **`tests/test_opponent_reply_ties.py` calls `sys.exit()` at module scope**, so
  `pytest tests/` dies with `INTERNALERROR` during collection. 3,774 tests
  collect and 3 error. The suite cannot be run as a whole until that file stops
  being a script.
- **`tests/test_all_flows.py` needs a live API** (`REACT_APP_BACKEND_URL`,
  default `localhost:8001`) and **exits 0 when every request fails**. Its exit
  code is not a pass signal. CLAUDE.md presents it as the suite to run after
  every backend change.
