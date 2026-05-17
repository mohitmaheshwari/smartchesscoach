---
name: Coaching Content Backlog
description: Original 14 items complete (2026-04-12). Two open items as of 2026-04-27 — per-pattern decay for time/positional/opening, and the announce-and-test teaching loop.
type: project
originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---
## Original 14 items (2026-04-12) — all complete

1. Threat awareness — detects actual threats, allows counterattacks. **Done.**
2. Calculation — detects 1-move tactics (undefended pieces). **Done.**
3. Center control — piece pressure + extended center. **Done.**
4. Rook usage — connection + open file detection. **Done.**
5. Generic commentary — 7 new plan rules, phase-aware fallbacks. **Done.**
6. Observation dedup — title-based suppression across moves. **Done.**
7. Outposts + overloaded pieces in position reader. **Done.**
8. Plan text — position-specific plans for all common positions. **Done.**
9. Coach move explanation — position-aware (captures, threats, dev). **Done.**
10. V5 overlap removed — single coaching system. **Done.**
11. Guardian + deviation fix — skip guardian when deviation handled. **Done.**
12. Text variety — names specific undeveloped pieces. **Done.**
13. Positive reinforcement — encouraging messages on good play. **Done.**
14. Post-game phase analysis — Opening/Middle/Endgame breakdown. **Done.**

## Open items (added 2026-04-27)

15. **Per-pattern decay for time_collapse / positional / opening_disaster.**
    `improvement_proof_engine.ROOT_PATTERNS` only has 4 root buckets
    (threat_awareness, calculation, coordination, endgame). Time discipline,
    positional play, and opening discipline have no honest root bucket — the
    UI now shows "no signal yet" for them rather than borrow an unrelated
    bucket's reduction_pct. To surface real decay for these:
    - **Time discipline**: count `move_time_stats.rushed_critical=True` games
      in last 10 vs prior 10. Data already exists per-game.
    - **Opening discipline**: use opening-phase cp_loss (already computed in
      `services/opening_fit._opening_phase_cp_by_family`) and trend it.
    - **Positional play**: needs a new signal — there's no clean per-game
      tag for this today.

16. **Closed-loop "did you listen" signal end-to-end.** Mirror snapshots
    fire on Lab open (`[MIRROR] window closed`). Verified one-leg flow:
    `student_weaknesses` populated from `get_established_patterns` at
    coach session start. The remaining gaps in
    [Teaching Coach Design](project_teaching_coach_design.md):
    announce-and-test loop on the move (look-carefully prompt + follow-up
    "did you spot it?") and "you missed it" voice when student doesn't
    exploit a created opportunity.
