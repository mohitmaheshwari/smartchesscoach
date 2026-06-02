# PWC Migration to Central Caption Pipeline — Spec

**Status:** DRAFT v1 — **HIGH-RISK ARCHITECTURAL REWRITE. Awaiting Mohit explicit sign-off.**
**Version:** v1 (2026-06-02).
**Scope:** largest of the three PWC specs; multi-day, not half-day. Per [memory/project_pwc_runs_second_coaching_engine]: "Major rewrite, needs sign-off."

---

## 1. The problem

PWC's base per-move narrative runs on a **parallel coaching engine**: `move_critique` → `coaching_policy` → `coaching_voice`. This pipeline does NOT route through `services/caption_pipeline.build_move_teaching_decision` — the central layer that V5 review (Insights tab) uses.

Consequence:
- **None of today's failure-mode work** ("why played wrong" two-clause captions, contextual verbs, teaching principles) reaches PWC.
- **Severity classifications diverge ~50%** of the time between the two engines.
- Every voice rule fix, every detector improvement, every memory rule we encode has to be **applied twice** — once in the central layer (V5 review), once in the parallel engine (PWC).
- Memory rules ([feedback_one_source_of_truth]) explicitly forbid parallel coaching paths. PWC is a known violator we've been carrying.

A migration consolidates: one engine, one set of detectors, one set of voice rules, one place to fix bugs.

---

## 2. The shape — what the migration produces

PWC's per-move feedback after migration:

```
USER PLAYS MOVE
  → realtime_coaching_feedback orchestration runs
  → instead of calling move_critique/coaching_policy/coaching_voice,
    calls services.caption_pipeline.build_move_teaching_decision()
  → the central layer's R-rules fire (R12_blunder, R02_multi_target_attack,
    R03_aligned_pieces, R_FALLBACK_no_primary, etc.)
  → caption + caption_llm + caption_facts come back
  → PWC-specific surfaces (Socratic question, "Are you sure?" guardian,
    pre-move hint) wrap around that central decision
```

The PWC-specific surfaces ARE preserved: Socratic questions, guardian, teaching mode dispatches. What changes is the **base narrative** of "what just happened on the board" — that becomes the central caption.

---

## 3. What gets retired

After migration, these modules no longer drive PWC's per-move narrative:

- `services/move_critique.py`
- `services/coaching_policy.py`
- `services/coaching_voice.py`
- Per-skill detector duplicates in PWC's path (the central layer's caption_facts.py already covers them)

These modules might be retired entirely, OR kept as a fallback path behind a feature flag for safety during rollout. Decision: keep behind flag until migration is verified clean across a corpus of PWC sessions.

---

## 4. What stays

- **Realtime coaching feedback orchestration** ([backend/services/realtime_coaching_feedback.py](backend/services/realtime_coaching_feedback.py)) stays as the per-move orchestrator. The change is which engine it calls inside.
- **PWC-specific surfaces** — Socratic question generation, pre-move guardian, teaching modes (traps + endgames), escape squares quiz — all stay. These don't conflict with the central layer; they layer on top of it.
- **Rating-aware thresholds** — the rating-band severity classifier (`<1000 / 1000-1399 / 1400-1799 / 1800+`) becomes a wrapper around the central caption's severity, not a parallel computation.

---

## 5. The migration plan

### Phase 1 — diff baseline (1 day)

1. Run `snapshot_surface1.py` against current PWC narrative engine on 20 analyzed games. Capture the "before" set.
2. Render the central caption pipeline against the SAME 20 games' positions. Capture the "shadow" set.
3. Diff: for every user move, compare PWC's current narrative vs. what central would say. Tag each as `agree-clean / agree-with-different-wording / disagree-severity / disagree-content / one-empty-other-not`.
4. **Sign-off gate:** if the agree rate is < 60%, the migration is riskier than expected and we should pause to understand why. If > 60%, proceed to phase 2.

### Phase 2 — feature-flagged dual-run (2-3 days)

1. Add `PWC_USE_CENTRAL_CAPTION_PIPELINE` env var (default false).
2. When flag is on: `realtime_coaching_feedback` calls `build_move_teaching_decision()` instead of the legacy engine.
3. When flag is off: today's behaviour (the legacy engine).
4. Internal testing: Mohit + Parth + I (via probe) run PWC sessions with the flag on. Capture and triage divergences from expectations.
5. Iterate on central-pipeline gaps surfaced by PWC use cases (e.g., curriculum-aware nudges, teaching-mode integration) — those gaps go into existing caption_pipeline work.

### Phase 3 — production rollout (1 day)

1. Flip the flag on for 10% of users for one week. Monitor for support complaints, severity divergence, missing nudges.
2. If clean: flip to 100%.
3. Legacy engine modules stay behind the flag for one more week as rollback.
4. After two weeks clean at 100%: delete the legacy modules in a follow-up cleanup PR.

### Phase 4 — cleanup

1. Delete `move_critique.py`, `coaching_policy.py`, `coaching_voice.py`.
2. Update [CLAUDE.md](CLAUDE.md) to remove references.
3. Update [memory/project_pwc_runs_second_coaching_engine.md] to "RESOLVED" with the migration commit hash.

---

## 6. Risk + rollback

**Highest-risk migration in the codebase.** PWC is the premium feature. ~Every paying user's session hits this code path.

**Failure modes:**
- **Severity drift:** central layer says "Inaccuracy", legacy said "Mistake". A 1200 reading "Inaccuracy" on a -300cp move feels unsure. Mitigation: phase 1 diff baseline catches this before flipping.
- **Voice drift:** central layer uses the new failure-mode captions ("walks into Nb7 forking your queen") but PWC users are used to the existing voice. Acceptable — the new voice is better, but it's still a change.
- **Coverage hole:** R-rules in the central layer might not cover edge cases that the legacy engine had heuristics for. Mitigation: phase 1 baseline surfaces them; address before phase 2.
- **Teaching-mode breakage:** PWC's trap-teaching and endgame-teaching wrap around the per-move narrative. If they assumed the legacy engine's output shape, they'll break. Mitigation: explicit test of trap + endgame teaching flows under the flag.
- **Performance:** central layer is slightly heavier than the legacy engine (more fact extraction, R-rule evaluation). Should be sub-100ms per move; if it adds latency that breaks the "feels live" UX, abort.

**Rollback:** the feature flag IS the rollback. Flipping `PWC_USE_CENTRAL_CAPTION_PIPELINE` to false reverts to today's behaviour instantly. No data migration, no irreversible schema changes.

---

## 7. Open questions (Mohit must answer before phase 1)

1. **Severity divergence tolerance.** If phase 1 shows central says "Inaccuracy" where legacy said "Mistake" 30% of the time, is that acceptable? (The 1200 user perceives the severity word as the dominant signal.)
2. **Teaching-mode integration.** PWC's trap teaching and endgame teaching layer narrative on top of the per-move base. The central pipeline doesn't currently know about teaching modes. Do we:
   - (a) Make teaching mode bypass the central pipeline (today's behaviour),
   - (b) Pass teaching context as facts into the central pipeline so its R-rules can adapt, or
   - (c) Stop using the central pipeline during teaching mode and route to a third path?

   My recommendation: (a). Teaching mode is a different surface; not all surfaces share the central layer.
3. **Cleanup timing.** When the legacy modules retire (phase 4), the imports in unrelated files might break. Acceptable cleanup time: 1-2 days of post-migration triage. Mohit's tolerance?
4. **Diff sign-off.** Who reviews the phase 1 diff baseline? Mohit alone, or also Parth (for chess accuracy)?

---

## 8. Why this is worth the cost

- **One source of truth = one place to fix bugs.** Every R12 improvement (today's failure-mode work, tomorrow's defender-removal work) reaches both Lab and PWC. No duplicate work.
- **Voice consistency.** The "walks into Nd4" caption a user reads in Lab review = the same caption in PWC live coaching. Builds trust.
- **Maintainability.** New contributors (or future-me) only need to learn one caption engine, not two. The architectural memory rule ([feedback_one_source_of_truth]) stops being violated.
- **Better captions in PWC.** PWC's legacy engine is older than the central layer. Today's R12 is materially better than `coaching_voice` for "why played wrong" diagnoses. PWC users get the upgrade automatically.

The cost is real (multi-day, high-risk). The benefit is structural and compounds — every future caption improvement ships once and reaches both surfaces.

---

## 9. Recommendation

**Do specs #1 and #2 first.** Both are additive, low-risk, ship in a half-day each, deliver immediate premium-tier value (skill mastery awareness + curriculum guidance). They also give us another week of PWC usage to study before committing to the rewrite.

**Then start spec #3 with phase 1 (diff baseline only).** That's a 1-day investment that tells us whether the rewrite is even safe to attempt. If the diff baseline shows < 60% agreement, we file the rewrite, don't start it.

**Only commit to phases 2-4 once the diff baseline says it's tractable AND we have explicit sign-off on the open questions in §7.**
