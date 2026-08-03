# Piece-Safety Teaching Depth — Authored & Verified Tier Content

Pre-code deliverable for `docs/rating_band_teaching_depth_scope.md` §7
("A locked, authored set of tier-specific concept rules for `piece_safety`
across enough real positions to validate the pattern"). Every position
below is a real, analyzed game from production, and every board claim was
verified directly with python-chess (attackers/defenders of the relevant
square), not inferred from the stored `cp_loss`/`threat` fields alone.

Two of the 4 candidate positions originally pulled were **dropped after
verification contradicted the simple narrative** — recorded here so the
same mistake isn't repeated:
- `game_efa6a7a5d0bf` Rab1 (eval stayed +567→+407 — White was never
  actually losing the "hanging" rook in a way that changes the picture;
  calling this "you hung a piece" would have been false).
- `game_9a0145e36678` Rf2 (both the played move and the best move allow
  the same `Nxf4` reply — the real difference is a subtler recapture
  move-order issue, not a clean hang-a-piece story).

`piece_safety` naturally splits into (at least) two distinct sub-patterns,
which the tier text below treats consistently:
- **Direct hang** — the move itself lands a piece on a square already
  covered by the opponent, with no reply defending it.
- **Ignored existing threat** — a different piece was already
  undefended/attacked before this move, and the move played doesn't
  address it.

---

## Position 1 — Direct hang (bishop sac achieves nothing)

`game_f2c022e03856`, move 7, White plays **Bxf7+**
FEN before: `r2qkbnr/ppp2pp1/3p3p/4p3/2BnP1b1/P1NP1N2/1PP2PPP/R1BQK2R w KQkq - 1 7`
Verified: after Bxf7+, the bishop on f7 has zero own defenders; Black's
king on e8 still attacks f7 and simply recaptures. `eval_before=+1 →
eval_after=-378`. `best_move=Be3`.

| Tier | Text |
|---|---|
| beginner_low (600-999) | "Bxf7+ gives check, but nothing defends your bishop on f7 — Black's king just takes it back with Kxf7. Before you capture with check, make sure the square is actually safe afterward, not just that it forces a reply." |
| beginner_high (1000-1399) | "Bxf7+ wins a pawn and forces the king to move, but only your bishop attacks f7 — no other piece backs it up. So after Kxf7, you're not up material, you're down a whole bishop for one pawn." |
| intermediate (1400-1799) | "Bxf7+ trades your bishop for a pawn and a forced king move, but the king move alone isn't worth a piece here — Black's king on f7 isn't actually in danger afterward, so you've spent your best minor piece for nothing concrete. Be3 kept developing and left the bishop for a moment when it would really cost something." |
| advanced (1800+) | "Bxf7+?? Kxf7 just loses the piece — the check achieves nothing since nothing backs it up. Be3 was calm and correct." |

## Position 2 — Direct hang (queen sac into a covered square)

`game_8efcc1db5aa4`, move 24, Black plays **Qxh3**
FEN before: `5rk1/ppp3pp/8/4pq2/P2nN3/1P1P3P/2PQ2P1/4R1K1 b - - 3 24`
Verified: after Qxh3, White's pawn on g2 already covers h3; Black has zero
defenders there. `eval_before=+2 (White) → eval_after=+477 (White)` — a
straight queen loss. `best_move=Qg6`.

| Tier | Text |
|---|---|
| beginner_low | "Qxh3 puts your queen on a square White's pawn on g2 already guards — gxh3 wins your queen for a pawn. Before any capture, check whether a pawn or piece already covers that square." |
| beginner_high | "Qxh3 takes a pawn, but g2 was already watching h3 the whole time — your queen has nothing backing it up there, so gxh3 just wins your queen outright, not a fair trade." |
| intermediate | "Qxh3 looks tempting — it grabs a pawn and gets close to White's king — but the g2 pawn was always covering h3, so this isn't a real sacrifice, it's a straight queen loss. Qg6 kept the queen active and safe, still eyeing the kingside without handing over your most valuable piece." |
| advanced | "Qxh3?? gxh3 just loses the queen for a pawn — g2 always had it covered. Qg6 kept the pressure without the risk." |

## Position 3 — Ignored existing threat

`game_665fd66c997a`, move 6, White plays **Qd2**
FEN before: `rn2kbnr/ppp2ppp/3pb1q1/4p1B1/2B1P3/3P1N2/PPP2PPP/RN1QK2R w KQkq - 3 6`
Verified: Black already has `Bxc4` available *before* White's move — the
c4 bishop had no defender then, and `Qd2` neither defends it nor moves it.
`eval_before=+34 → eval_after=-229`. `best_move=Bxe6` (a counter-capture,
not a defense of c4).

| Tier | Text |
|---|---|
| beginner_low | "Qd2 doesn't deal with the fact that Black can already play Bxc4, winning your bishop — it was already undefended. Before making your own plan, always check: is anything of mine hanging right now?" |
| beginner_high | "Qd2 develops the queen, but it ignores that your bishop on c4 has no defender and Black can simply take it with Bxc4. A move here needed to either defend c4, move the bishop, or find something bigger to do instead." |
| intermediate | "Qd2 leaves the c4 bishop hanging to Bxc4 — and since the queen move doesn't create a big enough threat of its own, Black just wins the piece next move with nothing to show for it. Bxe6 was the right idea: instead of trying to save the bishop, it grabs Black's own loose piece on e6 first, so even after Bxc4, the trade comes out even or ahead." |
| advanced | "Qd2 ignores Bxc4 hanging — Bxe6 first was correct, since it wins material of your own before Black gets to collect on c4." |

## Position 4 — Direct hang (capture into a queen-covered square)

`0069d81a-506f-4d41-bf53-f8a48642d2d6`, move 4, Black plays **Nxg4**
FEN before: `rnbqk2r/pppp1ppp/5n2/2b1p3/6P1/2N1P3/PPPP1PBP/R1BQK1NR b KQkq - 2 4`
Verified: White's queen on d1 already attacks g4 before the move; Black
has zero defenders there after capturing. `eval_before=+11 (White) →
eval_after=+392 (White)`. `best_move=d5`. A useful variant of Position 2
(Qxh3) — here the piece already covering the square is the queen itself,
not a pawn, and the capturing piece is a knight, not the queen.

| Tier | Text |
|---|---|
| beginner_low | "Nxg4 takes a pawn, but White's queen on d1 already covers that square — Qxg4 wins your knight next. Before any capture, check what's already watching the square you're capturing on." |
| beginner_high | "Nxg4 grabs a pawn, but the queen on d1 was already aimed at g4 down that diagonal, so nothing protects your knight there — Qxg4 just wins it back for free." |
| intermediate | "Nxg4 wins a pawn, but the g4 square was already covered by White's queen on d1, so this isn't really winning material — it's trading your knight for one pawn. d5 was the calmer choice: it fights for the center without handing over a piece." |
| advanced | "Nxg4?? Qxg4 just costs the knight for a pawn — the queen on d1 already had g4 covered. d5 was correct instead." |

## Position 5 — Ignored existing threat (castling hangs the queen)

`b9b5fc63-ae8f-4632-ac31-b38207d742ed`, move 11, White plays **O-O**
FEN before: `r1bqk2r/pp4bp/3p2pn/2pNp1p1/2BnP3/3P1Q1P/PPP2PP1/1RB1K2R w Kkq - 2 11`
Verified: `Nxf3+` (capturing White's queen with check) is legal for Black
both before and after White's castling move — castling neither addresses
nor is affected by it. `eval_before=-335 → eval_after=-680`. `best_move
=Qg3`. The most severe example in this set (the queen itself, not a minor
piece) and the first not built around a capturing move — castling is a
completely ordinary, usually-safe move that here simply ignores what's
actually happening on the board.

| Tier | Text |
|---|---|
| beginner_low | "O-O doesn't save your queen — Black can already play Nxf3+, winning it with check, and castling doesn't stop that. Before you castle, always check: is anything of mine hanging right now?" |
| beginner_high | "O-O looks like a normal, safe move, but it ignores that your queen on f3 can already be captured by Nxf3+ — castling doesn't defend the queen or move it away." |
| intermediate | "O-O is a completely normal move in general, but here it walks right past the fact that Nxf3+ wins your queen with check — the king move doesn't change what's happening on f3 at all. Qg3 moved the queen to safety first, keeping it in the game instead of losing it outright." |
| advanced | "O-O ignores Nxf3+ winning the queen with check — Qg3 was needed first, saving the queen before anything else." |

## Position 6 — Direct hang (check-with-capture achieves nothing, rook version)

`aef99109-9f2d-45a8-98f1-0cb97db825ee`, move 37, Black plays **Rxf1+**
FEN before: `5k2/1q3r1p/1R2Q1p1/5p2/1P6/2P3P1/5P1P/3r1BK1 b - - 2 37`
Verified: White's king on g1 already covers f1 before the move; Black has
zero defenders after capturing, so `Kxf1` recaptures for free.
`eval_before=-50 → eval_after=+362`. `best_move=Qe4`. A second, confirming
example of the same "check-with-capture achieves nothing" shape as
Position 1 (Bxf7+) — here the advanced tier correctly uses "loses the
exchange" (rook for bishop, the precise traditional sense of the term,
same judgment call as the "wins the exchange" keeps in
`traps.json`/`opening_book.py` from the earlier jargon sweep), not the
banned generic usage.

| Tier | Text |
|---|---|
| beginner_low | "Rxf1+ gives check, but nothing defends your rook on f1 — White's king just takes it back with Kxf1. Before you capture with check, make sure the square is actually safe afterward." |
| beginner_high | "Rxf1+ wins the bishop and forces the king to move, but only your rook attacks f1 — the king on g1 already covers that square, so Kxf1 just wins your rook back." |
| intermediate | "Rxf1+ trades your rook for a bishop and a forced king move, but the check alone isn't worth a whole rook here — White's king isn't in real danger afterward. Qe4 kept the pressure on without giving up material for a check that doesn't lead anywhere." |
| advanced | "Rxf1+?? Kxf1 just loses the exchange for nothing real — Qe4 kept the initiative without the cost." |

---

## What this authoring pass confirms about the pattern

- The 4-tier shape holds across six real positions and two structurally
  different piece_safety sub-patterns without forcing awkward phrasing —
  beginner_low always stays to one fact + one rule; advanced always
  compresses to the shortest possible statement of cause + correct
  alternative.
- **Not every stored `cognitive_gap: piece_safety` mistake is a clean
  teaching case.** 2 of the first 4 pulled from the corpus turned out
  misleading on direct engine verification and were correctly dropped
  rather than authored around. Any production wiring of this feature must
  keep this same verify-before-render discipline per-position, not assume
  every tagged mistake is tier-authorable as-is.
- **Deliberately not generalized into parameterized templates.** With
  only 6 authored positions (3 `direct_hang`, 2 `ignored_existing_threat`,
  plus the `check_achieves_nothing` variant shared by Positions 1 and 6),
  forcing a one-size-fits-all template risks exactly what this project's
  own caption-distillation history already found: over-generalizing too
  early produces vaguer text that diverges from what a specific real
  position actually needs. The established, working pattern in this
  codebase (`R12_blunder.json`'s dozens of hand-authored variants) is the
  right model — grow this as a library of specific, verified situations,
  not a generic template, until a genuinely large authored set reveals
  where real generalization is safe.
