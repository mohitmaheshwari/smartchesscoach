# The three review services, run on the same four games

Read-only, 2026-10-15. The three services were called directly with production
data; **nothing was written**. Outputs below are verbatim.

---

## 0. First, my Game A story was wrong

You caught it, and the board confirms it.

| | |
|---|---|
| before **11.b4** | queen on c4, **attacked by nobody**, defended by d2 and d3 |
| after **11…Be6** | queen on c4 **attacked by the bishop on e6** |
| before **12.bxc5** | the queen had **six safe squares**: Qd5, Qxc5, Qb5+, Qd4, Qb3, Qa2 |
| he played | **12.bxc5**, taking a pawn |
| material | even through move 11 → **+1** after bxc5 → **−8** after 12…Bxc4 → −5 after 13.Nxc4 |

So the event is: **his queen was attacked, he had six ways to save it, and he
took a pawn instead.** The rooks on a1 and h1 went at moves 16–17, *after* he
was already down a queen for a bishop. My "delayed castling and disconnected
rooks" account was a narrative built on the consequence — exactly the failure
you warned about, and a worse error than the isolated label would have been,
because it was coherent.

**The existing service already had this right.** `compose_story` says:
*"b4 runs into Bxc4, **trading your queen on c4 for a bishop**; instead d4 was
stronger."* And `game_moments_service` supplies the sequence:
`pv_after_played: ["Be6", "bxc5", "Bxc4", "Nxc4"]`. I was wrong where the code
was right.

**One real input defect this exposes:** the engine charges **352cp to 11.b4**
and **0cp to 12.bxc5** — the move that actually handed over the queen is costed
at zero, because by then the eval had already moved. Any turning-point logic
built on cp_loss alone will point at b4 and never mention bxc5. The material
curve is needed alongside.

---

## 1. Verbatim outputs, side by side

### Game A — loss, White 1301 v 1373, timeout, 19 moves

| Service | Output |
|---|---|
| **coach_summary** | diagnosis `PIECE_GIVEAWAY`; root_cause *"You hung a piece."*; subline *"Move 11 b4."*; context *"3.5 pawns of material gone on that move"*, *"d4 would have saved a piece"*, **"Your opponent played clean — no mistakes to punish."** |
| **coach_review** | opener *"You played the this game and you lost as White. The game turned at move 11 in the opening."*; **good_moves `[]`**; diagnosis *"b4 runs into Bxc4, trading your queen on c4 for a bishop"*; closing *"2 real mistakes decided this game."* |
| **moments** | 2 moments: `context` m7 *"The position was balanced."* → `break` m11 *"The position was level. One move changed everything."* with FENs, evals and `pv_after_played` |

### Game B — **win**, White 1293 v 1190, timeout, 50 moves, 11 blunders

| Service | Output |
|---|---|
| **coach_summary** | diagnosis `WON_OPPONENT_BLUNDER`; root_cause *"Messy win."*; subline *"You had 11 blunders too — your opponent's were bigger."*; context *"Your total inaccuracy: 5796 centipawns"* |
| **coach_review** | *"The game turned at move 9"*; **good_moves `[]`**; 3 homework items; summary_table of 5 mistakes — **two with `"remedy": ""`** |
| **moments** | 3 moments: `context` m4 *"You had a small edge."* → `warning` m6 *"You were still winning, but this was the first slip."* → `break` m9 *"You were winning. Then this happened."* |

### Game C — **win by checkmate**, Black 1322 v 1433, from an eval of −9970

| Service | Output |
|---|---|
| **coach_summary** | diagnosis `WON_OPPONENT_BLUNDER`; root_cause *"Messy win."*; critical_move m20 `Qxh3+` cp_loss **1385**, eval_before **9970** |
| **coach_review** | *"3 real mistakes decided this game. The biggest was move 20"*; **good_moves `[]`**; diagnosis *"Qxh3+ misses mate in 3"* |
| **moments** | 2 moments: `context` m15 *"You were winning here."* → `break` m20, **`eval_before: 99.7`** |

**None of the three mentions that he won, by checkmate, from a lost position.**

### Game D — loss, Black 1295 v 1392, timeout, 52 moves

| Service | Output |
|---|---|
| **coach_summary** | diagnosis `REPEATED_BLUNDERS`; *"The game was really decided at **move 4**"*; **"Total material leaked: 99.3 pawns worth"**; critical_move m51 cp_loss **9108**; **"Your opponent played clean — no mistakes to punish."** |
| **coach_review** | *"The game turned at **move 51**"*; **good_moves `[]`**; m51 title *"King in the corner = mate"* with diagnosis *"it runs into Bxg8, taking your bishop"*; m43 remedy: *"**This spot got hard a few moves ago, around move 4.** Bb2+ holds on longer — **but the real fix is earlier**."* |

---

## 2. Do they explain the five things?

| | coach_summary | coach_review | moments |
|---|---|---|---|
| **decisions connected across moves** | No — one critical move, one root cause | **Partly.** One reply deep as standard ("b4 runs into Bxc4"); and on Game D m43 it reaches back four decades of plies: *"this spot got hard around move 4… the real fix is earlier."* That is the only cross-move reasoning in any of the three | Partly — an arc by eval shape (context → warning → break), not by cause |
| **opponent's threats and contributions** | Names the *result* (`WON_OPPONENT_BLUNDER`) but never a threat. **And asserts "opponent played clean" on Games A and D** — Game A has **zero** `move_observations` rows, Game D has one `missed_opponent_blunder`. A blank is being rendered as a fact | No | No |
| **what the player handled well** | No | **`good_moves` exists and is `[]` on all four games** | No |
| **where the game changed, with verified alternatives** | Yes, by max cp_loss — and it **disagrees with coach_review on Game D** (move 4 vs move 51) | Yes, by max cp_loss, with FEN + best move | Yes, with FEN before/after, both evals and `pv_after_played` — the best evidence of the three |
| **one lesson, uncertainty stated** | A lesson, no uncertainty | A lesson plus homework, **no uncertainty anywhere**, and two empty remedies shipped in Game B | A lesson implicitly, no uncertainty |

**No service states uncertainty of any kind** — not about intention, not about
missing data, not about mate scores.

### What a balanced review of Game B would have said

Not "demonstrates nothing" — that was my phrasing and it was as unbalanced as
the services' "messy win". The data:

**26 of his 50 moves cost nothing**, and `concept_used` fired on 27 of them.
After the move-9 disaster took him from +491 to −197, he played **eight
consecutive engine-approved moves** (m11–m20, all 0cp) and rebuilt the eval
from −208 to **+509**: `Qc4`, `Qxd5`, `Bxd5`, `Be6`, `a3`, `Ra3`, `Rb7`,
`Rxc7`. `found_best_in_critical` fired once. So the game contains a genuine
demonstrated ability — **recovering from a self-inflicted collapse and
converting** — next to eleven blunders and seven unpunished opponent errors.
Both halves are true and the services report only the second.

### What a balanced review of Game C would have said

At **move 19** the eval was **−9970**: he was facing forced mate. He played the
engine's best move anyway (`Qg3`, 0cp). **The opponent did not deliver the
mate.** By move 23 the eval was **+396**, and he won by checkmate, punishing
**both** errors the opponent offered and missing none.

He also missed mate in 3 at move 20 (`Qxh3+` instead of `Qxf3+`). All of that
belongs in one account: *the opponent let a won position go, he kept playing
sound moves while lost, he missed a faster finish, and he still mated.* The
services render only the missed mate, and call the game "messy".

---

## 3. One recommendation

**Extend `game_coach_review.compose_story`.** Not because three exist — because
it is the only one of the three that already reasons across moves at all, and
the only one with a slot for strengths. `game_coach_summary` is more widely
wired (6 importers) but is structurally one verdict about one move;
`game_moments_service` has the best per-moment evidence and should be **read by**
`compose_story` rather than extended separately — its `pv_after_played` is
exactly the verified-alternative evidence `compose_story`'s principles lack.

**Exactly what it lacks, in priority order:**

1. **`good_moves` is never populated** — `[]` on all four games, including a win
   and a checkmate recovery. The field exists; nothing fills it. This is the
   single largest gap and the cheapest to close: 26 of 50 moves at 0cp in Game
   B, 17 of 30 in Game C, with `concept_used` already naming what was applied.
2. **No cross-move causal link, except by accident.** The Game D m43 remedy
   proves the voice exists ("the real fix is earlier") but it is triggered by
   something local, not by tracking what a move created. Game A needs exactly
   this: *the queen was attacked at move 11 and he had six squares.* The
   material curve, the attacked/defended state of each piece, and "what this
   move stopped blocking" are all computable and none is consulted.
3. **Mate scores leak into user-facing text as centipawns** — `−9108cp`,
   `−1385cp`, *"99.3 pawns worth"*, `eval_before: 99.7`. Every one of those is
   a mate evaluation rendered as material. Must be a separate state.
4. **No uncertainty is ever stated.** It needs two sentences it currently cannot
   produce: *"we do not know what you intended here"* and *"no opponent data
   was recorded for this game"*.
5. **The turning point is max cp_loss only**, which picks a move made while
   already winning (Game C m20), disagrees with the other service (Game D:
   move 4 vs 51), and attributes nothing to the move that actually lost the
   material (Game A m12 at 0cp).
6. **Empty strings ship as teaching** — `"remedy": ""` twice in Game B.
7. **The opening name is empty on every lichess game**, producing *"You played
   the this game"* in all four openers.
8. **Title and diagnosis can contradict** — Game D m51: *"King in the corner =
   mate"* against *"it runs into Bxg8, taking your bishop."*

Item 2 is the only one that needs new analysis. Items 1, 3, 6, 7 and 8 are
defects in a shipped service, and item 4 is a wording addition.

**What I am not recommending:** merging the three. `compose_story` reading
`moments`' evidence is composition; a fourth service would be duplication.
