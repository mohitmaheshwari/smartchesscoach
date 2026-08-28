# Personal Curriculum Phase 4 — Current-Surface Baseline

**Status:** STRUCTURAL REACH LOCKED; ENGAGEMENT BASELINE INTENTIONALLY ABSENT —
2026-08-28.

**Run-in implementation update:** The privacy-allowlisted legacy emitters were
implemented on 2026-08-28. This does not retroactively fill the baseline and
does not change this document's PARTIAL status; deployment plus an observed
production interval is still required.

## Decision

Phase 4 mockup validation does not require PostHog history. The current product
did not instrument Learn/Lab, opening, endgame, or Progress impressions and
lesson transitions consistently, so no honest current-entry-point click-through
or lesson-funnel baseline can be reconstructed—and none will be manufactured.

The instrumentation-only run-in is deployed. For recruitment, use the
server-side structural reach in
`backend/data/corpus_snapshots/funnel_and_recruitment_2026-08-28.json`.
Player-facing implementation remains blocked on real representative sessions.
After implementation, a clean treatment interval—not historical PostHog
behavior—must supply numeric rollout and success thresholds before expansion.

## Sources

- Production MongoDB aggregate query run read-only inside the production backend container.
- Static source audit of the custom PostHog calls in `frontend/src/lib/analytics.js` and the current Home, Learn/Lab, prescribed-training, Play-with-Coach, openings, endgame, and Progress pages.
- Versioned aggregate snapshot: `backend/data/corpus_snapshots/personal_curriculum_surface_baseline_2026-08-28.json`.

No credentials, raw user IDs, or raw game IDs are present in the snapshot.

## What can be measured now

The table contains **persisted activity proxies**, not page impressions or conversion rates.

| Persisted activity | Lifetime records | Lifetime users | Last 7 days | Last 30 days |
|---|---:|---:|---:|---:|
| Coach sessions | 468 | 73 | 1 record / 1 user | 18 / 8 |
| Puzzle attempts | 400 | 18 | 0 / 0 | 6 / 1 |
| Training solve attempts | 118 | 13 | 0 / 0 | 0 / 0 |
| Opening practice sessions | 25 | 2 | 0 / 0 | 0 / 0 |
| Opening progress updates | 6,433 | 57 | 216 / 22 | 424 / 26 |
| Opening mastery updates | 706 | 66 | 0 / 0 | 6 / 5 |
| Diagnostic sessions | 28 | 24 | 3 / 3 | 5 / 5 |
| Coaching prescription history | 5 | 2 | 0 / 0 | 4 / 1 |

The query timestamp was `2026-08-28T14:39:21.200289+00:00`; the 7-day window begins `2026-08-21T14:39:21.200289+00:00` and the 30-day window begins `2026-07-29T14:39:21.200289+00:00`.

### Timestamp caveat

`user_opening_progress.last_practiced_at` contains 184 legacy `YYYY.MM.DD` strings. All are older than the two measurement windows and therefore do not change the 7-day or 30-day counts. The snapshot records the mixed timestamp types explicitly.

## Instrumentation coverage found in source

Home already emits custom events for page viewing, mirror reading, conversation scrolling, CTA clicks, navigation tiles, and the Personal Improvement Cycle. Prescribed Training emits `funnel_training_solve`; Play with Coach emits `funnel_pwc_started`.

No equivalent custom events were found on the current:

- Learn/Lab page;
- opening overview;
- opening lesson;
- endgame lesson; or
- Progress page.

The public PostHog initialization exists, but no private history-export credential or event-history connector was available during this audit. MongoDB does not contain these frontend events. Therefore Home's historical custom-event counts also cannot be cited from the production database snapshot.

## What cannot be recovered retroactively

- current Learn/Lab impressions;
- opening and endgame catalogue impressions;
- lesson starts attributable to those catalogues;
- explanation-to-guided-to-independent lesson progression;
- endgame lesson completion;
- Progress impressions;
- cross-surface recommendation click-through rate; and
- the share of lesson starters who reach an independent attempt.

“No event exists” must not be interpreted as “zero users did it.”

## Instrumentation-only run-in contract

All Personal Curriculum funnel events must be registered in the existing analytics source, `frontend/src/lib/analytics.js`; pages must not create a second registry or duplicate raw event strings.

Minimum semantic events:

| Event | Required meaning |
|---|---|
| `curriculum_decision_shown` | A recommendation was visibly rendered, with surface and stable decision ID. |
| `curriculum_primary_clicked` | The visible primary recommendation was chosen. |
| `curriculum_review_clicked` | The visible review item was chosen. |
| `learn_viewed` | The current Learn/Lab surface became viewable. |
| `progress_viewed` | The current Progress surface became viewable. |
| `explore_opened` | A browse category or browse lesson was opened. |
| `lesson_started` | A lesson interaction began; a catalogue view is insufficient. |
| `explanation_completed` | The teaching explanation was completed. |
| `guided_attempt` | A guided board attempt was submitted, including support level and result. |
| `independent_attempt` | An unassisted attempt was submitted, including result. |
| `review_attempt` | A scheduled review attempt was submitted, including result and support. |
| `back_to_plan` | A lesson returned the student to the coach-owned plan. |

Every event must carry only stable, non-sensitive dimensions needed to segment the funnel: surface, lesson/content type, canonical content ID, rating band, recommendation versus Explore origin, and experiment/flag state. Do not send FENs, PGNs, free-form coaching text, email addresses, usernames, or raw database IDs.

The run-in must reuse the current surface labels in its dimensions so the current experience and Phase 4 variant can be compared without redefining the denominator.

## Threshold lock still required

The signed scope requires final numeric success thresholds before user-facing code. This snapshot does not justify a number for:

- recommendation-start uplift;
- minimum share reaching independent attempt;
- reduction in help at review;
- delayed recall improvement;
- application improvement; or
- A/B rollout, rollback, and minimum-sample gates.

Those values must be chosen from clean treatment distributions, with
denominators, observation window, rating-band cuts, and sparse-cohort behavior
recorded. They are rollout gates, not invented mockup-validation bars. The
selection and review thresholds already locked for Phase 3 remain valid.

## Gate result

Structural reach is satisfied by the reproducible server-side snapshot. The
behavior funnel remains deliberately unknown for pre-launch engagement and is
not a blocker for mockup recruitment. Phase 4 product code may begin only after
the representative-player sessions pass; the flag may expand only after clean
treatment evidence locks the numeric rollout choices.
