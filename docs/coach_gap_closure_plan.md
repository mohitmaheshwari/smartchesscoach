# Gap-Closure Plan — "a personal coach that feels human and makes you improve"

**Status:** DRAFT v1, 2026-08-27. Derived from the investor pitch, checked
against code and the production corpus. Strategy lives in
`chessguru_master_plan.md`; this is the actionable backlog.

**Runs alongside the UI/UX rebuild.** That work owns the four screens. This work
owns what those screens are allowed to say.

**How to read a row:** every item names the *verified* gap, not a suspicion.
Where a claim in the pitch is currently unsupportable, it says so.

---

## The pitch, reduced to two promises

| Promise | What has to be true |
|---|---|
| **Feels human** | It remembers, it says "again", it speaks once and simply, it knows what *you* are working on |
| **Makes you improve** | One plan, tracked, proven with real evidence, honest when there is none |

Everything below serves one of those two. Anything that serves neither is not on
this list.

---

## Tier 0 — without these, the pitch is literally false

### 0.1 · Turn PIC on and walk the loop · **S**
It landed (`2497e47e`), 53 tests green, flag default-off, **and no human has ever
used it.** Nothing else on this list can be trusted until one person goes
diagnosis → practice → checkpoint → verdict end to end.
**Done when:** you have personally completed one full cycle and filed what broke.

### 0.2 · Focus → game review · **M** ★ the pitch sentence
> *"in game decryption the coach actively tells you the mistakes that are in your focus"*

**Verified gap:** neither `caption_pipeline` nor `game_decryption` reads
`user_active_focus`. Review is focus-blind today. `user_active_focus` is consumed
by `focus_bridge`, `daily_fix_service`, `coach_memory`, emails and the weakness
pickers — everywhere *except* the surface users actually look at.
**Build:** a compact repeated-pattern block on the focus moment, through the
central caption pipeline. No parallel caption path.
**Done when:** opening a reviewed game surfaces the active focus's moment first,
with recurrence, in the same words as everywhere else.

### 0.3 · Focus + motifs → Play With Coach · **M** ★ "you're doing it *again*"
**Verified gap:** nothing in `backend/coach_play/` reads `motif_profiles` or
`user_active_focus`. PWC is intelligent about *this position* and blind to your
history — it coaches like a strong stranger, not like someone who has watched you
for a month.
**Build:** extend the conductor pattern (which already does exactly this for
openings) to motifs; let the live coach read the active focus.
**Done when:** PWC can say "again" and be right, with evidence.

### 0.4 · Reconcile the two rep paths · **M**
Two implementations coexist: the PIC session serving `best_move_san` puzzles
through `teaching_engine`, and the `rep_generator` + `RepRunner` serving
`is_safe` / `who_takes` scans. **Do not build a third.**
**Recommendation:** keep the PIC session plumbing (resumable sessions, idempotent
events, `evidence_eligible=false` for assisted practice — that machinery is
good), and make the *rep type* a parameter so the scan types run inside it.
**Also:** one locked constant, two definitions — `D_LIVE_SEE_FLOOR_CP` in the
deriver vs `SEE_FLOOR_CP` in the generator. Collapse to one.

---

## Tier 1 — without these, it is accurate but not human

### 1.1 · Named leaks · **S** ★ best effort-to-feel ratio on this list
A coach names your mistake and the name is how you catch yourself mid-game.
Today the product can say "piece_safety"; it cannot say *"the square you don't
check."*
**Build:** every active focus carries a short, memorable, personal name, derived
deterministically (no LLM), used identically on Home, review, reps, PWC and the
verdict.
**Done when:** the player can state their weakness in their own words.

### 1.2 · Where-was-it-lost detector · **M**
**The trap:** where a game *ended* is not where it was *lost*. Most endgame
losses were decided in the middlegame. Routing on final phase teaches endgames to
people whose problem is the middlegame.
**Build:** decisive evaluation swing from stored eval history.
**Unlocks:** phase routing, "tap where you lost it" (2.5), honest verdicts.

### 1.3 · Backfill `games.user_rating` · **S**
**Verified:** 663 of 858 corpus hangs (**77%**) fall in rating band `unknown`
because the field is absent. Rating-aware coaching silently degrades for most of
the corpus. `backfill_game_user_rating.py` already exists — run it, report
coverage, leave true unknowns as `unknown`.

### 1.4 · Quarantine the pre-SEE residue · **S**
**Verified:** 1,145 of 2,003 `simple_hang` events (**57%**) sit on schema <16,
whose predecessor over-fired ~⅓ of the time. Must never enter a baseline or a
verdict. Either re-derive or exclude explicitly at query level.

### 1.5 · One progress authority · **M**
Multiple improvement calculations exist across routes and services and can
disagree. `concept_mastery_service` owns the learner-facing projection
(`Learning` / `Remembered` / `Proven in games`). Everything else becomes an
evidence producer. Demote or retire the rivals — do not add a fourth.

---

## Tier 2 — what makes it a coach rather than a good tool

### 2.1 · Endgame detectors · **L**
**Verified:** endgame failures are 25.3% `generic_oversight` + 25.0%
`generic_endgame_slip` — **half of all endgame detections are "something went
wrong here."** You have 6 endgame lessons and nothing that says which one a
player needs. Until this splits, "you need endgame work" is the most specific
honest statement available.

### 2.2 · Concept tags → the variety engine · **M**
Tag traps, motifs, endgame lessons and opening lessons by concept so the coach
can ask for *"material for `piece_safety`, unseen by this player, in a format not
used in two days."* This is what stops the same drill five days running. A trap
is not a separate subject — it is the memorable version of the current lesson.

### 2.3 · Opening curation, 79 → 2 · **M**
No coach hands a 900 a catalog. Derive the player's two from games actually
played, assign them, hide the other 77. The catalog becomes the coach's library,
not the student's menu.

### 2.4 · `which_is_better` positional reps · **M**
Coaches teach position by **contrast** — two boards, same material, "why is White
better here?" — and that is engine-gradeable. Opens open files, outposts, weak
squares and pawn chains to the same generated, verified, zero-authoring machine
that unlocked piece-safety reps.

### 2.5 · "Tap where you lost it" · **M** ★ a second provable metric
A coach asks *before* telling. After a loss, the player taps the move they think
lost it; then the engine's swing move is revealed. The gap between guess and
truth is **calibration** — and it improves measurably. *"A month ago you couldn't
find your own mistakes. Now you're within two moves."* Depends on 1.2.

### 2.6 · Praise the decision, not the result · **S**
D_live makes this provable: a loss with 6 of 6 safety decisions handled is
objectively progress. The verdict language should say so. This is the retention
mechanic that does not lie.

### 2.7 · Know when to stop them playing · **S**
"Three losses in twenty minutes — go home, we'll look tomorrow." Anti-engagement,
which is exactly why it buys the trust everything else spends. Opt-out, never
shaming.

---

## Withdrawn from the pitch until fixed

> *"time you've taken per move… are you taking time now to solve things, or still
> making the same mistake"*

**Three independent blockers, all measured 2026-08-27:**

| Finding | Number |
|---|---|
| Moves carrying `time_spent_seconds` | **20.8%** (31,128 / 149,886) |
| `time_flag` set at all | **0.56%** (846 moves: 821 impulsive_critical, 25 time_pressure_blunder) |
| `cognitive_gap == "time_pressure"` | **0 moves, 0 users — the detector never fires** |

The `time_pressure` category exists in the taxonomy and has never produced a
single observation. This confirms the suspicion filed in the July 2026 study
roster ("no users found with ≥10 mistakes in time_pressure — check if detection
is working") that was never followed up.

**Do not repeat this claim to an investor until:** clock data coverage is raised
(imported PGNs need clock annotations), the detector is fixed or deleted, and a
now-vs-before trend actually exists. Three separate pieces of work, none started.

---

## Housekeeping

- `backend/coach_play/teaching_coach.py` — **dead**, imported by nothing. Revive
  or delete before it confuses the next person.
- `npm run build` runs without an explicit `CI` override; GitHub Actions sets
  `CI=true`, which turns existing `react-hooks/exhaustive-deps` warnings in
  `Reflect.jsx`, `TrainingNew.jsx` and `PostLossRecovery.jsx` into errors. That
  build step may already be failing.
- Local `working-code` still carries 4 commits duplicated upstream. Reset to
  `origin/working-code` once the worktree is clean.

---

## Sequence

```
0.1 walk the loop
 └─ 0.4 reconcile rep paths ──┐
 └─ 0.2 focus → review        ├─ 1.1 named leaks (makes 0.2 + 0.3 land)
 └─ 0.3 focus + motifs → PWC ─┘
        │
        └─ 1.2 where-was-it-lost ─┬─ 2.1 endgame detectors
                                  └─ 2.5 tap where you lost it
1.3 / 1.4 data hygiene — any time, no dependencies
1.5 one progress authority — before any new surface reads progress
```

**Tier 0 is roughly three weeks of wiring.** It contains no new science, and at
the end of it the pitch is true rather than aspirational.

---

## The honesty register stays

Guarding this is the moat; everyone else inflates. Still un-claimable:
rating improvement, any "fixed" outside piece safety, time habits, endgame
specifics, fork weakness as a focus, and any date for a fix.
