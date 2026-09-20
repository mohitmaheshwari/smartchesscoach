# Caption gold vs generated — 2026-09-20

Mohit: "i am happy with the detectors and they are firing really well, what i am
not happy with is captions ... can you claude help me write the captions and
then we compare, like your gold vs what is generating."

This is that comparison. Every claim in every gold caption below was checked on
a real board or against Stockfish before it was written; the failures found in
the generated captions were checked the same way.

---

## 1. The baseline, measured

4,378 user-mistake captions (cp_loss >= 150, render version 165+):

| Defect | Count | Rate |
|---|---|---|
| **`principle_cue` EMPTY** | 4,311 | **98.5%** |
| recommends a move with no why clause | 760 | 17.4% |
| severity contradiction ("playable" on a >=150cp move) | 162 | 3.7% |
| does not name the move the player played | 83 | 1.9% |
| duplicate caption within the same game | 19 | 0.4% |

**The captions are diagnostic, not didactic.** 82.6% do explain what happened
and what was better. 98.5% never say what to remember. That single number is
the gap, and it is bigger than everything else on the list combined.

## 2. A separate check: do the recommendations survive?

220 stored recommendations re-analysed at depth 20:

| | |
|---|---|
| recommended move genuinely better | 212 (96.4%) |
| within 30cp | 4 (1.8%) |
| **recommended move is WORSE** | **4 (1.8%)** |

Not systemic — but the four failures cluster around mate:

```
played Rb1 = +99978 (the player had MATE)   "better" Kf6 = +1081
played Rf6 =    -801                        "better" h3  = -99991 (mate against)
```

We told a player who had found mate that something else was better, and in
another we recommended a move that gets mated. Both are the mate-handling
family already recorded in [[project-mate-gate-and-backfill]].

---

## 3. Gold vs generated

### Case A — `O-O`, −300cp (king_safety)
`r2qk2r/ppp1bppp/2n1p3/3p1b2/3PnB2/2PBPN2/PP1N1PPP/R2Q1RK1 b kq - 5 8`

> **GENERATED:** "O-O is a major blunder. g5 was better — it attacks the bishop
> on f4, forcing it to move. A pawn that pokes an enemy piece wins you time —
> they have to stop and answer it."

**Verified:** g5 does attack f4; the bishop has five legal squares
(Bxc7, Bd6, Bxg5, Be5, Bg3), so "forcing it to move" is true and "trapped"
would not have been.

**Verdict: this one is already close to gold.** It names the played move, the
better move, a true why, and a transferable line. The only thing missing is
what O-O *cost* — it explains why g5 is good and never why castling was wrong.

> **GOLD:** "Castling was fine in itself, but it ignored the bishop sitting on
> f4. g5 hits it at once and it has to move, so you gain a tempo while it
> retreats. When an enemy piece settles on a strong square near your king, ask
> whether a pawn can chase it before you finish developing."

### Case B — `h5`, −266cp (piece_safety) — **the generated why is FALSE**
`r2q1rk1/ppp1b1pp/4pp2/3p1b2/3PnB2/2PBP3/PP1N1PPP/R2Q1RK1 b - - 1 11`

> **GENERATED:** "h5 lets Bxe4 win your knight on e4. Nxf2 was better — it
> sacrifices your knight to break open the pawn shield in front of their king.
> The attack that follows is worth more than the pawn you lose."

**Verified — and the second half is wrong.** Nxf2 does **not** give check, and
it is not a sacrifice. The line is `Nxf2 Rxf2 Bxd3`, ending **+202 for Black**:
it wins material outright. The caption sells a material-winning combination as
a speculative attacking sacrifice, and tells the player they "lose a pawn" when
they gain a piece.

This is the dangerous failure class: fluent, confident, and false. A player who
believes it learns the wrong lesson about when to sacrifice.

> **GOLD:** "h5 leaves your knight on e4 with nothing defending it, and Bxe4
> simply takes it. Nxf2 was the move: after Rxf2 your bishop takes on d3 and you
> come out a piece ahead. Before making a quiet pawn move, look at every one of
> your pieces sitting undefended in the middle of the board."

### Case C — `Kc7`, −193cp (endgame) — **the recommendation is worse**
`8/pp1k4/8/3K4/PPP5/8/8/8 b - - 0 50`

> **GENERATED:** "Kc7 is a mistake. b6 was better. This spot got hard a few
> moves ago, around move 36. b6 holds on longer — but the real fix is earlier."

**Verified at depth 26:** `Kc7 = −1157`, `b6 = −8308`. The recommended move is
seven pawns worse than the move played. At depth 20 the two look equal (−559
each), which is why it shipped.

> **GOLD:** *(silence, or an honest statement of the position)* — "This endgame
> is already lost; there is no move here that saves it. The decision that
> mattered was earlier, around move 36."
>
> No recommendation at all. Recommending b6 here is worse than saying nothing.

### Case D — `Bxb6+`, −226cp (tactical_oversight) — **true, badly written**
`2k4r/pbBr1p2/1p1P4/8/P2nP2p/3B4/3N1PQ1/2R3K1 w - - 1 30`

> **GENERATED:** "Bxb6+ is an inaccuracy. Qg7 was better — it attacks the rook
> on h8. it wins the rook."

**Verified:** after Qg7 the h8 rook has **zero defenders** and one attacker, so
the claim is true. Engine: Bxb6+ +800, Qg7 +1104.

The defect is craft, not truth: a duplicated clause and a lower-case sentence
start. `pwc_coaching_lint` exists to catch exactly this and did not.

> **GOLD:** "Bxb6+ keeps a winning position, but Qg7 wins more — it attacks the
> rook on h8, and nothing defends it. When you are already winning, take the
> free material before you take the check."

### Case E — `e5`, −194cp (opening_knowledge)
`rnbqk2r/ppp1pp2/3p1bpp/8/3PP2P/2N5/PPP2PP1/R2QKBNR w KQkq - 0 7`

> **GENERATED:** "e5 is a mistake — it drops the pawn after dxe5. Qd2 was
> better. When two opening moves look equal, prefer the one that keeps your
> worst-placed piece useful."

The first clause is good. "Qd2 was better" then carries **no why**, and the
closing principle is generic — it is not about Qd2 and would fit any opening
card. That is the 17.4% defect and the principle-bank filler problem together.

> **GOLD:** "e5 pushes a pawn you cannot defend — dxe5 just takes it. Qd2 keeps
> the pawn and connects your rooks. When a pawn push gains no space and can be
> captured, count its defenders before you play it."

---

## 4. The authoring contract for a gold caption

Two rounds of correction from Mohit produced this shape.

> "your captions should just not mention what's on the board, it should mention
> the teaching concept for player to learn."

> "it should tell something to remember next time and is relatable ... Always
> look for your pieces should have defended before making any move ... I like
> 'a piece with no defender is a move for your opponent'."

**A gold caption is two sentences:**

1. **A principle they can remember** — short, relatable, no square names.
2. **The habit to run next move** — what they physically do before moving.

The principle alone is a proverb and changes nothing at the board. The habit
alone is a chore with no reason behind it. Together they are coaching.

```
  PRINCIPLE  A piece with no defender is a free move for your opponent.
  HABIT      Before every move, look over your own pieces and find the ones
             nothing is guarding — that's what they'll take while you're
             busy elsewhere.
```

Board narration — "h5 leaves your knight on e4 undefended, and Bxe4 takes it" —
is what the generator already does well. It is not what gold adds. Squares
appear only where they are unavoidable, and every factual claim is
Stockfish- or board-verified *before* it is written.

### The five cases as gold

**A — `O-O`** *(chasing an intruder)*
> An enemy piece camped near your king will not leave on its own, but a pawn can
> send it home — and that costs you nothing.
> When one settles in, look for the pawn that can hit it before you get on with
> your own plans.
>
> *Verified: g5 attacks f4; the bishop has five squares, all retreats.*

**B — `h5`** *(the loose piece)*
> A piece with no defender is a free move for your opponent.
> Before every move, look over your own pieces and find the ones nothing is
> guarding — that is what they take while you are busy elsewhere.
>
> *Verified: Nxf2 gives no check; Nxf2 Rxf2 Bxd3 = +202, it wins a piece.*

**C — `Kc7`** *(the game was lost earlier)*
> Not every lost position was lost on the move in front of you.
> When nothing you try works, go back and find the last move where something
> still did — that is the one worth studying.
>
> *Verified: Kc7 −1157 vs b6 −8308 at depth 26. No move is recommended here.*

**D — `Bxb6+`** *(free material before check)*
> When you are already winning, a check that wins nothing just hands the game
> back a move at a time.
> Before you check, scan for what is sitting undefended — take that first.
>
> *Verified: after Qg7 the h8 rook has zero defenders and one attacker.*

**E — `e5`** *(the unsupported push)*
> A pawn that moves past its own support is a pawn you have given away.
> Before you push, count what defends the square it lands on. If the answer is
> nothing, it is not a push, it is a gift.
>
> *Verified: dxe5 wins it; Qd2 = +17.*

### What this changes about the generator

Three of these concepts — loose piece, free material before check, unsupported
push — are **already detected**; the facts sit in `caption_facts` today. What
is missing is the pair of sentences, not the detection. That is authoring work
against detectors that already fire, which is exactly where Mohit says the
product is strong.

The fourth needs something the generator structurally lacks: permission to
recommend nothing.

## 5. Proposal

1. **Fix the false-why class first** (Case B). A wrong mechanism is worse than
   no mechanism, and it is invisible in every aggregate metric we have —
   the caption looks complete and scores well.
2. **Gate recommendations on a depth re-check** where the position is decided
   or mate is present — the 1.8%, all of them mate-adjacent.
3. **Fill `principle_cue`** — 98.5% empty is the single biggest gap, and the
   slot already renders on the card.
4. **Re-run `pwc_coaching_lint`** over rendered output; Case D should not ship.

Measured, not estimated. Every number here re-derives from production data on
2026-09-20: 4,378 captions, 220 re-verified recommendations, 6 hand-checked
positions.
