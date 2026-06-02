---
name: author-r12-predicate
description: Scaffold a new R12_blunder.json failure-mode predicate end-to-end — fact gating, variant template with contextual verb, teaching principle, probe case. Use when adding a new "why played wrong" failure mode (e.g. allows_skewer, removes_defender, allows_discovered_attack) after the 2026-06-02 two-clause shipping. Trigger when the user types /author-r12-predicate or says "add a failure mode for X" or "we need a predicate for the [pattern] case".
---

# Author a new R12 failure-mode predicate

The 2026-06-02 "why played wrong" architecture (see [docs/why_played_wrong_spec.md](../../docs/why_played_wrong_spec.md)) is built on three pieces per failure mode:

1. A `failure_mode_clauses_user` predicate (when does it fire)
2. A variant template with a contextual verb (how it reads)
3. A teaching principle (the universal lesson)

Adding a new one means doing all three plus a probe case + (often) a new fact extractor in `caption_facts.py`. This skill walks through the scaffold so each new failure mode ships consistently.

## When to invoke

- User describes a failure pattern not covered by the existing 7 failure modes (`walks_into_check`, `allows_fork`, `allows_capture`, `exchange_losing_with_reply`, `exchange_losing_no_reply`, `played_piece_attacked`, `hangs_piece`)
- User has ≥2 concrete examples (per [memory/feedback_build_detectors_on_first_approval] — single-flag designs are filed, not built)
- User types `/author-r12-predicate`

Do NOT invoke on a single example — file it in [CAPTION_BACKLOG.md](../../CAPTION_BACKLOG.md) and wait for a second.

## Required input

- **Failure name** in snake_case (e.g. `allows_skewer`)
- **Verb phrase** for the variant template (e.g. `"allows {opp_reply_san} skewering your {target_1} through {target_2}"`)
- **Teaching principle** — one universal sentence (e.g. `"When valuable pieces line up on the same file or diagonal, watch for skewers."`)
- **≥2 example positions:** FEN + played move + best move + expected opp reply

## Steps

1. **Check non-duplication.** Read `failure_mode_clauses_user` in [backend/data/captions/R12_blunder.json](../../backend/data/captions/R12_blunder.json). If the new failure overlaps with an existing predicate's facts, either (a) refine the new predicate to be strictly disjoint, or (b) merge into the existing one with a parameter switch. Don't add a near-duplicate predicate — it'll cause ordering bugs like the 2026-06-01 reorder attempt.

2. **Identify the gating facts.** What's true in the example positions that wouldn't be true in a random mistake? Examples:
   - For `allows_skewer`: opp's reply attacks a high-value piece + a lower-value piece is on the same line behind it.
   - For `removes_defender`: opp's reply captures a piece that was defending a >value own piece.

   Map each required fact to either:
   - An EXISTING fact in `caption_facts.py` (good — no new extractor)
   - A NEW fact you need to add (write the extractor in this step's substep)

3. **Write the fact extractor** (only if step 2 surfaced a new fact). Pattern: add right after the existing `opp_reply_*` block in `caption_facts.py` (around line 4880-5000 area). Same conventions:
   - Compute on the post-opp-reply position (`sim` board)
   - Return structured info (boolean + named-target piece + named-target square) when the pattern fires
   - Defensive on PGN drift (try/except, leave facts None on failure)
   - Expose in the returned facts dict near line ~5197 alongside `opp_reply_creates_fork`

4. **Add the predicate entry** to `failure_mode_clauses_user`. Placement order matters — higher in the list = higher priority. Convention from the existing entries:
   - Most severe wins → `walks_into_check` (mate threat) is highest
   - Concrete material loss next → `allows_fork`, `allows_capture`
   - Damaging-but-not-immediately-fatal next → `exchange_losing`, `hangs_piece`, `played_piece_attacked`

   Match this rule of thumb when placing yours.

5. **Add the variant template** to the `variants` block. Conventions:
   - Verb starts with a present-tense verb the user hears as agency-on-the-played-move ("walks into", "allows", "hangs to", "loses to", "drops the", "leaves your", "exposes your"). No "is a mistake" framing — that's covered by the wrapper.
   - Lowercase, no trailing period — the wrapper variant adds the period.
   - Reference fact slots in the template with curly braces — same syntax as the existing failure variants.

6. **Add the teaching principle** to the `teaching_principles` dict. Conventions:
   - One sentence, universal (applies beyond this position).
   - Action-oriented ("Before X, do Y" / "When X, scan for Y"), not descriptive.
   - No trailing period (wrapper adds one).
   - No "?" at end (creates `?.`).
   - Avoid chess jargon — see [memory/feedback_caption_voice_avoid_chess_jargon].

7. **Add a probe case** to `backend/scripts/probe_why_played_wrong.py`. Two test cases: failure-only (verify principle fallback fires) + failure-plus-alternative (verify combined wrapper fires). Use one of the example FENs you collected as the realistic case.

8. **Run the probe** via `docker cp` + `docker exec` (see [memory/project_docker_no_source_mount] for the iterative testing pattern):

   ```bash
   MSYS_NO_PATHCONV=1 docker cp backend/data/captions/R12_blunder.json chess-coach-backend:/app/backend/data/captions/R12_blunder.json
   MSYS_NO_PATHCONV=1 docker cp backend/services/caption_facts.py chess-coach-backend:/app/backend/services/caption_facts.py
   MSYS_NO_PATHCONV=1 docker cp backend/scripts/probe_why_played_wrong.py chess-coach-backend:/app/backend/scripts/probe_why_played_wrong.py
   MSYS_NO_PATHCONV=1 docker exec chess-coach-backend python /app/backend/scripts/probe_why_played_wrong.py
   ```

   Expected: the new test cases produce the target caption shape; existing test cases unchanged.

9. **Update the spec** ([docs/why_played_wrong_spec.md](../../docs/why_played_wrong_spec.md)) §2 contextual-verb table and teaching-principles table to include the new entry. Spec is the source of truth for what's authored.

10. **Bump V5_COACHING_VERSION** in `backend/services/game_decryption_v5_service.py` (line 48). The note pattern is documented in that line's history. Bumping forces regen so existing games get the new caption.

11. **Commit + push** with a single commit including: predicate + variant + principle + facts extractor (if new) + probe + spec update + version bump. Title: `feat(R12): failure_<name> failure-mode predicate`. Body: motivation (the ≥2 examples), the contextual verb chosen, and the test outputs.

## What NOT to do

- **Don't ship on one example.** File against [CAPTION_BACKLOG.md](../../CAPTION_BACKLOG.md) and wait for a second per the memory rule.
- **Don't override an existing failure variant.** If the new pattern overlaps, refine to be disjoint or merge into the existing variant — don't duplicate predicates.
- **Don't omit the teaching principle.** Two-clause architecture requires it for the "failure + no alternative" outcome. Without it, the failure-only case produces a naked "{played} {failure}." sentence with no follow-up.
- **Don't add `_comment` entries inline.** The predicate walker treats those as unconditional matches and breaks selection. Use the `_note` keys at the bottom of the JSON instead (see existing pattern in `_failure_mode_promotion_note`).
- **Don't skip the probe.** The whole point of the probe is catching predicate-ordering and template-rendering bugs locally before they hit production.

## Notes

- The 7 existing failure modes were authored 2026-06-02 in commits `03b84eb8` (phase 1) + `aca067e4` (phase 2: fork). Read the diffs for concrete examples of what each entry looks like.
- If the new fact requires complex board geometry (e.g. detecting an alignment between three pieces), look at `_aligned_pieces_evidence` in caption_facts.py — it's the closest existing pattern.
- After shipping: run `/detector-quality-scan` on the new failure mode to spot-check FP/FN rate on ~50 games.
