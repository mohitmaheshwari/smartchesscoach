# Piece-Safety Subtype + Severity — Scope

**Author:** Claude (working with Mohit)
**Status:** DRAFT — pending signoff
**Date:** 2026-07-02

---

## The problem this solves

The coach currently tells every user with a lot of `piece_safety` events the
same story: "you leave pieces undefended, scan before moving." That's
correct for a 1200 who literally drops pieces — and completely wrong for a
1950 whose "piece_safety" events are actually calculation errors inside
forcing sequences.

Evidence I pulled on Parth (1950):

- 127 `piece_safety` events
- 40% **simple hangs** (median 440cp, quiet moves, immediate captures)
- 9% **tactical sequence losses** (his own forcing move miscalculated)
- 3% **ignored opponent threats**
- 47% **small slips** (<200cp — background noise)

So even at 1950, Parth genuinely hangs pieces in 40% of cases. Rating
alone doesn't tell us that. The fix isn't rating-band templates — it's
per-event evidence + a narrative built from that user's actual histogram.

Mohit's principle (verbatim from this conversation):

> "you can't really just configure it in json templates, you need to
> learn it by analysing games, i mean i can never take anything for
> granted"

> "somebody just probably played his first game on chess.com but is an
> international master, doing some ladder up practise or something"

Rating is a signal. Evidence is the anchor.

---

## What we're building

Every `piece_safety` observation gets **two new fields** derived from
board evidence:

1. `subtype` — what KIND of piece_safety this was
2. `severity` — how bad it was in context (not just cp_loss)

Then everything downstream (picker, coach cards, emails) uses that
per-user histogram to speak to the individual, not the tier.

---

## Taxonomy — `piece_safety` subtypes

| subtype | derivation rule | base severity |
|---|---|---|
| `simple_hang` | user's move was NOT forcing/capture, opponent's previous move did NOT create a threat, cp_loss ≥ 200, opponent's next move captured the just-moved piece | **critical** |
| `threat_ignored` | opponent's previous move created a threat (via `opponent_previous.created_threat`), user did not respond, cp_loss ≥ 200 | **moderate** |
| `tactical_seq_loss` | user's move was forcing (`was_forcing=True` or `was_capture=True`), cp_loss ≥ 150 | **moderate** |
| `small_slip` | cp_loss < 200 (anything not caught above) | **minor** |

Order of evaluation: threat_ignored → tactical_seq_loss → simple_hang →
small_slip (first match wins; small_slip is the catch-all).

---

## Severity — base + contextual promotion

Per Mohit's guidance: **do not use raw cp_loss as a threshold.** Endgames
+ sacrifices + already-lost positions distort raw cp. Instead:

```
severity = base_severity(subtype)

Promote one level (minor → moderate → critical) if ANY of:
  A. execution_quality == "blunder"  (engine label)
  B. Move loses significant material immediately
     (opponent's next move captures the piece, and material_delta ≤ -300)
  C. cp_loss ≥ 400 AND eval_before ≥ -300
     (very bad move, and the position wasn't already hopeless)
```

Rule C is the "not already hopeless" guard — a 10425cp loss when you're
already down a queen isn't instructionally meaningful.

Cap at `critical` (no promotion above it).

---

## Rating confidence (per Mohit's thresholds)

```
game_count < 10   → confidence = "unreliable"  (ignore rating entirely, evidence-only)
game_count 10-25  → confidence = "low"         (rating prior dampened 0.5×)
game_count > 25   → confidence = "high"        (rating prior at full 1.0×)
```

This handles the "IM on a new chess.com account" case: even if his
rating shows 900, with <10 games we don't trust it and let the evidence
speak.

---

## Picker changes

Old scoring:
```
score = (event_count / total_moves × 100) × impact_weight[band]
```

New scoring:
```
score = Σ over events of that pattern:
   severity_weight[event.severity] × rating_prior[band] × confidence_multiplier

where severity_weight = { critical: 3.0, moderate: 1.5, minor: 0.5 }
```

Effect: 40 critical simple_hangs beats 100 minor small_slips
(40×3.0=120 vs 100×0.5=50). And 40 simple_hangs at any rating gets
attention — even for a 1950, because the evidence is there.

---

## Narrative generation (replaces `DIAGNOSTIC_NARRATIVES` templates)

The templated `DIAGNOSTIC_NARRATIVES` dict gets deleted. Instead, at
pick time, generate the narrative from the user's own histogram:

**Template (structural, not content):**
```
{pattern_name} is your top pattern ({total} events across {games} games).

- {pct_critical}% are {dominant_critical_subtype} — {subtype_1liner}
- {pct_moderate}% are {second_subtype} — {subtype_1liner}
- Rest are small slips (<200cp).

{tier-aware closing}
```

For Parth this generates:
> "Piece safety is your top pattern (127 events across 30 games). 40% are
> simple hangs — literal drops in quiet positions. 9% are tactical
> miscalculations inside forcing sequences. Rest are small slips. Even
> at 1950 you're dropping pieces in quiet positions — that's a scanning
> gap, not a calculation gap."

For a 900 rated user with the same distribution:
> "Piece safety is your top pattern (127 events across 30 games). 40%
> are simple hangs. Rest are small slips. Right now, the biggest thing
> is: before every move, ask 'can this be taken?'"

Same DATA drives both. Different phrasing per band, but the phrasing
comes from the histogram not from a hardcoded dict.

---

## Where the narrative surfaces

Once we have a good `piece_safety` story, wire it into:

1. **Picker output** (`user_active_focus.coaching_narrative`) — done at
   assignment time.
2. **Focus card** (frontend `FocusCard.jsx`) — reads the narrative
   directly.
3. **Coach home intelligence** (`home_intelligence_service.py`) — the
   "coach message" text.
4. **Re-engagement emails** (`send_*_reengagement.py`) — the body of the
   email uses the narrative + a link to the moments page.

All four surfaces read the same field on `user_active_focus`.

---

## Data changes

**`move_observations` collection — new fields:**
- `subtype` (string, nullable) — only populated when `missed_pattern != null`
- `severity` ("minor" | "moderate" | "critical", nullable) — same rule

**Schema version bump:** SCHEMA_VERSION = 4 in
`move_observation_deriver.py`. Backfill script re-derives on any doc
where `schema_version < 4`.

**`user_active_focus` — new fields:**
- `subtype_histogram` — `{"simple_hang": {"count": 51, "severity": "critical"}, ...}`
- `rating_confidence` — "unreliable" | "low" | "high"

---

## Acceptance criteria

Test on **Parth (1950), Mohit (1270), and 3 other users** covering
different rating bands. Each of them should get a narrative that:

1. States the top subtype + percentage
2. Names the actual number of events + games
3. Sounds like it was written FOR THAT USER, not templated
4. Ends with a concrete instruction that matches THEIR dominant subtype

Success: Mohit reads each of the 5 narratives and says "yeah, that's
actually what's going on with them."

Failure: two users get essentially the same narrative → we're back to
templating.

---

## Non-goals (for this pass)

- The other 8 cognitive_gap tags (king_safety, missed_tactic, etc.) —
  extend AFTER piece_safety is validated end-to-end. Same architecture,
  different derivation rules.
- Move-quality-vs-rating mismatch as a confidence signal — game_count
  only for v1. If someone truly is an IM on a new account, <10 games
  will already flag them as "unreliable" and we'll rely on evidence.
- Fixing the duplicate-observations bug (Rxc3 appearing twice). Separate
  ticket. Doesn't block this work — dupes inflate counts uniformly and
  the histogram remains proportionally correct.

---

## Rollout order

1. Deriver: add subtype + severity for piece_safety (~1 hr)
2. Backfill script re-derives all piece_safety observations (~10 min run)
3. Picker: severity-weighted scoring + rating confidence (~30 min)
4. Narrative generator function (~1 hr)
5. Wire to `user_active_focus`, `FocusCard`, `home_intelligence`,
   emails (~2 hr)
6. Reassign focuses for all 46 active users (~5 min run)
7. Validate on 5 users, iterate on narrative wording (~1 hr)
8. Commit + push + deploy signal for prod server (~15 min)

Total: ~half a day of build, then validation.

---

## Sign-off checkbox

- [ ] Mohit reviewed and approved
