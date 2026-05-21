# m19 Kf8 — borderline losing position, "Opponent's strongest reply" engine-speak

**Game:** `c25fea91` move 19
**FEN:** `4r1k1/p1p2ppp/2p3q1/8/5B2/2PP2P1/P1P1bPQP/R5K1 b - - 5 19`
**Played:** `Kf8` (cp_loss = 179)
**Current caption:** *"Kf8 is a mistake. Qf6 was better. Opponent's strongest reply: Be3."*

## Engine analysis (Stockfish depth 18)

| Move | eval (user POV) | Comment |
|---|---|---|
| Before move | +12cp | Roughly balanced (Black to move) |
| After Kf8 (played) | **-108cp** | Black has drifted into slightly worse |
| After Qf6 (best) | +15cp | Maintains balance |

Best PV (after Qf6): `Qf6 Bd2 Bf3 Qf1 h6 Re1 Rb8 Rb1 Rb6 Rxb6 cxb6`

## Diagnosis

Black is borderline: eval_after_played = -108cp, just barely "losing" (our threshold is -200cp). So `user_is_losing` is FALSE here. Neither the winning nor losing reframing should fire.

`why_user_reply` fires ("Opponent's strongest reply: Be3") which is the LOW engine-speak fallback. Then user_with_best_and_why renders the full caption.

This is a genuine case where cp_loss is meaningful (Black gave up balance and is now slightly worse), but the caption is still weak because:
1. No tactical why-clause fires (the move isn't a 1-move blunder)
2. No principle detector fires (not in the opening, not an obvious structural error)
3. board_state describer might fire here but apparently didn't

## Suggested fix

Lower priority than Pattern A. This position genuinely doesn't have a clear principle to teach — Kf8 just gives up some positional pressure. The "Opponent's strongest reply" engine-speak is the WEAKEST surface we have.

Options:
1. **Investigate why board_state didn't fire.** This is an endgame-ish position (move 19, simplified) — board_state metrics may not be tuned for endgames.
2. **Accept the engine-speak.** If we can't say anything better, "Opponent's strongest reply: Be3" at least gives the user the line to look at. Not great, but honest.
3. **New endgame-aware detector.** "Your king move loses activity / your queen has no good follow-up" — requires endgame-specific analysis.

## Category

`pattern_a_borderline_no_detector_fires`
