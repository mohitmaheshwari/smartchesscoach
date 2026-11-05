# Phase 1 scope — reviewed lesson evidence

**Status:** scope, 2026-10-20. No code written.
**Decision it implements:** founder, 2026-10-20 — *"right now we are not live, so shadow
only mastery need to have some sort of thing for our coaches to review and approve"*.
**Supersedes:** the "open the gate" phrasing in
`vision_to_implementation_alignment_2026_10_20.md` §F, which was wrong — see C1 and C4.

---

## 1. The problem, measured

`learning_sessions` holds 6,824 events. `evidence_eligible` is **True on 3**.

| rejection_reason | events |
|---|---|
| `shadow_only_not_visible_mastery` | 6,091 |
| `assisted_or_incorrect` | 7 |
| `answer_revealed` | 4 |
| `assisted_verified_practice` | 4 |

The lessons run and the attempts grade honestly — 272 correct against 93 wrong, with
`board_verified` set and `reason_choice` recorded. Then 89% of the resulting events are
discarded. "Demonstrated learning", the product's most important claim, is unmeasurable
because nothing admits the evidence.

## 2. Four constraints I verified before designing anything

**C1 — Shadow-ness is an enforced invariant, not a flag.**
`services/learning_evidence_ledger.py:94` hardcodes `evidence_eligible: False`, and
`_event_skill_id` *raises* `ContractViolation` when it is anything else. So there is no
flag to flip and the events must never be mutated. Admission has to be a separate record
that *references* an event. This is the right shape anyway: the shadow ledger stays an
immutable account of what happened.

**C2 — A review is not a promotion. House rule, stated in code.**
`routes/admin_detector_review.py` docstring: *"not a promotion. Verdicts accumulate into
the precision figure a promotion packet needs, but `detector_quality` remains the only
authority on what may reach a player, and nothing here writes to it."* So a coach's
approval must not itself award mastery; it produces evidence that an authority then reads.

**C3 — Do not invent a fifth review shape.**
Same docstring: it *"follows the geometry-gaps queue (`/admin/geometry-gaps/next` + POST +
`/results`) rather than inventing a fourth review shape."* There are now four queues on
one shape — `next` / `POST` / `results`, keyed on a claim key, ruled `true｜false｜unsure`,
drawn in corpus order and skipped once ruled. Phase 1 uses that shape exactly.

**C4 — The one that changes the design: mastery does not read lesson evidence today.**
`services/concept_mastery_tracker.py:414-425` sets `acknowledged` and then `mastered_at`
off a **clean-game streak**. Lesson results are not an input. So building only a review
queue would admit evidence that nothing consumes, and the surface would not move — the
same "zero delta" mistake I made twice this week (a gate on SHADOW detectors; a duplicate
tablebase path beside a starved one). **Phase 1 is therefore not complete without changing
the mastery authority to read reviewed evidence.** This is also why
`mastered_at` currently sits on never-shown concepts: a streak can happen with no teaching.

## 3. Design — three workstreams, in dependency order

### WS1 — A review queue over lesson evidence

New endpoints on the established shape, in a new router beside the others:

- `GET /admin/lesson-evidence/next` — one unjudged shadow event, rendered as the player
  saw it: the lesson, the position, the attempt (`correct`, `assistance`,
  `requested_help`, `reason_choice`), and the `application.outcome`.
- `GET /admin/lesson-evidence/batch` — same source, same ordering.
- `POST /admin/lesson-evidence` — verdict `true｜false｜unsure`, plus `note` and
  `reviewer_name` (the admin login is shared with a reviewing coach, so `ruled_by` alone
  cannot separate two reviewers — the existing surface already handles this and the same
  reason applies here).
- `GET /admin/lesson-evidence/results` — tallies, and every event ruled false, because
  those are the bug reports.

Queue source: `learning_sessions` events where `event_type == "lesson_result"` and
`rollout_mode == "shadow"`, in corpus order, skipping ruled ones. Claim key: the event's
own `idempotency_key`, which is already stable and content-addressed.

Rulings land in a new `lesson_evidence_rulings` collection, keyed `(claim_key, skill_id)`,
mirroring `detector_claim_rulings`.

The question a coach is asked must be the honest one, and it is **not** "is this detector
right". It is: **did this attempt demonstrate that the player understands the concept?**
That is a different judgement and it needs its own wording on the card.

### WS2 — Mastery reads reviewed evidence

`concept_mastery_tracker` gains reviewed lesson evidence as an input alongside the clean
streak. Concretely: a concept may reach `mastered_at` only when it has at least one
coach-approved demonstration **and** the existing streak condition. Approval alone is not
mastery (one correct answer is not understanding, per the vision's own warning); the
streak alone stops being sufficient, which is the defect behind the 33 stamps on
never-shown concepts.

This respects C2: the coach's verdict is evidence, `concept_mastery_tracker` remains the
authority that decides.

`MASTERY_STRICT_EVIDENCE` (`detector_quality.py:1353`, default false) is the existing
switch for exactly this kind of tightening and should gate the new requirement, so the
change can land dark and be turned on deliberately.

### WS3 — `concept_id` on cards

Independent of WS1/WS2 and smaller. `concept_id` is null on all 22,557 user cards sampled
while `concept_applied` is populated on 57.1%: the card records *that* a concept applied
and not *which*. Populating it restores the join that makes "taught → later observed"
answerable (today lessons meet observations on 1 id of 13).

Sequenced last because progress measurement needs it, mastery does not.

## 4. Explicitly not in scope

- **Flipping `evidence_eligible`.** Forbidden by C1; the ledger raises on it.
- **Auto-admitting anything.** Not live is the whole premise of the founder's answer.
- **Writing to `detector_quality`.** Forbidden by C2.
- **A new review UI pattern.** Forbidden by C3; extend the existing admin pages.
- **Re-grading attempts.** Grading already works (272/93, board-verified). The gap is
  admission, not grading.
- **Pillar Five retrieval.** Phase 4.

## 5. How this gets verified

Each check is a positive and a negative control, because three of my conclusions this week
survived only until I ran the negative one.

1. **Queue is not self-selecting.** Events served in corpus order; assert the first N
   served are not ranked by `correct`. The detector-review surface had exactly this bug
   (a single-element list being "sorted") and it is recorded in its own comments.
2. **Immutability.** After a full review pass, assert zero `learning_sessions` events were
   modified — `evidence_eligible` still False on all 6,821, and the ContractViolation path
   never fires.
3. **Non-zero delta, stated before building.** With WS2 enabled on the three Phase-5 users
   (`user_b189135388c9`, `user_8b599930d7ef`, `user_76ee10b87522`), the count of concepts
   reaching `mastered_at` must *change* versus the streak-only baseline. If it is
   identical, the gate is in the wrong place and the work stops.
4. **Tightening, not loosening.** No concept may gain `mastered_at` that the streak-only
   path would have refused *and* that has no approved demonstration.
5. **Idempotency.** Replaying the ledger produces no duplicate rulings
   (`idempotency_key` is content-addressed; assert it).

## 6. Decisions still needed before code

1. **Who reviews?** The admin login is shared with a reviewing coach. Is the reviewing
   coach an existing identity, or does `reviewer_name` stay free text as it is today?
2. **How many approvals per concept?** I propose one approved demonstration *plus* the
   existing streak. One is weak evidence of understanding; requiring several may starve
   the surface at 346 sessions.
3. **Does a `false` ruling do anything beyond being a bug report?** It could strip a
   `mastered_at` already awarded. I would not: stripping on review feels punitive and the
   existing `mastery_stripped_*` fields already have their own semantics.

---

## 7. REVISION, same day — WS2 as written is impossible, and the surface is bigger than I said

Measuring before building changed three things in this scope. Recording all of it,
including the two places I read the wrong field and reported a misleadingly small number.

### 7.1 The evidence surface is substantial, not scarce

My first count said "365 graded attempts, 2 users, 5 pairs". That read `event['attempt']`,
but `lesson_result` events nest theirs at `event['lesson_result']['attempt']`. The real
figures:

| | |
|---|---|
| `lesson_result` events | **6,124** |
| distinct users | **38** |
| distinct (user, concept) pairs | **42** — 30 of them with 10+ events |
| `application.outcome` | **3,590 applied / 2,141 missed** / 393 not_measured |
| `application.source_type` | **5,709 `organic_game`** / 370 lesson / 23 mixed_drill / 22 coached |

The important line is the last one. 93% of this evidence is **game-derived**: the system
already observes whether a player applies a concept in a *later real game*, which is
precisely the vision's "demonstrated learning", with an honest 63/37 split. It is computed
and then discarded.

Caveat, and it is a real one: **5,759 of 6,124 events are one lesson**
(`piece_safety.simple_hang`); the rest are `piece_safety` 350, `rook_endgames/lucena` 13,
`king_and_pawn/key_squares` 1, `rook_endgames/active_rook` 1. The loop has been exercised
on effectively one skill. So Phase 1's payoff is real but concentrated, and breadth is a
separate problem from admission.

### 7.2 WS2 cannot be built yet — the vocabularies do not meet

| vocabulary | distinct ids | example |
|---|---|---|
| curriculum skills (lessons) | 5 in use | `piece_safety.simple_hang` |
| mastery (`user_concept_understanding`) | 261 | `DEF_MOST_ATTACKED`, `END_OPPOSITION` |
| observed (`move_observations`) | 63 | `destination_safety_exact` |
| focus (`user_active_focus`) | 7 | `piece_safety` |
| `pattern_catalog.json` | 35 | `missed_mate` |
| detector registry | 48 | `endgame_opposition` |

Lesson ids ∩ mastery ids = **zero**. All **995** mastered (user, concept) pairs sit on ids
that have no lesson. So "a concept may reach `mastered_at` only with an approved
demonstration" would strip all 995 — not because the evidence failed, but because the two
sides cannot be joined at all. That is a vocabulary defect, not a standards decision, and
shipping it would have looked like a tightening while actually deleting the feature.

`pattern_catalog.json` is not the bridge: its 35 ids cover neither side (0 lesson ids,
0 `DEF_`/`END_` ids). It is a sixth island.

### 7.3 WS0 — one concept identity, derived not invented

New keystone, ahead of everything else. Do **not** author a seventh mapping file.

`detector_quality_id` already spans two layers: it is the authorization key in
`detector_quality` (`gap:piece_safety:simple_hang`, `concept:endgame_opposition`) **and**
it is already carried on lesson evidence at `lesson_result.application.detector_quality_id`.
It is the only identity in the system that both an authority and an evidence record agree
on. Adopt it as canonical and make the other stores carry it — `user_concept_understanding`
and `move_observations` first, since those are the two WS2 needs.

That is deriving from an existing key, which is what the single-source-of-truth rule asks
for, rather than reconciling six vocabularies with a new table that would become a seventh.

### 7.4 WS1 correction — stratify the queue, do not use corpus order

§3 said corpus order, copying the detector-review house pattern. That is wrong here. The
largest pair holds **1,405** events, so corpus order would hand a coach the same user and
concept indefinitely. Serve one event per (user, concept) pair round-robin instead. The
anti-self-selection property still has to hold — ordering must not favour `correct` —
but it has to hold *within* a pair, not across the corpus.

### 7.5 Revised dependency order

**WS0** concept identity (unblocks everything) → **WS1** stratified review queue →
**WS2** mastery reads reviewed evidence → **WS3** `concept_id` on cards.

WS1 can proceed in parallel with WS0, because reviewing evidence does not require the
join; only awarding mastery from it does.

---

## 8. Re-measured 2026-11-05 — nothing built, the evidence keeps growing

Read-only against prod `chess_coach.learning_sessions`, events nested at
`events[]` (469 session documents hold them).

| | 2026-10-20 (§7.1) | 2026-11-05 |
|---|---|---|
| all events | 6,824 | **8,150** (1,204 since 10-20) |
| `evidence_eligible` True | 3 | **3** — same three, one user, none since 10-20 |
| `shadow_only_not_visible_mastery` | 6,091 | **7,276** |
| `lesson_result` events | 6,124 | **7,276** (1,063 since 10-20) |
| distinct users | 38 | **43** |
| (user, concept) pairs | 42, 30 with 10+ | **105, 38 with 10+** |
| `application.outcome` | 3,590 applied / 2,141 missed / 393 not_measured | **4,031 / 2,784 / 461** |
| `application.source_type` organic_game | 5,709 | **6,793** of 7,276 (93%) |
| `piece_safety_simple_hang` share | 5,759 of 6,124 | **6,645 of 7,276** (91%) |

New since 10-20: tactic skills now carry evidence (`missed_tactic_missed_skewer` 69,
`_pin` 48, `_fork` 43). Breadth is still thin; concentration in one skill is unchanged.

**Built since 10-20: nothing.** No `lesson_evidence_rulings` collection or
`/admin/lesson-evidence` route exists in `backend/` or `frontend/src`; no commit on
`working-code` since 10-20 names WS0–WS3. `concept_id` is still written as `None`
(`services/game_decryption_v5_service.py:5164`). The two related branches
(`closed-loop-sprint/ws0-ws1a-dryrun`, `codex/progress-evidence-page-v1`) are September
work, 890+ commits behind, and implement neither this scope's WS0 nor WS1.

**A correction to carry forward.** On 11-05 I proposed "switch the evidence on for one
lesson first". That is the "open the gate" framing §0 already retired: it breaks C1 and
the founder decision (coach review before any admission). The order stays WS0 → WS1 →
WS2 → WS3.

**Still blocking code — unchanged from §6, plus one:**
1. Who reviews (existing identity, or free-text `reviewer_name`)?
2. How many approved demonstrations per concept (proposed: one, plus the streak)?
3. Does a `false` ruling do anything beyond being a bug report (proposed: no)?
4. WS0: is adopting `detector_quality_id` as the one concept identity agreed?

**Answered 2026-11-05.** Mohit, replying "go ahead" to questions 2–4 as proposed:
one approved demonstration plus the existing streak; a `false` ruling is a bug report
only and strips nothing; `detector_quality_id` is the one concept identity. Question 1
was not answered, so the default stands: free-text `reviewer_name`, as on the existing
review surfaces. Next gate: `/audit-pre-code`.

**Pre-code audit 2026-11-05: BLOCKED.** One finding changes the design:

- **C4 is stale.** Mastery does not promote on the streak alone. Since 2026-09-21
  `may_promote_to_mastered` (`services/concept_test_service.py:99-129`) refuses unless
  `tests_passed >= 1`, and `concept_mastery_tracker.py:418-421` calls it; `tests_passed`
  is incremented by the concept test (`concept_test_service.py:413`). So a proof
  requirement already exists. WS2 must decide whether a coach-approved lesson
  demonstration is a **second way** to satisfy that proof, or an **extra** requirement on
  top of the concept test. Not decided.
- Also missing before code: a literal mockup of the coach review card and of what the
  player sees when evidence is admitted; a behaviour-changing success criterion; explicit
  signoff to code.

**Answered 2026-11-05 (Mohit, "go ahead" to the recommendation):** a coach-approved
demonstration is a **second way** to satisfy the proof in `may_promote_to_mastered`,
beside the concept test. The clean streak is still required on top. Section 9 drafts the
rest.

---

## 9. Draft 2026-11-05 — mockups and success measure (awaiting sign-off)

### 9.1 What the coach sees — EXTEND the existing review shape

A new tab beside `/admin/geometry-gaps` and the detector review, using the same
`next` / POST / `results` shape (C3). One event per (player, concept) pair, round-robin
(§7.4). Built from a real event: `piece_safety_simple_hang`, origin
`external_game_observation`, outcome `applied`, provenance
`move_observations 83010352-…:22`.

```
┌ Lesson evidence ─────────────────────────────── 38 pairs waiting ┐
│ Concept   Keeping a piece safe after it moves                    │
│           gap:piece_safety:destination_safety_exact              │
│ Player    user_…  ·  taught this on 2 Sep  ·  this is a real game│
│                                                                  │
│   [ board: the position before the player's move ]               │
│   green arrow: the move they played                              │
│   grey arrow:  the move that would have left a piece hanging     │
│                                                                  │
│ After the lesson, in a real game, they moved the bishop to a     │
│ square where it could not be taken for free.                     │
│ Their record on this concept since the lesson: kept 14, lost 9.  │
│                                                                  │
│ Does this move show they understand the idea?                    │
│   [ Yes, it shows it ]   [ No ]   [ Not sure ]                   │
│   Why not? (optional) ________   Your name ________              │
└──────────────────────────────────────────────────────────────────┘
```

The question is the honest one (§3): did this attempt demonstrate understanding, not
"is the detector right". Admin surface, so counts are allowed here.

### 9.2 What the player sees — EXTEND the Lab mastery panel

`MasteryPanel` on `/lab` (`frontend/src/components/coach/MasteryPanel.jsx`, mounted by
`Dashboard.jsx`) already has a `demonstrated` state with an emerald check. The new path
lands there. No new page. Player text follows the house rules: simple English, no numbers.

After a coach approves, before the streak is complete:
```
  Piece safety
   ◐ Keeping pieces safe                          Shown in a game
     A coach looked at a game where you kept a piece safe that you
     used to leave hanging. Keep doing it and it counts as learned.
     [ See that move ]
```
After the streak completes:
```
   ✓ Keeping pieces safe                                  Learned
     You showed it in a real game and kept it up after that.
     [ See that move ]
```
If they slip later, the existing amber "slipping" state applies unchanged.

### 9.3 Success measure

**Baseline, measured 2026-11-05 (prod, read-only).** For the 35 (player, concept)
pairs with at least 10 real-game outcomes, the median share "kept" (applied) is **0.52**.
Splitting each pair's history in half by time, the median goes from **0.58** in the first
half to **0.46** in the second; 10 pairs went up, 17 down, 8 unchanged. That is a small
sample with a known confound (opponents and positions change over time), so this sizes the
problem and does not characterise it. It does mean "learned" cannot be assumed to stick.

**Primary (behaviour):** of pairs that reach *Learned* through the new path, at least
**70%** keep a kept-share in real games over the next 30 days that is no lower than their
own share in the 30 days before the approval. Provisional; `/lock-via-data` after the
first 20 such pairs.

**Secondary (the surface changes):** after a concept becomes *Learned*, the player's next
Lab focus is a different concept by their next session.

**Health, not success:** share of reviewed events ruled Yes / No / Not sure, and every
No, which is a bug report (§6.3).

### 9.4 One more open question, raised by the mockup

5. **What makes an event worth reviewing?** Most real-game "kept" events are a piece
   moved to a safe square, which most moves are. Approving those would make mastery
   easy without showing anything. Proposed: serve only events where a hanging move
   was a real temptation, e.g. Maia at the player's rating gives the hanging move at
   least some probability. The cutoff gets locked with `/lock-via-data` from the
   distribution, not chosen now. Also to verify in WS1: whether `move_observations`
   stores the hanging alternative, or the card must recompute it.

### 9.5 Q5 locked 2026-11-05 (Mohit: "do what you recommend")

```
DECISION LOCKED: which real-game "kept" events a coach is asked to review

VALUE: serve an event only when all four hold
  1. the stored outcome is "applied" AND the played move grades "pass" today under
     grade_destination_safety_candidate (the outcome still agrees with the detector)
  2. temptation T >= 0.05, where T = Maia probability, at the player's game rating
     against the opponent's, summed over every legal move that
     grade_destination_safety_candidate marks "fail" (it hangs a piece)
  3. the played move's execution_quality is not mistake or blunder (inherited
     classification, not a new number)
  4. the game has a stored user rating (Maia needs one)

EVIDENCE (prod read-only export, Maia2 rapid model locally, 5,511 of 6,757 real-game
piece-safety events joined to their stored position):
  - Positive control: in 1,475 "missed" events where the played move really hangs a
    piece today, T in that position has deciles .008 .016 .026 .040 .060 .085 .123
    .179 .303. 0.05 sits at the median: 55% of real hangs happened at T >= 0.05.
  - "Kept" events: T deciles 0 .001 .002 .004 .007 .011 .020 .036 .088. Most kept
    events had almost no temptation: the triviality problem, measured.
  - Coverage, kept-and-not-a-mistake: T>=.02 572 events / 25 pairs;
    T>=.05 257 / 23 pairs (median 7 per pair); T>=.10 115 / 20 pairs. No cliff in pair
    coverage, so the cutoff is anchored on the positive control instead.
  - Agreement check: 192 "applied" events now grade "fail" (the move did hang a
    piece) and 605 "missed" events now grade "pass"; 197 "missed" are pawn or king
    moves the detector does not cover. 994 of 5,511 (18%) stored outcomes disagree with
    today's detector, which is why rule 1 re-grades instead of trusting the stored label.

REJECTED:
  - no cutoff: 3,042 events, nearly all with nothing tempting to resist
  - T > 0 ("any hanging move exists"): 95.5% of kept events qualify; filters nothing
  - T >= 0.02: easier than three quarters of real hangs; weaker demonstration for 2 more pairs
  - T >= 0.10: drops to 20 pairs and 4 events per pair for little gain in strength

MEASUREMENT METHOD: scratchpad q5/export.py (prod container, read-only) ->
q5/temptation.py (local Maia2, grade_destination_safety_candidate on every legal move)
-> q5/analyse.py. Caveat: Maia predicts real hangs weakly (median Maia probability of the
hanging move a player actually played: 0.019), so T ranks temptation; it does not prove it.
```

**Sign-off to code, 2026-11-05.** Mohit: "do what you recommend, you already know what
am i trying to build", in reply to the request for "locked, code it". Recorded as the
explicit sign-off for WS1; WS0, WS2 and WS3 follow in that order.

### 9.6 WS1 built 2026-11-05 — the first seed

`scripts/seed_lesson_evidence_reviews.py`, run export (prod, read-only) → score (local
Maia) → load (prod). From 5,892 real-game destination-safety events:

| step | events |
|---|---|
| not kept (stored outcome) | 1,883 |
| no stored position to join | 775 |
| the move was itself a mistake or blunder | 525 |
| stored "kept" but the move hangs a piece today | 175 |
| no game rating | 60 |
| **candidates** | **2,474** |
| **rows after the temptation floor** | **274**, across **23** player-concept pairs |

Only **5 of 274** rows come after the player's first finished piece-safety lesson; 265
are from players who have not finished one. So most of this evidence says "can already
do it", not "the lesson landed". The card states which it is, and WS2 must decide whether
pre-lesson evidence may count (§10, open).

## 10. Open after WS1

6. **Does a demonstration before any lesson count toward mastery?** 265 of 274 rows
   are pre-lesson. Counting them measures skill; not counting them measures teaching.
   Decide before WS2.
