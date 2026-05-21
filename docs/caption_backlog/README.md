# Caption Backlog — Per-Position Authoring Candidates

This folder collects LOW-tier (or otherwise unsatisfying) caption positions surfaced by the v50 audit. Each MD file documents one position: FEN, played move, current caption, engine analysis, what's wrong, and what the caption should say.

Authoring workflow:
1. Pick a position file (priority by frequency or by pattern).
2. Read the engine analysis.
3. Decide whether the fix is **content** (better wrong_feedback in a curriculum tree, new caption variant) or **logic** (predicate fix, threshold change, new detector).
4. Author the fix; remove the MD file when shipped + verified.

## Active entries (8 from v50 audit, 2026-05-21)

### Pattern A — Position-eval reframing blocked by engine-speak why-clause (5)

The `user_winning_position` / `user_losing_position` variants in R12 are gated on `why_clause: absent`. But the engine-speak fallbacks (`why_user_reply`, `why_user_missed_material`) still fire and *set* `why_clause`, blocking the reframing. Fix: gate those engine-speak why-clauses on `user_is_winning: false, user_is_losing: false` so they don't fire when position-eval framing should win.

- [m28_Bd4_winning.md](m28_Bd4_winning.md) — winning +720cp, captioned "serious mistake" + engine-speak reply
- [m29_g6_winning.md](m29_g6_winning.md) — winning +730cp, same pattern
- [m17_Nb4_winning.md](m17_Nb4_winning.md) — winning +465cp, same pattern (borderline — just above +200cp threshold)
- [m19_Kf8_losing.md](m19_Kf8_losing.md) — losing -108cp, just barely "losing"; reframing may or may not be appropriate
- [m20_Qe6_losing.md](m20_Qe6_losing.md) — losing -395cp, deserves the user_losing_position framing

### Pattern B — `why_user_missed_material` LOW engine-speak (1)

When the missed_tactic detector finds a material gain but eval_guard rejects piece_capture, falls back to "wins material in the resulting line" — engine-speak. Could be improved with a more specific phrasing or by extending the detector to identify the kind of material won.

- [m8_b6_material.md](m8_b6_material.md) — early Benoni-like position, "a5 wins material in the resulting line"

### Pattern C — Weird off-book early opening (2)

Games where black plays an unusual / dubious opening (1.h4 e5 2.a4 — King's Knight Variation-adjacent). No curriculum applies; engine sees specific lines but the teaching is hard to articulate at 1200 level.

- [m5_Qf6_weird_opening.md](m5_Qf6_weird_opening.md) — bizarre 1.h4 game, Black plays Qf6 at move 5
- [m7_Qe5_weird_opening.md](m7_Qe5_weird_opening.md) — same game, two moves later

## How to interpret each MD file

```
**FEN:** the board state before the played move
**Played:** the move the user actually played (with cp_loss)
**Current caption:** what V5 produced at v50
**Engine analysis:** Stockfish depth-18 eval, best move, best PV
**Diagnosis:** why the current caption is weak
**Suggested fix:** what the caption SHOULD say + implementation path
```
