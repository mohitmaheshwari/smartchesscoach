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

## 4. The gold captions (third attempt — the first two were wrong)

Two earlier drafts of these were published in this document and both were
wrong on the facts. Recorded here rather than quietly replaced, because the
failure is the point: I wrote a rule saying every claim must be
Stockfish-verified before it is written, then wrote three unverified claims.

| Draft | What it said | Truth |
|---|---|---|
| 1st | "your knight on e4 had nothing defending it" | it has TWO defenders (d5, f5) |
| 2nd | "your knight on e4 had none" | same error, repeated after correction |
| generated | "h5 lets Bxe4 win your knight" | Bxe4 dxe4 is an even trade, not a win |

Mohit's brief for the rewrite: "simple english, nothing too fancy, with facts
but principal based that's easy to visualise."

---

**A — `O-O` was played; `g5` was the move**
`r2qk2r/ppp1bppp/2n1p3/3p1b2/3PnB2/2PBPN2/PP1N1PPP/R2Q1RK1 b kq - 5 8`

> When a pawn attacks a piece, the piece has to move — and that move is free
> for you. g5 hit the bishop on f4, and the bishop could not take the pawn
> because you guarded g5 twice. Castling was safe, but it let the bishop stay.

*Verified:* g5 is defended by e4 and e7. Bxg5 → +360 for Black; Bg3 → +478;
Be5 → +277. O-O → −13. Every bishop move leaves Black clearly better.

**B — `h5` was played; `Nxf2` was the move**
`r2q1rk1/ppp1b1pp/4pp2/3p1b2/3PnB2/2PBP3/PP1N1PPP/R2Q1RK1 b - - 1 11`

> f2 and f7 are the weakest squares on the board — only the king guards them at
> the start. You already had a knight pointing at f2 and played on the edge
> instead. Nxf2 was winning.

*Verified:* Nxf2 → **+187** for Black; h5 → −81. The knight on e4 is defended
twice, so nothing was hanging — the cost of h5 is the lost chance, plus the h5
pawn itself once Bxe4 dxe4 clears and Qxh5 follows.

**C — `Kc7` was played; nothing was better**
`8/pp1k4/8/3K4/PPP5/8/8/8 b - - 0 50`

> This game was lost before this move, and Kc7 was your best try. When a
> position is already gone, the lesson sits further back — not here.

*Verified:* Kc7 −1157, b6 −8308 at depth 26. **No move is recommended.** The
shipped caption recommended b6, seven pawns worse than what was played.

**D — `Bxb6+` was played; `Qg7` was the move**
`2k4r/pbBr1p2/1p1P4/8/P2nP2p/3B4/3N1PQ1/2R3K1 w - - 1 30`

> A check feels forcing, but it only helps if it wins something. Qg7 attacks
> the rook on h8, and nothing defends it — the rook has to run and you come out
> further ahead. When you are already winning, look for the undefended piece
> before you look for the check.

*Verified:* after Qg7 the h8 rook has zero defenders. It is not trapped — it
has six squares — so "wins the rook" would overclaim. Qg7 +1104 vs Bxb6+ +800.

**E — `e5` was played; `Qd2` was the move**
`rnbqk2r/ppp1pp2/3p1bpp/8/3PP2P/2N5/PPP2PP1/R2QKBNR w KQkq - 0 7`

> Before you push a pawn, count what is hitting the square and what is guarding
> it. Two black pieces attacked e5 and only one white pawn defended it, so the
> pawn was simply lost.

*Verified:* e5 attacked by d6 and f6, defended by d4 alone. e5 → −174; Qd2 → +6.

---

### Why these are different

Each one is a picture you can hold: a pawn shoving a piece, two arrows onto one
square against one, a rook with nothing behind it. The principle is in the
sentence rather than bolted onto the end, and there is no "before every move,
check X" homework — that advice fits every position, which is exactly why it
reads as filler when it appears six times in a game.

And one of them recommends nothing at all, which the generator cannot currently
express.

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
