# m28 Bd4 — winning position, captioned as "serious mistake"

**Game:** `db4ea92d` move 28
**FEN:** `6k1/5ppp/pp6/3p4/1P2q1b1/P4NP1/5bKP/3Q4 b - - 1 28`
**Played:** `Bd4` (cp_loss = 175)
**Current caption:** *"Bd4 is a mistake. Be3 was better. Opponent's strongest reply: b5."*

## Engine analysis (Stockfish depth 18)

| Move | eval (user POV) | Comment |
|---|---|---|
| Before move | **+665cp** | Black is winning by ~6.6 pawns |
| After Bd4 (played) | **+720cp** | Still winning by ~7.2 |
| After Be3 (best) | +707cp | Marginally better |

Best PV (after Be3): `Be3 h3 Bd7 Kh2 h5 Nh4 Qe6 Qf1 d4 Qg2`

## Diagnosis

Black is **crushing** — up by ~7 pawns of eval — and Bd4 *increases* black's advantage from +665 to +720. The cp_loss of 175 is purely the gap between Bd4 and the engine's slightly preferred Be3.

Calling this "a mistake" is misleading coaching. The user is winning by a huge margin; Bd4 is fine.

The v50 `user_winning_position` variant exists *exactly* for this case but doesn't fire here because:

1. `opp_reply_san` is present (b5), so `why_user_reply` fires last in the why_clauses_user list.
2. `why_clause` is now SET to "Opponent's strongest reply: b5."
3. `user_winning_position` in select_variant requires `why_clause: absent` → fails.
4. Falls through to `user_with_best_and_why` → the bare engine-speak caption.

## Suggested fix

Gate the engine-speak fallbacks (`why_user_reply`, `why_user_missed_material`) so they DON'T fire when user_is_winning or user_is_losing. Add to their predicates:

```json
{"when": {
   "opp_reply_san": "present",
   "user_is_winning": false,
   "user_is_losing": false
 }, "variant": "why_user_reply"}
```

After this, the why_clause stays absent in winning/losing positions, and `user_winning_position` fires:

> *"Bd4 is fine — you're still winning. Be3 would have kept the pressure on."*

## Category

`pattern_a_eval_reframing_blocked_by_engine_speak`
