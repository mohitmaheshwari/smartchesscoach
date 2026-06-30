# Primary Weakness Picker — Scope

**Status:** Drafted 2026-06-30. Awaiting Mohit's signoff before code.
**Related:** [move_observations_scope.md](move_observations_scope.md), [email_page_contract.md](email_page_contract.md).
**Parent theme:** Theme 3 — Curriculum Engine (the "stop being a stat dashboard, start being a coach" track).

---

## TL;DR

Today, every user with analyzed games gets a list of ~5-9 weaknesses surfaced across the app — top_weaknesses on the profile, decay-weighted picks on the Lab page, blunder counts on HomePage cards. **No one tells the user which one to fix FIRST.** A real chess coach picks ONE thing for a student to work on and locks them on it until it moves.

The Primary Weakness Picker does that. Per user, we pick one weakness, **lock it for 2 weeks**, surface it as "your focus for the next 14 days" across every coaching surface, and measure whether it actually moved by the end of the lock. If it did → celebrate + unlock + pick the next one. If it didn't → escalate (deeper session, different framing).

This is the smallest unit of structured coaching. Everything else in Theme 3 (curriculum sequencing, habit framework, spaced repetition, measurement loop) hangs off it.

---

## Why now

Memory: *"subtractive vs additive at small N — at 50 users additive wins."* Right, at the platform level. **But within a single user's coaching experience, additive is paralyzing.** Showing Mohit his 9 weaknesses produces decision fatigue. Showing him "for the next 14 days: hanging pieces — that's it" produces action.

Three things make NOW the right time to ship this:

1. **The move_observations layer is shipping today.** Once backfill finishes (in progress), per-user weakness signals are 10× richer than what `top_weaknesses` gave us. The picker has real data to choose from.
2. **The "3 Moments" page is ready** — gives us a credible destination when we say "your focus this week is X."
3. **The re-engagement emails are running** — we've started the coaching conversation. Without a focus to anchor them, follow-up emails have nowhere to go.

---

## What it ships

A new collection + a small UI surface:

### Data model

```
Collection: user_active_focus
{
  "_id": ObjectId,
  "user_id": "user_xxx",
  "status": "active" | "completed" | "escalated" | "abandoned",
  "topic_key": "piece_safety",       // matches moments_topic_registry keys
  "started_at": ISODate,
  "locked_until": ISODate,            // started_at + 14 days by default
  "baseline_metric": {
    "name": "piece_safety_per_game",
    "value": 1.53,                    // per-game rate at lock time
    "n_games_in_baseline": 30
  },
  "current_metric": {                 // recomputed weekly, displayed on cards
    "value": 1.38,
    "delta_pct": -10,                 // negative = improving
    "n_games_since_start": 12,
    "last_computed": ISODate
  },
  "completion_check_at": ISODate,     // first check at locked_until
  "resolution": "improved" | "stuck" | "regressed" | null,  // populated on check
  "next_action": null | "celebrate" | "escalate" | "extend",
  "created_at": ISODate,
  "updated_at": ISODate
}
```

One active focus per user. Historic focuses kept (for the user's improvement timeline).

### Picker logic (the algorithm)

When a user has no active focus (or completed/abandoned their last one), pick the next one via:

```python
def pick_next_focus(user_id):
    # 1) Aggregate move_observations for last 30 games
    sigs = aggregate_user_signals(observations_last_30_games(user_id))

    # 2) Build candidate list ranked by impact-weighted occurrence
    candidates = []
    for pattern, count in sigs["missed_pattern_counts"].items():
        per_game = count / sigs["total_user_moves"] / 25  # normalize
        impact = IMPACT_TABLE[pattern]  # see below — 0..1 weight
        candidates.append({
            "topic": pattern_to_topic(pattern),
            "score": per_game * impact,
            "evidence_count": count,
        })

    # 3) Also surface positive-signal-gap candidates (things they DON'T do)
    if sigs.get("threat_response_rate", 1.0) < 0.7:
        candidates.append({
            "topic": "threat_awareness",
            "score": (1 - sigs["threat_response_rate"]) * 0.8,
            "evidence_count": sigs["ignored_opponent_threat"],
        })
    if sigs.get("blunder_punish_rate", 1.0) < 0.5:
        candidates.append({
            "topic": "punish_blunders",
            "score": (1 - sigs["blunder_punish_rate"]) * 0.6,
            "evidence_count": sigs["missed_opponent_blunder"],
        })

    # 4) Exclude topics they just completed (cooldown)
    candidates = [c for c in candidates if not in_cooldown(user_id, c["topic"])]

    # 5) Top candidate wins
    return max(candidates, key=lambda c: c["score"])
```

**Impact weights** (the editorial layer — we as designers say "fixing X has higher impact than fixing Y at the same frequency"):

| Pattern | Impact weight | Reason |
|---|---:|---|
| `piece_safety` (one-move blunders) | 1.0 | Highest impact — every hung piece costs ~3+ pawns |
| `ignoring_king_safety_threats` | 0.9 | Often game-ending |
| `fork_misses` | 0.7 | Multiple-piece value |
| `discovered_attack_misses` | 0.7 | Same |
| `removal_of_defender_misses` | 0.6 | High but harder to teach |
| `neglecting_development` | 0.5 | Cumulative; multi-game habit issue |
| `poor_piece_activity` | 0.5 | Same |
| `pawn_structure_damage` | 0.4 | Long-term, harder to feel improvement |
| `king_activity_neglect` | 0.4 | Endgame, lower frequency |

The weights live in a single `IMPACT_TABLE` constant in `services/primary_weakness_picker.py` — easy to tune.

### The lock (the discipline that makes this work)

For 14 days after a focus is picked:
- **All coaching surfaces filter to this one topic** — Lab page Coach's Pick shows games with this pattern, HomePage card calls it out, weekly email digest only references it
- **Other patterns fade** but aren't hidden — user can click "show all weaknesses" to see them. Default view = one thing.
- **Lock can be released early** only if user explicitly says "I'm done with this" or has 0 occurrences in a 7-day rolling window with ≥10 games played.

### The measurement loop (the part that makes it feel like a coach)

At `locked_until` (default day 14), automatic check:

```python
def check_focus_outcome(focus):
    new_metric = compute_metric_since(focus.user_id,
                                       focus.topic_key,
                                       since=focus.started_at)
    delta = (new_metric.value - focus.baseline_metric.value) / focus.baseline_metric.value
    if delta <= -0.20:       # improved by ≥20%
        resolution = "improved"
        action = "celebrate"
    elif delta >= 0.10:      # got worse by ≥10%
        resolution = "regressed"
        action = "escalate"
    else:
        resolution = "stuck"
        action = "extend"     # give it 1 more week, then escalate
    return resolution, action
```

Actions:
- **celebrate** — surface a "you reduced piece-blunders by 30% in 2 weeks. Here's what's next." card + email
- **extend** — auto-extend lock by 7 days, send "still working on it, let's give it another week" message
- **escalate** — schedule a Play-with-Coach session focused on this pattern, send "let's tackle this together" email

### UI surfaces (what changes for the user)

| Surface | Today | With this | Effort |
|---|---|---|---|
| **HomePage** | List of cards including ~5 weaknesses | One BIG card "Your focus: piece safety — 12 days left" + small "what's working" + small "other patterns (hidden)" | ~1 day |
| **Lab page Coach's Pick** | Decay-weighted last game | Filter to games featuring active focus pattern, fallback to existing logic | ~half day |
| **Re-engagement emails** | One per user, generic recent observations | Subject + body anchored to user's active focus | ~half day |
| **Settings / Profile** | (none) | "Change my focus" button (releases lock + re-picks) | ~1 hr |
| **Email digest (weekly)** | (doesn't exist yet) | Auto-sent Monday: progress on focus, what to do this week | ~1 day (separate scope) |

---

## What it does NOT do (v1)

1. **No multi-focus simultaneously.** One focus per user. Period. We can revisit if a user complains they want to work on 2 things — most won't.
2. **No per-rating-band picker tuning.** Same algorithm for 700 and 1500 (impact weights stay the same). Future: weights might vary by rating band, but not v1.
3. **No automatic Play-with-Coach scheduling on escalation.** v1 just sends an email/notification suggesting it. Auto-scheduling is a separate scope.
4. **No A/B testing of focus picks** in v1. Ship the deterministic algorithm. Measure improvement rates. Iterate weights based on data.
5. **No "earn back time" lock breaking.** Once locked, user can't shorten it unilaterally. They CAN reset (which counts as abandoning current focus + picking new).

---

## Success criteria

Ship if:

1. ✅ Every user with ≥10 analyzed games gets an active focus assigned by Monday after this ships.
2. ✅ Focus appears on HomePage as the largest card.
3. ✅ At day 14, ≥50% of active focuses get a resolution (improved/stuck/regressed) — not just "no data."
4. ✅ **Among focused users, the per-game rate of their focus pattern drops by ≥15% in the first 28 days** (the actual coaching outcome we care about). If this fails, the picker isn't picking impactful patterns — adjust weights.

---

## Implementation plan (phases)

### Phase 0 — Signoff (this doc)
You read, ask questions, sign off or push back on:
- The picker algorithm
- The impact weight table
- The 14-day lock duration
- The success criteria thresholds (especially #4)

### Phase 1 — Picker service + collection (1 day)
- `services/primary_weakness_picker.py` with `pick_next_focus()`, `check_focus_outcome()`, helpers
- New `user_active_focus` collection + 2 indexes
- Cron job (using existing cron infrastructure) that picks focuses for all users without one, weekly

### Phase 2 — HomePage card (1 day)
- Big card replacing the current weakness-list block
- Days remaining countdown
- Current_metric.delta_pct progress indicator
- "Show all weaknesses" expander for the others

### Phase 3 — Email integration (half day)
- Email generator pulls active focus, anchors subject + body to it
- Re-engagement campaign next-batch uses this

### Phase 4 — Lab page filter integration (half day)
- Coach's Pick prefers games featuring the focus pattern when available

### Phase 5 — Outcome check + escalation (half day)
- Cron at lock expiry, sends celebrate/extend/escalate email
- Surfaces resolution on HomePage

### Phase 6 — "Change my focus" UI (1 hr)
- Settings button to release lock + re-pick

**Total: ~5 days.** Shippable end-to-end.

---

## Risks + open questions

| Risk | Mitigation |
|---|---|
| Picker fixates on noise patterns (e.g. user makes 2 "pawn_structure" mistakes and gets locked into a 2-week pawn focus) | Minimum evidence threshold — require ≥3 occurrences in last 30 games to pick a pattern. Otherwise default to `piece_safety` (most impactful). |
| 14 days is too long for fast players who play 30 games/week | Add adaptive lock: 14 days OR 50 games played, whichever comes first. Whichever flushes first releases. |
| User feels "trapped" by the focus | The "Change my focus" escape valve handles this. Default lock is firm, escape is one click. |
| Picker picks the same thing repeatedly because user doesn't improve | After 2 stuck/regressed resolutions on the same topic, force-rotate to the next-highest-impact candidate, mark it as "deferred." |
| Picker has no signal for new users (<10 games) | New users get a "diagnostic" focus instead — see [diagnostic_service.py](../backend/services/diagnostic_service.py). Already exists. Just connect it. |

### Open questions for Mohit

1. **Lock duration.** I picked 14 days. Too long? Too short? Best practice from real coaching literature is "2-4 weeks per skill habit" so 14 days is the floor. Want to try 21 days?
2. **Improvement threshold.** I picked −20% rate improvement = "improved." Too strict? Real chess improvement is slow — 20% over 14 days is aggressive. Open to −10%.
3. **Impact weight table.** I drafted weights based on chess intuition. Want your editorial input — are these the priorities you'd assign as a coach?
4. **Escalation action.** I default to "send email suggesting Play-with-Coach session." Do you want me to also auto-create a Play-with-Coach session pre-loaded with the focus pattern? That's more work but more powerful.
5. **New-user path.** Should brand-new users see a focus immediately (assigned diagnostically) or only after their first 10 games are analyzed? Current draft: 10-game minimum.

---

## What you're signing off on

1. The picker algorithm + impact weights (or your revisions)
2. The data model + lock semantics (14 days, escape valve, escalation behavior)
3. The 4 success criteria (especially #4 — the 15% improvement target)
4. The 5-day implementation plan
