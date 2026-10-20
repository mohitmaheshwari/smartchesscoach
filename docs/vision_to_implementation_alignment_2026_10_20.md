# Vision-to-Implementation Alignment Report

**Date:** 2026-10-20 · **Against:** "ChessGuru — Complete Product Vision" (founder + ChatGPT)

**Method:** measured against production (`chess_coach`: 130 collections, 128 users,
19,457 games, 18,625 analyses) and the code on `working-code`. Every figure was measured
for this report unless marked *(carried)*, meaning it comes from an earlier verified
session. No code was changed to produce this.

---

## 0. The one-paragraph answer

The vision describes a coach that observes, remembers, teaches, and checks whether
teaching landed. ChessGuru has built the **observing** half to a genuinely high standard:
602,351 move observations, 81% of them carrying real clock data, 19,355 detector claims,
and a quality lock that refuses to let a model approve its own claims. It has not built
the **teaching** half — and the gap is not spread evenly. It is concentrated in two
specific wires. Lesson evidence is admitted at a rate of **3 events out of 6,824**. And
the pillar the founder is most excited about, teaching from other people's games, has
**no data substrate at all**: no curated game library, no concept index over games, and
all three embedding collections at zero rows.

My strongest disagreement with the proposal is its priority order. It puts "strengthen
Game Intelligence" first. Game intelligence is the most-built part of this product, and
its output is already being discarded downstream. Putting it first would spend months
improving the quality of data that nothing consumes.

---

## A. What exists, with verdicts

Verdicts: **Reliable** · **Needs work** · **Partial** · **Missing** · **Unverified**

| Capability | Verdict | Evidence |
|---|---|---|
| Game analysis (Stockfish) | **Reliable** | 18,625 analyses over 19,457 games; `analysis_worker.py`; queue healthy (pending 2, stale 0) |
| Move-level observation layer | **Reliable** | `move_observations` 602,351 rows, 43 fields each, 63 distinct observed concepts |
| Clock / time-pressure data | **Reliable** | `time_left_seconds` on 81.1%, `time_spent_seconds` on 78.5%. **Corrects a prior belief that the pipeline drops the clock** — true of `game_analyses`, false of `move_observations` |
| Tactical detectors | **Needs work** | 48 concept detectors: **11 CAPTION, 36 SHADOW, 1 DISABLED**. Tactical motifs live in a separate system (`motif_alignment.py`, `data/captions/R12_blunder.json`); `R12_blunder` is the single largest live caption rule at 16.2% |
| Strategic / positional detectors | **Partial** | 9 positional concept detectors, 5 CAPTION-grade. Good-vs-bad bishop **does not exist** (see G1) |
| Opening analysis | **Needs work** | `user_opening_progress` 8,340; `user_opening_mastery` 760. Naming is per-platform: chess.com ~98%, lichess ~0% *(carried)* |
| Game summary / "the story" | **Needs work** | **Three** competing services (`game_coach_review`, `game_decryption_v5`, `board_state_game_summary`) — a single-source-of-truth violation |
| Player profile | **Partial** | `user_teaching_memory` 28,333 moments; `identity_snapshots` 204. Keyed by `principle_id` / `shape_pattern_id`, not by concept |
| Progress tracking | **Needs work** | Only **23 of 345** focus rows (7%) carry both `baseline_metric` and `current_metric`. Nine supersession generations visible in `status` |
| Coaching memory | **Partial** | 28,333 moments; 34 of 68 moment ids join to `user_concept_understanding` |
| Interactive review / lessons | **Partial** | 346 sessions, 293 completed, 365 graded attempts (272 correct / 93 wrong). Grading works; evidence admission does not |
| Learning recommendations | **Reliable** | `personal_curriculum.py` serves Home and Learn; 128/128 users build without error |
| Community **game** library | **Partial — revised, see §H2** | The corpus exists and is ours: **18,638 analysed games**, of which **17,192 belong to the 28 users holding 100+ each**. What is missing is the index and the ranker, not the games. Founder decided 2026-10-20 that ChessGuru community games are the source |
| Instructional retrieval / similarity | **Missing** | `game_embeddings` 0, `pattern_embeddings` 0, `analysis_embeddings` 0; no embedding code in `services/` |
| Play with Coach | **Needs work** | 499 sessions, 73,381 `pwc_session_traces` — but those are HTTP traces (`endpoint`, `request`, `duration_ms`). `behavior_events` non-empty: **0** |

---

## B. The four findings that matter

### B1. Lesson evidence is admitted at 3 events in 6,824

`learning_sessions` holds 6,824 events. `evidence_eligible` is **True on 3**.

| rejection_reason | events |
|---|---|
| `shadow_only_not_visible_mastery` | 6,091 |
| `assisted_or_incorrect` | 7 |
| `answer_revealed` | 4 |
| `assisted_verified_practice` | 4 |

The lessons run. The attempts are graded, with `board_verified` set and a real split of
272 correct against 93 wrong. Then 89% of the resulting events are discarded because the
surface is shadow-only.

"Demonstrated learning" — the vision's own most important measure, and the thing that
separates a coach from an analysis tool — is therefore not measurable today. Not because
the data is missing, but because the gate is shut.

**This is the highest-value fix in the product, and it is a flag and a wire, not an engine.**

### B2. The join key between teaching and observation is null

`concept_id` is null on **all 22,557** user cards sampled, while `concept_applied` is
populated on 57.1%. The card knows that a concept applied; it does not record *which one*
in a form anything can join on.

Measured vocabulary overlap:

| source | distinct ids | overlap |
|---|---|---|
| lessons (`learning_sessions`) | 13 | ∩ observed = **1** (`piece_safety`) |
| lessons | | ∩ understood = **0** |
| understood (`user_concept_understanding`) | 261 | ∩ observed = **1** (`knight_fork`) |
| focus (`user_active_focus`) | 7 | ∩ observed = **4 of 7** — works |
| moments (`user_teaching_memory`) | 68 | ∩ understood = **34 of 68** — works |

Note the shape. The **diagnosis** side joins. The **teaching** side does not. This is a
narrower and far more fixable problem than "five vocabularies with nothing in common":
the broken edge is specifically *taught → later observed*, which is precisely the edge
Pillar Six depends on.

### B3. Pillar Five has no index — but it does have a corpus

*Revised 2026-10-20 after the founder chose ChessGuru community games as the source.
The original finding read "no substrate", which was wrong once the source question was
settled: it assumed an external corpus was required.*

What is genuinely absent: no concept index over games, no position-similarity search, no
difficulty or instructional-clarity scoring. `coaching_library.py`, despite the name, is
a text-template bank.

What is present, and enough to start: 18,638 analysed games, 17,192 of them held by the
28 users with 100+ games each. Every one already carries move-level observations.

It remains the pillar most easily faked. A retrieval system that returns plausible-looking
games nobody has verified as instructive would pass a demo and teach nothing. The
definition of instructive has to come before the index — see §H3.

### B4. What the product actually says today

Live caption rules across 22,557 user cards:

| rule | share |
|---|---|
| `R12_blunder` | 16.2% |
| `distilled:*` (3 rules) | 16.0% |
| `facts:*` (3 rules) | 14.5% |
| `R_FALLBACK` + `R16_board_state_fallback` | **11.7%** |
| `R15_good_move` | 7.1% |
| remainder | rest |

Severity mix: **76.5% "good"**, 23.5% criticism (mistake 10.4%, blunder 5.5%,
inaccuracy 4.7%, serious 2.9%).

So about one card in eight is a fallback, and three in four say nothing critical. Measured
against "every game has a story", today's reality is closer to "most moves get a sentence,
and one in eight of those is a floor".

---

## C. Data architecture — where the flow breaks

    PGN + Stockfish ──► game_analyses (18,625)             works
            │
            ├──► move_observations (602,351, 81% clocked)  works — the real asset
            │          │
            │          ├──► user_active_focus (345)        7% have before/after
            │          ├──► user_concept_understanding     joins observations 1/261
            │          └──► user_teaching_memory (28,333)  joins understanding 34/68
            │
            └──► decryption_v5 cards                       concept_id null 100%
                       │
                       └──► learning_sessions (346)        grades attempts correctly
                                  │
                                  └──► mastery evidence    3 of 6,824 admitted
                                             │
                                             └──► progress cannot close

Two broken links, both at the **end** of the chain. That is the characteristic failure
mode of this codebase, and it already has a name in our own notes: the last wire.

---

## D. Reliability — which claims are safe to make

**Trustworthy:** anything resting on Stockfish, or on `move_observations` geometry.

**Provable:** anything inside 5-piece Syzygy range — but that is only 6.8% of games and
2.6% of moves, so the tables are an offline adjudicator, never a detector.

**Not trustworthy yet:**

- 36 of 48 concept detectors are unverified (SHADOW) by their own authorization records.
- `detector_claims` 19,355 against `detector_claim_rulings` 267 — **1.4% adjudicated**.
- Behavioural traits are stable but have never been checked for *correctness*; a
  blind-label packet exists and has never been sent to a coach *(carried)*.
- Concept detectors overwhelmingly congratulate rather than correct *(carried)*.

**A live false-claim class, as the type specimen.** Fixed yesterday and worth recording
because it shows where our false coaching claims actually come from. The severity
classifier forced "blunder" whenever the eval after a move was a mate score, without
checking that the player was not *already* being mated — so every move by a player in a
lost position was a "major blunder". Measured: 0.47 false labels per game, roughly 9,200
corpus-wide, and only a third of them in the endgame. Shipped as v224, adjudicated against
Syzygy where provable (101 of 101 downgraded cards were genuinely lost before the move).

The generalisable lesson: our false coaching claims have so far come from **framing and
gating bugs, not from weak chess knowledge**. That should shape where review effort goes.

---

## E. Architecture — and where I disagree

The six-layer proposal is a good description of what the product should *contain*. It is a
poor description of what to *do*, because five of the six layers already exist in some
form. Taken literally, it invites a parallel build next to working code — and this
codebase has already been bitten by exactly that: a complete tablebase caption path sits
provisioned-but-starved, and I nearly built a second one beside it this week before
checking.

| Proposed layer | Reality |
|---|---|
| 1 Chess Evidence Engine | **Exists** — `move_observations` is it |
| 2 Game Intelligence | **Exists three times** — consolidate, don't add |
| 3 Player Intelligence | **Exists, partial** — `user_teaching_memory` plus focus |
| 4 Coaching Memory & Progress | **Exists, gate shut** — fix admission |
| 5 Instructional Retrieval | **Genuinely missing** — this is the real build |
| 6 Interactive Coaching | **Exists, partial** — grading already works |

So the work is: **consolidate 2, unblock 4, build 5.** Not six new engines.

---

## F. Roadmap — reordered, with reasoning

The proposal's order is: 1) game intelligence, 2) player profile, 3) progress, 4) game
selection, 5) interactive study, 6) PWC. I recommend a different order.

**Phase 1 — Open the gate.** Admit lesson evidence; populate `concept_id` on cards.
Unblocks "demonstrated learning" and progress simultaneously. Everything required already
exists and is currently being thrown away. Days, not months, and the highest value per
unit of work anywhere in the product.

**Phase 2 — One game story.** Collapse three game-story services into one. Fix the eval
clamp that breaks turning-point maths *(carried)*, because "where did the balance change"
is the vision's central question and currently rests on a broken peak-minus-trough.

**Phase 3 — Progress on honest denominators.** Only 7% of foci can compute before and
after. Move to taken-over-offered, controlled within rating band. Expect this to refute
some current claims — that is the point of doing it.

**Phase 4 — The game library.** Corpus, concept index, instructional-value ranking. The
large build. Deliberately after Phases 1–3, so there is a working loop to plug it into,
and so "instructive" is defined before anything is indexed.

**Phase 5 — Deepen interactive study**, now that attempts count as evidence.

**Phase 6 — Play with Coach**, per the founder's separate vision. Noting it currently
stores 73,381 HTTP traces and zero behavioural events.

**Why game intelligence is not first:** it is the strongest layer we have, and its output
is discarded at the gate three steps later. Improving it first raises the quality of data
that nothing yet consumes.

---

## G. Questions only the founder can answer

1. **Good-vs-bad bishop — asked today who owns it.** There is **no such detector**.
   `endgame_curriculum__bishop_endgames__good_vs_bad_bishop` is auto-generated by
   `_make_detector()` in `concept_detectors/endgame_curriculum_positions.py` and is an
   *exact lesson-position matcher*, not a structural evaluator. SHADOW, and 0 fires across
   1,200 analyses (positive control: 23 detectors fired, 6,164 fires in the same run). My
   candidate rule from 2026-10-19 — own-colour pawn share at or above 0.60, two or more
   fixed pawns, past move 12, matching about 12.1% of games — was never built and never
   tested against a control of good moves. That control is the whole question: weaker
   players reach bad-bishop structures *and* play worse moves, so a raw correlation
   measures rating, not structure. Spec it properly, or drop it until the loop is closed?
2. **Game corpus rights.** Which sources may we store and display? This gates Pillar Five
   entirely, and it is a legal question before it is a technical one.
3. **What counts as "instructive"?** Required before indexing a single game.
4. **Is shadow-only deliberate?** 6,091 events rejected for
   `shadow_only_not_visible_mastery`. If that gate is a conscious safety choice, Phases 1
   and 3 are blocked behind a product decision rather than engineering.
5. **About 120 users predate these features** *(carried)*. Should progress claims be
   restricted to users whose history postdates the measurement?

---

## What I could not determine

- Whether the 36 SHADOW detectors are *wrong* or merely *unreviewed*. At 1.4%
  adjudication the honest answer is "unknown", not "fine".
- Whether behavioural traits are valid. Stability is not correctness, and validity has
  never been tested against a human coach.
- Caption **quality** at scale. Keyword audits are unreliable here, and the rule mix in B4
  says what fires, not whether it teaches.

---

## H. Founder decisions, 2026-10-20

All five open questions from §G were answered. Two overturned findings above; both have
been corrected in place rather than left to contradict this section.

### H1. Good-vs-bad bishop — DEFER, do not abandon

Not to be prioritised until detector → game intelligence → player profile → progress →
coaching works reliably. It stays on the long-term strategic list.

**Founder's refinement, which changes the spec:** a bad bishop is not necessarily a bad
move or even a disadvantage. When this is built, the **structural property** must be
distinguished from its **actual effect on the position**. That rules out the rule I had
been circling (own-colour pawn share, fixed pawns, move number) as a *standalone* signal:
it measures the structure only. Effect needs a separate, independently verified step.

### H2. Game source — ChessGuru community games

Games played by other people on ChessGuru, not an external corpus. This is why §A and §B3
were revised: the substrate exists.

Two constraints that follow, neither a blocker:

- **No consent or sharing field exists** on `games` or `users` — measured, zero fields
  matching consent/share/public/privacy/opt-in. A basis for showing one player's game to
  another needs to be established before anything ships.
- **The precedent is de-identification, and it is stricter than it looks.**
  `community_puzzles` (56,064 rows) carry **0 source `game_id` and 0 contributing
  `user_id`** — every link back to game and player is already stripped. A *position* can
  be de-identified that way. A *whole game* cannot be, to the same standard: the PGN
  carries player names, ratings and dates, and the move sequence itself makes the game
  findable on chess.com or lichess. So "anonymise it like we anonymise puzzles" is not
  automatically available at game granularity, and that is a design decision, not an
  oversight to code around.

### H3. What counts as instructive — founder's definition adopted

My proposed test ("the concept must decide the result") was **rejected, correctly**. It
would have excluded a well-handled Scandinavian, a sound defence, a positional exchange
that improves a bishop, an endgame draw saved, a fifteen-move plan, and a community player
making our student's own recurring mistake. None of those decide a game; all of them teach.

Adopted definition: *a game or position is instructive when it clearly demonstrates a
verified chess concept, is relevant to a specific player's learning needs, and can support
a meaningful interactive teaching experience.*

Five criteria: **concept clarity · chess validity · player relevance · appropriate
difficulty · interactive potential.** A decisive tactic is one kind of instructive moment,
not the requirement.

**What this costs, stated plainly.** My version was narrow because it was cheap — "the
result changed" is computable from data we already hold. Of the five criteria, only two
are computable today:

| criterion | computable now? |
|---|---|
| chess validity | **yes** — Stockfish, and Syzygy inside 5 pieces |
| player relevance | **yes** — `user_active_focus`, `move_observations` |
| concept clarity | no — needs a verifier or human review |
| appropriate difficulty | partly — rating band exists; lesson difficulty does not |
| interactive potential | no — needs authoring or a new signal |

That is a reason to sequence it, not to narrow the definition back. Three of five criteria
route naturally through the review surface in H4.

**On rating range:** 600–1500 is **not hardcoded** anywhere as a cap. `RATING_BANDS` spans
0–999 / 1000–1399 / 1400–1799 / **1800+**, so the band machinery already reaches beyond
1500. What *is* bounded at 1500 is the **evidence**: the puzzle proofs behind many
detectors were validated on Lichess puzzles rated 600–1500. So serving stronger players
means **re-validating detectors on stronger puzzles**, not deleting a constant. Worth
knowing because the two look identical from the outside and only one is cheap.

### H4. Shadow-only mastery — route it to coach review

Not live yet, so mastery must not be auto-awarded; it needs a surface where coaches review
and approve.

**The surface already exists and must be extended, not rebuilt:**

- Backend: `GET /admin/detector-review/{detectors,next,batch,results}` and
  `POST /admin/detector-review` in `backend/routes/admin_detector_review.py`
- Frontend: `AdminDetectorReview.jsx`, alongside `AdminAuthoringReview.jsx`,
  `AdminCaptionDrafts.jsx`, `AdminGeometryGaps.jsx`, `AdminDashboard.jsx`
- It already works: `detector_claim_rulings` holds **267** human rulings

**This revises Phase 1.** It is no longer "open the gate" — that would auto-award mastery
on unverified detectors, the worst available failure. It is: route the 6,091 shadow-rejected
events into the existing review queue, and admit only what a coach approves. A human is a
permitted adjudicator under the detector quality lock, so approved evidence is admissible
by the same standard the lock already demands. The queue is also where concept clarity and
interactive potential from H3 get judged.

### H5. Progress tracking — three users, deep histories

Track it properly for three users with varied, substantial histories rather than
restricting claims globally. Measured candidates (analysed games only):

| user | games | distinct openings | time controls | history span |
|---|---|---|---|---|
| `user_b189135388c9` | 1,996 | 533 | 3 | 2026-04-19 → 09-11 |
| `user_8b599930d7ef` | 871 | 254 | **7** | 2026-02-23 → 09-10 |
| `user_76ee10b87522` | 1,016 | 285 | 3 | **2026-02-27 → 09-10** |

Chosen for different reasons, not as the top three on one axis: the first for volume and
opening breadth, the second for the widest time-control and result spread (7 controls, 4
result types — the only candidate that can separate a clock problem from a board problem),
the third for the longest continuous history. Before-and-after needs time depth, so the
two reaching back to February matter more than raw counts.

28 users hold 100+ analysed games, so this set can be widened once the method is proven.
