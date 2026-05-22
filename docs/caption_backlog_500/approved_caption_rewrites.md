# Approved caption rewrites — voice reference for future detector/template work

Captions Mohit approves during FEN-review sessions live here. Each entry pairs
the shipped v55 caption with the approved-style rewrite + notes. Once we have
5-10 examples, we'll have enough pattern to propose a single detector change
or template rewrite covering the family.

**Voice rules so far** (from approvals on 2026-05-22):
- Name what the engine's best move DOES mechanically ("kicks the bishop", "hits with tempo"), not just the resulting eval ("wins material").
- Name the consequence concretely: which square / which piece / which line opens.
- Avoid chess jargon — say "your g2 bishop" not "your fianchetto bishop". Target audience is 600-1500 (see [feedback_caption_voice_avoid_chess_jargon](../../../.claude/projects/c--Users-MIISCO-smartchesscoach/memory/feedback_caption_voice_avoid_chess_jargon.md)).

---

## #1 — game 6569e93f-a90 m6 Qe2

**FEN:** `rnbqk1nr/pppp1ppp/8/2b1P3/5p2/2N2N2/PPPP2PP/R1BQKB1R w KQkq - 1 6`

**Engine PV:** `d4 Bb4 Bxf4 d5 Bd3 Bxc3+` (+225cp)

**Shipped (LOW, `why_user_missed_material`):**
> Qe2 is a mistake. d4 was better. d4 wins material in the resulting line.

**Approved rewrite:**
> Qe2 is a mistake. d4 was better — it hits the bishop on c5 with tempo and lets you recapture f4.

**Why this works:** Names two things the move accomplishes (hits bishop + opens line to f4). The player sees "d4 with tempo" and learns the mechanism, not just the verdict.

---

## #2 — game 461ece5c-604 m11 e4

**FEN:** `r2qk2r/1ppn1p2/p2bpp1p/5b2/2pP4/2N2NP1/PP2PPBP/R2QR1K1 w kq - 0 11`

**Engine PV:** `Nh4 Bh7 Bxb7 Rb8 Bxa6 Rxb2` (+155cp)

**Shipped (LOW, `why_user_missed_material`):**
> e4 is a mistake. Nh4 was better. Nh4 wins material in the resulting line.

**Approved rewrite:**
> e4 is a mistake. Nh4 was better — it kicks the bishop off the long diagonal, so your g2 bishop can take on b7.

**Why this works:** Names the mechanism (kick), the resource being created (long diagonal opens up), and the target (b7). Avoids "fianchetto" — says "g2 bishop" concretely.

---

## #8 — same-piece-better-square positional choice (new pattern family)

**FEN:** `rb1q1rk1/1b1p1pp1/p5np/np1PP3/2p5/P1NQ1N2/1PB2PPP/R1B1R1K1 w - - 0 16`

**Engine PV:** `Qf5 Nb3 Rb1 Nc5 h4 Nd3` (+198cp)

**Shipped v55 (LOW, `why_user_missed_material`):**
> Qe4 is a mistake. Qf5 was better. Qf5 wins material in the resulting line.

**Approved rewrite:**
> Qe4 is a mistake. Qf5 was better — both squares attack Black's knight on g6, but Qf5 also eyes the d7 pawn. Pick the queen square that attacks more.

**Why this works:** Both candidate moves are similar-looking queen moves. The lesson isn't "more active" (vague) — it's two-attacks-vs-one. Names what's the same (g6 attack), what's different (d7 attack), and the universal principle (pick the square that attacks more). This is teachable to 600-1500.

**Geometry:**
- Qd3 → Qe4: attacks g6 via d3-e4-f5-g6 diagonal... wait, **both** queen moves attack g6 via diagonals (Qe4 via e4-f5-g6, Qf5 via f5-g6 single step).
- Qf5 additionally attacks d7 via f5-e6-d7 diagonal (e6 empty).
- So Qf5 = Qe4's attacks PLUS d7. Strictly more work from the same piece.

**New pattern family (H): same-piece-better-square positional choice.** Distinct from:
- attack_with_tempo (engine best attacks a piece that forces retreat — Group I/II)
- queen-fork (king + undefended target)
- un-developing (piece going home)

Here both moves are valid piece moves; the teaching is *between two reasonable destinations, the engine's choice attacks one more target*. Detector spec (when N≥2):
- User and engine move the same piece type
- Engine's destination attacks N enemy targets
- User's destination attacks M < N targets
- The teaching names the shared attack + the engine's extra

N=1 so far — log for later, don't build yet.

---

## #7 — defensive pawn push instead of developing (new pattern family)

**FEN:** `rnb1kb1r/ppp1ppp1/1q3n2/7p/3P4/2N1BN2/PPP2PPP/R2QKB1R w KQkq - 2 7`

**Engine PV (top 3, all within ~12cp):** `Bd3 c6 O-O g6 Qd2 Bg7 Rfe1 Qxb2` (+184cp) — Bd3 / Qd2 / Bc4 all roughly equivalent developing moves.

**Shipped v55 (LOW, `why_user_reply`):**
> b3 is a mistake. Bd3 was better. Opponent's strongest reply: Bg4.

**Approved rewrite:**
> b3 is a mistake — in the opening, don't waste tempo defending a pawn. Bd3 was better, developing your bishop and preparing to castle.

**Why this works:** Leads with the universal principle (develop, don't defend in opening), names the better move + what it accomplishes (develops + prepares castling). Keeps the lesson clean — doesn't dive into Bg4 pin complications. Right for the 600-1500 audience who needs the habit reinforced, not the tactical analysis.

**Geometry:** Black played early `...Qb6` eyeing b2. b3 by white defends but uses a tempo that should go to a piece (Bd3 develops AND prepares O-O). The +184cp positional advantage from white's lead in development is worth more than the b2 pawn — even after Qxb2 in the engine PV, white is still better.

**New pattern family (G): defensive-pawn-push-instead-of-developing.** Detector spec (when we have 2-3 more examples):
- Opening phase (move ≤ 15)
- User played a pawn move (single-square advance, no capture)
- Engine's best move was a piece move that develops OR castles
- User's pawn move was defending a piece/pawn under attack
- cp_loss in mistake tier (100-249)

Different from attack_with_tempo, clearance_then_check, queen-fork, and discovered-attack — this one is **purely principle-based**, no tactical pattern. Sits in the same family as the existing `R_PROMOTED_principle` variants (`OP_FINISH_DEVELOPMENT`, `OP_CLAIM_CENTER`) but for the specific anti-pattern of "defending a pawn move when you should have developed."

---

## #6 — game 3e1a1a93-704 m11 Qa5 (discovered-attack via vacating-with-check)

**FEN:** `r2qkb1r/pp3p1p/2p2np1/3p4/1n1P3N/BPNP2P1/P4P1P/R2QK2R b KQkq - 0 11`

**Engine PV:** `Nxd3+ Qxd3 Bxa3 O-O O-O Nf3` (eval -231cp = +231cp for black)

**Shipped v55 (LOW, `why_user_reply`):**
> Qa5 is a mistake. Nxd3+ was better. Opponent's strongest reply: Bb2.

(Note: the shipped opp_reply "Bb2" doesn't even match the real PV's `Qxd3` — secondary bug in the engine-speak fallback that picks the wrong opp reply.)

**Approved rewrite:**
> Qa5 is a mistake. Nxd3+ was better — it grabs a pawn with check AND clears the way for your bishop to take on a3.

**Why this works:** Names the dual function of the moved piece (capture + check) AND the discovered-attack consequence (Bxa3) without using "discovered attack" jargon. Plain "clears the way" describes the geometric vacating move.

**Geometry:** Knight on b4 was blocking its own bishop's diagonal (f8-e7-d6-c5-b4-a3). The bishop on a3 is undefended. Nxd3+ does three things at once: (1) wins the d3 pawn, (2) gives check via knight-on-d3-attacks-e1, (3) vacates b4 so the bishop diagonal opens. After Qxd3 (forced recapture), Bxa3 collects the bishop.

**New pattern family (F): discovered-attack-via-vacating-with-check.** Distinct from:
- #5 queen fork (one piece attacks two targets directly from the same square)
- attack_with_tempo (kicks a piece, forces retreat)
- clearance_then_check (slider clears + can swing to check square — moved piece is the line opener, not the attacker)

Here the MOVED piece (knight) provides check + capture AT ITS DESTINATION, while VACATING enables a SEPARATE piece's discovered attack. The geometry-distinct family. Detector design (when we have 2-3 more examples): check that engine's best move (a) gives check, (b) vacates a square that was blocking own slider's line to opp undefended piece.

---

## #5 — game 2e99850b-64be m16 Qd2 (queen fork — new pattern family)

**FEN:** `rn1q1rk1/1p2b1p1/p1p3bp/5p2/3P4/2N1BB2/PP3PPP/R2QR1K1 w - - 6 16`

**Engine PV:** `Qb3+ Kh7 Qxb7 Bd6 Qxa8 ...` (+311cp)

**Shipped v55 (LOW, `why_user_missed_material`):**
> Qd2 is a serious mistake. Qb3+ was better. Qb3+ wins material in the resulting line.

**Approved rewrite:**
> Qd2 is a serious mistake. Qb3+ was better — it forks Black's king and the undefended b7 pawn. After Kh7, your queen wins b7 and then the a8 rook.

**Why this works:** Names the tactic (fork), both targets (king + b7 pawn), why b7 falls (undefended), the forced king response (Kh7), and the full material gain (pawn + rook). Mohit reframed my initial "check forces Kh7 then grab" framing — fork is the right concept here.

**Geometry:** Qb3+ attacks the king along the b3-g8 diagonal (clear because f7 is empty — black pushed f-pawn to f5) AND attacks the b7 pawn along the b-file. b7 is undefended (Ra8 doesn't defend b7; Be7 has no diagonal to it; Nb8 can't reach).

**New pattern family (E): queen-fork-check-plus-undefended.** Engine best move is a queen move that delivers check AND attacks an undefended piece. Different from the existing fork detectors (knight_fork / bishop_fork / rook_fork / pawn_fork) — those exist for non-queen pieces. Queen forks involving check + material on another square are missed here. Worth a detector once we have 2-3 more examples (don't build from N=1).

**Eval-guard regression also applies:** +311cp is just under the 400cp piece_capture threshold, so it fell to LOW engine-speak. Same issue as the Bb5 case (#3).

---

## #3 — game fc97ee1d-ba3 m7 Bb5 (v53 regression case → fixed in v56)

**FEN:** `r1bqkbnr/pppp3p/n4p2/3Pp1p1/4P3/2P2N1P/PP3PP1/RNBQKB1R w KQkq - 0 7`

**Engine PV:** `Nxe5 Ke7 d6+ cxd6 Nc4 d5` (+408cp). PV #2: `Nxg5 Nh6 Qh5+ Ke7 ...` (+343cp) — the Légal's pattern.

**Shipped v55 (LOW, `why_user_missed_material`):**
> Bb5 is a mistake. Nxe5 was better. Nxe5 wins material in the resulting line.

**v56 caption (HIGH, NEW variant `why_user_missed_clearance_then_check`):**
> Bb5 is a mistake. Nxe5 was better. Nxe5 opens the line — your queen can then play Qh5+ to chase the king on e8.

**Why this is the right shape:** Names the mechanism (opens the line), the piece (queen), the follow-up move (Qh5+), and the target (king on e8). Honest about the 2-move plan — says "can then play" so there's no 1-move hallucination.

**This case was a v53 regression** — the 2-move clearance detection existed pre-v53 but I deleted it overnight to silence a 1-move-caption hallucination instead of fixing the template. v56 restores the detection as a distinct evidence type with a proper multi-move template. See [feedback_fix_framing_not_detection](../../../.claude/projects/c--Users-MIISCO-smartchesscoach/memory/feedback_fix_framing_not_detection.md).

---

## Shared pattern across #1 and #2

Both shipped captions hit `why_user_missed_material` because the engine's PV
shows a material gain but the eval-guard rejected the more specific
`piece_capture` claim. In both cases the engine's *best move* is doing
something tactical (hits a piece with tempo) that the existing template
doesn't surface.

The proposed detector / template angle:
- **Input:** the engine's PV after best move.
- **Detect:** does white's best move attack a piece (i.e. opponent's first PV
  response moves that piece away)?
- **If yes:** caption claims "Nh4 was better — it [attacks/hits/kicks] the
  [piece] on [square]."
- **Optionally extend:** if the *next* white move in the PV captures a different
  piece/pawn, append "so you can take on [square]" — this gives the consequence
  without the engine-speak.

This needs to wait for 5-10 examples before designing the detector — premature
generalization from 2 examples will likely miss edge cases.
