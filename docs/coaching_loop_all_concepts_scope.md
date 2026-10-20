# The coaching loop, for every concept

**Status:** scope, 2026-10-20. No code written.
**Supersedes:** `phase1_lesson_evidence_review_scope.md`, which scoped the loop for one
concept. That document stays valid as the detail of WS0–WS3; this one is the frame it
sits in.
**Founder direction:** *"obviously chessguru has to work for several concepts with the
loop, so that's the overall scope"* — plus loop tracking.

---

## 1. What "the loop works for concept X" means

Testable definition, five stages. A concept is **loop-complete** only with all five. Any
missing stage breaks the chain, and the product today has concepts missing each of them.

| # | stage | the question | where it lives |
|---|---|---|---|
| 1 | **Detect** | can we find X in a real game, reliably enough to say so? | detector + `detector_quality` grade |
| 2 | **Plan** | can X become someone's current priority? | `user_active_focus`, the picker |
| 3 | **Teach** | is there content that teaches X interactively? | lesson content, `learning_sessions` |
| 4 | **Practise** | is there a pool to drill X? | puzzle pools |
| 5 | **Observe & track** | do we see X applied in a *later real game*, and record it? | `lesson_result.application`, mastery state |

Stage 5 is the one that makes this a coach rather than a dashboard, and it is the stage
the product already does best — and then discards (see §3.1).

## 2. Measured coverage, today

Identity space: **70 `detector_quality` authorizations**. The family lesson evidence
actually uses is `gap:*` — 16 ids, of which **9 are PLAN grade** (the lock's highest bar:
Caption plus 200 fires, 60% recall, 30 true negatives) and 2 are CAPTION.

| concept family | 1 Detect | 2 Plan (focus rows) | 3 Teach | 4 Practise (puzzles) | 5 Evidence |
|---|---|---|---|---|---|
| **piece_safety** | CAPTION ×2, PLAN ×1, SHADOW ×1 | 219 (34 active) | yes | 4,707 | **5,765 events** |
| missed_tactic | **PLAN ×4**, SHADOW ×1 | 11 (9 active) | no | 3,726 | **0** |
| king_safety | **PLAN ×1**, SHADOW ×1 | 37 (8 active) | no | 151 | **0** |
| time_management | **PLAN ×3** | 27 (2 active) | no | **0** | **0** |
| opening_knowledge | SHADOW ×2 | 0 | yes (41 publishable) | 143 | **0** |
| endgames | SHADOW ×26, CAPTION ×3 | 0 | yes (20 publishable) | 12 | **15 events** |
| calculation_depth | **none** | 0 | no | **47,319** | **0** |

Lesson evidence, in full — only two ids have any:

| gap id | events | outcomes |
|---|---|---|
| `gap:piece_safety:destination_safety_exact` | 5,153 | 3,595 applied / 1,535 missed |
| `gap:piece_safety:simple_hang` | 612 | **0 applied** / 607 missed |

That second row is its own finding: `simple_hang` has recorded 607 failures and **not one
success**. A concept that can only ever be failed cannot show improvement, so it is unfit
to carry a progress claim in its current form, independent of everything else here.

## 3. There are three different breadth failures, not one

Treating "make it work for more concepts" as one task would produce the wrong work. The
measurements separate it into three, each needing a different fix.

### 3.1 Failure A — detected and planned, but never taught (missed_tactic, king_safety, time_management)

Eight PLAN-grade gap detectors, all reaching the plan surface (75 focus rows between
them, 19 currently active), and **zero** lesson content, so zero evidence. These concepts
can already be found and prioritised; a player is told this is their weakness and then
there is nothing to study.

**Fix: author content.** Not engineering. The detectors already clear the lock's highest
bar, which is the expensive half.

**Exception worth stating:** `time_management` has three PLAN detectors and zero puzzles,
and puzzles cannot train clock use. It needs a different teaching form entirely
(pacing exercises against a clock), so it should not be lumped in with the other two.

### 3.2 Failure B — taught, but never observed in later games (endgames, openings)

20 publishable endgame lessons and 41 publishable openings, with content authored and
verified — and 15 lesson events in total. The endgame detectors that would notice a player
applying the lesson in a real game are 26-of-29 SHADOW, and measured earlier at near-zero
fire rates. So a player can be taught the Lucena position and the system will never see
them use it.

**Fix: engineering, specifically stage 5 for authored content.** Each authored lesson needs
an application observer — a detector that recognises the taught idea occurring in an
organic game. Where a geometric detector is not feasible, the honest alternative is to
measure practice transfer rather than claim game transfer, and to say which one is being
shown.

### 3.3 Failure C — practised, but not a concept the system knows (calculation_depth)

47,319 puzzles, the single largest pool in the product, serving a label with **no gap
detector, no focus rows and no lesson content**. It cannot enter the loop at all; it is
drill supply attached to nothing the coach can diagnose or track.

**Fix: a decision, not a build.** Either `calculation_depth` becomes a real concept with a
detector and content, or that pool is re-labelled against concepts that exist. Leaving
47k puzzles pointed at a non-concept guarantees practice that no progress measure can read.

## 4. The keystone, unchanged: one concept identity

From the Phase 1 revision, and it gates everything above. Six vocabularies that do not
meet:

| vocabulary | ids | example |
|---|---|---|
| `detector_quality` | 70 | `gap:piece_safety:simple_hang` |
| mastery (`user_concept_understanding`) | 261 | `DEF_MOST_ATTACKED` |
| observed (`move_observations`) | 63 | `destination_safety_exact` |
| focus (`user_active_focus`) | 7 | `piece_safety` |
| `pattern_catalog.json` | 35 | `missed_mate` |
| lesson ids in use | 5 | `piece_safety.simple_hang` |

Lesson ids ∩ mastery ids = **zero**; all 995 mastered pairs sit on ids with no lesson.

**Adopt `detector_quality_id` as canonical** — it is already the authorization key *and*
already carried on lesson evidence at `lesson_result.application.detector_quality_id`, the
only identity an authority and an evidence record already agree on. Derive the others from
it. Do not author a seventh mapping file.

Note the one real cost of this choice: `move_observations` ids (63) and mastery ids (261)
are both richer than the 70 authorizations, so some will not map. Those are not concepts
the loop can track, and saying so is better than inventing a parent for each.

## 5. Loop tracking — how we will know it works

The founder asked for tracking explicitly. It is a per-concept report, not a dashboard,
and it is the acceptance test for this whole scope.

**Per concept, the five stage flags** from §1, plus the conversions between them:

| measure | definition |
|---|---|
| detect rate | fires per 100 user moves, by grade |
| plan reach | distinct users with an active focus on it |
| teach reach | distinct users with ≥1 lesson event |
| practise reach | distinct users with ≥1 attempt |
| **application rate** | `applied / (applied + missed)` on organic games |
| **transfer delta** | application rate after first teaching − before, same user, same concept |

`transfer delta` is the only one that answers the vision's actual question. It needs
`occurred_at` ordering against the teaching date, which the ledger already carries.

Three rules for this report, each from a mistake already made here:

1. **Denominators, never counts.** `applied / offered`, never "applied 3,595 times".
2. **A concept with no failures and a concept with no successes are both unfit** to carry
   a progress claim. `simple_hang` (0 applied / 607 missed) fails this today.
3. **Separate practice transfer from game transfer** and label which is shown. Puzzle
   success is not game understanding.

Where it lives: one script in `backend/scripts/`, the pattern used by
`what_a_real_user_sees.py`, runnable per concept and per user, with the three named
Phase-5 users as its fixture.

## 6. Priority order, with reasoning

1. **WS0 — concept identity.** Gates everything. Nothing else can be verified without it.
2. **Loop tracking report (§5).** Second, not last, deliberately: it is how every later
   phase gets judged, and building it early means each concept closed is provably closed.
3. **Close one family end-to-end that is NOT piece_safety** — `missed_tactic`. Chosen
   because it is the cheapest complete loop available: 4 PLAN detectors already exist,
   3,726 puzzles already exist, 9 active focus rows already exist, and only stage 3
   (content) is missing. One concept family proves the pattern; proving it on
   `piece_safety` would prove nothing, since that is the one already wired.
4. **Then king_safety** (same shape, thinner puzzle supply at 151).
5. **Stage 5 observers for authored endgame content** (Failure B) — engineering-heavy, and
   it unlocks 20 lessons at once.
6. **Decide `calculation_depth`** (Failure C) — a decision that can be taken at any point
   and should not block the above.
7. **`time_management`** last of the detected set, because it needs a teaching form that
   does not exist yet.

Phase 1's WS1 (review queue) and WS2 (mastery reads reviewed evidence) run alongside 1–3;
they are how evidence becomes admissible, and they are detailed in the Phase 1 scope.

## 7. Not in scope

- **Pillar Five retrieval** (teaching from other players' games). Separate, later, and
  dependent on this loop existing first.
- **New detectors** beyond stage-5 observers. 36 of 48 concept detectors are SHADOW; the
  constraint is verification, not supply.
- **Re-grading or re-authoring existing content.**
- **Opening breadth** (38 of 79 openings unpublishable) — a content backlog, tracked
  separately.

## 8. Verification

Each item gets a positive and a negative control, because several conclusions in this
document survived only until the negative control ran.

1. **Loop-complete is provable per concept.** For the chosen family, assert all five stage
   flags true and a non-zero application rate — and assert the same report shows a
   *missing* stage for a family that has one, so the report can fail.
2. **Non-zero delta before building.** For each concept closed, `transfer delta` must be
   computable and must differ from the pre-teaching baseline. If identical, the loop is not
   closed regardless of how the flags look.
3. **No identity regressions.** After WS0, every id currently resolvable must still
   resolve; the count of unmappable mastery ids must be *reported*, not silently dropped.
4. **Review stays stratified.** Per the Phase 1 revision, one event per (user, concept)
   pair round-robin — the largest pair holds 1,405 events.

## 9. Decisions needed

1. **Content authoring for `missed_tactic` and `king_safety`** — who writes it? This is
   the critical path for item 3, and it is authoring, not engineering.
2. **`calculation_depth`**: promote to a real concept, or re-label 47,319 puzzles?
3. **`simple_hang` has zero recorded successes.** Is the detector only capable of firing on
   failure? If so it needs a success branch before it can carry progress.
4. **Unmappable ids under WS0** — 261 mastery ids against 70 authorizations. Report and
   retire the remainder, or keep two tiers of concept?
5. **`time_management` teaching form** — pacing drills are a new surface. In or out?

---

## 10. CORRECTION — Failure A is a filter, not an authoring gap

Mohit asked why `missed_tactic` and `king_safety` cannot be taught. They can. §3.1 was
wrong, and it was wrong in the way I keep being wrong today: I read "no lessons were
taken" and concluded "no content exists".

### What actually exists for both concepts

| loop requirement | missed_tactic | king_safety |
|---|---|---|
| detector | **4 PLAN grade** (fork, pin, skewer, mate) | **1 PLAN** + 1 shadow |
| reaches the plan surface | 11 focus rows, **9 active** | 37 rows, **8 active** |
| puzzle positions | **3,726** | 151 |
| question + grading spec | **yes** — `lesson_question_spec.py` covers `missed_tactic`, `pin`, `skewer` | **yes** — covers `king_safety` |
| explanation content | `tactical_patterns.json` — 17 entries incl. `knight_fork`, `pin_to_king`, `skewer`, `discovered_attack` | `positional_rules.json` — 20 entries incl. `weakens_king`, `allows_back_rank`, `allows_checkmate` |

Nothing on that list needs authoring. Detectors at the lock's highest grade, positions,
questions, graders and explanation text all exist.

### The actual blocker: one hardcoded allowlist

`services/review_learning_adapter.py`, in `application_results_from_observations`:

```python
if not (simple_hang or exact_destination):
    continue
```

- `simple_hang` → `missed_pattern == "piece_safety" and subtype == "simple_hang"`
- `exact_destination` → the `destination_safety_exact` fact

Two observation shapes, both `piece_safety`. Every other observation is dropped before it
can become a `LessonResult` — which is exactly why lesson evidence exists for precisely
two `gap:` ids, and why both are piece_safety. It is not that other concepts are untaught;
it is that their evidence is discarded at this line.

### The same function explains the 0-applied mystery

§2 flagged that `gap:piece_safety:simple_hang` has 607 missed and zero applied, and called
it unfit to carry progress. The cause is three lines below the filter:

```python
application_outcome = (
    ApplicationOutcome.APPLIED
    if exact_destination and exact_outcome == "handled"
    else ApplicationOutcome.MISSED
)
```

`APPLIED` requires `exact_destination`. `simple_hang` can never satisfy it, so a
`simple_hang` observation is **structurally incapable of recording a success**. That is a
property of this expression, not of the detector, and not evidence that players never
avoid hanging a piece.

### What this does to the scope

Failure A drops from "author content for three concept families" to **widen one filter and
give each admitted shape an applied branch**. Far cheaper, and it moves the critical path
off authoring and back onto engineering — so item 3 in §6 is no longer blocked on a
content decision.

Two things it does *not* change:

- **Failure B** (authored endgame and opening lessons with no stage-5 observer) stands.
  Those concepts have content and no detector; this is the mirror case.
- **Failure C** (`calculation_depth`, 47,319 puzzles, no concept) stands unchanged.

And the widening is not free of judgement: each newly admitted observation shape needs a
defensible `applied` definition. For `destination_safety_exact` that is `outcome ==
"handled"`. For a missed fork, "applied" means the player *took* an available fork, which
is a different observation than "did not miss one" — and conflating them would manufacture
successes. That definition, per shape, is the real work.

---

## 11. Why only three tactics — and why the rest are nearly free

Mohit, on the three admitted motifs: *"what about attacking the defender, what
about deflection, what about there is a lot?"* He is right, and the reason is
one level below the admission table.

### The ceiling is the subtype classifier, not the adapter

`services/cognitive_gap_subtypes.py` cascades a missed tactic through exactly
four motif names — fork, pin, skewer, discovered_attack — plus a
prover-gated `missed_mate`, and everything else falls to a generic bucket:

```python
if (mv.get("cp_loss") or 0) >= 200:
    return ("missed_generic_tactic", ...)
```

Measured over every `missed_pattern == "missed_tactic"` observation:

| subtype | observations |
|---|---|
| **`missed_generic_tactic`** | **7,195** |
| `missed_pin` | 1,513 |
| `missed_skewer` | 1,021 |
| `missed_fork` | 902 |
| `missed_discovered_attack` | 480 |
| `missed_mate` | 442 |

**62% of missed tactics are unlabelled.** A generic row carries no motif hint
at all — no shape id, no pattern field — so deflection and
removing-the-defender misses are in there, unrecoverable without re-deriving.

`detector_quality` already records why this matters: naming motifs
individually was chosen over the generic bucket because a focus called
"generic tactic" is *"the repetition problem wearing a different hat."*

### The expensive part is already built

`backend/data/theory/tactical_patterns.json` authors **17** motifs, including
`removing_the_defender`, `deflection`, `decoy`, `overloaded_piece`,
`interference`, `zwischenzug`, `trapped_piece`, `back_rank_weakness`,
`discovered_check`, `pin_to_king`, `pin_to_queen`, `undefended_piece`,
`double_attack`.

And **eighteen provers exist**, each versioned with a `build_*_proof()` entry
point:

| prover | version |
|---|---|
| `removal_defender_puzzle_proof` | **v3** |
| `deflection_puzzle_proof` | v1 |
| `interference_puzzle_proof` | v1 |
| `trapped_piece_puzzle_proof` | v1 |
| `xray_attack_puzzle_proof` | v1 |
| `back_rank_mate_puzzle_proof` | v1 |
| plus | clearance, attraction, free_piece, advanced_pawn, defensive_move, forced_mate, fork, discovered_attack, aligned_tactic, destination_safety, piece_safety |

So for roughly ten motifs the prover is written and the content is authored,
and the classifier simply does not call it. The gap is a wire, not chess work
— the same shape as the adapter filter, one layer down.

### The part that makes this better than what I just shipped

A prover takes a position and a move. Run it on the **engine's best move** and
a true result means the motif was there and missed. Run it on the **played
move** and a true result means the player executed it.

That is a denominator-matched pair by construction, from one piece of code.

It is strictly better than the admitted-shape table in §10, where `missed_fork`
pairs a subtype against a separate `tactical_pattern_executed` vocabulary that
happens to align, and where `ignored_king_attack` had to be withdrawn precisely
because its two sides counted different populations. With a prover, that
failure mode cannot arise.

### The per-motif recipe, already proven once

`missed_pin` is the worked example and it is the template:

1. call the prover inside the subtype cascade; name `missed_<motif>` only when
   it returns true, so the label is true by construction rather than measured
2. register `gap:missed_tactic:missed_<motif>` at SHADOW
3. verify the player-facing sentence per FEN
4. promote to PLAN on that evidence
5. add to the §10 admission table, applied side = the same prover on the played
   move

Step 1 is what `missed_pin` did when it was gated on
`verify_created_alignment`: precision became 100% by construction and the three
disagreeing precision estimates stopped mattering.

### Cost, honestly

Not free. Each motif needs the wiring, the per-FEN sentence check, and a
re-derivation of stored observations — the 7,195 generic rows keep their label
until re-derived, exactly as the `missed_pin` authorization already warns. And
the subtype cascade is ordered, so inserting motifs changes which name a
position gets when two apply; that ordering is a coaching judgement about which
lesson is the more useful one to name, not a technical detail.

**Revised breadth estimate:** 3 tactic concepts today → roughly 10–13 with the
provers that already exist, bounded by sentence verification rather than by
detection.

---

## 12. MEASURED: the motif-naming route is far thinner than §11 estimated

§11 estimated 10–13 tactic concepts from the provers that already exist. That
estimate was wrong, and the two measurements that killed it are below. I did
not wire anything.

### 12.1 Prover reach on the generic bucket, strictly verified

Each prover returns a bundle plus a `verifier.verified` flag from an
independent board check. The two are different detectors and only the strict
one is defensible. Run over 1,500 real `missed_generic_tactic` observations:

| prover | bundle returned | **strictly verified** |
|---|---|---|
| clearance | 163 | **121** |
| deflection | 39 | **39** |
| attraction | 22 | **22** |
| xray_attack | 19 | 16 |
| interference | 16 | 15 |
| remove_defender | **150** | **5** |
| trapped_piece | 1 | 1 |
| free_piece, back_rank_mate | 0 | 0 |
| **any prover** | 366 (24.4%) | **200 (13.3%)** |

So about 959 of the 7,195 generic observations are nameable — before precision
is checked. Note `remove_defender`: 150 loose against 5 strict. My earlier
"8% of the generic bucket" figure was the loose signal and overstated it
thirtyfold.

### 12.2 Precision against Lichess themes, with hard negatives

`lichess_puzzles` carries 4,110,434 positions and 74 theme tags. The control
arm is deliberately *other tactical themes* rather than random positions,
because a random position is trivial to reject and would flatter the number;
a false positive among real tactics is the mistake that actually reaches a
player.

| motif | recall | precision | false positives | strict fires |
|---|---|---|---|---|
| **attraction** | 95.7% | **100.0%** | 0 | 22 |
| deflection | 93.4% | 94.2% | 52 | 39 |
| **clearance** | 77.1% | **75.3%** | 228 | **121** |
| **remove_defender** | 63.8% | **100.0%** | 0 | 5 |

The highest-reach prover is the least precise. `clearance` supplies 121 of the
200 strict fires and must not be named at 75.3%, which is nowhere near the
lock's 95% bar. `deflection` sits at 94.2% — one tightening short, not a
failure.

**So the precise, shippable subset is attraction plus remove_defender: 27 of
1,500, about 130 of 7,195 — 1.8%, not the 13.3% the reach table suggested and
nothing like 10–13 new concepts.**

### 12.3 Recommendation: do not wire this now

Naming 130 observations costs a classifier change, an authorization entry, an
authored sentence, per-FEN verification, an admission-table entry and a
re-derivation of stored observations. That is the full ceremony for a 1.8%
dent, and the ceremony is right — it is what keeps precision at 100% — so the
answer is not to skip it but to spend it on something with reach.

The more useful finding is the one underneath: **the 7,195 are mostly not
single-motif tactics.** Three quarters of them no prover recognises at all,
and the quarter that is recognised is dominated by the one prover that cannot
be trusted. Mohit's instinct that "there is a lot" is right about chess and
wrong about this bucket — the volume here is not in nameable motifs. The next
honest question is what those positions actually are, which is cheap to
characterise and would decide whether a new detector family is warranted at
all.

`deflection` at 94.2% is the one candidate worth a second look: it has real
reach relative to the precise set and needs tightening rather than inventing.

### 12.4 What was built

`backend/scripts/validate_motif_prover_against_lichess.py` — parameterised
over six motif/theme pairs, hard-negative control, reports both the loose and
strict signals. Whenever a motif's reach justifies the ceremony, its precision
gate is now one command.

---

## 13. The residue was mostly lost mates, and that one is nearly free

§12 recommended characterising the generic bucket instead of guessing another
motif. Doing so found the win that two motif guesses had missed.

### 13.1 What the 7,195 actually are

Walking the engine's own best line over 1,500 of them:

| the best line | share |
|---|---|
| wins material within 4 plies | 50.9% |
| **no material gain at all: positional** | **30.5%** |
| wins material only later | 11.1% |
| mate in the best line | 7.5% |

The best move is a capture 51% of the time, a check 29%, quiet 20%. By phase,
the endgame slice is 47% positional — so an endgame "missed tactic" usually
is not one. And 17.5% of the played moves lose material outright, which is a
different error from missing something.

The 30.5% matter on their own: `missed_generic_tactic` is assigned on a
200-centipawn loss with no motif match, so a third of the bucket is a
**positional** loss wearing a tactical name. No authorization exists for the
generic subtype, so it cannot reach a player as a focus today — the mislabel
is internal, which is why this is recorded rather than treated as urgent.

### 13.2 The finding: 41.5% had a forced mate and lost it

`mate_info` is stored per move, signed and white-relative. Reading it over
2,000 generic observations: **41.5% had a forced mate for the mover that the
played move threw away.** Distances are flat — mate in two 79, three 69, four
68, five 58, six 40, seven 46, eight 41, nine 46.

The cause is one line. The classifier's mate check pushes the engine's move and
asks `is_checkmate()`, which only ever catches **mate in one**. Everything
longer fell through to generic.

This is the cheap, high-reach fix the last two attempts were looking for, and
it needs none of the ceremony a new motif needs: `missed_mate` already exists,
`gap:missed_tactic:missed_mate` is already **PLAN** grade, the sentence is
already authored, and the renderer already dispatches it.

### 13.3 Measured effect

Re-classifying 1,500 stored generic observations through the real classifier:
**642 (42.8%) move out of the bucket into `missed_mate`** — about 3,079 of
7,195, roughly seven times that concept's current 442 observations.

For comparison, the two motif routes I recommended before measuring would have
named about 130 (§12) and about 24 (remove_defender alone).

### 13.4 One knob built, measured, and removed

I first scaled severity by mate distance — critical within four, moderate
beyond — on the reasoning that telling a 1200 player they missed a mate in
nine is discouraging. Then I measured it: **all 831 lost mates are already
promoted by `_promote_severity`**, because a lost mate always carries a
cp_loss at or above 400. The split would have changed the outcome on **0.0%**
of them.

So it was removed. Depth framing belongs to the caption layer, where it can
actually act — and renaming the label by depth would have been deleting a true
detection to fix a framing problem.

### 13.5 Caveat

Observations are derived once at analysis time, so this changes newly analysed
games only. The 7,195 stored rows keep their generic label until re-derived,
exactly as the `missed_pin` authorization already warns for its own gate.
