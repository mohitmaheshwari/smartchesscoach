# Whole-game coaching — feasibility, on four real games

Read-only, 2026-10-15. Nothing written, no code changed, **no architecture
proposed** — components, missing connections and unreliable inputs first, as
instructed. Games are from the **100 distinct** analysed games of
user_8b599930d7ef.

---

## 1. What already exists

Most of this is built. The gap is that nothing joins it.

| Component | What it does | Wiring |
|---|---|---|
| `game_coach_review.compose_story()` | "Coach-shaped game review story… structured narrative, driven by Stockfish's `move_evaluations`", deterministic, no LLM | `routes/games.py` → `/coach-review`, **3 frontend refs** |
| `game_coach_summary.compute_game_summary()` | "One brutal truth about WHY you lost/won", deterministic | **6 importers**, `routes/home.py`, `lab.py`, `training_advanced.py`, 3 frontend refs |
| `game_moments_service.extract_game_moments()` | "Extracts 3–4 key moments… Not every move. Not one move. The STORY of the game" | `routes/training_advanced.py`, 1 importer |
| `board_state_game_summary` | game-wide board-state trends, not per-move | `routes/games.py` |
| `game_phase_service` | continuous 0–100 phase slider from material | 3 importers |
| `game_conversation_thread` | what the coach already said *this* game | `routes/coach_play.py` |
| `move_observations` | per-move derived facts, incl. the paired `missed/punished_opponent_blunder` and `responded/ignored_opponent_threat` | 632k rows |
| `game_decryption_v5_service` | per-move captions, `narrative` field, `move_story` classifier | live |

So "the story of the game" is already a named, shipped idea in three separate
services. **A whole-game layer would be a fourth consumer of existing parts,
not a new analysis.**

### The one component that is built and unwired

`game_context_enricher` — **0 importers.** Its docstring: derives
`time_control_category`, `opponent_rating` and `user_rating` "from data that's
already stored", reading WhiteElo/BlackElo out of the PGN. That is exactly what
question 1 needs, and it explains two gaps measured earlier:
`games.opponent_rating` is only 48.9% populated, and
`time_control_category` is **`None` on all four games below**.

---

## 2. Four contrasting games

Selected by criteria fixed before looking. Ratings are PGN-derived
(WhiteElo/BlackElo), so they are the opponent's *expected* strength only — see
§4 on why how they actually played is largely unavailable.

### Game A — an accurate-looking loss that was over by move 11

`lichess.org/CnATF3rC` · 2026-09-17 · blitz 300+3 · White **1301** vs **1373**
(+72) · **lost on time forfeit** after 19 moves · mean cp lost **53.8**,
1 blunder, 2 mistakes.

```
1. e4 e5 2. Nf3 Nc6 3. Bc4 h6 4. c3 d6 5. Qb3 Qf6 6. d3 Be7 7. Nbd2 a6
8. a4 Na5 9. Qa2 Nxc4 10. Qxc4 c5 11. b4 Be6 12. bxc5 Bxc4 13. Nxc4 dxc5
14. Ncxe5 Bd6 15. Ng4 Qxc3+ 16. Bd2 Qxa1+ 17. Ke2 Qxh1 18. Nh4 O-O-O
19. Be1 Bxh2 0-1
```

**The story.** He reaches +53 by move 4 and then never castles: at move 6 the
engine wants `O-O`, he plays `d3`. His queen goes `Qb3 → Qa2 → Qxc4` while the
king stays on e1 and the rooks on a1 and h1 — **neither rook moves in the
entire game**. The eval drifts −16, −48, −58, and then **11.b4 costs 352cp**
and opens the queenside he had just committed to. From move 15 Black's queen
collects both unconnected rooks: `Qxc3+`, `Qxa1+`, `Qxh1`.

**Connected moments, not a list.** Three decisions, each cheap on its own,
compose the loss: declining to castle (move 6, 49cp), walking the queen to a2
and c4 (moves 9–10, 37cp and 0cp), then opening lines with b4 (move 11, 352cp)
with the king still in the centre. The 352cp blunder is the only flagged event;
the position it arose in was built by the three moves before it.

**Why "played accurately" is wrong here, and it is my error.** I selected this
game as the accurate loss because its mean cp loss is 53.8. But one 352cp
blunder across 19 moves averages down to look clean. **Mean cp loss is not an
accuracy measure in a short game** — see §4.

**Q5 is unanswerable for this game.** `move_observations` holds **zero** paired
records here: opponent errors punished 0, missed 0; threats answered 0, ignored
0. Not "he faced no threats" — no observation rows exist.

### Game B — a win that demonstrates very little

`66ac48e5` · 2026-09-21 · blitz · White **1293** vs **1190** (**−103**) ·
**won on time forfeit** · 50 moves · mean cp lost **115.9** ·
**11 blunders, 4 mistakes**.

Blunders at moves 6, 7, 9, 21, 22, 24, 25, 30, 38, 39, 50. Three are decisive
in character:

| Move | He played | Engine wanted | Cost | Stored gap |
|---|---|---|---|---|
| 9 | `Qh5` | `Bf7+` | **704cp** | missed_tactic |
| **21** | `Bd5` | **`Rc8#`** | **580cp** | missed_tactic |
| 30 | `f4` | `Bd5` | 471cp | endgame_technique |

**He missed mate in one at move 21** and remained +420 anyway. He **punished 1
of 8** opponent errors (7 missed) and answered 4 of 9 threats.

**The story.** He won this game by clock against an opponent rated 103 points
below him, while making eleven blunders and declining a mate. Nothing about the
result demonstrates strength, and the game is a direct example of your first
point: **a win over a weaker opponent is not evidence of good play.** It is
also the cleanest possible case for whole-game framing — with 11 blunders,
asking "which was *the* mistake" has no defensible answer.

### Game C — a genuine recovery

`73140de9` · 2026-10-14 · blitz · Black **1322** vs **1433** (+111) ·
**won by checkmate** · 30 moves · mean cp lost 73.2, 2 blunders · lowest eval
**−1500** (he was facing mate) · opponent errors **punished 2, missed 0**.

**The story.** Against an opponent 111 points stronger he reached a position
evaluated at the mate floor, and won anyway — punishing both errors the
opponent offered, missing none. Whatever else is true of him, **this game
demonstrates practical recovery**, and a results-first or an
accuracy-first reading would both hide it: 2 blunders and a −1500 trough look
like a disaster.

### Game D — a selection failure, reported rather than dressed up

`0f00953e` · 2026-09-03 · Black **1295** vs **1392** (+97) · **lost on time** ·
52 moves · mean cp lost **223.3**, 4 blunders, 8 mistakes.

I selected this as the "loss with no decisive fall" category. **It is not one.**
My filter computed `fall = peak − trough` on evals clamped to ±1500, and when a
mate score appears at both the peak and the trough the subtraction gives **0** —
so a filter for `fall < 200` selected the most violent games instead of the
quietest. This game has 12 significant errors.

I have left it in because the defect matters more than the example: see §4.

---

## 3. Missing connections

1. **Nothing composes the parts.** Three services each produce a game story
   (`game_coach_review`, `game_coach_summary`, `game_moments_service`) from
   overlapping inputs, independently. There is no single account of a game, and
   no component asks "what did the earlier move prepare?"
2. **No component spans moves.** Everything above is per-move facts aggregated,
   or a hand-picked set of moments. Nothing computes *what a move created* —
   the loose piece, the departed defender, the opened line — which §2's Game A
   and the earlier Rh6+ example both turn on. That is the actual gap, and it is
   detection work, so it is out of scope here by instruction.
3. **`game_context_enricher` is unwired**, so question 1's own inputs
   (`opponent_rating`, `time_control_category`) are absent or partial on the
   very games we would narrate.
4. **Observation coverage is not guaranteed per game.** Game A has zero
   `move_observations` rows, so its paired opponent/threat measures are blank.
   Any whole-game layer must report coverage per game rather than render zeros
   as facts.
5. **Opening identity is missing on lichess games** — `opening_name`,
   `opening` and `eco` are all `None` on all four — so "the opening situation"
   has to be derived from the moves each time.

---

## 4. Unreliable inputs

Four, and the first two are defects in my own analysis today.

1. **The ±1500 eval clamp destroys any peak-to-trough measure.** Mate
   sentinels sit at the clamp, so `fall` collapses to 0 exactly in the games
   with a mate in them. This produced a wrong selection (Game D) and would
   corrupt any automated turning-point detection built the same way. A
   whole-game layer must treat mate evals as a separate state, not a number.
2. **Mean cp loss is not an accuracy measure.** Game A averages 53.8 while
   being lost by move 11, because one 352cp blunder divides across 19 moves. It
   should not be used to characterise how well a game was played, and I used it
   that way to pick Game A.
3. **The opponent's actual play is not measurable.** `move_evaluations` stores
   only his moves, so there is no cp_loss for the opponent at all. Question 1's
   "how they actually played this game" can only be approached indirectly,
   through `missed/punished_opponent_blunder` counts — which are themselves
   missing on some games (point 4 of §3). Expected strength we have; actual
   performance we do not.
4. **`cognitive_gap` labels are thin on the decisive moves.** In Game A the
   352cp blunder carries no gap at all; in Game B the two biggest carry
   `missed_tactic`, which does not distinguish a missed mate from a missed pawn.

And one caution on intention, since questions 3 and 7 depend on it: everything
in §2 labelled "the story" is **inferred from the moves**. Game A's account —
that he declined to castle and left the rooks unconnected — is supported by the
PGN (no castling, neither rook moves) but says nothing about whether he
intended a queenside plan. **Engine disagreement is not evidence of having no
plan**, and the only way to establish intention is to ask at the moment; move 6
and move 11 are the two candidates in that game.

---

## 5. What a whole-game pass could say today, and what it could not

**Could, from existing data:** the context (with `game_context_enricher`
wired), the eval shape, the connected sequence where it is visible in the moves,
the opponent-error pair where observations exist, demonstrated strengths such as
Game C's recovery, and a main lesson traced to numbered moves.

**Could not, without new work explicitly out of scope here:** what a move
*created* (the cross-move feature tracking), how well the opponent played, the
player's intention, and any turning point computed from a clamped eval.

**One further question for you before anything is designed:** of the three
existing story services, `game_coach_summary` is the most wired (6 importers,
3 frontend refs) and `game_coach_review` already claims to be the structured
narrative. Should a whole-game layer extend one of those, or is the right first
step to read all three and report what they already say about these four
games — so we find out whether the gap is analysis or composition before
building either?
