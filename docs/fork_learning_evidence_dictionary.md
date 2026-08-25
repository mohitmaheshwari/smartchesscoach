# Fork Learning Evidence Dictionary

**Status:** DRAFT v1 — executable rules awaiting Mohit approval  
**Date:** 2026-08-24  
**Applies to:** migrated knight-fork lesson only  
**Projection owner:** `backend/services/concept_mastery_service.py`

This document defines what ChessGuru may infer from a learner interaction. It separates lesson
stages from internal evidence checkpoints and prevents exposure, hints, reveals, repeated items, or
legacy puzzle labels from being presented as learning.

---

## 1. Terms that must not be conflated

- **Lesson stage** is a screen in the signed knight-fork journey.
- **Internal checkpoint** is the strongest capability supported by eligible evidence.
- **Learner state** is the three-state user-facing projection: Learning, Remembered, or Proven in
  games, optionally modified by Refresh needed.
- **Highest checkpoint** is historical best evidence and never decreases.
- **Current checkpoint** is the strongest still-fresh evidence and may decrease.
- **Lesson Stage 8** is a guided personal role reversal. It does not earn internal checkpoint 8.
- **Internal checkpoint 8** requires verified behavior in a real-game opportunity after teaching.

The user never sees an eight-rung ladder.

---

## 2. Evidence invariants

Evidence can advance a checkpoint only when all applicable conditions hold:

1. the asset revision is approved Gold for the learner's cohort;
2. the event chain has stable user, session, lesson, skill, asset, and content-version identifiers;
3. the response was graded by the frozen canonical grader version;
4. the learner received no more assistance than that checkpoint permits;
5. the item was not already revealed, skipped, corrupted, duplicated within the scored form, or
   invalidated by a semantic content change;
6. orientation and prompt role satisfy the checkpoint contract;
7. calibration users and admin sessions are excluded from confirmatory learning claims;
8. a personal claim uses exact provenance and reviewed content.

An event can remain useful for coaching even when `evidence_eligible=false`. Every rejection carries
one or more machine-readable reasons; it never silently disappears.

---

## 3. Checkpoint rules

### Checkpoint 1 — Introduced

**Capability:** The coach has explicitly introduced the knight-fork idea and its two-target
geometry.

**Accepted evidence:** A reviewed explanation/example was presented and the learner completed the
required acknowledgement interaction.

**Rejected as stronger evidence:** Merely opening the page, an interrupted presentation, a tooltip,
marketing copy, an old motif label, or a passive board impression.

**Help/reveal:** Allowed. This checkpoint is exposure, not recall.

**Freshness/demotion:** Current can return to Not measured if the only introduction belongs to a
semantically invalidated content version. Time alone does not convert introduction into recall.

**Test-out:** A valid higher checkpoint implies checkpoint 1; the learner need not replay the
introduction.

### Checkpoint 2 — Recognises with help

**Capability:** The learner identifies the fork square or targets after a visual/verbal scaffold.

**Accepted evidence:** A correct response on a reviewed recognition item after one or more declared
hints, highlights, arrows, target emphasis, or constrained choices.

**Rejected as stronger evidence:** A revealed answer, a click on a single enabled square, a correct
response after the solution was shown, or an answer copied from an immediately repeated item.

**Help/reveal:** Hints cap the event at checkpoint 2. Reveal grants no recognition checkpoint.

**Freshness/demotion:** A later assisted success can support current checkpoint 2 after an
independent failure, without erasing a higher historical checkpoint.

**Test-out:** Higher independent evidence implies this checkpoint.

### Checkpoint 3 — Sees the geometry independently

**Capability:** The learner identifies the fork square and attacked targets without instructional
help.

**Accepted evidence:** A correct first response on a reviewed clear-geometry item with zero hints,
zero reveals, no highlighted targets, and no lesson-name cue in the prompt.

**Rejected evidence:** Second-attempt success after feedback, assisted choices that make the answer
obvious, exact repetition of a recently shown position, or a correct answer based only on SAN text.

**Help/reveal:** Any hint caps at checkpoint 2. Reveal grants no checkpoint for that item.

**Freshness/demotion:** An unassisted failure on comparable fresh content can lower current evidence
to checkpoint 2 or lower according to the frozen reducer; highest remains unchanged.

**Test-out:** May be earned by an unseen baseline item if its role and difficulty were frozen before
the response.

### Checkpoint 4 — Executes it cleanly

**Capability:** The learner legally plays a knight move that creates the named fork in a clear
position.

**Accepted evidence:** A first-attempt legal board move, without hints or reveal, for which the
canonical fork evidence fires, `is_named_fork()` is true, and the attacker is a knight. A reviewed
alternative move is accepted when it satisfies the asset's frozen answer contract.

**Rejected evidence:** Exact engine-move equality without fork evidence, an illegal move, a raw
pawn-only/non-promoted shape, a move that gives check but leaves the checker unsafely capturable, a
retry after the answer was exposed, or a move in a corrupt orientation.

**Help/reveal:** A directional hint or candidate restriction prevents checkpoint 4 for that item.
Reveal grants no checkpoint.

**Freshness/demotion:** A later clean execution failure on comparable fresh content may reduce
current evidence; it cannot erase highest checkpoint 4.

**Test-out:** May be earned on a frozen unseen execution item.

### Checkpoint 5 — Handles variation

**Capability:** The learner succeeds when surface features change: reversed orientation, different
target arrangement, or a reviewed counterexample where no named fork should be claimed.

**Accepted evidence:** Unassisted first-attempt success across the frozen variation contract,
including required negative/counterexample decisions. The form must prevent success through a
single repeated visual template.

**Rejected evidence:** Passing only positive fork positions, passing only one orientation, seeing
the lesson name in the prompt, or treating every check-plus-target shape as a user-visible fork.

**Help/reveal:** Any help on a required variation prevents checkpoint 5 for that form. The learner
may continue learning but must use a fresh form for evidence.

**Freshness/demotion:** Failure on a required variation lowers current evidence to the strongest
still-supported checkpoint. Highest remains.

**Test-out:** May be earned by a frozen unseen form containing all required variation roles.

### Checkpoint 6 — Finds it in mixed unseen positions

**Capability:** The learner discriminates knight forks from non-forks in an unseen mixed set without
being told which concept is present.

**Accepted evidence:** The learner completes the frozen mixed form, with no hints/reveals, meeting
the pre-registered item-level rule across positive and negative positions. Forms are
difficulty-matched and role-counterbalanced.

**Rejected evidence:** A fork-only puzzle queue, a set labelled “Knight forks,” a convenient subset
selected after outcomes, a group average standing in for the individual's evidence, or a form with
failed difficulty equivalence.

**Help/reveal:** Help makes the affected form ineligible for checkpoint 6. Practice can continue on
different content.

**Freshness/demotion:** This is immediate independent learning evidence, not retention. It remains
current only until the frozen delayed-recall window requires revalidation.

**Test-out:** A baseline test-out may grant at most checkpoint 6 when the pre-registered bar is met.
It never grants remembered or proven-in-games status.

### Checkpoint 7 — Remembers after a delay

**Capability:** The learner independently retains the skill after the calibrated delay.

**Accepted evidence:** A completed delayed form, different from the learner's baseline and post
forms but matched in difficulty and counterbalanced role, meeting the frozen individual rule with no
hints, reveals, or advance concept cue.

**Rejected evidence:** Immediate repetition, a notification that names the answer pattern before the
test, reused positions, missing follow-up treated as success, an unlocked delay, or calibration users
included in confirmatory results.

**Help/reveal:** Help prevents checkpoint 7 and can support only the lower checkpoint its interaction
actually demonstrates.

**Freshness/demotion:** A missed or failed due recall sets `Refresh needed` and lowers
`current_demonstrated_checkpoint` to the strongest fresh evidence. The precise expiry window,
missing-follow-up rule, and retry schedule are locked via data before confirmation. Highest
checkpoint 7 remains historical.

**Test-out:** Cannot be granted from an immediate baseline. It requires elapsed time and a matched,
unseen delayed form.

### Checkpoint 8 — Applies it in a real game

**Capability:** After teaching, the learner handles a verified real-game fork opportunity in play.

**Accepted evidence:** A canonical detector establishes that a genuine application opportunity
occurred after teaching, exact session/game timing proves ordering, the learner's response is graded
against the frozen opportunity contract, and the event is not a guided lesson position. Success can
mean creating a sound named fork or avoiding a verified opponent fork opportunity, as separately
defined before rollout.

**Rejected evidence:** Completing personal lesson Stage 8, solving a personal puzzle, an old game
played before teaching, absence of a detected fork in a game without a verified opportunity, an
ambiguous-provenance position, or a coach intervention that supplied the answer before the move.

**Help/reveal:** Guided or revealed gameplay moments do not prove checkpoint 8.

**Freshness/demotion:** `highest_demonstrated_checkpoint=8` is permanent history. The learner-facing
`Proven in games` state may gain `Refresh needed` or lower current evidence only under the future
pre-registered repeated-miss/opportunity rule; one game with no opportunity cannot demote it.

**Test-out:** No lesson test-out can grant checkpoint 8.

---

## 4. Learner-facing projection

The reducer emits one state from the strongest current eligible evidence:

| Current evidence | Learner-facing state |
|---|---|
| Not measured through checkpoint 6 | `Learning` |
| Checkpoint 7 | `Remembered` |
| Checkpoint 8 | `Proven in games` |

`Refresh needed` is a modifier, not a fourth achievement ladder. It appears when due retention or
the future verified-application freshness rule is not satisfied. The UI also shows a concrete
capability and next action; it never shows “rung 6/8.”

`highest_demonstrated_checkpoint` records what the learner has demonstrated at least once.
`current_demonstrated_checkpoint` records what remains supported now. A reduction in current
evidence does not rewrite history.

All numeric pass bars, minimum item counts, delay windows, retry intervals, freshness periods, and
repeated-miss rules are deliberately absent until `/lock-via-data` closes them.

---

## 5. Assistance and attempt precedence

For one asset presentation, the reducer applies this order:

1. semantic invalidation or corrupted content -> no evidence;
2. reveal before a correct response -> no checkpoint for that item;
3. hint/highlight/candidate restriction -> cap at checkpoint 2 unless the checkpoint explicitly
   requires a different lower cap;
4. corrective feedback or retry -> not first-attempt evidence for checkpoints 3–7;
5. unassisted first response -> evaluate against the checkpoint and form contract;
6. later assistance cannot upgrade earlier evidence, and later success cannot erase the recorded
   initial failure.

Practice feedback remains supportive even when an interaction is evidence-ineligible.

---

## 6. Historical evidence and migration

### Does not count automatically

- `puzzle_attempts` rows;
- motif drill views or solution reveals;
- active-recall `learning_checkpoints` rows;
- legacy mastery labels;
- generic fork counts in player profiles;
- games without a verified post-teaching application opportunity.

These stores lack one or more required semantics: content revision, assistance history, prompt role,
orientation, first-attempt status, matched form, timing order, or canonical grader version.

### May count through an audited adapter

A historical source may map to a checkpoint only after a written equivalence audit proves every
required field or reconstructs it without guessing. The adapter emits the original source reference,
the audit version, and explicit eligibility reasons. It cannot infer help status or content role from
absence. Unsupported history begins as Not measured and the learner may test out on unseen Gold
content.

---

## 7. Content-version invalidation

| Change | Evidence treatment |
|---|---|
| Spelling, punctuation, or visual spacing only | Preserve evidence. |
| Prompt meaning, hint strength, target highlight, accepted answer, orientation, FEN, side to move, grader, difficulty role, or assessment membership changes | New content version; affected pending evidence is not silently carried forward. |
| Source puzzle changes while a session is active | Session continues on its frozen revision or is explicitly invalidated with a recorded reason. |
| Canonical fork detector/promotion semantics change | Recompute eligibility under a named migration; never relabel historical evidence silently. |

Historical events remain immutable for audit. The projection chooses which versions remain
comparable under an explicit migration rule.

---

## 8. Minimum executable fixture set

Before the learner-facing projection is enabled, reducer tests must cover at least:

- introduction only -> Learning, checkpoint 1;
- recognition after a highlight -> checkpoint 2, never 3;
- reveal then correct -> no recognition checkpoint for that item;
- independent geometry -> checkpoint 3;
- legal alternative named knight fork -> checkpoint 4;
- exact engine move without canonical fork evidence -> rejected for checkpoint 4;
- positive-only form -> cannot earn checkpoint 5 or 6;
- mixed unseen form with a failed negative -> no checkpoint 6;
- baseline test-out -> at most checkpoint 6;
- immediate repeated set -> cannot earn checkpoint 7;
- matched delayed form -> checkpoint 7 and Remembered;
- failed due recall -> Refresh needed, lower current, preserve highest;
- personal Stage 8 role reversal -> no internal checkpoint 8;
- verified post-teaching game opportunity and success -> checkpoint 8 and Proven in games;
- game with no verified opportunity -> no checkpoint 8 success or failure;
- ambiguous provenance -> no personal or application credit;
- semantic version change -> pending evidence invalidated, history retained;
- admin/Provisional event -> visible for plumbing, ineligible for mastery and cohort analysis.

The implementation may add more fixtures. It may not weaken these rules without changing the signed
scope and this dictionary explicitly.
