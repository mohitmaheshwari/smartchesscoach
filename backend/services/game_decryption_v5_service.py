"""
Game Decryption V5 Service - "Thinking Simulator"
==================================================

Vision: Teach HOW to think, not just WHAT to play.

Key Principles:
1. EVERY move gets coaching (user + opponent)
2. Plans > Moves (transferable knowledge)
3. LLM = Language translator ONLY (all logic from existing layers)
4. Smart theory (track what user has understood)
5. Simple language (1200-friendly)

Architecture:
┌─────────────────────────────────────────────────────────────────┐
│  1. STOCKFISH LAYER - Get eval, best move, PV (the future)     │
├─────────────────────────────────────────────────────────────────┤
│  2. LOGIC LAYER - Existing services                            │
│     - chess_theory_service → opening/endgame/tactical match    │
│     - line_parser → PV analysis, pattern detection             │
│     - thinking_coach → principle-based feedback                │
│     - coaching_answer → thinking pattern detection             │
├─────────────────────────────────────────────────────────────────┤
│  3. PLAN EXTRACTION - Turn PV into a PLAN (not just moves)     │
├─────────────────────────────────────────────────────────────────┤
│  4. MEMORY CHECK - Has user seen this concept? Acknowledged?   │
├─────────────────────────────────────────────────────────────────┤
│  5. LANGUAGE LAYER - LLM for key moments, templates for rest   │
└─────────────────────────────────────────────────────────────────┘
"""

import chess
import chess.pgn
import chess.engine
import json
import os
import io
import re
import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# V5 coaching version — increment when coaching logic changes to trigger re-generation
V5_COACHING_VERSION = 102  # v102 (2026-06-03): second authoring apply on prod — 75 new override rows applied after FEN backfill lifted 4 records out of NO_FEN limbo. Bumping the version forces existing decryption_v5_data to regen so the new overrides reach stored captions. v101 (2026-06-03): authored caption overrides — V5 service now checks authored_caption_overrides collection (keyed by game_id+move_number+move_san) at the end of per-move caption rendering. When a hit exists, Parth's authored prose replaces the templated caption text on both caption and caption_llm. Populated by backend/scripts/authoring_apply_safe_subset.py after a strict-gate audit (73 of 158 submissions passed; see backend/scripts/_snapshots/authoring_safe_subset.json). Engine-truth fields (severity, cp_loss, fen, shape_pattern) stay computed from the pipeline — only user-facing text changes. Bumping the version forces regen across existing analyzed games so the override layer reaches stored decryption_v5_data on next read. v100 (2026-06-02): two-clause "why played wrong" — R12_blunder.json failure_mode_clauses_user + teaching_principles + new wrapper variants (user_with_failure_and_alternative, user_with_failure_and_principle). Failure-mode facts (opp_reply_attacks_played_piece, opp_reply_creates_fork, pieces_now_undefended_present, etc.) now drive a "{played} {failure_clause}. {best} was better — {alt}" or "{played} {failure_clause}. {teaching_principle}." caption shape, replacing the old "X is a mistake. Y was better" framing on positions where a concrete failure mode fires. See docs/why_played_wrong_spec.md and commits 03b84eb8 (phase 1) + aca067e4 (phase 2: opp_reply_creates_fork). Bumping the version forces regen across analyzed games so existing decryption_v5_data gets the new failure-mode captions on next read. Triggered by Mohit's 2026-06-01 feedback batch (fb_3efc/fb_3d53/fb_1cd7/fb_79c3) where the old captions said "h4 was better — attacks Bg3" when the actual problem was "Bb2 walks into Nb7". Coach Review (services/game_coach_review.py) reads the regenerated captions from decryption_v5_data and renders them in the Insights tab principle cards. v99 (2026-05-25): wire severity_practical into R12/R v99 (2026-05-25): wire severity_practical into R12/R_PROMOTED severity_tiers — caption tone actually softens now. v96-v98 computed practical_tier and stamped it on the move record, but the caption render layer still used cp_loss-based severity_tiers — so the tone never changed (Rb3 still read "is a mistake" while internally classified as practical=inaccuracy). v99 injects severity_practical + state fields into caption_facts AT extract time (game_decryption_v5_service.py just after _extract_caption_facts call). R12_blunder.json + R_PROMOTED_basic_mistake.json severity_tiers now prefer severity_practical-based tier matching, fall through to cp_loss-based when practical is absent (defensive). Verified on Parth's Rb3 case: caption changed from "Opponent's Rb3 is a mistake" → "Opponent's Rb3 is an inaccuracy" (stayed_winning=True, practical=inaccuracy). Counter-case: m24 Qb8 in losing position softened from "is a mistake" to "is an inaccuracy" (small drift in lost position — no point harshly framing). The pedagogical voice now honours decisiveness state — Mohit's Q1 intent realised end-to-end. v98 (2026-05-25): hotfix — practical-severity wiring used wrong eval source for opp moves. eval_data is keyed on the USER's prior FEN, so its eval_before/eval_after track the user's prior move (not opp's pre/post eval). The V5 service tracks opp evals separately in opp_eval_before / opp_eval_after (lines ~2965-2973). v96 mistakenly used eval_data.* for opp moves → mover_state always read 'balanced' for opp regardless of actual eval. Verified post-fix on Parth's m24 Rb3 (cp=102 in white-winning +437 position): mover_state correctly winning→winning, stayed_winning=True, severity_practical=inaccuracy (softer than canonical=mistake — Mohit's Q1 intent). The displayed `severity` field still reads opp_mistake — caption pipeline doesn't yet consume severity_practical for tone (that's the next step). v97 (2026-05-25): Tier B Q5 — intent-aware prophylactic wing-pawn detection. Mohit 2026-05-25: "the real issue is your detector lacks intent understanding. h6 in Italian is not merely 'wing pawn + no development' — it's preventing Bg5, reducing pin ideas, asking bishop intention. Better fix: detect prophylactic justification." Implemented _is_prophylactic_wing_pawn() in pattern_catalog: when opp's a/h-file pawn push controls a square reachable by user's same-colour bishop from its home square (h6 vs c1-Bg5, a6 vs f1-Bb5, h3 vs c8-Bg4, a3 vs f8-Bb4), the push is preempting future bishop development — that's prophylaxis, not lazy development. Skip flagging opp_played_wing_pawn_san in those cases. Conservative heuristic: requires user's bishop to be ON HOME SQUARE (not yet developed). If bishop has already moved, the preemption interpretation doesn't apply. Verified: Parth's m3 h6 in Italian (white Bc1 home) silenced; h3 m2 vs black Bc8 home silenced; a6 in position where Bc4 already developed does NOT silence (bishop already committed elsewhere). v96 (2026-05-25): Tier B Q1 — practical severity from win-probability delta. Mohit 2026-05-25: "in winning positions, absolute cp loss exaggerates human importance. +4.0 -> +3.3 is often practically irrelevant unless it throws away forcing continuation, allows counterplay, or drops evaluation trend repeatedly. don't purely threshold on cp_loss. combine eval_before, eval_after, win-prob delta, decisiveness change." New services/severity.py functions: win_prob_from_cp(eval_cp) — Stockfish-style logistic 1/(1+exp(-cp/400)); classify_severity_practical(cp_loss, mover_is_user, mover_is_white, eval_before_cp, eval_after_cp) — returns PracticalSeverity dict with practical_tier (from |Δwin_prob|), canonical_tier (from cp_loss), winprob trajectory, decisiveness state, stayed_winning + decisiveness_changed flags. The practical tier uses |Δwin_prob| with thresholds {inaccuracy 0.05, mistake 0.15, serious 0.30, blunder 0.50} + a decisiveness-change overlay: lost-winning bumps practical tier +2 (Mohit "+2.0 -> +0.2 is still serious mistake"); other worsenings bump +1; stayed-winning gets no bump (softer). Capped at canonical so we never make a move look WORSE than its cp_loss says. V5 service stamps 8 new fields on each move record: severity_practical, severity_canonical, mover_winprob_before/after/delta, mover_state_before/after, decisiveness_changed, stayed_winning. v95 (2026-05-25): Tier B Q2 — drop engine-meta fallbacks. NOTE on prior commit history: the commit at 7a8def0f was labelled "v94 — drop engine-meta fallbacks" but its contents are actually the Q3 "Strongest move here" sweep (the v93 work). Two background commit tasks tangled .commit_msg_piece.txt — v93/v94 message + file pairing got swapped. The actual Q2 engine-meta cleanup lands here (v95). v94 (mislabel) -> v95 (Q2): Removed from R12_blunder.json (1) why_user_missed_material ("it wins material in the resulting line" — vague engine-meta); (2) why_user_reply ("Opponent's strongest reply: X" — engine-speak); (3) opp_soft_reply variant ("engine has a slight preference here. Best reply: X" — engine-meta apology). Reworded why_opp_punish_default from "Your strongest reply is X" → "Play X" (drops absolutist "strongest"). Side effects: ~30-40% more user-side mistake-tier moves render without a why-clause (silence beats fake explanation). caption_classifier promotes R12 user_with_best (no why) to LOW for authoring attention. Mohit 2026-05-25: "silence is NOT always worse. Silence is better than fake explanation. V5's biggest strength is supposed to be: only speak when grounded. Don't betray that principle because you fear empty UI." v94 (2026-05-25, mislabel — actually Q3 sweep): drop "Strongest move here" overclaim. Mohit 2026-05-25: "stop pretending every move deserves a concrete caption. silence is NOT always worse. silence is better than fake explanation. V5's biggest strength is supposed to be: only speak when grounded. Don't betray that principle because you fear empty UI." Removed from R12_blunder.json: (1) why_user_missed_material ("it wins material in the resulting line" — vague engine-meta); (2) why_user_reply ("Opponent's strongest reply: X" — pure engine-speak, no actionable why); (3) opp_soft_reply variant ("engine has a slight preference here. Best reply: X" — engine-meta apology Parth fb_656da02ac646 called out: "preference for what?"). Reworded why_opp_punish_default from "Your strongest reply is X" → "Play X" (drops absolutist "strongest"). Side effects: ~30-40% more user-side mistake-tier moves render without a why-clause (the ones that USED to fall through to engine-speak now silence the why_clause and use user_with_best "X is a mistake. Y was better." format). The user_with_best variant promoted to LOW in caption_classifier — these are the moves we could add concrete detectors for. v93 (2026-05-25): Tier B Q3 — drop "Strongest move here" overclaim from 12 principle cue_best entries. Parth fb_3dbc887c6686 (d3 cp_loss=42 captioned "Take the centre with a pawn. Strongest move here." — d3 ISN'T strongest, cp_loss>0 says so). Mohit 2026-05-25: "exact-best only, or within MultiPV equivalence band. 'Strongest move' is absolute language. If engine says another move is better, even by 0.15, your wording becomes objectively false. Users forgive simplification. They do NOT forgive fake certainty." Audit: 12 cue_best strings used "Strongest move here" across OP_FINISH_DEVELOPMENT, OP_CLAIM_CENTER, TAC_CHECKS_CAPTURES_THREATS, TAC_FORK_PATTERN, TAC_PIN_PATTERN, TAC_SKEWER_PATTERN, MID_KEEP_ATTACKERS, MID_PAWN_BREAK, END_KING_ACTIVE, END_ROOK_BEHIND_PASSER, OP_BISHOP_TRADE_DOUBLES_PAWN, OP_F2_F7_STRIKE. 6 are missed_chance/counterfactual/state_entry (user did NOT play the strongest move — claim is misleading); 4 are played_move with cp_loss_strict ≥30 gate (user's actual move wasn't engine's #1 even if principle-aligned). All 12 swept: dropped the "Strongest move here" sentence/clause; kept the principle teaching. The praise-when-grounded surface is R15_good_move (fires on cp_loss==0 user-played-best cases). v92 (2026-05-25): Tier B Q4 — single canonical severity evaluator. Mohit 2026-05-25: "If move classification, caption gating, and severity rendering use different thresholds, your entire system becomes incoherent." Diagnosis: V5 service used user 30/100/250 (no "serious" tier) and opp 50/100/250 (different thresholds for the same eval drop); R12_blunder.json used 100/250/400 (4-tier with "serious"); R_PROMOTED_basic_mistake.json used 250/400 (3-tier, no inaccuracy/good). Three sources, three answers — drift that Parth's fb_30611d827109 surfaced (cp_loss=87 marked "good" while R12 would have called it "inaccuracy"). New services/severity.py is the single source: 5-tier scheme {good <30, inaccuracy 30-99, mistake 100-249, serious 250-399, blunder ≥400}. classify_severity() returns SeverityClassification(tier, user_facing_tier, cp_loss, walked_into_mate). user_facing_tier adds "opp_" prefix for non-user moves; "good" opp moves become "context" (matching legacy convention). The V5 service's inline severity logic (lines 2986-3016) replaced with one call to _classify_severity. R12_blunder.json + R_PROMOTED_basic_mistake.json severity_tiers verified to match the canonical thresholds (validate_json_severity_tiers helper used in tests). v91 (2026-05-25): batch Tier A bug-fixes from Parth's 24 caption reports. Six concrete bugs, each with a synthetic test before commit. (1) OP_QUEEN_OUT_EARLY: silence on queen retreats — mirror the v81 OP_FINISH_DEVELOPMENT fix; require from_square == queen home (d1/d8) for the principle to fire. Parth fb_729003d52c7f + fb_48b2eb24a93c: Qd5→Qd8 retreat captioned as "Bringing the queen out early" — backwards on a retreat. (2) OP_SAME_PIECE_TWICE detector + cue: previously fired on "any same-type-twice case" which caught Bd7 (c8-bishop's first move) as the second-bishop move while Bc5 had moved earlier — wrong, that's a DIFFERENT bishop. Tighten to require played from_square in prior_destinations set (the actual moved-piece-moves-again case). Cue rewritten to drop the unverified "this move solves a specific threat" claim (Parth fb_441026e27b10). (3) MID_BAD_BISHOP: previously fired on "≥5 same-colour pawns" alone; misfires on active bishops outside the pawn chain. Added mobility gate — require ≤3 legal squares for the bishop. Parth fb_164108af2618: white Bg3 (mobility 7+) tagged as bad bishop. (4) Scandinavian opening_intro typo: text said "draws White's queen out" but it's BLACK's queen that recaptures on d5. Rewritten honestly. Parth fb_9539edd1bfa1. (5) Board describer fallback gated to cp_loss>=30 — on clean user moves the describer was firing as the only surface with useless narration ("rook has 1 legal move"). Now silence beats narration on good moves. Parth fb_cb7f872a0781 + fb_6fc2d6be0d6e + fb_a720c6dc633d. (6) Open Long Line shape pattern: added king-proximity check (king within 1 square of diagonal) + reworded description to not overclaim "to their king" or "their corner bishop is gone." Parth fb_55e490a74436. v90 (2026-05-25): consolidate trap data into a single source (data/traps.json). Mohit asked "why we had 2 sources for traps, 2 json files?" — accidental duplication, not deliberate. data/coaching/opening_theory_tree.json had 22 traps embedded in opening entries (11 duplicates of traps.json + 11 ORPHANS sitting unused — never consumed by services/trap_recognition). v90 migration: backend/scripts/migrate_traps_consolidation.py converts each orphan from theory_tree's schema (trap_id, full_line, trap_for, victim_color, refutation) → traps.json schema (name, setup_moves, trap_line with per-step explanation, trap_color, success_message, result_type) and appends to traps.json under the kebab-case opening key. 11 new traps added: Milner-Barry Gambit, London Move Order, Caro-Kann Classical Pin, Fishing Pole Trap, Philidor Legal's Mate, Petrov Fork Trap, Stafford Gambit, Marshall Trap, Budapest Smothered Mate, Scandinavian Queen Danger, Halloween Gambit. All 15 traps[] arrays stripped from theory_tree (both duplicates + now-migrated orphans). Total traps in detection pipeline: 43 → 54. trap_color: 54/54 filled (was 43/43). Drift risk eliminated. v89 (2026-05-25): VICTIM-warning captions on trap setups. Mohit "similarly about the traps, with the teaching thing??" + chose "Surface trap WARNING on positions before the trap fires" — the parallel ask to the v88 theory_tree wiring, for trap data this time. Audit found 37 of 43 traps in data/traps.json had blank trap_color (the setter's color) — backfilled all 37 by reading description + success_message of each. Mappings annotated inline in backend/scripts/backfill_trap_colors.py. services/trap_recognition now surfaces trap_color in the dict returned by detect_trap_setup. V5 trap_record creation computes user_is_victim = (user_color != trap_color); carried through the setup_completed step AND the continuation steps (victim_falls / trap_player_punishes). R_PROMOTED_trap_setup.json adds 4 new variants (victim_warning + victim_warning_with_desc + victim_warning_no_punish + victim_warning_no_punish_with_desc) that fire when user_is_victim=True regardless of who completed the setup. Result: when a user (as black) plays Damiano (1.e4 e5 2.Nf3 f6), the caption now reads 'f6 — watch out, you've walked into Damiano Defense Punishment territory. Black plays 2...f6, inviting a knight sacrifice... The punisher will play Nxe5 next.' Audit on 4,978 games: 140 setup events, 7 user-as-victim-completes-setup (clear warnings), 85 opp-completes-setup of which many are also user-victim cases (depending on user_color vs trap_color). v88 (2026-05-25): WIRE opening_theory_tree teaching into V5 captions. Mohit's chain (m3 Nc3 Scandinavian narration → "caption isn't teaching" → "opening principles ARE teaching" → "ensure it's general"): we have rich data in data/coaching/opening_theory_tree.json (26 openings, 176 critical positions, key_decisions + best_moves + mistake_moves + common_learnings) that was never reaching the caption pipeline. v88 wires it. New service services/opening_theory_lookup.py: loads tree at import, applies pre-commit filter (move1_/move2_/move3_ transposition hints share FENs across openings — filtered out per the v87.5 audit, which surfaced petrov_defense.move2_bb4 stealing 1,245 hits across the corpus on positions that aren't yet Petrov). FEN-replay derives FENs for 48 variation positions that lack explicit fen_pattern (unlocks Scandinavian after_Nc3, Caro-Kann Classical after_Nxe4, etc.). 75 trustworthy positions after filter; corpus audit on 4,974 games gave 3,029 matches (2.2%) with clean opening attribution. V5 per-move loop stamps opening_theory_{name, variation, key_decision, match_quality, played_idea/why_good/why_bad/consequence/learning, top_move_san, top_move_idea} on every opening-phase move whose post-move FEN hits a tree position. R_PROMOTED_opening_intro.json gains 5 new variants (theory_played_best / theory_played_mistake / theory_critical_variation / theory_critical / theory_key_decision) consuming these facts. promotion_ladder.json adds an opening_theory_name gate BEFORE the legacy opening_intro_idea gate so theory matches override R-rule captions (e.g. R10_threat 'Nc3 threatens the queen on d5' becomes 'Nc3 — Scandinavian Defense, Main Line (Qxd5). The queen must move — Qa5 is the main line: safe and active'). caption_classifier already tiers R_PROMOTED_opening_intro HIGH (v87), so has_teaching_content=True for every theory match. v87 (2026-05-25): reclassify R_PROMOTED_opening_intro as HIGH (was MID-by-default). Mohit on m3 Nc3 ("Nc3. Develops naturally, prepares e4 or supports d5."): "for that move I would say the teaching moment was the opening principle here for this specific opening — this is one of the most played moves at the top level, so that gives them teaching about theory and things to remember." Right — opening curriculum knowledge IS teaching for a 1200, not narration. Even when the caption is brief like "Nc3. Develops naturally, prepares e4 or supports d5." (idea_only variant when opening_intro_name is absent), it surfaces opening theory the user should LEARN. Promoted in caption_classifier.py high_files. Side-effect: caption_tier now correctly reads HIGH and has_teaching_content reads True for every opening_intro fire. (Follow-up backlog: enrich services.opening_lookup.get_opening_introduction to name more openings — Scandinavian/Caro-Kann/Vienna main-line positions currently fall back to idea_only.) v86 (2026-05-25): surface caption_tier + has_teaching_content on every move record. Mohit on m3 Nc3 ("Nc3. Develops naturally, prepares e4 or supports d5."): "caption is showing what is on the board which is not great — can we add one more property if there is any teaching content here?" The existing services/caption_classifier.py already labels every rule variant HIGH/MID/LOW/NONE (HIGH = named tactical/strategic teaching, MID = concrete board observation, LOW = engine-speak fallback). v86 calls classify(caption, rule_name) once per move and stamps the result as caption_tier (string) + has_teaching_content (bool, True iff tier=='HIGH'). Consumers (admin/captions audit UI, lab review, future home-intelligence aggregations) can now filter for moves with real lesson content vs board narration. Verified on the m3 Nc3 case (MID — narration) vs m11 Nd4 (HIGH — lost-defender lead). v85 (2026-05-25): pin/skewer delta-check rejects slides along the SAME line. Mohit caught m8 Bb6 (bishop retreat c5→b6 along the b6-c5-d4-e3-f2-g1 diagonal) firing TAC_PIN_PATTERN with cue "Two enemy pieces on a line — pin or skewer the front one with a slider. Strongest move here." The bishop was already pinning f2 against the g1 king from c5; Bb6 just slid one square back along the SAME diagonal. The existing delta-check at line 4861 dedupes by (attacker_square, front_piece_square, rear_piece_square) — but attacker_square changes when the slider slides, so the same pin reads as "new." Fix adds two more filters: (a) dedup by (front_piece_square, rear_piece_square) target pair — if the same front/rear was pinned before by any of own pieces, this isn't new; (b) belt-and-braces, exclude shapes where the played piece's from_square is collinear with (attacker, rear) via chess.ray() — catches slides through previously-blocked lines too. Both R03_aligned_pieces (rule renderer) and TAC_PIN_PATTERN (principle) benefit. Verified Ruy Lopez Bg5→Nf6 against Qd8 still fires (genuinely new pin). v84 (2026-05-25): polish for v83 lead pairing — corpus audit on 10 pinned games surfaced two awkward combinations. (1) Redundancy: y4 cases like m20 Qb4→c4 produced "Qb4 is a mistake — you moved your queen away from defending c2. c4 was better — Your pawn on c2 is now undefended." Both halves named c2. Fix: suppress why_user_hanging when lost_defender_lead_clause is present — the lead carries that message. (2) Tonal mismatch: 2 cases where lead paired with why_user_position_already_losing produced "you removed a defender — but actually you were already losing since move N." The "already losing" framing is meant to SOFTEN blame; pairing with concrete action attribution undermines it. Fix: suppress why_user_position_already_losing(_since_known) when lead is present — the lead provides actionable WHY, more valuable for a 1200 than contextual framing. (3) Add user_with_best_with_lead_only variant: "{played} {phrase} — {lead}. {best} was better." for cases where the lead is present but no other why_clause fires (after the suppressions). Classifier maps as HIGH. v83 (2026-05-25): lost-defender lead clause paired with better-move why_clause. Mohit on m11 Nd4 (Nc6→d4 removes the defender of e5): "for a 1200 voice the problem with Nd4 was that it WAS defending the pawn and you removed it — caption should tell both things, why this move was a mistake AND what was better." Current R12 only said the better-move half. v83 enriches TAC_HANGING_PIECE.trigger=lost_defender evidence with lost_defender_piece + lost_defender_square (already computed in pieces_now_undefended, just surfaces them). caption_facts derives new top-level fact lost_defender_lead_clause = "you moved your {piece} away from defending {square}" when the principle fires on a user move. R12_blunder.json adds two new variants user_with_best_em_dash_with_lead + user_with_best_and_why_with_lead (paired form — only fires when BOTH lost-defender AND a better-move why_clause are present, to avoid orphan leads). Classifier maps both to HIGH. Result on m11 Nd4: "Nd4 is a mistake — you moved your knight away from defending e5. e4 was better — it attacks the knight on f3, forcing it to move. Pawn pushes that attack enemy pieces gain tempo — the opponent has to react." Both halves of the teaching, 1200 voice. v82 (2026-05-25): TAC_DISCOVERED_PATTERN gate — require the discovered target to be a non-pawn piece (≥knight). Mohit caught m7 e5 (central pawn push, cp_loss=10, best=e5) firing the principle because e7→e5 uncovered the f8 bishop's f8-a3 diagonal onto a3 (a white pawn). Geometrically a discovered attack, tactically meaningless — it's just classical opening pawn play, and the cue_best ("Move the front piece — your slider behind it attacks. Play this immediately.") talks like a real tactic was found. Mirrors the TAC_FORK_PATTERN gate that already excludes pawn-only forks. After v82: discovered-attack principle silences when every candidate target is a pawn, picks the first non-pawn target when mixed. v81 (2026-05-25): OP_FINISH_DEVELOPMENT detector — require queen to be LEAVING her starting square for queen_sortie to count as the attack signal. Mohit caught m5 Qd8 (queen retreat from d5 back to d8 after being chased) firing OP_FINISH_DEVELOPMENT with the off-topic cue "this position rewards attacking, but most positions don't" — a retreat is the OPPOSITE of an attack. The queen_sortie broadening (v36 era) was meant to catch Qh5/Qf3-style forward aggression with undeveloped minors. Without this guard, ANY queen move in the opening triggered FD on cp_loss>=30 with the catch-all principle winning priority 26 < 30 (OP_QUEEN_OUT_EARLY) and 31 (OP_SAME_PIECE_TWICE) — so the most-generic principle won over the most-specific. After v81: FD's queen_sortie trigger requires from_square == own queen home square (d1/d8). For Qd5→Qd8 (retreat to home), FD silences and OP_QUEEN_OUT_EARLY's "Queen to d8 early — develop minor pieces first; queens get chased" wins the resolver — concrete and on-topic. v80 (2026-05-25): teaching for opp positional mistakes. Mohit: "Opponent's a3 is a mistake. Your strongest reply is e5. where is the teaching here?? until you tell, why it's a mistake." Right. v77 surfaced WHAT user should play in response, but not WHY the opp move was wrong. New services/pattern_catalog.detect_opp_positional_mistake() runs four self-contained heuristics on (pre_fen, opp_played_san, move_number): wing-pawn-push-in-opening (matches Mohit's a3 case), knight-on-rim, queen-out-early, piece-retreats-home. Doesn't need engine's preferred opp move (which we can't easily access — eval entries are user-side only). Adds opp_played_* facts + four new why_opp_* variants in R12_blunder.json. Now: "a3 is a wing-pawn push in the opening — doesn't develop a piece or fight for the center. Play e5." Real coaching. v79 (2026-05-24): "Play this line" extended to opp mistakes/blunders. Mohit: "it should render on both user mistakes/blunders, opponent mistakes/blunders." For opp moves, pv_after_best can't carry the line (opp positions have no engine entry — that field is empty). v79 builds an explicit coach_line_moves list = [opp_played_san, user_best_reply, opp_followup, user_continuation] for opp moves with opp_cp_loss>=100. Frontend (v78.4) prefers coach_line_moves over the pv_after_best slice and drops the !isUser gate. Result: button now appears on both sides; line animates the full coaching narrative (watch opp's move + watch how to punish). v78 (2026-05-23): board_state_describer as UNIVERSAL FALLBACK — Mohit: "why we didn't fire the chess descripter caption on those 30% when it was silent?" Right — the describer was gated to is_user+cp_loss>=50, so silent-but-otherwise-uncoachable moves never got its content. Now the describer runs unconditionally on every move (each bs_* metric self-gates via its own threshold so clean positions return 0 facts), and when the rest of the rendering produces no caption, board_state_clause becomes the primary caption ("Bd3. Your rook on f1 has only 1 legal move."). Expected: ~50% drop in silence on the 10-game audit. v77 (2026-05-23): OPP-MISTAKE DETECTORS — symmetric to user-mistake detectors. Mohit: "you laready have built detectors for user mistakes, so we can build detectors for opponent mistakes." New services/pattern_catalog.detect_opp_move_punishments() runs the same shape detectors (pawn_kicks_piece, attack_with_tempo, queen_fork_with_check, endgame_loose_pawn_grab, clearance_then_check, clearance_for_attack, missed_tactic) against (post-opp-position, user_best_reply) — the detectors are perspective-agnostic so the same code surfaces user's PUNISHMENT context. New opp_user_reply_* facts in caption_facts. New 10 why_opp_user_* variants in R12_blunder.json at higher priority than the bare "Your strongest reply is X" fallback. Now Parth's m4 Be6 produces "Play d5 — your pawn kicks their bishop on e6" instead of just "Your strongest reply is d5." Real coaching. v76 (2026-05-23): opp-move narration + audit visibility — Mohit + Parth. Three layers: (1) /admin/captions endpoint + caption_coverage_v5.py audit script no longer filter on is_user_move; samples now tagged with mover_side="user"|"opp" so reviewers see both sides. Closes the systemic blindspot that hid Parth's 6 opp-move flags from our review tooling. (2) caption_classifier marks (R12_blunder.json, "opp") bare-severity variant as LOW (was MID-by-default), so opp captions without a why-clause bubble up in the low-quality bucket. (3) V5 per-move loop now populates user_best_reply_san + user_best_reply_san_is_forcing + captured_piece_type + target_square in caption_facts for opp moves with opp_cp_loss >= 30. These are the facts R12_blunder.json's why_clauses_opp predicates require to fire — until now they were dead code because no upstream populated them, so every opp blunder rendered the bare "Opponent's X is a serious mistake." Now: "Opponent's Rg7 is a serious mistake. You can play Y winning the Z." Parth's m18 Rg7 / m16 Nf7 / m4 Be6 / m9 Be7 / m45 Rf8 / etc. should all surface concrete punishments now. v75 (2026-05-23): Parth feedback closure pass. Fixed (a) R01_mate.json cp-loss-as-material variants ("Opponent gives up about N pawns of advantage" → "Opponent's position is lost — mate is on the board for you"); pre-commit hook extended to catch "gives up"/"swings by" verbs + scans backend/data/captions/*.json files so this class can't regress. (b) shape_patterns.py terminology: Free Pawn → "Passed Pawn" with corrected description (no enemy pawn on adjacent files); Weak Squares description rewritten to the correct definition (squares no enemy pawn can defend); Double Attack Line → "Aligned Pieces" with description that doesn't overclaim "double power." (c) caption_principles.py: TAC_HANGING_PIECE cues less preachy ("Watch the loose piece" instead of "Always count attackers vs defenders before each move"); OP_LOOSE_KING_PAWNS cue_absent rewritten to concrete advice ("Pushing pawns near your king before castling weakens the squares around it. Castle, then think about pawn breaks."); OP_QUEEN_OUT_EARLY cue_absent now consistent with engine disagreement (was self-contradictory "Queen's fine here. But that's rare..."); OP_BISHOP_TRADE_DOUBLES_PAWN cues no longer overclaim "Long-term target." (d) R12_blunder.json why_user_attacks_played softened: "has no safe square" (overclaim on king moves) → "is under attack" (just states the fact). v74 (2026-05-23): opening narration on early moves — Mohit + Parth feedback. v69 wired trap_context into captions but scoped opening_name surfacing too narrowly (trap-only). On quiet developing moves like m1 e4, m2 d6 (Philidor), m2 Nf3 the opening was detected upstream but never reached the caption. Now: (a) get_opening_introduction extended with Philidor d6 + Be7/g6/Nbd2/Nbc3 follow-ups for broader coverage; (b) V5 per-move loop sets caption_facts.opening_intro_name + opening_intro_idea on the first 6 plies in opening phase whenever get_opening_introduction returns a match; (c) R13_opening_central_pawn picks up the intro for m1-m2 central pushes ('e4 — King\\'s Pawn Opening. White stakes a claim in the center.'); (d) new R_PROMOTED_opening_intro rule covers non-central early moves ('d6 — Philidor-style setup. Defends e5 with the d-pawn. Solid but passive...'); (e) promotion_ladder.json adds R_PROMOTED_opening_intro right after R_PROMOTED_opening so it only fires when ≥3 setup steps haven't matched yet. v73 (2026-05-23): P2 PHASE 2 — hit detection. New services/pattern_catalog.detect_position_patterns() runs only the position-based detectors (clearance_for_attack, clearance_then_check, queen_fork, attack_with_tempo, endgame_loose_pawn, knight_outpost, active_defense, discovered_vacating_check, pawn_kicks_piece, missed_tactic[mate/piece], king_pawn_lifted, trap_punishment) — pattern presence depends only on (fen, best_move), so when user plays best_move we know they "hit" the pattern. Contrastive detectors (un_developing, knight_on_rim, defensive_pawn_push, same_piece_better_square, stop_opp_pawn, blocked_own_pawn) are excluded from hit detection — they're definitionally about user diverging from best. V5 per-move loop now writes BOTH outcomes: miss event when (cp_loss>=100 + played != best), hit event when (move_san == best_move). Aggregator + per-game endpoint surface hit_count, miss_count, accuracy_pct (gated on N>=3 per [[respect-sample-sizes]]). GameAnalysis UI panel shows ✓N for hits + ×N for misses with per-move chips colored by outcome. v72 (2026-05-23): P2 detector memory MVP. New backend/data/pattern_catalog.json (21 patterns, plain-English names + family + description for each detector). New services/pattern_catalog.py exposes resolve_pattern_ids(caption_facts) → list of pattern_ids that fired. New services/pattern_event_logger.py manages the user_pattern_events Mongo collection (idempotent per-game writes, indexes on user_id+pattern_id, user_id+game_id, user_id+created_at). V5 generation now collects pattern-miss events through the per-move loop (gated on is_user + best != played + cp_loss>=100, matching the existing detector gate) and flushes in bulk at end-of-game. New optional kwarg game_id on generate_game_decryption_v5 enables idempotent delete-then-insert across regens. LIMITATION (v1): only "miss" outcomes are recorded — "hit" detection requires running detectors on user GOOD moves too, future refactor. v71 (2026-05-23): missed_tactic_mate fix — Mohit caught that the template "mate in {missed_tactic_ply} moves." was rendering ply count where chess natural-language expects moves (so PV ply=3 read as "mate in 3 moves" when it's really mate-in-2: w1 b1 w2#). Plus grammar bug "mate in 1 moves". Fix: caption_rules.py adds missed_tactic_moves_to_mate = (ply+1)//2 + missed_tactic_mate_word ("move" if 1 else "moves") to caption_facts; R12_blunder.json template now "mate in {missed_tactic_moves_to_mate} {missed_tactic_mate_word}." Also: P5 board_state_game_summary service — aggregates per-move bs_* metrics across all user positions into game-level trends ("opponent had pieces aimed at your king across 8 moves"), surfaced via new endpoint GET /games/{id}/board-summary and a "Board patterns across the game" panel in GameAnalysis Review (renders only when ≥1 trend fires ≥3 times). MIN_OCCURRENCES=3 threshold keeps the panel silent on clean games. v70 (2026-05-23): "Play this line" data surfacing. Each user-move dict in decryption_v5_data now carries (a) trap_line_full — list of {move, explanation} step records from data/traps.json when a known trap fires (richer than pv_after_best because the per-step text is hand-authored); (b) coach_line_length_hint — int hinting how many plies of pv_after_best to play back when no trap_line is present (defaults to 3 for user mistakes with best_move != played; equals len(trap_line) when trap fires). Consumed by the GameAnalysis Review UI's "Play this line" button (auto-step at 2s/move, resets to game position on Next-button navigation). Also: grammar fixes in board_state_describer (bs_development_gap, bs_central_control_gap) for the singular-N-with-plural-noun bug class first caught on bs_worst_placed_piece. v69 (2026-05-22): trap-context wiring. New caption_facts keys trap_context_name (display-cleaned, " Punishment"/" Trap" suffix stripped), trap_context_full_name (raw), trap_context_first_punishment_san, trap_context_description, opening_name. Set by V5 service per-move when (a) services.trap_scanner finds a trap whose setup the user reached, (b) the user is the trap's setter (i.e. punisher), (c) the trap is not yet sprung (sprung_moves < len(trap_line)), and (d) the engine's best_move equals trap_line[0]. R12_blunder.json gains highest-priority why-clause why_user_missed_trap_punishment + variant "it's the textbook refutation in the {trap_context_name}." For Damiano fc97ee1d m7 Bb5, the caption now reads: "Bb5 is a mistake. Nxe5 was better — it's the textbook refutation in the Damiano Defense." Opening_name reserved (per [[opening-name-only-at-critical-lessons]]) for the trap-fire moment only — naming the opening on every routine move would be noise. Mohit 2026-05-22: "trap and openings ship next whatever applies". v68 (2026-05-22): MAJOR BUG FIX — _r12_render in caption_rules.py was building an explicit subset of facts to pass to render_rule for R12_blunder.json, which meant that every new caption_fact key added to the V5 service in v56-v66 was being DROPPED at R12 render time. The detectors fired correctly (e.g. clearance_then_check populated missed_clearance_then_check_follow_up_san='Qh5+') but R12's _r12_render built a fresh dict that excluded those keys, so the predicates in why_clauses_user couldn't match and the caption fell through to engine-speak why_user_missed_material. Mohit caught it on game fc97ee1d m7 Bb5 — should have produced 'Nxe5 was better — it opens the line, and your queen can then play Qh5+ to chase the king on e8' but actually produced 'Nxe5 was better. it wins material in the resulting line.' Fix: in _r12_render, start with `facts = dict(f)` (full caption_facts) and then .update() with R12-computed extras. Now ALL detector outputs from v56-v66 flow through to the JSON predicates: clearance_then_check, queen_fork, attack_with_tempo, endgame_loose_pawn, un_developing, defensive_pawn, knight_outpost, stop_opp_pawn, active_defense, same_piece_better_square, discovered_vacating_check, knight_on_rim, pawn_kicks_piece, why_clause_em_dash. Expect massive caption improvement across the corpus on next regen. v67 (2026-05-22): LLM polish layer. New service services/v5_llm_polish.py uses GPT-4.1-mini (configurable via V5_POLISH_MODEL env) as a COPYWRITER, not a chess engine. It receives the structured caption_facts + the deterministic base caption and rewrites the prose in coach voice. Strict prompt forbids inventing chess moves/squares/pieces. A regex-based verifier rejects any LLM output containing chess tokens not in the input whitelist; rejection falls back silently to base caption. Polish runs only for user mistake-tier captions (is_user AND cp_loss >= 100) to keep latency bounded. Storage: new field caption_llm on each move dict (None when polish was not attempted or rejected). Caller prefers caption_llm when non-empty, falls back to caption. Set V5_POLISH_ENABLED=false to disable. v66 (2026-05-22): voice match to Mohit's approved captions. Added new parent variant user_with_best_em_dash ("{played_san} {phrase}. {best_move_san} was better — {why_clause}") in R12_blunder.json + select_variant rule that picks it when fact why_clause_em_dash=true. V5 service sets that fact whenever any best-move-focused detector fires (mate, piece_capture, attack_with_tempo, clearance_then_check, queen_fork, endgame_loose_pawn, active_defense, same_piece_better_square, discovered_vacating, un_developing, defensive_pawn, knight_outpost, stop_opp_pawn, knight_on_rim, pawn_kicks_piece, king_pawn_lifted). Why-clauses rewritten to start with "it" instead of "{best_move_san}" — em-dash continuation now reads naturally. Consequence-focused why-clauses (why_user_attacks_played, why_user_capture, etc.) untouched — they still use the original 2-sentence parent. v65 (2026-05-22): two final detectors for Mohit's approval set. simulate_knight_on_rim_in_opening (#9 Na6/e5 — user knight to a/h-file in opening when engine wanted something else; bypasses the silent OP_KNIGHT_ON_RIM principle to inject a real why-clause in R12_blunder). simulate_pawn_kicks_piece (#10 Qd7/c4 — engine's best is a pawn push that attacks an opp non-pawn piece; simpler than the full 'undermine-the-defender' framing but matches the kick-the-piece teaching). Brings 15 of Mohit's 15 approvals to detector-shipped status. v64 (2026-05-22): three more detectors per memory rule feedback_build_detectors_on_first_approval — second batch. simulate_active_defense (#12 a5/Qe7 — defends threatened own piece AND counter-attacks undefended opp), simulate_same_piece_better_square (#8 Qe4/Qf5 — same piece type, engine's destination attacks more undefended targets), simulate_discovered_attack_vacating_check (#6 Qa5/Nxd3+ — moved piece gives check AND vacating-square opens own slider's line to undefended opp piece). Brings the total of detector-shipped approvals to 13 of 15. Remaining deferred: #9 (knight-on-rim, overlaps OP_KNIGHT_ON_RIM) + #10 (undermine-the-defender, geometric spec unclear from one example). v63 (2026-05-22): batch detectors for Mohit's approved patterns (per new memory rule feedback_build_detectors_on_first_approval — N=1 approval is sufficient to build). Four new detectors: simulate_un_developing (#4 — piece retreats to home square in opening), simulate_defensive_pawn_push (#7 — passive wing pawn move when developing was right), simulate_knight_outpost (#11 — knight to defended central outpost), simulate_stop_opponent_pawn_advance (#14 — block opp's pawn advance). New caption_facts keys + R12 variants + classifier mappings. v62 (2026-05-22): endgame-loose-pawn-grab detector. Active piece (king, rook, etc.) in endgame captures or attacks an undefended opp pawn. Closes approvals #13 (Kxh3), #15 (Rf3 attacks h3), #031 (same Rf3 grab one move later). Two sub-templates: direct_capture ("Kxh3 grabs the undefended h3 pawn") and attack ("Rf3 attacks the undefended h3 pawn — your rook can grab it next"). Universal principle ending: "In the endgame, hunt undefended pawns with your active pieces." Endgame heuristic: total non-pawn pieces ≤ 8. v61 (2026-05-22): queen-fork-with-check detector. Fires when engine's best move is a queen move that delivers check AND wins material (either as capture-with-check or as fork on king + undefended piece). Closes Mohit-approved approvals #5 (Qb3+ forks king + b7), #16 (Qh4+ forks king + g4), #19 (Qxb4+ captures b4 with check). Two sub-templates wired into R12_blunder.json: why_user_missed_queen_capture_with_check + why_user_missed_queen_fork. caption_facts gains queen_fork_{sub_kind, secondary_piece, secondary_square, king_square}. v60 (2026-05-22): piece_capture eval-guard lowered 400 → 250cp in best_move_tactic_detector.py. Catches the residual_low cases where engine sees a clean piece-win in PV but eval is dampened by black's compensation. Cases fixed: row #003 (Bxa6 eval +379, rejected at 400), row #009 (Nxe5 eval +295), row #014 (Nxe5 eval +57 with clear PV win), row #025 (Nxe5 eval +140), row #038 (Bxh6 eval +186). Threshold history: 500cp (v36 and earlier) → 400cp (v44) → 250cp (v60). 250cp is the floor at which the PV-claim is reliably backed by eval; lower would risk over-claiming when engine's PV captures are illusory. v59 (2026-05-22): REVERT v58. The PV-vs-stored-best reconciliation introduced in v58 made the wrong assumption ("PV is always more reliable than stored best_move"). Empirically untrue: row #032 (Qd7/c4) has stored best=c4 correct and PV[0]=Bxc3 stale (Mohit verified); row #003 (Bc4/Bxa6) has stored best=Bxa6 stale and PV[0]=Nxe5 correct. Without re-running engine inline we can't tell which is reliable. Revert keeps the stored best as-is for both cases. The right long-term fix is engine-based disambiguation when stored ≠ PV[0], but that's heavier work. For now: status quo + log the unresolved problem. v58 (2026-05-22, reverted by v59): reconcile best_move with pv_after_best[0] when they disagree. Mohit 2026-05-22 caught it on residual_low row #003 (FEN r1bqkbnr/pp1p3p/n1p2p2/1B1Pp1p1/4P3/2P2N1P/PP3PP1/RNBQK2R w KQkq - 0 8): stored best_move was "Bxa6" but the depth-15 multipv PV starts with "Nxe5" — caption said "wins the knight on a6" but the actual engine plan is "wins the e5 pawn for free, knight reroutes, THEN Bxa6 as cleanup." Same bug class as row #034 (b6/Na5) where v57's attack_with_tempo detector didn't fire because pv_after_best[0] != best_move_san. Fix: in the V5 service, after loading both fields from eval_data, if they disagree, prefer pv_after_best[0] as the effective best_move — the PV is what the engine actually plans to play. Single-line reconciliation upstream of all caption_facts/detector consumers, so attack_with_tempo / clearance_then_check / piece_capture detectors all benefit. Cascading effect: captions will now describe the move the engine actually wants to play, not a stale earlier-depth choice. v57 (2026-05-22): attack_with_tempo detector — fires when engine's best move attacks an opp non-king piece AND pv_after_best[1] is opp retreating that piece. Captures the "with tempo" tactical pattern from Mohit's approved-caption review (#1 Qe2/d4, #2 e4/Nh4 — both in attack-with-tempo family). New caption_facts keys (attack_with_tempo_{piece, square, follow_up_san}) populated by simulate_attack_with_tempo(best_move, pv_after_best). New R12_blunder variant why_user_missed_attack_with_tempo with template '{best_move_san} hits the {piece} on {square} with tempo. Your follow-up: {follow_up_san}.' Excludes checks on king (different pattern — queen-fork family, future detector). Categorizer found 17 matching positions in residual_low corpus; expected to upgrade ~17 LOW captions to HIGH on next regen. v56 (2026-05-22): clearance_then_check — restore the 2-move sacrifice-then-check Légal's-Mate-family detection that v53 removed. v53 deleted the 2-move "simulate slider to newly-reachable square" logic to silence a caption hallucination ("your queen comes through to attack f7" implied a 1-move plan while the underlying detection was 2-move). The right fix was always to keep the detection and write an honest multi-move caption template; v53's choice was lazy and regressed the Légal's family corpus. v56 adds a NEW detector detect_clearance_then_check (parallel to detect_clearance_for_attack) that fires when the slider can move to a newly-reachable square FROM WHICH it gives direct check, plus a NEW R12_blunder variant why_user_missed_clearance_then_check with explicit-multi-move phrasing ("{best_move_san} opens the line — your {piece} can play {follow_up_san} to chase the king"). caption_facts gains 4 new keys (missed_clearance_then_check_{piece, destination, follow_up_san, king_square}) computed via simulate_clearance_then_check(best_move) on the pre-move board. The 1-move clearance_for_attack detector untouched. Mohit 2026-05-22 caught the regression on r1bqkbnr/pppp3p/n4p2/3Pp1p1/4P3/2P2N1P/PP3PP1/RNBQKB1R w KQkq - 0 7 m7 Bb5 where engine best Nxg5 + Qh5+ was the Légal's pattern but caption fell to engine-speak why_user_missed_material. See memory/feedback_fix_framing_not_detection. v55 (2026-05-21): user_is_winning / user_is_losing flags now require BOTH eval_before AND eval_after to support the framing. Closes m20_Qe6 backlog case where eval went from -104cp (balanced) to -395cp (losing) — the PLAYED MOVE caused the loss but the v50 logic (eval_after only) labeled it 'you were already losing' which was wrong. After v55: user_is_winning fires only when user was already winning before AND remains winning after; user_is_losing fires only when already losing AND remains losing. Captions like 'X is fine — you're still winning' or 'X doesn't change much — you were already losing' now correctly reflect persistent state, not just current state. v54 (2026-05-21): curriculum walker filters openings by color before iterating. Previously V5 walked EVERY opening (regardless of authored color) and accepted the first one returning is_in_book=True. For black users, white-curric trees could match first and produce mis-attributed wrong_feedback (the walker's user_plays_curriculum_color check tries to handle both branches but the responses-vs-next mapping in our trees is authored for the matching color). Fix: pre-filter _candidate_openings by color == user_color before iterating. v53 (2026-05-21): clearance_for_attack detector — drop the speculative 'simulate-slider-moving-to-cleared-square' step. The previous logic checked "if the slider moved to this newly-opened square, would it attack king zone from there?" — implying a 2-move plan, while the caption template ("your {piece} comes through to attack {sq}") implies a 1-move clearance with direct attack. Verifier (services/scripts/caption_verifier.py) found 10/50 sample captions were hallucinations (e.g., "Nd5 clears the line — your rook comes through to attack c7" when the rook would need to move to c5 first). v53 tightens the detector to fire ONLY when the slider's newly-attacked squares directly include a king-zone square — no further movement assumed. Trade-off: fewer firings (the speculative case was over-claiming), but every firing is now truthful. v52 (2026-05-21): Phase 3 curriculum — deepened 7 high-traffic opening trees with more wrong_feedback nodes + variation branches (italian_game w/ Hungarian/Two Knights/Fried Liver/Polerio/Modern depth, sicilian_defense w/ Najdorf English Attack + Bg5, caro_kann w/ Advance/Exchange/Classical Ng3, ruy_lopez w/ Closed main/Berlin Open, french_defense w/ McCutcheon/Tarrasch/Advance/Exchange, queens_gambit w/ Tartakower/Albin/Slav branches, kings_indian_defense w/ Samisch/Fianchetto). Plus 3 NEW entries from scratch: petrov_defense (color=black; sound defense to 1.e4 e5, includes the d6-before-Nxe4 trap teaching), italian_game_black (color=black; how to defend the Italian incl Polerio vs Fried Liver), nimzo_indian_defense (color=black; Rubinstein/Classical/Samisch lines, gives-bishop-for-structure teaching). 16 of 17 curated openings now populated. Smoke-tested 23/23 deviation walk paths return is_in_book=True with expected_move + wrong_feedback. v51 (2026-05-21): Pattern A fix — gate engine-speak why-clauses (why_user_reply, why_user_missed_material) on user_is_winning: false, user_is_losing: false. Previously these LOW fallbacks fired whenever opp_reply_san was present (i.e., on every R12 move with a Stockfish reply line), SETTING why_clause and BLOCKING the v50 user_winning_position / user_losing_position reframings. Per docs/caption_backlog 5 of 8 LOW captions in v50 audit (m17 Nb4, m20 Qe6, m28 Bd4, m29 g6, m7 Qe5) traced to this single root cause. After v51: engine-speak why-clauses only fire in balanced positions (user neither winning nor losing); winning/losing positions instead surface the user_winning_position / user_losing_position variants ('X is fine — you're still winning' / 'X doesn't change much — you were already losing'). Mohit-flagged via the docs/caption_backlog audit-position writeups. v50 (2026-05-21): position-aware framing — when user is decisively winning (user_is_winning=true, user_eval_after >= +200cp) or losing (user_is_losing=true, user_eval_after <= -200cp), low-to-mid cp_loss captions (< 250) reframe as encouragement/context instead of criticism. Mohit-flagged via Qh5+ on rnb1kbB1/ppp4p/3p3p/4p3/4P3/3P4/PPP2PPP/RN1QK2R w - 0 12 where white is up a queen (+868cp) and Qh5+ cp_loss=15 was captioned 'is a mistake' — overharsh framing when you're crushing. New variants in R12_blunder.json (user_winning_position / user_losing_position) and R_PROMOTED_basic_mistake.json (with_winning_position / with_losing_position) reframe as: 'Qh5+ is fine — you're still winning. Nc3 would have kept the pressure on.' For losing positions: 'X doesn't change much — you were already losing. Y would have made the loss slower.' Position-eval flags (user_is_winning / user_is_losing) were already computed in caption_facts; just threaded through caption_rules and promotion_facts. Classifier maps these as MID (contextual content, not a named tactic / curriculum but not bare engine-speak either). v49 (2026-05-21): Phase 2 curriculum authoring — extended 5 more opening trees (french_defense, queens_gambit, kings_indian_defense, slav_defense, english_opening). Each has main line walked 5-10 plies with 2-4 critical-decision wrong_feedback nodes in 'In the [Opening], the idea is X — why' voice. Now 12 of 17 curated openings have populated trees with deviation teaching. Smoke-tested 16/16 walk paths return is_in_book=True with expected_move and wrong_feedback. v48 (2026-05-21): authored opening_curriculum.json trees for the 7 highest-frequency openings in user games (italian_game 183 games, scotch_game 127, philidor_defense 72 [new entry], caro_kann 64, ruy_lopez, sicilian_defense, scandinavian_defense). Each tree has main line + 2-4 critical decision-point wrong_feedback nodes in "In the [Opening], the idea is X — why" voice (per Mohit editorial rule). White-curric trees follow existing convention (next=user move, responses=opp variations); black-curric trees use the same convention (caro_kann/sicilian/scandinavian: next=user black move, responses=opp white variations) — fixing a structural inconsistency present in some pre-existing black-curric entries. Smoke-tested 10/10 deviation cases walk correctly to expected move with wrong_feedback present. V5's curriculum walker (added in v47) now has real content to surface — opening-phase captions become curated teaching for these 7 high-traffic openings. v47 (2026-05-21): curriculum-walker wiring — V5 caption pipeline now consults opening_curriculum.json's tree (via existing get_opening_guidance) on every user move in the opening (move <= 20, cp_loss >= 30). When the tree expects move X but user played Y, V5 injects curriculum_deviation_clause = the tree's hand-authored wrong_feedback. R12_blunder.json and R_PROMOTED_basic_mistake.json gain new variants (why_user_curriculum_deviation / with_curriculum_deviation) at high priority — above the generic blocked_pawn / board_state detectors but BELOW concrete-about-played-move clauses (per Mohit: tactical 1-move blunders should not lose priority — user might hang a piece while also deviating from book). For Mohit's flagged Nc3 case on the Modern Defense, caption now reads the rich curriculum text: 'Nc3 is a mistake. In the Modern Defense, the idea is: c3 (the pawn) supports your d4 + e5 center. Nc3 blocks the c-pawn for good — now d4 has no pawn behind it. Black plays ...d6 then ...dxe5 and your big center falls apart.' v46 (2026-05-21): R_PROMOTED_basic_mistake — asymmetric cp_loss threshold. Detector-driven variants (with_blocked_pawn / with_board_state) still fire at the promotion-ladder gate (cp_loss >= 50), but the bare engine-speak default variant now requires cp_loss >= 100. Below 100cp with NO detector → silent. Closes the Bb3-style false-positive (cp_loss ~14-50 positional preference being captioned 'is a mistake. Bd3 was better.' — overharsh engine-speak with no teaching content). Mohit principle: silence beats engine-speak. Positional preferences shouldn't be framed as mistakes. v45 (2026-05-21): blocked-own-pawn principle detector — names an opening-fundamental violation. New services/principle_blocked_pawn.py fires when (a) engine's best move was a pawn move to square X, (b) user played a non-pawn piece to that same X, (c) it's the opening (move ≤ 15), (d) cp_loss ≥ 30. Detects the classic Nbc3-blocking-c-pawn pattern in d4+e5 structures (Mohit-flagged on r1bqk2r/1pppnpbp/p1n1p1p1/4P3/2BP4/5N2/PPP2PPP/RNBQ1RK1 w - - 0 7 where Nc3 cp=60 was correctly flagged a mistake but no why-clause fired). New why-clauses in R12_blunder.json (why_user_blocks_pawn_supports / why_user_blocks_pawn) and new variants in R_PROMOTED_basic_mistake.json (with_blocked_pawn_supports / with_blocked_pawn). Caption now reads "Nc3 is a mistake — it blocks your c-pawn. c3 would have supported your d4 pawn." instead of bare "Nc3 is a mistake. c3 was better." v44 (2026-05-21): missed_tactic_detector eval-guard threshold lowered 500cp → 400cp. Sacrifice tactics where the user gives up a minor piece to win a queen now correctly classify as piece_capture (was misclassified as 'material' engine-speak fallback). Mohit-flagged via Bb5+ on rnbqkb1r/pp3ppp/1n1p4/4p3/2B5/5N2/PPP2PPP/RNBQR1K1: best move Nxe5 leads to Nxe5 dxe5 Bxf7+ Kxf7 Qxd8 winning the queen, but engine eval was +431cp (not +500cp) because of the bishop+knight investment. Caption now reads 'Nxe5 wins the queen on d8.' instead of 'Nxe5 wins material in the resulting line.' v43 (2026-05-21): board-state worst_placed_piece tightened — skip pieces still on starting home squares. A rook on a1 with 0 legal moves is normal opening play (a-pawn hasn't moved yet), not a coaching moment. Without this filter, the metric falsely lectured "Your rook on a1 has only 0 legal moves" on positions where the real lesson was tactical. Mohit-flagged via Bb5+ blunder on rnbqkb1r/pp3ppp/1n1p4/4p3/2B5/5N2/PPP2PPP/RNBQR1K1 — describer now correctly produces 0 facts there, caption stays honest ("Bb5+ is a major blunder. Nxe5 was better.") rather than fabricating a misleading board-state reason. v42 (2026-05-21): board-state describer extended to R_PROMOTED_basic_mistake.json. cp_loss gate lowered from 100 to 50 (matches basic_mistake's promotion threshold; each board-state metric is self-gating, so cleaner positions don't accumulate noise). promotion_facts now carries board_state_clause from the V5 caption_facts dict. R_PROMOTED_basic_mistake.json gets a new with_board_state variant + select_variant predicate ({board_state_clause: present} → with_board_state, else default). Classifier maps (R_PROMOTED_basic_mistake.json, with_board_state) to HIGH tier. Closes the 100 LOW captions in R_PROMOTED_basic_mistake.json that v41 couldn't touch. v41 (2026-05-21): board-state describer — universal coach-voice fallback. New services/board_state_describer.py computes 11 FEN-only metrics (isolated_attacker, worst_placed_piece, development_gap, pieces_on_back_rank, king_shield_broken, king_attackers, central_control_gap, open_file_owned_by_opp, queen_alone_active, connected_rooks_only_opp, passive_pieces_count) from the post-move board, ranks by severity with category-diversity (max 2 per category), returns up to 3. V5 service joins the rendered bs_* templates into a single board_state_clause string. R12_blunder.json adds the new why_user_board_state predicate (priority above missed_material/reply, below all concrete-about-played-move clauses) plus 11 bs_* variants. Mohit-driven principle: when we can't explain the best move at human depth, never fall back to engine-speak ('Opponent's strongest reply: Nxe5'). Describe the board from user POV — pure geometry, both sides, coach voice. v40 (2026-05-21): eval-trajectory fact — engine-derived leverage instead of per-pattern detectors. New services/eval_trajectory.py reads move_evaluations and decides if the user was already losing for 3+ consecutive user moves before the current move. When true, V5 injects position_was_already_losing + losing_since_move into caption_facts. R12_blunder.json adds two new why-clause variants (priority above missed_material/reply, below the named tactical ones): why_user_position_already_losing ('You were already in trouble before this move. {best_move_san} only slows the loss.') and why_user_position_already_losing_since_known (names the specific move where the position started going wrong). Mohit-driven scaling principle: stop writing one detector per chess pattern; read what the engine already knows. v39: clearance_for_attack detector The Légal's Mate / Fried Liver family — detect when the engine's best move would have opened a line for an own slider (Q/R/B) to coordinate with another own piece on a king-zone square. Shape pattern #26 (clearance_for_attack) + simulate_clearance_for_attack helper that R12 calls with best_move to check 'would the best move have triggered this?'. New R12 why-clause why_user_missed_clearance_attack — priority above king_pawn_lifted and material. For Mohit's m5 Ng1: 'Ng1 is a serious mistake. Nxe5 was better. Nxe5 clears the line — your slider comes through to attack f7.' (Légal's Mate teaching, not engine-speak). Also ships backend/scripts/caption_coverage_v5.py — frequency-prioritized content backlog tool that classifies blunder captions into HIGH/MID/LOW/NONE specificity tiers, surfaces low-specificity positions as content-authoring candidates. Run inside container with --sample N. v38: king_pawn_lifted geometry detector Closes Mohit-flagged gap — a 1200 needs to UNDERSTAND why f7 is weak when black's f-pawn has moved, not read engine-speak about "winning material". New shape pattern (#25) detects when opp's king-shelter pawn is lifted off its starting square AND we have attackers piling on AND non-king defenders are fewer than attackers. Generalizes across uncastled (f7/d7 etc.), kingside-castled (f/g/h files), and queenside-castled (a/b/c files) positions. Detection runs as part of detect_all_shapes; the V5 service injects the resulting shape_pattern_id + target_square into caption_facts so R12_blunder's why-clause priority can use it. New why-clause variant why_user_missed_king_pawn_pressure: '{best_move_san} keeps the pressure on {shape_pattern_target_square}.' Priority above generic material but below mate/piece_capture. For Mohit's m5 Ng1: caption is now 'Ng1 is a serious mistake. Nxe5 was better. Nxe5 keeps the pressure on f7.' (teaches geometry, not engine-speak). v37: missed-tactic detector with eval guard R12_blunder now walks pv_after_best with python-chess (new services/best_move_tactic_detector.py module) to identify the tactical climax the user missed — mate-in-N, piece capture (knight or higher), or pawn captures. The result feeds three new highest-priority why-clauses in R12_blunder.json: why_user_missed_mate / why_user_missed_piece / why_user_missed_material. Closes Mohit-flagged bug fb_80a39c40321a (game 0a5af44c m5 Ng1) where the caption said 'Ng1 is a serious mistake. Nxe5 was better. Opponent plays exd4 winning your pawn.' — failing to mention that Nxe5's PV (Nf6 Nf7 Bg4 Nxd8) wins the queen on d8. After v37: 'Ng1 is a serious mistake. Nxe5 was better. Nxe5 wins the queen on d8.' v36: trigger thresholds + max_caption_words moved to JSON Every numeric cutoff that controls 'should this rule fire' (cp_loss < 30 for R05/R06/R11, cp_loss < 80 for R08, cp_loss >= 100 for R12/R14, cp_loss == 0 for R15, full_move_number <= 2 for R13, max_threat_see_cp >= 200 for R10, material_delta >= 100 for R08) now lives in each rule's trigger.when block in JSON. Cross-rule constants (max_caption_words=25, min_threat_see_cp, min_aligned_rear_value_cp, min_material_caption_gain_cp, max_cp_loss_for_tactic_celebration, default_visible_tactic_threshold) consolidated into caption_config.json; caption_config.py is now a thin proxy that re-exports from there for backwards compatibility. New helper should_fire(rule_name, facts) evaluates JSON trigger blocks. v35: decision/data split (variants + severity + why-clauses + promotion ladder) — every conditional that picks a caption variant, severity tier, why-clause priority, or promotion-ladder branch has been MOVED OUT of Python into JSON. Python now reads facts, calls render_rule(name, facts) for R-rules or dispatch_promotion(facts) for the promotion ladder; both walk JSON-encoded predicate lists and return text. Thresholds (400/250/100/50/20), priority orderings, and variant selection are all data, not code. Predicate vocabulary in caption_templates.py: equality, present/absent, gte/lte/gt/lt, in-list, dotted access for nested facts (trap_record.step_label etc.). New JSON blocks: select_variant, severity_tiers, why_clauses_user, why_clauses_opp, suppression, plus promotion_ladder.json for cross-rule priority. The if/elif chains in caption_rules.py (_r01_render, _r02_render, ..., _r12_render) and the V5 promotion ladder are gone — replaced by single render_rule / dispatch_promotion calls. v34: content/code split (strings only) All user-facing caption strings moved out of Python into backend/data/captions/*.json: R01_mate, R02_multi_target_attack, R03_aligned_pieces, R04_discovered_attack, R05_check_extra, R06_check_plain, R07_forced_recapture, R08_material, R09_king_safety, R10_threat (already done in v33), R12_blunder (severity tiers + 13 why-clause variants), R13_opening_central_pawn, R14_forced_best, R15_good_move + promotion ladder (trap_setup / trap_defense / opening / shape / principle / basic_mistake). LAW R3 ("no user-facing strings in Python") is now literally true across caption_rules.py and the V5 promotion ladder. Architecture docs moved to backend/data/captions/README.md so even prose lives outside .py files. Authoring is now JSON-only for Mohit + Parth. v33: start of content/code split (R10 only) — R10_threat text moved out of caption_rules.py f-string into backend/data/captions/R10_threat.json. Python now calls render_template("R10_threat", "default", facts); JSON owns the phrasing. First rule migrated; remaining R-rules + promotion ladder migrate one-by-one in follow-up commits. LAW R3 updated: no user-facing strings in Python. v32: trap-defense celebration — when user plays a move IN the trap_line and engine likes it (cp_loss ≤ 20), promote a caption recognizing the precise defense ("d5 — correct response in the Fried Liver Attack. Keep playing precisely; the line isn't over."). Trap library labels move 'victim_falls' regardless of whether the victim defends or falls in, so we cross-reference with engine eval to distinguish. Mohit Italian Game / Fried Liver test — m4 USER d5 (the correct Fried Liver defense) was silent because R10/R11 didn't fire on a quiet good move and the trap_record was ignored. Now opening_record + trap_record + trap-defense + shape/principle/basic_mistake all surface through the promotion ladder. v31: silence R11_development — "Develops the X to Y" / "Opponent develops the X to Y" was pure narration of board events the user can already see. Mohit pushed back: tell user what they don't know, not what's on the board. R11 trigger conditions already exclude tactical content (cp<30, no capture/check/threat), so when R11 would fire there is by definition nothing new to teach. Honest silence per [[no-hollow-coverage]]; the promotion ladder still surfaces opening/trap/principle/shape teaching when those detectors hit. v30: opening + trap promotion (OVERRIDE). Mohit Italian Game / Fried Liver test — m3 Bc4 captioned "Opponent develops the bishop to c4" while opening_record carried {name:"Italian Game", summary:"A classic opening. Develop quickly, point your bishop at f7..."}. m4 Ng5 captioned "Opponent develops the knight to g5" while trap_record carried {name:"Fried Liver Attack", description:"A deadly knight sacrifice on f7..."}. Both fired in the data, both ignored by the renderer, replaced by useless narration. Now trap setup_completed and opening_record (matched ≥3 setup steps) OVERRIDE the main caption (not just fill empty). v29: shape+principle+basic_mistake promotion (FILL when caption empty). v28: "drops/loses N pawns" → severity tier. v27: patient-academic voice pass. v26: 800-1400 vocab. v25: habit-principle bypass + R15. v24: R01 no-ply concretization. v23: Parth bug triage.

# Stockfish path
STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")

# ── V5 caption pipeline feature flag ────────────────────────────────────
# When True, every move record also carries new fields produced by the
# extractor→rules→renderer pipeline (caption, rule_name, caption_arrows,
# caption_highlight_squares, caption_facts_primary_reason). Legacy fields
# (narrative, plan, future_moves, highlight_squares) remain in place so
# reviewers can compare side-by-side. Disable by setting env to "0".
# Per docs/caption_pipeline_design.md.
CAPTION_V5_PIPELINE_ENABLED = os.environ.get("CAPTION_V5_PIPELINE_ENABLED", "1") not in ("0", "false", "False", "")

# v100 FINAL: V5 service now calls build_move_teaching_decision() —
# all 12 A-helpers + render + suppression + cue-pick + v78 fallback
# + promotion ladder + tier classification run inside the central
# layer. Only compute_severity_for_move stays imported separately
# because V5 applies its own book-move / best-equals / rating-band
# downgrades to `severity` BEFORE the central call (which then
# accepts the downgraded value via severity_override).
try:
    from services.caption_pipeline import (
        compute_severity_for_move as _compute_severity_for_move,
        build_move_teaching_decision as _build_move_teaching_decision,
        MoveInputs as _CaptionMoveInputs,
        CrossMoveState as _CaptionCrossMoveState,
    )
except Exception as _caption_import_exc:  # pragma: no cover — defensive
    _compute_severity_for_move = None
    _build_move_teaching_decision = None
    _CaptionMoveInputs = None
    _CaptionCrossMoveState = None
    logger.warning(f"[caption_v5] import failed; pipeline disabled: {_caption_import_exc}")
    CAPTION_V5_PIPELINE_ENABLED = False

# Trap recognition (named opening traps from data/traps.json). Stateful:
# fires on setup-completing move and again on each move that follows the
# authored trap_line. Pure Python, no engine call.
try:
    from services.trap_recognition import detect_trap_setup, match_trap_line_step
except Exception as _trap_import_exc:  # pragma: no cover — defensive
    detect_trap_setup = None
    match_trap_line_step = None
    logger.warning(f"[trap] import failed; trap layer disabled: {_trap_import_exc}")

# Opening curriculum lookup (data/opening_curriculum.json). Matches the
# moving side's played-move prefix against setup_order. Returns name +
# summary + golden_rules when on-book ≥ 3 setup moves.
try:
    from services.opening_lookup import match_opening_for_mover
except Exception as _opening_import_exc:  # pragma: no cover — defensive
    match_opening_for_mover = None
    logger.warning(f"[opening] import failed; opening layer disabled: {_opening_import_exc}")

# Load theory data
THEORY_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "theory")
COACHING_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "coaching")


def _load_json_safe(filepath: str) -> dict:
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
            data.pop("_meta", None)
            return data
    except Exception as e:
        logger.warning(f"Could not load {filepath}: {e}")
        return {}


# Cache for theory data
_THEORY_CACHE = {}

def get_theory_data(key: str) -> dict:
    global _THEORY_CACHE
    if key not in _THEORY_CACHE:
        if key == "endgame_principles":
            _THEORY_CACHE[key] = _load_json_safe(os.path.join(THEORY_DIR, "endgame_principles.json"))
        elif key == "opening_mistakes":
            _THEORY_CACHE[key] = _load_json_safe(os.path.join(THEORY_DIR, "opening_mistakes.json"))
        elif key == "tactical_patterns":
            _THEORY_CACHE[key] = _load_json_safe(os.path.join(THEORY_DIR, "tactical_patterns.json"))
        elif key == "positional_rules":
            _THEORY_CACHE[key] = _load_json_safe(os.path.join(THEORY_DIR, "positional_rules.json"))
        elif key == "opening_plans":
            _THEORY_CACHE[key] = _load_json_safe(os.path.join(COACHING_DIR, "opening_plans.json"))
    return _THEORY_CACHE.get(key, {})


# ─── DATA CLASSES ───────────────────────────────────────────────────

@dataclass
class CandidateMove:
    """A candidate move with its strategic idea."""
    move_san: str                # The move in SAN notation
    idea: str                    # The strategic idea/plan behind this move
    move_type: str               # "counter_attack" | "prophylactic" | "development" | "central" | "tactical"


@dataclass
class ChessPlan:
    """A transferable chess plan (not just moves)."""
    goal: str                    # What we're trying to achieve
    current_problem: str         # Why current move doesn't achieve it
    consequence: str             # What happens after (the future)
    better_approach: str         # What to do instead (summary)
    transferable_learning: str   # The concept that applies to many games
    concept_id: str              # Unique ID for tracking acknowledgment
    concept_type: str            # "opening" | "endgame" | "tactical" | "positional"
    candidate_moves: List[Dict] = field(default_factory=list)  # Multiple alternatives with ideas


@dataclass
class MoveCoaching:
    """Complete coaching for a single move."""
    # Identification
    move_number: int
    move_san: str
    is_user_move: bool
    is_white: bool
    fen_before: str
    fen_after: str
    phase: str  # opening/middlegame/endgame
    
    # Evaluation
    cp_loss: int
    eval_before: Optional[int]
    eval_after: Optional[int]
    best_move_san: Optional[str]
    severity: str  # good/inaccuracy/mistake/blunder/context
    
    # The Coaching (V5)
    narrative: str              # Simple, 1200-friendly explanation
    plan: Optional[ChessPlan]   # The transferable plan
    
    # For clickable UI
    future_moves: List[str]     # PV moves to show on board
    highlight_squares: List[str]  # Key squares to highlight
    
    # Theory connection
    theory_match: Optional[Dict]  # Matched theory pattern
    needs_acknowledgment: bool    # Show "I understand" button
    already_acknowledged: bool    # User already knows this
    acknowledgment_prompt: Optional[str]  # Message about understanding
    
    # For opponent moves
    your_plan_now: Optional[str]  # What user should do after this
    
    # Tracking
    is_best_move: bool           # Did user play the best move?
    concept_applied: Optional[str]  # What concept user demonstrated


# ─── PHASE DETECTION ─────────────────────────────────────────────────

def detect_phase(board: chess.Board, move_number: int) -> str:
    """Detect game phase based on material and move number."""
    piece_count = len(board.piece_map())
    queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
    
    if move_number <= 10 and piece_count >= 28:
        return "opening"
    if move_number <= 15 and piece_count >= 24:
        return "opening"
    if queens == 0 or piece_count <= 12:
        return "endgame"
    if piece_count <= 18:
        return "endgame"
    return "middlegame"


def get_piece_name(piece: chess.Piece) -> str:
    names = {
        chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
        chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"
    }
    return names.get(piece.piece_type, "piece")


# ─── OPENING DETECTION ───────────────────────────────────────────────

def detect_opening_from_pgn(pgn: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract opening name and ECO code from PGN headers."""
    opening_name = None
    eco_code = None
    
    eco_match = re.search(r'\[ECO\s+"([^"]+)"\]', pgn)
    if eco_match:
        eco_code = eco_match.group(1)
    
    opening_match = re.search(r'\[Opening\s+"([^"]+)"\]', pgn)
    if opening_match:
        opening_name = opening_match.group(1)
    
    if not opening_name:
        eco_url_match = re.search(r'\[ECOUrl\s+"[^"]*openings/([^"]+)"\]', pgn)
        if eco_url_match:
            opening_name = eco_url_match.group(1).replace("-", " ").title()
    
    return opening_name, eco_code


def get_opening_data(eco_code: Optional[str], opening_name: Optional[str]) -> dict:
    """Get opening-specific plans and ideas."""
    opening_plans = get_theory_data("opening_plans")
    if not opening_plans:
        return opening_plans.get("default", {})
    
    # Match by ECO code
    if eco_code:
        eco_prefix = eco_code[:2] if len(eco_code) >= 2 else eco_code
        for key, data in opening_plans.items():
            if key.startswith("_"):
                continue
            prefixes = data.get("eco_prefix", [])
            if eco_code in prefixes or eco_prefix in [p[:2] for p in prefixes]:
                return data
    
    # Match by name
    if opening_name:
        name_lower = opening_name.lower()
        for key, data in opening_plans.items():
            if key.startswith("_"):
                continue
            if key.replace("_", " ") in name_lower or data.get("name", "").lower() in name_lower:
                return data
    
    return opening_plans.get("default", {})


def get_opening_introduction(
    eco_code: Optional[str],
    opening_name: Optional[str],
    move_san: str,
    user_color: str,
    move_index: Optional[int] = None,
    prev_move_san: Optional[str] = None,
) -> Optional[Dict]:
    """
    Get opening introduction for the first few moves.
    Returns context about what opening this is and what the plans are.

    move_index (ply index, 0-based) is used to gate the "first-move
    opening" labels: e4/d4/c4/Nf3 only refer to a named opening when
    they are white's literal first move (idx 0); e5/c5/c6/Nf6 etc only
    when they are black's literal first response (idx 1). Without this
    gate, Nf3 played as move 3 (e.g., after 1.e4 e5 2.f4) gets labelled
    "Réti Opening" — wrong, because Réti specifically means 1.Nf3 with
    no prior pawn play. Source bug: fb_d0454a4088f3.
    """
    # Common opening patterns by first moves
    opening_intros = {
        # White first moves
        "e4": {
            "name": "King's Pawn Opening",
            "idea": "White stakes a claim in the center. Most popular opening - leads to open games.",
            "black_response_hint": "You can match with e5 (Open Game) or fight back with c5 (Sicilian), e6 (French), c6 (Caro-Kann), or d5 (Scandinavian)."
        },
        "d4": {
            "name": "Queen's Pawn Opening", 
            "idea": "White controls the center from the side. Games tend to be more closed and strategic.",
            "black_response_hint": "d5 is solid (closed games), Nf6 is flexible (Indian systems), f5 is aggressive (Dutch)."
        },
        "c4": {
            "name": "English Opening",
            "idea": "White controls d5 without committing the d-pawn. Flexible and positional.",
            "black_response_hint": "c5 for symmetry, e5 to grab space, Nf6 for flexibility."
        },
        "Nf3": {
            "name": "Réti Opening",
            "idea": "White develops without committing pawns. Can transpose to many openings.",
            "black_response_hint": "d5 is the most principled. Nf6 mirrors White's approach."
        },
        
        # Common Black responses to e4
        "e5": {"name": "Open Game", "idea": "Symmetric center control. Leads to tactical play."},
        "c5": {"name": "Sicilian Defense", "idea": "Asymmetric counter-attack. Black fights for d4 control."},
        "e6": {"name": "French Defense", "idea": "Solid but cramped. Black will undermine with c5 and sometimes f6."},
        "c6": {"name": "Caro-Kann Defense", "idea": "Very solid. Black develops the bishop to f5 or g4 before e6."},
        
        # Common Black responses to d4
        "d5": {"name": "Closed Game", "idea": "Solid central control. Strategic middlegames."},
        "Nf6": {"name": "Indian Defense", "idea": "Flexible - can become King's Indian, Nimzo-Indian, or Queen's Indian."},
        
        # Common follow-ups
        "Nc3": {"idea": "Develops naturally, prepares e4 or supports d5."},
        "Bf4": {"name": "London System", "idea": "White develops bishop before e3. Solid and easy to play."},
        "Bg5": {"idea": "Pins the knight. White may double Black's pawns or force concessions."},
        "Bc4": {"name": "Italian Game direction", "idea": "Aims at f7 weakness. Classic development."},
        "Bb5": {"name": "Spanish Game direction", "idea": "Pressures e5 indirectly through the knight on c6."},
        # v74 (2026-05-23) — Mohit + Parth feedback. Extend coverage so
        # early opening moves get a name + idea even outside the strict
        # m1/m2 set above. These are context-light (the move's idea on
        # its own); the V5 service combines them with detected
        # opening_name when both are available.
        "d6": {
            "name": "Philidor-style setup",
            # fb_d098b736e25c: "your dark-squared bishop" was ambiguous —
            # Mohit asked "your or their." Name the square (f8) and skip
            # the dark-squared label so the reference is unambiguous.
            "idea": "Defends e5 with the d-pawn. Solid but passive — Black's f8-bishop stays blocked behind the d6 and e5 pawns.",
        },
        "Be7": {
            "idea": "Passive bishop development. Safe but doesn't create pressure — Bc5 or Bb4 are usually more active.",
        },
        "g6": {
            "idea": "Fianchetto setup — the bishop will go to g7 to control the long diagonal.",
        },
        "Nbd2": {
            "idea": "Quiet development. Reroutes via f1-g3 in some structures; keeps the c-pawn free.",
        },
        "Nbc3": {
            "idea": "Develops the queenside knight. Blocks the c-pawn — usually fine, but watch for c-pawn-blocked positions.",
        },
    }
    
    # Gate first-move labels on move_index — see docstring. The set
    # of move_sans below is "openings named purely from the move name,
    # ASSUMING it's the first or second ply." Without the gate they
    # mis-fire on transpositions.
    _WHITE_FIRST_MOVE_OPENINGS = {"e4", "d4", "c4", "Nf3"}
    _BLACK_FIRST_RESPONSES = {"e5", "c5", "e6", "c6", "d5", "Nf6"}

    # v74 (2026-05-23) — Mohit + Parth: prev_move context fix.
    # 1.e4 d5 = Scandinavian Defense, but the move-keyed dict has
    # `d5 → "Closed Game"` (correct for 1.d4 d5). Disambiguate by
    # looking at prev_move when it's an idx=1 black response.
    _CONTEXT_OVERRIDES = {
        # (move_san, prev_move_san, move_index) → intro
        # v91 (2026-05-25): Parth fb_9539edd1bfa1 — "not draws white
        # queen out. Black queen usually comes out early usually to
        # recapture on d4. White then develops Knight with tempo."
        # In the Scandinavian after 1.e4 d5 2.exd5, BLACK's queen
        # comes out to recapture on d5 (Qxd5), then white attacks
        # the black queen with Nc3, gaining tempo.
        ("d5", "e4", 1): {
            "name": "Scandinavian Defense",
            "idea": "Black challenges the centre immediately. After 2.exd5 Qxd5, Black's queen comes out early to recapture — and White develops with tempo by Nc3.",
        },
        # Parth fb_95ff0d1ec513 (2026-05-31): "it is not exactly
        # Italian yet. It can transpose to italian though." The
        # default "Bc4" entry in opening_intros labels every Bc4 as
        # "Italian Game direction" — but 1.e4 e5 2.Bc4 is the
        # BISHOP'S OPENING (ECO C23-C24), not Italian. The Italian
        # Game proper requires 1.e4 e5 2.Nf3 Nc6 3.Bc4. This entry
        # catches the 2.Bc4 case via (Bc4, e5, move_index=2) and
        # leaves the default to fire on the 3.Bc4 (post-Nf3/Nc6)
        # transposed case, where the label is correct.
        ("Bc4", "e5", 2): {
            "name": "Bishop's Opening",
            "idea": "Aims at the f7 square. Not the Italian Game yet — it transposes there if Nf3 and Nc6 follow.",
        },
        # Parth fb_541f1f71cbe2 (2026-05-31, authoring): after
        # 1.e4 e5 2.Bc4 (Bishop's Opening), Black's Nf6 is principled:
        # develops a piece + hits e4 + no Nf3 means e5 isn't actually
        # under attack so Black can play centrally. Also covers
        # important king-side squares against early queen tricks
        # (Scholar's Mate ideas).
        ("Nf6", "Bc4", 3): {
            "name": None,
            "idea": "Develops your knight and attacks e4. White hasn't played Nf3, so e5 is safe. Also defends against early queen attacks.",
        },
        # Parth fb_b0379bf528f0 (2026-05-31, authoring): after
        # 1.e4 e5 2.Bc4 Nf6 3.d3 (Bishop's Opening, Berlin Defense
        # style). d3 supports e4, strengthens Bc4, and opens the
        # c1 bishop's diagonal. Black's main equalizing plan is
        # ...c6 preparing the ...d5 break.
        ("d3", "Nf6", 4): {
            "name": "Bishop's Opening, Berlin Defense",
            "idea": "Supports e4, strengthens the Bc4, and frees the dark-square bishop. Black's main plan is ...c6 preparing the ...d5 break.",
        },
        # Parth fb_b554778710ba (2026-05-31, authoring): after
        # 1.e4 e5 2.Bc4 Nf6 3.d3 Bc5. Bishop sits outside the pawn
        # chain (not blocked behind a future d6 push), so the bishop
        # stays active. Black is ready to castle.
        ("Bc5", "d3", 5): {
            "name": None,
            "idea": "Active bishop placement. It sits outside the pawn chain, so a later ...d6 won't lock it in. Castle next.",
        },
    }
    if (
        prev_move_san
        and move_index is not None
        and (move_san, prev_move_san, move_index) in _CONTEXT_OVERRIDES
    ):
        ctx = _CONTEXT_OVERRIDES[(move_san, prev_move_san, move_index)]
        return {
            "name": ctx.get("name"),
            "idea": ctx.get("idea"),
            "hint": None,
        }

    if move_san in opening_intros:
        if move_index is not None:
            if move_san in _WHITE_FIRST_MOVE_OPENINGS and move_index != 0:
                # Not white's first move — can't be the named first-move
                # opening (likely a transposition). v74: but still surface
                # a generic development idea if the move is in the
                # "follow-up" tier of opening_intros (no `name` key,
                # just `idea`) — that's safe at any ply.
                follow_up = opening_intros[move_san]
                if not follow_up.get("name"):
                    return {
                        "name": None,
                        "idea": follow_up.get("idea"),
                        "hint": None,
                    }
                # v74: Nf3/Nc3/etc. at idx > 0 — return generic
                # development idea instead of misnaming as Réti.
                # Mohit 2026-05-28 (game 2d7ade57 m2 d4): the fallback
                # idea ('Develops a piece... Knights before bishops')
                # was firing on PAWN MOVES like d4 because
                # _WHITE_FIRST_MOVE_OPENINGS includes d4/c4/e4 as
                # legitimate first moves. Gate the develop-piece prose
                # to actual knight/bishop SAN (move_san starts with
                # 'N' or 'B'). Pawn moves at idx>0 fall through —
                # other detectors (R15 central_break, opening curriculum)
                # handle them; silent is fine when none fire.
                if move_san and move_san[0] in ("N", "B"):
                    return {
                        "name": None,
                        "idea": "Develops a piece toward the center. Knights before bishops, control the center.",
                        "hint": None,
                    }
                return None
            if move_san in _BLACK_FIRST_RESPONSES and move_index != 1:
                # Not black's first response — same reasoning.
                return None
        intro = opening_intros[move_san]
        return {
            "name": intro.get("name"),
            "idea": intro.get("idea"),
            "hint": intro.get("black_response_hint") if user_color == "black" else None
        }
    
    # Use ECO-based name if available
    if opening_name:
        return {
            "name": opening_name,
            "idea": None,
            "hint": None
        }
    
    return None


# ─── OPENING BOOK MOVE DETECTION ─────────────────────────────────────

# Known opening responses that Stockfish may score poorly but are completely valid theory.
# Maps FEN position prefix -> set of valid SAN moves in that position.
# We only need to track positions where Stockfish might disagree with theory.
KNOWN_OPENING_RESPONSES = None  # Will be built dynamically using python-chess

def is_book_opening_move(board: chess.Board, move_san: str, move_index: int,
                         opening_name: Optional[str] = None, cp_loss: int = 0,
                         move_history: Optional[List[str]] = None) -> bool:
    """
    Check if a user's move is a known opening book move that shouldn't be
    flagged as an inaccuracy, even if Stockfish slightly prefers another line.

    Returns True if the move is a recognized opening response.

    move_history: optional list of SAN moves played up to (not including)
        the candidate move. When provided, the opening-detection check uses
        it directly. When None, falls back to board.move_stack (which is
        empty if board was built from a raw FEN). Audit scripts that
        reconstruct from FEN should pass move_history explicitly.
    """
    # Only applies to early game (first 12 half-moves)
    if move_index > 12:
        return False
    
    # If cp_loss is very high (>120), it's genuinely bad even for an opening
    if cp_loss > 120:
        return False
    
    # --- Check 1: Use the opening-detection service for moves >= 2 ---
    # Reconstruct the played sequence + the candidate move, ask
    # services.opening_mastery whether the sequence matches a known
    # opening line. Handles 23+ openings via the existing detector —
    # no hardcoded per-opening response sets here. Detector requires
    # at least 2 moves to classify, so move 1 (idx 0/1) falls through
    # to Check 2 below.
    try:
        from services.opening_mastery import detect_opening_from_moves
        # Prefer explicit move_history when caller provides it (audit
        # scripts reconstructing from FEN). Fall back to board.move_stack
        # (production path where board was built incrementally).
        if move_history is not None:
            prior_sans = list(move_history)
        else:
            replay_board = chess.Board()
            prior_sans = []
            for past_mv in board.move_stack:
                prior_sans.append(replay_board.san(past_mv))
                replay_board.push(past_mv)
        full_sequence = prior_sans + [move_san]
        opening_info = detect_opening_from_moves(full_sequence)
        if opening_info and opening_info.get("opening_key"):
            return True
    except Exception:
        pass

    # --- Check 2: Move-1 sanity (detector needs >=2 moves to classify) ---
    # Any standard first move by white is book. Any standard first
    # response by black to a recognised first move is book.
    _STANDARD_FIRST_WHITE_MOVES = {
        "e4", "d4", "c4", "Nf3", "g3", "b3", "f4", "e3", "d3", "b4", "Nc3",
    }
    _STANDARD_FIRST_BLACK_RESPONSES = {
        "e5", "c5", "e6", "c6", "d5", "d6", "Nf6", "Nc6", "g6", "b6", "a6", "f5",
    }
    if move_index == 0 and move_san in _STANDARD_FIRST_WHITE_MOVES:
        return True
    if move_index == 1 and move_san in _STANDARD_FIRST_BLACK_RESPONSES:
        return True
    
    # --- Check 2: If opening was detected, trust early moves ---
    # If the game eventually reaches a recognized opening (e.g., Scandinavian),
    # the moves that got us there were book moves
    if opening_name and move_index < 8:
        return True
    
    # --- Check 3: Common early-game developing moves with small cp_loss ---
    # In the first few moves, natural developing moves shouldn't be flagged
    if move_index <= 6 and cp_loss < 60:
        # Check if it's a natural developing move
        try:
            move = board.parse_san(move_san)
            piece = board.piece_at(move.from_square)
            if piece:
                # Knight/Bishop development, castling, central pawn pushes
                if piece.piece_type in (chess.KNIGHT, chess.BISHOP):
                    return True
                if piece.piece_type == chess.KING and board.is_castling(move):
                    return True
                if piece.piece_type == chess.PAWN:
                    # Central or semi-central pawn moves
                    to_file = chess.square_file(move.to_square)
                    if to_file in (2, 3, 4, 5):  # c, d, e, f files
                        return True
        except Exception:
            pass
    
    return False


# ─── PLAN EXTRACTION ─────────────────────────────────────────────────

def extract_plan_from_pv(
    board: chess.Board,
    played_move: chess.Move,
    best_move: Optional[str],
    pv_after_played: List[str],
    pv_after_best: List[str],
    phase: str,
    opening_data: dict,
    cp_loss: int,
    eco_code: Optional[str] = None,
    stockfish_candidates: Optional[List[Dict]] = None
) -> Optional[ChessPlan]:
    """
    Extract a PLAN from the Stockfish PV (not just moves).
    
    This is the core innovation of V5 - turning engine analysis into
    transferable chess understanding.
    """
    if cp_loss < 30:
        return None  # Good moves don't need a plan explanation
    
    played_san = board.san(played_move)
    
    # ─── MATE BLUNDER CHECK ──────────────────────────────
    # If this move allows checkmate, everything else is irrelevant.
    #
    # The trigger condition (cp_loss >= 5000 OR PV-has-"#") is too
    # eager — fb_ca616e985bf8 fired "Bb6 allows checkmate" on a 50-pawn
    # eval swing where no forced mate actually existed (white's
    # position was already losing; Bb6 made it more losing without a
    # real mate threat). Verify the mate claim with a deeper engine
    # search before emitting "allows checkmate."
    mate_trigger = (
        cp_loss >= 5000
        or (pv_after_played and any("#" in m for m in pv_after_played[:4]))
    )
    if mate_trigger:
        board_after = board.copy()
        board_after.push(played_move)

        # Verify the mate claim against the engine. losing_side is the
        # player whose move is accused (the side whose turn it WAS in
        # `board`, before played_move).
        mate_confirmed = True
        try:
            from services.threat_verifier import (
                _get_singleton_engine,
                position_allows_forced_mate,
            )
            engine = _get_singleton_engine()
            if engine is not None:
                mate_confirmed = position_allows_forced_mate(
                    fen_after_played_move=board_after.fen(),
                    losing_side=board.turn,
                    engine=engine,
                )
        except Exception as exc:
            logger.debug(f"[V5] mate verifier skipped: {exc}")

        if mate_confirmed:
            consequence = _describe_consequence(pv_after_played, board_after) if pv_after_played else "This allows a forced checkmate."
            return ChessPlan(
                goal="Avoid checkmate",
                current_problem=f"{played_san} allows checkmate.",
                consequence=consequence,
                better_approach=f"{best_move} stops the checkmate and keeps the game going." if best_move else "You needed to block the checkmate threat first.",
                transferable_learning="Before every move, check: can my opponent give checkmate? If yes, stop that before doing anything else.",
                concept_id="king_safety_mate_threat",
                concept_type="tactical"
            )
        # Mate not confirmed — fall through to the regular plan-
        # extraction path so the caption describes the actual eval
        # swing (material loss, positional collapse) instead of
        # claiming a checkmate that doesn't exist.
    
    # Create a board with the user's move played (for consequence analysis)
    board_after_move = board.copy()
    board_after_move.push(played_move)
    
    # Try opening theory tree first (more comprehensive)
    try:
        from services.opening_theory_tree_service import get_mistake_from_theory
        
        theory_mistake = get_mistake_from_theory(eco_code, played_san, board.fen())
        if theory_mistake:
            return ChessPlan(
                goal="Follow opening principles",
                current_problem=theory_mistake.get("why_bad", f"{played_san} is a theoretical mistake"),
                consequence=theory_mistake.get("consequence", _describe_consequence(pv_after_played, board_after_move)),
                better_approach=f"{theory_mistake.get('better_move', best_move)} is better" if theory_mistake.get('better_move') else (f"{best_move} was better" if best_move else ""),
                transferable_learning=theory_mistake.get("learning", ""),
                concept_id=f"theory_{theory_mistake.get('position_name', 'unknown').lower().replace(' ', '_').replace(':', '_')}",
                concept_type="opening"
            )
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Theory tree lookup failed: {e}")
    
    # Try to match opening theory from legacy data
    opening_mistakes = get_theory_data("opening_mistakes")
    for pattern_id, pattern in opening_mistakes.items():
        if not isinstance(pattern, dict) or not pattern.get("fen_pattern"):
            continue
        
        try:
            pattern_board = chess.Board(pattern["fen_pattern"])
            if board.board_fen() == pattern_board.board_fen():
                bad_move = pattern.get("bad_move", "").lower().replace("+", "").replace("#", "")
                if played_san.lower().replace("+", "").replace("#", "") == bad_move:
                    return ChessPlan(
                        goal="Control the center and develop safely",
                        current_problem=pattern.get("why_bad", f"{played_san} is premature here"),
                        consequence=_describe_consequence(pv_after_played, board_after_move),
                        better_approach=f"{pattern.get('good_move', best_move)} — {pattern.get('why_good', 'keeps the position solid')}",
                        transferable_learning=pattern.get("rule", ""),
                        concept_id=pattern_id,
                        concept_type="opening"
                    )
        except Exception:
            continue
    
    # Try endgame principles
    if phase == "endgame":
        endgame_plan = _match_endgame_principle(board_after_move, played_move, best_move, pv_after_played)
        if endgame_plan:
            return endgame_plan
    
    # Try tactical patterns
    tactical_plan = _detect_tactical_issue(board_after_move, played_move, pv_after_played, cp_loss, played_san)
    if tactical_plan:
        return tactical_plan
    
    # Get the piece type for generic plan
    piece_type = board.piece_at(played_move.from_square).piece_type if board.piece_at(played_move.from_square) else None
    
    # Generic positional plan - now with Stockfish candidate moves!
    return _generate_generic_plan(
        board_after_move, played_san, piece_type, played_move.to_square,
        best_move, pv_after_played, cp_loss,
        board_before=board, played_move=played_move,
        stockfish_candidates=stockfish_candidates
    )


def _describe_consequence(pv: List[str], board: chess.Board) -> str:
    """
    Describe what SPECIFICALLY happens in the PV.
    
    Priority:
    1. Checkmate in PV → "Checkmate"
    2. Material loss in PV (walk the moves, find captures) → "Your knight gets taken"
    3. Static analysis (undefended pieces) → fallback
    """
    if not pv:
        return "Something's not right here!"
    
    sim = board.copy()
    user_color = not board.turn  # User just moved, so opponent is to move
    first_move_san = pv[0]
    
    # ─── 1. CHECKMATE CHECK ──────────────────────────────
    if "#" in first_move_san:
        return f"After {first_move_san}, it's checkmate. Game over."
    
    try:
        first_move = sim.parse_san(first_move_san)
        sim.push(first_move)
        if sim.is_checkmate():
            return f"After {first_move_san}, it's checkmate. Game over."
        
        # Check mate in PV (2-3 moves)
        sim2 = sim.copy()
        for pv_san in pv[1:4]:
            try:
                if "#" in pv_san:
                    return f"After {first_move_san}, forced checkmate follows within a few moves."
                pm = sim2.parse_san(pv_san)
                sim2.push(pm)
                if sim2.is_checkmate():
                    return f"After {first_move_san}, forced checkmate follows within a few moves."
            except Exception:
                break
    except Exception:
        pass
    
    # ─── 2. WALK THE PV — find material loss (most accurate) ───
    sim = board.copy()
    for i, san in enumerate(pv[:5]):
        try:
            move = sim.parse_san(san)
            
            if sim.is_capture(move):
                captured = sim.piece_at(move.to_square)
                if captured:
                    captured_name = _get_fun_piece_name(captured)
                    sq_name = chess.square_name(move.to_square)
                    
                    if captured.color == user_color and captured.piece_type != chess.PAWN:
                        # User loses a piece — this is the key consequence
                        # Explain the forcing sequence
                        if i == 0:
                            return f"After {san}, your {captured_name} on {sq_name} gets captured!"
                        elif i >= 2:
                            # There's a forcing sequence leading to this
                            sequence = " ".join(pv[:i+1])
                            # Check if there was a check forcing the defense
                            check_move = None
                            for j in range(i):
                                if "+" in pv[j]:
                                    check_move = pv[j]
                                    break
                            if check_move:
                                return f"After {check_move}, you're forced to deal with the check, and then {san} wins your {captured_name}!"
                            else:
                                return f"After {sequence}, your {captured_name} on {sq_name} gets taken!"
                        else:
                            return f"After {pv[0]}, your {captured_name} on {sq_name} gets captured!"
                    
                    elif captured.color == user_color and captured.piece_type == chess.PAWN:
                        # Pawn loss — note but keep looking for bigger losses
                        pass
            
            sim.push(move)
        except Exception:
            break
    
    # ─── 3. STATIC ANALYSIS — undefended pieces (fallback) ───
    sim = board.copy()
    problems = []
    
    try:
        first_move = sim.parse_san(first_move_san)
        sim.push(first_move)
        
        # Check for checks first
        if sim.is_check():
            problems.append("your King gets checked! Gotta deal with that first!")
        
        # Check user pieces for new attacks
        for sq in chess.SQUARES:
            piece = sim.piece_at(sq)
            if piece and piece.color == user_color and piece.piece_type != chess.PAWN:
                attackers = list(sim.attackers(not user_color, sq))
                defenders = list(sim.attackers(user_color, sq))
                
                if attackers and not defenders:
                    piece_name = _get_fun_piece_name(piece)
                    sq_name = chess.square_name(sq)
                    problems.append(f"your {piece_name} on {sq_name} is hanging with no defenders!")
                    break
                elif attackers and len(attackers) > len(defenders):
                    piece_name = _get_fun_piece_name(piece)
                    sq_name = chess.square_name(sq)
                    problems.append(f"your {piece_name} on {sq_name} is outnumbered - {len(attackers)} vs {len(defenders)}!")
                    break
        
        # If no piece issues, check pawns
        if not problems:
            for sq in chess.SQUARES:
                piece = sim.piece_at(sq)
                if piece and piece.color == user_color and piece.piece_type == chess.PAWN:
                    attackers = list(sim.attackers(not user_color, sq))
                    defenders = list(sim.attackers(user_color, sq))
                    if attackers and not defenders:
                        sq_name = chess.square_name(sq)
                        problems.append(f"your pawn on {sq_name} is undefended!")
                        break
    except Exception:
        pass
    
    if not problems:
        problems = _analyze_positional_weakness(board, user_color)
    
    if problems:
        return f"After {first_move_san}, {problems[0]}"
    
    return f"After {first_move_san}, your opponent gains space and activity. You'll need to defend!"


def _analyze_positional_weakness(board: chess.Board, user_color: bool) -> List[str]:
    """
    Find positional weaknesses when no tactical issues are found.
    Returns a list of specific problems.
    """
    problems = []
    
    # Check for center control issues
    center_squares = [chess.D4, chess.D5, chess.E4, chess.E5]
    user_center_control = 0
    opp_center_control = 0
    
    for sq in center_squares:
        user_attackers = len(list(board.attackers(user_color, sq)))
        opp_attackers = len(list(board.attackers(not user_color, sq)))
        user_center_control += user_attackers
        opp_center_control += opp_attackers
    
    if opp_center_control > user_center_control + 3:
        problems.append("your opponent has more pieces aimed at the center (d4, d5, e4, e5). This gives their pieces better squares to go to.")
    
    # Check for development issues (pieces still on back rank)
    undeveloped = 0
    back_rank_squares = [chess.B1, chess.C1, chess.F1, chess.G1] if user_color == chess.WHITE else [chess.B8, chess.C8, chess.F8, chess.G8]
    for sq in back_rank_squares:
        piece = board.piece_at(sq)
        if piece and piece.color == user_color and piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
            undeveloped += 1
    
    if undeveloped >= 2:
        problems.append(f"you still have {undeveloped} pieces on the back rank that haven't moved. Get your knights and bishops out before attacking.")
    
    # Check for king safety (castling rights)
    if user_color == chess.WHITE:
        if not board.has_kingside_castling_rights(chess.WHITE) and not board.has_queenside_castling_rights(chess.WHITE):
            king_sq = board.king(chess.WHITE)
            if king_sq and chess.square_file(king_sq) in [3, 4]:  # King still in center
                problems.append("your king is stuck in the center and can't castle anymore. It's exposed to attacks.")
    else:
        if not board.has_kingside_castling_rights(chess.BLACK) and not board.has_queenside_castling_rights(chess.BLACK):
            king_sq = board.king(chess.BLACK)
            if king_sq and chess.square_file(king_sq) in [3, 4]:
                problems.append("your king is stuck in the center and can't castle anymore. It's exposed to attacks.")
    
    # Check for weak pawns
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == user_color and piece.piece_type == chess.PAWN:
            # Check if pawn is isolated
            file = chess.square_file(sq)
            has_neighbor = False
            for neighbor_file in [file - 1, file + 1]:
                if 0 <= neighbor_file <= 7:
                    for rank in range(8):
                        neighbor_sq = chess.square(neighbor_file, rank)
                        neighbor_piece = board.piece_at(neighbor_sq)
                        if neighbor_piece and neighbor_piece.color == user_color and neighbor_piece.piece_type == chess.PAWN:
                            has_neighbor = True
                            break
            
            if not has_neighbor:
                sq_name = chess.square_name(sq)
                attackers = list(board.attackers(not user_color, sq))
                if attackers:
                    problems.append(f"your isolated pawn on {sq_name} is a target!")
                    break
    
    return problems


def _is_move_safe(board: chess.Board, move_san: str, user_color: bool) -> bool:
    """
    Check if a move is SAFE - doesn't hang the moving piece.
    
    A move is unsafe if:
    1. The piece lands on a square attacked by a lower-value piece
    2. The piece is a Queen/Rook and lands where it can be taken
    3. The piece becomes hanging (attacked with insufficient defense)
    """
    try:
        move = board.parse_san(move_san)
    except Exception:
        return False
    
    piece = board.piece_at(move.from_square)
    if not piece:
        return False
    
    # Simulate the move
    sim = board.copy()
    sim.push(move)
    
    to_square = move.to_square
    piece_value = _piece_value(piece)
    
    # Check if the piece is now attacked
    attackers = list(sim.attackers(not user_color, to_square))
    
    if not attackers:
        return True  # Not attacked = safe
    
    # Get defenders (excluding the piece itself)
    defenders = list(sim.attackers(user_color, to_square))
    
    # For each attacker, check if it's a bad trade
    min_attacker_value = float('inf')
    for attacker_sq in attackers:
        attacker = sim.piece_at(attacker_sq)
        if attacker:
            attacker_value = _piece_value(attacker)
            min_attacker_value = min(min_attacker_value, attacker_value)
    
    # If the cheapest attacker is worth less than our piece, it's a bad trade
    # Unless we have enough defenders to make it safe
    if min_attacker_value < piece_value:
        # Simple heuristic: if attacker is worth less AND we don't have more defenders than attackers
        if len(defenders) <= len(attackers):
            return False  # Losing material!
    
    # For Queen: be VERY careful - any attack is dangerous
    if piece.piece_type == chess.QUEEN:
        # Queen is attacked - check if we can recapture profitably
        if len(attackers) > 0 and len(defenders) < len(attackers):
            return False
        # If attacked by something worth less than queen (anything except another queen)
        if min_attacker_value < piece_value:
            return False
    
    # For Rook: careful about minor pieces
    if piece.piece_type == chess.ROOK:
        if min_attacker_value <= 3:  # Bishop or knight value
            if len(defenders) < len(attackers):
                return False
    
    return True


async def _get_stockfish_candidates(board: chess.Board, num_moves: int = 3, depth: int = 12) -> List[Dict]:
    """
    Use Stockfish multi-PV to get the TOP candidate moves.
    
    This ensures we only suggest moves that are actually GOOD according to the engine.
    Returns moves sorted by evaluation (best first).
    """
    candidates = []
    
    try:
        transport, engine = await chess.engine.popen_uci(STOCKFISH_PATH)
        
        try:
            # Multi-PV analysis to get top N moves
            result = await engine.analyse(
                board,
                chess.engine.Limit(depth=depth),
                multipv=num_moves
            )
            
            for info in result:
                if "pv" not in info or not info["pv"]:
                    continue
                
                move = info["pv"][0]
                san = board.san(move)
                
                # Get evaluation
                score = info.get("score")
                if score:
                    if score.is_mate():
                        cp = 10000 if score.relative.mate() > 0 else -10000
                    else:
                        cp = score.relative.score(mate_score=10000)
                else:
                    cp = 0
                
                # Get PV continuation
                pv_san = []
                temp_board = board.copy()
                for pv_move in info["pv"][:4]:
                    try:
                        pv_san.append(temp_board.san(pv_move))
                        temp_board.push(pv_move)
                    except Exception:
                        break
                
                candidates.append({
                    "move": san,
                    "eval_cp": cp,
                    "pv": pv_san,
                    "is_best": len(candidates) == 0  # First one is best
                })
        finally:
            await engine.quit()
            
    except Exception as e:
        logger.error(f"Stockfish multi-PV analysis failed: {e}")
    
    return candidates


def _analyze_candidate_moves(
    board_before: chess.Board,
    played_move: chess.Move,
    best_move_san: Optional[str],
    user_color: bool,
    stockfish_candidates: Optional[List[Dict]] = None
) -> List[Dict]:
    """
    Analyze candidate moves from Stockfish and explain the IDEA behind each.
    
    Uses STOCKFISH multi-PV data if available, otherwise falls back to best_move only.
    This ensures we only suggest moves that are actually GOOD.
    
    Each move gets categorized and explained:
    - counter_attack: Creates threats, gains initiative  
    - prophylactic: Prevents opponent's plan
    - development: Gets pieces into the game
    - central: Controls key squares
    - tactical: Wins material or creates threats
    """
    candidates = []
    played_san = board_before.san(played_move)
    
    # Use Stockfish candidates if available
    if stockfish_candidates:
        for sf_candidate in stockfish_candidates:
            move_san = sf_candidate.get("move")
            if move_san == played_san:
                continue  # Skip the move that was actually played
            
            # Get the idea behind this Stockfish-approved move
            idea = _explain_move_idea(board_before, move_san, user_color)
            
            if idea:
                candidates.append({
                    "move": move_san,
                    "idea": idea["explanation"],
                    "type": idea["type"],
                    "is_best": sf_candidate.get("is_best", False),
                    "eval_cp": sf_candidate.get("eval_cp")
                })
            else:
                # Fallback explanation if our heuristics don't match
                candidates.append({
                    "move": move_san,
                    "idea": f"{move_san} is a strong move here according to the engine",
                    "type": "engine_choice",
                    "is_best": sf_candidate.get("is_best", False),
                    "eval_cp": sf_candidate.get("eval_cp")
                })
    
    # If no Stockfish candidates, use just the best move
    elif best_move_san:
        idea = _explain_move_idea(board_before, best_move_san, user_color)
        if idea:
            candidates.append({
                "move": best_move_san,
                "idea": idea["explanation"],
                "type": idea["type"],
                "is_best": True
            })
        else:
            candidates.append({
                "move": best_move_san,
                "idea": f"{best_move_san} was the best move here",
                "type": "engine_choice",
                "is_best": True
            })
    
    return candidates[:3]


def _explain_move_idea(board: chess.Board, move_san: str, user_color: bool) -> Optional[Dict]:
    """
    Explain the strategic idea behind a specific move.
    Returns the idea type, explanation, and a quality score.
    """
    try:
        move = board.parse_san(move_san)
    except Exception:
        return None
    
    piece = board.piece_at(move.from_square)
    if not piece:
        return None
    
    sim = board.copy()
    sim.push(move)
    
    to_sq = move.to_square
    to_file = chess.square_file(to_sq)
    to_rank = chess.square_rank(to_sq)
    
    # Check different move ideas
    ideas = []
    
    # 1. COUNTER-ATTACK: Does this move create a threat?
    threats_created = []
    for sq in chess.SQUARES:
        opp_piece = sim.piece_at(sq)
        if opp_piece and opp_piece.color != user_color:
            if sim.is_attacked_by(user_color, sq):
                # Was it attacked before?
                if not board.is_attacked_by(user_color, sq):
                    threats_created.append(_get_fun_piece_name(opp_piece))
    
    if threats_created:
        target = threats_created[0]
        ideas.append({
            "type": "counter_attack",
            "explanation": f"{move_san} attacks their {target} - forces them to respond!",
            "score": 8 if "Queen" in target or "Tower" in target else 5
        })
    
    # 2. PROPHYLACTIC: Does this move prevent an opponent threat?
    # Check if move blocks or prevents an attack
    if piece.piece_type == chess.PAWN:
        # Check for moves like a6/h6 that prevent piece invasions
        # a6 prevents Bb5 or Nb5, h6 prevents Bg5 or Ng5
        prophylactic_targets = {
            # Black pawns preventing White pieces
            chess.A6: [(chess.B5, "Bb5"), (chess.B5, "Nb5")],
            chess.H6: [(chess.G5, "Bg5"), (chess.G5, "Ng5")],
            chess.A3: [(chess.B4, "Bb4"), (chess.B4, "Nb4")],
            chess.H3: [(chess.G4, "Bg4"), (chess.G4, "Ng4")],
            # White pawns preventing Black pieces
            chess.A3: [(chess.B4, "Bb4"), (chess.B4, "Nb4")],
            chess.H3: [(chess.G4, "Bg4"), (chess.G4, "Ng4")],
        }
        
        if to_sq in prophylactic_targets:
            for target_sq, piece_name in prophylactic_targets[to_sq]:
                # Check if opponent could have played this move
                opp_color = not user_color
                for opp_move in board.legal_moves:
                    if opp_move.to_square == target_sq:
                        opp_piece = board.piece_at(opp_move.from_square)
                        if opp_piece and opp_piece.color == opp_color:
                            ideas.append({
                                "type": "prophylactic",
                                "explanation": f"{move_san} stops {piece_name} - no invasion allowed!",
                                "score": 5
                            })
                            break
        
        # Generic prophylactic check for pawn moves on the wings
        if to_file in [0, 7]:  # a or h pawn
            # Check if this stops a knight/bishop invasion to b5/g5
            invasion_squares = []
            if user_color == chess.BLACK:
                invasion_squares = [chess.B5, chess.G5] if to_file == 0 else [chess.G5, chess.B5]
            else:
                invasion_squares = [chess.B4, chess.G4] if to_file == 0 else [chess.G4, chess.B4]
            
            for inv_sq in invasion_squares:
                if board.is_attacked_by(not user_color, inv_sq):
                    ideas.append({
                        "type": "prophylactic",
                        "explanation": f"{move_san} prevents their piece from invading {chess.square_name(inv_sq)}",
                        "score": 4
                    })
                    break
        
        # Check if pawn stops piece from coming to a square
        blocked_squares = [to_sq + 8, to_sq + 9, to_sq + 7] if user_color == chess.WHITE else [to_sq - 8, to_sq - 9, to_sq - 7]
        for bsq in blocked_squares:
            if 0 <= bsq < 64 and board.is_attacked_by(not user_color, bsq):
                ideas.append({
                    "type": "prophylactic",
                    "explanation": f"{move_san} blocks their piece from reaching {chess.square_name(bsq)}",
                    "score": 3
                })
                break
    
    # 3. DEVELOPMENT: Is this developing a piece?
    if piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
        back_rank = 0 if user_color == chess.WHITE else 7
        if chess.square_rank(move.from_square) == back_rank:
            # Check if it's going to a good square
            center_distance = abs(to_file - 3.5) + abs(to_rank - 3.5)
            if center_distance < 3:
                ideas.append({
                    "type": "development",
                    "explanation": f"{move_san} develops with a purpose - aims at the center",
                    "score": 6
                })
            else:
                ideas.append({
                    "type": "development",
                    "explanation": f"{move_san} develops a piece toward the center",
                    "score": 4
                })
    
    # 4. CENTRAL CONTROL: Does this move improve center control?
    center_squares = [chess.D4, chess.D5, chess.E4, chess.E5]
    if to_sq in center_squares:
        if piece.piece_type == chess.PAWN:
            # Distinguish first central push (d2-d4) from break (d3-d4).
            # Both land on d4 but they're different ideas: the first
            # OCCUPIES the center; the second CHALLENGES the opposing
            # pawn that already contests the center. Same words for both
            # produces nonsense like "puts your pawn in the center" when
            # the pawn was already on d3.
            from_rank = chess.square_rank(move.from_square)
            is_first_push = (
                (user_color == chess.WHITE and from_rank == 1)
                or (user_color == chess.BLACK and from_rank == 6)
            )
            if is_first_push:
                ideas.append({
                    "type": "central",
                    "explanation": f"{move_san} puts your pawn in the center where it controls the most squares",
                    "score": 7,
                })
            else:
                # Identify the enemy pawn this break now attacks, if any.
                attacked_pawn_sq = None
                for atk_sq in sim.attacks(to_sq):
                    p = sim.piece_at(atk_sq)
                    if p and p.color != user_color and p.piece_type == chess.PAWN:
                        attacked_pawn_sq = atk_sq
                        break
                if attacked_pawn_sq is not None:
                    ideas.append({
                        "type": "central",
                        "explanation": f"{move_san} strikes at their pawn on {chess.square_name(attacked_pawn_sq)} and opens the center",
                        "score": 7,
                    })
                else:
                    ideas.append({
                        "type": "central",
                        "explanation": f"{move_san} pushes forward in the center and opens lines",
                        "score": 7,
                    })
        else:
            placed_name = chess.piece_name(piece.piece_type)
            ideas.append({
                "type": "central",
                "explanation": f"{move_san} puts your {placed_name} in the center where it controls the most squares",
                "score": 7,
            })
    elif piece.piece_type == chess.PAWN and to_file in [3, 4]:  # d or e file
        ideas.append({
            "type": "central",
            "explanation": f"{move_san} fights for central space",
            "score": 5
        })
    
    # 5. CASTLING: King safety
    if board.is_castling(move):
        ideas.append({
            "type": "king_safety",
            "explanation": f"{move_san} castles your king to safety and connects your rooks",
            "score": 7
        })
    
    # 6. TACTICAL: Check or capture
    if sim.is_check():
        ideas.append({
            "type": "tactical",
            "explanation": f"{move_san} gives check — your opponent must respond to this first",
            "score": 6
        })
    
    if board.is_capture(move):
        captured = board.piece_at(move.to_square)
        if captured:
            attacker_value = _piece_value(piece)
            captured_value = _piece_value(captured)
            captured_name = _get_fun_piece_name(captured)
            attacker_name = _get_fun_piece_name(piece)
            to_sq_name = chess.square_name(move.to_square)
            if captured_value > attacker_value:
                ideas.append({
                    "type": "tactical",
                    "explanation": f"{move_san} takes their {captured_name} on {to_sq_name} with your {attacker_name} — winning material",
                    "score": 9
                })
            elif captured_value == attacker_value:
                # Equal trade — explain WHY it might be good (removes a defender, etc.)
                sim_after = board.copy()
                sim_after.push(move)
                # Check if this creates new threats
                new_threats = []
                for sq in chess.SQUARES:
                    target = sim_after.piece_at(sq)
                    if target and target.color != piece.color and target.piece_type not in (chess.PAWN, chess.KING):
                        if sim_after.is_attacked_by(piece.color, sq) and not board.is_attacked_by(piece.color, sq):
                            new_threats.append(f"{_get_fun_piece_name(target)} on {chess.square_name(sq)}")
                if new_threats:
                    ideas.append({
                        "type": "tactical",
                        "explanation": f"{move_san} trades {attacker_name} for their {captured_name} and reveals an attack on their {new_threats[0]}",
                        "score": 9
                    })
                else:
                    ideas.append({
                        "type": "tactical",
                        "explanation": f"{move_san} captures their {captured_name} on {to_sq_name}",
                        "score": 7
                    })
    
    # Return the best idea for this move
    if ideas:
        ideas.sort(key=lambda x: x["score"], reverse=True)
        return ideas[0]
    
    return None




def _match_endgame_principle(
    board: chess.Board,
    played_move: chess.Move,
    best_move: Optional[str],
    pv: List[str]
) -> Optional[ChessPlan]:
    """Match position to endgame principles."""
    endgame_principles = get_theory_data("endgame_principles")
    
    # Count material to classify endgame type
    pieces = {}
    for color_name, color in [("white", chess.WHITE), ("black", chess.BLACK)]:
        for piece_name, piece_type in [("Q", chess.QUEEN), ("R", chess.ROOK), ("B", chess.BISHOP), ("N", chess.KNIGHT), ("P", chess.PAWN)]:
            pieces[f"{color_name}_{piece_name}"] = len(board.pieces(piece_type, color))
    
    total = sum(v for k, v in pieces.items())
    has_rook = (pieces["white_R"] + pieces["black_R"]) > 0
    has_pawn = (pieces["white_P"] + pieces["black_P"]) > 0
    
    # Rook endgame
    if has_rook and total <= 6:
        for key, principle in endgame_principles.items():
            if principle.get("pattern_type") == "rook_endgame":
                return ChessPlan(
                    goal=principle.get("key_rule", "Activate your rook"),
                    current_problem=principle.get("common_mistake", "Passive play"),
                    consequence=_describe_consequence(pv, board),
                    better_approach=principle.get("correct_technique", ""),
                    transferable_learning=principle.get("rule", ""),
                    concept_id=key,
                    concept_type="endgame"
                )
    
    # King and pawn
    if has_pawn and total <= 3:
        for key, principle in endgame_principles.items():
            if principle.get("pattern_type") == "KP_vs_K":
                return ChessPlan(
                    goal=principle.get("key_rule", "Get your king in front of the pawn"),
                    current_problem=principle.get("common_mistake", "Pushing the pawn too early"),
                    consequence=_describe_consequence(pv, board),
                    better_approach=principle.get("correct_technique", ""),
                    transferable_learning=principle.get("rule", ""),
                    concept_id=key,
                    concept_type="endgame"
                )
    
    return None


def _detect_tactical_issue(
    board_after: chess.Board,
    played_move: chess.Move,
    pv: List[str],
    cp_loss: int,
    played_san: str
) -> Optional[ChessPlan]:
    """Detect if the move allows a tactical pattern."""
    if cp_loss < 100:
        return None
    
    tactical_patterns = get_theory_data("tactical_patterns")
    
    # Board already has the move played
    sim = board_after.copy()
    user_color = not board_after.turn  # The user just moved
    
    if pv:
        try:
            opp_response = sim.parse_san(pv[0])
            
            # Check for fork
            if sim.piece_at(opp_response.from_square):
                if sim.piece_at(opp_response.from_square).piece_type == chess.KNIGHT:
                    # Check if THIS SPECIFIC knight attacks multiple pieces after moving
                    sim2 = sim.copy()
                    sim2.push(opp_response)
                    knight_landing = opp_response.to_square
                    # Only check squares attacked by THIS knight (not all opponent pieces)
                    knight_attacks = sim2.attacks(knight_landing)
                    attacked = []
                    attacked_values = []
                    for sq in knight_attacks:
                        piece = sim2.piece_at(sq)
                        if piece and piece.color == user_color and piece.piece_type != chess.PAWN:
                            piece_name = _get_fun_piece_name(piece)
                            attacked.append(piece_name)
                            attacked_values.append(_piece_value(piece))

                    # Fork detected if attacking 2+ valuable pieces (total value >= 5)
                    if len(attacked) >= 2 and sum(attacked_values) >= 5:
                        attacked_with_values = list(zip(attacked, attacked_values))
                        attacked_with_values.sort(key=lambda x: x[1], reverse=True)
                        piece1 = attacked_with_values[0][0]
                        piece2 = attacked_with_values[1][0]

                        return ChessPlan(
                            goal="Avoid knight forks",
                            current_problem=f"{played_san} allows a knight fork — their knight can attack two of your pieces at once.",
                            consequence=f"After {pv[0]}, their knight attacks your {piece1} and {piece2}. You can only save one.",
                            better_approach=f"Before playing {played_san}, check: can a knight jump to a square that attacks two of my pieces?",
                            transferable_learning=f"A knight fork happens when one knight attacks two valuable pieces at once. You lose one of them. Always check if your {piece1} and {piece2} can both be reached by one knight jump.",
                            concept_id="knight_fork",
                            concept_type="tactical"
                        )
            
            # Check for back rank issues — ONLY if:
            # 1. It's middlegame or later (move > 20)
            # 2. King is actually on the back rank
            # 3. The check is from a rook or queen (not a minor piece)
            move_count = board_after.fullmove_number or (len(sim.move_stack) // 2)
            checking_piece = sim.piece_at(opp_response.from_square) if opp_response else None
            is_heavy_piece_check = checking_piece and checking_piece.piece_type in (chess.ROOK, chess.QUEEN)
            if sim.is_check() and move_count > 20 and is_heavy_piece_check:
                king_sq = sim.king(user_color)
                if king_sq and chess.square_rank(king_sq) in [0, 7]:
                    pattern = tactical_patterns.get("back_rank_weakness", {})
                    return ChessPlan(
                        goal="Protect your back rank",
                        current_problem=f"{played_san} leaves your back rank weak. Your king has no escape square.",
                        consequence=f"After {pv[0]}, your opponent threatens checkmate on the back rank.",
                        better_approach="Push h3 or g3 to give your king an escape square before this becomes a problem.",
                        transferable_learning=pattern.get("rule", "If your king is on the back rank with no escape square, a rook or queen can checkmate you. Push one pawn (h3 or g3) to create a way out."),
                        concept_id="back_rank_weakness",
                        concept_type="tactical"
                    )
        except Exception:
            pass
    
    return None


def _generate_generic_plan(
    board_after: chess.Board,
    played_san: str,
    piece_type: Optional[int],
    to_square: int,
    best_move: Optional[str],
    pv_after_played: List[str],
    cp_loss: int,
    board_before: Optional[chess.Board] = None,
    played_move: Optional[chess.Move] = None,
    stockfish_candidates: Optional[List[Dict]] = None
) -> ChessPlan:
    """
    Generate a plan with FUN language, SPECIFIC consequences, and STOCKFISH candidate moves.
    
    Key improvement: Uses Stockfish multi-PV for candidate moves (not pattern matching).
    """
    
    # Analyze what went wrong SPECIFICALLY
    consequence = _describe_consequence(pv_after_played, board_after)
    
    # Get candidate moves with their ideas - NOW FROM STOCKFISH!
    candidate_moves = []
    if board_before and played_move:
        user_color = board_before.turn
        candidate_moves = _analyze_candidate_moves(
            board_before, played_move, best_move, user_color,
            stockfish_candidates=stockfish_candidates
        )
    
    # Build a rich "better approach" from candidates
    better_approach = _format_better_approach(candidate_moves, best_move)
    
    # Determine transferable learning based on the candidate types
    transferable_learning = _derive_transferable_learning(candidate_moves, piece_type, to_square)
    
    # ── Build concrete, board-specific explanation ──
    sq_name = chess.square_name(to_square)

    if piece_type == chess.KNIGHT:
        if chess.square_file(to_square) in [0, 7] or chess.square_rank(to_square) in [0, 7]:
            return ChessPlan(
                goal="Keep your knight active",
                current_problem=f"{played_san} puts your knight on the edge of the board where it only controls a few squares.",
                consequence=consequence,
                better_approach=better_approach or f"{best_move} keeps the knight near the center where it controls more squares.",
                transferable_learning=transferable_learning or "A knight on the edge controls 2-4 squares. In the center it controls 8. Always prefer central squares for knights.",
                concept_id="knight_on_rim",
                concept_type="positional",
                candidate_moves=candidate_moves
            )
        else:
            return ChessPlan(
                goal="Make your knight do something",
                current_problem=f"{played_san} moves your knight but it doesn't attack anything or defend anything important.",
                consequence=consequence,
                better_approach=better_approach or f"{best_move} was better here.",
                transferable_learning=transferable_learning or "Before moving a piece, ask: what will it attack or defend from the new square?",
                concept_id="piece_without_purpose",
                concept_type="positional",
                candidate_moves=candidate_moves
            )

    elif piece_type == chess.BISHOP:
        # Before defaulting to "blocked diagonal", check what the bishop
        # ACTUALLY does on its new square. If it attacks a high-value
        # enemy piece, the move is tactical, not positional — name the
        # attack target. Source bug: fb_1dbdb06502eb (Bg4 attacks queen
        # but caption said "pawns block its diagonal" — wrong reason).
        bishop_target_phrase = None
        try:
            opp_color = not board_after.turn  # bishop just moved, so it
                                              # belongs to side that just moved
            attacked_pieces = []
            for attacked_sq in board_after.attacks(to_square):
                p = board_after.piece_at(attacked_sq)
                if (
                    p
                    and p.color != opp_color
                    and p.piece_type != chess.PAWN
                    and p.piece_type != chess.KING  # checks are not "attacks on pieces" in this template
                ):
                    attacked_pieces.append((p, attacked_sq))
            # Prefer queens, then rooks, then minor pieces.
            attacked_pieces.sort(key=lambda x: -_piece_value(x[0]))
            if attacked_pieces:
                target_piece, target_sq = attacked_pieces[0]
                target_name = get_piece_name(target_piece)
                target_sq_name = chess.square_name(target_sq)
                bishop_target_phrase = (
                    f"{played_san} attacks their {target_name} on {target_sq_name}, "
                    f"but it's still a mistake here — see what comes next."
                )
        except Exception:
            bishop_target_phrase = None

        if bishop_target_phrase:
            return ChessPlan(
                goal="Make your move count tactically",
                current_problem=bishop_target_phrase,
                consequence=consequence,
                better_approach=better_approach or (f"{best_move} was better." if best_move else ""),
                transferable_learning=transferable_learning or "Attacking a piece isn't always good — check whether your opponent has a strong reply that punishes the attacker.",
                concept_id="bishop_tactical_attack",
                concept_type="tactical",
                candidate_moves=candidate_moves
            )

        return ChessPlan(
            goal="Keep your bishop on an open diagonal",
            current_problem=f"{played_san} puts your bishop where pawns block its diagonal. It can't do much from {sq_name}.",
            consequence=consequence,
            better_approach=better_approach or f"{best_move} gives the bishop a longer diagonal with more targets.",
            transferable_learning=transferable_learning or "Bishops are strongest on long, open diagonals. If your own pawns block it, look for a better diagonal.",
            concept_id="blocked_bishop",
            concept_type="positional",
            candidate_moves=candidate_moves
        )

    elif piece_type == chess.PAWN:
        return ChessPlan(
            goal="Be careful with pawn moves",
            current_problem=f"{played_san} pushes a pawn that can't come back. This weakens the squares around it.",
            consequence=consequence,
            better_approach=better_approach or f"{best_move} was safer.",
            transferable_learning=transferable_learning or "Pawns can never move backwards. Every pawn push creates squares that can't be defended by pawns anymore.",
            concept_id="premature_pawn",
            concept_type="positional",
            candidate_moves=candidate_moves
        )

    else:
        return ChessPlan(
            goal="Check what your opponent can do",
            current_problem=f"{played_san} has a problem — look at what your opponent can do next.",
            consequence=consequence,
            better_approach=better_approach or f"{best_move} was the better move here.",
            transferable_learning=transferable_learning or "Before every move, ask yourself: what can my opponent do after this? Check for captures, checks, and threats.",
            concept_id="generic_mistake",
            concept_type="general",
            candidate_moves=candidate_moves
        )


def _format_better_approach(candidates: List[Dict], best_move: Optional[str]) -> str:
    """
    Format the candidate moves into a readable "better approach" string.
    Shows the main idea, not just the move.
    """
    if not candidates:
        return f"{best_move} was better" if best_move else ""
    
    # Get the best move's idea
    best_candidate = candidates[0] if candidates else None
    if best_candidate:
        return best_candidate.get("idea", f"{best_move} was better")
    
    return f"{best_move} was better" if best_move else ""


def _derive_transferable_learning(
    candidates: List[Dict],
    piece_type: Optional[int],
    to_square: int
) -> str:
    """
    Derive a transferable learning from the candidate moves.
    This teaches the PATTERN, not just the move.
    """
    if not candidates:
        return ""
    
    # Analyze the types of good moves available
    move_types = [c.get("type", "") for c in candidates]
    
    # If there was a counter-attack available
    if "counter_attack" in move_types:
        return "When your opponent attacks, don't just defend. Look for your own threat that's even stronger."

    if "prophylactic" in move_types:
        return "Ask: what does my opponent want to do next? If you can stop their plan first, you take control."

    if "development" in move_types:
        return "Bring your pieces out to squares where they point at the center or at your opponent's weak spots."

    if "central" in move_types:
        return "Pieces in the center control more squares. A knight on e4 is much stronger than a knight on a3."

    if len(set(move_types)) >= 2:
        return "There were several good moves here. When you have choices, pick the one that improves your worst-placed piece."
    
    return ""


# ─── OPPONENT MOVE ANALYSIS ──────────────────────────────────────────

def analyze_opponent_move(
    board: chess.Board,
    move: chess.Move,
    eval_before: Optional[int],
    eval_after: Optional[int],
    pv_after: List[str],
    user_color: str,
    move_history_san: Optional[List[str]] = None,
    full_move_number: Optional[int] = None,
) -> Tuple[str, Optional[str], List[str]]:
    """
    Analyze opponent's move from USER's perspective with EDUCATIONAL depth.
    
    When opponent makes a mistake, we explain:
    1. WHAT they weakened (specific squares, diagonals, pieces)
    2. HOW to punish it (best move and why)
    3. THE PATTERN to remember
    
    Returns: (narrative, your_plan_now, highlight_squares)
    """
    board.san(move)
    
    # Calculate eval swing from user's perspective
    eval_swing = 0
    if eval_before is not None and eval_after is not None:
        if user_color == "white":
            eval_swing = eval_after - eval_before
        else:
            eval_swing = eval_before - eval_after
    
    highlight_squares = []
    your_plan_now = None
    
    # Simulate the position after opponent's move
    sim = board.copy()
    sim.push(move)
    user_is_white = (user_color == "white")
    
    # Get the best response from PV
    best_response = pv_after[0] if pv_after else None
    
    # Opponent made a significant mistake (100+ centipawns swing)
    if eval_swing >= 100:
        narrative, your_plan_now, highlight_squares = _analyze_opponent_mistake(
            board, move, sim, eval_swing, best_response, user_is_white, pv_after
        )
    
    # Opponent played a normal move
    elif abs(eval_swing) < 50:
        narrative, your_plan_now = _explain_opponent_move_with_context(
            board, move, user_color, pv_after,
            move_history_san=move_history_san,
            full_move_number=full_move_number,
        )
    
    # Small inaccuracy (50-100 cp)
    else:
        narrative, your_plan_now, highlight_squares = _analyze_opponent_slip(
            board, move, sim, eval_swing, best_response, user_is_white
        )
    
    return narrative, your_plan_now, highlight_squares


def _analyze_opponent_mistake(
    board_before: chess.Board,
    move: chess.Move,
    board_after: chess.Board,
    eval_swing: int,
    best_response: Optional[str],
    user_is_white: bool,
    pv_after: List[str]
) -> Tuple[str, str, List[str]]:
    """
    Deeply analyze opponent's mistake to create educational content.
    
    Looks for:
    - Weakened squares (especially around their king)
    - Hanging pieces
    - Tactical vulnerabilities (pins, forks, discoveries)
    - Pawn structure damage
    """
    move_san = board_before.san(move)
    highlight_squares = []
    
    # What type of mistake was this?
    piece_moved = board_before.piece_at(move.from_square)
    is_pawn_move = piece_moved and piece_moved.piece_type == chess.PAWN
    to_sq = move.to_square
    to_file = chess.square_file(to_sq)
    to_rank = chess.square_rank(to_sq)
    
    # ─── 1. CHECK FOR HANGING PIECES ───
    hanging_pieces = _find_hanging_pieces(board_after, not user_is_white)
    if hanging_pieces:
        piece_info = hanging_pieces[0]
        highlight_squares = [piece_info["square"]]
        
        if best_response:
            narrative = f"{move_san} leaves their {piece_info['name']} on {piece_info['square']} undefended! {best_response} wins it."
            your_plan_now = f"Capture the hanging {piece_info['name']} with {best_response}!"
        else:
            narrative = f"{move_san} leaves their {piece_info['name']} on {piece_info['square']} hanging!"
            your_plan_now = f"Take the free {piece_info['name']}!"
        
        return narrative, your_plan_now, highlight_squares
    
    # ─── 2. CHECK FOR WEAKENED KING POSITION ───
    opp_king_sq = board_after.king(not user_is_white)
    if opp_king_sq and is_pawn_move:
        king_file = chess.square_file(opp_king_sq)
        king_rank = chess.square_rank(opp_king_sq)
        
        # Did they weaken squares near their king?
        if abs(to_file - king_file) <= 2 and abs(to_rank - king_rank) <= 2:
            weakened = _find_weakened_squares_near_king(board_before, board_after, opp_king_sq, user_is_white)
            if weakened:
                highlight_squares = weakened[:3]
                sq_names = ", ".join(weakened[:2])
                
                if best_response:
                    # Try to explain what best_response does
                    response_explanation = _explain_response_idea(board_after, best_response, user_is_white, weakened)
                    narrative = f"{move_san} weakens the squares {sq_names} around their king. {response_explanation}"
                    your_plan_now = f"Target {sq_names} — their king's defenses are compromised!"
                else:
                    narrative = f"{move_san} creates holes on {sq_names}. Their king is exposed!"
                    your_plan_now = f"Attack the weak squares: {sq_names}"
                
                return narrative, your_plan_now, highlight_squares
    
    # ─── 3. CHECK FOR TACTICAL VULNERABILITIES ───
    # Look for pins, forks, discoveries that are now possible
    tactics = _find_tactical_opportunities(board_after, user_is_white)
    if tactics:
        tactic = tactics[0]
        highlight_squares = tactic.get("squares", [])
        
        if best_response:
            narrative = f"{move_san} allows {tactic['type']}! {best_response} {tactic['description']}"
        else:
            narrative = f"{move_san} allows a {tactic['type']}! {tactic['description']}"
        your_plan_now = tactic.get("plan", "Look for the tactic!")
        
        return narrative, your_plan_now, highlight_squares
    
    # ─── 4. CHECK FOR PIECE ACTIVITY LOSS ───
    if piece_moved:
        activity_issue = _check_piece_activity_loss(board_before, board_after, move, not user_is_white)
        if activity_issue:
            if best_response:
                narrative = f"{move_san} {activity_issue['problem']}. {best_response} takes advantage — {activity_issue['exploitation']}."
            else:
                narrative = f"{move_san} {activity_issue['problem']}."
            your_plan_now = activity_issue.get("plan", "Exploit their passive piece!")
            return narrative, your_plan_now, highlight_squares
    
    # ─── 5. FALLBACK: Explain based on best response ───
    if best_response:
        response_idea = _explain_response_idea(board_after, best_response, user_is_white, [])
        if response_idea and "Unknown" not in response_idea:
            narrative = f"{move_san} is a mistake. {response_idea}"
            your_plan_now = f"Play {best_response}!"
            return narrative, your_plan_now, highlight_squares
    
    # Last resort severity tier — don't translate centipawn swing
    # to a literal pawn count. Eval shift includes positional collapse
    # / king exposure / tempo, not just material (Mohit 2026-05-19).
    if eval_swing >= 400:
        narrative = f"{move_san} is a major mistake."
    elif eval_swing >= 250:
        narrative = f"{move_san} is a serious mistake."
    else:
        narrative = f"{move_san} is a mistake."
    your_plan_now = "Look for the best continuation."
    
    return narrative, your_plan_now, highlight_squares


def _analyze_opponent_slip(
    board_before: chess.Board,
    move: chess.Move,
    board_after: chess.Board,
    eval_swing: int,
    best_response: Optional[str],
    user_is_white: bool
) -> Tuple[str, str, List[str]]:
    """Analyze a small opponent inaccuracy (50-100 cp)."""
    move_san = board_before.san(move)
    highlight_squares = []
    
    if best_response:
        response_idea = _explain_response_idea(board_after, best_response, user_is_white, [])
        if response_idea and "Unknown" not in response_idea:
            narrative = f"{move_san} is slightly passive. {response_idea}"
            your_plan_now = f"{best_response} improves your position."
            return narrative, your_plan_now, highlight_squares
    
    pawn_swing = eval_swing / 100
    narrative = f"{move_san} gives you a small edge (+{pawn_swing:.1f})."
    your_plan_now = "You're slightly better — keep up the pressure!"
    
    return narrative, your_plan_now, highlight_squares


def _find_hanging_pieces(board: chess.Board, color: bool) -> List[Dict]:
    """Find pieces that are attacked but not defended."""
    hanging = []
    
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == color and piece.piece_type != chess.KING:
            attackers = list(board.attackers(not color, sq))
            defenders = list(board.attackers(color, sq))
            
            if attackers and not defenders:
                hanging.append({
                    "square": chess.square_name(sq),
                    "name": get_piece_name(piece),
                    "value": _piece_value(piece)
                })
    
    # Sort by value (most valuable first)
    hanging.sort(key=lambda x: x["value"], reverse=True)
    return hanging


def _find_weakened_squares_near_king(
    board_before: chess.Board,
    board_after: chess.Board,
    king_sq: int,
    user_is_white: bool
) -> List[str]:
    """Find squares near the king that became weaker after the move."""
    weakened = []
    king_file = chess.square_file(king_sq)
    king_rank = chess.square_rank(king_sq)
    
    # Check squares in the king's vicinity
    for df in [-1, 0, 1]:
        for dr in [-1, 0, 1]:
            if df == 0 and dr == 0:
                continue
            
            f = king_file + df
            r = king_rank + dr
            if 0 <= f <= 7 and 0 <= r <= 7:
                sq = chess.square(f, r)
                
                # Check if this square was defended before but not after
                defenders_before = len(list(board_before.attackers(not user_is_white, sq)))
                defenders_after = len(list(board_after.attackers(not user_is_white, sq)))
                
                # Also check if we can now attack it
                our_attackers = len(list(board_after.attackers(user_is_white, sq)))
                
                if defenders_after < defenders_before or (our_attackers > 0 and defenders_after == 0):
                    weakened.append(chess.square_name(sq))
    
    return weakened


def _find_tactical_opportunities(board: chess.Board, user_is_white: bool) -> List[Dict]:
    """Find tactical opportunities (forks, pins, etc.) in the position."""
    tactics = []
    
    # Check for knight fork opportunities
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == user_is_white and piece.piece_type == chess.KNIGHT:
            for target_sq in board.attacks(sq):
                target = board.piece_at(target_sq)
                if target and target.color != user_is_white:
                    # Check if moving the knight here creates a fork
                    for knight_move in board.legal_moves:
                        if knight_move.from_square == sq:
                            sim = board.copy()
                            sim.push(knight_move)
                            attacked = []
                            for attacked_sq in sim.attacks(knight_move.to_square):
                                attacked_piece = sim.piece_at(attacked_sq)
                                if attacked_piece and attacked_piece.color != user_is_white:
                                    if attacked_piece.piece_type in [chess.QUEEN, chess.ROOK, chess.KING]:
                                        attacked.append(attacked_piece)
                            
                            if len(attacked) >= 2:
                                tactics.append({
                                    "type": "knight fork",
                                    "squares": [chess.square_name(knight_move.to_square)],
                                    "description": "the knight forks two pieces.",
                                    "plan": f"Look for {board.san(knight_move)}."
                                })
                                return tactics
    
    return tactics


def _check_piece_activity_loss(
    board_before: chess.Board,
    board_after: chess.Board,
    move: chess.Move,
    piece_color: bool
) -> Optional[Dict]:
    """Check if the move made a piece less active."""
    piece = board_before.piece_at(move.from_square)
    if not piece:
        return None
    
    # Count controlled squares before and after
    attacks_before = len(list(board_before.attacks(move.from_square)))
    attacks_after = len(list(board_after.attacks(move.to_square)))
    
    if attacks_after < attacks_before - 2:
        piece_name = get_piece_name(piece)
        return {
            "problem": f"puts their {piece_name} on a passive square",
            "exploitation": "your pieces have more freedom now",
            "plan": "Take the center. Their piece can't stop you from there."
        }
    
    # Check if piece is now blocked
    if piece.piece_type == chess.BISHOP:
        # Check if bishop's diagonals are blocked by own pawns
        blocked_by_pawns = 0
        for diag_sq in board_after.attacks(move.to_square):
            blocker = board_after.piece_at(diag_sq)
            if blocker and blocker.color == piece_color and blocker.piece_type == chess.PAWN:
                blocked_by_pawns += 1
        
        if blocked_by_pawns >= 2:
            return {
                "problem": "blocks their own bishop behind pawns",
                "exploitation": "their bishop is buried — does nothing",
                "plan": "Your pieces are more active. Press your advantage."
            }
    
    return None


def _explain_response_idea(
    board: chess.Board,
    response_san: str,
    user_is_white: bool,
    weak_squares: List[str]
) -> str:
    """
    Explain what the best response achieves - EDUCATIONAL version.
    
    Goes beyond just naming the move - explains the IDEA.
    """
    try:
        move = board.parse_san(response_san)
    except:
        return f"Unknown response."
    
    piece = board.piece_at(move.from_square)
    if not piece:
        return f"Unknown response."
    
    sim = board.copy()
    is_capture = board.is_capture(move)
    sim.push(move)
    
    get_piece_name(piece)
    to_sq = move.to_square
    to_file = chess.square_file(to_sq)
    to_rank = chess.square_rank(to_sq)
    
    # ─── PAWN MOVES - Often the most instructive ───
    if piece.piece_type == chess.PAWN:
        # Pawn break - check if this pawn attacks enemy pawns/pieces
        attacked_by_pawn = list(sim.attacks(to_sq))
        enemy_pieces_attacked = [sq for sq in attacked_by_pawn 
                                  if sim.piece_at(sq) and sim.piece_at(sq).color != user_is_white]
        
        # Central pawn break (d5, e5, d4, e4 type moves)
        if to_sq in [chess.D5, chess.E5, chess.D4, chess.E4, chess.E6, chess.D6]:
            chess.square_name(to_sq)
            # Check what it opens
            if sim.is_check():
                return f"{response_san} breaks through with check! The center is torn open."
            
            # Check if it attacks pieces
            for attacked_sq in attacked_by_pawn:
                attacked = sim.piece_at(attacked_sq)
                if attacked and attacked.color != user_is_white and attacked.piece_type != chess.PAWN:
                    return f"{response_san} breaks in the center, attacking their {get_piece_name(attacked)}! This blows open the position."
            
            return f"{response_san} is a powerful pawn break! It opens lines and creates threats. h6 weakened this possibility."
        
        # Attacking pawn — detect forks (2+ non-pawn pieces attacked
        # simultaneously). Source bug: fb_c45f3552e4d9 said "f6 attacks
        # their knight" when f6 actually forked bishop + knight.
        if enemy_pieces_attacked:
            non_pawn_targets = [
                sq for sq in enemy_pieces_attacked
                if sim.piece_at(sq) and sim.piece_at(sq).piece_type != chess.PAWN
            ]
            if len(non_pawn_targets) >= 2:
                names = sorted({
                    get_piece_name(sim.piece_at(sq)) for sq in non_pawn_targets
                })
                if len(names) >= 2:
                    return (
                        f"{response_san} forks the {names[0]} and {names[1]} — "
                        f"double attack, you win material."
                    )
                # Two pieces of the same type forked (e.g., two knights)
                return (
                    f"{response_san} forks two {names[0]}s — "
                    f"double attack, you win material."
                )
            attacked = sim.piece_at(enemy_pieces_attacked[0])
            if attacked:
                return f"{response_san} attacks their {get_piece_name(attacked)}."
        
        # Passed pawn creation
        # Check if there are no enemy pawns in front
        is_passed = True
        for r in range(to_rank + 1, 8) if user_is_white else range(0, to_rank):
            for f in [to_file - 1, to_file, to_file + 1]:
                if 0 <= f <= 7:
                    sq = chess.square(f, r)
                    p = sim.piece_at(sq)
                    if p and p.piece_type == chess.PAWN and p.color != user_is_white:
                        is_passed = False
                        break
        
        if is_passed:
            return f"{response_san} creates a dangerous passed pawn!"
    
    # ─── CAPTURES ───
    if is_capture:
        captured = board.piece_at(to_sq)
        if captured:
            captured_name = get_piece_name(captured)
            attacker_value = _piece_value(piece)
            captured_value = _piece_value(captured)
            
            if captured_value > attacker_value:
                return f"{response_san} wins the {captured_name}! Free material."
            elif captured_value == attacker_value:
                # Check if recapture is problematic
                defenders = list(sim.attackers(not user_is_white, to_sq))
                if not defenders:
                    return f"{response_san} takes the {captured_name} for free — no recapture!"
                return f"{response_san} trades off the {captured_name}."
            else:
                return f"{response_san} wins the {captured_name}."
    
    # ─── CHECKS ───
    if sim.is_check():
        # Analyze what kind of check
        # Is it a discovered check?
        if piece.piece_type not in [chess.QUEEN, chess.ROOK, chess.BISHOP]:
            # The checking piece might be different
            opp_king = sim.king(not user_is_white)
            checkers = list(sim.attackers(user_is_white, opp_king))
            for checker_sq in checkers:
                checker = sim.piece_at(checker_sq)
                if checker and checker_sq != to_sq:
                    return f"{response_san} unleashes a discovered check! Devastating."
        
        return f"{response_san} gives check, forcing their king to move."
    
    # ─── ATTACKS ON VALUABLE PIECES (with fork detection) ───
    # Collect every enemy non-pawn piece this move attacks. If 2+, name
    # the fork explicitly. If 1, fall back to the single-target template.
    enemy_targets = []
    for attacked_sq in sim.attacks(to_sq):
        attacked = sim.piece_at(attacked_sq)
        if attacked and attacked.color != user_is_white and attacked.piece_type != chess.PAWN:
            enemy_targets.append(attacked)
    if len(enemy_targets) >= 2:
        names = sorted({get_piece_name(p) for p in enemy_targets})
        if len(names) >= 2:
            return (
                f"{response_san} forks the {names[0]} and {names[1]} — "
                f"double attack, you win material."
            )
        return (
            f"{response_san} forks two {names[0]}s — "
            f"double attack, you win material."
        )
    if len(enemy_targets) == 1:
        attacked = enemy_targets[0]
        if attacked.piece_type == chess.QUEEN:
            return f"{response_san} attacks their Queen!"
        if attacked.piece_type == chess.ROOK:
            return f"{response_san} attacks their Rook."
    
    # ─── KNIGHT MOVES ───
    if piece.piece_type == chess.KNIGHT:
        if to_sq in [chess.D5, chess.E5, chess.D4, chess.E4]:
            return f"{response_san} plants the knight powerfully in the center — hard to kick out!"
        
        # Outpost?
        # Check if the square can be attacked by enemy pawns
        can_be_attacked = False
        for f in [to_file - 1, to_file + 1]:
            if 0 <= f <= 7:
                for r in range(8):
                    sq = chess.square(f, r)
                    p = board.piece_at(sq)
                    if p and p.piece_type == chess.PAWN and p.color != user_is_white:
                        # Could this pawn ever attack our square?
                        if (user_is_white and r < to_rank) or (not user_is_white and r > to_rank):
                            can_be_attacked = True
                            break
        
        if not can_be_attacked:
            return f"{response_san} establishes a permanent outpost — no pawns can challenge it!"
    
    # ─── BISHOP MOVES ───
    if piece.piece_type == chess.BISHOP:
        # Long diagonal?
        diag_length = len(list(sim.attacks(to_sq)))
        if diag_length >= 7:
            return f"{response_san} activates the bishop on a long diagonal."
    
    # ─── ROOK MOVES ───
    if piece.piece_type == chess.ROOK:
        # Open file?
        pawns_on_file = sum(1 for r in range(8) 
                           if board.piece_at(chess.square(to_file, r)) 
                           and board.piece_at(chess.square(to_file, r)).piece_type == chess.PAWN)
        if pawns_on_file == 0:
            return f"{response_san} seizes the open file — Rooks love open files!"
        
        # Seventh rank?
        if (user_is_white and to_rank == 6) or (not user_is_white and to_rank == 1):
            return f"{response_san} invades the seventh rank — threatens their pawns and cramps their king!"
    
    # ─── QUEEN MOVES ───
    if piece.piece_type == chess.QUEEN:
        # Check what it attacks
        attacked = list(sim.attacks(to_sq))
        valuable_targets = [sq for sq in attacked 
                           if sim.piece_at(sq) and sim.piece_at(sq).color != user_is_white 
                           and sim.piece_at(sq).piece_type in [chess.ROOK, chess.KNIGHT, chess.BISHOP]]
        if len(valuable_targets) >= 2:
            return f"{response_san} creates multiple threats — their position is crumbling!"
    
    # ─── LANDING ON WEAK SQUARES ───
    to_sq_name = chess.square_name(to_sq)
    if to_sq_name in weak_squares:
        return f"{response_san} exploits the weak {to_sq_name} square that they created."
    
    # ─── FALLBACK ───
    return f"{response_san} improves your position."


def _explain_opponent_move_with_context(
    board: chess.Board,
    move: chess.Move,
    user_color: str,
    pv_after: List[str],
    move_history_san: Optional[List[str]] = None,
    full_move_number: Optional[int] = None,
) -> Tuple[str, str]:
    """
    Explain opponent's move.

    First-pass: if the move is in known opening theory, prefer theory
    over invented "fun" copy. e5 in response to e4 should say
    "Open Game / King's Pawn Opening — symmetric center control. Leads
    to tactical play.", not "Pawn advances. They want the center! Don't
    let them have all the space. Push back!".

    Falls through to the legacy fun-text branches when theory has
    nothing to say.
    """
    move_san = board.san(move)
    piece = board.piece_at(move.from_square)

    sim = board.copy()
    sim.push(move)

    # ── Opening-theory first-pass ──
    # When move_history is available and we're in the opening phase,
    # use the opening detector to emit theory-grounded captions instead
    # of hardcoded "fun" text. Source bugs: fb_d0454a4088f3 / fb_e093213e873f
    # / fb_a12c4f9d39ed (opening moves got "Pawn advances to e5. They
    # want the center! Don't let them have all the space. Push back!"
    # instead of "King's Pawn Opening — Open game, both sides fight for
    # the center.").
    #
    # Try get_opening_theory_note first (curriculum-grade content for
    # named lines like the Queen's Gambit, Sicilian variations, etc.).
    # Fall back to detect_opening_from_moves (broader coverage including
    # bare e4/d4/c4/Nf3 + first responses) when curriculum has no entry.
    if move_history_san and full_move_number and full_move_number <= 12:
        try:
            from services.opening_theory_note import get_opening_theory_note
            note = get_opening_theory_note(
                move_history=move_history_san,
                move_number=full_move_number,
            )
            if note:
                opening_name = note.get("opening_name") or ""
                summary = (note.get("summary") or "").strip()
                key_rule = (note.get("key_rule") or "").strip()
                if opening_name and summary:
                    return (
                        f"{opening_name}: {summary}",
                        key_rule or f"Stay with the {opening_name.lower()} plan.",
                    )
        except Exception as exc:
            logger.debug(f"opening_theory_note failed (non-fatal): {exc}")

        # Detector fallback — covers the common "no curriculum entry"
        # case (e4-e5, d4-d5, e4-c5, etc.). Returns name + description
        # + introduction which are enough to teach with.
        try:
            from services.opening_mastery import detect_opening_from_moves
            info = detect_opening_from_moves(move_history_san)
            if info:
                opening_name = info.get("opening_name") or ""
                description = (info.get("description") or "").strip()
                introduction = (info.get("introduction") or "").strip()
                if opening_name and description:
                    # Description sometimes has " / " separating white
                    # vs black ideas — take the first half (more
                    # universally framed) for the narrative.
                    desc_short = description.split(" / ")[0].strip().rstrip(".")
                    return (
                        f"{opening_name} — {desc_short}.",
                        introduction.rstrip("!") + ("!" if introduction.endswith("!") else ".") if introduction else f"Stay with the {opening_name.lower()} plan.",
                    )
        except Exception as exc:
            logger.debug(f"detect_opening_from_moves failed (non-fatal): {exc}")

    # Check what this move threatens
    threats = []

    # 1. Does it create a direct threat?
    for sq, p in sim.piece_map().items():
        if p.color == (user_color == "white"):  # User's pieces
            attackers = sim.attackers(not (user_color == "white"), sq)
            defenders = sim.attackers(user_color == "white", sq)
            if len(attackers) > len(defenders):
                piece_name = _get_fun_piece_name(p)
                threats.append(f"eyeing your {piece_name} on {chess.square_name(sq)}")
    
    # 2. Is this a capture?
    if board.is_capture(move):
        captured = board.piece_at(move.to_square)
        if captured:
            captured_name = _get_fun_piece_name(captured)
            return (
                f"Chomp! They took your {captured_name}.",
                "Recapture? Check if it's worth it first!"
            )
    
    # 3. Is this castling?
    if board.is_castling(move):
        return (
            "They castled! Their King is tucked away safely now.",
            "Time to make a plan. Where's their weakness?"
        )
    
    # 4. Check for piece-specific ideas with FUN names
    if piece:
        if piece.piece_type == chess.PAWN:
            to_file = chess.square_file(move.to_square)
            if to_file in [3, 4]:  # d or e file
                return (
                    f"Pawn advances to {move_san}. They want the center!",
                    "Don't let them have all the space. Push back!"
                )
            return (
                f"Pawn to {move_san}. What's the plan behind it?",
                "Every pawn move creates a weakness. Where is it?"
            )
        
        elif piece.piece_type == chess.KNIGHT:
            to_sq = move.to_square
            if to_sq in [chess.C3, chess.F3, chess.C6, chess.F6]:
                return (
                    f"Their horsey hops to {move_san}. Classic development!",
                    "Keep developing. Don't fall behind!"
                )
            if to_sq in [chess.D5, chess.E5, chess.D4, chess.E4]:
                return (
                    f"Whoa! Their knight lands in the center with {move_san}. Strong!",
                    "Can you kick it out? Challenge that knight!"
                )
            return (
                f"Knight to {move_san}. Where's it heading?",
                "Watch where that horsey wants to jump next!"
            )
        
        elif piece.piece_type == chess.BISHOP:
            return (
                f"Bishop slides to {move_san}. Bishops love open diagonals!",
                "Make sure your pieces aren't on that diagonal!"
            )
        
        elif piece.piece_type == chess.ROOK:
            to_file = chess.square_file(move.to_square)
            file_pawns = len([sq for sq in chess.SQUARES if chess.square_file(sq) == to_file and board.piece_at(sq) and board.piece_at(sq).piece_type == chess.PAWN])
            if file_pawns == 0:
                return (
                    f"Tower Power! Their rook hits the open file with {move_san}.",
                    "Open files are dangerous. Contest it or block it!"
                )
            return (
                f"Rook moves to {move_san}.",
                "Rooks want open files. Don't give them one!"
            )
        
        elif piece.piece_type == chess.QUEEN:
            return (
                f"Her Majesty enters with {move_san}. Respect the Queen!",
                "The Queen is powerful but attackable. Can you harass her?"
            )
    
    # 5. If there's a threat, warn about it
    if threats:
        return (
            f"Watch out! {move_san} is {threats[0]}.",
            "Deal with this threat first, then continue your plan."
        )
    
    # 6. Fallback - but still useful
    return (
        f"They played {move_san}.",
        "Keep developing! Castle if you haven't."
    )


def _get_fun_piece_name(piece: chess.Piece) -> str:
    """Get clear piece names."""
    names = {
        chess.PAWN: "pawn",
        chess.KNIGHT: "knight",
        chess.BISHOP: "bishop",
        chess.ROOK: "rook",
        chess.QUEEN: "queen",
        chess.KING: "king"
    }
    return names.get(piece.piece_type, "piece")


# ─── GOOD MOVE RECOGNITION ───────────────────────────────────────────

def recognize_good_move(
    board: chess.Board,
    move: chess.Move,
    best_move: Optional[str],
    cp_loss: int,
    phase: str,
    opening_data: dict,
    pv_after_best: List[str] = None,
    eval_before: float = None,
    eval_after: float = None
) -> Tuple[str, Optional[str], bool]:
    """
    Recognize when user plays a good move - use FUN, MEMORABLE language!
    Returns: (narrative, concept_applied, is_best_move)
    
    NOW HANDLES: Critical situations like mate threats!
    """
    move_san = board.san(move)
    is_best = best_move and move_san.lower().replace("+", "").replace("#", "") == best_move.lower().replace("+", "").replace("#", "")
    
    piece = board.piece_at(move.from_square)
    
    concept_applied = None
    narrative = ""
    
    # ─── CRITICAL: Handle mate situations FIRST ───
    # Mate detected when eval_after is very high (±9000+) indicating forced mate
    # Or when there's a big eval swing indicating critical position
    
    board_after = board.copy()
    board_after.push(move)
    
    # Check if WE just gave checkmate
    if board_after.is_checkmate():
        return f"Checkmate. {move_san} ends the game.", "checkmate_delivery", True

    # ── Checks (non-mating) ──
    # Don't let development templates fire on a check. "Bc4+. Bishop on
    # an active diagonal." is wrong on so many levels — the news is the
    # check, not the bishop's diagonal. Route to a check-specific
    # template that names what the check forks/attacks if anything.
    if board_after.is_check():
        opp_color = not board_after.turn  # we just moved → opp's turn
        # What else does the moving piece attack besides the king?
        extras = []
        if move.to_square is not None:
            for sq in board_after.attacks(move.to_square):
                p = board_after.piece_at(sq)
                if (p and p.color == board_after.turn  # opp pieces (current turn = opp)
                        and p.piece_type != chess.KING
                        and p.piece_type != chess.PAWN):
                    extras.append(get_piece_name(p))
        if extras:
            # Check + extra attack = mini fork
            extra = extras[0]
            return (
                f"{move_san} — check, and attacks the {extra} too.",
                "double_attack_check",
                is_best,
            )
        return (
            f"{move_san} — check. Their king has to move or block.",
            "check_given",
            is_best,
        )

    # Check for mate threats (eval indicates forced mate - values near ±10000)
    if eval_after is not None:
        # We're getting mated (eval around -9000 to -10000 for mate scores)
        if eval_after <= -5000:  # Forced mate against us
            if is_best:
                return f"{move_san} — the only move. You're facing a forced mate; this puts up the best fight.", "defensive_critical", True
            else:
                return f"{move_san} delays it, but mate is coming. The position was already lost.", "defensive_critical", False

        # We're winning with mate (eval around +9000 to +10000)
        if eval_after >= 5000:
            if is_best:
                return f"{move_san} keeps the winning attack going. Mate is close.", "winning_attack", True
            else:
                return f"{move_san}. You're winning — keep playing accurate moves to close it out.", "winning_attack", False

        # Check if eval dropped significantly (position collapsed from okay to lost)
        if eval_before is not None:
            # Went from reasonable to getting mated
            if eval_before > -1000 and eval_after <= -5000:
                if is_best:
                    return f"{move_san} — the best option in a lost position. The damage was done earlier.", "best_in_lost", True
                else:
                    return f"{move_san} — but the position collapsed. This was the critical moment.", "desperate_defense", False

            # Went from reasonable to significantly worse (but not mate)
            if eval_before > -200 and eval_after <= -500:
                if is_best:
                    return f"{move_san} — best in a difficult position. You're under pressure.", "best_under_pressure", True
                else:
                    return f"{move_san} — things are tough here. Time to slow down.", "under_pressure", False

    # ─── Check if this matches opening theory ───
    typical_ideas = opening_data.get("typical_ideas", {})
    if move_san in typical_ideas:
        concept_applied = f"opening_{move_san.lower()}"
        narrative = f"{move_san}. {typical_ideas[move_san]}"
        return narrative, concept_applied, is_best

    # Castling
    if board.is_castling(move):
        concept_applied = "king_safety_castling"
        move_num = len(list(board.move_stack)) // 2 + 1
        if move_num <= 10:
            narrative = "Castled. King's in the corner, rook joins the game."
        else:
            narrative = "Castled. Should have come sooner — but the king is safe now."
        return narrative, concept_applied, is_best

    # Development by piece type
    if piece:
        back_rank = 0 if piece.color == chess.WHITE else 7

        if piece.piece_type == chess.KNIGHT:
            to_sq = move.to_square
            if to_sq in [chess.F3, chess.C3, chess.F6, chess.C6]:
                concept_applied = "knight_development"
                narrative = f"{move_san}. Knights are strongest on f3/c3 — they control the center from here."
                if is_best:
                    narrative = f"{move_san}. The right square for the knight here."
                return narrative, concept_applied, is_best
            elif to_sq in [chess.E5, chess.D5, chess.E4, chess.D4]:
                concept_applied = "central_knight"
                narrative = f"{move_san}. Knight in the center, hard to kick out."
                return narrative, concept_applied, is_best

        elif piece.piece_type == chess.BISHOP:
            if chess.square_rank(move.from_square) == back_rank:
                concept_applied = "bishop_development"
                to_sq = move.to_square
                to_file = chess.square_file(to_sq)
                if to_file in [1, 2, 5, 6]:  # b, c, f, g files - active squares
                    narrative = f"{move_san}. Bishop on an active diagonal."
                else:
                    narrative = f"{move_san}. Bishop out — open diagonal ahead."
                return narrative, concept_applied, is_best

        elif piece.piece_type == chess.PAWN:
            to_file = chess.square_file(move.to_square)
            if to_file in [3, 4]:  # d or e file
                to_rank = chess.square_rank(move.to_square)
                if (piece.color == chess.WHITE and to_rank == 3) or (piece.color == chess.BLACK and to_rank == 4):
                    concept_applied = "center_control"
                    narrative = f"{move_san}. Grabs space in the center."
                    return narrative, concept_applied, is_best

        elif piece.piece_type == chess.ROOK:
            to_file = chess.square_file(move.to_square)
            file_pawns = len([sq for sq in chess.SQUARES if chess.square_file(sq) == to_file and board.piece_at(sq) and board.piece_at(sq).piece_type == chess.PAWN])
            if file_pawns == 0:
                concept_applied = "rook_on_open_file"
                narrative = f"{move_san}. Rook on an open file — controls the whole column."
                return narrative, concept_applied, is_best

    # Capture that wins material
    if board.is_capture(move):
        captured = board.piece_at(move.to_square)
        if captured:
            attacker_value = _piece_value(piece)
            captured_value = _piece_value(captured)
            if captured_value > attacker_value:
                concept_applied = "winning_material"
                narrative = f"{move_san} wins material — straight gain."
                return narrative, concept_applied, is_best

    # Generic best move
    if is_best:
        sim = board.copy()
        sim.push(move)

        for sq, p in sim.piece_map().items():
            if p.color != piece.color:
                attackers = sim.attackers(piece.color, sq)
                if attackers:
                    narrative = f"{move_san}. Creates a new threat — they have to respond."
                    return narrative, "found_best_move", True

        narrative = f"{move_san}. Best move here."
        return narrative, "found_best_move", True

    if cp_loss < 10:
        return f"{move_san}. Solid.", None, False

    return f"{move_san}.", None, False


def _piece_value(piece: chess.Piece) -> int:
    """Get approximate piece value."""
    values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
    return values.get(piece.piece_type, 0)


# ─── NARRATIVE GENERATION ────────────────────────────────────────────

def generate_simple_narrative(
    plan: ChessPlan,
    move_san: str,
    best_move: Optional[str],
    cp_loss: int,
    already_acknowledged: bool
) -> str:
    """
    Generate a simple, 1200-friendly narrative.
    
    If user already acknowledged this concept, keep it brief.
    If not, include the learning.
    """
    if already_acknowledged:
        # Brief reminder
        if plan.concept_type == "opening":
            return f"{move_san} — you know this position. {best_move} was better."
        return f"{move_san} loses something. You've seen this pattern before."
    
    # Full explanation for new concepts
    parts = []
    
    # Start with what they tried to do (acknowledge intent)
    parts.append(f"You played {move_san}.")
    
    # The problem (simple)
    if plan.current_problem:
        parts.append(plan.current_problem)
    
    # The consequence (show the future)
    if plan.consequence:
        parts.append(plan.consequence)
    
    # The better approach
    if plan.better_approach:
        parts.append(plan.better_approach)
    
    return " ".join(parts)


# ─── MAIN ORCHESTRATOR ───────────────────────────────────────────────

async def _get_adaptive_config(db, user_id: str) -> Dict:
    """
    Get adaptive decryption config based on player rating + known weaknesses.
    
    Philosophy:
    - 1100 player: Only blunders/mistakes. Inaccuracies are noise.
    - 1400 player: Blunders/mistakes + inaccuracies that match known weaknesses.
    - 1700+ player: Everything.
    - If a known weakness reappears: ALWAYS explain, even at low cp_loss.
    """
    config = {
        "rating": 1200,
        "min_cp_explain": 100,   # Only explain moves with cp_loss >= this
        "min_cp_detail": 200,    # Only show detailed plans for moves >= this
        "known_weaknesses": set(),  # concept_ids / pattern types to always explain
        "weakness_patterns": {},    # pattern_type -> count (for emphasis)
    }

    if db is None:
        return config

    try:
        # Get player rating from profile
        profile = await db.player_profiles.find_one(
            {"user_id": user_id},
            {"_id": 0, "estimated_elo": 1, "current_rating": 1}
        )
        if profile:
            config["rating"] = profile.get("estimated_elo") or profile.get("current_rating") or 1200

        # Get known weaknesses from player identity
        identity = await db.player_identities.find_one(
            {"user_id": user_id},
            {"_id": 0, "blunder_taxonomy": 1, "priority_focus": 1, "learning_velocity": 1}
        )
        if identity:
            taxonomy = identity.get("blunder_taxonomy", {})
            by_type = taxonomy.get("by_type", {})
            # Top 3 most frequent weakness patterns
            sorted_types = sorted(by_type.items(), key=lambda x: x[1], reverse=True)
            for ptype, count in sorted_types[:3]:
                config["known_weaknesses"].add(ptype)
                config["weakness_patterns"][ptype] = count

            priority = identity.get("priority_focus")
            if priority:
                config["known_weaknesses"].add(priority)

            # Also add worsening areas
            velocity = identity.get("learning_velocity", {})
            for area in velocity.get("worsening_areas", []):
                config["known_weaknesses"].add(area)

        # Adaptive thresholds based on rating
        rating = config["rating"]
        if rating < 1200:
            config["min_cp_explain"] = 100   # Only mistakes & blunders
            config["min_cp_detail"] = 150
        elif rating < 1400:
            config["min_cp_explain"] = 70    # Include bigger inaccuracies
            config["min_cp_detail"] = 120
        elif rating < 1600:
            config["min_cp_explain"] = 50    # Include most inaccuracies
            config["min_cp_detail"] = 80
        else:
            config["min_cp_explain"] = 30    # Full detail (current behavior)
            config["min_cp_detail"] = 50

        logger.info(f"[ADAPTIVE] Rating={rating}, min_explain={config['min_cp_explain']}, weaknesses={config['known_weaknesses']}")

    except Exception as e:
        logger.warning(f"Could not load adaptive config: {e}")

    return config


def _get_move_priority(
    severity: str,
    cp_loss: int,
    plan: object,
    config: Dict,
    is_user: bool,
) -> str:
    """
    Determine decryption priority for a move.
    Returns: "essential" | "weakness_match" | "growth" | "silent"
    
    essential: Always show (blunders, mistakes, opponent blunders)
    weakness_match: Matches a known weakness — show with emphasis
    growth: Inaccuracy worth explaining at this level
    silent: Skip detailed explanation
    """
    if not is_user:
        # Opponent moves: show blunders/mistakes, skip the rest
        if severity in ("opp_blunder", "opp_mistake"):
            return "essential"
        return "context"

    if severity in ("blunder",):
        return "essential"
    if severity in ("mistake",):
        return "essential"

    # Check if this move matches a known weakness pattern
    if plan and hasattr(plan, 'concept_id') and plan.concept_id:
        concept = plan.concept_id.lower()
        for weakness in config.get("known_weaknesses", set()):
            if weakness.lower() in concept or concept in weakness.lower():
                return "weakness_match"

    # Inaccuracies: only explain if cp_loss meets the adaptive threshold
    if severity == "inaccuracy":
        if cp_loss >= config.get("min_cp_explain", 100):
            return "growth"
        return "silent"

    # Good moves
    return "silent"


async def generate_game_decryption_v5(
    pgn: str,
    user_color: str,
    move_evaluations: List[Dict],
    user_id: str,
    db,  # MongoDB database reference
    game_id: Optional[str] = None,
) -> List[Dict]:
    """
    Generate V5 "Thinking Simulator" coaching for a game.
    
    Key differences from V4:
    1. Coaches EVERY move (not just mistakes)
    2. Extracts PLANS (not just moves)
    3. Tracks concept acknowledgment
    4. Simple, 1200-friendly language
    """
    try:
        # Parse game
        game = chess.pgn.read_game(io.StringIO(pgn))
        if not game:
            logger.error("Could not parse PGN")
            return []
        
        moves = list(game.mainline_moves())
        
        # Detect opening
        opening_name, eco_code = detect_opening_from_pgn(pgn)
        opening_data = get_opening_data(eco_code, opening_name)
        logger.info(f"[DECRYPTION V5] Opening: {opening_name or 'Unknown'} ({eco_code or 'N/A'})")

        # v69 (2026-05-22): scan the PGN for traps so we can surface the
        # trap NAME in captions when the user missed a punishment
        # (role="setter" in scanner terminology — user is the punisher
        # who failed to land the trap_line). Mohit caught the gap on
        # game fc97ee1d (Damiano Defense missed by white on m3, still
        # the engine's plan on m7).
        try:
            from services.trap_scanner import scan_pgn_for_traps
            game_trap_fires = scan_pgn_for_traps(pgn, user_color)
        except Exception as _trap_scan_exc:
            logger.info(f"[trap_scan] failed: {_trap_scan_exc}")
            game_trap_fires = []
        
        # Build eval lookup by FEN
        eval_lookup = {}
        for eval_data in move_evaluations:
            fen = eval_data.get("fen_before", "")
            if fen:
                fen_key = " ".join(fen.split()[:4])
                eval_lookup[fen_key] = eval_data
        
        # Get user's acknowledged concepts
        acknowledged_concepts = set()
        if db is not None:
            try:
                cursor = db.user_concept_understanding.find(
                    {"user_id": user_id, "acknowledged": True},
                    {"concept_id": 1}
                )
                async for doc in cursor:
                    acknowledged_concepts.add(doc.get("concept_id"))
            except Exception as e:
                logger.warning(f"Could not fetch acknowledged concepts: {e}")
        
        # Get adaptive config (rating-based filtering + known weaknesses)
        adaptive = await _get_adaptive_config(db, user_id)
        
        # Process each move
        decryption_data = []
        board = chess.Board()
        prev_move = None
        # v72 (2026-05-23) — P2 detector memory. Buffer pattern-miss
        # events as user mistakes get captioned; flush in bulk to the
        # user_pattern_events collection at the end of the game so the
        # whole batch is one DB call. Build-events function is pure;
        # the DB write is gated on db != None AND a non-empty user_id.
        pattern_miss_events: List[Dict] = []
        prev_user_eval_after = None  # Track eval after user's last move

        # ── Teaching-layer suppression state ──────────────────────────
        # Catalog declares per-principle suppression semantics:
        #   once_per_move        — default; no game-state filter
        #   once_per_state_entry — fire on transitions from "not firing
        #                          last move" to "firing this move"
        #   once_per_game        — fire only the FIRST time per game
        # Detectors are pure (no game-state); filtering happens here.
        # Without this, state-persistent principles like END_KING_ACTIVE
        # spammed 34k times across the audit corpus (first audit pass
        # surfaced the gap).
        principles_fired_this_game: set = set()
        principles_fired_last_move: set = set()
        # State-keyed suppression set (Phase 0.5, 2026-05-18):
        # tracks (principle_id, state_key) tuples so the same principle
        # CAN fire again when board state meaningfully changes (different
        # focal squares, different king pair, different best-move family).
        # See project_suppression_key_overhaul.md for the design.
        state_keys_fired_this_game: set = set()
        # TIER 3 shape-pattern suppression — same convention as principles:
        # each pattern fires at most once per game, so the cue stays a
        # memorable marker instead of a repeated label.
        shapes_fired_this_game: set = set()
        # v78 (2026-05-23) — board_state_describer suppression. Same
        # bs_* fact firing on consecutive moves is spammy ("rook on f8
        # has only 1 legal move" on m11, m12, m17, m18 in a row).
        # Window=1 (default in central layer's
        # inject_board_state_describer_clause) suppresses immediately-
        # consecutive repeats. The list is owned by V5 (per-game) and
        # passed to the central call each move; the helper appends new
        # fact_ids and trims to bs_window_size.
        _bs_recent_window: List[set] = []

        # Trap + opening recognition state (walked statefully across the game).
        # `played_san_so_far` accumulates SAN of every move played; trap and
        # opening lookup compare against this sequence each move.
        played_san_so_far: List[str] = []
        active_trap: Optional[Dict[str, Any]] = None
        active_trap_setup_completed_by_user: Optional[bool] = None
        active_trap_step_cursor: int = 0

        for idx, move in enumerate(moves):
            # Defensive: a small share of corpus games have PGN ↔
            # move_evaluations drift where the next mainline move
            # isn't legal in the replayed board state. Skip the
            # offending move rather than aborting the entire game.
            try:
                move_san = board.san(move)
            except (AssertionError, ValueError, chess.IllegalMoveError) as _drift_exc:
                logger.warning(
                    f"[V5] PGN-replay drift at idx={idx} ({move.uci()}): "
                    f"{_drift_exc}. Skipping this move; remainder of game "
                    f"continues."
                )
                continue
            full_move_number = (idx // 2) + 1
            is_white = (idx % 2 == 0)
            is_user = (user_color == "white" and is_white) or (user_color == "black" and not is_white)

            # v70 (2026-05-23): "Play this line" support. Initialize the
            # per-iteration coach-line state here so it's defined even
            # when no detector populates it; the move_output assembly
            # below reads these unconditionally.
            _trap_steps_for_iter: Optional[List[Dict]] = None
            _coach_line_length_hint_for_iter: Optional[int] = None
            # v78.4 (2026-05-24) — Mohit: "Play this line" should also
            # fire on opp mistakes/blunders. For opp moves we can't
            # rely on pv_after_best (empty for opp positions) so we
            # build the line explicitly: [opp's played move, user's
            # best reply, opp's followup, user's continuation]. That
            # tells the full coaching story — "watch what they did,
            # then watch how you should have punished it."
            _coach_line_moves_for_iter: Optional[List[str]] = None

            # Get eval data - for user moves, from current position; for opponent, we'll use next position
            fen_key = " ".join(board.fen().split()[:4])
            eval_data = eval_lookup.get(fen_key, {})
            cp_loss = abs(eval_data.get("cp_loss", 0)) if is_user else 0

            # Mate-sentinel cp_loss capture — when the engine returns a
            # mate-loss as eval_after, cp_loss may be absent/0 in the
            # stored eval_data even though the move walked into mate.
            # Recompute cp_loss from eval_before + eval_after when those
            # are available and the stored cp_loss looks suspicious.
            # Source bug: fb_a9ac9f02affa (Rxc3 = "Equal trade" caught by
            # Phase 2 audit at +381cp swing; underlying severity was tagged
            # "good" because the stored cp_loss didn't reflect the swing).
            if is_user:
                eval_before_v = eval_data.get("eval_before")
                eval_after_v = eval_data.get("eval_after")
                if eval_before_v is not None and eval_after_v is not None:
                    user_eval_before = eval_before_v if user_color == "white" else -eval_before_v
                    user_eval_after = eval_after_v if user_color == "white" else -eval_after_v
                    derived_loss = max(0, user_eval_before - user_eval_after)
                    cp_loss = max(cp_loss, derived_loss)
            
            # For opponent moves, calculate eval swing using:
            # - eval BEFORE opponent move = eval AFTER user's last move (prev_user_eval_after)
            # - eval AFTER opponent move = eval BEFORE user's next move (look ahead)
            opp_eval_before = None
            opp_eval_after = None
            opp_cp_loss = 0
            if not is_user:
                opp_eval_before = prev_user_eval_after
                # Look ahead to get eval after opponent's move
                if idx + 1 < len(moves):
                    # Simulate opponent's move to get the FEN that will be user's turn
                    sim_board = board.copy()
                    sim_board.push(move)
                    next_fen_key = " ".join(sim_board.fen().split()[:4])
                    next_eval_data = eval_lookup.get(next_fen_key, {})
                    opp_eval_after = next_eval_data.get("eval_before")  # This is the eval at user's next turn
                
                # Calculate opponent's cp_loss (from opponent's perspective, positive = bad for them)
                if opp_eval_before is not None and opp_eval_after is not None:
                    if user_color == "white":
                        # User is white, opponent is black
                        # If eval went from -100 to +50, opponent blundered (swing of 150 in user's favor)
                        opp_cp_loss = opp_eval_after - opp_eval_before
                    else:
                        # User is black, opponent is white
                        # If eval went from +100 to -50, opponent blundered (swing of 150 in user's favor)
                        opp_cp_loss = opp_eval_before - opp_eval_after
            
            phase = detect_phase(board, full_move_number)
            
            # v100 step 2/12 (2026-05-26): severity classification +
            # practical-severity + forced-recapture extracted to
            # services/caption_pipeline.compute_severity_for_move. Same
            # logic — V5 service is now thin caller. PWC will use the
            # same helper once live_v5_teaching is wired (step 9).
            # Book-move and best-equals-played sanity downgrades stay
            # INLINE below for this extraction (they're not yet safe to
            # auto-apply in PWC where book-move detection has different
            # implications). They'll fold into the helper in a future
            # commit once PWC consumes the pipeline end-to-end.
            _user_post_eval_for_severity = None
            _ea = eval_data.get("eval_after")
            if _ea is not None:
                _user_post_eval_for_severity = (
                    _ea if user_color == "white" else -_ea
                )
            _sev = _compute_severity_for_move(
                cp_loss=cp_loss,
                opp_cp_loss=opp_cp_loss,
                is_user=bool(is_user),
                is_white=bool(is_white),
                user_color=user_color,
                mate_sentinel_eval_cp=_user_post_eval_for_severity,
                # White-POV evals for practical-severity (the function
                # does its own sign-flip based on mover_is_white).
                user_eval_before_white_pov=eval_data.get("eval_before"),
                user_eval_after_white_pov=eval_data.get("eval_after"),
                opp_eval_before=opp_eval_before,
                opp_eval_after=opp_eval_after,
                board_before=board,
                played_move=move,
                prev_move=prev_move,
            )
            severity = _sev.severity_user_facing
            _practical = _sev.practical
            is_forced_recapture = _sev.is_forced_recapture

            # Override: known opening book moves should never be flagged as inaccuracies
            if is_user and severity in ("inaccuracy", "mistake") and phase == "opening":
                if is_book_opening_move(board, move_san, idx, opening_name, cp_loss):
                    logger.info(f"[BOOK MOVE] {move_san} (cpl={cp_loss}) is a book opening move — overriding '{severity}' to 'good'")
                    severity = "good"

            # Category 6 fix — best-move agreement sanity check. When the
            # severity classifier says mistake/inaccuracy/blunder but the
            # stored best_move EQUALS the played move, the stored cp_loss
            # is internally inconsistent (you can't lose centipawns by
            # playing the engine's top choice). Downgrade severity to
            # "good" rather than mislead the user. Source bugs:
            #   fb_4102902e3639 (Qe5 marked mistake but is engine's best)
            #   fb_5dd398d092c9 (h6 marked mistake; Parth: both moves fine)
            if is_user and severity in ("inaccuracy", "mistake", "blunder"):
                _stored_best = (eval_data.get("best_move") or "").strip().rstrip("!?+#")
                _played_norm = (move_san or "").strip().rstrip("!?+#")
                if _stored_best and _stored_best == _played_norm:
                    logger.info(
                        f"[SEVERITY-SANITY] move {move_san} == stored best_move but "
                        f"severity={severity} (cpl={cp_loss}). Reclassifying as "
                        f"'forced' (best damage control in a losing position). "
                        f"Internal severity stays 'good' for downstream-consumer "
                        f"compatibility; user-facing caption surfaces via "
                        f"R14_forced_best (\"only move\")."
                    )
                    severity = "good"
            
            fen_before = board.fen()
            
            # ─── ADAPTIVE PRIORITY ────────────────────────────────
            # Determine if this move should be fully explained based on player level
            # For lower-rated players: skip inaccuracies, focus on mistakes/blunders
            move_priority = "silent"
            if is_user and severity == "inaccuracy" and cp_loss < adaptive.get("min_cp_explain", 100):
                # Below this player's threshold — treat as fine
                severity = "good"
                move_priority = "silent"
            elif is_user and severity == "inaccuracy":
                move_priority = "growth"
            elif is_user and severity in ("mistake", "blunder"):
                move_priority = "essential"
            elif not is_user and severity in ("opp_blunder", "opp_mistake"):
                move_priority = "essential"
            elif not is_user:
                move_priority = "context"
            elif severity == "good":
                move_priority = "silent"
            
            # Get PV data
            pv_after_played = eval_data.get("pv_after_played", [])
            pv_after_best = eval_data.get("pv_after_best", [])
            best_move = eval_data.get("best_move")

            # v59 (2026-05-22): v58's PV-vs-stored-best reconciliation reverted.
            # The assumption "PV[0] is more reliable than stored best_move"
            # was wrong: empirically sometimes the stored best is right and PV
            # is stale (row #032 — c4 stored, Bxc3 in PV, c4 verified correct),
            # sometimes the PV is right and stored is stale (row #003 — Bxa6
            # stored, Nxe5 in PV, Nxe5 verified correct). Without re-running
            # engine inline, we can't tell which is reliable. Trust the
            # stored best for now; tackle the PV-vs-best problem with a real
            # disambiguation strategy later.

            # Build coaching based on move type
            narrative = ""
            plan = None
            future_moves = []
            highlight_squares = []
            your_plan_now = None
            needs_acknowledgment = False
            already_acknowledged = False
            acknowledgment_prompt = None
            is_best_move = False
            concept_applied = None
            
            if not is_user:
                # OPPONENT MOVE - Analyze from user's POV with proper eval data
                # Get the user's best response from the NEXT position's eval data
                user_best_response = None
                if idx + 1 < len(moves):
                    sim_board = board.copy()
                    sim_board.push(move)
                    next_fen_key = " ".join(sim_board.fen().split()[:4])
                    next_eval_data = eval_lookup.get(next_fen_key, {})
                    user_best_response = next_eval_data.get("best_move")
                
                # Use the best response in PV if available
                pv_for_analysis = [user_best_response] if user_best_response else pv_after_played
                
                # Build move history (SAN list) including this opponent
                # move — used by analyze_opponent_move to look up opening
                # theory and emit theory-grounded captions in the
                # opening phase.
                move_history_san = []
                try:
                    replay = chess.Board()
                    for past_move in board.move_stack:
                        move_history_san.append(replay.san(past_move))
                        replay.push(past_move)
                    move_history_san.append(replay.san(move))
                except Exception:
                    move_history_san = []

                narrative, your_plan_now, highlight_squares = analyze_opponent_move(
                    board, move,
                    opp_eval_before,
                    opp_eval_after,
                    pv_for_analysis,
                    user_color,
                    move_history_san=move_history_san,
                    full_move_number=full_move_number,
                )
                future_moves = pv_after_played[:3] if pv_after_played else []
                
                # Add opening introduction for early moves (only if it's a normal move)
                if idx < 10 and phase == "opening" and severity == "context":
                    intro = get_opening_introduction(
                        eco_code, opening_name, move_san, user_color,
                        move_index=idx,
                    )
                    if intro:
                        intro_name = intro.get("name")
                        intro_idea = intro.get("idea")
                        intro_hint = intro.get("hint")
                        
                        if intro_name and intro_idea:
                            narrative = f"{intro_name}: {intro_idea}"
                            if intro_hint:
                                your_plan_now = intro_hint
                        elif intro_name:
                            narrative = f"This is the {intro_name}. {narrative}"
                
            elif severity == "good":
                # GOOD USER MOVE - Recognize and track
                narrative, concept_applied, is_best_move = recognize_good_move(
                    board, move, best_move, cp_loss, phase, opening_data,
                    eval_before=eval_data.get("eval_before"),
                    eval_after=eval_data.get("eval_after")
                )
                
            elif is_forced_recapture:
                # FORCED RECAPTURE - Natural move
                captured = board.piece_at(move.to_square)
                narrative = f"Forced recapture — {move_san} takes back the {get_piece_name(captured) if captured else 'piece'}."
                
            else:
                # MISTAKE/INACCURACY - Extract plan
                # Get Stockfish candidates for alternative moves
                stockfish_candidates = await _get_stockfish_candidates(board, num_moves=3, depth=12)
                
                plan = extract_plan_from_pv(
                    board, move, best_move,
                    pv_after_played, pv_after_best,
                    phase, opening_data, cp_loss,
                    eco_code=eco_code,
                    stockfish_candidates=stockfish_candidates
                )
                
                # ── GOLDEN RULE INJECTION ──
                # Enrich the plan's transferable_learning with phase-specific wisdom
                try:
                    from services.golden_rule_service import get_golden_rule
                    golden = get_golden_rule(
                        board=board,
                        move=move,
                        phase=phase,
                        severity=severity,
                        cp_loss=cp_loss,
                        eco_code=eco_code,
                        opening_name=opening_name,
                        best_move_san=best_move,
                        concept_type=plan.concept_type if plan else None,
                    )
                    if golden and golden.get("rule"):
                        if plan:
                            # Override generic transferable_learning with specific golden rule
                            plan.transferable_learning = golden["rule"]
                        else:
                            # No plan exists — create a minimal one with the golden rule
                            plan = ChessPlan(
                                goal="",
                                current_problem=f"{move_san} was not the best choice here.",
                                consequence="",
                                better_approach=f"{best_move} was better." if best_move else "",
                                transferable_learning=golden["rule"],
                                concept_id=f"golden_{golden.get('source', 'rule')}_{full_move_number}",
                                concept_type=golden.get("category", "general"),
                            )
                except Exception as gr_err:
                    logger.debug(f"Golden rule injection failed (non-fatal): {gr_err}")

                if plan:
                    already_acknowledged = plan.concept_id in acknowledged_concepts
                    
                    # Check how many times we've shown this concept
                    shown_count = 0
                    if db is not None:
                        try:
                            concept_doc = await db.user_concept_understanding.find_one({
                                "user_id": user_id,
                                "concept_id": plan.concept_id
                            })
                            if concept_doc:
                                shown_count = concept_doc.get("shown_count", 0)
                        except Exception:
                            pass
                    
                    if not already_acknowledged:
                        needs_acknowledgment = True
                        if shown_count >= 3:
                            acknowledgment_prompt = "Let's revisit this concept — it keeps coming up."
                        else:
                            acknowledgment_prompt = "Click 'I understand' when this is clear to you."
                    
                    narrative = generate_simple_narrative(
                        plan, move_san, best_move, cp_loss, already_acknowledged
                    )
                    future_moves = pv_after_played[:4] if pv_after_played else []
                else:
                    # Fallback narrative — severity tier, not literal
                    # pawn-count (centipawn loss != material lost).
                    if cp_loss >= 400:
                        narrative = f"{move_san} is a major mistake. {best_move} was better."
                    elif cp_loss >= 250:
                        narrative = f"{move_san} is a serious mistake. {best_move} was better."
                    else:
                        narrative = f"{move_san} is a mistake. {best_move} was better."
                    future_moves = pv_after_played[:3] if pv_after_played else []
            
            # Check weakness match — boost priority if move matches known pattern
            weakness_match = False
            weakness_count = 0
            if plan and is_user and severity in ("inaccuracy", "mistake", "blunder"):
                concept = (plan.concept_id or "").lower()
                concept_type = (plan.concept_type or "").lower()
                for weakness in adaptive.get("known_weaknesses", set()):
                    wk = weakness.lower()
                    if wk in concept or wk in concept_type or concept in wk:
                        weakness_match = True
                        weakness_count = adaptive.get("weakness_patterns", {}).get(weakness, 0)
                        if move_priority != "essential":
                            move_priority = "weakness_match"
                        break

            # ── V5 CAPTION PIPELINE ─────────────────────────────────────
            # Extractor → rules → renderer. Runs for EVERY move (user +
            # opponent). Pure-function: facts come from FEN + engine truth,
            # renderer never touches `chess`. New fields land on move_output
            # alongside the legacy `narrative`/`plan`/`highlight_squares`
            # so we can review side-by-side before retiring the dispatcher.
            # Per docs/caption_pipeline_design.md §3.
            caption_payload = {
                "caption": "",
                "rule_name": "R_FALLBACK_disabled",
                "highlight_squares": [],
                "arrows": [],
            }
            caption_primary_reason = None
            caption_principles_violated: List[Dict] = []
            principle_cue = ""
            principle_id_used: Optional[str] = None
            caption_captured_piece: Optional[str] = None
            # Initialize unconditionally so the promotion-facts block
            # below can read caption_facts safely even when the V5
            # pipeline branch didn't run (flag off, or extractor crash).
            caption_facts: Dict[str, Any] = {}
            # v100 FINAL — Mohit "completely called through a central
            # layer" 2026-05-26. V5 service per-move caption work now
            # flows through build_move_teaching_decision(). The 12
            # A-helpers + render + suppression + cue-pick + v78 fallback
            # + promotion ladder + tier classification all run inside
            # the central layer in the canonical order. Future caption-
            # pipeline changes propagate automatically.
            shape_pattern_record: Optional[Dict[str, Any]] = None
            trap_record: Optional[Dict[str, Any]] = None
            opening_record: Optional[Dict[str, Any]] = None
            _caption_tier = "NONE"
            if CAPTION_V5_PIPELINE_ENABLED and _build_move_teaching_decision is not None:
                try:
                    # SAN history (excluding current — central layer
                    # appends current internally for trap-recognition).
                    cap_history: List[str] = []
                    _replay = chess.Board()
                    for _past in board.move_stack:
                        cap_history.append(_replay.san(_past))
                        _replay.push(_past)

                    # opening_record (V5-only) — compute BEFORE central
                    # call since A9 promotion ladder reads it.
                    if match_opening_for_mover is not None:
                        try:
                            mover_color = "white" if is_white else "black"
                            opening_record = match_opening_for_mover(
                                played_san_so_far + [move_san], mover_color,
                            )
                        except Exception as _open_exc:
                            logger.info(
                                f"[opening] detect failed on move {full_move_number}: {_open_exc}"
                            )
                            opening_record = None

                    # Eval inputs (white-POV; helpers sign-flip internally).
                    if is_user:
                        _eb = eval_data.get("eval_before")
                        _ea = eval_data.get("eval_after")
                        _cpl = cp_loss
                    else:
                        _eb = opp_eval_before
                        _ea = opp_eval_after
                        _cpl = max(0, opp_cp_loss)

                    _inputs = _CaptionMoveInputs(
                        fen_before=fen_before,
                        played_san=move_san,
                        mover_is_user=bool(is_user),
                        mover_is_white=bool(is_white),
                        user_color=user_color,
                        full_move_number=full_move_number,
                        move_history_san=cap_history,
                        prev_move_san=(cap_history[-1] if cap_history else None),
                        best_move_san=best_move,
                        eval_before_cp=_eb,
                        eval_after_cp=_ea,
                        cp_loss=int(_cpl or 0),
                        pv_after_played=pv_after_played or [],
                        pv_after_best=pv_after_best or [],
                        opp_eval_before=opp_eval_before,
                        opp_eval_after=opp_eval_after,
                        opp_cp_loss=int(opp_cp_loss or 0),
                        eco_code=eco_code,
                        opening_name=opening_name,
                        prev_move_uci=(prev_move.uci() if prev_move else None),
                        best_move_uci=(eval_data.get("best_move_uci") or None),
                    )
                    _state = _CaptionCrossMoveState(
                        fired_principles=set(principles_fired_this_game),
                        fired_state_keys=set(state_keys_fired_this_game),
                        active_trap=active_trap,
                        active_trap_setup_completed_by_user=active_trap_setup_completed_by_user,
                        active_trap_step_cursor=active_trap_step_cursor,
                        prev_user_eval_after=prev_user_eval_after,
                    )
                    _decision = _build_move_teaching_decision(
                        _inputs, _state,
                        shapes_fired_this_game=shapes_fired_this_game,
                        bs_recent_window=_bs_recent_window,
                        game_trap_fires=game_trap_fires,
                        eval_lookup=eval_lookup,
                        move_evaluations=move_evaluations,
                        opening_record=opening_record,
                        severity_override=severity,
                    )

                    # Unpack into V5 locals (move_output / P2 / polish read these).
                    caption_facts = _decision.debug_facts
                    caption_payload = {
                        "caption": _decision.text.caption,
                        "rule_name": _decision.text.rule_name,
                        "highlight_squares": _decision.visual.highlight_squares,
                        "arrows": _decision.visual.arrows,
                    }
                    caption_primary_reason = caption_facts.get("primary_reason")
                    caption_captured_piece = caption_facts.get("captured_piece_type")
                    caption_principles_violated = caption_facts.get("principles_violated") or []
                    principle_cue = caption_facts.get("principle_cue") or ""
                    principle_id_used = caption_facts.get("principle_id_used")
                    shape_pattern_record = _decision.shape_pattern_record
                    trap_record = _decision.trap_record
                    _caption_tier = _decision.teaching_meta.caption_tier
                    # Mohit 2026-05-31: capture R12's chosen severity word
                    # so the Lab board badge stays in sync with the
                    # caption text. Field is None for non-R12 captions
                    # (R15 good-move, opening intro, silent).
                    _caption_severity_word = _decision.teaching_meta.caption_severity_word
                    principles_fired_last_move = set(_decision.state_mutations.fired_principles_added)

                    # ─── DATA-RICHNESS (Mohit 2026-05-27) ──────────────
                    # Persist the coach-move + Socratic teaching that the
                    # central layer auto-derives for EVERY move, so the
                    # review surface is as data-rich as PWC. coach_extras
                    # fires on opponent moves (narrate them like coach
                    # moves); socratic_extras fires on user mistakes
                    # (narrative + question + hint). Both are None on
                    # moves that don't qualify — stored only when present.
                    _coach_extras = _decision.coach_extras
                    if _coach_extras is not None:
                        caption_facts["coach_move_coaching"] = {
                            "move_san": _coach_extras.move_san,
                            "explanation": _coach_extras.explanation,
                            "plan": _coach_extras.plan,
                            "threats": list(_coach_extras.threats or []),
                            "teaching_point": _coach_extras.teaching_point,
                            "hint_for_user": _coach_extras.hint_for_user,
                            "opponent_opportunity": _coach_extras.opponent_opportunity,
                            "v2_intent": _coach_extras.v2_intent,
                            "v2_label": _coach_extras.v2_label,
                        }
                    _socratic_extras = _decision.socratic_extras
                    if _socratic_extras is not None:
                        caption_facts["socratic_coaching"] = {
                            "narrative": _socratic_extras.narrative,
                            "plan": _socratic_extras.plan,
                            "question": _socratic_extras.question,
                            "hint": _socratic_extras.hint,
                        }

                    # Apply state mutations to V5 game-state vars.
                    principles_fired_this_game.update(_decision.state_mutations.fired_principles_added)
                    state_keys_fired_this_game.update(_decision.state_mutations.fired_state_keys_added)
                    active_trap = _decision.state_mutations.active_trap_after
                    active_trap_setup_completed_by_user = _decision.state_mutations.active_trap_setup_completed_by_user_after
                    active_trap_step_cursor = _decision.state_mutations.active_trap_step_cursor_after
                except Exception as _caption_exc:
                    # Downgraded warning → info after audit noise: these
                    # fire predictably on PGN ↔ eval-data drift games
                    # (small corpus subset). The wrapper returns silent
                    # caption; only debugging needs every entry logged.
                    logger.info(
                        f"[caption_v5] move {full_move_number} {move_san} "
                        f"extract/render failed: {_caption_exc}"
                    )
                    caption_payload = {
                        "caption": "",
                        "rule_name": "R_FALLBACK_extractor_crashed",
                        "highlight_squares": [],
                        "arrows": [],
                    }
                    caption_primary_reason = None
                    caption_principles_violated = []

            # Build move output
            prev_move = move
            board.push(move)

            # Track user's eval_after for opponent blunder detection
            if is_user:
                prev_user_eval_after = eval_data.get("eval_after")

            # v100 FINAL: append played SAN to game-wide history for
            # opening / trap matchers on subsequent moves.
            played_san_so_far.append(move_san)

            # v72 (2026-05-23) — P2 detector memory: collect pattern-
            # miss events. Captures user mistakes where a known catalog
            # pattern (queen_fork, attack_with_tempo, etc.) fired. We
            # build the event docs here while caption_facts is fully
            # populated; bulk-insert happens at the end of the game.
            # Gate: user mistake (is_user + cp_loss>=100 + best != played)
            # — matches the existing detector-firing gate.
            if (is_user and best_move and best_move != move_san
                    and (cp_loss or 0) >= 100 and user_id):
                try:
                    from services.pattern_catalog import resolve_pattern_ids
                    from services.pattern_event_logger import build_event
                    _pattern_ids = resolve_pattern_ids(caption_facts)
                    for _pid in _pattern_ids:
                        pattern_miss_events.append(build_event(
                            user_id=user_id,
                            game_id=game_id or "",
                            move_number=full_move_number,
                            move_san=move_san,
                            best_move_san=best_move,
                            pattern_id=_pid,
                            outcome="miss",
                            cp_loss=cp_loss or 0,
                            fen_before=fen_before,
                            detector_versions={"v5_coaching": V5_COACHING_VERSION},
                        ))
                except Exception as _patt_exc:
                    logger.info(
                        f"[pattern_events] collect failed m{full_move_number} "
                        f"{move_san}: {_patt_exc}"
                    )

            # v73 (2026-05-23) — P2 phase 2 HIT detection. When the
            # user played the engine's best move AND that move triggers
            # a position-based catalog pattern (queen_fork, clearance,
            # attack_with_tempo, etc.), log a "hit" event. Only
            # position-based detectors run here — contrastive ones
            # (un_developing, knight_on_rim, etc.) are inherently miss
            # concepts and are excluded by is_hit_eligible(). With
            # both hits and misses tracked, insights can now say
            # "you understand X (3 hits, 1 miss)" instead of only
            # "you've missed X N times".
            if (is_user and best_move and move_san == best_move
                    and user_id):
                try:
                    from services.pattern_catalog import detect_position_patterns
                    from services.pattern_event_logger import build_event
                    _hit_ids = detect_position_patterns(
                        fen_before=fen_before,
                        best_move_san=best_move,
                        pv_after_best=pv_after_best,
                        user_color=user_color,
                        eval_before_cp=eval_data.get("eval_before"),
                        shape_pattern_id=caption_facts.get("shape_pattern_id"),
                        trap_context_name=caption_facts.get("trap_context_name"),
                    )
                    for _pid in _hit_ids:
                        pattern_miss_events.append(build_event(
                            user_id=user_id,
                            game_id=game_id or "",
                            move_number=full_move_number,
                            move_san=move_san,
                            best_move_san=best_move,
                            pattern_id=_pid,
                            outcome="hit",
                            cp_loss=cp_loss or 0,
                            fen_before=fen_before,
                            detector_versions={"v5_coaching": V5_COACHING_VERSION},
                        ))
                except Exception as _hit_exc:
                    logger.info(
                        f"[pattern_events] hit collect failed m{full_move_number} "
                        f"{move_san}: {_hit_exc}"
                    )

            # v67 LLM polish layer (Mohit 2026-05-22): pre-compute a
            # GPT-4.1-mini-polished version of the deterministic caption.
            # Stored alongside; UI uses polished when present, falls back
            # to base otherwise. Gated on user-mistake-tier captions only
            # to keep latency bounded (LLM call adds ~500ms-1s/move).
            caption_llm_polished: Optional[str] = None
            if (is_user and (cp_loss or 0) >= 100
                    and caption_payload.get("caption")):
                try:
                    from services.v5_llm_polish import polish_caption_async
                    caption_llm_polished = await polish_caption_async(
                        facts=caption_facts,
                        base_caption=caption_payload["caption"],
                        pattern_family=caption_payload.get("rule_name"),
                    )
                except Exception as _polish_exc:
                    logger.info(
                        f"[llm_polish] move {full_move_number} {move_san} "
                        f"failed: {_polish_exc}"
                    )

            # Mohit 2026-06-03 — authored caption override lookup.
            # Reads from the `authored_caption_overrides` collection,
            # keyed by (game_id, move_number, move_san). Populated by
            # backend/scripts/authoring_apply_safe_subset.py from
            # Parth's strict-gated authoring submissions.
            #
            # When a hit exists, the override REPLACES the rendered
            # caption text (both caption and caption_llm). Engine-
            # truth fields (severity, cp_loss, fen, etc.) stay
            # computed from the pipeline — only the user-facing
            # text changes. This keeps the audit trail intact while
            # letting human-authored prose ship in place of the
            # templated version.
            #
            # Cheap: single indexed lookup per move; falls through
            # silently on any error so the pipeline never breaks.
            try:
                if game_id:
                    _override = await db.authored_caption_overrides.find_one(
                        {
                            "game_id": game_id,
                            "move_number": full_move_number,
                            "move_san": move_san,
                        },
                        {"_id": 0, "caption": 1, "source_feedback_id": 1},
                    )
                    if _override and (_override.get("caption") or "").strip():
                        _override_text = _override["caption"].strip()
                        logger.info(
                            f"[authored_override] m{full_move_number} {move_san} "
                            f"replaced via {_override.get('source_feedback_id')}"
                        )
                        # Override both surfaces — the V5 service reads
                        # caption_llm preferentially when present.
                        caption_payload["caption"] = _override_text
                        caption_llm_polished = _override_text
            except Exception as _override_err:
                logger.warning(
                    f"[authored_override] lookup failed for m{full_move_number} "
                    f"{move_san}: {_override_err}"
                )

            # v100 FINAL: _caption_tier set inside central call above
            # from _decision.teaching_meta.caption_tier.
            move_output = {
                "move_number": full_move_number,
                "move_san": move_san,
                "is_user_move": is_user,
                "is_white": is_white,
                "fen_before": fen_before,
                "fen_after": board.fen(),
                "phase": phase,
                "opening_name": opening_name,

                # Evaluation - include opponent eval data too
                "cp_loss": cp_loss if is_user else opp_cp_loss,
                "eval_before": eval_data.get("eval_before") if is_user else opp_eval_before,
                "eval_after": eval_data.get("eval_after") if is_user else opp_eval_after,
                "best_move_san": best_move,
                # Threaded for the deterministic PV tactical analyzer so it
                # can explain why the best move works (material gained,
                # forks, defender deflection, etc.) instead of relying on
                # the LLM narrator to guess the reason.
                "best_move_uci": eval_data.get("best_move_uci", ""),
                "pv_after_best": pv_after_best,
                # v70 (2026-05-23): "Play this line" UI in Review.
                # `trap_line_full` is the curated step records (move +
                # explanation) when a trap fires — preferred over raw
                # pv_after_best because the per-step text is hand-
                # authored. `coach_line_length_hint` tells the frontend
                # how many plies of pv_after_best to play back when no
                # trap_line is present.
                "trap_line_full": _trap_steps_for_iter if is_user else None,
                "coach_line_length_hint": _coach_line_length_hint_for_iter,
                # v78.4 — explicit list of SAN moves to animate. Set
                # on opp mistakes/blunders (where pv_after_best can't
                # serve as the line — opp positions have no engine
                # eval entry, so pv_after_best is empty). When set,
                # frontend prefers this over the pv_after_best slice.
                "coach_line_moves": _coach_line_moves_for_iter,
                # The opponent's best reply to the played move — the
                # PUNISHMENT line. Stockfish computes this for bad
                # moves (mistake/blunder/inaccuracy in stockfish_service
                # lines 628-640) but until now it was dropped on the
                # floor instead of carried forward. Captions need it
                # to teach WHY a blunder is bad (the threat that
                # follows), not just WHAT the better move was. Mohit
                # feedback fb_eb1d11ba227f.
                "pv_after_played": pv_after_played,
                "severity": severity,
                "is_mistake": severity in ("mistake", "blunder", "opp_blunder", "opp_mistake"),

                # v96 (2026-05-25) — Tier B Q1: practical severity from
                # win-probability delta + decisiveness-change overlay.
                # Consumers reading the move record (caption renderer,
                # admin/captions UI, future home-intelligence aggregation)
                # can pick the practical tier when softening the harshness
                # of "is a mistake" on still-winning positions, OR the
                # canonical tier for hard-data audits.
                "severity_practical": _practical.practical_tier,
                "severity_canonical": _practical.canonical_tier,
                "mover_winprob_before": round(_practical.mover_winprob_before, 3),
                "mover_winprob_after": round(_practical.mover_winprob_after, 3),
                "mover_winprob_delta": round(_practical.winprob_delta, 3),
                "mover_state_before": _practical.state_before,
                "mover_state_after": _practical.state_after,
                "decisiveness_changed": _practical.decisiveness_changed,
                "stayed_winning": _practical.stayed_winning,
                
                # Adaptive priority
                "priority": move_priority,
                "weakness_match": weakness_match,
                "weakness_count": weakness_count if weakness_match else None,
                
                # ── LEGACY PROSE FIELDS RETIRED ─────────────────
                # narrative / plan.{goal,current_problem,consequence,
                # better_approach,transferable_learning,concept_id,
                # concept_type} / your_plan_now / future_moves are no
                # longer emitted. The frontend reads its move-by-move
                # text from the new V5 caption pipeline via the
                # /coach/decryption/per-move/{game_id} endpoint, which
                # sources from `caption` below. Per memory rule
                # `feedback_v5_caption_rewrite_no_patches.md`: ship the
                # new pipeline end-to-end, drop the legacy prose.
                #
                # Engine candidate moves (just the SAN list) are kept
                # on plan.candidate_moves so the click-to-see-line UI
                # still works — those aren't prose, they're an
                # interactive game-tree feature.
                "narrative": "",
                "plan": (
                    {
                        "goal": None,
                        "current_problem": None,
                        "consequence": None,
                        "better_approach": None,
                        "transferable_learning": None,
                        "concept_id": None,
                        "concept_type": None,
                        "candidate_moves": plan.candidate_moves,
                    }
                    if plan and plan.candidate_moves else None
                ),
                "future_moves": [],
                "highlight_squares": highlight_squares,

                # Concept-acknowledgment loop retired with the legacy
                # transferable_learning surface (frontend JSX deleted).
                "needs_acknowledgment": False,
                "already_acknowledged": False,
                "acknowledgment_prompt": None,
                "concept_id": None,
                "concept_type": None,

                "your_plan_now": None,

                # Good move tracking — concept_applied is the only
                # legacy "good move" string we leave in; renderer
                # doesn't surface it but other lab consumers may.
                "is_best_move": is_best_move,
                "concept_applied": concept_applied,

                # ── NEW V5 CAPTION PIPELINE (the only text source) ─
                # Per docs/caption_pipeline_design.md. Frontend reads
                # via /coach/decryption/per-move/{game_id}.
                "caption": caption_payload["caption"],
                # LLM-polished version (v67) — None when polish failed or
                # the move wasn't gated for polish. Caller prefers this
                # when non-empty, falls back to `caption`.
                "caption_llm": caption_llm_polished,
                "rule_name": caption_payload["rule_name"],
                "caption_arrows": caption_payload["arrows"],
                "caption_highlight_squares": caption_payload["highlight_squares"],
                "caption_facts_primary_reason": caption_primary_reason,
                # Teaching layer — list of evidence dicts, one per
                # firing principle. Grows as detectors are shipped
                # one-by-one per feedback_design_clean_code_leaky.md.
                # Audit script reads this; renderer integration is a
                # later commit once enough detectors are live.
                "caption_facts_principles_violated": caption_principles_violated,
                # Captured piece type (pawn/knight/bishop/rook/queen/None).
                # Surfaced from caption_facts so the LLM caption generator
                # can name what was actually taken instead of guessing
                # "won a pawn". Parth flagged exd6 captioned "won a pawn"
                # when actually a knight was captured.
                "captured_piece_type": caption_captured_piece,
                # Teaching cue — highest-priority principle's
                # endorsement-tiered cue string. Frontend renders this
                # as a separate italic line under the main caption so
                # the diagnosis + the named-principle habit stay
                # visually distinct.
                "principle_cue": principle_cue,
                "principle_id_used": principle_id_used,

                # ── CAPTION CLASSIFICATION (v86) ─────────────────────
                # Per Mohit 2026-05-25: many context/silent captions
                # are observations of what the user can already see
                # on the board ("Nc3. Develops naturally, prepares e4")
                # rather than actual teaching. Surface the classifier's
                # tier so consumers can tell narration from lesson:
                #   HIGH — names a tactical/strategic concept the user
                #          should LEARN (mate, pin, fork, named trap,
                #          opening curriculum, principle violation).
                #   MID  — concrete chess observation (threat, capture,
                #          check, opening pawn push, development).
                #   LOW  — generic engine-speak fallback to be improved.
                #   NONE — no caption / no variant matched.
                # has_teaching_content is the boolean shortcut: True
                # only when tier == "HIGH". Computed via _caption_tier
                # local set just above the output dict.
                "caption_tier": _caption_tier,
                "has_teaching_content": _caption_tier == "HIGH",

                # ── Caption severity word (Mohit 2026-05-31) ──────
                # R12-chosen severity for the rendered caption text
                # (blunder / mistake / inaccuracy / None). Frontend
                # board badge derives from this so badge color +
                # caption text always agree. None for non-R12
                # captions (R15 good, opening intro, silent).
                "caption_severity_word": _caption_severity_word,

                # ── TIER 3 shape pattern (visual danger language) ─
                # At most one pattern per move; once-per-game suppression.
                # Frontend renders pattern_name as a callout under the
                # caption, with pattern_desc on hover/expansion and
                # target squares for board highlighting.
                "shape_pattern_id":   shape_pattern_record["pattern_id"] if shape_pattern_record else None,
                "shape_pattern_name": shape_pattern_record["pattern_name"] if shape_pattern_record else None,
                "shape_pattern_desc": shape_pattern_record["pattern_desc"] if shape_pattern_record else None,
                "shape_pattern_mover": shape_pattern_record["mover"] if shape_pattern_record else None,
                "shape_pattern_targets": shape_pattern_record["targets"] if shape_pattern_record else [],
                "shape_pattern_executing_move": shape_pattern_record["executing_move"] if shape_pattern_record else None,

                # ── Trap recognition (data/traps.json) ─────────────
                # Set on the move that completes a known trap setup, and on
                # subsequent moves that follow the authored trap_line.
                # Fields nested under one dict to keep the move record clean.
                "trap": trap_record,

                # ── Opening curriculum match (data/opening_curriculum.json) ─
                # Set when the mover's played-move prefix matches an opening's
                # setup_order ≥ 3 steps. Carries name, summary, golden_rules.
                "opening": opening_record,

                # ── DATA-RICHNESS coaching extras (Mohit 2026-05-27) ─
                # Same teaching the live PWC surface shows, now available
                # in review too (the central layer auto-derives both for
                # every qualifying move). coach_move_coaching fires on
                # opponent moves (narrate them like coach moves);
                # socratic_coaching fires on user mistakes (narrative +
                # Socratic question + hint). None on moves that don't
                # qualify. Per [[one-source-of-truth-for-coaching]].
                "coach_move_coaching": caption_facts.get("coach_move_coaching"),
                "socratic_coaching": caption_facts.get("socratic_coaching"),
            }

            decryption_data.append(move_output)
            
            # Update concept shown count
            if plan and needs_acknowledgment and db is not None:
                try:
                    await db.user_concept_understanding.update_one(
                        {"user_id": user_id, "concept_id": plan.concept_id},
                        {
                            "$inc": {"shown_count": 1},
                            "$set": {
                                "concept_type": plan.concept_type,
                                "concept_text": plan.transferable_learning,
                                "updated_at": datetime.now(timezone.utc).isoformat()
                            },
                            "$setOnInsert": {
                                "user_id": user_id,
                                "concept_id": plan.concept_id,
                                "acknowledged": False,
                                "source_position": fen_before,
                                "created_at": datetime.now(timezone.utc).isoformat()
                            }
                        },
                        upsert=True
                    )
                except Exception as e:
                    logger.warning(f"Could not update concept tracking: {e}")
        
        logger.info(f"[DECRYPTION V5] Generated coaching for {len(decryption_data)} moves")
        
        # ─── NARRATIVE ENHANCEMENT PASS ───────────────────────────────
        # Two-stage narrative: try the deterministic PV tactical analyzer
        # first (walks Stockfish's principal variation with python-chess;
        # grounded, no fabrication). If it finds a concrete tactical reason
        # (fork, deflection, material gain), use that as the narrative. If
        # not, fall back to the LLM narrator for positional/vague mistakes
        # where the PV doesn't yield a clean tactical signal.
        try:
            from services.pv_tactical_analyzer import explain_best_move_tactically
            from services.v5_llm_narrator import generate_concise_narrative

            mistakes_to_enhance = [
                (i, m) for i, m in enumerate(decryption_data)
                if m.get("severity") in ("mistake", "blunder", "inaccuracy")
                and m.get("plan")
                and m.get("priority") != "silent"
            ]

            if mistakes_to_enhance:
                logger.info(
                    f"[DECRYPTION V5] Enhancing {len(mistakes_to_enhance)} mistakes "
                    f"(deterministic tactical first, LLM fallback)..."
                )

                det_hits = 0
                llm_hits = 0

                for idx, move_data in mistakes_to_enhance:
                    # Stage 1: deterministic PV walk.
                    det_narrative = None
                    try:
                        det_narrative = explain_best_move_tactically(
                            fen_before=move_data.get("fen_before", ""),
                            best_move_uci=move_data.get("best_move_uci", ""),
                            best_move_san=move_data.get("best_move_san", ""),
                            pv_after_best=move_data.get("pv_after_best") or [],
                        )
                    except Exception as e:
                        logger.debug(f"PV analyzer failed for move {idx}: {e}")

                    if det_narrative:
                        decryption_data[idx]["narrative"] = det_narrative
                        decryption_data[idx]["narrative_source"] = "pv_tactical"
                        det_hits += 1
                        continue

                    # Stage 2: LLM narrator fallback.
                    try:
                        llm_narrative = await generate_concise_narrative(
                            move_san=move_data.get("move_san", ""),
                            plan_data=move_data.get("plan", {}),
                            phase=move_data.get("phase", "middlegame"),
                            severity=move_data.get("severity", "mistake"),
                            is_user_move=True,
                        )
                        if llm_narrative:
                            decryption_data[idx]["narrative"] = llm_narrative
                            decryption_data[idx]["narrative_source"] = "llm"
                            llm_hits += 1
                    except Exception as e:
                        logger.warning(f"LLM enhancement failed for move {idx}: {e}")

                logger.info(
                    f"[DECRYPTION V5] Narrative pass complete: "
                    f"{det_hits} deterministic, {llm_hits} LLM fallback"
                )
        except ImportError:
            logger.warning("[DECRYPTION V5] Narrative enhancers not available, using rule-based narratives")
        except Exception as e:
            logger.warning(f"[DECRYPTION V5] Narrative enhancement skipped: {e}")

        # Hallucination guard pass — every per-move text the user will
        # see (narrative, consequence, your_plan_now, better_approach)
        # gets verified against that move's FEN. Strings with hallucinated
        # piece references are stripped (set to empty) so the frontend
        # falls back to other available context. Better silence than
        # confidently-wrong claims. Source bugs:
        #   fb_a36d3d477950 ("Your pawn on f4" with no pawn there)
        #   fb_4f5aff6798ed ("Your queen on g5" — actually a bishop)
        #   fb_93b8af5dd608 ("your knight on e5" — knight is enemy's)
        #   fb_274dfae7eb44 ("your bishop on f7" — bishop is enemy's)
        try:
            from services.coaching_text_guard import verify_coaching_text
            stripped = 0
            for item in decryption_data:
                fen = item.get("fen_before") or item.get("fen") or ""
                if not fen:
                    continue
                for field in ("narrative", "consequence", "your_plan_now", "better_approach"):
                    text = (item.get(field) or "").strip()
                    if not text:
                        continue
                    issues = verify_coaching_text(text, fen, user_color=user_color)
                    if issues:
                        logger.warning(
                            f"[DECRYPTION V5] Stripped hallucinated {field} on move "
                            f"{item.get('move_number')} {item.get('move_san')}: "
                            f"{[i.detail for i in issues]}"
                        )
                        item[field] = ""
                        stripped += 1
            if stripped:
                logger.warning(f"[DECRYPTION V5] Hallucination guard stripped {stripped} fields")
        except Exception as e:
            logger.warning(f"[DECRYPTION V5] Hallucination guard skipped: {e}")

        # Vacuous text suppressor — Category 5. After rendering, if the
        # narrative on a mistake/inaccuracy/blunder is vacuous (no
        # squares, no specific moves, no tactical pattern names —
        # filler like "Something just changed on the board"), strip it.
        # Frontend falls back to severity badge + best move, which is
        # honest silence vs. confidently-wrong fluff. Source bugs:
        #   fb_53710952f696, fb_81ea58440719, fb_2d3cd3b7bf57,
        #   fb_50304a538492, fb_2f2b3ec9dcde
        try:
            from services.vacuous_text_detector import strip_vacuous_segments
            vacuous_stripped = 0
            vacuous_partial = 0
            for item in decryption_data:
                severity = (item.get("severity") or "").strip().lower()
                phase = (item.get("phase") or "").strip().lower()
                played_san = item.get("move_san") or ""
                # Sentence-level strip: drops only the filler-bearing
                # sentences, preserving opening names / diagnoses /
                # alt-move recommendations that appear alongside filler.
                # Earlier all-or-nothing wipe nuked captions like
                # "This is the Nimzo Indian Defense… Bishop slides to
                # Bb4. Bishops love open diagonals!" — losing the
                # opening-name content with the praise tail.
                for field in ("narrative", "consequence", "your_plan_now"):
                    text = (item.get(field) or "").strip()
                    if not text:
                        continue
                    cleaned = strip_vacuous_segments(
                        text,
                        severity=severity,
                        played_move_san=played_san,
                        phase=phase,
                    )
                    if cleaned == text:
                        continue  # nothing to do
                    if not cleaned:
                        logger.warning(
                            f"[DECRYPTION V5] Stripped vacuous {field} on move "
                            f"{item.get('move_number')} {played_san}: "
                            f"\"{text[:80]}\""
                        )
                        item[field] = ""
                        vacuous_stripped += 1
                    else:
                        logger.info(
                            f"[DECRYPTION V5] Trimmed filler from {field} on move "
                            f"{item.get('move_number')} {played_san}: "
                            f"\"{text[:80]}\" -> \"{cleaned[:80]}\""
                        )
                        item[field] = cleaned
                        vacuous_partial += 1
            if vacuous_stripped or vacuous_partial:
                logger.warning(
                    f"[DECRYPTION V5] Vacuous-text suppressor: "
                    f"{vacuous_stripped} fields fully stripped, "
                    f"{vacuous_partial} partially trimmed"
                )
        except Exception as e:
            logger.warning(f"[DECRYPTION V5] Vacuous-text suppressor skipped: {e}")

        # Multi-ply chain verifier — Category 8. Coaching strings often
        # claim future move sequences ("After g4 Nxe5 Nxe5, your knight
        # on e5 gets taken"). Verify each move in the chain is legal
        # from the post-played-move position. Illegal chains (typo'd
        # moves, hallucinated sequences) get the field wiped.
        # Source bug: fb_93b8af5dd608 (chain interpretation issues).
        try:
            from services.coaching_text_guard import verify_chain_claims
            chain_stripped = 0
            for item in decryption_data:
                # Compute post-move FEN. The chain claim describes what
                # happens AFTER the played move, so we verify the chain
                # starting from that position.
                fen_pre = item.get("fen_before") or item.get("fen") or ""
                played_san = item.get("move_san") or ""
                if not fen_pre or not played_san:
                    continue
                try:
                    _b = chess.Board(fen_pre)
                    _b.push_san(played_san)
                    fen_post = _b.fen()
                except Exception:
                    continue
                for field in ("narrative", "consequence"):
                    text = (item.get(field) or "").strip()
                    if not text:
                        continue
                    chain_issues = verify_chain_claims(text, fen_post)
                    if chain_issues:
                        logger.warning(
                            f"[DECRYPTION V5] Stripped illegal-chain {field} on move "
                            f"{item.get('move_number')} {played_san}: "
                            f"{[i.detail for i in chain_issues]}"
                        )
                        item[field] = ""
                        chain_stripped += 1
            if chain_stripped:
                logger.warning(f"[DECRYPTION V5] Chain-legality verifier stripped {chain_stripped} fields")
        except Exception as e:
            logger.warning(f"[DECRYPTION V5] Chain-legality verifier skipped: {e}")

        # v72 (2026-05-23) — P2 detector memory: flush the per-user
        # pattern-miss events collected through the loop. Idempotent
        # write (delete-then-insert keyed by user_id+game_id) keeps
        # the corpus correct across regens. Skipped when db is None
        # or game_id wasn't passed; callers without those just lose
        # the per-user log for that run (no functional impact on the
        # caption pipeline).
        if db is not None and user_id and game_id and pattern_miss_events:
            try:
                from services.pattern_event_logger import replace_events_for_game
                inserted = await replace_events_for_game(
                    db, user_id=user_id, game_id=game_id,
                    events=pattern_miss_events,
                )
                logger.info(
                    f"[pattern_events] flushed {inserted} miss events "
                    f"for user={user_id} game={game_id}"
                )
            except Exception as _flush_exc:
                logger.warning(f"[pattern_events] flush failed: {_flush_exc}")

        return decryption_data
        
    except Exception as e:
        logger.error(f"Error in game decryption V5: {e}")
        import traceback
        traceback.print_exc()
        return []


# ─── SYNC WRAPPER ────────────────────────────────────────────────────

def generate_game_decryption_v5_sync(
    pgn: str,
    user_color: str,
    move_evaluations: List[Dict],
    user_id: str,
    db
) -> List[Dict]:
    """Synchronous wrapper for V5 decryption."""
    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            generate_game_decryption_v5(pgn, user_color, move_evaluations, user_id, db)
        )
        loop.close()
        return result
    except RuntimeError:
        # Already in event loop
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(
                asyncio.run,
                generate_game_decryption_v5(pgn, user_color, move_evaluations, user_id, db)
            )
            return future.result(timeout=180)


# ─── ACKNOWLEDGMENT API ──────────────────────────────────────────────

async def acknowledge_concept(db, user_id: str, concept_id: str) -> bool:
    """
    Mark a concept as acknowledged by the user.
    Called when user clicks "I understand" button.
    """
    try:
        result = await db.user_concept_understanding.update_one(
            {"user_id": user_id, "concept_id": concept_id},
            {
                "$set": {
                    "acknowledged": True,
                    "acknowledged_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        # Also add to coach_memory.learning.concepts_mastered
        await db.coach_memory.update_one(
            {"user_id": user_id},
            {
                "$addToSet": {"learning.concepts_mastered": concept_id},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
            }
        )
        
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"Error acknowledging concept: {e}")
        return False


async def track_concept_application(
    db,
    user_id: str,
    concept_id: str,
    applied_correctly: bool
) -> None:
    """
    Track when user applies (or fails to apply) a concept.
    Called after analyzing a game where the concept was relevant.
    """
    try:
        update_field = "applied_correctly_count" if applied_correctly else "failed_to_apply_count"
        await db.user_concept_understanding.update_one(
            {"user_id": user_id, "concept_id": concept_id},
            {
                "$inc": {update_field: 1},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
            }
        )
    except Exception as e:
        logger.warning(f"Could not track concept application: {e}")
