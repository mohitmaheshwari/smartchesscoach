# Play with Coach — Unified Experience Pre-Code Audit

Date: 2026-09-13
Scope: `docs/play_with_coach_unified_experience_scope.md`
Data lock: `docs/play_with_coach_unified_experience_data_lock.md`

## Single-source-of-truth audit

| Concept | Current competing sources or owners | Canonical owner for Unified V1 | Retain / adapt / retire |
|---|---|---|---|
| Player-facing session mode | React `gameMode`, `evidenceMode`, setup's three choices, `coach_sessions.game_mode`, `coach_sessions.evidence_mode` | Stored `coach_sessions.game_mode` with only `coach` or `play` | Retain `game_mode`; make evidence mode internal; retire the third player-facing choice |
| Learning evidence stage | Setup selection plus `analysis_completion_evidence` | `effective_pwc_evidence_mode()` and `pwc_game_context()` | Retain and derive; never ask the player to choose checkpoint terminology |
| Active focus | `focus_engine`, `player_behavior_tracker.get_focus_concept`, session goal/focus snapshots, `user_active_focus` | `focus_bridge.build_coaching_context()` reading `user_active_focus` | Retain canonical bridge; session fields become projections only; retire rival reads from the unified path |
| Supporting focus | Unqualified `runners_up`, root-problem and weakness arrays | `coaching_context.supporting_focuses` after detector-quality authorization | Retain fail-closed authorization; no fallback |
| Pending move evaluation | Opening deviation call, `/evaluate`, `/evaluate-pending`, Guardian | Existing `/evaluate-pending` contract | Adapt once; remove the other evaluator calls from the unified path |
| Move commitment | `/move`, `/move/confirm`, clock-tap release, several frontend branches | One `useCoachFlow` state transition; `/move` for ordinary commit and `/move/confirm` only for an explicit verified-warning override | Adapt and share atomic commit behavior; retire hidden clock commit |
| Move-flow state | `CoachPlay` state, `useGuardian`, `useCoachFlow`, teaching hook, local opening state | Existing `useCoachFlow` | Adapt as the sole owner of pending move and visible intervention; other systems submit evidence only |
| Chess truth and narration | Fast templates, Guardian text, message-decision templates, interactive feedback, V5, opening/geometry cards | `caption_pipeline.build_move_teaching_decision` for position claims, with Stockfish/verified facts | Retain central pipeline; the message selector may arbitrate candidates but may not author rival chess claims |
| Message arbitration | `message_decision_engine`, anti-silence rules, focus enforcement, sidebar conditional order, modal order | Existing `message_decision_engine` seam, adapted to select at most one authorized candidate | Retain selector role; retire forced gap fillers, questions, and parallel text ownership |
| Visible coaching turn | Guardian card, active strip, geometry card, V5 block, trap result, checklist, quiz, teaching panel | `useCoachFlow.activeCoachingMoment` projected into one unified coach panel | Adapt; suppress legacy surfaces while the unified flag owns the session |
| Postgame | Reflection, lesson, streak, proof, geometry summary, debug export | Existing postgame analysis projected into one unified summary | Retain analysis; replace stacking presentation; retire player debug export |

Adding a focus, detector, opening, trap, or endgame does not require an edit to the unified UI/controller. Those systems continue to publish evidence through their canonical registries and pipelines.

## State-transition contract

| State | Player action | System result |
|---|---|---|
| Entry | Open ordinary or deep-linked route | Load eligibility and canonical context; render one setup |
| Setup | Choose Coach or Play | Store only `game_mode`; derive evidence stage server-side |
| Ready | Start | Create one session; render board and one stable panel |
| Player turn, Play mode | Make legal move | Commit directly; never evaluate for a visible coaching intervention |
| Player turn, Coach mode | Make legal move | Preview locally; call `/evaluate-pending` once |
| Silent/ordinary result | No verified warning | Commit through `/move`; show at most one selected non-blocking message |
| Verified critical warning | Warning selected | Restore the pre-move board and show Try another move / Play it anyway |
| Warning retry | Try another move | Clear pending move and intervention; return to player turn |
| Warning override | Play it anyway | Commit exactly once through `/move/confirm`; record override; continue |
| Explicit help | Choose an Ask coach action | Render one verified response in the existing panel; never block the next legal move |
| Coach turn | Wait | Coach move is committed once; one eligible message may replace the idle panel |
| Evaluation failure | None | Commit the legal move and show recoverable status; never trap the session |
| Reconnect/resume | Return | Restore mode, FEN, clocks, focus, and at most one current message |
| Game over | Finish/resign/draw | Render one summary; persist existing analysis and evidence |
| Exit | Leave active game | Confirm only when data would be lost; otherwise preserve resumable state |

## Endpoint and persistence compatibility

- `coach_sessions` remains the session record. No second session collection or schema is introduced.
- `coach_messages` remains the durable message log. Unified messages add provenance and surface metadata without copying chess knowledge.
- `/coach/play/start`, `/move`, `/move/confirm`, `/state`, `/active`, `/end`, and `/postgame` remain the lifecycle endpoints.
- `/evaluate-pending` becomes the only move-evaluation request in Unified Coach mode.
- `/evaluate` remains available only to legacy sessions during rollback and is not called by the unified path.
- Existing teaching, escape-square, geometry, predict, and rate endpoints remain compatible for legacy sessions, but their UI cannot take ownership during a unified session.
- `coaching_context` is snapshotted for continuity, while fresh focus reads remain owned by `focus_bridge`.
- `analysis_completion_evidence` continues to derive assisted, checkpoint, and ordinary-play evidence after the game.

## Truth and abstention contract

- Legal move truth and evaluation come from python-chess and Stockfish.
- Position-specific teaching text comes through the central caption pipeline and its existing verifier.
- A pre-move warning may block auto-commit only when the evaluation is valid and the selected fact can name the affected piece/square or verified consequence.
- If the engine, verifier, or context fails, the system abstains from the claim and allows the legal move.
- Play mode does not request or reveal a live coaching verdict.
- The LLM may polish an already verified message asynchronously; it never chooses the move, classification, focus, or intervention.

## Rollout and rollback

- Add one default-off `PWC_UNIFIED_EXPERIENCE_V1_ENABLED` backend flag with admin/super-admin eligibility first.
- The session stores the experience version at creation so a deployment or flag change cannot switch an active game's controller halfway through.
- Legacy and Unified sessions remain resumable by their stored experience version.
- Rollback disables creation of new Unified sessions; it does not rewrite active sessions, messages, focus, or analysis.
- No production enablement occurs until the live desktop/mobile visual audit, strict journey verification, and the new end-to-end tests pass.

## Six-point audit

1. **Literal UI mockup — PASS.** The approved scope includes setup, idle coach, warning, positive teaching, contextual knowledge, and postgame copy.
2. **Pattern-led headline — PASS.** The session and postgame lead with “Piece safety” / “Keep every piece protected.” SAN appears only as turning-point evidence.
3. **Thresholds from data — PASS.** Defaults and cadence are locked in the accompanying production data note. Existing inherited caps are identified as inherited rather than falsely re-derived.
4. **Behavior-changing success metric — PASS.** Later unassisted handling of the primary focus is the learning outcome; setup, completion, abandonment, and return are supporting journey measures.
5. **Deferred work remains deferred — PASS.** No new detectors, content libraries, player model, pricing, voice, social play, or redesign of adjacent products enters V1.
6. **Mohit signoff — PASS.** Mohit explicitly replied “approved” after receiving the complete scope on 2026-09-13.

## Visual-audit caveat

The production browser-control helper failed to start twice. The current-state audit therefore used the routed code, supplied user evidence, live flags, and anonymized production aggregates. This does not weaken the implementation boundary, but it blocks production rollout: a live desktop and mobile visual walkthrough remains mandatory before the feature flag can reach players.

## Result

**PRE-CODE AUDIT: PASS**
Feature: Play with Coach — Unified Experience
Proceeding to implementation behind a default-off flag.
