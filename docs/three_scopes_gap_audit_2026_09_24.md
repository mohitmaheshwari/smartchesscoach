# Three scopes vs reality — gap audit, 2026-09-24

Mohit named two scopes he had already defined, then correctly added a third.
They are three layers of one loop:

```
  MEASURE   →   TEACH   →   PROVE   →   REPORT BACK
      |            |           |             |
   PIC scope   PIC scope   Teaching      Coach
  (APPROVED)  (APPROVED)  Loop (DRAFT)  Conversation
                                        (SIGNED OFF)
```

This audit asks one question of each promise: **built? reachable? true?**
No code was written. Everything below is measured against prod data.

---

## Headline

**The loop never closes, and nothing is ever proved.**

- **1,037 concepts are marked MASTERED. Zero were ever tested.**
- **Not one focus has ever ended because a player improved.** 163 of 193
  inactive focuses were `superseded_*` — wiped by our own picker version
  bumps. Every actual resolution value is a failure mode.
- The signed-off coach conversation reaches 52 of 56 users and its most
  common sentence lands on **44%** of them.

---

## 1. Teaching Loop — `teaching_loop_scope.md` (DRAFT, unsigned)

Its own claim, line 471: *"only the test is missing — four of five states
have live writers; TESTED has none."* **Verified true.**

| state | rows | users | verdict |
|---|---|---|---|
| SHOWN (`shown_count > 0`) | 2,483 | 65 | built |
| UNDERSTOOD (`acknowledged`) | 490 | 55 | built, set by the wrong things |
| MONITORING (`clean_games_total > 0`) | 1,659 | 58 | built, works |
| MASTERED (`mastered_at`) | **1,037** | 55 | built, works |
| stripped (`mastery_stripped_at`) | 251 | 39 | built, works |
| **TESTED** | **0** | **0** | **MISSING** |

```
concept_test_results    0
concept_tests           0
user_concept_tests      0
puzzle_attempts       431   <- exists, but not wired as concept proof
```

**So the product has told 55 people it mastered something on its own say-so,
1,037 times.** That draft exists precisely to stop this, and it is unsigned.

---

## 2. Personal Improvement Cycle — `personal_improvement_cycle_scope.md` (APPROVED v1.3)

The scope says `user_active_focus` is the single source of truth and its
outcome lifecycle needs repair. The lifecycle has never produced a verdict.

```
total weakness focuses       237
  status active               44
  status NOT active          193
      superseded_v6           46
      superseded_v7           40
      superseded_v8           39 (+1 local)
      superseded_v9           37 (+1 preview)
      closed_unresolvable_metric  18
      closed_detector_not_plannable 11

has current_metric             0   <- never computed, for anyone
```

Resolution values, all 64 that have one:

| resolution | n | what it means |
|---|---|---|
| `measurement_pending` | 35 | could not measure |
| `metric_gap` | 18 | no metric existed |
| `detector_not_authorized_for_plan` | 11 | the plan gate again |
| *(none)* | 173 | never resolved at all |

**There is no success value.** Not one focus closed because the player got
better. 163 ended because we shipped a new picker version — so a user's
focus history is really a log of our deploys.

`current_metric` is 0 of 237, so the before/after comparison the cycle is
built on has never run.

---

## 3. Home Coach Conversation — `home_page_coach_conversation_scope.md` (SIGNED OFF)

Built and reachable: the narrative renders for **52 of 56** users with 10+
analysed games. The promise it fails is distinctness.

```
distinct stage_opener: 4
   24 (46%)  "I'm starting to see your habits."
   15 (28%)  "I already know what will be hard for you, before it happens."
   10 (19%)  "I know what usually causes your losses."

distinct belief: 8
   23 (44%)  "When an attack is running, the rest of the board usually stops..."
   19 (36%)  "In a slow game the board feels settled, so it stops getting..."
    4 ( 7%)  "At your level this is rarely a piece left hanging for nothing..."
```

The signed-off mockup promised a coach who *changed its mind after watching
ten games*. What renders is 4 stage strings and 8 beliefs across 52 people.

This was already caught once — commit `4ce4021d` (2026-09-17), after Mohit
said *"there is a difference between knowing you and write, and write some
shit on the face of knowing you."* That fix made the sentences **honest**
(hedged statements about the pattern, not claims about the reader). It did
not make them **distinct**, and distinctness is the part the scope promised.

---

## Why all three are stuck on the same thing

Every layer reads `user_active_focus`. Measured today: **53 of 86 users hold
the same topic**, because exactly one quality id is PLAN-graded
(`gap:piece_safety:destination_safety_exact`).

That single fact explains all three findings at once:

- the conversation repeats itself because there is one topic to talk about
- `detector_not_authorized_for_plan` closed 11 focuses outright
- a proof step would currently only ever prove `piece_safety`

So detector promotion is not a side quest. **It is the input to all three
approved scopes.**

---

## What this changes about priority

An earlier recommendation in this session was to defer detector promotion
because it costs Mohit's review time. That was wrong in light of this audit:
promotion is the bottleneck feeding the product's whole loop, not an
optimisation of one surface.

The order the evidence supports:

1. **Promote detectors** — unblocks topic variety for all three layers.
2. **Sign or kill `teaching_loop_scope.md`** — 1,037 unproven masteries is
   the largest untruth the product currently tells, and the fix is drafted.
3. **Give the cycle a success path** — `current_metric` at 0 of 237 means
   "did it improve" has never been asked, let alone answered.
4. **Then** distinctness on the home sentence — it is the symptom, and the
   first three are the cause.

No code has been written. This is a measurement, not a plan.
