# Positional caption candidates

Generated locally: 2026-09-09T14:07:11.311239+00:00
Engine evidence: `Stockfish 17.1`, 30,000 nodes per search

## Result

- Caption targets: **199**
- Already decided: **17**
- Not a mistake: **24**
- Captions passing every local claim and voice check: **199**

The database contained one legacy submission and no saved identities for the stated 17/24 split. The two exclusion sets below are deterministic evidence-ranked reconstructions and remain reviewable candidates.

## Teaching reason mix

- take_available_piece: 35
- avoid_reply_attack: 27
- avoid_reply_capture: 27
- avoid_forcing_check: 19
- compare_replies: 18
- rook_file: 18
- create_concrete_threat: 14
- add_defender: 5
- advance_passed_pawn: 5
- active_endgame_king: 4
- advance_endgame_pawn: 4
- centralize_piece: 4
- limit_the_reply_capture: 4
- forcing_check_sequence: 3
- king_approaches_pawn: 3
- choose_more_valuable_capture: 2
- recapture_with_lower_value_piece: 2
- take_opposition: 2
- activate_rook: 1
- king_recaptures_keep_pawn: 1
- save_attacked_piece: 1

## Captions

### 04695f7616d54d58 · Ba6 → Bxf3

Ba6 moves the bishop to a6 and leaves that capture unused. Bxf3 takes the pawn on f3 before moving elsewhere. Bxf3 changes the material on the board immediately; Ba6 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### e324b14aecee8a63 · c4 → Rg1

c4 moves the pawn to c4 instead of placing the rook on the g-file. Rg1 puts the rook on g1, on the semi-open g-file. On g1 the rook has the file available; c4 leaves the rook out of that lane. When no tactic is urgent, look for an open or semi-open file for a rook.

**Lesson:** When no tactic is urgent, look for an open or semi-open file for a rook.

### 50455fe617c1a0f2 · Bd4 → Rad1

Bd4 moves the bishop to d4 instead of placing the rook on the d-file. Rad1 puts the rook on d1, on the semi-open d-file. On d1 the rook has the file available; Bd4 leaves the rook out of that lane. When no tactic is urgent, look for an open or semi-open file for a rook.

**Lesson:** When no tactic is urgent, look for an open or semi-open file for a rook.

### fb1659c820cb61e3 · Re1 → Be5+

Re1 puts the rook on e1 without creating that attack. Be5+ puts the bishop on e5, attacking the king on g3. Be5+ gives the opponent a concrete piece to answer on g3; Re1 does not. A useful improving move should attack, defend, or create a clear next threat.

**Lesson:** A useful improving move should attack, defend, or create a clear next threat.

### 890e42321353be4a · a4 → Bxb5

a4 moves the pawn to a4 and leaves that capture unused. Bxb5 takes the rook on b5 before moving elsewhere. Bxb5 changes the material on the board immediately; a4 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### f4c4e513da26a5f7 · Kd2 → b5

Kd2 allows this reply: Black answers Rc8, attacking the pawn on c7. b5 changes the setup; after it, Black answers Kh1, and the continuation reaches b6. Only Kd2 lets the reply attack the piece on c7; b5 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### 77f4153c4d0a1af4 · Ra4 → h4

Ra4 moves the rook to a4 and leaves that pawn on h5. h4 advances the passed pawn to h4, one rank closer to promotion. h4 makes the opponent answer the passed pawn sooner; Ra4 gives it no progress. In an endgame, calculate whether a passed pawn can advance safely before making a side move.

**Lesson:** In an endgame, calculate whether a passed pawn can advance safely before making a side move.

### 7f1740793472b593 · bxc3 → Kxc3

bxc3 uses the pawn from b2 for the same capture. Kxc3 uses the king from d2 to recapture on c3. Both moves capture on c3, but Kxc3 keeps the pawn on b2. When the king can recapture safely in an endgame, compare whether using it preserves your pawn structure.

**Lesson:** When the king can recapture safely in an endgame, compare whether using it preserves your pawn structure.

### ca95638cff2c334c · Kb4 → Kd6

Kb4 allows this concrete reply: Black answers Rxb5+, taking the pawn on b5. Kd6 changes the position first; after it, Black answers Rd5+, checking the king from d5. Only Kb4 gives the immediate capture on b5; Kd6 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### a279d160b5e7e4d6 · g4 → Re7

g4 allows this reply: Black answers Qf7, attacking the queen on f5. Re7 changes the setup; after it, Black answers Rh7, and the continuation reaches Qe6+. Only g4 lets the reply attack the piece on f5; Re7 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### bc53e6569846158e · f5 → Rxh2

f5 moves the pawn to f5 and leaves that capture unused. Rxh2 takes the pawn on h2 before moving elsewhere. Rxh2 changes the material on the board immediately; f5 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### 318c3517e620dbb9 · Rxa6 → Kd3

Rxa6 allows this concrete reply: Black answers c5+, checking the king from c5. Kd3 changes the move order; after it, Black answers c5, and the continuation reaches g3. The check after Rxa6 forces a response, while Kd3 avoids that immediate check. Before starting your plan, look for the opponent's checks and deal with the forcing one first.

**Lesson:** Before starting your plan, look for the opponent's checks and deal with the forcing one first.

### a3fad576efb9c9bd · Nd2 → Re8+

Nd2 moves the knight to d2 instead of placing the rook on the e-file. Re8+ puts the rook on e8, on the open e-file. On e8 the rook has the file available; Nd2 leaves the rook out of that lane. When no tactic is urgent, look for an open or semi-open file for a rook.

**Lesson:** When no tactic is urgent, look for an open or semi-open file for a rook.

### 55fd14180be49a41 · Rh3 → Ne4

Rh3 allows the larger capture: Black answers Bxh3, taking the rook on h3. Ne4 changes what can be taken; Black answers exf4, taking the pawn on f4. After Rh3, the reply takes a rook; after Ne4, it takes only a pawn. When both moves allow a capture, choose the line that keeps the more valuable piece safe.

**Lesson:** When both moves allow a capture, choose the line that keeps the more valuable piece safe.

### ade400ff9ed2c2a4 · Ke5 → Rxa5

Ke5 moves the king to e5 and leaves that capture unused. Rxa5 takes the pawn on a5 before moving elsewhere. Rxa5 changes the material on the board immediately; Ke5 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### d01278fcc81541d1 · Bg5 → Bxd2

Bg5 moves the bishop to g5 and leaves that capture unused. Bxd2 takes the knight on d2 before moving elsewhere. Bxd2 changes the material on the board immediately; Bg5 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### 1284be9458349c18 · a6 → Ke6

a6 puts the pawn on a6 while the king stays farther away. Ke6 brings the king from f7 toward the centre on e6. Ke6 gives the king a direct route to the pawns; a6 spends the move elsewhere. With few pieces left, activate the king before making a move that can wait.

**Lesson:** With few pieces left, activate the king before making a move that can wait.

### 3f9115b8cfa64349 · Ra8+ → Bg6

Ra8+ moves the rook to a8 instead of solving that loose piece. Bg6 moves the attacked bishop from h7 to g6, where it is not attacked. Bg6 removes the immediate target; Ra8+ leaves the attacked piece available. Before starting a new plan, find every attacked piece that has no defender.

**Lesson:** Before starting a new plan, find every attacked piece that has no defender.

### 1b61842269851b45 · Qe3+ → Qe1+

Qe3+ also checks from e3, but White answers Kd1, moving from c1 to d1. Qe1+ checks from e1; after Qd1, Qxd1+ takes the queen on d1. Qe1+ connects the check to a concrete capture; Qe3+ gives check without that same follow-up. Compare checks by what they force next; a check is useful when the follow-up wins something or improves the result.

**Lesson:** Compare checks by what they force next; a check is useful when the follow-up wins something or improves the result.

### 955de2c340879672 · h3 → Kf1

h3 allows this concrete reply: Black answers Ba5+, checking the king from a5. Kf1 changes the move order; after it, Black answers Rc8, moving from a8 to c8. The check after h3 forces a response, while Kf1 avoids that immediate check. Before starting your plan, look for the opponent's checks and deal with the forcing one first.

**Lesson:** Before starting your plan, look for the opponent's checks and deal with the forcing one first.

### 701cd12e90cd5de6 · Kg3 → f3

Kg3 moves the king to g3 and leaves that pawn on f4. f3 advances the passed pawn to f3, one rank closer to promotion. f3 makes the opponent answer the passed pawn sooner; Kg3 gives it no progress. In an endgame, calculate whether a passed pawn can advance safely before making a side move.

**Lesson:** In an endgame, calculate whether a passed pawn can advance safely before making a side move.

### d34cc66c157694fd · Bd5 → Rdxd7

Bd5 moves the bishop to d5 and leaves that capture unused. Rdxd7 takes the bishop on d7 before moving elsewhere. Rdxd7 changes the material on the board immediately; Bd5 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### 1bfc9d17c2a88020 · Re1+ → Kxg5

Re1+ moves the rook to e1 and leaves that capture unused. Kxg5 takes the rook on g5 before moving elsewhere. Kxg5 changes the material on the board immediately; Re1+ does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### 544d548182f16f7d · Bf4 → Bxd2

Bf4 moves the bishop to f4 and leaves that capture unused. Bxd2 takes the knight on d2 before moving elsewhere. Bxd2 changes the material on the board immediately; Bf4 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### 2daa5b6a273702fb · g4 → Re6+

g4 allows this concrete reply: Black answers Ba5+, checking the king from a5. Re6+ changes the move order; after it, Black answers Kf7, attacking the rook on e6. The check after g4 forces a response, while Re6+ avoids that immediate check. Before starting your plan, look for the opponent's checks and deal with the forcing one first.

**Lesson:** Before starting your plan, look for the opponent's checks and deal with the forcing one first.

### fc4efd2e6bf63790 · Bh8 → Rd8

Bh8 allows this concrete reply: White answers Nd6+, checking the king from d6. Rd8 changes the move order; after it, White answers Nxd4, taking the bishop on d4. The check after Bh8 forces a response, while Rd8 avoids that immediate check. Before starting your plan, look for the opponent's checks and deal with the forcing one first.

**Lesson:** Before starting your plan, look for the opponent's checks and deal with the forcing one first.

### 5c0571e7d4bef61f · f3 → Kd4

f3 allows this concrete reply: White answers gxf3+, taking the pawn on f3. Kd4 changes the position first; after it, White answers b5, attacking the pawn on a6. Only f3 gives the immediate capture on f3; Kd4 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### 866d3714ef0d9636 · Kc7 → Ke7

Kc7 allows this concrete reply: White answers Rbc6+, checking the king from c6. Ke7 changes the move order; after it, White answers Ra6, attacking the queen on a7. The check after Kc7 forces a response, while Ke7 avoids that immediate check. Before starting your plan, look for the opponent's checks and deal with the forcing one first.

**Lesson:** Before starting your plan, look for the opponent's checks and deal with the forcing one first.

### 56108f921d8a5603 · Ka5 → Rf6

Ka5 moves the king to a5 instead of placing the rook on the f-file. Rf6 puts the rook on f6, on the open f-file. On f6 the rook has the file available; Ka5 leaves the rook out of that lane. When no tactic is urgent, look for an open or semi-open file for a rook.

**Lesson:** When no tactic is urgent, look for an open or semi-open file for a rook.

### 5e46e00f3a1c135a · c6 → Nxa3

c6 moves the pawn to c6 and leaves that capture unused. Nxa3 takes the pawn on a3 before moving elsewhere. Nxa3 changes the material on the board immediately; c6 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### b809b896fef651a7 · Rae8 → Bxd2

Rae8 moves the rook to e8 and leaves that capture unused. Bxd2 takes the knight on d2 before moving elsewhere. Bxd2 changes the material on the board immediately; Rae8 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### 8a120a54a3555b92 · Rh5 → Rg5+

Rh5 moves the rook to h5 instead of placing the rook on the g-file. Rg5+ puts the rook on g5, on the semi-open g-file. On g5 the rook has the file available; Rh5 leaves the rook out of that lane. When no tactic is urgent, look for an open or semi-open file for a rook.

**Lesson:** When no tactic is urgent, look for an open or semi-open file for a rook.

### 680c5129741624be · a4 → Rh6

a4 allows this concrete reply: Black answers bxa4+, taking the pawn on a4. Rh6 changes the position first; after it, Black answers Rc4, attacking the pawn on g4. Only a4 gives the immediate capture on a4; Rh6 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### 139b613f3ce3afcd · Kg4 → f3

Kg4 allows this concrete reply: White answers Rxh3, taking the rook on h3. f3 changes the position first; after it, White answers Ra7, and the continuation reaches f2. Only Kg4 gives the immediate capture on h3; f3 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### f2d93816bb523906 · Qh2 → Qe5

Qh2 moves the queen to h2 without adding that defender. Qe5 places the queen on e5, where it adds a defender to the bishop on f6. After Qe5, the bishop on f6 has more support; after Qh2, it does not. When one of your pieces is attacked, count its attackers and defenders before moving elsewhere.

**Lesson:** When one of your pieces is attacked, count its attackers and defenders before moving elsewhere.

### 678cf0d39e02e578 · d4 → Rxf6

d4 moves the pawn to d4 and leaves that capture unused. Rxf6 takes the bishop on f6 before moving elsewhere. Rxf6 changes the material on the board immediately; d4 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### 45d1c47e14efd2af · Kd7 → axb4

Kd7 moves the king to d7 and leaves that capture unused. axb4 takes the pawn on b4 before moving elsewhere. axb4 changes the material on the board immediately; Kd7 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### 51cce1befeee9ff9 · Be1 → Bc5

Be1 puts the bishop on e1 instead. Bc5 moves the bishop from b4 toward the centre on c5, where it reaches g1, f2, a3. The bishop has central work from c5; Be1 uses the move on e1. When moves are quiet, prefer the piece whose new square gives it more concrete jobs.

**Lesson:** When moves are quiet, prefer the piece whose new square gives it more concrete jobs.

### adf384b53aaf6bd7 · c4 → Kc4

c4 moves the pawn to c4 without creating that king standoff. Kc4 places the king on c4, two squares from the enemy king on c2. After Kc4, the kings face each other with White to move; after c4, they do not. In king endgames, try to face the enemy king with one square between them and make it move first.

**Lesson:** In king endgames, try to face the enemy king with one square between them and make it move first.

### d89592575f9a6da1 · Kh7 → Kf7

Kh7 moves the king to h7 without creating that king standoff. Kf7 places the king on f7, two squares from the enemy king on f5. After Kf7, the kings face each other with White to move; after Kh7, they do not. In king endgames, try to face the enemy king with one square between them and make it move first.

**Lesson:** In king endgames, try to face the enemy king with one square between them and make it move first.

### 15f44ce006b0a89c · Rd1 → R5d6

Rd1 allows this concrete reply: White answers Qb5+, checking the king from b5. R5d6 changes the move order; after it, White answers Qc3, attacking the pawn on e5. The check after Rd1 forces a response, while R5d6 avoids that immediate check. Before starting your plan, look for the opponent's checks and deal with the forcing one first.

**Lesson:** Before starting your plan, look for the opponent's checks and deal with the forcing one first.

### fef57212047763a7 · Qa6 → Rd8

Qa6 moves the queen to a6 instead of placing the rook on the d-file. Rd8 puts the rook on d8, on the semi-open d-file. On d8 the rook has the file available; Qa6 leaves the rook out of that lane. When no tactic is urgent, look for an open or semi-open file for a rook.

**Lesson:** When no tactic is urgent, look for an open or semi-open file for a rook.

### 04fd520fb10716f6 · Kg5 → Kh7

Kg5 moves the king from g6 to g5; Black answers Rf6, attacking the pawn on f7. Kh7 moves the king from g6 to h7; Black answers Rf6, attacking the pawn on f7. After the same reply Rf6, Kg5 leads to f8=Q, while Kh7 leads to Kg7. Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

**Lesson:** Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

### e0b30305d0eaefd1 · Kg6 → Kg7

Kg6 moves the king from h7 to g6; White answers Kg4, and the continuation reaches Kh7. Kg7 moves the king from h7 to g7; White answers Ke3, and the continuation reaches Kg6. The concrete difference is the reply after Kg6 versus the reply after Kg7. Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

**Lesson:** Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

### 9dd92e16078d9134 · Qd4+ → Qh4+

Qd4+ moves the queen from a4 to d4; White answers Ke7, and the continuation reaches Qb4+. Qh4+ moves the queen from a4 to h4; White answers Kc7, and the continuation reaches Qc4+. The concrete difference is the reply after Qd4+ versus the reply after Qh4+. Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

**Lesson:** Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

### 7a5b128ccc8dd12c · Re1 → Rxc2

Re1 moves the rook to e1 and leaves that capture unused. Rxc2 takes the rook on c2 before moving elsewhere. Rxc2 changes the material on the board immediately; Re1 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### c09389fbe16c88f3 · h6 → Kh4

h6 moves the pawn from h7 to h6; White answers Rc8, and the continuation reaches Kf5. Kh4 moves the king from g5 to h4; White answers Kg7, attacking the pawn on g6. The concrete difference is the reply after h6 versus the reply after Kh4. Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

**Lesson:** Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

### 839f06691bf48a48 · Rf7 → dxe5

Rf7 moves the rook to f7 and leaves that capture unused. dxe5 takes the pawn on e5 before moving elsewhere. dxe5 changes the material on the board immediately; Rf7 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### 8a99efbbfecb62de · b5 → Ra7+

b5 allows this concrete reply: Black answers Re5+, checking the king from e5. Ra7+ changes the move order; after it, Black answers Kc8, and the continuation reaches Rg7. The check after b5 forces a response, while Ra7+ avoids that immediate check. Before starting your plan, look for the opponent's checks and deal with the forcing one first.

**Lesson:** Before starting your plan, look for the opponent's checks and deal with the forcing one first.

### f37c0ceba0074b62 · h3 → c5

h3 puts the pawn on h3 without creating that attack. c5 puts the pawn on c5, attacking the bishop on d4. c5 gives the opponent a concrete piece to answer on d4; h3 does not. A useful improving move should attack, defend, or create a clear next threat.

**Lesson:** A useful improving move should attack, defend, or create a clear next threat.

### 8316f8fc1a82babe · Qd7+ → Bd8

Qd7+ moves the queen from e6 to d7; White answers Ka6, moving from b5 to a6. Bd8 moves the bishop from e7 to d8; White answers Kc5, and the continuation reaches Qe7+. The concrete difference is the reply after Qd7+ versus the reply after Bd8. Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

**Lesson:** Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

### c2105293777e9b6f · Kc5 → Kb5

Kc5 puts the king on c5 and leaves the king farther from that pawn. Kb5 moves the king to b5, one step closer to the pawn on a6. Kb5 shortens the king's route to a6; Kc5 does not. In a reduced position, move the king toward the pawn you need to win or stop.

**Lesson:** In a reduced position, move the king toward the pawn you need to win or stop.

### 530dcc58be1aec4c · Nf7+ → Ng6+

Nf7+ also checks from f7, but Black answers Kg8, attacking the knight on f7. Ng6+ checks from g6; after Kh7, Nxe7 takes the bishop on e7. Ng6+ connects the check to a concrete capture; Nf7+ gives check without that same follow-up. Compare checks by what they force next; a check is useful when the follow-up wins something or improves the result.

**Lesson:** Compare checks by what they force next; a check is useful when the follow-up wins something or improves the result.

### 0c80a7f0596c5b21 · a2 → Ke2

a2 allows this concrete reply: White answers Rxa2+, taking the pawn on a2. Ke2 changes the position first; after it, White answers Kd4, and the continuation reaches f3. Only a2 gives the immediate capture on a2; Ke2 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### e8c87778ffe54998 · Rd3 → Ra6

Rd3 allows this reply: White answers Kc4, attacking the rook on d3. Ra6 changes the setup; after it, White answers d5, and the continuation reaches Ke5. Only Rd3 lets the reply attack the piece on d3; Ra6 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### ac7ce0645f2488dd · h4 → Rb6+

h4 allows this concrete reply: Black answers b4+, checking the king from b4. Rb6+ changes the move order; after it, Black answers Kc7, attacking the rook on b6. The check after h4 forces a response, while Rb6+ avoids that immediate check. Before starting your plan, look for the opponent's checks and deal with the forcing one first.

**Lesson:** Before starting your plan, look for the opponent's checks and deal with the forcing one first.

### 432aa819cfeeb37e · h5 → a5

h5 moves the pawn to h5 while that pawn stays on a6. a5 advances the pawn from a6 to a5, one rank closer to promotion. a5 gains one step in the pawn race; h5 spends the move elsewhere. In a pawn ending, count both sides' moves to promotion before spending a move on the king or another pawn.

**Lesson:** In a pawn ending, count both sides' moves to promotion before spending a move on the king or another pawn.

### c0d5906bc0221977 · Rg2+ → Rd1+

Rg2+ allows this reply: White answers Kf1, attacking the rook on g2. Rd1+ changes the setup; after it, White answers Kf2, and the continuation reaches Nd4. Only Rg2+ lets the reply attack the piece on g2; Rd1+ avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### cbbf9ba1fc47d86a · Rf8 → Be6

Rf8 allows this concrete reply: White answers Bg7+, checking the king from g7. Be6 changes the move order; after it, White answers Bxc7, taking the pawn on c7. The check after Rf8 forces a response, while Be6 avoids that immediate check. Before starting your plan, look for the opponent's checks and deal with the forcing one first.

**Lesson:** Before starting your plan, look for the opponent's checks and deal with the forcing one first.

### c6eb0d59a3573ca1 · Ra3 → b3

Ra3 moves the rook to a3 and leaves that pawn on b4. b3 advances the passed pawn to b3, one rank closer to promotion. b3 makes the opponent answer the passed pawn sooner; Ra3 gives it no progress. In an endgame, calculate whether a passed pawn can advance safely before making a side move.

**Lesson:** In an endgame, calculate whether a passed pawn can advance safely before making a side move.

### fe8aabcb0595c9f1 · Kg6 → Bxb4

Kg6 moves the king to g6 and leaves that capture unused. Bxb4 takes the pawn on b4 before moving elsewhere. Bxb4 changes the material on the board immediately; Kg6 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### 3758993751d0a0c4 · Nc6+ → b5

Nc6+ moves the knight to c6 while that pawn stays on b7. b5 advances the pawn from b7 to b5, one rank closer to promotion. b5 gains one step in the pawn race; Nc6+ spends the move elsewhere. In a pawn ending, count both sides' moves to promotion before spending a move on the king or another pawn.

**Lesson:** In a pawn ending, count both sides' moves to promotion before spending a move on the king or another pawn.

### da1415dd8bfcda58 · Rf7 → Rf8+

Rf7 moves the rook to f7 instead of placing the rook on the f-file. Rf8+ puts the rook on f8, on the open f-file. On f8 the rook has the file available; Rf7 leaves the rook out of that lane. When no tactic is urgent, look for an open or semi-open file for a rook.

**Lesson:** When no tactic is urgent, look for an open or semi-open file for a rook.

### 41d1498a2c75e739 · f5 → Kd4

f5 puts the pawn on f5 while the king stays farther away. Kd4 brings the king from e3 toward the centre on d4. Kd4 gives the king a direct route to the pawns; f5 spends the move elsewhere. With few pieces left, activate the king before making a move that can wait.

**Lesson:** With few pieces left, activate the king before making a move that can wait.

### 6f46afea53d44c06 · Qc4+ → Bf6

Qc4+ moves the queen from c7 to c4; White answers Qd3, attacking the queen on c4. Bf6 moves the bishop from e5 to f6; White answers Bf4, attacking the queen on c7. The concrete difference is the reply after Qc4+ versus the reply after Bf6. Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

**Lesson:** Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

### 2ccca58928f8fb65 · a5 → Bf5+

a5 allows this concrete reply: White answers Rd6+, checking the king from d6. Bf5+ changes the move order; after it, White answers Kg7, and the continuation reaches Bxh7. The check after a5 forces a response, while Bf5+ avoids that immediate check. Before starting your plan, look for the opponent's checks and deal with the forcing one first.

**Lesson:** Before starting your plan, look for the opponent's checks and deal with the forcing one first.

### 8056eb8810d5b030 · Rf1 → Rc6

Rf1 allows this reply: Black answers Ra8, attacking the pawn on a7. Rc6 changes the setup; after it, Black answers Qxa7, taking the pawn on a7. Only Rf1 lets the reply attack the piece on a7; Rc6 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### dba7e0bd0776d9f6 · Rd5 → Rd2

Rd5 allows this concrete reply: White answers Nxd5, taking the rook on d5. Rd2 changes the position first; after it, White answers b3, and the continuation reaches Bc6. Only Rd5 gives the immediate capture on d5; Rd2 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### c1d455ded8d70841 · d3 → Qd5

d3 allows this concrete reply: White answers Qh8+, checking the king from h8. Qd5 changes the move order; after it, White answers Qf6, attacking the bishop on e6. The check after d3 forces a response, while Qd5 avoids that immediate check. Before starting your plan, look for the opponent's checks and deal with the forcing one first.

**Lesson:** Before starting your plan, look for the opponent's checks and deal with the forcing one first.

### 91747f408a8dd795 · Rc6 → h5

Rc6 allows this reply: White answers Bg2, attacking the queen on f3. h5 changes the setup; after it, White answers gxh5, taking the pawn on h5. Only Rc6 lets the reply attack the piece on f3; h5 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### 618b6ffb72ac637b · Rd1 → Rxe2

Rd1 moves the rook to d1 and leaves that capture unused. Rxe2 takes the rook on e2 before moving elsewhere. Rxe2 changes the material on the board immediately; Rd1 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### 799a2e413ccef28e · Rf5+ → g5

Rf5+ allows this reply: White answers Ke6, attacking the rook on f5. g5 changes the setup; after it, White answers Rc1, and the continuation reaches Kh6. Only Rf5+ lets the reply attack the piece on f5; g5 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### da83f971da13c798 · Ra6 → e5

Ra6 moves the rook to a6 while that pawn stays on e6. e5 advances the pawn from e6 to e5, one rank closer to promotion. e5 gains one step in the pawn race; Ra6 spends the move elsewhere. In a pawn ending, count both sides' moves to promotion before spending a move on the king or another pawn.

**Lesson:** In a pawn ending, count both sides' moves to promotion before spending a move on the king or another pawn.

### 1449c17feed2a010 · Kc5 → f6

Kc5 allows this reply: White answers Rc3, attacking the rook on c4. f6 changes the setup; after it, White answers Ka2, and the continuation reaches Rd4. Only Kc5 lets the reply attack the piece on c4; f6 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### 19633200e0b5cb2d · hxg3 → Qxg3

hxg3 moves the pawn to g3 without adding that defender. Qxg3 places the queen on g3, where it adds a defender to the pawn on h2. After Qxg3, the pawn on h2 has more support; after hxg3, it does not. When one of your pieces is attacked, count its attackers and defenders before moving elsewhere.

**Lesson:** When one of your pieces is attacked, count its attackers and defenders before moving elsewhere.

### 83e5c4c7f975b26c · b6 → Bxf5

b6 moves the pawn to b6 and leaves that capture unused. Bxf5 takes the pawn on f5 before moving elsewhere. Bxf5 changes the material on the board immediately; b6 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### c7d2f3f0ee4ee47d · Re3 → Qf6+

Re3 allows this reply: White answers h5, attacking the bishop on g6. Qf6+ changes the setup; after it, White answers Ka2, and the continuation reaches Qxh4. Only Re3 lets the reply attack the piece on g6; Qf6+ avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### ecc86d402b43df5d · Rxf5 → Rxc5

Rxf5 allows the larger capture: White answers Rxf5, taking the rook on f5. Rxc5 changes what can be taken; White answers cxb5, taking the pawn on b5. After Rxf5, the reply takes a rook; after Rxc5, it takes only a pawn. When both moves allow a capture, choose the line that keeps the more valuable piece safe.

**Lesson:** When both moves allow a capture, choose the line that keeps the more valuable piece safe.

### 3dd4fa9b072e3f27 · Qxg7 → Bb5

Qxg7 puts the queen on g7 without creating that attack. Bb5 puts the bishop on b5, attacking the knight on c6. Bb5 gives the opponent a concrete piece to answer on c6; Qxg7 does not. A useful improving move should attack, defend, or create a clear next threat.

**Lesson:** A useful improving move should attack, defend, or create a clear next threat.

### da761dd86db51f58 · Kd3 → b3

Kd3 moves the king to d3 and leaves that pawn on b4. b3 advances the passed pawn to b3, one rank closer to promotion. b3 makes the opponent answer the passed pawn sooner; Kd3 gives it no progress. In an endgame, calculate whether a passed pawn can advance safely before making a side move.

**Lesson:** In an endgame, calculate whether a passed pawn can advance safely before making a side move.

### dec00cb959af46d1 · Ke8 → Bxd1

Ke8 moves the king to e8 and leaves that capture unused. Bxd1 takes the rook on d1 before moving elsewhere. Bxd1 changes the material on the board immediately; Ke8 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### 77bc1520033160f3 · Rxf7 → Be4

Rxf7 moves the rook to f7 without adding that defender. Be4 places the bishop on e4, where it adds a defender to the pawn on d3. After Be4, the pawn on d3 has more support; after Rxf7, it does not. When one of your pieces is attacked, count its attackers and defenders before moving elsewhere.

**Lesson:** When one of your pieces is attacked, count its attackers and defenders before moving elsewhere.

### c406ed43345f5b64 · Rxa3 → Kh7

Rxa3 allows this reply: White answers Rd7, attacking the pawn on g7. Kh7 changes the setup; after it, White answers h5, and the continuation reaches Ra7. Only Rxa3 lets the reply attack the piece on g7; Kh7 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### 0857ae07ca390658 · f4 → Kf4

f4 puts the pawn on f4 and leaves the king farther from that pawn. Kf4 moves the king to f4, one step closer to the pawn on f5. Kf4 shortens the king's route to f5; f4 does not. In a reduced position, move the king toward the pawn you need to win or stop.

**Lesson:** In a reduced position, move the king toward the pawn you need to win or stop.

### e61f6104973a3dab · Re6 → Qxf7+

Re6 moves the rook to e6 and leaves that capture unused. Qxf7+ takes the queen on f7 before moving elsewhere. Qxf7+ changes the material on the board immediately; Re6 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### 125a8303bf24c430 · Rf4 → c5

Rf4 allows the larger capture: White answers Rxf4, taking the rook on f4. c5 changes what can be taken; White answers Rxc4, taking the pawn on c4. After Rf4, the reply takes a rook; after c5, it takes only a pawn. When both moves allow a capture, choose the line that keeps the more valuable piece safe.

**Lesson:** When both moves allow a capture, choose the line that keeps the more valuable piece safe.

### d8bd124a52f3414b · Rc7 → Qc7

Rc7 puts the rook on c7 without creating that attack. Qc7 puts the queen on c7, attacking the queen on f4. Qc7 gives the opponent a concrete piece to answer on f4; Rc7 does not. A useful improving move should attack, defend, or create a clear next threat.

**Lesson:** A useful improving move should attack, defend, or create a clear next threat.

### b8b8e263927a7e3f · Bd5 → Rhe8

Bd5 moves the bishop from c4 to d5; White answers g3, attacking the queen on f4. Rhe8 moves the rook from h8 to e8; White answers Qa3, attacking the pawn on a7. The concrete difference is the reply after Bd5 versus the reply after Rhe8. Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

**Lesson:** Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

### 605cbc4f23961a56 · Bf4 → c5

Bf4 puts the bishop on f4 without creating that attack. c5 puts the pawn on c5, attacking the bishop on d4. c5 gives the opponent a concrete piece to answer on d4; Bf4 does not. A useful improving move should attack, defend, or create a clear next threat.

**Lesson:** A useful improving move should attack, defend, or create a clear next threat.

### cdbb0a352c048e83 · Rhd8 → fxe6

Rhd8 moves the rook to d8 and leaves that capture unused. fxe6 takes the queen on e6 before moving elsewhere. fxe6 changes the material on the board immediately; Rhd8 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### 4ef032ae4a2e4a6a · Rc2 → Rh1

Rc2 moves the rook to c2 instead of placing the rook on the h-file. Rh1 puts the rook on h1, on the semi-open h-file. On h1 the rook has the file available; Rc2 leaves the rook out of that lane. When no tactic is urgent, look for an open or semi-open file for a rook.

**Lesson:** When no tactic is urgent, look for an open or semi-open file for a rook.

### 5569802e2753b705 · Kf2 → Ra2

Kf2 moves the king to f2 and leaves the rook on a4. Ra2 moves the rook to a2, where it can reach a1, b2, c2. The rook has more usable squares after Ra2; Kf2 leaves its old limits in place. For a quiet rook move, count the open squares it gains from the new rank or file.

**Lesson:** For a quiet rook move, count the open squares it gains from the new rank or file.

### 125a8303bf24c430 · Rf4 → c5

Rf4 allows the larger capture: White answers Rxf4, taking the rook on f4. c5 changes what can be taken; White answers Rxc4, taking the pawn on c4. After Rf4, the reply takes a rook; after c5, it takes only a pawn. When both moves allow a capture, choose the line that keeps the more valuable piece safe.

**Lesson:** When both moves allow a capture, choose the line that keeps the more valuable piece safe.

### 3013104e6608873c · Kf8 → Bxh6

Kf8 moves the king to f8 and leaves that capture unused. Bxh6 takes the knight on h6 before moving elsewhere. Bxh6 changes the material on the board immediately; Kf8 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### bfeb4894e6ac7350 · Kg3 → Rxc5

Kg3 moves the king to g3 and leaves that capture unused. Rxc5 takes the pawn on c5 before moving elsewhere. Rxc5 changes the material on the board immediately; Kg3 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### 7fc31be9b2e4c201 · Bb7 → Kf8

Bb7 allows this reply: White answers c6, attacking the bishop on b7. Kf8 changes the setup; after it, White answers c6, and the continuation reaches Rfd2. Only Bb7 lets the reply attack the piece on b7; Kf8 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### a415037645fe50cc · Kc5 → Kd3

Kc5 allows this concrete reply: Black answers Re5+, checking the king from e5. Kd3 changes the move order; after it, Black answers Re1, and the continuation reaches Ra4. The check after Kc5 forces a response, while Kd3 avoids that immediate check. Before starting your plan, look for the opponent's checks and deal with the forcing one first.

**Lesson:** Before starting your plan, look for the opponent's checks and deal with the forcing one first.

### 76c0e549b03fd85d · Rb7 → Be2

Rb7 allows this concrete reply: Black answers Rxb7, taking the rook on b7. Be2 changes the position first; after it, Black answers Kg7, and the continuation reaches Ra5. Only Rb7 gives the immediate capture on b7; Be2 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### a7e231e7e6211b0a · Bg5 → Bh4+

Bg5 allows this concrete reply: White answers Rxa7, taking the pawn on a7. Bh4+ changes the position first; after it, White answers g3, attacking the bishop on h4. Only Bg5 gives the immediate capture on a7; Bh4+ avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### 90bd5955d8108d4c · Rfd1 → Qe2

Rfd1 moves the rook from f1 to d1; Black answers Ne5, attacking the queen on f3. Qe2 moves the queen from f3 to e2; Black answers Ne5, attacking the rook on d3. After the same reply Ne5, Rfd1 leads to Qf1, while Qe2 leads to Na4. Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

**Lesson:** Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

### 27762ecce9d8bca5 · Nc5 → c4

Nc5 puts the knight on c5 without creating that attack. c4 puts the pawn on c4, attacking the rook on d5. c4 gives the opponent a concrete piece to answer on d5; Nc5 does not. A useful improving move should attack, defend, or create a clear next threat.

**Lesson:** A useful improving move should attack, defend, or create a clear next threat.

### dcb79c19371dbbb0 · e5 → Ke7

e5 allows this concrete reply: White answers fxe5+, taking the pawn on e5. Ke7 changes the position first; after it, White answers Nd4, attacking the pawn on f5. Only e5 gives the immediate capture on e5; Ke7 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### 27e313329c835ad4 · f4+ → a5

f4+ allows this reply: White answers Ke4, attacking the pawn on f4. a5 changes the setup; after it, White answers c3, and the continuation reaches Kd5. Only f4+ lets the reply attack the piece on f4; a5 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### 095707fe0f6742c9 · Qe3 → h3

Qe3 allows this concrete reply: Black answers Qxg4+, taking the pawn on g4. h3 changes the position first; after it, Black answers Qa4, attacking the knight on b3. Only Qe3 gives the immediate capture on g4; h3 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### aca9169c6bd27b24 · Ke4 → Rxb7

Ke4 moves the king to e4 and leaves that capture unused. Rxb7 takes the pawn on b7 before moving elsewhere. Rxb7 changes the material on the board immediately; Ke4 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### 275b2e4c83980197 · Ng5 → Bf4+

Ng5 allows this concrete reply: Black answers Bg4+, checking the king from g4. Bf4+ changes the move order; after it, Black answers Kd7, and the continuation reaches Kd2. The check after Ng5 forces a response, while Bf4+ avoids that immediate check. Before starting your plan, look for the opponent's checks and deal with the forcing one first.

**Lesson:** Before starting your plan, look for the opponent's checks and deal with the forcing one first.

### 6af9611b21b741db · Nd3 → Ne4

Nd3 allows this concrete reply: White answers Nxd3, taking the knight on d3. Ne4 changes the position first; after it, White answers Ra5, attacking the bishop on b5. Only Nd3 gives the immediate capture on d3; Ne4 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### 26a4cd472098b3b0 · Ke2 → Kf3

Ke2 puts the king on e2 while the king stays farther away. Kf3 brings the king from f2 toward the centre on f3. Kf3 gives the king a direct route to the pawns; Ke2 spends the move elsewhere. With few pieces left, activate the king before making a move that can wait.

**Lesson:** With few pieces left, activate the king before making a move that can wait.

### 985643a6702332f0 · Ba6 → g5+

Ba6 allows this concrete reply: Black answers Rxg4, taking the pawn on g4. g5+ changes the position first; after it, Black answers Kg7, and the continuation reaches Be6. Only Ba6 gives the immediate capture on g4; g5+ avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### beed1274614c0d97 · Nxc2 → Nxg8

Nxc2 takes the pawn on c2 instead. Nxg8 takes the bishop on g8. The bishop on g8 is the larger immediate target, so Nxg8 comes first. When several captures are legal, compare the value and the reply before choosing one.

**Lesson:** When several captures are legal, compare the value and the reply before choosing one.

### 72f891bbd2f23df1 · Rh3+ → f4+

Rh3+ allows this reply: White answers Kf4, attacking the pawn on f5. f4+ changes the setup; after it, White answers Kxf4, taking the pawn on f4. Only Rh3+ lets the reply attack the piece on f5; f4+ avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### fc2e8471e60683d5 · Ra6 → Nxh3+

Ra6 moves the rook to a6 and leaves that capture unused. Nxh3+ takes the pawn on h3 before moving elsewhere. Nxh3+ changes the material on the board immediately; Ra6 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### 95a3e77df2bb234e · b5 → Bd7

b5 allows this concrete reply: White answers axb5, taking the pawn on b5. Bd7 changes the position first; after it, White answers c4, attacking the pawn on d5. Only b5 gives the immediate capture on b5; Bd7 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### 4ab39bde39491209 · Re3 → Rh3

Re3 allows this reply: White answers Rh2, attacking the pawn on h7. Rh3 changes the setup; after it, White answers Rf2+, checking the king from f2. Only Re3 lets the reply attack the piece on h7; Rh3 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### 94c8f2a8d1854f85 · Qe3+ → Qf1+

Qe3+ moves the queen from f3 to e3; White answers Kd1, and the continuation reaches Qf3+. Qf1+ moves the queen from f3 to f1; White answers Kd2, and the continuation reaches Qf4+. The concrete difference is the reply after Qe3+ versus the reply after Qf1+. Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

**Lesson:** Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

### 1bb40e1b4e4b6d2b · c6 → c5

c6 moves the pawn to c6 while that pawn stays on c7. c5 advances the pawn from c7 to c5, one rank closer to promotion. c5 gains one step in the pawn race; c6 spends the move elsewhere. In a pawn ending, count both sides' moves to promotion before spending a move on the king or another pawn.

**Lesson:** In a pawn ending, count both sides' moves to promotion before spending a move on the king or another pawn.

### 4ab39bde39491209 · Re3 → Rh3

Re3 allows this reply: White answers Rh2, attacking the pawn on h7. Rh3 changes the setup; after it, White answers Kd4, and the continuation reaches h5. Only Re3 lets the reply attack the piece on h7; Rh3 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### ce3942534dcb6386 · Ke3 → Ra8

Ke3 allows this reply: Black answers Rb4, attacking the bishop on b5. Ra8 changes the setup; after it, Black answers Re4+, checking the king from e4. Only Ke3 lets the reply attack the piece on b5; Ra8 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### f4b073d39c42cf79 · Kh4 → Rxd6+

Kh4 moves the king to h4 and leaves that capture unused. Rxd6+ takes the bishop on d6 before moving elsewhere. Rxd6+ changes the material on the board immediately; Kh4 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### 2624e01e822ec20d · d2 → Bb7

d2 allows this reply: White answers Rd1, attacking the pawn on d2. Bb7 changes the setup; after it, White answers f4, and the continuation reaches Bd5. Only d2 lets the reply attack the piece on d2; Bb7 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### 75328ef4fd599876 · Kc5 → Ke7

Kc5 moves the king from d6 to c5; White answers g4, and the continuation reaches f6. Ke7 moves the king from d6 to e7; White answers b4, and the continuation reaches Kf6. The concrete difference is the reply after Kc5 versus the reply after Ke7. Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

**Lesson:** Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

### 0daf267380bd0d9d · h4+ → f6+

h4+ also checks from h4, but Black answers Kxh4, taking the pawn on h4. f6+ checks from f6; after Kxf6, Bxc4 takes the pawn on c4. f6+ connects the check to a concrete capture; h4+ gives check without that same follow-up. Compare checks by what they force next; a check is useful when the follow-up wins something or improves the result.

**Lesson:** Compare checks by what they force next; a check is useful when the follow-up wins something or improves the result.

### 71ed10743c734ed0 · h5 → c5

h5 puts the pawn on h5 without creating that attack. c5 puts the pawn on c5, attacking the bishop on d4. c5 gives the opponent a concrete piece to answer on d4; h5 does not. A useful improving move should attack, defend, or create a clear next threat.

**Lesson:** A useful improving move should attack, defend, or create a clear next threat.

### 78c4121b9255b8e5 · Nd5 → Rg1

Nd5 moves the knight to d5 instead of placing the rook on the g-file. Rg1 puts the rook on g1, on the semi-open g-file. On g1 the rook has the file available; Nd5 leaves the rook out of that lane. When no tactic is urgent, look for an open or semi-open file for a rook.

**Lesson:** When no tactic is urgent, look for an open or semi-open file for a rook.

### 15531b696d9d048e · Bxc4 → Rd2

Bxc4 moves the bishop to c4 instead of placing the rook on the d-file. Rd2 puts the rook on d2, on the open d-file. On d2 the rook has the file available; Bxc4 leaves the rook out of that lane. When no tactic is urgent, look for an open or semi-open file for a rook.

**Lesson:** When no tactic is urgent, look for an open or semi-open file for a rook.

### d8a9e7ce524b204d · Ke5 → Rg1

Ke5 moves the king to e5 instead of placing the rook on the g-file. Rg1 puts the rook on g1, on the open g-file. On g1 the rook has the file available; Ke5 leaves the rook out of that lane. When no tactic is urgent, look for an open or semi-open file for a rook.

**Lesson:** When no tactic is urgent, look for an open or semi-open file for a rook.

### 90e227e140fa82ab · d5 → Bd4

d5 allows this concrete reply: White answers Nxc5, taking the bishop on c5. Bd4 changes the position first; after it, White answers Rad1, attacking the bishop on d4. Only d5 gives the immediate capture on c5; Bd4 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### e57327d7ea3dd613 · Re3 → Kg7

Re3 moves the rook from a3 to e3; White answers b6, and the continuation reaches Re4+. Kg7 moves the king from g6 to g7; White answers Rf4, attacking the pawn on f3. The concrete difference is the reply after Re3 versus the reply after Kg7. Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

**Lesson:** Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

### 99d55107bed0edf6 · a4 → e5

a4 allows this concrete reply: White answers dxe6, taking the pawn on e6. e5 changes the position first; after it, White answers d6, and the continuation reaches Rc8. Only a4 gives the immediate capture on e6; e5 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### 8e6e143376263786 · Kb4 → Ra8

Kb4 moves the king to b4 instead of placing the rook on the a-file. Ra8 puts the rook on a8, on the semi-open a-file. On a8 the rook has the file available; Kb4 leaves the rook out of that lane. When no tactic is urgent, look for an open or semi-open file for a rook.

**Lesson:** When no tactic is urgent, look for an open or semi-open file for a rook.

### f05ac7cd1415d1ef · Be8 → Ra6

Be8 allows this concrete reply: Black answers Rxh2, taking the pawn on h2. Ra6 changes the position first; after it, Black answers Rf6, and the continuation reaches h4. Only Be8 gives the immediate capture on h2; Ra6 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### 7db63dd7a5aee2fe · Ree7 → Qc4

Ree7 allows this concrete reply: White answers fxe6, taking the pawn on e6. Qc4 changes the position first; after it, White answers Nd4, attacking the pawn on c6. Only Ree7 gives the immediate capture on e6; Qc4 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### eb60bd60802c3454 · Re7 → Rb7

Re7 moves the rook from h7 to e7; Black answers Rd2, attacking the pawn on b2. Rb7 moves the rook from h7 to b7; Black answers Rd2, attacking the pawn on b2. After the same reply Rd2, Re7 leads to Rb7, while Rb7 leads to Kf3. Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

**Lesson:** Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

### cb1e1e579793ad53 · Rh5 → Kf3

Rh5 puts the rook on h5 while the king stays farther away. Kf3 brings the king from e2 toward the centre on f3. Kf3 gives the king a direct route to the pawns; Rh5 spends the move elsewhere. With few pieces left, activate the king before making a move that can wait.

**Lesson:** With few pieces left, activate the king before making a move that can wait.

### 6f3ba97759201c04 · g4 → Bg7

g4 allows this concrete reply: White answers fxg4, taking the pawn on g4. Bg7 changes the position first; after it, White answers a4, and the continuation reaches Rd8. Only g4 gives the immediate capture on g4; Bg7 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### 179e2b13011ca8f7 · Ra7 → Rc7

Ra7 allows this reply: Black answers Rd2, attacking the pawn on b2. Rc7 changes the setup; after it, Black answers a5, moving from a6 to a5. Only Ra7 lets the reply attack the piece on b2; Rc7 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### f9b0c67aeba7f096 · Kg6 → Re4

Kg6 moves the king to g6 instead of placing the rook on the e-file. Re4 puts the rook on e4, on the open e-file. On e4 the rook has the file available; Kg6 leaves the rook out of that lane. When no tactic is urgent, look for an open or semi-open file for a rook.

**Lesson:** When no tactic is urgent, look for an open or semi-open file for a rook.

### 5abbb97d3efe472d · Qb8 → Qa2

Qb8 moves the queen to b8 without adding that defender. Qa2 places the queen on a2, where it adds a defender to the pawn on d5. After Qa2, the pawn on d5 has more support; after Qb8, it does not. When one of your pieces is attacked, count its attackers and defenders before moving elsewhere.

**Lesson:** When one of your pieces is attacked, count its attackers and defenders before moving elsewhere.

### 09143374cda4472e · Re7+ → Rxh7

Re7+ moves the rook to e7 and leaves that capture unused. Rxh7 takes the pawn on h7 before moving elsewhere. Rxh7 changes the material on the board immediately; Re7+ does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### a5e236f912e1ea09 · Kf7 → h5

Kf7 moves the king to f7 and leaves that pawn on h7. h5 advances the passed pawn to h5, one rank closer to promotion. h5 makes the opponent answer the passed pawn sooner; Kf7 gives it no progress. In an endgame, calculate whether a passed pawn can advance safely before making a side move.

**Lesson:** In an endgame, calculate whether a passed pawn can advance safely before making a side move.

### 64f4e399b9ae526c · Nb5 → Be7

Nb5 puts the knight on b5 instead. Be7 moves the bishop from f8 toward the centre on e7, where it reaches h4, g5, d6. The bishop has central work from e7; Nb5 uses the move on b5. When moves are quiet, prefer the piece whose new square gives it more concrete jobs.

**Lesson:** When moves are quiet, prefer the piece whose new square gives it more concrete jobs.

### 1acb1464b0586d52 · exd5 → Qe2

exd5 allows this reply: Black answers Ng4, attacking the bishop on e3. Qe2 changes the setup; after it, Black answers dxe4, taking the pawn on e4. Only exd5 lets the reply attack the piece on e3; Qe2 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### c3825dda8669bb82 · Rc7 → Bxb5

Rc7 moves the rook to c7 and leaves that capture unused. Bxb5 takes the pawn on b5 before moving elsewhere. Bxb5 changes the material on the board immediately; Rc7 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### b130047ebb71bc81 · Rd8+ → Be5

Rd8+ allows this concrete reply: Black answers Rxd8, taking the rook on d8. Be5 changes the position first; after it, Black answers a5, attacking the pawn on b4. Only Rd8+ gives the immediate capture on d8; Be5 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### 659bd7ef6efd6e08 · Rab1 → a5

Rab1 allows this concrete reply: Black answers Rxb6, taking the rook on b6. a5 changes the position first; after it, Black answers Bb5, attacking the pawn on d3. Only Rab1 gives the immediate capture on b6; a5 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### 8a01dc8cb098edd4 · Bc4 → Be2

Bc4 allows this concrete reply: Black answers Nxc4, taking the bishop on c4. Be2 changes the position first; after it, Black answers Bc5, attacking the pawn on f2. Only Bc4 gives the immediate capture on c4; Be2 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### 06b8182067bd3a04 · Qxd6 → cxd6

Qxd6 uses the more valuable queen from d7 for the same capture. cxd6 uses the pawn from c7 to recapture on d6. Both moves capture on d6, but cxd6 keeps the queen on d7. When two pieces can recapture, compare which piece you want to keep active afterward.

**Lesson:** When two pieces can recapture, compare which piece you want to keep active afterward.

### fb2a59fa67fa80b8 · Rxe3 → Rd1

Rxe3 allows this concrete reply: White answers Rd8+, checking the king from d8. Rd1 changes the move order; after it, White answers Rd8, attacking the rook on e8. The check after Rxe3 forces a response, while Rd1 avoids that immediate check. Before starting your plan, look for the opponent's checks and deal with the forcing one first.

**Lesson:** Before starting your plan, look for the opponent's checks and deal with the forcing one first.

### 0189d26f45ae6380 · Bf6 → Bxf5

Bf6 moves the bishop to f6 and leaves that capture unused. Bxf5 takes the knight on f5 before moving elsewhere. Bxf5 changes the material on the board immediately; Bf6 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### fa93917d9e01396c · Kf3 → Kg2

Kf3 moves the king from f2 to f3; Black answers Bc6, and the continuation reaches Ke2. Kg2 moves the king from f2 to g2; Black answers Bc6, and the continuation reaches Kh2. After the same reply Bc6, Kf3 leads to Ke2, while Kg2 leads to Kh2. Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

**Lesson:** Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

### 646d72d8d13f558c · Ne4 → Nd5

Ne4 puts the knight on e4 without creating that attack. Nd5 puts the knight on d5, attacking the queen on f4. Nd5 gives the opponent a concrete piece to answer on f4; Ne4 does not. A useful improving move should attack, defend, or create a clear next threat.

**Lesson:** A useful improving move should attack, defend, or create a clear next threat.

### 5c8ca6326098c345 · f3 → Bc4

f3 allows this reply: Black answers Be6, attacking the pawn on a2. Bc4 changes the setup; after it, Black answers Bf5, and the continuation reaches Rc1. Only f3 lets the reply attack the piece on a2; Bc4 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### df7dc31ddab9899d · Rf3 → dxc4

Rf3 moves the rook to f3 and leaves that capture unused. dxc4 takes the pawn on c4 before moving elsewhere. dxc4 changes the material on the board immediately; Rf3 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### a378dfb84c49cb5d · Rc8 → Rb8

Rc8 moves the rook to c8 instead of placing the rook on the b-file. Rb8 puts the rook on b8, on the open b-file. On b8 the rook has the file available; Rc8 leaves the rook out of that lane. When no tactic is urgent, look for an open or semi-open file for a rook.

**Lesson:** When no tactic is urgent, look for an open or semi-open file for a rook.

### 15a91241182cd2bb · Rg1+ → Rh4

Rg1+ moves the rook from g4 to g1; White answers Kc2, moving from d1 to c2. Rh4 moves the rook from g4 to h4; White answers Re2, attacking the rook on e8. The concrete difference is the reply after Rg1+ versus the reply after Rh4. Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

**Lesson:** Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

### e8911c009ba3c31f · Bd7 → Qxe3

Bd7 moves the bishop to d7 and leaves that capture unused. Qxe3 takes the pawn on e3 before moving elsewhere. Qxe3 changes the material on the board immediately; Bd7 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### 7af38a371c575ead · Re2 → Be2

Re2 allows this concrete reply: White answers bxc4, taking the pawn on c4. Be2 changes the position first; after it, White answers Re1, attacking the bishop on e2. Only Re2 gives the immediate capture on c4; Be2 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### 2d323bf4f9bc1337 · b4 → Bxb8

b4 moves the pawn to b4 and leaves that capture unused. Bxb8 takes the rook on b8 before moving elsewhere. Bxb8 changes the material on the board immediately; b4 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### da396e9a5cf9fe80 · c5 → Bd6

c5 puts the pawn on c5 without creating that attack. Bd6 puts the bishop on d6, attacking the bishop on e7. Bd6 gives the opponent a concrete piece to answer on e7; c5 does not. A useful improving move should attack, defend, or create a clear next threat.

**Lesson:** A useful improving move should attack, defend, or create a clear next threat.

### 65bfb745a5ac56b9 · Ba6 → Ra5

Ba6 moves the bishop from e2 to a6; Black answers Rc1+, checking the king from c1. Ra5 moves the rook from a7 to a5; Black answers Rc1+, checking the king from c1. After the same reply Rc1+, Ba6 leads to Kh2, while Ra5 leads to Kh2. Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

**Lesson:** Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

### 4e05063c1ad500dc · Qa5 → Qf4

Qa5 puts the queen on a5 without creating that attack. Qf4 puts the queen on f4, attacking the pawn on f3. Qf4 gives the opponent a concrete piece to answer on f3; Qa5 does not. A useful improving move should attack, defend, or create a clear next threat.

**Lesson:** A useful improving move should attack, defend, or create a clear next threat.

### 12fd39c4883b7d77 · Kd6 → Kd8

Kd6 allows this reply: White answers Nd4, attacking the rook on c2. Kd8 changes the setup; after it, White answers Rxh7, taking the pawn on h7. Only Kd6 lets the reply attack the piece on c2; Kd8 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### c6d3d177f45aa517 · Bb5 → Qh6

Bb5 allows this concrete reply: White answers Bg4+, checking the king from g4. Qh6 changes the move order; after it, White answers Qd5, attacking the bishop on d7. The check after Bb5 forces a response, while Qh6 avoids that immediate check. Before starting your plan, look for the opponent's checks and deal with the forcing one first.

**Lesson:** Before starting your plan, look for the opponent's checks and deal with the forcing one first.

### fd8e4067b83a3303 · Rxc8 → Bxc5

Rxc8 puts the rook on c8 without creating that attack. Bxc5 puts the bishop on c5, attacking the pawn on b4. Bxc5 gives the opponent a concrete piece to answer on b4; Rxc8 does not. A useful improving move should attack, defend, or create a clear next threat.

**Lesson:** A useful improving move should attack, defend, or create a clear next threat.

### a6e1c0a600a0e07b · Nb5 → Rxf7

Nb5 moves the knight to b5 and leaves that capture unused. Rxf7 takes the pawn on f7 before moving elsewhere. Rxf7 changes the material on the board immediately; Nb5 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### a02baa4e819110f7 · Rf8 → Kg7

Rf8 allows this concrete reply: White answers Nxf6, taking the pawn on f6. Kg7 changes the position first; after it, White answers Bd1, and the continuation reaches Ra2. Only Rf8 gives the immediate capture on f6; Kg7 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### dc1c976a67fa9dff · b4 → f5

b4 allows this concrete reply: White answers Nxf6+, taking the pawn on f6. f5 changes the position first; after it, White answers Nf6+, checking the king from f6. Only b4 gives the immediate capture on f6; f5 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### 23876894e9bdd2af · Ba6 → Ne6

Ba6 allows this concrete reply: White answers Bg5+, checking the king from g5. Ne6 changes the move order; after it, White answers Bh6, attacking the rook on f8. The check after Ba6 forces a response, while Ne6 avoids that immediate check. Before starting your plan, look for the opponent's checks and deal with the forcing one first.

**Lesson:** Before starting your plan, look for the opponent's checks and deal with the forcing one first.

### 8e52c1c659e14ccc · Kg3 → Ba6

Kg3 moves the king from h2 to g3; Black answers e2, and the continuation reaches Rb3. Ba6 moves the bishop from b7 to a6; Black answers Bd1, attacking the pawn on f3. The concrete difference is the reply after Kg3 versus the reply after Ba6. Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

**Lesson:** Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

### 09be62497c4b0ee6 · Ke4 → Rf8+

Ke4 moves the king to e4 instead of placing the rook on the f-file. Rf8+ puts the rook on f8, on the open f-file. On f8 the rook has the file available; Ke4 leaves the rook out of that lane. When no tactic is urgent, look for an open or semi-open file for a rook.

**Lesson:** When no tactic is urgent, look for an open or semi-open file for a rook.

### 35da4cfb6f3d6c21 · Rxg7+ → fxg7

Rxg7+ uses the more valuable rook from g6 for the same capture. fxg7 uses the pawn from f6 to recapture on g7. Both moves capture on g7, but fxg7 keeps the rook on g6. When two pieces can recapture, compare which piece you want to keep active afterward.

**Lesson:** When two pieces can recapture, compare which piece you want to keep active afterward.

### 9e4b5c0f3fc62418 · Kxf6 → Qxe1

Kxf6 takes the pawn on f6 instead. Qxe1 takes the rook on e1. The rook on e1 is the larger immediate target, so Qxe1 comes first. When several captures are legal, compare the value and the reply before choosing one.

**Lesson:** When several captures are legal, compare the value and the reply before choosing one.

### b0dab5603bde4df0 · Ke1 → Kg1

Ke1 allows this concrete reply: Black answers Re2+, checking the king from e2. Kg1 changes the move order; after it, Black answers Re8, attacking the bishop on e4. The check after Ke1 forces a response, while Kg1 avoids that immediate check. Before starting your plan, look for the opponent's checks and deal with the forcing one first.

**Lesson:** Before starting your plan, look for the opponent's checks and deal with the forcing one first.

### a9d07968afee611e · Kf7 → Ref7

Kf7 moves the king to f7 instead of placing the rook on the f-file. Ref7 puts the rook on f7, on the open f-file. On f7 the rook has the file available; Kf7 leaves the rook out of that lane. When no tactic is urgent, look for an open or semi-open file for a rook.

**Lesson:** When no tactic is urgent, look for an open or semi-open file for a rook.

### 89e610b4a2ccdfb8 · Ke4 → a5

Ke4 allows this reply: White answers b4, attacking the pawn on c5. a5 changes the setup; after it, White answers Ke1, and the continuation reaches Ke4. Only Ke4 lets the reply attack the piece on c5; a5 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### 77ab535cc9e6dca0 · Re6+ → Bd5

Re6+ puts the rook on e6 instead. Bd5 moves the bishop from c4 toward the centre on d5, where it reaches h1, a2, g2. The bishop has central work from d5; Re6+ uses the move on e6. When moves are quiet, prefer the piece whose new square gives it more concrete jobs.

**Lesson:** When moves are quiet, prefer the piece whose new square gives it more concrete jobs.

### 4188a2b637b61e72 · Kf5 → a5

Kf5 allows this concrete reply: White answers hxg5, taking the pawn on g5. a5 changes the position first; after it, White answers Ke4, attacking the pawn on f4. Only Kf5 gives the immediate capture on g5; a5 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### d3f63204620b0e1b · Re8 → Rh3

Re8 moves the rook to e8 instead of placing the rook on the h-file. Rh3 puts the rook on h3, on the semi-open h-file. On h3 the rook has the file available; Re8 leaves the rook out of that lane. When no tactic is urgent, look for an open or semi-open file for a rook.

**Lesson:** When no tactic is urgent, look for an open or semi-open file for a rook.

### 4c1b24a6848e3942 · bxc3 → b3+

bxc3 allows this reply: White answers Rc4, attacking the pawn on c3. b3+ changes the setup; after it, White answers Kb1, and the continuation reaches Rf6. Only bxc3 lets the reply attack the piece on c3; b3+ avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### 7c5b58a186d4fe6c · g5 → Qd3

g5 puts the pawn on g5 without creating that attack. Qd3 puts the queen on d3, attacking the knight on f3. Qd3 gives the opponent a concrete piece to answer on f3; g5 does not. A useful improving move should attack, defend, or create a clear next threat.

**Lesson:** A useful improving move should attack, defend, or create a clear next threat.

### 098d0bdd10296cc7 · Re8 → gxh6

Re8 moves the rook to e8 and leaves that capture unused. gxh6 takes the bishop on h6 before moving elsewhere. gxh6 changes the material on the board immediately; Re8 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### c72251f317c16409 · Rf1 → Rc1

Rf1 moves the rook from a1 to f1; Black answers Rxc3, taking the pawn on c3. Rc1 moves the rook from a1 to c1; Black answers Rxa3, taking the pawn on a3. The concrete difference is the reply after Rf1 versus the reply after Rc1. Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

**Lesson:** Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

### 530bae51cf3b65e0 · Kf6 → Ng3

Kf6 moves the king from e7 to f6; White answers Kh2, attacking the pawn on h3. Ng3 moves the knight from e4 to g3; White answers Nd4, attacking the pawn on f5. The concrete difference is the reply after Kf6 versus the reply after Ng3. Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

**Lesson:** Before choosing between quiet moves, calculate the opponent's strongest reply to each one.

### d95aba942ddfe204 · Qb6 → O-O-O

Qb6 allows this concrete reply: White answers Rxf7, taking the pawn on f7. O-O-O changes the position first; after it, White answers Bg4, attacking the bishop on d7. Only Qb6 gives the immediate capture on f7; O-O-O avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### 7995afedcf30429f · Rd6 → Qb7

Rd6 allows this reply: White answers Qa4, attacking the bishop on a6. Qb7 changes the setup; after it, White answers Qxb7+, taking the queen on b7. Only Rd6 lets the reply attack the piece on a6; Qb7 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### 78047cb9bd335c22 · Re3 → Rc5+

Re3 moves the rook to e3 instead of placing the rook on the c-file. Rc5+ puts the rook on c5, on the open c-file. On c5 the rook has the file available; Re3 leaves the rook out of that lane. When no tactic is urgent, look for an open or semi-open file for a rook.

**Lesson:** When no tactic is urgent, look for an open or semi-open file for a rook.

### 795f778aaebc4707 · Ba6 → Be4

Ba6 puts the bishop on a6 without creating that attack. Be4 puts the bishop on e4, attacking the pawn on g2. Be4 gives the opponent a concrete piece to answer on g2; Ba6 does not. A useful improving move should attack, defend, or create a clear next threat.

**Lesson:** A useful improving move should attack, defend, or create a clear next threat.

### dd662ab4de4e561e · Rb1 → Nxd5

Rb1 moves the rook to b1 and leaves that capture unused. Nxd5 takes the pawn on d5 before moving elsewhere. Nxd5 changes the material on the board immediately; Rb1 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### 1b89da7ae6f91174 · Rxg6 → Rc7+

Rxg6 allows this concrete reply: White answers h4+, checking the king from h4. Rc7+ changes the move order; after it, White answers Kb3, and the continuation reaches Kh6. The check after Rxg6 forces a response, while Rc7+ avoids that immediate check. Before starting your plan, look for the opponent's checks and deal with the forcing one first.

**Lesson:** Before starting your plan, look for the opponent's checks and deal with the forcing one first.

### 8329153a724dca65 · Nf5 → Rc1

Nf5 allows this concrete reply: Black answers Rg2+, checking the king from g2. Rc1 changes the move order; after it, Black answers Kg6, and the continuation reaches c4. The check after Nf5 forces a response, while Rc1 avoids that immediate check. Before starting your plan, look for the opponent's checks and deal with the forcing one first.

**Lesson:** Before starting your plan, look for the opponent's checks and deal with the forcing one first.

### 55ab35d828a65a6b · f4 → Kg3

f4 puts the pawn on f4 and leaves the king farther from that pawn. Kg3 moves the king to g3, one step closer to the pawn on h6. Kg3 shortens the king's route to h6; f4 does not. In a reduced position, move the king toward the pawn you need to win or stop.

**Lesson:** In a reduced position, move the king toward the pawn you need to win or stop.

### 6d99ca37b9cdb9c5 · Re1+ → Ne4

Re1+ moves the rook to e1 without adding that defender. Ne4 places the knight on e4, where it adds a defender to the pawn on f2. After Ne4, the pawn on f2 has more support; after Re1+, it does not. When one of your pieces is attacked, count its attackers and defenders before moving elsewhere.

**Lesson:** When one of your pieces is attacked, count its attackers and defenders before moving elsewhere.

### ec3e4d9d5f6a8aab · Nxh3+ → Qd3

Nxh3+ allows this reply: White answers Kg2, attacking the knight on h3. Qd3 changes the setup; after it, White answers Qxd3, taking the queen on d3. Only Nxh3+ lets the reply attack the piece on h3; Qd3 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### a06c80ab881b9b95 · Re8 → Nd5

Re8 puts the rook on e8 without creating that attack. Nd5 puts the knight on d5, attacking the bishop on b4. Nd5 gives the opponent a concrete piece to answer on b4; Re8 does not. A useful improving move should attack, defend, or create a clear next threat.

**Lesson:** A useful improving move should attack, defend, or create a clear next threat.

### 6bd982c6baceee54 · dxe5 → d5

dxe5 allows this concrete reply: White answers Rxe5+, taking the pawn on e5. d5 changes the position first; after it, White answers e6, and the continuation reaches a5. Only dxe5 gives the immediate capture on e5; d5 avoids that version. After choosing a move, scan every opponent capture before judging the move safe.

**Lesson:** After choosing a move, scan every opponent capture before judging the move safe.

### 3182c77f5d3e2f63 · Re8+ → Ne3

Re8+ allows this reply: Black answers Kf7, attacking the rook on e8. Ne3 changes the setup; after it, Black answers Rxh2+, taking the pawn on h2. Only Re8+ lets the reply attack the piece on e8; Ne3 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

### 6c51db5fabd93cec · c4 → Rxe5

c4 moves the pawn to c4 and leaves that capture unused. Rxe5 takes the rook on e5 before moving elsewhere. Rxe5 changes the material on the board immediately; c4 does not. Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

**Lesson:** Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement.

### 0189d646b0d2f721 · Nc8 → Nc6

Nc8 puts the knight on c8 instead. Nc6 moves the knight from e7 toward the centre on c6, where it reaches b4, d4, a5. The knight has central work from c6; Nc8 uses the move on c8. When moves are quiet, prefer the piece whose new square gives it more concrete jobs.

**Lesson:** When moves are quiet, prefer the piece whose new square gives it more concrete jobs.

### fdb1d91cf50f0f27 · Ne7 → Qb5

Ne7 allows this reply: White answers Rfe1, attacking the knight on e7. Qb5 changes the setup; after it, White answers Rfe1, and the continuation reaches Qd5. Only Ne7 lets the reply attack the piece on e7; Qb5 avoids that version. Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.

**Lesson:** Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond.
