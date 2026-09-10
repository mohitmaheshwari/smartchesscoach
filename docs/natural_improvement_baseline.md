# Natural Improvement Baseline — do players fix these patterns alone?

Measured 2026-09-10. Re-run with
`backend/scripts/natural_drift_study.py` (read-only).

## Why this exists

We cannot currently measure whether ChessGuru improves anyone. On 2026-09-10,
2 of 125 users had logged in within 7 days, 87 had never logged in at all, and
the complete-coaching journey ledger held events for exactly **one** human.
Game import runs as a background sync against chess.com and lichess, so 17
users a day of *imported games* and 0 a day of *logins* are entirely
compatible — a distinction worth keeping, because it is easy to mistake sync
volume for usage.

So the question "does the coaching work?" is unanswerable today. This measures
the question that **is** answerable and that every future claim depends on:
how much do these mistake patterns move on their own, with no coaching at all?

Without this number, a coached 15% reduction is uninterpretable. With it, it
is either a real effect or noise.

## Method

18 users have 200+ analysed games. For each, their own history is split in
half chronologically and the per-game rate of each `cognitive_gap` (at
≥150cp) is compared between halves. Rating and opponent rating are reported
alongside, so an "improvement" that is really a softer opponent pool is
visible rather than hidden.

## Result: nothing moves

| pattern | early | late | change | improved |
|---|---|---|---|---|
| tactical_oversight | 0.28 | 0.26 | −4.0% | 8/18 |
| piece_safety | 1.10 | 1.08 | −1.9% | 11/18 |
| missed_tactic | 0.78 | 0.77 | −0.4% | 9/18 |
| endgame_technique | 0.32 | 0.33 | +0.6% | 11/18 |
| king_safety | 0.70 | 0.70 | +0.8% | 8/18 |
| unlabelled | 0.61 | 0.63 | +2.7% | 8/18 |
| opening_knowledge | 0.21 | 0.21 | +4.1% | 6/18 |

Every pattern sits within ±5%, and "improved" is 8–11 of 18 in every row —
a coin flip. Overall, 10 of 18 users' blunder rate fell. **Across hundreds of
games, unaided, these patterns do not move.**

This is the strongest available evidence *for* the product's premise. The
patterns are sticky, so a coach that genuinely reduced piece-safety blunders
by 20% would be doing something players demonstrably cannot do for themselves.

It also settles a live design question: piece safety is both the most frequent
pattern (1.10 per game) and among the least self-correcting, so focusing
players on it is defensible. The opposite hypothesis — that piece safety is
exactly what improves on its own, making it the worst possible focus — was
proposed during this analysis and is not supported.

## The instrument works, verified at both extremes

| user | rating | blunder rate |
|---|---|---|
| user_3e1eaba9e5ad | 1422 → 1721 (+299) | −21.5% |
| user_e6de078c2508 | 1628 → 1907 (+279) | −4.1% |
| user_88682a1254d4 | 659 → 494 (−165) | +16.0% |

The metric catches the large improver and the large decliner. It can see real
change when real change happens, which is the precondition for it ever proving
a coaching effect.

## The finding that should shape the roadmap

Rating and blunder rate **decouple in the middle of the distribution**:

| user | rating | blunder rate |
|---|---|---|
| user_f7e92a45149c | 1054 → 1142 (+88) | +0.5% |
| user_76ee10b87522 | 1109 → 1266 (+157) | +2.5% (worse) |
| user_a66b5bb10c86 | 1456 → 1571 (+115) | −0.7% |

Three users gained 88–157 rating points while their blunder rate stayed flat
or worsened. The currency the product coaches in (fewer blunders per gap) is
only loosely coupled to the currency players care about (rating). A user could
gain 150 points while Progress tells them the pattern is "still recurring".
Worth deciding deliberately which one the product promises.

## Limits — not hidden

* Fixed 150cp blunder threshold, while the product grades rating-aware. For
  users whose rating moved 300 points this is not neutral.
* Halves are split by game **count**, so the two windows are not equal
  durations.
* Per-**game** rates rather than per-opportunity, so a player who moved to
  longer games looks worse.
* 18 users, with between-user spread from −21% to +24%. Detecting a coaching
  effect against that noise needs a large effect or many more users.
* ~15% of blunders carry no `cognitive_gap` (the `unlabelled` row) — a real
  gap in the taxonomy.

## What this unlocks

Natural drift ≈ **0%** is now the control arm. Any future coaching figure
should be reported next to it. It does not make coaching measurable — that
still requires humans using the product — but it makes the eventual number
mean something.
