# Fork Confidence Formula

Authored design doc. **Source of truth for fork detection scoring.** Any
implementation that scores a fork's confidence must implement this formula
exactly. No drift, no "looks similar."

## Output shape

```python
{
  "detected": bool,
  "confidence": float,   # 0.0..1.0
  "tier": "HIGH" | "MEDIUM" | "LOW",
  "evidence": {
    "target_count": int,
    "high_value_targets": int,
    "forker_safe": bool,
    "net_material_gain": int,    # in pawn units
    "escape_available": bool,
    "counterplay_risk": "low" | "medium" | "high",
  }
}
```

## Core philosophy

A fork is only **real** if:
1. It creates multiple threats
2. At least one threat is valuable
3. The forking piece is not immediately lost for nothing
4. The sequence is materially or positionally meaningful

Everything else is noise.

## Step 1 — Base detection gate (binary, before scoring)

Reject immediately if:
- `targets < 2`
- Both targets are low value (pawn/pawn, or two weak minor squares)
- Same-piece-type nonsense (knight-forks-knight is not a fork)

```
if targets < 2: return detected = false
```

## Step 2 — Feature scoring (each on 0–1)

Six components, weighted sum.

### 1. Target Value Score (TVS) — weight 0.25

```
piece_values = {pawn: 1, knight: 3, bishop: 3, rook: 5, queen: 9, king: ∞}
top_two_targets = sorted(targets by value desc)[:2]
TVS = min(1.0, (value(t1) + value(t2)) / 10)
```

Examples: Q+R → 1.0 (cap). R+N → 0.8. P+N → 0.4.

### 2. Forker Safety Score (FSS) — weight 0.25 (CRITICAL)

Kills most false positives.

```
if square_defended_by_us > attacked_by_them:
    FSS = 1.0
elif SEE(fork_square) >= 0:
    FSS = 0.8
elif has_safe_escape_next_move:
    FSS = 0.6
else:
    FSS = 0.0
```

### 3. Net Material Gain Score (NMGS) — weight 0.20

Uses SEE.

```
NMGS = clamp(SEE(best_target_capture), -5, +5) / 5
NMGS = (NMGS + 1) / 2   # normalize 0..1
```

### 4. Dual Threat Realization Score (DTRS) — weight 0.15

```
if both_targets_defendable:    DTRS = 0.3
elif one_forced_loss:          DTRS = 0.8
elif both_hanging:             DTRS = 1.0
```

### 5. Tempo / Forcing Score (TFS) — weight 0.10

```
if fork gives check:           TFS = 1.0
elif creates immediate threat: TFS = 0.7
else:                          TFS = 0.4
```

### 6. Counterplay Risk (CRS) — weight -0.10 (penalty)

```
if opponent has immediate stronger tactic: CRS = 1.0
elif some compensation:                    CRS = 0.5
else:                                      CRS = 0.0
```

## Step 3 — Final confidence

```
confidence =
      0.25 * TVS
    + 0.25 * FSS
    + 0.20 * NMGS
    + 0.15 * DTRS
    + 0.10 * TFS
    - 0.10 * CRS

confidence = max(0, min(1, confidence))
```

## Step 4 — Tier mapping

```
HIGH   if confidence >= 0.75
MEDIUM if confidence >= 0.5
LOW    otherwise
```

## Step 5 — Voice mapping (STRICT, no exceptions)

```
HIGH   → "This is a clean fork."
MEDIUM → "This looks like a fork — check if it's safe."
LOW    → say nothing
```

## Reference walkthroughs

### Clean knight fork: queen + rook, forker defended
```
TVS=1.0, FSS=1.0, NMGS=0.8, DTRS=0.9, TFS=0.7, CRS=0
confidence ≈ 0.87 → HIGH
```

### Fake fork: knight forks knight + pawn, forker hanging
```
TVS=0.4, FSS=0.0, NMGS=0.3, DTRS=0.3, TFS=0.4, CRS=0.5
confidence ≈ 0.29 → LOW (filtered)
```

### Sacrificial fork setup: temporary material loss but winning
```
TVS=0.9, FSS=0.6, NMGS=0.7, DTRS=0.8, TFS=1.0, CRS=0.2
confidence ≈ 0.73 → MEDIUM
```

## Critical implementation notes

1. **SEE is non-negotiable.** Naive SEE is wrong on x-rays, batteries,
   pinned defenders, en passant. Use a battle-tested implementation.
2. **Attack graph must be precise** — attackers(sq), defenders(sq), and
   basic pinned-piece awareness.
3. **Don't overfit early.** Corpus validates the formula; doesn't rewrite it.
4. **Evidence matters more than score.** Return *why*, not just the number.

## Reality check

This formula does not make detection perfect. It does:
- Kill false positives
- Surface uncertainty honestly
- Make claims trustable

Right now we guess loudly. This makes us measure quietly.
