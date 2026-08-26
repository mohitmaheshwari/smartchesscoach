---
name: scaffold-skill-drill
description: Bootstrap the full puzzle-drill pipeline for a new concept-detector skill in smartchesscoach. Builds the community puzzle pool, adds the skill_id to the drillable list, and registers per-skill copy in the frontend drill page. Trigger when the user adds a new concept_detector and wants it drillable.
---

# Scaffold a skill drill end-to-end

When a new concept_detector ships (or an existing one is re-tightened), the drill side has 4 mechanical steps before users can play it. This skill runs them in order.

## When to invoke

- User says "wire up the drill for `<skill_id>`" / "make `<skill_id>` drillable"
- User explicitly types `/scaffold-skill-drill <skill_id>`
- User merges a new concept_detector and asks "what's next?"

## Required input

- `skill_id` — must match a key in `backend/services/concept_detectors/registry.py:DETECTORS`. If it doesn't, stop and tell the user to add the detector + register it first.

## Prerequisites (check, don't build)

Skill ships once these are true. Verify before doing anything:

1. `backend/services/concept_detectors/{detector_module}.py` exists with a `detect_*` function
2. `DETECTORS` map in `backend/services/concept_detectors/registry.py` contains `{skill_id}: detect_fn`
3. `skill_id` is in `backend/data/coaching/skill_tree.json` with a label

If any of these are missing, stop. Tell the user what's missing. The drill scaffolding only makes sense once detection works.

## Steps

1. **Run the community pool builder** for this skill. Dry-run first:

   ```bash
   MSYS_NO_PATHCONV=1 docker exec chess-coach-backend python /app/backend/scripts/build_community_skill_pool.py --skill {skill_id}
   ```

   Report the counts (`applied_inserted`, `missed_inserted`, `positions_found`). If `positions_found == 0` across 5000+ games, that's a signal the detector is too narrow — STOP and tell the user (don't apply, the drill will be empty).

   If counts look reasonable (say, ≥20 positions), apply:

   ```bash
   MSYS_NO_PATHCONV=1 docker exec chess-coach-backend python /app/backend/scripts/build_community_skill_pool.py --skill {skill_id} --apply
   ```

2. **Add to DRILLABLE_SKILLS** in `frontend/src/components/coach/MasteryPanel.jsx`. Find the `const DRILLABLE_SKILLS = new Set([...])` block and add the new `skill_id`. Keep the registry comment in sync.

3. **Add SKILL_COPY entry** in `frontend/src/pages/SkillDrill.jsx`. Map `skill_id → {title, prompt, hint}`. Voice: neutral, 600-1500 audience, no chess jargon ([feedback_caption_voice_avoid_chess_jargon]). Skim 2-3 existing entries first to match tone.

4. **Smoke test** end-to-end:
   - Hit `GET /api/training/skill-puzzles/{skill_id}` (lazy extraction fires; returns puzzles).
   - Spot-check: for one puzzle, what does the detector return for the user's actual move at that position? Should be "applied" or "missed", not "none". If "none", the extract logic is leaking non-fires into the pool — STOP and report.

5. **Commit + push** with a single commit. Title: `feat(skill-drill): wire {skill_id} drill end-to-end`. Body: counts from step 1, files touched, and "verified via lazy-extract endpoint". Co-author tag per [feedback_always_push_after_commit].

## What NOT to do

- Don't write a new drill page. `SkillDrill.jsx` is generic over `skill_id`; only `SKILL_COPY` needs an entry.
- Don't write a new attempt-grading endpoint. `POST /api/training/skill-puzzle-attempt` dispatches via `registry.DETECTORS`.
- Don't add a backfill script for per-user evidence. Live wiring (`record_concept_applications_from_game`) handles that on every newly-analyzed game.
- Don't migrate skill_ids. Use the canonical name from `skill_tree.json` (e.g. `endgame_X`, not `X`) — see the rule_of_square migration ([project_docker_no_source_mount] has the docker-cp pattern if testing iteratively).

## Open question to flag

After scaffolding, ask the user if they want a `SKILL_COPY` hint and prompt review pass — wording always benefits from one round of feedback, and writing it cold tends to produce jargon.
