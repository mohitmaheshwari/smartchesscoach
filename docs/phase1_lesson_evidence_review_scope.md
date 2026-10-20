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
