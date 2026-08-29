# ChessGuru — Master Plan

**Status:** DRAFT v1, 2026-08-27. Written against verified code and production
corpus, not against intentions. Every "built" claim below was checked.

**The product in one line:** a chess coach that watches your games, finds the one
thing that keeps costing you, drills it until it stops, and proves it stopped.

---

## PART 1 — Where we actually are

Verified against the codebase and the production database, not the roadmap.

| Capability | State | Evidence |
|---|---|---|
| Watch & analyse games | ✅ **Built** | 14,021 games · 13,425 analyses · 421,464 move observations |
| Detect mistakes | 🟡 **Uneven** | `piece_safety` 96.9% precision. But ~50% of endgame and much of middlegame lands in generic buckets |
| Verified per-move explanations | ✅ **Built** | Central caption pipeline, ~98% coverage, engine-verified whys |
| Prove improvement | ✅ **Built, unproven** | `piece_safety.d_live.v1`: 22,583 decisions / 149,886 moves (15.07%), 9.47% miss |
| Improvement plan + tracking | ✅ **Built, OFF** | PIC landed `2497e47e`; flag default-off; zero users have touched it |
| Live in-game coaching | ✅ **Strong** | Guardian (<100ms), coaching_triggers (knows when to be quiet), punishment_puzzle, CPR |
| **Focus visible in game review** | 🔴 **Missing** | `caption_pipeline` / `game_decryption` never read `user_active_focus` |
| **"You're doing it again" in PWC** | 🔴 **Missing** | Nothing in `coach_play/` reads `motif_profiles` or the active focus |
| Named, memorable leaks | 🔴 **Missing** | Designed, not built |
| Time-habit trend | 🔴 **Missing** | Per-move time is stored and consumed; no now-vs-before comparison exists |
| Endgame routing | 🔴 **Missing** | 6 lessons exist; no detector says which one you need |

**The diagnosis: the brain is built and two nerves are not connected.**
`user_active_focus` — the spine — reaches emails, daily-fix and the weakness
picker, but not the two surfaces people actually use.

Nothing below requires research. It is wiring, naming, and a small number of new
detectors.

---

## PART 2 — The complete user journey

### Day 0 · The first ten minutes

**1. Connect** — one action, no menu.
> *Let ChessGuru watch how you actually play.* → Connect Chess.com / Lichess

**2. The wait is part of the product.** Analysis takes time. Do not show a
spinner. Show games arriving and results appearing — "34 games found · analysing
your last 20". If they have no account, a 6-position provisional diagnostic
substitutes; it chooses where to start, it is never called a diagnosis.

**3. The diagnosis — one claim, their evidence.**
```
I watched your last 20 games.

One thing keeps happening: you move a piece
to a square your opponent can take.

Four times in your last ten games.
                    [ Show me the first one ]
```

**4. The proof — three positions from THEIR games.** Board, their actual move,
the piece that took it. Not a lecture; three boards.

**5. The name.** The leak gets a short, memorable, personal name — "the square
you don't check". This name is then used everywhere, forever.

**6. Eight reps.** ~3 minutes. Board-first. `is_safe` → `who_takes`. Generated,
verified, own-positions first.

**7. The plan.** Exit criteria, never dates (PART 3).

**8. The handoff.** *"Go play a game. I'll watch."*

**Success test for Day 0:** the player can state their own weakness in their own
words, and has already worked on it.

### Day 1–N · The loop

Home shows **one** action, chosen by cascade:

1. New game since last visit → **the moment from that game**
2. Checkpoint due → unannounced mixed set
3. Delayed recall due → one item, folded in, pattern unnamed
4. Focus needs practice → reps
5. Nothing pending → syllabus item, with a personal reason

Rule 1 keeps it personal. Rule 5 keeps it from going silent. The player never
chooses.

### Every game they play

| Surface | What the coach does |
|---|---|
| **Before** | One line: the instruction they're carrying |
| **During (PWC)** | Guardian intercepts the blunder; punishment puzzle when the coach errs; silence otherwise |
| **After** | Verdict: *"came up 7 times, you handled 6. Move 31."* |
| **Review** | The focus moment surfaced first, with recurrence: *"third time this month"* |

### Resolution

When the exit criteria are met: promotion, not a certificate. The old habit moves
to background and is re-checked quietly forever. The next focus is introduced by
the same coach voice, referencing the last one.

---

## PART 3 — The plan model

**The plan is a commitment with an evidence-defined finish line. Never a schedule.**

We have zero data on how long a fix takes, so any date is fiction — and honesty
is the moat.

| Stage | Meaning | Exit criterion |
|---|---|---|
| **See it** | Spots the danger in a position | 8 reps, mostly unassisted |
| **Do it** | Handles it with no help | one silent checkpoint, no hints |
| **Prove it** | Does it in real games | N clean D_live decisions |
| **Fixed** | It's a habit | background, re-checked forever |

These map 1:1 onto PIC's existing state machine — `diagnosed` →
`practice_assisted` → `checkpoint_*` → `external_*` → `resolved`. **The plan is
the user-facing face of machinery that already exists.**

What the player sees: a number from their own games that moves (`14 of 20
clean`), no dates, and one teaser of what's next. Never the full list of their
weaknesses — that is demoralising and invites cherry-picking.

---

## PART 4 — Content routing: puzzles, openings, traps, endgames

The library is not a menu. It is what the coach reaches for.

### Puzzles / reps — **solved, generated, no authoring**

The unlock: *"is this square safe, who takes it?"* is engine-answerable, unlike
*"what's the best move?"*. So reps are generated and verified from data we hold.

Priority: **their own positions** → rating-matched community → corpus.
Sources: 149,886 v16 observations · 37,266 community positions.

### Traps — **teaching material for the active focus**

28 families exist. A trap is a piece-safety story with a name (Légal's Mate =
"you took without checking what was defended"). Traps are not a separate subject;
they are the memorable version of the current lesson. **Needs: concept tags on
each trap** so the coach can ask for "material for `piece_safety`, unseen, format
not used in 2 days."

### Openings — **curate 79 down to 2**

No coach hands a 900 a catalog. Derive the player's two from games actually
played, assign them, hide the rest. The conductor already catches recurring
opening mistakes and knows deviation ≠ mistake. **Needs: curation, not content.**

### Endgames — **honest gap**

6 lessons exist. **No detector says which one a player needs** — 50% of endgame
failures are `generic_oversight` / `generic_endgame_slip`. Until detectors split
those, the most specific honest statement is "you need endgame work."
**Needs: real detectors matched to the 6 lessons.**

### Positional chess — **drillable, and this was the surprise**

A coach teaches position by **contrast**: two boards, same material, "why is
White better here?" That is engine-gradeable. A `which_is_better` rep type opens
open files, outposts, weak squares and pawn chains to the same verified-generation
machine. No authoring.

---

## PART 5 — Execution plan

Sequenced by dependency. Sizes are estimates, not commitments.

### Phase 0 — Turn on what exists · **S**
- Flip `PERSONAL_IMPROVEMENT_CYCLE_ENABLED` for admin; walk the whole loop yourself
- Fix anything the walk breaks
- **Why first:** PIC is built, green, and has never been used by a human. Costs
  almost nothing; de-risks everything after it.

### Phase 1 — The activation slice · **L** ★ the demo
- Onboarding → diagnosis → 3 evidence boards → name → 8 reps → plan
- Wire `RepRunner` to the rep generator through PIC's session
- **Reconcile the two parallel paths first** (their session plumbing + the scan
  rep types) — do not build a third
- **Deliverable:** a new user feels the pitch in 10 minutes

### Phase 2 — Connect the nerves · **M** ★ the pitch
- **Focus → review**: compact repeated-pattern block in DecryptionV5, through the
  central caption pipeline, no parallel path
- **Focus + motifs → PWC**: extend the conductor pattern from openings to motifs
- **Named leaks** used consistently on every surface
- **Deliverable:** "you're doing it *again*" becomes possible

### Phase 3 — Close the loop · **M**
- Verdict after real games; the plan number moves from D_live
- Resolution → next focus, with continuity language
- Where-was-it-lost detector (decisive eval swing, not final phase)
- **Deliverable:** provable improvement, end to end

### Phase 4 — Breadth · **L**
- Endgame detectors splitting the generic buckets
- `which_is_better` positional reps
- Opening curation (79 → 2)
- Concept tags across traps/motifs/endgames → the variety engine
- Second and third focus types
- **Deliverable:** the coach covers enough ground to feel like a coach

### Phase 5 — Prove and price · **M**
- Within-player measurement (each player their own control; N is too small for
  group statistics)
- Thresholds locked from post-launch data only
- Pricing decided after the first real conversions

### Always-on
- Backfill `games.user_rating` — 77% of corpus hangs have no rating band
- Exclude the 1,145 pre-SEE events from every baseline
- Delete or revive `teaching_coach.py` (dead: imported by nothing)
- Verify `time_pressure` detection before claiming time-habit tracking

---

## PART 6 — What we cannot claim yet

Guarding this list *is* the moat. Everyone else inflates.

| Claim | Why not yet |
|---|---|
| "We improved your rating" | No transfer measurement has ever completed |
| "You've fixed X" for anything but piece safety | Only `simple_hang`/D_live is precision-verified |
| "You're taking more time now" | Time trend doesn't exist; detection health unverified |
| "You lost in the endgame because of Y" | 50% of endgame detections are generic |
| "Your fork weakness" | Motifs aren't wired into focus selection |
| Any date for a fix | Zero data on time-to-fix |

Two prior studies died at enrollment. The third attempt must be within-player,
must be small, and must actually run.

---

## PART 7 — What 10/10 means

Not feature count. Five tests:

1. **A stranger onboards and, within ten minutes, can say their own weakness in
   their own words** — and has already worked on it.
2. **The same instruction appears in review, in play, and in practice**, worded
   identically, because one spine feeds all three.
3. **A number moves, from their own games**, and the player believes it because
   it has been honest with them when nothing moved.
4. **The coach says "again"** — and is right, with evidence.
5. **Someone stops making the mistake**, and we can prove it without inflating.

Today: 1 is partial, 2 is missing, 3 is built but off, 4 is missing, 5 is
unproven. **All five are reachable without new science.**
