# Canonical Coaching Context — Spec

**Status:** IMPLEMENTED DEFAULT-OFF — staging validation pending.  
**Version:** v1 (2026-08-28).  
**Scope:** largest; multi-day to ship across four product surfaces.

---

## 1. The problem

ChessGuru has a canonical focus store and bridge, but not a canonical
cross-surface presentation contract. Coach Play reads `focus_bridge`; the
active-focus route directly reads Mongo and owns duplicate labels/trend logic;
Training has compatibility selection; routed Game Review fetches a separate
cognitive priority. The same player can therefore see different priorities,
and legacy absence/trend logic can overstate improvement.

The production census found 90 active focus records across 52 users but only
one active instruction ID and no populated `current_metric` or PIC V1 records.
This migration must expose missing evidence honestly; it must not manufacture
continuity from sparse records.

## 2. The shape — five outcomes

```text
user_active_focus
      │
focus_bridge + detector authorization + PIC/mastery projection
      │
coaching_context.v1 builder
      ├── Home adapter
      ├── Review adapter (+ authorized game move matches)
      ├── Training adapter
      └── Coach Play server-side session snapshot
```

| Outcome | Contract behavior |
|---|---|
| `no_focus` | No rival fallback; explain that verified evidence is still being collected |
| `primary_only` | One canonical primary focus/instruction and one next action |
| `primary_with_support` | Same primary; bounded secondary issues that cannot own the CTA |
| `evidence_pending` | Show observations/denominator and explicit no-claim language |
| `pic_outcome` | Render the canonical PIC/mastery projection; never recalculate in a surface |

Core response shape:

```json
{
  "schema_version": "coaching_context.v1",
  "state": "primary_with_support",
  "primary_focus": {
    "focus_id": "...",
    "topic_key": "piece_safety",
    "label": "Piece safety",
    "instruction_id": "...",
    "instruction_text": "Before every move, ask: can this piece be taken?",
    "instruction_version": 1
  },
  "supporting_focuses": [],
  "evidence": {"eligibility": "verified", "verdict": "measurement_pending"},
  "learner_projection": null,
  "next_action": {"type": "practice", "href": "/training/...", "label": "Practise this check"},
  "rollout": {"eligible": true, "reason": "enabled"}
}
```

## 3. Schema / files touched

- Extend `backend/services/focus_bridge.py` with a versioned context builder;
  keep `get_active_focus_bundle()` as the focus authority.
- Add a thin response route in `backend/routes/coach.py`; refactor the existing
  `/active-focus` handler to delegate under the flag rather than re-querying.
- Add a Review adapter using existing `move_observations` and
  `focus_area_badges`; do not add a detector.
- Update `frontend/src/pages/HomePageNew.jsx`, `LabV2.jsx`,
  `components/GameDecryptionV5.jsx`, `PrescribedTraining.jsx`, and Coach Play
  setup/session consumers to render the contract.
- Extend `frontend/src/lib/analytics.js` only with approved context event IDs.
- No new Mongo collection. Historical sessions retain immutable context IDs;
  active authority remains `user_active_focus`.

## 4. New facts / data the system needs

- Stable active focus document ID exposed as `focus_id`.
- Detector authorization/rollout reason in the response.
- Existing PIC proof eligibility, evidence summary and learner projection.
- For Review only: authorized move numbers whose observation topic matches the
  primary/supporting focus. Empty matches mean “not observed,” not “fixed.”
- A bounded supporting-focus policy selected from existing authorized
  `runners_up`; no new score formula in V1.

## 5. Gating — preventing the parallel-coach trap

- `COACHING_CONTEXT_V1_ENABLED=false` is the only migration gate.
- Flag-on context may read focus priority only through `focus_bridge`.
- Detector `PLAN` authority gates both primary and supporting issues.
- Surface adapters cannot rewrite instruction text, compute verdicts or choose
  fallback priorities.
- A schema validator rejects missing/unknown state, action and evidence enums.
- A static contract test fails if migrated flag-on code calls
  `/cognitive/training-priority` or directly reads `user_active_focus`.
- Client analytics never grants learning or payment state.

## 6. Test strategy

1. **Stateless probe:** build all five outcomes from fixed focus/PIC fixtures;
   validate exact schema, authorization and no-claim language.
2. **Boundary suite:** no focus, stale focus, unauthorized detector, flag off,
   missing instruction, supporting-only evidence, no matching review move and
   game-deciding off-focus move.
3. **Cross-surface snapshot:** the same fixture returns identical focus and
   instruction IDs/text through Home, Review, Training and Coach Play.
4. **Integration:** Coach Play session stores the server-built snapshot;
   Review uses existing observations; analytics properties contain IDs but no
   private text.
5. **Browser/E2E:** Mohit and Parth verify literal states at desktop/mobile and
   compare flag-off versus flag-on accounts.
6. Run focused suites, `test_all_flows.py`, frontend production build and one
   staging event-inspector trace before rollout.

## 7. Risk + rollback

Main risks are a blank Home for users with legacy-only priority, Review hiding
the decisive move, extra database latency, an unauthorized supporting focus,
or a partial rollout producing two simultaneous coach cards.

Rollback: set `COACHING_CONTEXT_V1_ENABLED=false`; old endpoints/components
remain intact until the deletion phase. No data rollback is required because
V1 adds response shaping and immutable session IDs, not a new authority.

## 8. What this spec does NOT cover

- Detector improvement, caption generation, PIC threshold locking, recurring
  billing, opening curriculum, unlimited player-chosen plans or a UI redesign.
- Migration of every legacy “focus” component outside Home, routed Review,
  Prescribed Training and Coach Play.
- Changes to the V1 supporting-focus cap of one contextual supporting focus.

## 9. Implementation order

1. Land scope/spec alone; no runtime code.
2. After §10 signoff, add schema fixtures, validators and failing contract tests.
3. Implement builder/route default-off (`COACHING_CONTEXT_V1_ENABLED=false`).
4. Wire one internal Home account, then Review, Training and Coach Play; prove
   same IDs/text and no competing card.
5. Mohit + Parth A/B for one week with flag on, subordinate to the active-
   experiment policy.
6. Roll out to 10% for one week; monitor payload errors, CTA use, context
   consistency, latency and qualitative confusion.
7. Roll out to 100% after the gate report passes.
8. After two clean weeks at 100%, delete the four replaced selector paths and
   compatibility rendering; keep focus_bridge as the only authority.

Recommended implementation commits after signoff:

- `test(coach): lock coaching_context.v1 contract`
- `feat(coach): add default-off canonical context builder`
- `feat(review): carry canonical context through core surfaces`
- `chore(coach): remove migrated legacy focus selectors`

## 10. Decisions / Open questions for Mohit

Approved decisions for implementation phase 2:

1. One primary instruction plus at most one visible contextual supporting focus.
2. Requested openings/endgames are a separate elective object, not a
   diagnosed focus.
3. Chess truth leads Review; active focus leads the
   explicit practice connection.
4. The one flag-on Home renderer is the existing
   PIC-aware `HomePageNew` conversation, not legacy `FocusCard` trend UI.
5. Coach Play context is constructed server-side at session creation.
6. Rollout must wait for, or be proven orthogonal to, the currently
   active product experiment.
