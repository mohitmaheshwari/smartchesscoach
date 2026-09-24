# Promotion packet — `gap:king_safety:ignored_king_attack`

**Requested grade:** SHADOW → PLAN
**Prepared:** 2026-09-24
**Decision:** Mohit's. Not taken.

The caption-surface lock requires a reviewed packet before any id reaches
that surface, and this project's rule is that no model approves its own
claims. So this document argues the case; it does not close it. The grade in
`detector_quality.py` stays SHADOW until signed.

---

## What promoting it changes

One thing, and it is the thing the whole coaching loop is stuck on.

`topic_can_be_planned(topic)` reads `gap:{topic}:` ids at PLAN grade and
nothing else. Exactly one id in the whole authorization table qualifies, so
the picker has one topic it is allowed to choose:

```
piece_safety         True   ('destination_safety_exact',)
king_safety          False  ()
opening_knowledge    False  ()
missed_tactic        False  ()
endgame_technique    False  ()      ... and five more, all False
```

**53 of 86 users hold the same focus.** Not because their games look alike —
because there is one authorized id. Eleven more focuses were closed outright
with `resolution=detector_not_authorized_for_plan`. The coach repeats itself
because it is allowed one subject.

Promoting this id makes `king_safety` the second plannable topic in the
product.

## Why this id rather than another

**It is the largest gap.** 20,150 mistakes of ≥100cp carrying a
`cognitive_gap`, across 46 users:

| cognitive gap | mistakes | users | has a `gap:` id |
|---|---|---|---|
| **king_safety** | **5,794** | **46** | yes, SHADOW |
| piece_safety | 5,660 | 45 | yes, PLAN |
| missed_tactic | 4,323 | 44 | none existed |
| opening_knowledge | 2,242 | 45 | yes, SHADOW |
| endgame_technique | 1,853 | 39 | none existed |

king_safety is bigger than the one topic everybody is stuck on.

**It has evidence, and the alternatives do not.** The other two SHADOW `gap:`
ids cannot accumulate any:

```
allowed_mate_exact             0 fires    0 users
left_book_for_a_worse_move     2 fires    2 users
trapped_piece_exact            0 fires    0 users
ignored_king_attack        4,028 fires   57 users
-- positive control, same field, same query --
destination_safety_exact   4,970 fires   57 users
simple_hang                2,332 fires   54 users
```

`detect_allowed_mate` has exactly one caller: the admin review route. It never
runs during analysis, so it can never write an observation. Promoting it would
hand 46 users a focus backed by nothing.

`ignored_king_attack` reaches **57 users — every user in the collection**, more
than the PLAN id it would join.

## Both halves of the sentence are now true

The user is told: *"your opponent had pieces near your king and you didn't
defend."* That is two claims, and before today the rule tested one.

**Claim 1 — pressure exists.** 3+ squares within distance 2 of the king
attacked by the opponent. Holds on **0 of 768** fires below threshold, against
a **49.9%** base rate over 27,618 positions. The test discriminates; it is not
passing everything.

**Claim 2 — "you didn't defend."** The rule never tested this. It required
only that the move was quiet and lost 150cp. Measured over 900 replayed games:

| change in attacked squares around the king | share |
|---|---|
| −8 to −1 (**player reduced the pressure**) | **18.3%** |
| 0 | 71.6% |
| +1 or more | 10.1% |

On 172 of 940 fires the player **defended their own king** — one of them by
eight squares — and was told they ignored the attack. Same shape as the
`DEF_WALK_KING` bug: premise tested, accusation not.

Gated in this change: the fire is suppressed when the move reduces pressure,
measured around where the king **actually ends up**, since walking the king
off a pressured square is one of the commonest ways to answer an attack.
After the gate: **940 → 768 fires, claim 2 false on 0%.**

## Limitations, stated rather than buried

- Pressure is counted as attacked squares near the king. That is a proxy for
  danger, not danger. One well-placed piece can be worse than three loose ones.
- `board.attackers()` is pseudo-legal, so a pinned attacker still counts.
  Defensible for king safety — a pinned piece still controls squares the king
  wants — but it is a choice, not a measurement.
- The detector gates on `cp_loss >= 150`, so **its agreement with the engine is
  circular**. Do not cite that as evidence of quality. The case rests on the
  two board claims above and nothing else.
- It says the attack was ignored. It never says why it was missed.
- Sample is 46–57 users against ~86 in prod. Treat the percentages as shape,
  not census.

## What is NOT being asked for

The four tactical motifs (`missed_pin` 1,278/50, `missed_fork` 759/49,
`missed_skewer` 529/43, `missed_discovered_attack` 399/43) are registered at
SHADOW in the same change. They are **not** proposed for promotion: none has
been through the per-FEN caption check that caught five principles stating
things the board did not support on 2026-09-24. Volume is not a promotion case.

## If signed

Add `gap:king_safety:ignored_king_attack` to the allowlist in
`tests/test_simple_hang_caption_authorization.py`, and update
`tests/test_detector_quality_gate.py::test_plan_sanitizer_keeps_evidence_but_hides_shadow_gap`,
which currently asserts that no king_safety pattern survives the sanitizer —
an assertion that encodes the one-topic world this change ends.
