# Coach Ladder — Scope Document

> Status: DRAFT — awaiting Mohit signoff. No code until signed off.
> Scope covers **Phase 1 only**. Phases 2 (concierge paid-session test) and 3 (marketplace + payout)
> are named for context but are explicitly out of scope for this V1.

---

## 0. Existing surfaces audit (EXTEND / PARALLEL / REPLACE)

The loop reuses far more than it builds. Decision per piece:

| Piece of the loop | Decision | Evidence |
|---|---|---|
| Points / XP / levels / leaderboard | **EXTEND** | `gamification_service.py` — 20 levels, ~30 achievements, live leaderboard; scores *own activity* today |
| "Your games are teaching people" | **EXTEND** | `shared_by` + `get_user_contributions()` exist (`community_learning_service.py:63,359`), never shown to solvers |
| Solve-another's-puzzle mechanic | **EXTEND** | Works; solves flow back to puzzle (`puzzle_extraction_service.py:342`). Missing: credit + notify author |
| Improvement / certification data | **EXTEND** | Decay states, mastery, `improvement_rate`, `concepts_mastered` (`pattern_decay_service.py`, `coach_memory.py:172`) |
| Notification infra | **EXTEND** | Generic infra exists (`notification_service.py`); add one type + producer |
| Human tip/caption on a puzzle | **BUILD NEW** | Only a machine `description` (`puzzle_extraction_service.py:215`); no user can author teaching text |
| Contribution scoring *rules* | **BUILD NEW** (as XP events in the existing engine) | Nothing rewards authoring/teaching today |
| Coach-level role + gate | **BUILD NEW** | Only `user`/`super_admin`/`is_reviewer` exist |
| Mentorship booking + payout | **BUILD NEW / DEFERRED** | Payments inbound-only (`billing.py`); no payout path — Phase 3 |

**Single-source-of-truth guardrails (from the audit):**
- There are already TWO badge systems (`gamification` achievements vs `badge_service` Chess-DNA stars) and TWO
  writers into `puzzle_attempts`. The Coach Ladder adds **no third scoring system** — all points extend
  `gamification_service` XP, tagged as *contribution* XP so certification can read the contribution subtotal.
- Human tips route through the **same engine-verification discipline as AI captions** — no unverified teaching text ships.

**Net decision: EXTEND-dominant.** The only genuinely new surfaces are (a) user-authored tips + their verification,
(b) contribution XP events, (c) a visible coach-level ladder + certification computation.

---

## 1. What it is

The Coach Ladder turns solving into teaching, and teaching into a path you can climb. When a player solves a
community puzzle — a position from another player's real game — cleanly, we invite them to **share their reasoning
for why that move was best**. They submit it, and **our service reviews the reasoning against the engine, rates it,
and surfaces the top-rated reasons** on that puzzle for the next player to learn from. This is the "what you thought
vs. what was actually true" idea: many players explain the same position, the sound explanations rise, the unsound
ones are caught (a player can find the right move for the wrong reason — the review distinguishes them). Reason-
authors are credited by username, so good teaching earns real recognition. Good contributions earn points on the
ladder the user already has. As a player both **improves** (proven by our own data — breaking plateaus, mastering
concepts) **and helps others** (top-rated reasons, puzzles that teach), they climb toward "Coach level" — a visible,
aspirational status. In a later phase, Coach level will unlock the ability to earn money mentoring; in Phase 1 it is
the destination that makes the climbing worth it, and the contributor's games are surfaced back to them warmly
("your games are teaching people"), never as "people aced your blunder."

---

## 2. What the user sees (mockups — the product contract)

### 2a. The "share your reasoning" moment (after a clean solve)
Only offered when the solver played the engine-best move (they earned the right to explain this one).

```
┌─────────────────────────────────────────────┐
│  ✓ You found it — first try.                 │
│                                              │
│  Why did you think that was the best move?   │
│  One or two lines. The best reasons get      │
│  shown to the next player.                   │
│  ┌─────────────────────────────────────────┐ │
│  │ His knight on the rim was undefended,   │ │
│  │ so I looked for a way to win it.        │ │
│  └─────────────────────────────────────────┘ │
│              [ Skip ]   [ Submit reason → ]   │
└─────────────────────────────────────────────┘
```
On submit → the service reviews the reasoning against the engine and **rates** it → if sound, it enters the
puzzle's ranked reasons + contribution XP. If the move was right but the *reason* was off, the player is thanked
and gently shown the real reason (a teaching moment), and the reason is held from the public list — never publicly
rejected in a shaming way.

### 2b. A puzzle that already has top-rated reasons (shown while solving)
```
   [ board ]         Coach's read: the knight on the rim
                     can be chased and forked.  (AI)

                     Top player reasons
                     1. "Win the undefended knight."
                        — @arjun_1180   ▲ 12
                     2. "His piece had no defender."
                        — @meera_k      ▲ 7
```

### 2c. "Your games are teaching people" (weekly, on /home or /progress)
Batched weekly so it never looks empty at low density. Pride-framed, contributor anonymized to solvers.
```
┌─────────────────────────────────────────────┐
│  Your games are teaching people 📈           │
│                                              │
│  This week, 6 players trained on positions   │
│  from your games. 2 solved them first try.   │
│  You've helped 14 players so far.            │
│                              +40 ladder pts  │
└─────────────────────────────────────────────┘
```

### 2d. The Coach Ladder (visible in Phase 1; earning unlocks later)
```
┌─────────────────────────────────────────────┐
│  The Coach Ladder                            │
│  Solver ──▶ Helper ──▶ ★ Coach               │
│  ●●●●●●●●●●●●●●●○○○○○○  You're a Helper       │
│                                              │
│  To reach Coach level:                       │
│   ✓ Broke a plateau (fewer blunders, proven) │
│   ◔ 60% to the teaching-points needed        │
│                                              │
│  Coaches will be able to earn from mentoring │
│  sessions — coming soon.                     │
└─────────────────────────────────────────────┘
```

### 2e. The social notification (in-app + weekly digest email)
```
🔔  A player solved a puzzle from your Tuesday game — first try.
    Your games make good practice material.
```

---

## 3. In scope (V1 = Phase 1)

- **Solver reasoning capture** on community puzzles: prompt shown only to solvers who played the engine-best move,
  asking *why* that move was best.
- **Review + rating of every reason** before it goes public (best-move-gate + engine/AI check that the stated
  reason matches the real reason the move is best — not just that the move was right). Same verification discipline
  as AI captions. Reasons are **ranked**; the top-rated ones surface on the puzzle.
- **"Got the move, wrong reason" handling:** when the move is right but the reasoning is unsound, the player is
  gently shown the real reason (a teaching moment) and the reason is held from the public list.
- **Ranked-reasons display** while solving: the top verified reasons under the AI caption, each credited by
  **username**, with a "found this helpful" upvote that feeds the ranking.
- **Contribution XP events** added to the existing `gamification_service` engine, tagged as contribution XP:
  submitting a verified reason, a reason getting upvoted / ranked top, someone solving your shared puzzle (all
  capped to reward quality over volume — see Open Questions for the numbers).
- **"Your games are teaching people"** card, weekly-batched, pride-framed. Reason-authors are named by username;
  the contributor (source of the puzzle) is shown as "a fellow player" by default, name attached only if they
  opt in. Extends existing `shared_by` + `get_user_contributions()`.
- **Coach Ladder surface** (Solver → Helper → Coach) — visible and progressing in Phase 1, unlocking nothing
  monetary yet. Progress = contribution-XP subtotal **AND** verified improvement (plateau broken / concepts
  mastered), read from existing decay + mastery + coach_memory data.
- **One new notification type** ("someone learned from your game") + producer, delivered in-app and in the
  existing weekly re-engagement digest email.

## 4. Explicitly out of scope (V1)

- **All payments-out / payout / booking / real mentoring sessions** — Phase 3. Billing stays inbound-only.
- **The concierge paid-session willingness-to-pay test** — Phase 2 (hand-booked, no code).
- **Coach level unlocking any earning ability** — Phase 1 shows the ladder; money is deferred.
- **A contribution leaderboard / ranking users against each other** — deferred; competitive ranking risks
  demoralizing 400–1200 players. The existing personal-XP leaderboard is untouched.
- **High-frequency real-time "someone solved yours" pings** — at ~50 users the event is too sparse; Phase 1
  uses the weekly digest instead. Real-time is density-gated to a later flip.
- **A second/third scoring or badge system** — forbidden by the SSoT guardrail; extend `gamification_service` only.
- **Editing/curating existing AI captions by users** — authoring is additive (tips), not overwriting AI text.
- **Tip threading / replies / discussion** — one tip + upvote only in V1.

## 5. Success criteria (behavior-changing, not vanity)

- **Tip-capture rate:** ≥ 25% of eligible (best-move) solvers who see the prompt submit a tip, within 3 weeks.
- **Tip quality:** ≥ 80% of submitted tips pass engine verification (proves the gate + prompt produce sound advice,
  not noise).
- **Corpus growth:** ≥ [N] verified peer tips accumulated in 4 weeks (N set once we see submission volume).
- **Retention lift:** contributors (users who authored ≥1 verified tip OR earned contribution XP) show higher
  D7/D30 return than matched non-contributors. This is the core reason the feature exists.
- **Ladder pull:** ≥ [X]% of users who view the Coach Ladder return to a contribution action within 7 days.

(Bracketed numbers are locked in Open Questions / pre-code, not guessed here.)

## 6. Open questions

- **Question (PARTIAL LOCK, 2026-06-29 via /lock-via-data):** Contribution-XP amounts + caps.
  **Finding:** only **8 of 97 users** have ever correctly solved a puzzle; XP system dormant (17 users, flat at
  ~220). No distribution exists for the contribution behavior → cannot data-lock without gut-locking.
  **Resolution:** PROVISIONAL, anchored to existing locked `XP_REWARDS` (`puzzle_solved=15`, `game_analyzed=25`),
  instrumented for re-lock: verified reason = 20 (cap ~3/day), reason ranked top = +10 (once/reason), your puzzle
  solved by another = +2 (cap ~10/day). **Re-lock trigger:** ≥30 active contributors OR ≥200 verified reasons.
- **Question (PARTIAL LOCK, 2026-06-29):** Coach-level thresholds.
  **Locked component:** "verified improvement" gate = **mastered_concepts ≥ 27** (p90 of the 52-user populated
  distribution: med 13 / p75 23 / p90 27 / max 43) — chosen for coach scarcity, ~top 10%. Corroborating signals
  available: decay `state active→fading` + clean-streak, `coach_memory.performance` rating gain.
  **Deferred:** the *contribution-points* half of the gate — no distribution yet; setting it now would be
  threshold-before-distribution. Finalize when the re-lock trigger above is hit.
- **PROJECT DECISION (2026-06-29):** Data shows the contribution loop has an 8-user engagement base. Coach Ladder
  is **PARKED** (signed off, partially locked) pending a larger active-solver base. The **solo daily hook** is
  sequenced first as the prerequisite that grows that base. Resume Coach Ladder Phase 1 when the base supports it.
- **Question (RESOLVED):** Are usernames shown? → **Yes for reason-authors** (credit makes it genuine — Mohit,
  2026-06-29). The **contributor** (puzzle source) stays "a fellow player" by default, name attached only on
  opt-in, to protect the insecure user whose blunder became the puzzle. Confirm the opt-in default is acceptable.
- **Question:** Exact reason-review pipeline — how does the service decide a stated reason "matches the real reason
  the move is best" (best-move-gate + LLM/engine claim-check against the engine line), and how are reasons ranked
  (verification score + upvotes)?
  **Why unresolved:** needs a small design pass reusing the caption-verification approach. **Unblocking step:**
  design note + probe on a sample of real submitted reasons.
- **Question:** At what active-user count do we flip on real-time social notifications instead of weekly digest?
  **Why unresolved:** density-dependent. **Unblocking step:** pick a threshold when DAU data is available.

## 7. Pre-code requirements (hard gates)

- Mohit has explicitly signed off on this full scope document.
- Contribution-XP amounts/caps locked via `/lock-via-data` (histogram first).
- Coach-level thresholds (points + verified-improvement definition) locked via `/lock-via-data`.
- Tip-verification pipeline chosen and documented.
- Contributor anonymity decision made (Mohit).
- Card mockups (§2) approved as the product contract.
- Confirmed: all points extend `gamification_service` XP — no new scoring system (SSoT).
- `/audit-pre-code` run before the first file.
