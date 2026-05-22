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

## #9 — knight on the rim + central pawn break (row #035)

**FEN:** `rnbqkbnr/ppp1pppp/8/2Pp4/8/8/PP1PPPPP/RNBQKBNR b KQkq - 0 2`

**Engine PV:** `e5 d4 exd4 e3 Bxc5 exd4` (eval -184cp = +184cp for black)

**Shipped v55 (LOW):**
> Na6 is a mistake. e5 was better. e5 wins material in the resulting line.

**Approved rewrite:**
> Na6 is a mistake — knights on the rim are weak. e5 was better, claiming central space. In the opening, knights belong on c6 or f6 — never the edge.

**Why this works:** Three opening principles in three sentences — (1) knights on the rim are weak (concrete: a6/h6 are bad squares), (2) e5 fights for central space, (3) general rule for where knights belong (c6/f6). Teaches a 600-1500 player a habit they can apply across all openings, not just this position.

**Pattern family overlap.** Maps onto existing `OP_KNIGHT_ON_RIM` principle in `R_PROMOTED_principle.json` — could likely repurpose the existing variant. Plus a "missed central pawn break in the opening" principle. N=1 for the specific combination.

---

## #15 — endgame: grab undefended pawn with active piece (row #030, same family as #013)

**FEN:** `8/2p3pk/1b1pp2p/4p3/1PP1P3/7P/3KNr2/1R6 b - - 0 27`

**Engine eval:** Rf3 = +414cp for black (huge).

**Shipped v55 (LOW):**
> c5 is a serious mistake. Rf3 was better. Rf3 wins material in the resulting line.

**Approved rewrite:**
> c5 is a serious mistake — White's h3 pawn is undefended and your rook can swing over to grab it. Rf3 was better, attacking h3. In the endgame, look for undefended pawns and pick them up with your active pieces.

**Why this works:** Same three-beat structure as #013 (active king). Concrete (h3 undefended) → better move (Rf3 attacks it) → universal principle (hunt undefended pawns with active pieces). Same family, different piece.

**Pattern family (L extended): endgame — grab loose pawn with active piece.** #013 used the king; this one uses the rook. Now N=2 for the family — **buildable detector**:
- Phase = endgame (few pieces left)
- Engine's best move attacks an undefended opponent pawn
- The attacking piece is the player's most-active piece (king or rook in endgame)
- Caption names the loose pawn + the piece + the principle

---

## #14 — stop opponent's pawn advance (row #012)

**FEN:** `r1bqk2r/pppp1ppp/2n2n2/2b1p3/P1B1P3/2PP4/1P3PPP/RNBQK1NR b KQkq - 0 5`

**Engine eval:** a5 = +8cp (basically equal), d6 (played) ≈ +280cp (~3 pawns worse).

**Shipped v55 (LOW):**
> d6 is a serious mistake. a5 was better. Opponent's strongest reply: b4.

**Approved rewrite:**
> d6 is a serious mistake — White played a4 preparing a5 to attack your bishop and gain queenside space. a5 was better, stopping the push. When your opponent threatens a pawn advance, blocking it is often more important than developing.

**Why this works:** Three beats — concrete (a4-a5 plan + targets), better move + reason, universal principle. The principle ("when your opponent threatens a pawn advance, blocking it is often more important than developing") transfers to many positions: Maroczy bind, Spanish a4-a5, Catalan c4-c5, etc.

**Pattern family (M): stop-opponent-pawn-advance.** Distinct from defensive-pawn-push (#7 was about not wasting tempo on defense). This one is about *prophylactic blocking* — a real strategic principle. Detector spec (when N≥2):
- Opponent's previous move was a pawn advance preparing further advance (a4→a5, c4→c5 etc.)
- User played a non-pawn-blocking move (often developing)
- Engine's best is the blocking-pawn move (a5 against a4, etc.)
- cp_loss > 100 (real positional cost)

N=1 for now.

---

## #13 — active king in the endgame (row #010)

**FEN:** `r7/1b1nk3/2p1p1r1/p6p/1pNP4/P3R1Pp/1P3P1K/4R2B w - - 3 34`

**Engine eval:** Kxh3 = +257cp (top of 5 candidates).

**Shipped v55 (LOW):**
> a4 is a mistake. Kxh3 was better. Opponent's strongest reply: Rf8.

**Approved rewrite:**
> a4 is a mistake — Black's h3 pawn is undefended, and your king is right next door. Kxh3 was better. In the endgame, your king becomes a fighting piece — use it to win loose pawns.

**Voice note (2026-05-22):** Mohit asked "it's too long, no?" then approved the long version anyway. He prefers the explicit-principle ending ("In the endgame, your king becomes a fighting piece") over a terser one-sentence form, when the principle is teaching value. Lesson: when the caption can name a universal endgame/middlegame principle as the last sentence, keep it — the audience learns the habit, not just the move.

**Why this works:** Three teaching beats:
1. Concrete (h3 undefended, king nearby)
2. The move (Kxh3 with reason)
3. Universal principle (active king in endgame)

For 600-1500 the principle is the *transfer-out* — once they hear it framed this way, they can apply it across every endgame.

**Pattern family (L): active-king-in-endgame.** Distinct from the queen-fork, attack-with-tempo families — purely positional endgame teaching. Maps onto existing principle vocabulary in `R_PROMOTED_principle.json` (`END_KING_ACTIVE`); might already have a variant we can route to. N=1 for now.

---

## #12 — active defense vs passive defense (row #029)

**FEN:** `r1bqk2r/p1pp1ppp/2p5/4P3/1nP5/B7/P1P2PPP/R2QKB1R b KQkq - 2 10`

**Engine eval:** Qe7 = +3cp (equal), a5 = +245cp (+~2.5 pawns worse for black)

**Shipped v55 (LOW, misleading):**
> a5 is a mistake. Qe7 was better. Qe7 wins material in the resulting line.

(Wrong — Qe7 doesn't *win* material, it *saves* the knight + counter-attacks.)

**Approved rewrite:**
> a5 only defends your knight passively — White plays c3 next, attacking the knight twice, and it has to retreat to a6 (the rim). Qe7 was better: it defends the knight AND attacks the undefended e5 pawn, so White must defend before attacking again.

**Why this works:** Names the actual situation (knight under attack from Ba3) and contrasts passive defense (a5 — just defends, gets piled on by c3) with active defense (Qe7 — defends + counter-threatens e5). Teaches a universal middlegame principle.

**Geometry:**
- Black Nb4 attacked by white Ba3, no defenders.
- `a5` defends via pawn diagonal a5→b4. But white plays c3 — c3 pawn ALSO attacks b4. Now 2 attackers, 1 defender. Knight retreats to a6 (the rim).
- `Qe7` defends b4 via diagonal e7→d6→c5→b4. AND attacks the undefended e5 pawn via e-file. After Qe7, white CAN'T play c3 (would lose e5 to Qxe5+). White is forced to defend e5 first (PV: Qe7 Bb2 d5 ...).

**Pattern family (K): active-defense-vs-passive-defense.** Distinct from all prior families. The lesson is: when defending a threatened piece, prefer moves that *also* create a counter-threat. Detector spec (when N≥2):
- User's played move defends a threatened piece passively (1 defender vs 1 attacker)
- Engine's best move defends the SAME piece AND attacks an undefended target
- Caption names both (passive vs active framing)

N=1, log for later.

---

## #11 — knight outpost (row #011)

**FEN:** `rnb2r2/2q1npkp/p1p1p1p1/1p2N3/2pP4/2N1P1P1/PP1Q1PBP/R4RK1 w - - 2 14`

**Engine PV:** `Ne4 Nd7 Nxd7 Bxd7 b3 cxb3 axb3 a5 Nc5 Bc8` (+66cp, top of 5 candidate moves)

**Shipped v55 (LOW, `why_user_reply`):**
> a3 is a mistake. Ne4 was better. Opponent's strongest reply: f6.

**Approved rewrite:**
> a3 is a mistake — Ne4 was better. e4 is an outpost: defended by your g2 bishop and safe from any enemy pawn. From there, your knight can jump to Nc5 to attack Black's pieces.

**Why this works:** Names the positional concept (**outpost**) and defines it inline by example ("defended by your g2 bishop and safe from any enemy pawn"). Even players who haven't encountered "outpost" before learn it through context. Then names the follow-up (Nc5 attacking).

**Geometry:** Nc3 → Ne4. e4 is defended by Bg2 (fianchetto). No black pawn can attack e4 (the f-pawn is on f7, the d-pawn is gone). So Ne4 is a permanent strong square. From e4, the knight can jump to Nc5, attacking black's pieces.

**Pattern family (J): knight outpost — positional principle.** Maps onto the existing strategic concept teaching. N=1 for the specific combination of "missed knight outpost vs passive pawn move." Voice rule: use **"outpost"** word per memory_caption_voice_avoid_chess_jargon (outpost is on the OK-list because curriculum teaches it).

---

## #10 — pawn break to undermine defender (row #032)

**FEN:** `r2q1rk1/pb2npbp/1n1pp1p1/2p5/4PP2/1BN1BN1P/PPP3P1/1R1Q1RK1 b - - 5 13`

**Engine eval:** -259cp (+259cp for black) after `c4`. Stored best=`c4`. PV (stored) starts with `Bxc3 bxc3 c4 Ba4 Bxe4 Bb5` — note PV disagrees with stored best; the stored best is the right one here (verified by Mohit + reasoning).

**Shipped v55 (LOW):**
> Qd7 is a mistake. c4 was better. c4 wins material in the resulting line.

**Approved rewrite:**
> Qd7 is a mistake. c4 was better — it kicks White's bishop off b3, leaving e4 undefended for your Bb7 to grab.

**Why this works:** Names the mechanism (`c4` kicks Bb3) AND the consequence (e4 becomes undefended, Bb7 grabs it). Teaches a tactical idea: *undermine the defender* — a piece is defended only because of another piece's position; kick that other piece and the target falls.

**Geometry:** Black Bb7 is on the a8-h1 diagonal, aimed at the e4 pawn. Currently e4 is defended by Nc3 (knight covers e4). The c-pawn push to c4 attacks Bb3 (white can't recapture because Nb6 defends c4). Bb3 retreats to Ba4 — and now black plays Bxe4. Even though Nc3 still defends e4, the *Nxe4 recapture costs white a knight for bishop + pawn* — net +1 pawn for black plus a useful advanced c-pawn.

**Pattern family (I): undermine-the-defender pawn break.** Distinct from:
- attack_with_tempo (best move directly attacks a piece that retreats)
- queen-fork (best move attacks two targets at once)

Here the best move attacks ONE piece (the bishop) but the *consequence* is that ANOTHER target (e4 pawn) becomes capturable. Indirect attack. N=1, log for later.

**Important: v58 reconciliation note.** The stored PV starts with `Bxc3` but the stored best is `c4`. v58 reconciles by preferring PV[0] — which would WRONGLY swap c4 → Bxc3 here. This case shows v58 is unsafe: sometimes stored best is correct and PV is stale, sometimes vice versa. Need to revisit the v58 approach. See message thread 2026-05-22.

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
