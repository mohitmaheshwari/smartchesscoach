# PWC Skills-Aware Live Coaching — Spec

**Status:** SHIPPED — v2 revises the mastery outcome from SUPPRESS to DOWNGRADE per Mohit 2026-06-03 (commits `fc8909ee` phase A, `0586313b` phase B, `60eceb2e` SUPPRESS→DOWNGRADE).
**Version:** v2 (2026-06-03). v1 was 2026-06-02.
**Scope:** smallest of the three PWC specs; shipped in ~half-day as planned.

**v1 → v2 change:** the mastered-skill outcome was SUPPRESS (hide the nudge). Mohit pushed back on this: missing one warning > one redundant warning (asymmetric cost). v2 replaces SUPPRESS with DOWNGRADE — the nudge stays visible but gets a `"You've handled this before — quick reminder."` prefix. ESCALATE branch unchanged.

---

## 1. The problem

PWC's live coaching layer consults `coach_memory.weaknesses` (recurring mistakes) but **does not consult `coach_memory.learning.skills`** (engine2 mastery counters). The audit (2026-06-02) confirmed: no grep hits for `learning.skills` in [backend/services/realtime_coaching_feedback.py](backend/services/realtime_coaching_feedback.py) or anywhere in the coaching dispatch.

Consequence: a user who has mastered rule of the square (16/22 applied) still gets the same basic "watch the king vs pawn race" prompts they got on day one. A user who keeps missing knight forks (`defend_scholars_mate: wrong=3 correct=2`) gets the same intensity as a user who's mastered it.

This is the "premium tier delta" — PWC should *remember* what the user knows.

---

## 2. The shape

For every PWC coaching nudge, before emitting:

1. **Look up the skill_id this nudge maps to.** Each coaching nudge in PWC corresponds to ≥1 Engine 2 skill (e.g., a Fried Liver-defense warning maps to `defend_fried_liver`; a king-pawn-race coaching point maps to `endgame_rule_of_square`).
2. **Read the user's mastery state.** From `coach_memory.learning.skills`: `seen / applied / correct / wrong`.
3. **Gate or escalate**:

   | Skill state | Effect on the nudge |
   |---|---|
   | `applied ≥ 3` AND `wrong / max(seen,1) < 0.2` | **Downgrade** (v2 2026-06-03) — keep the nudge visible, prepend `"You've handled this before — quick reminder."` Replaces v1's SUPPRESS, which had asymmetric cost (one missed warning > one redundant warning). |
   | `wrong ≥ correct` AND `seen ≥ 3` | **Escalate** — surface harder, with explicit "you've missed this before" framing |
   | `seen < 3` | **Default** — normal nudge, no modifier |

4. **Record the coaching event** in `coach_memory.learning.skills.{skill_id}.evidence` as a "PWC live coaching surfaced" entry, so the mastery system can later credit applied skills triggered through PWC.

---

## 3. Where the change lands

[backend/services/realtime_coaching_feedback.py](backend/services/realtime_coaching_feedback.py):

- After each coaching candidate is selected (around line 1500-1620 where shape/trap/curriculum facts are assembled) but BEFORE the candidate is formatted for the response, run a new `gate_by_skill_mastery(candidate, coach_memory)` filter.
- As shipped: `services/pwc_skill_gate.gate_decision(nudge_id, learning_skills)` returns a dict with `decision ∈ {PASS, DOWNGRADE, ESCALATE}`, `reason`, `matched_skills`, `escalate_prefix`, `downgrade_prefix`. v1 had `SUPPRESS`; the constant remains in the API for backwards-compat but is not produced by the default decision logic in v2. The consumer prepends `downgrade_prefix` to the warning text (e.g., `trap_suggestion["description"]`).

A new module `backend/services/pwc_skill_gate.py` houses this. Keeps the change isolated from the legacy `coaching_voice` engine and easy to revert.

---

## 4. The candidate → skill_id mapping

The mapping is the hardest part. Most PWC nudges don't currently know which skill they correspond to. We need an explicit `coaching_skill_map.json` (or similar) that lives in `backend/data/coaching/`:

```json
{
  "fried_liver_warning": ["defend_fried_liver"],
  "scholars_mate_setup_warning": ["defend_scholars_mate"],
  "kp_race_coaching": ["endgame_rule_of_square"],
  "opposition_pointer": ["endgame_opposition"],
  "lucena_bridge_setup": ["endgame_lucena"],
  "philidor_defensive_setup": ["endgame_philidor"],
  "mate_kq_vs_k_coaching": ["mate_kq_vs_k"],
  "mate_kr_vs_k_coaching": ["mate_kr_vs_k"]
}
```

Initial coverage: the 8 skills already in `concept_detectors/registry.py`. Other PWC nudges that don't map to a known skill default to ungated (no change in behaviour).

---

## 5. Gating thresholds — calibrated

The thresholds in §2 are starting points. Calibration:

- **Mastery cutoff** `applied ≥ 3 AND wrong/seen < 0.2`: matches the existing `SkillProgress.is_learned()` definition in `coach_memory.py` (so we don't define a new mastery concept).
- **Struggle cutoff** `wrong ≥ correct AND seen ≥ 3`: stricter than the engine2 default to avoid hammering users on a few unlucky games.

After ship, monitor: per-user count of downgraded-nudge events. If downgrade count > 30% of nudges, the threshold is too loose (we're prepending "you've handled this before" too often). If < 5%, too tight.

---

## 6. Behaviour for the three outcome cases

**Mastered + still applicable (DOWNGRADE):** keep the nudge visible; prepend `"You've handled this before — quick reminder."` to the warning text. Replaces v1's SUPPRESS, which hid the nudge entirely. Reasoning: missing one warning > one redundant warning, so we don't gamble on "the user definitely knows this." Mastery counters can also overestimate — a user with `applied=3/seen=4` on a defence may still miss the trap setup from an unfamiliar move-order.

**Struggling + applicable:** prepend the existing nudge with a one-line cross-game framing: `"You've missed this pattern 3 times before — let's lock it in."` Then the regular nudge text.

**Default + applicable:** unchanged from today.

---

## 7. Testing strategy

1. **Unit test** the gate function on synthetic `SkillProgress` records covering all three states. ~12 cases.
2. **Stateless probe** `probe_pwc_skill_gate.py` — given a candidate + simulated skill state, what does the gate return.
3. **Per-user integration test**: spin up the test user (`user_8b599930d7ef`) with their actual skill state. Walk through a synthetic PWC game's coaching candidates and verify downgrade/escalation matches expectations.
4. **A/B for one week**: gate disabled by default (env var). Mohit + Parth play one PWC game each with the gate enabled; eyeball whether the downgrade prefix reads naturally and the escalation hits land.

---

## 8. Risk + rollback

**Blast radius:** PWC coaching is per-move; the gate runs on every coaching candidate. ~Every paid user's session hits this code path.

**Failure modes:**
- Over-downgrade: user mastered a skill in lessons but hasn't applied in real-time; PWC prepends "you've handled this before" on a position where they're still building muscle memory. Lower-risk than v1's full suppression — the warning still appears.
- Mapping miss: nudge isn't in `coaching_skill_map.json`, behaviour unchanged but the gate had nothing to do.
- Coach_memory schema drift: if `learning.skills` is missing/empty, gate must degrade gracefully (fall through to default behaviour).

**Rollback:** env var `PWC_SKILL_GATE_ENABLED` (default false on first ship). Disabling reverts to today's behaviour. The map JSON stays in place — harmless without the gate consulting it.

---

## 9. Implementation order

1. Add `coaching_skill_map.json` with the 8 known entries.
2. Add `services/pwc_skill_gate.py` with `gate_by_skill_mastery()` + unit tests.
3. Wire the gate into `realtime_coaching_feedback.py` candidate-finalisation step. Behind env var, default off.
4. Stateless probe + per-user integration test.
5. Ship with env var off. Mohit + Parth flip it on for personal sessions, gather feedback.
6. Default on after one week of clean usage.

---

## 10. Out of scope

- Bidirectional update: PWC coaching events should write back to `learning.skills` evidence ("applied via PWC at this position") for closed-loop tracking. Worth doing but a separate spec — the mastery system already tracks engine2 attempts through the lesson surfaces.
- New skills: this spec only consults what already exists in the registry. New skills follow `/scaffold-skill-drill`.
- Voice/wording changes: the gate adjusts FLOW (downgrade / escalate / default), not WORDING. The two prefix strings (`downgrade_prefix`, `escalate_prefix`) are minimal teaching framings, not full rewrites; deeper voice work goes through `/rewrite-for-1200`.
