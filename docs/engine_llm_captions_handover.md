# Engine facts + LLM captions — what shipped while you were away

22 October 2026. Everything below is on `working-code` and live on
chessguru.ai. Nothing touches arrows.

---

## The short version

The engine now says something about **every** move, not just the faulted
ones, and an LLM writes the caption from the engine's facts — once, at
analysis time, stored. No model call when a page renders.

Verified on prod with the real key: **6 of 6 captions accepted**, and in the
earlier 12-card run **11 of 12**, the one refusal being correct (the model
invented a move that was not in the facts).

---

## What a card used to say, and says now

```
was   "Kf1 loses to Qxd3+. Ke2 was better."
now   "Ke2 guards your d3 pawn and stops their threat of Qxd3+. Learn to
       meet threats to your pieces before moving your king elsewhere."

was   a 9,148cp position — the player is being mated — explained as a PAWN
      being taken
now   "Qd2 lets your opponent force mate, so look for ways to keep their
       king under pressure. Qxf5+ also checks their king and protects your
       pawn on e5."
```

---

## The four decisions you made, and what each became

| you chose | what shipped |
|---|---|
| purposes as a **pure function** | `services/move_purposes.py` — no DB, no engine. Works on all 18,920 existing games with no re-analysis. |
| **wire into captions** | `services/llm_caption.py`, written at analysis time, spliced into the V5 card. |
| **build MultiPV** | `candidates` + `best_is_only_move`, gated to faulted moves. |
| **leave old games alone** | No backfill. Nothing re-analysed, no arrow moved. |

---

## 1. The engine speaks for every move

It was silent on **91.8% of good moves**, and good moves are **70% of a
game** — so two-thirds of what a player did came back as an eval and a
blank. It was never a search cost: `eval_after` is stored on 100% of moves,
so the search ran every time and `evaluate_position` discarded the principal
variation sitting in the same result.

`evaluate_position_with_line()` returns what that one search already found.
Good moves now carry 11–12 ply lines.

Stored under its own key, `eval_line_played`. It is **never** merged into
`pv_after_played`, which is what the arrow builder reads — that is what
guarantees no existing card moved.

## 2. `opp_replies` reaches the database

Computed at depth 18 by the analysis and dropped by `_serialize_move`, which
simply did not copy it out. Present on **0.0%** of stored moves in every era
since May.

It is the only field separating *"they win your rook"* from *"they might"* —
whether the punishment is forced or one of several equal replies.

## 3. The purpose vocabulary

Not invented. Read 23 mined positions one at a time, wrote down what the
better move did, then measured every candidate on 7,346 flagged cards:

```
attacks a piece that cannot escape 21.7%   avoids an attacked square 14.4%
moves the attacked piece to safety 14.1%   check worsens the king     7.1%
defends the attacked piece          6.9%   a pawn attacks a piece     6.4%
activates the rook                  6.3%   trades off their piece     5.9%
denies their counterplay            4.3%   stops their passed pawn    3.5%

at least one purpose  61.7%   (against 27% for the two shapes that existed)
two or more           23.5%
```

Two entries did not survive the measurement. *Supports our passed pawn*
fired on 0.4% — 28 cards — and was dropped. *Attacks a piece that cannot
escape* was the biggest number and the loosest probe: it merged "hanging"
with "trapped", so it was **split**, and the trapped half routes through
`game_ledger._piece_trapped_after`, already proven and stricter than
anything I would have written.

Two more came from the residue nothing could explain: **94%** of it carries
a `threat` the engine already stored, and **23%** is mate in one direction or
the other, already in `mate_info`.

It returns a **ranked list**, never one winner — on 23.5% of cards there is
more than one true thing to say, and the old code was an if-chain that
returned the first match.

## 4. MultiPV

`candidates` and `best_is_only_move`. "This was the only move" and "any of
four was fine" are different lessons and nothing could tell them apart.

Gated to faulted moves: MultiPV costs **3.05x** per position (0.881s →
2.682s, measured on disjoint positions with a fresh engine each), and faulted
moves are ~19% of a game, so the whole-game cost stays near **1.4x**.

## 5. The caption

`services/llm_caption.py`. The model may choose, order and phrase. It may
**not** add a square, piece or move that is not in the fact bundle — the
validator rejects the caption if it does, and a rejection leaves the
deterministic caption standing. This layer may only replace, never erase.

Why a model at all: on your `Bd6+` card, same model, only the facts
differing — with what the pipeline had it produced the same vague caption we
already ship; with the refutation added it named `Bd6#`. **The model was
never the bottleneck. The facts were.**

---

## What you should check

1. **Open a newly analysed game.** Cards whose text came from the model have
   `LLM_CAPTION` in their `rule_name`.
2. **The flag.** `LLM_CAPTIONS_ENABLED=1` in `/root/repos/smartchesscoach/.env`.
   Setting it to `0` and restarting falls straight back to the deterministic
   captions. Nothing else changes.

## The limitation you need to know

**Only newly analysed games get LLM captions.** The caption is written at
analysis time, so the 18,920 existing games still show their deterministic
text.

Making them show it does **not** need re-analysis — the facts come from
stored data — but it does need a V5 re-render, which re-renders every card.
I did not do that while you were away because a full re-render is exactly
where an unrelated change could move an arrow. It is a one-command job when
you want it.

## Not done, and why

- **`D` split is built but not separately measured.** I split hanging from
  trapped as the spec required, but the 21.7% figure was measured before the
  split, so neither half has its own number yet.
- **Routing.** Another session measured 1,054 filler-bearing cards, 90 of
  which had a concrete why that lost its slot anyway. Richer facts do not fix
  that, and I did not touch it.
- **Opponent cards.** `cp_loss` is 0 on them, so the facts are thin by
  construction. Sizing that is its own piece of work.

## Tests

342 across the arrow, caption, purpose and engine suites, including all 8
arrow suites. New files: `test_move_purposes.py`,
`test_llm_caption_may_not_invent.py`, `test_llm_caption_reaches_the_card.py`,
`test_engine_speaks_for_every_move.py`.
