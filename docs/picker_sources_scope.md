# Picker sources — scope

Status: **Section 0 only. Blocked pending Mohit's decision.**
Sections 1–7 are deliberately unwritten: the audit below invalidated the
feature that was about to be scoped.

---

## 0. Existing surfaces audit

### The feature that was proposed

"Widen `primary_weakness_picker` so it reads the opening and motif data,
not just `move_observations` — so 53 users stop sharing one focus label."

### What already exists

**`services/primary_weakness_picker.py`** (1,280 lines) builds a scored
candidate list and assigns one focus into `user_active_focus`.

- Candidates come from `signals["missed_pattern_counts"]`, read from
  `move_observations` (line 512).
- `time_management` is already added as a **synthetic topic** (line ~686)
  — proof that a non-`missed_pattern` dimension can be scored here without
  new architecture. Adding openings or motifs would follow this precedent.
- `services/primary_strength_picker.py` writes strengths into the same
  collection.

So the proposed change is an EXTEND, and a cheap one. Two new synthetic
topic families, ~100 lines, no new collection.

### Why that would have delivered nothing

Line 786, immediately after the ranking:

```python
plannable, not_plannable = [], []
for c in candidates:
    (plannable if topic_can_be_planned(c["topic"]) else not_plannable).append(c)
```

`topic_can_be_planned` (`services/detector_quality.py:976`) returns true
only for a pattern with a **PLAN-graded** detector behind it. Measured in
the live container:

```
enforcement_enabled: True
grades: {shadow: 46, caption: 7, plan: 1, disabled: 5}

PLAN-graded quality ids: 1
    gap:piece_safety:destination_safety_exact
```

**One.** `piece_safety` is the only topic that can currently be assigned.
Every other candidate — however strong the evidence — is filed under
`not_plannable` and discarded.

### The overlap is total

Any new source added to the picker produces topics with no PLAN-graded
detector, so every one of them lands in `not_plannable` on the very next
line. The opening and motif wiring would run, score correctly, log its
candidates, and change nothing a user sees.

### Evidence this is the live cause, not a theory

Focus assignments by topic, all users:

```
topic                  n    first assigned        last assigned
piece_safety         195    2026-07-01            2026-09-17     <- still running
time_management       19    2026-07-02            2026-07-02     <- dead 3 months
threat_awareness      10    2026-07-02            2026-09-16
king_safety           10    2026-07-02            2026-07-02     <- dead 3 months
punish_blunders        1    2026-08-14            2026-08-14
missed_tactic          1    2026-07-21            2026-07-21
tactical_oversight     1    2026-07-21            2026-07-21
```

Everything except `piece_safety` stopped being assignable. And of the 9
focus documents written since `not_plannable` began being recorded,
**9 of 9** had a refused runner-up:

```
refused topic          times  users  best score
threat_awareness           9      9        52.2
punish_blunders            1      1        45.6
```

One real user on 2026-09-17 scored `threat_awareness` at **52.17 across 22
events** and was assigned `piece_safety` instead.

The picker is working. The ranking is working. The evidence is there.
The gate throws it away.

### Decision: the scope must change

Not EXTEND the picker's sources. The real scope is **detector promotion** —
moving graded-`shadow` detectors onto the plan surface so more than one
topic is assignable.

`_AUTHORIZATIONS` in `services/detector_quality.py` is the single control,
and **no model may edit it**. Promotion runs through the packet process
(`scripts/build_*_promotion_packet.py`, reviewed docs under `docs/`), which
ends in a human approval — the route `destination_safety_exact` took on
2026-09-01 to become the one PLAN grade that exists.

### Paths open to Mohit

1. **Promote the next detector(s) by packet.** Real fix. I build the
   packets and the evidence; Mohit grades. Priority should be set by
   fires-per-game, not by review convenience.
2. **Narrow the enforcement scope** so the gate governs *captions* (claims
   made to the player) but not *focus selection* (what we choose to work
   on). Argument: choosing to work on threat_awareness makes no unverified
   claim. Risk: the downstream plan surfaces still have nothing authorized
   to say, so it may just move the silence.
3. **Leave the gate; accept one topic for now** and spend the effort on
   surfaces that don't route through the picker at all — the opening
   breadth card and the motif queue can read their data directly.

Not on the list: disabling `DETECTOR_QUALITY_GATE_ENFORCED`. It fails
closed by design and turning it off ships 46 shadow detectors to players.

**AWAITING MOHIT'S DECISION on path 1 / 2 / 3 before sections 1–7 are
written and before any code.**
