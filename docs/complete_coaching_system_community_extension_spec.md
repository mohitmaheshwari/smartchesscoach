# Complete Coaching System — Community Extension Technical Spec

**Status:** LOCKED FOR SHADOW FOUNDATION IMPLEMENTATION
**Date:** 2026-09-15
**Parent authority:** docs/complete_coaching_system_scope.md
**Data lock:** docs/complete_coaching_system_community_extension_data_lock_2026_09_15.md

## 1. Product boundary

This is not a community destination. It adds two teaching methods to the same persistent coach:

1. the coach may assign a licensed or explicitly consented whole game because its verified chapters fit the learner's current plan;
2. two opted-in learners may play an invite/scheduled human match, receive a neutral shared review and then return to different private coaching plans.

Home still owns the conversation, Game Review the guided study, Learn the assignment, Play with Coach the application and Progress the proof.

## 2. Canonical authorities

| Concern | Owner | Rule |
|---|---|---|
| Learner focus | user_active_focus through services/focus_bridge.py | Community code reads it; it never chooses another weakness. |
| Chess claims | Existing GameTeachingPlan, TeachableEvent and detector-quality authorization | Community code may neutralize presentation, but may not reinterpret a FEN, engine score or detector output. |
| Review lifecycle | Existing game_review_prescriptions and services/coach_selected_review_service.py | Personal and community reviews share recommended, started, dismissed, completed and superseded behavior. |
| Whole-game admission | New community_game_studies admission rows | This is the missing authority for license, privacy, replay, plan identity and publishability. It stores references and admission facts, not copied caption knowledge. |
| Game and analysis truth | Existing games and game_analyses contracts, with explicit community ownership metadata | A community record cannot appear in a personal archive query. |
| Lesson and transfer evidence | Existing LessonResult v2 and canonical learning reducer | Community study is assisted learning. It cannot prove later-game transfer. |
| Human-match lifecycle | A future community_matches owner within Play with Coach | It owns invitations, acceptance, clock state, reconnect, result and termination; it does not own learning conclusions. |

## 3. Community game admission contract

An admission row contains:

- stable opaque study_id and source game_id;
- schema and admission-policy version;
- status: shadow, admitted, quarantined, withdrawn or stale;
- source provider, release identifier, source checksum, license and terms-review date;
- anonymous rating band and time-control category;
- legal-replay result and replay fingerprint;
- current GameTeachingPlan ID, input fingerprint and safe-projection version;
- admitted chapter event IDs and their authorization identities;
- identity/PII scan result;
- created, checked, withdrawn and stale timestamps plus explicit reason codes.

Admission fails closed if the source is unapproved, replay fails, identity fields survive, plan identity is stale, fewer than two authorized chapters survive, or any selected event cannot be projected neutrally.

No player name, username, profile link, email, source URL token or original learner diagnosis reaches the public payload.

## 4. Neutral chapter projection

The source player's personalized GameTeachingPlan cannot be shown verbatim to another learner. A neutral projection may retain only:

- board position and legal move sequence;
- side to move and neutral White/Black language;
- verified objective setup, constraint, payoff and teaching principle;
- current player-facing authorization/provenance IDs;
- opening, tactical, positional or endgame labels already owned by canonical content.

It removes source-player memory, recurrence, weakness, reflection, emotional framing, private answers and next action. The target learner's focus connection is added separately by focus_bridge; it never rewrites the chess fact.

## 5. Selection and prescription

The Shadow foundation evaluates admitted community candidates through the formula locked in the data document. It records the best community candidate beside the existing personal recommendation but does not alter the player-visible prescription.

After blinded quality approval, the one canonical selector ranks personal and community candidates through an explicitly measured source-mix policy. Until that later lock exists, community may not silently displace an eligible personal game.

The public prescription adds source_kind and study_id while keeping internal game ID, plan fingerprint, source record key and license audit metadata private. Community copy says why the pattern fits and that the players were in the learner's rating band; it never presents source identity as evidence.

## 6. Review runtime

- The existing Game Review page and GameDecryptionV5 renderer remain the only board experience.
- A source-aware loader returns the same review projection shape for a personal game or admitted community study.
- The URL carries only the opaque study/prescription identity.
- Start, resume, dismiss and complete call the existing prescription lifecycle.
- Completion emits assisted LessonResult evidence and the existing next-action handoff.
- Later organic games remain the only transfer authority.

## 7. Human-match workstream

Human matches remain inside this active program but start after the community-study Shadow packet and the approved threat model. The first mode is invite/scheduled.

Required before coding the player-visible match:

- invitation, acceptance and expiration semantics;
- server-authoritative clocks and move legality;
- reconnect, duplicate request, abandonment, resignation and draw behavior;
- explicit unassisted-versus-symmetric-coaching mode;
- fair-play and engine-assistance policy;
- report, block, moderation and abuse escalation;
- consent, retention, deletion and community-study reuse choice;
- shared-review projection that cannot read either private coaching context;
- separate authenticated private follow-up calls after the shared review.

The engine-opponent path remains available and is never labeled as a community player.

## 8. Flags and rollout

- COMMUNITY_GAME_STUDY_SHADOW_ENABLED: computes and records identity-free Shadow selection evidence only.
- COMMUNITY_GAME_STUDY_VISIBLE_ENABLED: remains absent or false until the blinded player-facing packet passes.
- COMMUNITY_HUMAN_MATCH_ENABLED: remains absent or false until its separate threat-model and E2E gate passes.

The existing complete-coaching access decision owns account enrollment. These flags provide technical safety and do not create new user cohorts.

## 9. Testing

The Shadow foundation must prove:

- accepted and rejected admission cases for every fail-closed rule;
- complete legal replay and stable fingerprints;
- no Chess.com or unknown-license admission;
- no PII or source-player personalization in public/neutral projections;
- exact canonical focus matching and data-locked ordering;
- minimum two current authorized chapters;
- completed/dismissed study exclusion and deterministic replay;
- personal recommendation behavior is byte-equivalent when Shadow is off;
- Shadow cannot change the visible prescription;
- no imports of Stockfish, an LLM or a second caption engine in the selector.

Player-visible work additionally requires backend contract tests, frontend interaction tests, production build, privacy/adversarial tests, a blinded coach packet and real account-isolated E2E.

## 10. Delivery sequence

1. Implement pure admission and neutral-projection validators.
2. Implement read-only Shadow candidate loading and aggregate evidence output.
3. Produce the blinded neutral community-game packet and obtain Mohit/coach review.
4. Lock personal-versus-community source mixing from measured results.
5. Extend the existing prescription and source-aware review loader.
6. Add guided predict, compare and replay interaction through the existing renderer.
7. Connect completion to LessonResult and the canonical next action.
8. Complete the human-match threat model and invite/scheduled architecture.
9. Implement and validate the human match, shared review and private follow-ups.

No deployment, ingestion of new provider data, production write or ordinary-user exposure is authorized by this technical spec.
