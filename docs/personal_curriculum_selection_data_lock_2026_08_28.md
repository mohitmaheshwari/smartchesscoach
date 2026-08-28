# Personal Curriculum — selection data lock

**Status:** LOCKED 2026-08-28. Selection thresholds and the three-measured-game
review cadence are now backed by versioned production aggregates.

**Raw snapshots:**
`backend/data/corpus_snapshots/personal_curriculum_selection_2026-08-28.json`
and
`backend/data/corpus_snapshots/personal_curriculum_review_opportunities_2026-08-28.json`
— stored so the bake-offs are reproducible offline, with no database access and
no credentials. Cite the snapshots, not a live query.

**Method:** production `chess_coach`, read-only, deterministic full scan of
`move_observations` at `schema_version >= 16`. **No `$sample`** — it is unseeded
and two runs would disagree. Pre-SEE rows (<16) excluded: their predecessor
over-fired by roughly a third.

---

## 1 · Evidence availability — how many users can carry a plan at all

46 users have current-schema evidence.

| Per user | p25 | median | p75 | max |
|---|---|---|---|---|
| Observations | 307 | **791** | 2,792 | 53,497 |
| Analysed games | 9 | **28** | 96 | 1,510 |

| Users with ≥ N analysed games | |
|---|---|
| ≥1 | 46 |
| ≥3 | 42 |
| ≥5 | 39 |
| ≥10 | **34** |
| ≥20 | 25 |
| ≥40 | 20 |

**Implication.** Evidence is not the constraint. Even at ≥10 games, 34 of 46
users qualify. A minimum-evidence gate of **5 analysed games** admits 39/46
(85%) and is the natural floor — below that, per-user recurrence is noise.

## 2 · Repair candidates — is there something to fix?

A "repair" needs a *recurring* named weakness, not a one-off.

| Users with a named topic recurring ≥ N times | |
|---|---|
| ≥2 | 40 / 46 |
| ≥3 | **38 / 46 (83%)** |
| ≥5 | 33 / 46 |
| ≥8 | 27 / 46 |

Topics ranked by users affected (≥3 occurrences):

| Topic | Users |
|---|---|
| `simple_hang` | **36** |
| `ignored_king_attack` | 33 |
| `missed_fork` | (top 3) |
| `weakened_shelter` | 16 |
| `tempo_wasted_by_repeat` | 15 |
| `passed_pawn_ignored` | 12 |
| `missed_discovered_attack` | 11 |
| `early_flank_pawn_move` | 5 |
| `passive_king_in_endgame` | 4 |
| `threat_ignored` | 1 |

**Implication.** Recurrence ≥3 is the right repair threshold: it admits 83% of
users while still meaning "this keeps happening". `simple_hang` reaching 36/46
independently confirms piece safety as the correct first focus. The long tail
(`threat_ignored` at 1 user) must never be selected — a per-topic floor of
**≥4 users affected** keeps selection to topics with a real population.

## 3 · Expand candidates — is there something new to teach?

| Distinct named topics per user | p25 | median | p75 | max |
|---|---|---|---|---|
| | 4 | **7** | 10 | 17 |

Out of 20 named topics in the taxonomy.

**Implication.** The median user has already *touched* 7 topics, so "expand"
cannot mean "a topic you have never hit" — that set is large and undifferentiated.
Expand should mean **a topic with evidence but below the repair threshold**
(1–2 occurrences): the thing starting to go wrong, before it becomes a habit.

## 4 · Review interval — the finding that should change the design ★

| Days between a user's games | p25 | median | p75 | p90 |
|---|---|---|---|---|
| All gaps | 1 | **1** | 2 | **21** |
| Per-user median gap | 1.0 | 1 | 2 | — |

Measured on 15 users with ≥2 dated games.

**A fixed calendar interval will not work.** The median gap is 1 day, but the
p90 is 21 days — the same population contains daily players and users who
disappear for three weeks. A 7-day review fires *seven games late* for one and
*never with new evidence* for the other.

**Locked: schedule an evidence review after 3 measured games, not by elapsed
days.** The follow-up stored-fact aggregate covers 24 users, 254 fully
D_live-instrumented games, and 1,323 eligible decisions. Three games is the
first candidate where 99.05% of rolling windows contain at least 6 comparable
decisions; the overall p25 is 12.5 and 81.99% contain at least 12. It retains
75% measured-user reach. Two games leaves 10.43% of windows below 6 decisions;
five games lowers reach to 54.17%.

The **21-day backstop is a coach check-in or resume prompt, not an evidence
verdict**. It prevents a lapsed student from being silently dropped without
pretending that time passing produced new chess evidence.

## 5 · What a plan can honestly name today

| | |
|---|---|
| Observations with a subtype (v16+) | 12,504 |
| Named (says what happened) | 3,619 |
| **Naming rate** | **28.9%** |

Slightly better than the 25.8% all-schema figure, because current-schema
detection is stronger. Still: **seven in ten detected mistakes cannot say what
went wrong.** Selection ranking must prefer named topics, and the curriculum
should never surface a generic bucket as a "focus" — there is no lesson at the
end of `small_slip`.

---

## Recommended locks

| Parameter | Value | Basis |
|---|---|---|
| Minimum evidence to build a plan | **5 analysed games** | 39/46 users (85%) qualify; below this recurrence is noise |
| Repair threshold | **≥3 occurrences of one named topic** | 38/46 users (83%) qualify |
| Topic eligibility floor | **≥4 users affected** | excludes a tail down to n=1 |
| Expand definition | **named topic with 1–2 occurrences** | median user already touched 7 of 20 |
| Review trigger | **3 fully D_live-instrumented games** | 99.05% of rolling windows have ≥6 decisions; p25 12.5 |
| Review calendar backstop | **21-day check-in, not a verdict** | p90 of observed gaps |
| Selection eligibility | **named topics only** | 71% of detections are generic |

## Decision outcome

**Locked from this snapshot:**

- **5 analysed games** is the floor for an evidence-personalized selection.
  It is not a floor for receiving any plan: lower-evidence students receive
  OBSERVE or universal fundamentals.
- **Repair = at least 3 occurrences of one named topic.** Two occurrences lost
  because it admits one-offs too easily; five and eight lost because they delay
  help despite only modest reductions in eligible users.
- **V1 evidence-led topics must affect at least 4 corpus users and have a real
  lesson destination.** This is a V1 support/validation floor, not a claim that
  rare chess problems are unimportant.
- **Emerging need = a named topic with 1–2 occurrences.** It is one EXPAND
  candidate source, not the whole definition of expansion. Prerequisite-led
  universal ideas may still be truly new to the student.
- **Reviews are scheduled by games played, with a 21-day calendar backstop.**
  Fixed 7-day scheduling lost because median play gap is 1 day while p90 is 21.
- **The game count is 3 measured games.** One game usually has too little
  comparable evidence; two leaves one in ten windows below six decisions;
  five delays the coach and excludes nearly half the measured users.
- **Evidence-led selection uses named topics only.** Generic detections may
  contribute aggregate severity but cannot name a lesson.

The review-window evidence is versioned in
`backend/data/corpus_snapshots/personal_curriculum_review_opportunities_2026-08-28.json`.
Historical schema-16 games without `piece_safety.d_live.v1` are classified as
**not measured**, never as zero-opportunity games.

## Limitations, stated plainly

- **Cadence rests on 15 users.** Directionally clear (daily vs three-weekly), but
  not a tight estimate. Re-measure after launch.
- **Stored D_live window evidence rests on 24 users and 254 games.** Only 19
  three-game windows sit in the 0–999 band, so the three-game choice is a V1
  operating lock to re-measure after broader instrumentation.
- Behavioural data from this pre-launch corpus is not a baseline for engagement.
  These are *structural* facts — how much evidence exists, how often people play
  — not product-performance claims.
- One user holds 53,497 observations and 1,510 games. Percentiles are used
  throughout rather than means for exactly that reason.
