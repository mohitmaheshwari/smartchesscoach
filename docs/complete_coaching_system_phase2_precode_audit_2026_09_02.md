# Complete Coaching System Phase 2 — Pre-Code Audit

**Status:** PASS  
**Feature:** One idempotent evidence ledger and puzzle-attempt v2, shadow only  
**Approved scope:** `docs/complete_coaching_system_scope.md`  
**Phase 2 lock:** `docs/complete_coaching_system_phase2_data_lock_2026_09_02.md`

## Six gates

| Gate | Result | Evidence |
|---|---|---|
| 1. Literal UI mockup exists | Pass | The parent scope contains literal Home, Review, Teaching, Play, and Progress experiences. Phase 2 changes no visible UI; frontend-only submission identity is transport metadata. |
| 2. Headline is chess idea, not SAN | Pass | No player-facing headline or copy changes in Phase 2. The approved experience remains concept-led and move-evidenced. |
| 3. Thresholds come from data | Pass | Phase 2 adds no behavior or mastery threshold. Phase 0 explicitly rejected unsupported solve counts, opportunity counts, duration, and human-model visibility. |
| 4. Success changes behavior | Pass with phase distinction | Product success remains later real-game application and retention. Phase 2's integrity/parity checks are implementation acceptance evidence, not a substitute product metric. |
| 5. Deferred work remains deferred | Pass | No detector promotion, visible mastery, legacy status conversion, human-model difficulty, paid promise, result date, broad migration, or new content is included. |
| 6. Mohit explicitly approved this phase | **Pass** | After Phase 1 completion identified “Phase 2 — one evidence ledger” as next, Mohit replied “go” on 2026-09-02. |

## Existing-system audit before implementation

- The current `verified_puzzle_attempt_service` is the server-owned grader/write chokepoint but uses `insert_one` with a fresh UUID, so retries duplicate attempts.
- Nine runtime callers already use that chokepoint; one unused `CoachingPuzzleService` method still contains a direct insert and must not become a second authority.
- Review reflection, guided PIC practice, and positive application misses already serialize `LessonResult v2`, but generic ledger mechanics are embedded in a PIC-specific adapter.
- Personalized lesson answers serialize the same contract directly into their existing session.
- The existing shadow reducer is hardcoded to one PIC identity and cannot safely project another requested skill.
- Exact schema-18 destination safety distinguishes `handled`, `miss`, `not_eligible`, and `unavailable`; the current learning adapter records only positive misses.
- Current generic puzzle UIs do not provide server-verifiable assistance/reveal history. Phase 2 must record that limitation rather than infer “unassisted.”

## Verdict

```text
PRE-CODE AUDIT: PASS
Phase 2 may implement only the additive, default-off, shadow evidence path
defined in the Phase 2 data lock. No player-facing claim is authorized.
```
