# LLM Caption Test
_Source: queue · Games: 1 · Model: gpt-4o-mini_

## 1. `a50ddf30-c154-4486-81d9-0219eb621440` (TACTICAL_BLUNDER) — 34 moves

**1. e4** (opp · context · cp_loss=0)
- existing: e4. Opponent claims the center.
- **LLM**: e4 claims the center immediately, opening lines for your pieces.
- facts: rule={'category': 'opening_central_pawn', 'ref_field': 'target_square', 'priority_level': 9}

**1. e5** (user · good · cp_loss=0)
- existing: e5. Stakes a claim in the center.
- **LLM**: e5 claims the center — a strong opening move.
- facts: best=e5 | rule={'category': 'opening_central_pawn', 'ref_field': 'target_square', 'priority_level': 9}

**2. Nf3** (opp · context · cp_loss=2)
- existing: Opponent develops the knight to f3.
- **LLM**: Nf3 develops a piece, but finish bringing out your knight and bishop first.
- facts: rule={'category': 'development', 'ref_field': 'moving_piece_type', 'priority_level': 10}

**2. Nc6** (user · good · cp_loss=9)
- existing: Develops the knight to c6.
- **LLM**: Nc6 develops your knight nicely. Keep bringing out your pieces.
- facts: best=Nc6 | rule={'category': 'development', 'ref_field': 'moving_piece_type', 'priority_level': 10}

**3. Bc4** (opp · context · cp_loss=5)
- existing: Opponent develops the bishop to c4.
- **LLM**: Bc4 develops a piece but doesn't attack the center. Focus on claiming the center first.
- facts: rule={'category': 'development', 'ref_field': 'moving_piece_type', 'priority_level': 10}

**3. Nd4** (user · good · cp_loss=87)
- existing: Develops the knight to d4.
- **LLM**: Nd4 moves the same piece twice — develop your knight to f6 instead to hit their loose piece.
- facts: best=Nf6 | rule={'category': 'development', 'ref_field': 'moving_piece_type', 'priority_level': 10} | principles=TAC_HANGING_PIECE,OP_SAME_PIECE_TWICE

**4. Nxe5** (opp · opp_mistake · cp_loss=194)
- existing: Nxe5. Opponent grabs the pawn — nothing was defending it.
- **LLM**: Nxe5 grabs a pawn, but your knight and bishop are still at home — finish development first.
- facts: rule={'category': 'material', 'ref_field': 'material_delta_played_cp', 'priority_level': 6} | principles=OP_FINISH_DEVELOPMENT

**4. Qg5** (user · good · cp_loss=9)
- existing: Qg5 forks the knight on e5 and the pawn on g2.
- **LLM**: Qg5 creates a fork; you attack two pieces at once, forcing a tough choice.
- facts: best=Qg5 | rule={'category': 'tactic_played', 'ref_field': 'multi_target_attack_evidence', 'priority_level': 2} | principles=TAC_FORK_PATTERN

**5. Nxf7** (opp · opp_blunder · cp_loss=426)
- existing: Opponent's Nxf7 drops about 4 pawns.
- **LLM**: Nxf7 is a blunder — it leaves the knight hanging and exposes your position.
- facts: rule={'category': 'blunder', 'ref_field': 'cp_loss', 'priority_level': 11}

**5. Qxg2** (user · good · cp_loss=0)
- existing: Qxg2 forks the rook on h1 and the pawn on f2.
- **LLM**: Qxg2 forks two pieces at once — they can save only one.
- facts: best=Qxg2 | rule={'category': 'tactic_played', 'ref_field': 'multi_target_attack_evidence', 'priority_level': 2} | principles=TAC_FORK_PATTERN

**6. d3** (opp · context · cp_loss=-8)
- existing: _(no caption)_
- **LLM**: _(empty — nothing to teach)_
- facts: (none)

**6. Qxh1+** (user · good · cp_loss=7)
- existing: Qxh1+. Pins the king on e1 against the queen on d1.
- **LLM**: Qxh1+ captures a free piece, taking advantage of the pin on the knight.
- facts: best=Qxh1+ | rule={'category': 'tactic_played', 'ref_field': 'aligned_pieces_evidence', 'priority_level': 2} | shape=Free Piece | principles=TAC_PIN_PATTERN

**7. Kd2** (opp · context · cp_loss=2)
- existing: _(no caption)_
- **LLM**: _(empty — nothing to teach)_
- facts: (none)

**7. Bb4+** (user · mistake · cp_loss=160)
- existing: _(no caption)_
- **LLM**: Bb4+ is a mistake; Qxd1+ wins the queen and changes the game.
- facts: best=Qxd1+ | rule={'category': 'check_plain', 'ref_field': 'is_check', 'priority_level': 4} | principles=TAC_CHANGED_AFTER_MOVE

**8. c3** (opp · opp_inaccuracy · cp_loss=88)
- existing: c3 threatens the bishop on b4.
- **LLM**: c3 doesn't create any threats. Look for moves that attack or develop instead.
- facts: rule={'category': 'threat', 'ref_field': 'threats_created', 'priority_level': 8}

**8. Nf3+** (user · mistake · cp_loss=172)
- existing: _(no caption)_
- **LLM**: Nf3+ gives a check but misses the stronger Qxh2, which wins a pawn and threatens more.
- facts: best=Qxh2 | rule={'category': 'check_extra', 'ref_field': 'threats_created', 'priority_level': 3}

**9. Ke2** (opp · context · cp_loss=34)
- existing: _(no caption)_
- **LLM**: Ke2 is a step backward. Your king needs safety; castle instead.
- facts: (none)

**9. Nd4+** (user · blunder · cp_loss=308)
- existing: _(no caption)_
- **LLM**: Nd4+ misses Qxd1+ for a forced check; your knight's hanging and the position changed after your move.
- facts: best=Qxd1+ | rule={'category': 'check_plain', 'ref_field': 'is_check', 'priority_level': 4} | shape=Queen-Knight Mate | principles=TAC_HANGING_PIECE,TAC_DEFENDER_COUNT,TAC_CHANGED_AFTER_MOVE

**10. cxd4** (opp · context · cp_loss=11)
- existing: cxd4. Opponent forced to recapture the knight.
- **LLM**: The pawn capture on d4 was forced — you had to recapture that piece.
- facts: rule={'category': 'forced_recapture', 'ref_field': 'captured_piece_type', 'priority_level': 5}

**10. Qg2** (user · mistake · cp_loss=182)
- existing: Qg2 loses about 2 pawns. Qxh2 was better. Opponent plays Nxh8 winning your rook.
- **LLM**: Qg2 hangs the opportunity to take the h2 pawn. Qxh2 wins it and sets up a skewer on d1.
- facts: best=Qxh2 | rule={'category': 'blunder', 'ref_field': 'cp_loss', 'priority_level': 11} | shape=Skewer | principles=OP_QUEEN_OUT_EARLY,TAC_CHECKS_CAPTURES_THREATS

**11. Nxh8** (opp · context · cp_loss=-35)
- existing: Nxh8 uncovers the bishop hitting the knight on g8.
- **LLM**: Nxh8 leaves their rook with no safe square — attack it again and it falls.
- facts: rule={'category': 'tactic_played', 'ref_field': 'discovered_attack_evidence', 'priority_level': 2} | shape=No Safe Square

**11. Nf6** (user · good · cp_loss=41)
- existing: Develops the knight to f6.
- **LLM**: Nf6 is good, but Qg4+ gives a check and sets up a skewer.
- facts: best=Qg4+ | rule={'category': 'development', 'ref_field': 'moving_piece_type', 'priority_level': 10} | principles=TAC_CHECKS_CAPTURES_THREATS,TAC_SKEWER_PATTERN

**12. a3** (opp · opp_mistake · cp_loss=216)
- existing: Opponent's a3 drops about 2 pawns.
- **LLM**: a3 is a blunder in the opening — claim the center first instead.
- facts: rule={'category': 'blunder', 'ref_field': 'cp_loss', 'priority_level': 11}

**12. d5** (user · good · cp_loss=0)
- existing: _(no caption)_
- **LLM**: You're claiming the center with d5. Good move!
- facts: best=d5

**13. Bxd5** (opp · opp_blunder · cp_loss=9920)
- existing: Bxd5. Opp's position is lost.
- **LLM**: Bxd5 hangs the bishop and opens up for a strong attack — watch for threats to your pieces.
- facts: rule={'category': 'mate', 'ref_field': 'mate_threat_evidence', 'priority_level': 1}

**13. Bg4+** (user · good · cp_loss=0)
- existing: Bg4+. Wins by force.
- **LLM**: Bg4+ pins the knight to the king, but castle soon for safety.
- facts: best=Bg4+ | rule={'category': 'mate', 'ref_field': 'mate_threat_evidence', 'priority_level': 1} | principles=TAC_PIN_PATTERN,OP_NOT_CASTLED

**14. Ke3** (opp · context · cp_loss=0)
- existing: Ke3. Opp's position is lost.
- **LLM**: [ERROR: Error code: 429 - {'error': {'message': 'Rate limit reached for gpt-4o-mini in project proj_JPS3HXJkytdZwGTknrGfIQcx organization org-lZsETHYfpKzyBmbr8e4GbSFc on tokens per min (TPM): Limit 50000, Used 47949, Requested 3006. Please try again in 1.146s. Visit https://platform.openai.com/account/rate-limits to learn more.', 'type': 'tokens', 'param': None, 'code': 'rate_limit_exceeded'}}]
- facts: rule={'category': 'mate', 'ref_field': 'mate_threat_evidence', 'priority_level': 1}

**14. Bxd1** (user · good · cp_loss=0)
- existing: Bxd1. Wins by force.
- **LLM**: Bxd1 is a strong move, maintaining pressure and threatening mate.
- facts: best=Bxd1 | rule={'category': 'mate', 'ref_field': 'mate_threat_evidence', 'priority_level': 1}

**15. axb4** (opp · context · cp_loss=30)
- existing: axb4. Opp's position is lost.
- **LLM**: _(empty — nothing to teach)_
- facts: rule={'category': 'mate', 'ref_field': 'mate_threat_evidence', 'priority_level': 1}

**15. Ng4+** (user · blunder · cp_loss=9424)
- existing: Ng4+ allows mate in 4.
- **LLM**: [ERROR: Error code: 429 - {'error': {'message': 'Rate limit reached for gpt-4o-mini in project proj_JPS3HXJkytdZwGTknrGfIQcx organization org-lZsETHYfpKzyBmbr8e4GbSFc on requests per min (RPM): Limit 15, Used 15, Requested 1. Please try again in 4s. Visit https://platform.openai.com/account/rate-limits to learn more.', 'type': 'requests', 'param': None, 'code': 'rate_limit_exceeded'}}]
- facts: best=Qf3+ | rule={'category': 'mate', 'ref_field': 'mate_threat_evidence', 'priority_level': 1} | principles=TAC_CHANGED_AFTER_MOVE

**16. Kd2** (opp · context · cp_loss=-7)
- existing: _(no caption)_
- **LLM**: [ERROR: Error code: 429 - {'error': {'message': 'Rate limit reached for gpt-4o-mini in project proj_JPS3HXJkytdZwGTknrGfIQcx organization org-lZsETHYfpKzyBmbr8e4GbSFc on requests per min (RPM): Limit 15, Used 15, Requested 1. Please try again in 4s. Visit https://platform.openai.com/account/rate-limits to learn more.', 'type': 'requests', 'param': None, 'code': 'rate_limit_exceeded'}}]
- facts: principles=MID_BAD_BISHOP

**16. Qf3** (user · mistake · cp_loss=129)
- existing: Qf3 loses about 1 pawn. Nxf2 was better. Opponent's strongest reply: Nc3.
- **LLM**: [ERROR: Error code: 429 - {'error': {'message': 'Rate limit reached for gpt-4o-mini in project proj_JPS3HXJkytdZwGTknrGfIQcx organization org-lZsETHYfpKzyBmbr8e4GbSFc on requests per min (RPM): Limit 15, Used 15, Requested 1. Please try again in 4s. Visit https://platform.openai.com/account/rate-limits to learn more.', 'type': 'requests', 'param': None, 'code': 'rate_limit_exceeded'}}]
- facts: best=Nxf2 | rule={'category': 'blunder', 'ref_field': 'cp_loss', 'priority_level': 11} | shape=Pin | principles=TAC_CHECKS_CAPTURES_THREATS,TAC_CHANGED_AFTER_MOVE

**17. Bxb7** (opp · opp_blunder · cp_loss=9570)
- existing: Bxb7. Opp's position is lost.
- **LLM**: Bxb7 is a blunder — it misses a mate threat.
- facts: rule={'category': 'mate', 'ref_field': 'mate_threat_evidence', 'priority_level': 1}

**17. Qe2+** (user · good · cp_loss=0)
- existing: Qe2+. Wins by force.
- **LLM**: [ERROR: Error code: 429 - {'error': {'message': 'Rate limit reached for gpt-4o-mini in project proj_JPS3HXJkytdZwGTknrGfIQcx organization org-lZsETHYfpKzyBmbr8e4GbSFc on requests per min (RPM): Limit 15, Used 15, Requested 1. Please try again in 4s. Visit https://platform.openai.com/account/rate-limits to learn more.', 'type': 'requests', 'param': None, 'code': 'rate_limit_exceeded'}}]
- facts: best=Qe2+ | rule={'category': 'mate', 'ref_field': 'mate_threat_evidence', 'priority_level': 1}

---
**Total moves:** 34  ·  **Empty (skipped):** 3 (8%)  ·  **Errors:** 5