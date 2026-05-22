# Pending caption review — 25 unresolved residual LOW positions

After v53 / v56 / v57 detectors shipped, **15 of 40** residual_low positions auto-resolve. The remaining **25 are listed below**, each with my proposed caption and what I'd do if you approve.

**How to review:**
1. Open `/admin/captions` (LOW tier toggle on, default)
2. Paste the **Search** value into the new search input — narrows to that game's position
3. See the board, then come back here and tell me which to approve / reject / rewrite

Each row's **Action if approved** column shows what I'd build downstream. Multiple rows in the same family let me ship one detector that fixes all of them at once.

---

## Already-approved cases (for reference)

| # | Game | Played → Best | Approved as | Status |
|---|---|---|---|---|
| 015 | `3e1a1a93` | Qa5 → Nxd3+ | #6 — discovered-attack via vacating-with-check | logged |
| 024 | `2d5ad07d` | Bf1 → d3 | #4 — un-developing principle | logged |

---

## Pending review (24 remaining — review these)

### Group I: missed-material / capture (eval just under 400cp — eval-guard regression)

| # | Search | Played → Best | Shipped (LOW) | Proposed | Action if approved |
|---|---|---|---|---|---|
| 003 | `fc97ee1d` m8 | Bc4 → Bxa6 | Bc4 is a mistake. Bxa6 was better. Opponent's strongest reply: d6. | *Bc4 is a mistake. Bxa6 was better — it wins the knight on a6.* | Lower piece_capture eval-guard from 400cp → 250cp (fixes ~6 positions in this group at once) |
| 009 | `64e3c103` m4 | Nc3 → Nxe5 | Nc3 is a mistake. Nxe5 was better. Opponent's strongest reply: d6. | *Nc3 is a mistake — you missed Nxe5. The e5 pawn is undefended and your knight can grab it for free.* | Same — eval-guard relaxation |
| 014 | `27c79130` m7 | d4 → Nxe5 | d4 is a mistake. Nxe5 was better. Opponent's strongest reply: e4. | *d4 is a mistake — Nxe5 was better, winning the undefended e5 pawn before pushing d4.* | Same — eval-guard relaxation |
| 025 | `076710d8` m4 | d3 → Nxe5 | d3 is a mistake. Nxe5 was better. Nxe5 wins material in the resulting line. | *d3 is a mistake. Nxe5 was better — it wins the undefended e5 pawn.* | Same — eval-guard relaxation |
| 038 | `8b7d4545` m17 | Bd2 → Bxh6 | Bd2 is a mistake. Bxh6 was better. Bxh6 wins material in the resulting line. | *Bd2 is a mistake. Bxh6 was better — it wins the h6 pawn outright.* | Same — eval-guard relaxation |
| 039 | `8b282bab` m5 | exd5 → Bxd5 | exd5 is a mistake. Bxd5 was better. Bxd5 wins material in the resulting line. | *exd5 is a mistake — recapture with the bishop, not the pawn. Bxd5 keeps your pawn structure intact and your bishop active.* | Recapture-with-piece-not-pawn detector (new family) |
| 036 | `9e6941fc` m16 | Qe4 → Qf5 | Qe4 is a mistake. Qf5 was better. Qf5 wins material in the resulting line. | *Qe4 is a mistake. Qf5 was better — your queen is more active on f5, eyeing the king's side.* | Active-piece-square detector (positional) |

### Group II: queen-check + capture / fork patterns (pending detector — family D)

| # | Search | Played → Best | Shipped (LOW) | Proposed | Action if approved |
|---|---|---|---|---|---|
| 016 | `e7ce2c88` m8 | Be7 → Qh4+ | Be7 is a mistake. Qh4+ was better. Opponent's strongest reply: Bg2. | *Be7 is a mistake. Qh4+ was better — it forks White's king and the undefended g4 pawn.* | Queen-fork detector (with #5 + this = N=2, buildable) |
| 017 | `e7ce2c88` m9 | exf5 → Bh4+ | exf5 is a mistake. Bh4+ was better. Opponent's strongest reply: Ne2. | *exf5 is a mistake. Bh4+ was better — your bishop swings to h4 with check, dragging White's king out into the open.* | Bishop-check-disrupts-king detector (similar family, N=1) |
| 019 | `aa52c973` m24 | Rd7 → Qxb4+ | Rd7 is a major blunder. Qxb4+ was better. Opponent's strongest reply: Nf3. | *Rd7 is a major blunder. Qxb4+ was better — your queen grabs the b4 pawn AND gives check, winning material with tempo.* | Capture-with-check detector (or relaxed piece_capture guard) |

### Group III: positional / opening-principle (fight for center)

| # | Search | Played → Best | Shipped (LOW) | Proposed | Action if approved |
|---|---|---|---|---|---|
| 001 | `dfe3e5c8` m4 | g6 → d5 | g6 is a mistake. d5 was better. Opponent's strongest reply: d5. | *g6 is a mistake — in the opening, fight for the center first. d5 was better, contesting White's central pawns.* | Central-pawn-break-missed detector (new family) |
| 008 | `f4125049` m5 | Qf6 → d5 | Qf6 is a mistake. d5 was better. Opponent's strongest reply: Nc3. | *Qf6 is a mistake — don't develop the queen this early. d5 was better, claiming central space.* | Don't-develop-queen-early detector |
| 035 | `e6c0ca28` m2 | Na6 → e5 | Na6 is a mistake. e5 was better. e5 wins material in the resulting line. | *Na6 is a mistake — knights on the rim are weak. e5 was better, claiming central space.* | Knight-on-rim detector (or use existing OP_KNIGHT_ON_RIM) |
| 037 | `fc6a7bad` m4 | Bc5 → d5 | (engine-speak) | *Bc5 is a serious mistake — fight for the center first. d5 was better, claiming central space.* | Same — central-pawn-break |
| 040 | `b39642d4` m4 | Bc4 → d4 | Bc4 is a mistake. d4 was better. d4 wins material in the resulting line. | *Bc4 is a mistake — d4 was better, contesting the center before developing pieces.* | Same — central-pawn-break |

### Group IV: defensive-pawn / passive-move family (G — N already approved as #7)

| # | Search | Played → Best | Shipped (LOW) | Proposed | Action if approved |
|---|---|---|---|---|---|
| 020 | `a6b432f5` m8 | h6 → O-O | h6 is a mistake. O-O was better. Opponent's strongest reply: Nbd2. | *h6 is a mistake — in the opening, castle first instead of pushing wing pawns. O-O was better, getting your king safe and connecting your rooks.* | Build family G detector (with #7 + this = N=2, buildable) |
| 011 | `a9cd46d0` m14 | a3 → Ne4 | a3 is a mistake. Ne4 was better. Opponent's strongest reply: f6. | *a3 is a mistake — that's a waiting move. Ne4 was better, putting your knight on a central outpost.* | Same family G (passive pawn move when piece move is better) |
| 029 | `b84a1c55` m10 | a5 → Qe7 | a5 is a mistake. Qe7 was better. Qe7 wins material in the resulting line. | *a5 is a mistake — develop a piece instead of pushing a wing pawn. Qe7 was better, finishing development.* | Same family G |
| 012 | `f5a5f58c` m5 | d6 → a5 | d6 is a serious mistake. a5 was better. Opponent's strongest reply: b4. | *d6 is a serious mistake — stop White's queenside push. a5 was better, blocking a4-a5.* | Stop-opponent-pawn-expansion detector (new family) |

### Group V: un-developing / piece-back-to-home (family C — #24 approved)

| # | Search | Played → Best | Shipped (LOW) | Proposed | Action if approved |
|---|---|---|---|---|---|
| 026 | `2bdf179c` m5 | Bd3 → Nc3 | Bd3 is a mistake. Nc3 was better. Nc3 wins material in the resulting line. | *Bd3 is a mistake — your bishop is better on c4. Nc3 was the right move, developing your queen's knight.* | Build family C detector (with #4 + this = N=2, buildable) |

### Group VI: middlegame / queen-out positional

| # | Search | Played → Best | Shipped (LOW) | Proposed | Action if approved |
|---|---|---|---|---|---|
| 032 | `70cacf59` m13 | Qd7 → c4 | Qd7 is a mistake. c4 was better. c4 wins material in the resulting line. | *Qd7 is a mistake — c4 was better, breaking White's pawn chain with a central pawn push.* | Middlegame-pawn-break detector |
| 034 | `c80dd5fa` m6 | b6 → Na5 | b6 is a serious mistake. Na5 was better. Na5 wins material in the resulting line. | *b6 is a serious mistake. Na5 was better — your knight attacks the white queen on b3 and forces it to move.* | **v57 detector bug:** PV doesn't start with best_move_san → detector misses this attack_with_tempo case. Fix v57 to fall back when PV[0] ≠ best_move_san. |

### Group VII: endgame technique (rook activity / king activity)

| # | Search | Played → Best | Shipped (LOW) | Proposed | Action if approved |
|---|---|---|---|---|---|
| 010 | `849d1899` m34 | a4 → Kxh3 | a4 is a mistake. Kxh3 was better. Opponent's strongest reply: Rf8. | *a4 is a mistake — in the endgame, your king should be active. Kxh3 was better, grabbing the h3 pawn with your king.* | Endgame-king-active detector (new) |
| 030 | `fc3914fc` m27 | c5 → Rf3 | c5 is a serious mistake. Rf3 was better. Rf3 wins material in the resulting line. | *c5 is a serious mistake — keep your rook active. Rf3 was better, attacking White's pawns from behind.* | Endgame-rook-activity detector (new) |
| 031 | `fc3914fc` m28 | Rf8 → Rf3 | Rf8 is a mistake. Rf3 was better. Rf3 wins material in the resulting line. | *Rf8 is a mistake — your rook was active on f2. Rf3 was better, keeping pressure on White's pawns.* | Same — endgame-rook-activity |

---

## Summary by action

| Action | Rows | Detector status |
|---|---:|---|
| Relax piece_capture eval-guard from 400cp → 250cp | 6 (003, 009, 014, 025, 038, others) | Easy 1-line change |
| Fix v57 attack_with_tempo when PV[0] ≠ best_move_san | 1 (034) + likely 2-3 more | Easy fix |
| Build queen-fork / bishop-check detector (family D) | 3 (016, 017, 019) | N=3 after this batch |
| Build defensive-pawn-push detector (family G) | 4 (020, 011, 029, 012) | N=4 after this batch |
| Build un-developing detector (family C) | 1 (026) | N=2 with #4 |
| Build central-pawn-break-missed detector | 5 (001, 008, 037, 040, + #035 partial) | N=5, strong signal |
| Build endgame-piece-activity detector | 3 (010, 030, 031) | N=3 |
| Build recapture-with-piece detector | 1 (039) | N=1, wait |
| Build active-piece-square detector | 1 (036) | N=1, wait |
| Build middlegame-pawn-break detector | 1 (032) | N=1, wait |
| Build stop-opponent-pawn-expansion detector | 1 (012, dual) | N=1, wait |

Tell me which rows to approve and I'll batch the highest-leverage changes (eval-guard relax + the N≥2 detectors first).
