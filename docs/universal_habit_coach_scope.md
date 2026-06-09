# Universal Habit Coach — Final Scope, Dev Plan, L4 Experiment

> Status: **DRAFT — awaiting Mohit signoff.** Supersedes personalized-weakness coaching (retired: mistake-frequency
> personalization failed — players uniform on what AND when they err). Product = install the *same* core habits well,
> for everyone. First and only V1 goal: **prove the coaching loop changes behavior.** Not differentiation.

---

## A. FINAL SCOPE

### What we're building
A coaching loop that installs **ONE universal core habit** — *"Before you move: is anything hanging? what is the opponent
threatening?"* — the same way for every player, reinforced **at the moment of decision in Play-with-Coach**, and measures
whether the **targeted mistake (hung pieces / ignored threats) actually drops over the player's next games.**

We reuse the existing `focus_engine` loop (set focus → in-game reminder → track clean games → graduate). The only change vs.
the current system: the focus is a **fixed universal habit**, not a "unique weakness" (which we proved doesn't exist at
600–1500).

**Threat Scan is a CANDIDATE habit, not established truth.** It is our *best current hypothesis* for the highest-leverage
universal habit (the data shows hanging-pieces/missed-threats is ~everyone's most frequent mistake) — but "is threat-scan
THE highest-leverage habit?" is unproven and explicitly NOT what V1 tests. **V1 proves the LOOP MECHANISM** — does installing
*this* habit reduce *its* targeted mistake. If yes, the mechanism works and threat-scan is a validated first habit; whether a
*different* habit would move the needle more is a later question, not this one.

### Explicitly OUT of scope (V1)
- Personalized weakness diagnosis / unique player profiles / Theory of You / identity / plateau.
- Player-representation research (paused). Game-level/collapse families, `advantage_collapse`.
- A multi-habit menu / "light personalization" — **deferred to V1.1, only after L4 proves the single-habit loop works.**
- New UI surfaces or coaching concepts. Reuse the focus card + the PWC pre-move reminder.
- Rating as a metric (too noisy at this N).

### Success metric (pre-registered, before data)
In a **randomized holdout**, players who **receive the in-game habit reminder** show a **meaningfully larger reduction in
the targeted mistake** (hung-pieces + ignored-threat events per game) over their next N games than players who don't.
Exact threshold locked via `/lock-via-data` after seeing the baseline targeted-mistake-rate distribution.

### Failure metric
Treatment ≈ control (no extra reduction) → the loop does **not** change behavior → kill/redesign the universal-coach thesis.
A before/after gain *without* beating control = regression to the mean, **not** success.

### Acceptance criteria
1. The measurement loop **closes** — a focused player who finishes a PWC game gets a `game_results` entry (fixes the
   current 50/51 = 0 bug). Without this there is no L4.
2. The in-game reminder fires at decision time for the universal habit.
3. The L4 experiment runs with a **holdout control** and a **pre-registered** metric, and returns a yes/no on behavior change.

---

## B. DEVELOPMENT PLAN

Reuse: `focus_engine.py` (loop), `coach_play.py` (PWC reminder path, `get_enforcement_message`), `analysis_interpreter.py`
(`cognitive_gap` mistake detection), `game_analyses` (move_evaluations).

| # | Task | Files | Effort |
|---|------|-------|--------|
| **2** | **Fix the measurement loop (BLOCKER).** Root-cause why `update_focus_after_game` leaves `games_with_focus=0` for 50/51 users; make it record `game_results` on every PWC game end. | `focus_engine.py`, `coach_play.py:~1143` | 1–2 d |
| 1 | **Targeted-mistake detector.** Define the universal habit's mistake = `cognitive_gap ∈ {piece_safety, threat/ignored_threat}` with the audit's **piece_safety pawn-fix** (hanging *piece* or engine-punished, not incidental pawn). | `analysis_interpreter.py`, new `core_habit.py` | 1 d |
| 3 | **Universal habit assignment.** Replace the saturated detector: set every focused user's focus to the fixed universal habit (no "unique weakness" computation). | `focus_engine.set_user_focus` / new `universal_habit_service.py` | 0.5 d |
| 4 | **In-game reminder.** PWC pre-move prompt for the habit ("Before you move — anything hanging? any threats?"); reuse `get_enforcement_message`. | `coach_play.py` (reminder path), focus-rule copy | 0.5 d |
| 5 | **L4 harness + holdout.** Random treatment/control split; per-player targeted-mistake-rate over next N games; pre-registered metric. | new `l4_behavior_change.py` | 2 d |

**Build order:** 2 → 1 → 3 → 4 → 5. **Dependencies:** Task 2 blocks everything (no measurement → no L4). 3 needs 1. 4 needs 3.
5 needs 2+3+4 live to generate data. **Total: ~1 week to a running loop + experiment.**

**Hard gate:** Tasks 1–4 are infrastructure (safe to ship — "coach reminds you to scan," not a personalization claim).
Task 5's *result* is what decides whether the loop is real. Run `pwc_coaching_lint` after any coaching-surface change.

---

## C. L4 BEHAVIOR-CHANGE EXPERIMENT

**Question:** *Does the coaching loop reduce the targeted mistake over the next N games?*

### LOCKED METRIC (one equation — frozen before data)

```
            1                                  1
  DiD  =  ─────  Σ  (Rᵇᵃˢᵉ_p − Rᵖᵒˢᵗ_p)  −  ─────  Σ  (Rᵇᵃˢᵉ_p − Rᵖᵒˢᵗ_p)
           |T|  p∈T                           |C|  p∈C

                     Σ_{g∈W(p)}  targeted_mistakes(p, g)
  where   R^W_p  =  ──────────────────────────────────────
                     Σ_{g∈W(p)}  user_moves(p, g)
```

Terms (definitions, not prose):
- `targeted_mistakes(p,g)` = count of player p's moves in game g with `cognitive_gap ∈ {piece_safety(piece-or-engine-punished-pawn), ignored_threat}` and `cp_loss ≥ 150`
- `Rᵇᵃˢᵉ_p` = R over W = p's games **before** focus assignment;  `Rᵖᵒˢᵗ_p` = R over W = p's **next N** games after
- `T` = treatment (reminder on);  `C` = control (focus tracked, reminder off);  `N ≈ 10–15`
- **Success ⟺ `DiD ≥ θ`**, θ locked via `/lock-via-data` from the `Rᵇᵃˢᵉ` distribution **before** treatment/control are unblinded.

**Design — smallest experiment that actually answers it (forward, randomized — the only design that proves causation;
before/after alone is fooled by regression-to-mean, the night's repeated lesson):**
- **Holdout:** of players assigned the universal habit, randomly **50% TREATMENT** (get the in-game reminder) / **50%
  CONTROL** (focus tracked, *no* active reminder). Both measured identically.
- **Metric:** engine-detectable **targeted-mistake rate per game** (hung-pieces + ignored-threat events). NOT rating.
- **Window:** each player's **next N≈10–15 games** after assignment.
- **Comparison:** does TREATMENT's targeted-mistake rate drop **more** than CONTROL's (difference-in-differences)?
- **Pre-registered success** (set before data, via `/lock-via-data` on the baseline distribution): treatment's reduction
  exceeds control's by a meaningful, stable margin.
- **Power caveat (stated up front):** ~50–80 users → ~25–40 per arm. Adequate only for a *large* effect; report achievable
  power, and if underpowered, extend the window or pool more users rather than over-reading a noisy result.

**What it proves / doesn't:** proves (or kills) whether *this* habit's loop changes behavior. If yes → generalize to the
3-habit menu (V1.1) and *then* the paused representation question becomes worth revisiting (response-to-coaching data now
exists). If no → universal coaching as built doesn't work; reconsider before building more.
