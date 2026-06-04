# Engine 2 Phase 2 — Mastery Gate (DRAFT)

**Status:** DRAFT 2026-06-04. Awaiting Phase 1 backfill completion + Mohit sign-off.
**Depends on:** Phase 1 (`docs/engine2_phase1_concept_mastery.md`) — mastery signal must be present in `user_concept_understanding` rows.
**Owner:** Mohit + Claude

---

## 1. The problem

Phase 1 writes mastery state per user × concept. Phase 2 makes it MATTER. Today even after backfill, the V5 caption pipeline and PWC both render the same caption text regardless of whether the user has demonstrated mastery 100 times. We have the signal; nothing reads it.

Concrete user experience after Phase 1, before Phase 2:
- Mohit has `END_RULE_OF_SQUARE` mastered (18 clean games, 1 historical violation).
- Next time the rule of square comes up in his game, he STILL gets the full caption explaining the rule.

That's the gap Phase 2 closes.

## 2. The shape

A new service `services/user_mastery_gate.py` exposes one function:

```python
async def get_mastery_state(
    db, user_id: str, concept_id: str
) -> Literal["mastered", "slipping", "learning", "unseen"]
```

States:
- **`mastered`**: row exists, `acknowledged=True`, last violation > N days ago (or never).
- **`slipping`**: row exists, was mastered before (mastered_at != null) but recent violation reset it; `streak_clean < required` but `clean_games_total ≥ 5`.
- **`learning`**: row exists but `clean_games_total < 5` — user hasn't accumulated demonstration yet.
- **`unseen`**: no row OR the user has been shown < 2 times.

The caption pipeline and PWC each call the gate at the point where a caption is about to be emitted with a concept_id attached. Behavior per state:

| State | Caption action | PWC live-coaching action |
|---|---|---|
| `mastered` | SUPPRESS — drop the caption entirely, just show the move | SUPPRESS — no live nudge |
| `slipping` | DOWNGRADE — replace caption with brief reminder ("Quick check: piece safety here") | DOWNGRADE — brief audible nudge |
| `learning` | SHOW — full caption with WHY + principle | SHOW — full coaching |
| `unseen` | SHOW — full caption (default path, today's behavior) | SHOW — full coaching |

## 3. Call sites

### 3a. V5 caption pipeline finalize hook

In `services/game_decryption_v5_service.py`, after the caption is rendered, before `caption_payload["caption"]` lands on `move_output`, the gate is consulted:

```python
# Engine 2 Phase 2 — mastery gate.
if mastery_gate_enabled and caption_facts.get("principle_id_used"):
    state = await get_mastery_state(db, user_id, caption_facts["principle_id_used"])
    caption_payload["caption"] = _apply_gate(caption_payload["caption"], state)
```

### 3b. PWC live coaching

In `coach_play/coach_commentary.py`, after the coaching message is composed but before it's emitted to the session, the gate is consulted. PWC's coaching engine writes its own concept_ids per move (separate detector taxonomy from the central pipeline), so the gate is called with whichever concept_id PWC has at hand.

### 3c. Single function, two call sites

`services/user_mastery_gate.py` exports the function + a constant `MASTERY_GATE_ENABLED = bool(os.environ.get("PWC_SKILL_GATE_ENABLED"))`. Both sites short-circuit when the flag is unset.

## 4. The "slipping" definition

The hardest case is distinguishing:
- A user who's mastered a concept and hasn't been tested in a while → SUPPRESS still fires
- A user who's mastered a concept but just had a fresh violation → DOWNGRADE fires (brief reminder)

Rule (Phase 2 v1):

```
state = "slipping" if all of:
   row exists
   mastered_at != null  (was mastered at some point)
   streak_clean < streak_required
   last_violation_at within the last 7 days (configurable)
```

Translation: "you previously demonstrated mastery; you've had a fresh stumble; here's a brief reminder, not the full lesson again."

Otherwise the row falls back to `learning` or `mastered` based on current streak.

## 5. The mastered text → brief downgrade map

DOWNGRADE captions are picked from a small `mastery_downgrade_bank.json` keyed by concept_id prefix:
- TAC_ → "Quick: piece safety check"
- OP_ → "Opening discipline reminder"
- MID_ → "Middlegame pattern reminder"
- END_ → "Endgame fundamentals check"
- DEF_ → "Defense reminder"

Single sentence each; never more than 8 words. The point is to remind without re-teaching.

## 6. A/B rollout plan

| Phase | Cohort | Trigger | Duration |
|---|---|---|---|
| 6a | 0% — flag default-off | Default | Indefinite |
| 6b | 1 user (Mohit) — test | `PWC_SKILL_GATE_ENABLED=true` env override per his session | 2-3 days |
| 6c | 10% — sticky hash | New `user.skill_gate_cohort` field, gated by hash | 1 week |
| 6d | 50% | Bump hash threshold | 1 week |
| 6e | 100% | Flip env var; remove flag check | After QA |

Metric to watch: **caption-flag rate**. If users at gate-enabled cohort flag captions MORE often than control, we're suppressing/downgrading captions they actually wanted. Roll back.

Also: **clarification rate** (do users press "explain more" on downgraded captions? if yes, the brief reminder was too brief).

## 7. Schema additions

To `users.skill_gate_cohort` (sticky):
```js
{
  user_id, ...,
  skill_gate_cohort: "control" | "treatment",  // assigned at first session post-rollout
  skill_gate_cohort_assigned_at: ISO timestamp
}
```

No schema changes to `user_concept_understanding` — Phase 1 already added everything Phase 2 reads.

## 8. Test plan

1. **Function tests**: `get_mastery_state` returns the right state for synthesized row shapes (mastered with old violation, mastered with recent violation, learning with low clean count, unseen).
2. **Gate application**: `_apply_gate` returns the expected text per state.
3. **Integration**: regen a Mohit game where `END_RULE_OF_SQUARE` fires (he's mastered it). Confirm the caption is SUPPRESSED.
4. **Integration**: regen a Mohit game where `TAC_CHANGED_AFTER_MOVE` fires (he's struggling). Confirm the caption is SHOWN at full length.
5. **Flag-off behavior**: with `PWC_SKILL_GATE_ENABLED=` unset, no gating fires; behavior matches v104 exactly.
6. **Cohort assignment**: 10% rollout: of 1000 simulated users, ~100 land in treatment with stable hashing.

## 9. Rollback

Single env var flip: `PWC_SKILL_GATE_ENABLED=` (unset). Within minutes, all caption emissions revert to v104 behavior. The mastery signal in user_concept_understanding stays — only the read-side gate goes back to no-op.

## 10. What this does NOT do

- **No new mastery taxonomy**. Phase 2 reads what Phase 1 writes. New concepts only when Phase 1 auto-creates them.
- **No backwards-compatibility for the "I understand" button**. The button stays functional — users can manually flip acknowledged=True via the existing endpoint. The gate respects manual acks too (they look like mastered_at != null with no streak).
- **No PWC re-architecture**. PWC's own coaching engine (move_critique/coaching_policy/coaching_voice) is untouched. The gate is a thin wrapper at the emission point. The "one source of truth" migration (moving PWC entirely onto the central pipeline) is a separate effort (`docs/pwc_central_caption_migration.md`).
- **No opening-mastery extension**. The mirror gate for `user_opening_mastery` is Phase 3 (`docs/engine2_phase3_opening_gate.md`, not yet drafted).
