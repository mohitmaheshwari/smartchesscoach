---
name: audit-captions-for-why
description: Scan stored V5 captions across a sample of games to find ones that lack a WHY — captions that just say "X is mistake, Y better" without explaining why the move fails or what the user should learn. Returns a fail-rate, the worst offenders grouped by pattern, and concrete examples ready to paste into CAPTION_BACKLOG. Trigger when the user asks "are our captions actually teaching" / "how many are terse" / "audit captions for teaching value" or types /audit-captions-for-why.
---

# Audit captions for teaching value (does each caption have a WHY)

Built 2026-06-03 after `fb_ec0098264c8e` ("Qe2 is a mistake. O-O was better." — user replied "why??"). The caption was technically right (engine eval matches) but provides zero teaching value. A user who sees this caption learns nothing. This skill measures how widespread the problem is and surfaces the worst offenders.

## What "has a WHY" means (the definition)

A caption has a WHY if at least one of the following is true:

1. **Concrete consequence** — names a square/piece/move that explains what happens (e.g. *"Qxd4 wins the pawn"*, *"...hits Bf4"*, *"f7 falls next move"*). Mention beyond the played SAN itself.
2. **Causal connector** — uses "because", "since", "so that", "—" with explanation following, or "loses to {move}", "walks into {move}", "leaves {square} hanging".
3. **Universal principle ending** — closes with a transferable rule (e.g. *"Before moving a defender, count what depends on it"*, *"Knights need outposts in front of pawn chains"*). This is the [feedback_caption_keep_explicit_principle_ending.md] requirement.

A caption fails the WHY check if it has none of those — the canonical failure shape is:

> "{move} is a {severity}. {best} was better."

Five words of zero teaching. The user sees what they did wrong (the verdict) but learns nothing about why or how to avoid it next time.

## When to invoke

- User asks "how many of our captions actually teach" / "are captions terse" / "audit captions for why"
- User types `/audit-captions-for-why`
- After shipping a caption-framework change, to measure improvement
- Periodically (every N weeks) to track drift

Do NOT invoke for:
- Auditing ONE specific caption against a position — that's `/audit-flagged-caption`.
- Voice/jargon audits — that's `/check-voice`.

## Required input

- Sample size N (default 500 games — the Mohit-baseline). Larger = more confidence, more docker exec time.
- Optional severity filter (default: `mistake` + `blunder` only — `good`/`context`/`inaccuracy` captions can legitimately be brief).

## Steps

### 1. Run the programmatic checker

The actual work is a Python script in the container: [backend/scripts/audit_captions_for_why.py](../../backend/scripts/audit_captions_for_why.py).

```bash
MSYS_NO_PATHCONV=1 docker exec chess-coach-backend python \
  /app/backend/scripts/audit_captions_for_why.py --n 500
```

The script samples N random games with `decryption_v5_data` populated, walks every move where `severity ∈ {mistake, blunder}`, and scores the caption against the three WHY heuristics:

- `H1_has_concrete_consequence` — regex for "wins/loses/hangs/falls/threatens/attacks/walks into/hits/grabs/exposes/leaves … {square or piece}".
- `H2_has_causal_connector` — checks for "because", "since", "so that", "—", "loses to", "walks into", "leaves … hanging".
- `H3_has_principle_ending` — heuristic: last sentence contains a generalization verb ("always", "never", "before … check", "when X, do Y", "remember", "this is why", "count what", "look for").

A caption **passes** if any of H1/H2/H3 fires. A caption **fails** if none fire (this is the "X is mistake, Y better" shape).

### 2. Report shape

The script outputs:

```
TOTAL captions scanned: <N>
  passes WHY:          <count> (<pct>%)
  fails WHY:           <count> (<pct>%)

Fail rate by severity:
  blunder:  <count>/<total> = <pct>%
  mistake:  <count>/<total> = <pct>%

Top failing caption shapes (count):
  "X is a mistake. Y was better."          : <count>
  "X is a blunder. Y was better."          : <count>
  ... (template-extracted)

Sample failing captions (10 randoms):
  game={gid}  m{n}  {san}  sev={sev}  cp_loss={cpl}
    > "{caption_text}"
  ...
```

### 3. Translate findings into action

Based on the fail rate + top shapes, decide:

- **<10% fail rate**: pipeline is healthy. No action.
- **10-25% fail rate**: identify the top 2-3 shapes; check whether they come from one rendering path (e.g. all `concept_id=narrative` from a specific template). Localized fix possible.
- **>25% fail rate**: systemic. Likely the central caption pipeline ([backend/services/caption_pipeline.py](../../backend/services/caption_pipeline.py)) is falling through to a thin terse template too often. Needs a backlog entry against CAPTION_BACKLOG to design a "minimum-why" floor — if neither failure-mode nor alternative-promotion fires, the caption should add a generic teaching principle from a small bank rather than dump the "{move} is a {severity}. {best} was better." shell.

### 4. Output deliverable

A short report:
- One-line headline (e.g. "37% of mistake/blunder captions lack a WHY across 500 games").
- The breakdown table.
- The top 3 caption shapes responsible.
- One concrete recommendation (file backlog item, tighten template, or "ship now").

## What NOT to do

- Don't run on more than 1500 games at once. The aggregation is fast but Mongo cursor + per-caption regex takes a few minutes for 1500. Above that, batch in chunks.
- Don't treat the H1/H2/H3 heuristics as ground truth — they're a coarse filter. A caption can pass H2 with a "—" that's just punctuation, not explanation. Use the sampled failures (Step 2 output) to spot-check the false-pass rate.
- Don't propose specific caption rewrites here — that's `/rewrite-for-1200`'s job. This skill measures, doesn't fix.
- Don't audit `good`/`context`/`inaccuracy` severity. They're allowed to be brief. The teaching obligation is on `mistake`/`blunder`.

## Notes

- This skill IS programmatic — the actual rules live in [backend/scripts/audit_captions_for_why.py](../../backend/scripts/audit_captions_for_why.py). When the WHY definition evolves, edit that script, NOT this file.
- Pair with [/triage-feedback]: when N user-flagged "why??" complaints arrive, run this skill to see the systemic rate. If a flagged caption matches a top failure shape, file under CAPTION_BACKLOG.
- The 500-game baseline run (2026-06-03) is the first measurement. Re-run after any central-pipeline change to track movement.
