---
name: play-with-coach-phase1-design
description: Phase 1 implementation design — wedge V5 teaching layer into live Play with Coach behind a per-user feature flag. Deterministic draft <700ms + async LLM polish swap. Two-block sidebar composition with material-value gate. Coach-move teaching at 10-20% frequency. Three-layer silence (eligibility / necessity / interruption-worthiness). Per-game hard suppression + per-session soft decay. Builds on [[play-with-coach-teaching-integration]] and Mohit's answers 2026-05-18.
metadata:
  type: project
---

## Inputs locked (Mohit 2026-05-18, with corrections)

| Question | Decision |
|---|---|
| Latency | Deterministic draft <400-700ms immediately; LLM polish async swap-in within 2-3s. Truth layer = deterministic. LLM = presentation only. |
| Composition | Two visual blocks (primary realtime on top, V5 underneath). NEVER merge into one string. Suppress V5 if it adds no new abstraction. |
| Coach-move teaching | YES, ~20% default but ADAPTIVE — lower for quiet moves, higher for clear plans / tactical setups / endgame conversion. Hard cooldown: max 2 coach captions per 6 coach moves. NOT routine recaptures. |
| Silence rules | V5 must respect rating-aware silence. Eligibility ≠ necessity ≠ interruption-worthiness — three separate layers. |
| Suppression scope | State-based per-game hard suppression via state_key (see `[[suppression-key-overhaul]]`) + per-session soft decay weighting. **NOT** Set[principle_id] (too blunt). No permanent per-player. Cross-game recurrence is GOOD. |
| Material-value gate | **Structured comparison** (principle_id, pattern_id, target_square, piece_square, tactic_type, best_move_family) — NOT string match against primary_text. |
| Async polish swap | **Guarded** — hot-swap only if all four hold: same principle/target as draft, no contradiction with draft, polished length ≤1.4× draft length, arrives within 3s. Otherwise keep draft. |
| Pre-existing features | Independent for Phase 1. Long-term: shared interruption governor with pre-move guardian. |
| Feature flag | Per-user first; per-game override for A/B. Avoid global-only rollout. |

## Order (final)

1. **Phase 0.5** — Suppression-key overhaul (state_key + re-arm). See `[[suppression-key-overhaul]]`. Lands FIRST — live teaching must not ship on the current once_per_game blunt suppression.
2. **Phase 1.1** — Deterministic V5 block behind feature flag.
3. **Phase 1.2** — Structured material-value gate.
4. **Phase 1.3** — Adaptive coach-move teaching with 2/6 cooldown.
5. **Phase 1.4** — Guarded async polish.

## Architecture sketch

```
                  user makes move
                        │
                        ▼
        ┌───────────────────────────────┐
        │ POST /api/coach/play/move     │ (existing route)
        └───┬───────────────────────────┘
            │
            │ stockfish per-move analysis (existing)
            │ → fen_before, played_san, best_move_san,
            │   eval_before, eval_after, cp_loss, pv_after_*
            │
            ├── PATH A (existing, sub-second)
            │   realtime_coaching_feedback.generate_move_feedback()
            │   → MoveFeedback (rating-aware quality + brief why)
            │   → write coach_messages.primary_text
            │
            ├── PATH B (NEW for Phase 1 — also sub-second)
            │   ENABLED only when feature flag pwc_v5_teaching is on for user
            │   v5_teaching_decision_for_live_move(...)
            │   → caption_facts.extract_facts(...)
            │   → caption_priority_resolver.resolve_priority(move)
            │   → DETERMINISTIC draft = anchor_name + anchor_detail
            │     OR move["caption"] (renderer fallback)
            │   → suppression check (per-game state, per-session weight)
            │   → silence check (3-layer: eligibility / necessity / interruption)
            │   → if surfaced: write coach_messages.v5_block
            │       { anchor_name, anchor_detail, principle_id,
            │         polish_status: "draft" }
            │
            ▼
        frontend polls /api/coach/play/move-feedback/{session_id}
            → primary_text rendered immediately
            → v5_block rendered immediately if present (deterministic draft)
            │
            │ (in parallel, background task on backend)
            ▼
        ASYNC TASK (only if Path B surfaced)
        llm_caption_generator.generate_caption_for_move(move)
            → polished caption
            → patch coach_messages.v5_block.anchor_detail = polished
            → coach_messages.v5_block.polish_status = "polished"
            │
            ▼
        frontend's next poll picks up the polished version → smooth swap
```

## 1. Latency architecture

### Deterministic draft path (must be <700ms total)

Already-fast components:
- `extract_facts` is pure Python, ~50-100ms on typical positions.
- `resolve_priority` is pure Python, ~10-50ms.

Slow components to skip in the draft path:
- LLM polish (1-3s) — moved to async task.
- Any DB call that's not strictly needed for the response.

The draft sent to the user is `anchor_name + " — " + anchor_detail` from the resolver decision dict. Already 1200-test compliant by construction (the resolver detail is the IR).

### Async polish swap — GUARDED (Mohit 2026-05-18)

After the live move response is sent, the route schedules `asyncio.create_task(polish_task)`. The polish task:
1. Runs `generate_caption_for_move(move)` → polished string with a 3s deadline.
2. Applies guards before swapping:
   - **Same principle/target**: polished output must mention the same `principle_id` AND `target_square` (or `pattern_id`) as the draft. Use the resolver decision's protected_entities list to verify.
   - **No contradiction**: polished must not contradict the draft (no negation of named pattern, no flipping mover-perspective).
   - **Length cap**: polished length ≤ 1.4× draft length. Prevents the LLM from over-elaborating and replacing a crisp draft with a verbose paragraph.
   - **Deadline**: arrives within 3s of move-response send. After that, user has likely already moved on; abandon.
3. If all guards pass: update `coach_messages.v5_block.anchor_detail = polished`, `polish_status = "polished"`. Frontend's next poll hot-swaps.
4. If any guard fails: keep draft. Log the rejection reason (debugging tool).

Failure modes (no regression in any case):
- LLM call fails → guard 3 (deadline) trips; draft stays.
- LLM exceeds 3s → guard 3; draft stays.
- LLM contradicts draft → guard 2; draft stays.
- LLM elaborates verbosely → guard 4; draft stays.
- Backend restart during polish → polish task lost; record stays at draft.
- User left session → polish completes, record updates anyway (consistency with later /lab review).

### Failure modes

- LLM call fails → record stays as `polish_status: "draft"`, user keeps the deterministic version. No regression.
- Async task crashes → same as above; frontend renders draft.
- Polish takes too long → graceful drop.

## 2. Composition: two-block rendering

### Backend response shape (extension of existing coach_messages)

```python
{
    "session_id": str,
    "move_number": int,
    "primary_text": str,           # existing — realtime message
    "v5_block": Optional[{
        "anchor_name": str,        # "Rule of the Square" / "Loose piece on the board"
        "anchor_detail": str,      # the principle's specialised teaching text
        "principle_id": str,       # "END_RULE_OF_SQUARE" — for clickable rule UI
        "polish_status": "draft" | "polished",
        "is_coach_move_teaching": bool,  # True when this fires on COACH's move
    }],
    "highlight_squares": [...],    # for board overlay (existing field)
    "arrows": [...],               # for board overlay (existing field)
}
```

`v5_block` is OPTIONAL. Absent when:
- Feature flag is off for user
- V5 detector found nothing worth surfacing (no principle hit OR suppressed)
- Material-value gate rejects (see below)
- Interruption-worthiness gate rejects (see below)

### Material-value gate ("does V5 add a new abstraction?") — STRUCTURED

Mohit 2026-05-18: do NOT string-match. Compare structured fields the realtime path emits alongside its text.

Phase 1.2 augments the realtime path to emit a structured tag on every message:

```python
@dataclass
class MoveFeedbackTag:
    severity: str           # excellent / good / inaccuracy / mistake / blunder
    principle_id: Optional[str]   # if realtime path already named a principle
    pattern_id: Optional[str]     # if realtime path already named a shape pattern
    target_square: Optional[str]
    piece_square: Optional[str]
    tactic_type: Optional[str]    # "fork" / "pin" / "skewer" / "hang" / ...
    best_move_family: Optional[str]
```

V5 block is suppressed when:

```
realtime_tag.severity in ("excellent", "good") AND
no V5 principle hit OR
(realtime_tag.principle_id == v5.principle_id) OR
(realtime_tag.pattern_id == v5.pattern_id) OR
(realtime_tag.tactic_type == v5.principle.tactic_type AND
 realtime_tag.target_square == v5.evidence.target_square) OR
(realtime_tag.best_move_family == v5.state_key.best_move_family AND
 realtime_tag.piece_square == v5.evidence.piece_square)
```

Concrete examples:

KEEP (V5 adds new abstraction):
- Realtime tag: { severity=blunder, principle_id=null, tactic_type=null, target_square="e5", piece_square="e5" }
- Realtime text: "You left the knight on e5 hanging."
- V5 block: { principle_id="TAC_HANGING_PIECE", anchor_name="Loose piece on the board", target_square="e5" }
- → Different abstraction level (consequence vs. pattern name). Keep V5.

SUPPRESS (V5 duplicates):
- Realtime tag: { tactic_type="pin", target_square="c6" }
- Realtime text: "Good — Bb5 pins the knight on c6 against the king."
- V5 block: { principle_id="TAC_PIN_PATTERN", tactic_type="pin", target_square="c6" }
- → Same pattern + same target. Suppress V5.

Phase 1.2 ships the realtime tag emission AND the gate. Without structured tags from the realtime path, the gate degrades to "always show V5 when present" (acceptable Phase 1.1 behavior).

Example to KEEP (V5 adds value):
- Primary: "You left the knight on e5 hanging."
- V5 block: "Loose piece on the board — Your knight on e5 has no defender."
- Verdict: keep. Primary describes the consequence; V5 names the PATTERN ("loose piece on the board") which is the learning anchor.

Example to SUPPRESS (V5 duplicates):
- Primary: "Good — Bb5 pins the knight against the king. Classic Ruy Lopez idea."
- V5 block: "Two pieces on a line — Bb5 pins the front piece."
- Verdict: suppress V5. Primary already named the pattern.

## 3. Coach-move teaching (10-20% frequency)

### Selection rules

Coach-move V5 surfaces ONLY when one of these is true:
1. Coach's move triggered a PRINCIPLE detection with `match_kind: "missed_chance"` or `"played_move"` AND eval reflects meaningful change (>= 100cp swing).
2. Coach's move triggered a SHAPE pattern (tier 3) — these are inherently teaching-worthy.
3. Coach's move is a strategic transformation: opening transition, piece reorganization, structural break. (Identifiable via the `OP_*` and `MID_*` principle IDs — opening / middlegame strategic principles.)

Coach-move V5 surface is SUPPRESSED for:
- Routine recaptures (`forced_recapture: True` in facts).
- Engine-best moves with cp_loss < 30 AND no principle hit.
- Mate-search noise (eval already at mate territory).

### Adaptive frequency cap (Mohit 2026-05-18)

Default 20%, but ADAPTIVE based on the type of move:
- **Quiet moves** (no principle hit, routine play): much lower than 20% (maybe 0-5%).
- **Clear plans** (strategic transformation, opening plan transition): can exceed 20% in that window.
- **Tactical setup moments** (creating threats, pin/fork setup): can exceed 20%.
- **Endgame conversion ideas** (transitioning to a winning technique): can exceed 20%.

**Hard cooldown** (non-negotiable): at most 2 coach-V5 captions per 6 consecutive coach moves. If 2 have surfaced in the last 6 coach moves, suppress all further coach-V5 until the window resets.

Implementation:

```python
class CoachGameSession:
    ...
    coach_v5_surfaced_indices: List[int] = []   # coach move numbers where V5 surfaced
    coach_moves_made: int = 0

def coach_v5_within_cooldown(session) -> bool:
    """True if surfacing a new coach-V5 would violate 2-per-6 cooldown."""
    if session.coach_moves_made < 6:
        return False  # ramp-in: no cap for first 6 coach moves
    recent_surfaced = [
        i for i in session.coach_v5_surfaced_indices
        if i > session.coach_moves_made - 6
    ]
    return len(recent_surfaced) >= 2
```

The adaptive cap (higher for clear plans) is implemented via a per-candidate "teaching weight" 0-1 that combines:
- principle priority (lower priority number = higher weight)
- shape-pattern presence (+0.2)
- strategic transformation marker (+0.3)
- routine-recapture marker (-0.5)

Surface if weight × random_uniform > 0.7 AND not within cooldown. Threshold tuned empirically.

### Voice tone for coach-move teaching

Different from user-move teaching:
- User-move: "Your knight on e5 has no defender" (2nd person, present tense)
- Coach-move: "Coach centralizes the king before the pawn break" (3rd person, intention-framing)

The resolver detail templates currently assume user-move perspective. Phase 1: add a `coach_perspective` flag passed to `_principle_detail_text`; resolver branches on it to use intention-framed phrasing.

## 4. Three-layer silence model

V5_block is surfaced only if ALL three pass:

| Layer | Question | Implementation |
|---|---|---|
| Eligibility | Does the detector fire? | `extract_facts` returns a principle/shape match. |
| Necessity | Does this teaching add value for THIS user? | Rating-aware filter: e.g., a 1700 doesn't need "develop your knights first" once. Compare with user's per-session encounter weight (see §5). |
| Interruption-worthiness | Should we INTERRUPT the user with this *right now*? | Per-game suppression state. Plus: skip surfacing when primary_text is already a strong negative ("Hmm, you just hung your queen") — let the primary land first. |

These are separate gates implemented in order. Skipping any later gate means the principle DID fire but we chose not to surface it. We still write the principle hit to the move record for review-time use — silence applies to the LIVE surface only.

### Rating-band silence thresholds (initial — to tune)

```
user_rating_band     suppress when:
  <1000              principle has gate_policy=="endorsement_preferred"
                     and cp_loss < 100
  1000-1399          same as <1000
  1400-1799          principle is OP_* (opening basics) AND fired ≥2x
                     in this user's recent sessions
  1800+              suppress all OP_* principles (assume they know)
```

These thresholds will need real-corpus calibration. Ship the structure; tune the numbers.

## 5. Suppression state model

Two tiers of state:

### Hard suppression (per-game) — STATE-KEYED, not Set[principle_id]

Mohit 2026-05-18 corrected this — Set[principle_id] is too blunt. Phase 0.5 (`[[suppression-key-overhaul]]`) lands the state_key infrastructure FIRST. Phase 1.1 then uses it:

```python
# CoachGameSession augmentation (after Phase 0.5 lands):
class CoachGameSession:
    ...
    v5_state_keys_fired_this_session: Set[Tuple] = field(default_factory=set)
    v5_principles_fired_this_session: Set[str] = field(default_factory=set)
```

Suppression check on each fire:
- If principle's `suppress == "once_per_game"` → check `v5_principles_fired_this_session`.
- If principle's `suppress == "once_per_state_key"` → check `v5_state_keys_fired_this_session`.
- If `suppress == "once_per_move"` → no game-state filter (each move independent).

Reset on session start. Persists across moves within the same live game. Same mechanism as the review path now uses (single source of truth).

### Soft per-session weighting

A per-user "recent encounters" counter that decays. Used by the necessity gate (§4):

```
db.coaching_encounter_weights collection:
  user_id, principle_id, last_seen_at, fire_count, decay_score
```

Decay rate: ~20% per day. A principle fired 3 times today gets a soft cooldown; same principle fired 3 times last week is back to fresh.

Implementation note: this collection is NEW. Sized small (1 row per user per principle = ~28 rows per user max). Read on each live move, write on each fire. Fast.

### What this avoids (Mohit's catastrophic case)

> "Oh, we already taught forks 3 weeks ago so silence forever."

The decay model explicitly prevents permanent silence. Concept recurrence is the goal across weeks; per-game spam is the enemy.

## 6. Feature flag

### Schema

```
users.feature_flags = {
    "pwc_v5_teaching": {
        "enabled": bool,           # default False
        "rollout_cohort": str,     # "internal" | "early-adopter" | "general"
        "enabled_since": datetime,
    }
}
```

Plus per-game override (admin / debug):

```
coach_sessions.feature_overrides = {
    "pwc_v5_teaching": bool        # null = inherit from user flag
}
```

### Rollout sequence

1. Internal accounts only (Mohit + Parth) — validate UX on real games.
2. Early-adopter cohort (~10-30 users) — measure interruption tolerance, latency satisfaction.
3. Per-rating-band ramp — verify silence rules feel right at each level.
4. General rollout — default-on for new users; opt-in for existing.

### Per-game override

Useful for:
- A/B comparison ("classic coach" vs "V5 coach" within same user).
- Quick disable on a broken session.
- Internal debug ("regenerate this exact game with flag off").

## 7. Pre-move guardian + V5 boundary

Phase 1: independent. Pre-move guardian fires before the user submits a move; V5 teaching fires after. They don't compete on timing within the same move.

Long-term concern: both are interruption systems. Combined with realtime feedback, that's THREE interruption sources per move. Stacking them is noise. The shared "interruption governor" is a Phase 5+ concern, captured here so we don't forget.

## Implementation phase breakdown

| Step | What | Estimated effort |
|---|---|---|
| 1.1 | Add `pwc_v5_teaching` to user feature_flags schema + per-session override | Half-day |
| 1.2 | Build `v5_teaching_decision_for_live_move(move_data, user_id, session)` in a new service `services/live_v5_teaching.py` | 1-2 days |
| 1.3 | Add the call to `routes/coach_play.py` POST /api/coach/play/move (behind flag) | Half-day |
| 1.4 | Extend `coach_messages` schema with `v5_block` shape | Half-day |
| 1.5 | Add async polish task using `asyncio.create_task` | 1 day |
| 1.6 | Build `coaching_encounter_weights` collection + read/write helpers + decay logic | 1 day |
| 1.7 | Implement 3-layer silence gates (eligibility / necessity / interruption-worthiness) | 1-2 days |
| 1.8 | Material-value gate (suppress V5 when redundant with primary_text) | Half-day |
| 1.9 | Coach-move teaching: selection rules + 20% cap + intention-framed perspective | 1-2 days |
| 1.10 | Frontend: render `v5_block` underneath primary, with clickable anchor_name | 1-2 days |
| 1.11 | Async swap UI: render draft, hot-swap to polished when next poll returns | Half-day |
| 1.12 | Audit-style verification: 20 live sessions, log every v5_block surfacing decision + survey latency | Ongoing |

Total estimated effort: 2-3 weeks of focused work (1 dev). Could compress with parallel work.

## Edge cases enumerated upfront (per [[design-clean-code-leaky]])

1. **User makes move while async polish is mid-flight.** Discard the polish result; it's outdated.
2. **User leaves the session.** Async polish completes anyway; the record is updated for later /lab review consistency.
3. **Feature flag toggles mid-game.** New flag value applies on the NEXT move; in-flight moves complete with the pre-toggle behavior.
4. **Game ends.** Reset session state. Soft decay weights persist.
5. **Backend restart during async polish.** Polish task lost; record stays at "draft". Acceptable.
6. **LLM rate-limited.** Drop polish silently. Don't fail the move response.
7. **V5 detector crash.** Wrapped in try/except (existing pattern from game_decryption_v5_service). Move response returns with no `v5_block`.
8. **Coach plays a move that triggers V5 but the user hasn't moved yet.** Coach moves are tied to the user's previous move in the response cycle. V5 for coach move surfaces in the same response as the realtime "coach plays X" message.
9. **Frequency cap exceeded for coach moves.** Track cumulative coach-V5 count per session; suppress when over cap.
10. **User's first ever Play-with-Coach session (no encounter weights yet).** Necessity gate defaults to "speak" — let them see the first teaching.
11. **Same principle fires for both user AND coach on adjacent moves.** Surface once, with the higher-priority one winning.
12. **Engine analysis fails for this move (Stockfish timeout).** Skip V5 entirely; realtime path may also degrade.

## What's covered, what's NOT (per [[audit-coverage-tracks-surface]])

Covered by this design:
- The data flow between live route → V5 detection → composed response.
- The latency contract (sub-second draft, async polish).
- Suppression and silence rules.
- Coach-move teaching constraints.
- Feature flag plumbing.
- Frontend rendering shape.

NOT covered (separate work):
- Voice tone refinement for losing positions (Mohit's earlier guidance: "still lost but correct technique"). Separate doc.
- The `suppression_key` + re-arm conditions overhaul Mohit specified 2026-05-18 — that's a foundational architecture change that affects BOTH review and live. Should land BEFORE this Phase 1 ideally, OR Phase 1 ships with current once_per_game collapse and inherits the overhaul later.
- Pre-move guardian / V5 interruption governor (Phase 5+).
- Coach memory / identity wiring (out of scope).
- Real-corpus per-fire audit of the LIVE pipeline (will be its own audit script analogous to `audit_rule_of_square.py` but for the live-message decisions).

## Decisions LOCKED (Mohit 2026-05-18)

1. ✅ Suppression overhaul FIRST. Phase 0.5 (`[[suppression-key-overhaul]]`) lands before Phase 1.1.
2. ✅ Adaptive coach cap with 2/6 cooldown.
3. ✅ Structured material-value gate (compare IDs/squares, not strings).
4. ✅ Guarded async polish (same principle/target, no contradiction, ≤1.4× length, ≤3s).

## SHIP STATUS as of 2026-05-19

| Phase | What | Status |
|---|---|---|
| 0.5 | State-keyed suppression overhaul | ✅ |
| 1.1 | Deterministic V5 block behind feature flag | ✅ |
| 1.2 | Structured material-value gate | ✅ |
| 1.3 | Adaptive coach-move teaching with 2/6 cooldown | ✅ |
| 1.4 | Guarded async LLM polish | ✅ |
| 1.6 | `coaching_encounter_weights` collection + decay logic | ✅ (commit 8aa4bcff, 2026-05-19) |
| 1.7 | Three-layer silence (necessity layer) | ✅ (commit 8aa4bcff, 2026-05-19) |
| 1.11 | Frontend hot-swap UI | ⚠️ works via polling, no animation — post-playtest refinement |
| 1.12 | Live-session audit script | ⏳ deferred — Mohit's playtest IS the audit signal |

**Ready for live playtest 2026-05-19.** All ship-blockers cleared. Pull working-code + restart backend + flip `pwc_v5_teaching.enabled=True` on the test user. Frontend already renders the v5_teaching block (CoachPlaySidebar.jsx).

## Related memories

- `[[play-with-coach-teaching-integration]]` — the parent deep plan; this is its Phase 1 detail.
- `[[clickable-rule-names]]` — the `v5_block.principle_id` field IS the click target for the rule-info surface.
- `[[named-rule-real-game-examples]]` — once Phase 1 ships, live play becomes a rich source of real-game examples for the rule-info surface.
- `[[teaching-not-reading]]` — the V5 block must obey voice rules; primary realtime path already does.
- `[[sub1500-memory-anchors]]` — Phase 1's whole point.
- `[[no-yes-man]]` — when I implement, FEN-verify each surfacing decision against actual user-visible output.
- `[[v5-caption-rewrite-no-patches]]` — applies but doesn't block: this is integration into a new surface, not a V5 patch.
- `[[design-clean-code-leaky]]` — edge cases enumerated upfront (§9), audit coverage flagged for separate work.
