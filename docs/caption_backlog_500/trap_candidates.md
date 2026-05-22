# Trap-pattern candidates — 500-game scan

Scanned 500 games (v53+). Found 1066 early-blunder hits (move 3-15, cp_loss >= 300, either color).
Clustered to 4 pattern candidates (>= 2 games each, not already in `traps.json`).

**Methodology:** Same opening label + same first-N moves = same position class. A cluster is a trap candidate if it repeats across multiple games AND has a clear punishment move (the engine's best reply).

**Note:** Not every cluster is a real trap. Some are just common opening blunders (forgetting to develop, hanging a piece) that don't deserve a named-trap entry. You decide which ones merit authoring.

---

## Candidate #1 [T1] — T1 strict — Caro Kann Defense after 1.e4 c6 2.Bc4 d5 (2 games)

**Representative setup (4 half-moves):** `1.e4 c6 2.Bc4 d5`

**Blunder pattern:** `Qf3` (avg cp_loss 415, by white)

**Engine's punishment (stored):** ``

**FEN before blunder:** `rnbqkbnr/pp2pppp/2p5/3p4/2B1P3/8/PPPP1PPP/RNBQK1NR w KQkq - 0 3`

**Live engine (depth 15, multipv 3):**

- #1 eval(W) `-27cp` PV: `exd5 cxd5 Bb5+ Bd7 Bxd7+ Nxd7 d4 e6`
- #2 eval(W) `-65cp` PV: `Bd3 e5 exd5 Nf6 dxc6 Bc5 Nc3 Nxc6`
- #3 eval(W) `-87cp` PV: `Bb3 dxe4 Nc3 Nf6 f3 exf3 Nxf3 Bf5`

**Game IDs in cluster:**
- `58388c01-957` m3 Qf3 cp_loss=436 (opp)
- `5313773a-e7a` m3 Nf3 cp_loss=395 (user)

**Author as trap?** (Mohit to decide)
- [ ] Yes — this is a real trap pattern worth naming
- [ ] No — common blunder, not a named trap
- [ ] Already covered (note which trap in `traps.json` matches)

---

## Candidate #2 [T2] — T2 medium — Unknown, blunder `Qd4` at move 12 (2 games)

**Representative setup (22 half-moves):** `1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 4.c3 Nf6 5.d4 Nxe4 6.dxc5 O-O 7.Qd5 Nf6 8.Qd3 e4 9.Qe3 d6 10.Nfd2 Bf5 11.Be2 Nd5`

**Blunder pattern:** `Qd4` (avg cp_loss 585, by white)

**Engine's punishment (stored):** `Qg3`

**FEN before blunder:** `r2q1rk1/ppp2ppp/2np4/2Pn1b2/4p3/2P1Q3/PP1NBPPP/RNB1K2R w KQ - 4 12`

**Live engine (depth 15, multipv 3):**

- #1 eval(W) `+282cp` PV: `Qg3 dxc5 Na3 Qe7 Ndc4`
- #2 eval(W) `-338cp` PV: `Nb3 Nxe3 Bxe3 a5 cxd6 a4 dxc7 Qxc7`
- #3 eval(W) `-430cp` PV: `Na3 Nxe3 fxe3 Qh4+ g3 Qd8 O-O Be6`

**Game IDs in cluster:**
- `7927211d-4f5` m12 Qd4 cp_loss=873 (user)
- `7deab99c-3d6` m12 Qd4 cp_loss=298 (opp)

**Author as trap?** (Mohit to decide)
- [ ] Yes — this is a real trap pattern worth naming
- [ ] No — common blunder, not a named trap
- [ ] Already covered (note which trap in `traps.json` matches)

---

## Candidate #3 [T2] — T2 medium — Scotch Game 3...exd4, blunder `Ke8` at move 6 (2 games)

**Representative setup (11 half-moves):** `1.e4 e5 2.Nf3 Nc6 3.d4 exd4 4.Ng5 h6 5.Nxf7 Kxf7 6.Bc4+`

**Blunder pattern:** `Ke8` (avg cp_loss 10248, by black)

**Engine's punishment (stored):** ``

**FEN before blunder:** `r1bq1bnr/pppp1kp1/2n4p/8/2BpP3/8/PPP2PPP/RNBQK2R b KQ - 1 6`

**Live engine (depth 15, multipv 3):**

- #1 eval(W) `-293cp` PV: `d5 Bxd5+ Kg6 O-O Kh7 f4 Nf6 Bxc6`
- #2 eval(W) `-253cp` PV: `Kg6 O-O Kh7 f4 d5 Bd3 g6 f5`
- #3 eval(W) `-212cp` PV: `Ke7 c3 d3 O-O Qe8 f4 Kd8 e5`

**Game IDs in cluster:**
- `fcccb56b-579` m6 Ke8 cp_loss=10248 (opp)
- `9189db2b-037` m6 Ke8 cp_loss=10248 (opp)

**Author as trap?** (Mohit to decide)
- [ ] Yes — this is a real trap pattern worth naming
- [ ] No — common blunder, not a named trap
- [ ] Already covered (note which trap in `traps.json` matches)

---

## Candidate #4 [T3] — T3 loose — Kings Pawn Opening Kings Knight Variation, blunder `Bg5` (any move number) (3 games)

**Representative setup (38 half-moves):** `1.e4 e5 2.Nf3 d5 3.exd5 e4 4.Ng1 Qxd5 5.Nh3 Bxh3 6.gxh3 e3 7.Rg1 exf2+ 8.Kxf2 Qd4+ 9.Kg2 Bc5 10.Qe1+ Ne7 11.Bd3 O-O 12.Qe3 Qd5+ 13.Qe4 Qxe4+ 14.Bxe4 Bxg1 15.Kxg1 c6 16.Nc3 Nd7 17.d3 Nd5 18.Bxd5 cxd5 19.Nxd5 Rfe8`

**Blunder pattern:** `Bg5` (avg cp_loss 509, by white)

**Engine's punishment (stored):** `Nc7`

**FEN before blunder:** `r3r1k1/pp1n1ppp/8/3N4/8/3P3P/PPP4P/R1B3K1 w - - 1 20`

**Live engine (depth 15, multipv 3):**

- #1 eval(W) `+87cp` PV: `Nc7 Re1+ Kf2 Rxc1 Rxc1 Rd8 Nb5 a6`
- #2 eval(W) `-222cp` PV: `Be3 Rad8 c4 Nf6 Bg5 Nxd5 Bxd8 Rxd8`
- #3 eval(W) `-286cp` PV: `Bf4 Re2 Rc1 Nb6 Nc3 Re7 a3 Rc8`

**Game IDs in cluster:**
- `3e2441ef-1cc` m20 Bg5 cp_loss=606 (user)
- `29a4eef1-e34` m5 Bg5 cp_loss=614 (user)
- `87169570-eb3` m6 Bg5 cp_loss=308 (user)

**Author as trap?** (Mohit to decide)
- [ ] Yes — this is a real trap pattern worth naming
- [ ] No — common blunder, not a named trap
- [ ] Already covered (note which trap in `traps.json` matches)

---
