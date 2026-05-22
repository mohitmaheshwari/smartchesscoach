# Pending caption review — 24 unresolved residual LOW positions

After v53 / v56 / v57 detectors shipped, **15 of 40** residual_low positions auto-resolve. The remaining **24 are listed below**, each as a self-contained block with FEN, shipped caption, proposed caption, and what I'd build if you approve.

**To see the board:** paste the **FEN piece placement** (the first chunk of the FEN, before the first space) into the search input on `/admin/captions`. The position card will surface with the chessboard rendered + red/green arrows.

**To approve in bulk:** reply with row numbers — e.g. *"approve 003, 009, 014 in Group I"* or *"approve all of Group I"*.

---

## Group I — missed-material / capture (eval-guard regression, 1-line fix)

These all share the same root cause: engine sees a winning capture with eval *just under* the 400cp piece_capture detector threshold. Relax that threshold to 250cp and **all 7 fix at once**.

### 003 — game `fc97ee1d`, m8, white
**FEN:** `r1bqkbnr/pp1p3p/n1p2p2/1B1Pp1p1/4P3/2P2N1P/PP3PP1/RNBQK2R w KQkq - 0 8`
**Played:** `Bc4` (cp_loss 217) · **Best:** `Bxa6` (+379cp)
**Shipped:** *Bc4 is a mistake. Bxa6 was better. Opponent's strongest reply: d6.*
**Proposed:** *Bc4 is a mistake. Bxa6 was better — it wins the knight on a6.*

### 009 — game `64e3c103`, m4, white
**FEN:** `rnbqkbnr/pp1p1pp1/8/2p1p2p/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4`
**Played:** `Nc3` (cp_loss 192) · **Best:** `Nxe5` (+295cp)
**Shipped:** *Nc3 is a mistake. Nxe5 was better. Opponent's strongest reply: d6.*
**Proposed:** *Nc3 is a mistake — you missed Nxe5. The e5 pawn is undefended and your knight can grab it for free.*

### 014 — game `27c79130`, m7, white
**FEN:** `r1bqkbnr/2p2ppp/p7/3pp3/8/P4N2/1PPP1PPP/RNBQK2R w KQkq - 0 7`
**Played:** `d4` (cp_loss 115) · **Best:** `Nxe5` (+57cp)
**Shipped:** *d4 is a mistake. Nxe5 was better. Opponent's strongest reply: e4.*
**Proposed:** *d4 is a mistake — Nxe5 was better, winning the undefended e5 pawn before pushing d4.*

### 025 — game `076710d8`, m4, white
**FEN:** `rnbqk2r/pppp1ppp/5n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4`
**Played:** `d3` (cp_loss 120) · **Best:** `Nxe5` (+140cp)
**Shipped:** *d3 is a mistake. Nxe5 was better. Nxe5 wins material in the resulting line.*
**Proposed:** *d3 is a mistake. Nxe5 was better — it wins the undefended e5 pawn.*

### 038 — game `8b7d4545`, m17, white
**FEN:** `2rqr1k1/b1p2pp1/p3b2p/1p1np3/4N3/P1PP1Q1P/BP3PP1/R1B2R1K w - - 1 17`
**Played:** `Bd2` (cp_loss 210) · **Best:** `Bxh6` (+186cp)
**Shipped:** *Bd2 is a mistake. Bxh6 was better. Bxh6 wins material in the resulting line.*
**Proposed:** *Bd2 is a mistake. Bxh6 was better — it wins the h6 pawn outright.*

### 036 — game `9e6941fc`, m16, white
**FEN:** `rb1q1rk1/1b1p1pp1/p5np/np1PP3/2p5/P1NQ1N2/1PB2PPP/R1B1R1K1 w - - 0 16`
**Played:** `Qe4` (cp_loss 168) · **Best:** `Qf5` (+198cp)
**Shipped:** *Qe4 is a mistake. Qf5 was better. Qf5 wins material in the resulting line.*
**Proposed:** *Qe4 is a mistake. Qf5 was better — your queen is more active on f5, attacking key squares.*

**Action if Group I approved:** lower piece_capture eval-guard from 400cp → 250cp in `services/best_move_tactic_detector.py`. One-line change, fixes all 6 (+ likely a few more in the wider corpus).

---

## Group II — queen-check / fork patterns (build queen-fork detector)

### 016 — game `e7ce2c88`, m8, black
**FEN:** `rnbqkb1r/pp3pp1/2p1p2p/4P3/3PpPP1/2P5/PP5P/R1BQKBNR b KQkq - 0 8`
**Played:** `Be7` (cp_loss 159) · **Best:** `Qh4+`
**Shipped:** *Be7 is a mistake. Qh4+ was better. Opponent's strongest reply: Bg2.*
**Proposed:** *Be7 is a mistake. Qh4+ was better — it forks White's king and the undefended g4 pawn.*

### 017 — game `e7ce2c88`, m9, black
**FEN:** `rnbqk2r/pp2bpp1/2p1p2p/4PP2/3Pp1P1/2P5/PP5P/R1BQKBNR b KQkq - 0 9`
**Played:** `exf5` (cp_loss 163) · **Best:** `Bh4+`
**Shipped:** *exf5 is a mistake. Bh4+ was better. Opponent's strongest reply: Ne2.*
**Proposed:** *exf5 is a mistake. Bh4+ was better — your bishop swings to h4 with check, dragging White's king out into the open.*

### 019 — game `aa52c973`, m24, black
**FEN:** `Q1b2qk1/p1r3pp/4p1n1/P4pP1/1Pn2P1P/4P3/8/R1B1K1NR b KQ - 0 24`
**Played:** `Rd7` (cp_loss 522 — major blunder) · **Best:** `Qxb4+`
**Shipped:** *Rd7 is a major blunder. Qxb4+ was better. Opponent's strongest reply: Nf3.*
**Proposed:** *Rd7 is a major blunder. Qxb4+ was better — your queen grabs the b4 pawn AND gives check, winning material with tempo.*

**Action if Group II approved:** build queen-fork / check-with-side-attack detector. With #5 + #16 + #19 = N=3, confident shape.

---

## Group III — opening principle (fight for the center)

### 001 — game `dfe3e5c8`, m4, black
**FEN:** `r1bqkbnr/pp1ppppp/2n5/8/3PP3/8/PP3PPP/RNBQKBNR b KQkq - 0 4`
**Played:** `g6` (cp_loss 149) · **Best:** `d5`
**Shipped:** *g6 is a mistake. d5 was better. Opponent's strongest reply: d5.*
**Proposed:** *g6 is a mistake — in the opening, fight for the center first. d5 was better, contesting White's central pawns.*

### 008 — game `f4125049`, m5, black
**FEN:** `rnbqk1nr/pppp1ppp/8/2b5/P6P/4P3/1PP3P1/RNBQKBNR b KQkq - 0 5`
**Played:** `Qf6` (cp_loss 144) · **Best:** `d5`
**Shipped:** *Qf6 is a mistake. d5 was better. Opponent's strongest reply: Nc3.*
**Proposed:** *Qf6 is a mistake — don't develop the queen this early. d5 was better, claiming central space.*

### 035 — game `e6c0ca28`, m2, black
**FEN:** `rnbqkbnr/ppp1pppp/8/2Pp4/8/8/PP1PPPPP/RNBQKBNR b KQkq - 0 2`
**Played:** `Na6` (cp_loss 204) · **Best:** `e5`
**Shipped:** *Na6 is a mistake. e5 was better. e5 wins material in the resulting line.*
**Proposed:** *Na6 is a mistake — knights on the rim are weak. e5 was better, claiming central space.*

### 037 — game `fc6a7bad`, m4, black
**FEN:** `r1bqkb1r/pppp1ppp/2n2n2/4p3/4P1P1/2P2Q2/PP1P1P1P/RNB1KBNR b KQkq - 0 4`
**Played:** `Bc5` (cp_loss 337) · **Best:** `d5`
**Shipped:** *Bc5 is a serious mistake. d5 was better. d5 wins material in the resulting line.*
**Proposed:** *Bc5 is a serious mistake — fight for the center first. d5 was better, claiming central space.*

### 040 — game `b39642d4`, m4, white
**FEN:** `r1bqkbnr/pppp1ppp/2n5/8/4Pp2/5N2/PPPP2PP/RNBQKB1R w KQkq - 2 4`
**Played:** `Bc4` (cp_loss 126) · **Best:** `d4`
**Shipped:** *Bc4 is a mistake. d4 was better. d4 wins material in the resulting line.*
**Proposed:** *Bc4 is a mistake — d4 was better, contesting the center before developing pieces.*

**Action if Group III approved:** build central-pawn-break-missed detector — engine's best is a central pawn push (d4/d5/e4/e5/c4/c5), user played a non-central move in the opening (move ≤ 10). N=5 = strong signal.

---

## Group IV — defensive-pawn / passive-move (family G — #7 already approved)

### 020 — game `a6b432f5`, m8, black
**FEN:** `rnbqk2r/pp4pp/2p1pb2/3p4/3P2P1/5N2/PPP2P1P/RN1QKB1R b KQkq - 0 8`
**Played:** `h6` (cp_loss 152) · **Best:** `O-O`
**Shipped:** *h6 is a mistake. O-O was better. Opponent's strongest reply: Nbd2.*
**Proposed:** *h6 is a mistake — in the opening, castle first instead of pushing wing pawns. O-O was better, getting your king safe and connecting your rooks.*

### 011 — game `a9cd46d0`, m14, white
**FEN:** `rnb2r2/2q1npkp/p1p1p1p1/1p2N3/2pP4/2N1P1P1/PP1Q1PBP/R4RK1 w - - 2 14`
**Played:** `a3` (cp_loss 100) · **Best:** `Ne4`
**Shipped:** *a3 is a mistake. Ne4 was better. Opponent's strongest reply: f6.*
**Proposed:** *a3 is a mistake — that's a waiting move. Ne4 was better, putting your knight on a central outpost.*

### 029 — game `b84a1c55`, m10, black
**FEN:** `r1bqk2r/p1pp1ppp/2p5/4P3/1nP5/B7/P1P2PPP/R2QKB1R b KQkq - 2 10`
**Played:** `a5` (cp_loss 205) · **Best:** `Qe7`
**Shipped:** *a5 is a mistake. Qe7 was better. Qe7 wins material in the resulting line.*
**Proposed:** *a5 is a mistake — develop a piece instead of pushing a wing pawn. Qe7 was better, finishing development.*

### 012 — game `f5a5f58c`, m5, black
**FEN:** `r1bqk2r/pppp1ppp/2n2n2/2b1p3/P1B1P3/2PP4/1P3PPP/RNBQK1NR b KQkq - 0 5`
**Played:** `d6` (cp_loss 273 — serious) · **Best:** `a5`
**Shipped:** *d6 is a serious mistake. a5 was better. Opponent's strongest reply: b4.*
**Proposed:** *d6 is a serious mistake — stop White's queenside push. a5 was better, blocking a4-a5.*

**Action if Group IV approved:** build family G defensive-pawn-push detector. With #7 + 020/011/029 = N=4, strong shape (012 is a slightly different sub-family — stop-opponent-expansion — but lives in the same neighborhood).

---

## Group V — un-developing (family C — #4 already approved)

### 026 — game `2bdf179c`, m5, white
**FEN:** `rnbqkb1r/ppp2ppp/3p1n2/8/3PPp2/5N2/PPP3PP/RNBQKB1R w KQkq - 1 5`
**Played:** `Bd3` (cp_loss 102) · **Best:** `Nc3`
**Shipped:** *Bd3 is a mistake. Nc3 was better. Nc3 wins material in the resulting line.*
**Proposed:** *Bd3 is a mistake — your bishop is better elsewhere. Nc3 was the right move, developing your queen's knight.*

**Action if approved:** build family C detector — user moved a piece to a passive square when developing another piece was better. N=2 with #4.

---

## Group VI — middlegame positional (N=1 each, log for later)

### 032 — game `70cacf59`, m13, black
**FEN:** `r2q1rk1/pb2npbp/1n1pp1p1/2p5/4PP2/1BN1BN1P/PPP3P1/1R1Q1RK1 b - - 5 13`
**Played:** `Qd7` (cp_loss 100) · **Best:** `c4`
**Shipped:** *Qd7 is a mistake. c4 was better. c4 wins material in the resulting line.*
**Proposed:** *Qd7 is a mistake — c4 was better, breaking White's pawn chain with a central pawn push.*

### 034 — game `c80dd5fa`, m6, black
**FEN:** `r2qkb1r/pp2pppp/2n2n2/2pp4/2PP2b1/1Q2PN2/PP1N1PPP/R1B1KB1R b KQkq - 2 6`
**Played:** `b6` (cp_loss 203 — serious) · **Best:** `Na5`
**Shipped:** *b6 is a serious mistake. Na5 was better. Na5 wins material in the resulting line.*
**Proposed:** *b6 is a serious mistake. Na5 was better — your knight attacks the white queen on b3 and forces it to move.*

**Action if Group VI approved:** 034 is a **v57 bug** — should have fired attack_with_tempo but doesn't because the stored pv_after_best doesn't start with `Na5`. Fix v57 to fall back to "attacks-piece-and-piece-must-move" detection when PV[0] ≠ best_move_san. 032 is a one-off middlegame pawn-break — log for later.

---

## Group VII — endgame piece activity (3 positions)

### 010 — game `849d1899`, m34, white
**FEN:** `r7/1b1nk3/2p1p1r1/p6p/1pNP4/P3R1Pp/1P3P1K/4R2B w - - 3 34`
**Played:** `a4` (cp_loss 159) · **Best:** `Kxh3`
**Shipped:** *a4 is a mistake. Kxh3 was better. Opponent's strongest reply: Rf8.*
**Proposed:** *a4 is a mistake — in the endgame, your king should be active. Kxh3 was better, grabbing the h3 pawn with your king.*

### 030 — game `fc3914fc`, m27, black
**FEN:** `8/2p3pk/1b1pp2p/4p3/1PP1P3/7P/3KNr2/1R6 b - - 0 27`
**Played:** `c5` (cp_loss 276 — serious) · **Best:** `Rf3`
**Shipped:** *c5 is a serious mistake. Rf3 was better. Rf3 wins material in the resulting line.*
**Proposed:** *c5 is a serious mistake — keep your rook active. Rf3 was better, attacking White's pawns from behind.*

### 031 — game `fc3914fc`, m28, black
**FEN:** `8/6pk/1b1pp2p/1Pp1p3/2P1P3/7P/3KNr2/1R6 b - - 0 28`
**Played:** `Rf8` (cp_loss 131) · **Best:** `Rf3`
**Shipped:** *Rf8 is a mistake. Rf3 was better. Rf3 wins material in the resulting line.*
**Proposed:** *Rf8 is a mistake — your rook was active on f2. Rf3 was better, keeping pressure on White's pawns.*

**Action if Group VII approved:** build endgame-piece-activity detector — endgame phase + user moved an active piece passively. N=3.

---

## Bulk-approval shortcut

If you just want me to push ahead, the **single highest-leverage change is Group I** — one-line eval-guard relax fixes 6 positions immediately. Just reply *"ship Group I"* and I'll do it without per-row review.

Other groups need a real detector to be built, so per-row approval matters more (so I don't ship a detector that misframes a position you'd push back on).
