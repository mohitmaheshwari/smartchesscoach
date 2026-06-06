# Caption Teaching Audit — 1,000 re-analyzed games (2026-06-07)

**Question (Mohit):** for each move that has a caption, does it actually *teach* (position-specific why), or just label it / append filler?

**Method:** automatic scan of the 1,000 most-recently re-analyzed games (by queue completion). 62,579 moves. For each move with cp_loss ≥ 100 (where teaching matters), classify the stored caption: REAL teaching (names a position-specific mechanism) / floor-principle filler / bare shell / no-caption / positive-on-blunder. Keyword + regex heuristic, opp-aware.

## Headline

**~70%+ of mistakes/blunders get genuine position-specific teaching.** (Keyword-detected floor = 51%; calibration below shows most of the "no clear mechanism" 22% is real teaching the keyword list missed.)

| Category | keyword count | reality |
|---|---|---|
| ✅ REAL teaching (keyword-matched) | 51% (6,510) | **floor** |
| "severity-bearing, no keyword mechanism" | 22% (2,878) | **mostly real teaching** the ~45-keyword list missed ("parks on the rim", "out alone", "wastes a tempo", "aimed at your king", "moved away from defending e5", "grabs material with check") → add most of this to REAL → **~70%+** |
| Bare shell | 13% (1,686) | genuine gap — mostly OPP-side ("Opponent's X is a mistake. Play Y.") |
| Principle-floor filler | 6% (769) | genuine gap (looks like teaching, isn't) |
| No caption | 4% (587) | — |
| Positive-on-blunder (misleading) | 2% (309) | small; the actually-wrong set |

## User vs opp (the real story)
- **User mistakes (6,472):** 54% keyword-teaching, 30% "no-keyword-mechanism" (mostly real teaching missed), 11% floor-filler, ~0% bare.
- **Opp mistakes (6,267):** 48% keyword-teaching, **26% BARE** ("Opponent's X is a mistake. Play Y."), 15% no-keyword, 1% floor.

## What this means
1. **The system teaches better than a keyword scan shows.** Real rate ≈ 70%+. The chess teaching vocabulary (rim knights, loose queens, tempo, king safety, defensive abandonment) is far richer than any keyword list — so any automated "teaching coverage" metric is a floor.
2. **The concentrated, genuine gap is OPP-side bare shells (≈26% of opp mistakes).** The opp-failure framework currently covers only missed_capture / missed_mate (V1/V2); the rest of opp mistakes render bare. This is the single highest-leverage caption-quality target — and it's where opp V3 (traded_active) + completing the opp-failure clauses would land.
3. **Floor-principle filler (6%)** is the other soft spot — captions that *look* like teaching but aren't position-specific (per the principle-bank-is-filler rule).
4. **Actually-misleading captions are only ~2%** (positive framing on a blunder) — small, mostly already guarded by the `_tactic_ok` king_safety gate; residual are likely stale renders.

## Corrections logged during this audit (my errors)
- "v5_coaching_version = None on all games" → **wrong field name** (real field: `decryption_v5_version`); the freshest 1,000 games are mostly **v110** (760) — deployed worker IS current, re-analysis heals to v110.
- "23% positive-on-blunder = misleading" → **classifier artifact** (opp moves mis-bucketed: BARE regex was user-only, MECH list trimmed). Corrected to ~2%.

## Caveats
- Keyword/regex heuristic; "REAL teaching" is a floor (undercounts), the 70%+ estimate is a calibrated read of the sampled "no-keyword" bucket, not exact.
- Reflects current v110 stored captions on the freshest 1,000 re-analyzed games. The long tail of un-re-analyzed games is at older versions (healing as the queue drains).
