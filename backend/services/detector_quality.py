"""Canonical authorization for detector output.

Detector implementations and catalogs remain in their existing canonical
registries. This module stores only the right to influence a player-facing
surface. Unknown IDs deliberately fail closed to SHADOW.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

class QualityGrade(str, Enum):
    PLAN = "plan"
    CAPTION = "caption"
    SHADOW = "shadow"
    DISABLED = "disabled"


class QualitySurface(str, Enum):
    PLAN = "plan"
    CAPTION = "caption"
    MASTERY = "mastery"
    PROMPT = "prompt"
    DIAGNOSTIC = "diagnostic"


@dataclass(frozen=True)
class Authorization:
    grade: QualityGrade
    evidence_ref: str
    rationale: str
    limitations: Tuple[str, ...] = ()


_UNKNOWN = Authorization(
    grade=QualityGrade.SHADOW,
    evidence_ref="docs/detector_quality_threshold_lock_2026_08_27.md",
    rationale="No reviewed promotion packet; unknown IDs fail closed.",
    limitations=("Independent semantic precision and recall are not established.",),
)


_EXACT_ENDGAME_CURRICULUM = Authorization(
    grade=QualityGrade.SHADOW,
    evidence_ref=(
        "backend/data/corpus_snapshots/"
        "curriculum_endgame_tablebase_2026-08-29.json"
    ),
    rationale=(
        "The detector is derived from one exact publishable endgame lesson "
        "position, requires the already-stored best move, and reuses the "
        "independent tablebase or pinned-engine curriculum verifier."
    ),
    limitations=(
        "Exact canonical position only; it does not generalize the technique.",
        "Blind application review is still required before mastery promotion.",
    ),
)


# Promotions are intentionally sparse. Adding a detector to its canonical
# registry does not grant it product authority. Promotion is a separate,
# evidence-reviewed edit here.
_AUTHORIZATIONS: Mapping[str, Authorization] = {
    "review:board_transformation_causal_proof": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref=(
            "backend/data/corpus_snapshots/"
            "hidden_opportunities_phase3a2_board_transformation_validation_v1_2026-09-03.json"
        ),
        rationale=(
            "Exact multi-step board transformations retain every stored-line "
            "move and require a positive material payoff after legal horizon "
            "exchange resolution."
        ),
        limitations=(
            "Architecture packet only; blind holdout promotion is incomplete.",
            "Internal Shadow diagnostics only; no player-facing authority.",
        ),
    ),
    "review:endgame_geometry_causal_proof": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref=(
            "backend/data/corpus_snapshots/"
            "hidden_opportunities_phase3a2_endgame_geometry_validation_v2_2026-09-03.json"
        ),
        rationale=(
            "Exact endgame and promotion resources are reconstructed from "
            "both legal stored branches without asserting an unproved WDL."
        ),
        limitations=(
            "Architecture packet only; blind holdout promotion is incomplete.",
            "No named endgame technique without its canonical exact proof.",
            "Internal Shadow diagnostics only; no player-facing authority.",
        ),
    ),
    "review:forcing_tempo_causal_proof": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref=(
            "backend/data/corpus_snapshots/"
            "hidden_opportunities_phase3a2_forcing_tempo_validation_v2_2026-09-03.json"
        ),
        rationale=(
            "Exact forcing-tempo chains are reconstructed from both stored "
            "branches, but the family has not cleared independent Caption "
            "promotion evidence."
        ),
    ),
    "review:target_line_causal_proof": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref=(
            "backend/data/corpus_snapshots/"
            "hidden_opportunities_phase3a7_target_line_validation_v6_2026-09-04.json"
        ),
        rationale=(
            "Both stored branches are legally replayed with persistent piece "
            "identity, and the candidate must contain an exact setup, "
            "constraint and positive whole-sequence target payoff absent or "
            "weaker in the played line. The payoff must remain at least a "
            "minor piece after four legal capture/check/evasion settlement plies."
        ),
        limitations=(
            "Architecture packet only; blind holdout promotion is incomplete.",
            "Internal Shadow diagnostics only; no caption, prompt, plan or mastery authority.",
            "Generic target/line facts do not authorize a named tactical motif.",
        ),
    ),
    "review:exact_endgame_result_change": Authorization(
        grade=QualityGrade.CAPTION,
        evidence_ref=(
            "docs/exact_endgame_result_caption_evidence_2026_09_01.md"
        ),
        rationale=(
            "The caption names only an exact win/draw/loss transition from a "
            "pinned local Fathom/Syzygy probe whose buckets partition every "
            "legal move. The renderer accepts no model or detector inference."
        ),
        limitations=(
            "Single-position Caption authority only; no technique name or recurrence.",
            "CursedWin and BlessedLoss abstain from simple result language.",
            "Plan, mastery, prescription and psychological claims remain unauthorized.",
        ),
    ),
    "review:verified_single_game_cause": Authorization(
        grade=QualityGrade.CAPTION,
        evidence_ref=(
            "docs/verified_single_game_cause_caption_promotion_2026_09_01.md"
        ),
        rationale=(
            "Caption text is limited to one fully reconstructed board cause: "
            "legal exchange truth or two complete legal stored continuations. "
            "The ten-game reviewed packet and expanded structural/adversarial "
            "gates contain zero critical false claims."
        ),
        limitations=(
            "Single-move Caption authority only; no recurrence or learner diagnosis.",
            "It may not name an opening, trap, tactic motif, or endgame technique.",
            "Plan, mastery, prescription, and persistent prompts remain unauthorized.",
        ),
    ),
    "gap:piece_safety:trapped_piece_exact": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="backend/tests/test_trapped_piece_puzzle_proof.py",
        rationale=(
            "The canonical causal candidate is independently checked with a "
            "legal target-capture minimax across every escape, while the stored "
            "best move must avoid that exact trapped state."
        ),
        limitations=(
            "Only attacked non-pawn pieces with no escape below the material floor are named.",
            "Requires a different stored best move and at least 100cp consequence.",
        ),
    ),
    # The four named tactical motifs. Registered rather than promoted: they
    # fire well (missed_pin 1,278 across 50 users, missed_fork 759/49,
    # missed_skewer 529/43, missed_discovered_attack 399/43) and together they
    # cover 2,965 observations, but none has been through the caption check
    # that caught five principles saying things the board did not support on
    # 2026-09-24. Named individually rather than under missed_generic_tactic,
    # which carries more volume (4,413) and would give a user a focus called
    # "generic tactic" -- the repetition problem wearing a different hat.
    # Promote each one only when its sentence has been verified per-FEN.
    "gap:missed_tactic:missed_pin": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="fire volume measured 2026-09-24; caption unverified",
        rationale=(
            "1,295 observations across 50 users. Names the motif a 600-1500 "
            "player can actually look for, instead of 'generic tactic'. "
            "Measured 2026-09-26 against verify_created_alignment(kind='pin') "
            "over 17,298 moves: precision 81.1%, recall 89.1%."
        ),
        limitations=(
            "HELD AT SHADOW at 81.1% precision: 253 of 1,336 labels are not "
            "backed by the independent prover, so roughly one in five players "
            "told they missed a pin did not. missed_fork and missed_skewer "
            "already unlock this topic, so nothing is gained by shipping a "
            "label that is wrong that often.",
        ),
    ),
    "gap:missed_tactic:missed_fork": Authorization(
        # PROMOTED 2026-09-26. Unlocks missed_tactic, the third plannable
        # topic. 100% precision against verify_created_fork over 12,476 moves
        # where the player did not play the engine's move -- 364 of 364 labels
        # backed by the independent prover that carries the Lichess
        # validation.
        grade=QualityGrade.PLAN,
        evidence_ref="verified 2026-09-24 against fork_puzzle_proof over 700 games",
        rationale=(
            "759 observations across 49 users, and the only one of these four "
            "with its claim checked. Scored against verify_created_fork -- the "
            "independent geometry plus stored-line payoff path, already "
            "validated on Lichess fork puzzles -- on 12,476 moves where the "
            "player did NOT play the engine's move: "
            "precision 364 of 364 (100.0%), recall 364 of 559 (65.1%). "
            "It never claims a fork the geometry does not back. "
            "The 195 it misses are not dropped: _detect_tactic_on_move is an "
            "if/elif chain and they come back as missed_discovered_attack or "
            "missed_generic_tactic, which for a knight capture that gives "
            "check AND uncovers a line are both true descriptions. That is a "
            "labelling precedence question, not lost coverage."
        ),
        limitations=(
            "Recall 65.1%: a third of real missed forks are labelled as "
            "another motif, so this id undercounts fork weakness per user.",
            "Verified against another detector, not against a human. The "
            "oracle's own Lichess validation is inherited, not re-run here.",
        ),
    ),
    "gap:missed_tactic:missed_skewer": Authorization(
        # PROMOTED 2026-09-26, alongside missed_fork. Measured against
        # verify_created_alignment(kind="skewer") over 17,298 moves where the
        # player did not play the engine's move: precision 95.4%, recall 80.8%
        # -- 34 of 733 labels are not backed by the independent prover.
        grade=QualityGrade.PLAN,
        evidence_ref="verified 2026-09-26 against aligned_tactic_puzzle_proof",
        rationale="558 observations across 43 users; precision 95.4%.",
        limitations=(
            "Caption claim has not been checked against the board.",
            "Volume alone is not a promotion case.",
        ),
    ),
    "gap:missed_tactic:missed_discovered_attack": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="fire volume measured 2026-09-24; caption unverified",
        rationale="399 observations across 43 users.",
        limitations=(
            "Caption claim has not been checked against the board.",
            "Volume alone is not a promotion case.",
        ),
    ),
    "gap:king_safety:ignored_king_attack": Authorization(
        # PROMOTED 2026-09-26 on Mohit's explicit instruction ("i want to
        # promote all"), with the packet at
        # docs/ignored_king_attack_promotion_packet_2026_09_24.md as its case.
        # This makes king_safety the SECOND plannable topic in the product.
        # Kept below, for the record, the reasoning from when it was held: The measurements below are
        # strong enough to argue for PLAN -- this would be the first
        # non-piece_safety topic any user could be given, and 53 of 86 users
        # currently share one focus because there is exactly one PLAN id. But
        # the caption-surface lock requires a reviewed promotion packet for
        # anything reaching that surface, and this project's rule is that no
        # model approves its own claims. Promoting it here would mean editing
        # the allowlist that exists to stop exactly that.
        #
        # The packet is written and waiting at
        # docs/ignored_king_attack_promotion_packet_2026_09_24.md. Grade moves
        # when Mohit signs it, not before.  <- he has now signed it.
        grade=QualityGrade.PLAN,
        evidence_ref="docs/ignored_king_attack_promotion_packet_2026_09_24.md",
        rationale=(
            "The first non-piece_safety topic anyone can be given. Until now "
            "topic_can_be_planned returned True for exactly one pattern, so 53 "
            "of 86 users held the same focus -- not because their games looked "
            "alike but because there was one authorized id. king_safety is the "
            "largest gap in the corpus (5,794 mistakes of 100cp or worse "
            "against piece_safety's 5,660) and ignored_king_attack is its "
            "highest-volume detector: 4,028 observations across 57 users, "
            "which is every user in move_observations and more reach than the "
            "single PLAN id it joins. "
            "Both halves of what the user is told are now true of the board. "
            "'Opponent had pieces near your king': 0 of 768 fires sit below "
            "the 3-square threshold, against a 49.9% base rate over 27,618 "
            "positions, so the test discriminates rather than passing "
            "everything. 'And you didn't defend': measured and then enforced. "
            "Before the gate, 18.3% of fires were moves that REDUCED the "
            "pressure on their own king, one of them by eight squares, and "
            "the player was told they ignored the attack. Now 0%."
        ),
        limitations=(
            "Pressure is counted as squares within 2 of the king attacked by "
            "the opponent, which is a proxy for danger, not danger itself. A "
            "single well-placed piece can be worse than three loose ones.",
            "board.attackers() is pseudo-legal, so a pinned attacker still "
            "counts. That is arguably right for king safety -- a pinned piece "
            "still controls the squares the king wants -- but it is a choice, "
            "not a measurement.",
            "The detector gates on cp_loss >= 150, so its agreement with the "
            "engine is circular. Do not cite that as evidence of quality; the "
            "case rests on the two board claims above.",
            "Says the attack was ignored, never why it was missed.",
        ),
    ),
    "gap:king_safety:allowed_mate_exact": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/allowed_mate_evidence_2026_09_18.md",
        rationale=(
            "The claim is replayed to an actual board.is_checkmate() from the "
            "position after the played move, using the stored continuation. "
            "Moves already lost before the move are excluded, which is two "
            "thirds of the evaluation-sentinel candidates. Shadow until the "
            "reviewed packet exists."
        ),
        limitations=(
            "An evaluation sentinel alone proves nothing: 66.5% of candidates "
            "were already in a mating net before the move.",
            "Stored PVs run 4-6 moves, so 24.3% of genuine cases cannot be "
            "proven from storage and are left unknown rather than denied.",
            "Precise and partial by construction -- caption-grade trade, not "
            "plan-grade; recall needs the engine extension pass.",
            "Says nothing about why the player missed it, only that the "
            "position after their move is a forced mate.",
        ),
    ),
    "gap:opening_knowledge:left_book_for_a_worse_move": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/opening_left_book_evidence_2026_09_18.md",
        rationale=(
            "Three stored facts, each checkable against any opening database: "
            "the move is the recorded first departure from book, it cost at "
            "least 100cp, and the book continuation is also the stored engine "
            "best move. Shadow until the reviewed packet exists."
        ),
        limitations=(
            "Leaving book is not itself a mistake: 62.6% of stored deviations "
            "cost under 30cp, so the cp floor carries the claim.",
            "The book move is the engine's best in only 36.6% of costly "
            "deviations; the other 63% are deliberately not named.",
            "The book is shallow -- median in_book_through_user_move is 0 and "
            "the maximum observed is 6, so late departures are invisible.",
            "About 181 fires corpus-wide: enough for Caption review, short of "
            "the 200 reviewed fires Plan-grade requires.",
        ),
    ),
    "gap:time_management:clock_damage_exact": Authorization(
        grade=QualityGrade.PLAN,
        evidence_ref="docs/behavioural_focus_scope.md",
        rationale=(
            "Three stored facts, none of them inferred. A timeout LOSS is the "
            "game's own result plus its termination; a time-pressure blunder "
            "is the PGN clock under thirty seconds plus the engine's verdict; "
            "a long think that still went wrong is the clock over ninety "
            "seconds plus the same verdict. Nothing here is a judgement about "
            "the player's state of mind. Measured 2026-09-26: 1,258 timeout "
            "losses across 47 users, and 16 users lose on time in more than "
            "one game in ten."
        ),
        limitations=(
            "Moving fast is deliberately NOT part of this. Across 42 players "
            "with enough data, mistakes are LESS rushed than ordinary moves "
            "(13.2% against 23.5%) and not one player makes their mistakes "
            "faster than their usual pace, so scoring a focus on speed would "
            "tell almost everyone something untrue about themselves.",
            "969 of 2,227 games ending on the clock were WON on time, 44%. "
            "The measure counts losses only; anything reading `termination` "
            "without the result would be wrong about nearly half of them.",
            "PGN clocks are present on 78.4% of moves, so the two per-move "
            "halves are blind on the rest. Timeout losses are unaffected.",
            "slow_paralysis only became reachable on 2026-09-26 -- it "
            "required `not was_critical`, unreachable for a mistake -- so "
            "counts before the re-derive understate it.",
        ),
    ),
    "gap:opening_knowledge:retreated_a_developed_piece": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref=(
            "docs/opening_knowledge_promotion_finding_2026_09_26.md"
        ),
        rationale=(
            "Replaces tempo_wasted_by_repeat, whose label was both vacuous "
            "and false. Vacuous: a knight or bishop off its home square has "
            "already moved, so 'you moved the same piece twice' held for 557 "
            "of 557 fires and was never computed. False: in 240 of 557 the "
            "engine's own best move moves that same piece, so moving it again "
            "was not the error. Negative control over 4,000 opening mistakes "
            "puts that at 13.9%, so 43.1% is specific to retreats. Two gates "
            "now carry the claim -- the engine wants a different piece, and "
            "nothing legally attacks this one -- and 154 of 557 survive."
        ),
        limitations=(
            "Plan grade was MEASURED AND REJECTED, not merely withheld. Of "
            "the 33 users holding a surviving fire, 0 would see "
            "opening_knowledge outscore an already-plannable topic; the "
            "closest is 19 fires against 337. Promoting this id would change "
            "no user's focus, so it would buy the appearance of a fourth "
            "plannable topic and nothing else.",
            "154 fires corpus-wide, median 3 per user, against the 200 "
            "reviewed fires Plan-grade asks for.",
            "It says a piece came back, not what the player should have "
            "played instead; the engine's move is deliberately not named.",
            "Only knights and bishops, only through move 10, only "
            "non-captures costing 100cp or more.",
        ),
    ),
    "tactic:discovered_attack_with_stored_payoff": Authorization(
        # REVERTED to shadow 2026-09-19, hours after promotion, at Mohit's
        # agreement. The packet said 52 reviewed / 0 wrong. One more hour of
        # human review produced a FALSE claim -- a "discovered attack" whose
        # stored line stopped one ply before the opponent recaptured the
        # queen, recommending a move that loses 100cp. The payoff bug is
        # fixed and all 49 true fires survive, but two facts stand: the
        # evidence was overstated twice in one day, and the count is 49
        # against a bar of 50. Fails closed until 50 clean rulings exist on
        # the FIXED code. The caption wiring reads this grade, so nothing
        # renders while it says shadow.
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/discovered_attack_caption_promotion_2026_09_19.md",
        rationale=(
            "Meets every Caption-grade value in the 2026-08-27 threshold lock, "
            "and meets the precision one with HUMAN semantic review rather "
            "than a second implementation: fires judged one position at a "
            "time by Mohit in /admin/detector-review -- 49 of them on claims "
            "the code still makes, 49 true, 0 wrong, 100% precision, 95% "
            "Wilson lower bound 92.7% (bar 85). 30 true "
            "negatives drawn in corpus order from 2,537 engine-flagged "
            "mistakes (bar 20), and 0 critical false claims across an "
            "adversarial packet built from the four cases the reviewer could "
            "not call. Caption-grade sets no recall floor because a caption "
            "detector may safely stay silent. This is the first detector in "
            "the product promoted on human review rather than on agreement "
            "between two implementations -- the shortcut that put simple_hang "
            "at a false 96.9%."
        ),
        limitations=(
            "Only discovered attacks with the exact stored material payoff are named.",
            "Quiet discoveries and truncated continuations remain generic.",
            "Caption surface only. Plan-grade still needs 200 reviewed fires "
            "and >=60% semantic recall, which is not measured at all here.",
            "The precision sample is skewed HARD, not random: the queue serves "
            "least-certain first. That can only depress a measured precision, "
            "never inflate it.",
            "Negatives and adversarial cases are board-adjudicated, not human "
            "semantic gold. They supplement the human figure and do not "
            "substitute for it.",
            "REVIEWED FIRES ARE 49, ONE BELOW THE LOCKED BAR OF 50. The "
            "packet was assembled at 52; replaying all 56 rulings through the "
            "serving code shows 3 are on claims the payoff verifier now "
            "rejects, because two gates landed partway through the review. "
            "Precision is unaffected -- a claim the detector no longer makes "
            "cannot be wrong -- but the count is short and is recorded rather "
            "than rounded up, because rounding it up is what put simple_hang "
            "at a false 96.9%. The grade stands on Mohit's explicit 'we can "
            "switch it on'; one more ruling closes the formal gap.",
            "Wired 2026-09-19 as caption_pipeline detector #15, rendering "
            "through R12_blunder why_user_missed_discovered_attack, gated on "
            "this grade so dropping it to shadow silences the caption with no "
            "code change. Also still reaches users via verified_puzzle_builder.",
        ),
    ),
    "tactic:back_rank_mate_exact": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="backend/tests/test_back_rank_mate_puzzle_proof.py",
        rationale=(
            "The canonical candidate is independently checked on the terminal "
            "board: a rook or queen delivers checkmate along the defender's "
            "home rank while the mated king remains on that rank."
        ),
        limitations=(
            "Only immediate exact mates receive the back-rank name.",
            "Other stored forced mates retain the broader forced-mate concept.",
        ),
    ),
    "tactic:remove_defender_with_stored_payoff": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="backend/tests/test_removal_defender_puzzle_proof.py",
        rationale=(
            "The canonical sole-guard candidate is independently checked before "
            "and after the stored best capture, and the legal stored line must "
            "then capture the exact newly exposed target for net material."
        ),
        limitations=(
            "Only literal sole-defender removal with a stored payoff is named.",
            "Overload, deflection and decoy require separate proof families.",
        ),
    ),
    "tactic:aligned_with_stored_payoff": Authorization(
        grade=QualityGrade.CAPTION,
        evidence_ref=(
            "backend/data/detector_gold/"
            "aligned_payoff_caption_promotion_v1.json"
        ),
        rationale=(
            "Independent legal replay confirmed 25/25 pin fires and 25/25 "
            "skewer fires, with an 86.68% Wilson lower bound for each subtype, "
            "plus 50/50 stratified near-negative abstentions. All 436 stored "
            "candidates had exact geometry, payoff and stored-fact agreement."
        ),
        limitations=(
            "Only alignments whose exact payoff appears in the stored line are named.",
            "Requires a different played move and at least 100cp stored loss.",
            "Caption only; no persistent prompt, plan, recurrence or mastery claim.",
        ),
    ),
    "tactic:fork_with_stored_payoff": Authorization(
        grade=QualityGrade.CAPTION,
        evidence_ref=(
            "backend/data/detector_gold/"
            "fork_payoff_caption_promotion_v1.json"
        ),
        rationale=(
            "Independent legal replay confirmed 50/50 distinct-source fires "
            "and 25/25 stratified near-negative abstentions, with a 92.87% "
            "Wilson precision lower bound. All 709 stored candidates across "
            "both puzzle pools had exact geometry, payoff and stored-fact agreement."
        ),
        limitations=(
            "Only forks whose payoff appears in the stored continuation are named.",
            "Requires a different played move and at least 100cp stored loss.",
            "Caption only; no persistent prompt, plan, recurrence or mastery claim.",
        ),
    ),
    "tactic:free_piece_exact": Authorization(
        grade=QualityGrade.CAPTION,
        evidence_ref=(
            "backend/data/detector_gold/"
            "free_piece_exact_caption_promotion_v1.json"
        ),
        rationale=(
            "Independent legal replay confirmed 50/50 distinct-source fires "
            "and 20/20 stratified near-negative abstentions, with a 92.87% "
            "Wilson precision lower bound. The full 1,607-candidate population "
            "had zero semantic or stored-fact mismatches."
        ),
        limitations=(
            "Only immediate unrecapturable best-move captures are named.",
            "Requires a different played move and at least 100cp stored loss.",
            "Caption only; no persistent prompt, plan, recurrence or mastery claim.",
        ),
    ),
    "tactic:forced_mate_exact": Authorization(
        grade=QualityGrade.CAPTION,
        evidence_ref=(
            "backend/data/detector_gold/"
            "forced_mate_exact_caption_promotion_v1.json"
        ),
        rationale=(
            "Independent legal replay confirmed 25/25 mate-in-one and 25/25 "
            "longer-line distinct-source claims plus 50/50 stratified "
            "abstentions. Every candidate independently reproducible from its "
            "stored puzzle document matched; rows not reproducible from that "
            "document were excluded from the authorization packet."
        ),
        limitations=(
            "Only the exact stored best move is accepted.",
            "A mate marker without a complete legal replay remains unverified.",
            "A re-admission must recover any non-persisted consequence from the "
            "source game analysis and pass the independent zero-violation gate.",
            "Longer lines describe the verified stored continuation; they do "
            "not claim every defence loses or display a mate distance.",
            "Caption only; no prompt, plan, recurrence or mastery claim.",
        ),
    ),
    "curriculum:opening_exact_decision": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/curriculum_truth_and_delivery_scope.md",
        rationale=(
            "The claim is limited to an exact legal prefix in one publishable "
            "canonical opening line, with the stored best move matching the "
            "authored move and a greater-than-50cp stored consequence."
        ),
        limitations=(
            "Exact move order only; no transposition or similar-position claim.",
            "One match is lesson evidence, not a general opening-mastery claim.",
        ),
    ),
    "curriculum:opening_exact_position": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="backend/tests/test_canonical_curriculum_puzzle_proof.py",
        rationale=(
            "The complete four-field position and stored best move match one "
            "unique publishable canonical opening decision; an independent "
            "legal replay reaches the same position."
        ),
        limitations=(
            "Exact position only; no similar-position or strategic-plan inference.",
            "One match is lesson evidence, not general opening mastery.",
        ),
    ),
    "curriculum:opening_plan_exact_decision": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="backend/data/traps.json",
        rationale=(
            "The complete legal history and stored best move identify one "
            "publishable authored opening-plan decision."
        ),
        limitations=(
            "Exact canonical line only; no analogous-plan inference.",
            "Blind per-plan application review is pending.",
        ),
    ),
    "curriculum:opening_plan_exact_position": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="backend/data/traps.json",
        rationale=(
            "The complete four-field position and stored best move identify "
            "one publishable authored opening-plan decision."
        ),
        limitations=(
            "Exact canonical position only; no analogous-plan inference.",
            "Blind per-plan application review is pending.",
        ),
    ),
    "curriculum:trap_exact_decision": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/curriculum_truth_and_delivery_scope.md",
        rationale=(
            "The claim is limited to an exact validated defense or final trap "
            "decision, independently replayed, with the stored best move agreeing "
            "and a greater-than-50cp stored consequence."
        ),
        limitations=(
            "Does not generalize the trap name across transpositions.",
            "Arbitrary safe_moves metadata is not accepted as proof.",
        ),
    ),
    "curriculum:trap_exact_position": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="backend/tests/test_canonical_curriculum_puzzle_proof.py",
        rationale=(
            "The complete four-field position and stored best move match one "
            "unique validated trap decision; an independent legal replay reaches "
            "the same danger or execution position."
        ),
        limitations=(
            "Exact position only; no visually similar trap claim.",
            "Arbitrary safe_moves metadata is not accepted as proof.",
        ),
    ),
    "curriculum:endgame_exact_position": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref=(
            "backend/data/corpus_snapshots/"
            "curriculum_endgame_tablebase_2026-08-29.json"
        ),
        rationale=(
            "The exact validated FEN and canonical answer are independently "
            "backed by committed Syzygy WDL preservation or pinned Stockfish "
            "evidence for positions outside tablebase coverage."
        ),
        limitations=(
            "Exact canonical positions only; no approximate-geometry claim.",
            "One solve is evidence, not a general endgame-mastery claim.",
        ),
    ),
    "gap:piece_safety:destination_safety_exact": Authorization(
        grade=QualityGrade.PLAN,
        evidence_ref=(
            "docs/destination_safety_exact_plan_promotion_2026_09_01.md"
        ),
        rationale=(
            "The claim is limited to one exact board fact: after the player's "
            "move, exhaustive legal exchange analysis says the moved piece is "
            "lost on its destination, stored Stockfish consequence is at least "
            "150cp, and the stored first reply captures that exact piece. The "
            "sealed full-corpus audit passed 200/200 reviewed fires, 82.5% "
            "recall over 200 independently rebuilt opportunities, 60/60 true "
            "negatives, and 60/60 adversarial cases."
        ),
        limitations=(
            "Only knights, bishops, rooks, and queens moved onto a legally capturable destination.",
            "Promotion-capture exchanges are measured but remain silent pending a separate reviewed packet.",
            "It does not infer carelessness, time pressure, blindness, or lack of knowledge.",
            "It does not name a broader tactical motif or claim every piece-safety mistake is covered.",
        ),
    ),
    "gap:piece_safety:simple_hang": Authorization(
        grade=QualityGrade.CAPTION,
        evidence_ref="docs/simple_hang_caption_promotion_2026_08_31.md",
        rationale=(
            "Meets every Caption-grade value in the 2026-08-27 threshold lock: "
            "96.9% reviewed semantic precision over 260 fires (Wilson lower "
            "bound ~94.0%, bar 85%), 40 independently adjudicated "
            "non-opportunity cases (bar 20), and zero critical false claims "
            "across a 40-case near-threshold adversarial packet. Caption-grade "
            "sets no recall floor because a caption detector may safely stay "
            "silent, so the 61.61% taxonomy recall that correctly blocks "
            "Plan-grade does not bar the caption surface."
        ),
        limitations=(
            "Authorization applies only to the current-schema simple_hang subtype.",
            "Caption surface only. Plan-grade still requires the sealed blind "
            "packet, independent semantic review, and the >=60% recall floor "
            "that 16.09% D_live miss recall does not meet.",
            "Non-opportunity and adversarial cases are board/SEE-adjudicated "
            "facts, not human semantic gold; they supplement, and do not "
            "replace, the reviewed 260-fire precision corpus.",
        ),
    ),

    # Measured candidates remain explicit Shadow entries so the quality report
    # carries their real evidence and limitations instead of making them look
    # identical to never-reviewed detectors.
    "shape:free_piece": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/detector_exchange_truth_lock_2026_08_27.md",
        rationale=(
            "Strict post-capture recapture truth passed 200/200 rerated fires "
            "and 20/20 near-negative controls."
        ),
        limitations=(
            "No blinded independent semantic review packet.",
            "No Plan-grade opportunity/recall denominator.",
        ),
    ),
    "principle:TAC_HANGING_PIECE": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/detector_exchange_truth_lock_2026_08_27.md",
        rationale=(
            "Board-mutating legal exchange truth removed 3,571 unsafe stored "
            "claims and passed the fresh deterministic rerating packet."
        ),
        limitations=(
            "No blinded causal-language review.",
            "Recall against independently selected hanging-piece opportunities is unknown.",
        ),
    ),
    "brain:hanging_piece_detector": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/hanging_piece_detector_implementation_2026_08_28.md",
        rationale=(
            "Chess Brain now adapts canonical board-mutating legal-exchange "
            "truth with a measured material floor, engine consequence and a "
            "strict played-versus-best issue-set counterfactual."
        ),
        limitations=(
            "The residual candidates have not received blinded semantic review.",
            "No independent Chess Brain hanging-piece opportunity denominator exists.",
        ),
    ),
    "principle:TAC_FORK_PATTERN": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/detector_quality_threshold_lock_2026_08_27.md",
        rationale=(
            "Full-solution Lichess fork coverage reached 99.7%; a 28/28 "
            "move-attribution sample used the moving piece."
        ),
        limitations=(
            "Specificity is not established because theme absence is not negative truth.",
            "Independent semantic attribution sample is below the Caption-grade minimum.",
        ),
    ),
    "shape:pin": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/detector_tactical_attribution_2026_08_27.md",
        rationale=(
            "Before/after causal filtering is implemented and absolute-pin "
            "king ordering is corrected."
        ),
        limitations=(
            "Fresh independent semantic precision is not yet measured.",
            "Recall and hard-negative performance are unknown.",
        ),
    ),
    "shape:skewer": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/detector_tactical_attribution_2026_08_27.md",
        rationale=(
            "Before/after causal filtering is implemented and pin/skewer "
            "value ordering now treats the king as the highest alignment piece."
        ),
        limitations=(
            "Fresh independent semantic precision is not yet measured.",
            "The defended-front-piece adversarial packet is incomplete.",
        ),
    ),
    "concept:opening_play": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref=(
            "backend/data/corpus_snapshots/current_detector_fires_2026-08-30.json"
        ),
        rationale=(
            "The detector proves exact canonical in-book play and now requires "
            "at least two player decisions."
        ),
        limitations=(
            "A blind per-opening application review has not yet passed.",
            "Off-book moves remain ungraded rather than being called mistakes.",
        ),
    ),
    "concept:opening_sound_deviation": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "At an exact authored opening decision, the player chose a move "
            "outside the curriculum and that move exactly matched the already-"
            "stored Stockfish best move."
        ),
        limitations=(
            "This proves the deviation was sound in that position, not that the "
            "player mastered the authored opening line.",
            "Positive-only candidate; blind review pending.",
        ),
    ),
    "concept:opening_castling": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale="The stored best opening move was legal castling.",
        limitations=("Positive-only candidate; blind review pending.",),
    ),
    "concept:opening_center": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best opening move advanced a home d- or e-pawn to "
            "occupy d4/e4 or d5/e5."
        ),
        limitations=("Positive-only candidate; blind review pending.",),
    ),
    "concept:opening_development_with_tempo": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best opening move developed a home minor piece and the "
            "developed piece immediately attacked the enemy queen, rook or king."
        ),
        limitations=("Positive-only candidate; blind review pending.",),
    ),
    "concept:opening_plan_play": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="backend/data/traps.json",
        rationale=(
            "The played move and stored best move agree at one exact legal "
            "position from one publishable canonical opening-plan line."
        ),
        limitations=(
            "Exact authored positions only; analogous plans are not inferred.",
            "Positive-only candidate; blind per-plan review pending.",
        ),
    ),
    "concept:trap_detection": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref=(
            "backend/data/corpus_snapshots/current_detector_fires_2026-08-30.json"
        ),
        rationale=(
            "Only publishable canonical trap continuations and exact authored "
            "victim defenses can produce a candidate."
        ),
        limitations=(
            "Broad production trap misses were unsafe in the locked replay.",
            "The repaired exact-defense candidate still needs blind review.",
        ),
    ),
    "concept:coached_development": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The player developed a home-square minor piece with the exact "
            "already-stored Stockfish best move during the opening."
        ),
        limitations=("Positive application only; no missed claim.",),
    ),
    "concept:endgame_king_centralization": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "In the canonical endgame phase, the stored best king move reduced "
            "distance to a central square."
        ),
        limitations=("Positive application only; blind semantic review pending.",),
    ),
    "concept:endgame_create_passed_pawn": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best pawn move changed a non-passed pawn into a passed "
            "pawn by exact board geometry."
        ),
        limitations=("Positive application only; blind semantic review pending.",),
    ),
    "concept:endgame_active_rook": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best rook move changed an inactive rook into one on an "
            "open file or the seventh rank in the canonical endgame phase."
        ),
        limitations=("Positive application only; blind semantic review pending.",),
    ),
    "concept:endgame_stop_promotion": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best move captured or physically blockaded an advanced "
            "enemy passed pawn."
        ),
        limitations=("Positive application only; blind semantic review pending.",),
    ),
    "concept:endgame_opposition": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref=(
            "backend/data/corpus_snapshots/current_detector_fires_2026-08-30.json"
        ),
        rationale="Exact king-and-pawn opposition geometry is reconstructed.",
        limitations=("The missed-move branch has not passed blind review.",),
    ),
    "concept:endgame_lucena": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref=(
            "backend/data/corpus_snapshots/current_detector_fires_2026-08-30.json"
        ),
        rationale="A narrow rook-and-pawn bridge geometry is detected.",
        limitations=("Production opportunity coverage is extremely sparse.",),
    ),
    "concept:endgame_philidor": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref=(
            "backend/data/corpus_snapshots/current_detector_fires_2026-08-30.json"
        ),
        rationale="A narrow defensive rook geometry is detected.",
        limitations=("Production opportunity coverage is extremely sparse.",),
    ),
    "concept:concept_knight_outpost": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best move is recognized by the canonical middlegame "
            "pattern source as a pawn-supported knight outpost."
        ),
        limitations=("Positive-only candidate; blind positional review pending.",),
    ),
    "concept:concept_rook_open_file": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best move is recognized by the canonical middlegame "
            "pattern source as occupying an open file."
        ),
        limitations=("Positive-only candidate; blind positional review pending.",),
    ),
    "concept:concept_rook_seventh": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best move is recognized by the canonical middlegame "
            "pattern source as a rook reaching the seventh rank."
        ),
        limitations=("Positive-only candidate; blind positional review pending.",),
    ),
    "concept:concept_central_pawn_break": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best move is recognized by the canonical middlegame "
            "pattern source as a central pawn break."
        ),
        limitations=("Positive-only candidate; blind positional review pending.",),
    ),
    "concept:concept_minority_attack": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best move is recognized by the canonical middlegame "
            "pattern source as a minority-attack pawn push."
        ),
        limitations=("Positive-only candidate; blind positional review pending.",),
    ),
    "concept:concept_iqp": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best move is recognized by the canonical middlegame "
            "pattern source as play specific to an isolated queen-pawn structure."
        ),
        limitations=("Positive-only candidate; blind positional review pending.",),
    ),
    "concept:concept_luft": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best move is recognized by the canonical middlegame "
            "pattern source as creating an escape square for the king."
        ),
        limitations=("Positive-only candidate; blind positional review pending.",),
    ),
    "concept:concept_prophylactic_king_tuck": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best move is recognized by the canonical middlegame "
            "pattern source as a narrow preventive king tuck."
        ),
        limitations=(
            "This is not authorization for the broader prophylaxis concept.",
            "Positive-only candidate; blind positional review pending.",
        ),
    ),
    # Known unsafe claims do not need to execute in normal product paths.
    "concept:endgame_rule_of_square": Authorization(
        grade=QualityGrade.DISABLED,
        evidence_ref="docs/rule_of_square_consolidation_implementation_2026_08_27.md",
        rationale=(
            "Canonical legal-race truth is implemented and all consumers are "
            "adapters, but the production scan found only five eligible positions "
            "and all five belong to one game."
        ),
        limitations=(
            "Needs the locked review counts across independent games and source units "
            "before reconsideration.",
        ),
    ),
    "legacy_endgame:rule_of_square": Authorization(
        grade=QualityGrade.DISABLED,
        evidence_ref="docs/rule_of_square_consolidation_implementation_2026_08_27.md",
        rationale=(
            "The legacy surface is now a thin adapter over canonical legal-race "
            "truth; production evidence is still too sparse for authorization."
        ),
        limitations=(
            "Needs the locked review counts across independent games and source units "
            "before reconsideration.",
        ),
    ),
    "principle:END_RULE_OF_SQUARE": Authorization(
        grade=QualityGrade.DISABLED,
        evidence_ref="docs/rule_of_square_consolidation_implementation_2026_08_27.md",
        rationale=(
            "The caption predicate now consumes canonical legal-race truth, including "
            "immediate captures; production evidence is still too sparse for authorization."
        ),
        limitations=(
            "Needs the locked review counts across independent games and source units "
            "before reconsideration.",
        ),
    ),
    "brain:trapped_piece_detector": Authorization(
        grade=QualityGrade.DISABLED,
        evidence_ref="docs/trapped_piece_detector_implementation_2026_08_27.md",
        rationale=(
            "The turn-order defect is fixed and Chess Brain now adapts canonical "
            "move-causal trapped-piece truth, but independent semantic precision "
            "and recall are not established."
        ),
        limitations=(
            "No stable trapped-piece opportunity denominator.",
            "The seven post-gate production candidates still need blinded review.",
        ),
    ),
    "brain:king_safety_detector": Authorization(
        grade=QualityGrade.DISABLED,
        evidence_ref="docs/king_safety_detector_implementation_2026_08_28.md",
        rationale=(
            "Broad post-move geometry was replaced with canonical board-state facts, "
            "a best-move issue-set counterfactual, a consequence floor and an endgame "
            "gate; independent semantic precision and recall are not established."
        ),
        limitations=(
            "The 90 residual production candidates still need blinded review.",
            "No independent king-safety opportunity denominator exists.",
        ),
    ),
}


def gap_quality_id(pattern: str, subtype: Optional[str]) -> str:
    return f"gap:{pattern}:{subtype or '*'}"


def shape_quality_id(pattern_id: str) -> str:
    return f"shape:{pattern_id}"


def principle_quality_id(principle_id: str) -> str:
    return f"principle:{principle_id}"


def concept_quality_id(skill_id: str) -> str:
    return f"concept:{skill_id}"


def brain_quality_id(detector_id: str) -> str:
    return f"brain:{detector_id}"


def observation_concept_quality_id(concept_id: str) -> str:
    return f"observation_concept:{concept_id}"


def get_authorization(quality_id: str) -> Authorization:
    if str(quality_id).startswith("concept:endgame_curriculum__"):
        return _EXACT_ENDGAME_CURRICULUM
    return _AUTHORIZATIONS.get(quality_id, _UNKNOWN)


def explicit_authorizations() -> Dict[str, Authorization]:
    return dict(_AUTHORIZATIONS)


def grade_for(quality_id: str) -> QualityGrade:
    return get_authorization(quality_id).grade


def is_authorized(quality_id: str, surface: QualitySurface | str) -> bool:
    surface = QualitySurface(surface)
    grade = grade_for(quality_id)
    if surface == QualitySurface.DIAGNOSTIC:
        return grade != QualityGrade.DISABLED
    if surface == QualitySurface.CAPTION:
        return grade in (QualityGrade.CAPTION, QualityGrade.PLAN)
    # Plans, mastery claims and persistent coaching prompts need Plan-grade.
    return grade == QualityGrade.PLAN


def enforcement_enabled() -> bool:
    """Whether Shadow authorization is enforced on product output.

    Fail closed by default so Shadow output cannot silently influence players.
    Explicitly Disabled IDs remain blocked in either mode.
    """
    return os.environ.get(
        "DETECTOR_QUALITY_GATE_ENFORCED", "true"
    ).lower() == "true"


def mastery_strict_evidence_enabled() -> bool:
    """Whether strict per-event proof is required to move concept mastery.

    Deliberately NOT DETECTOR_QUALITY_GATE_ENFORCED. That flag defaults to
    true here and is set true in docker-compose, because it guards a
    different thing: whether Shadow-grade detectors may reach players. It is
    already on in production.

    Reusing it would mean this feature ships enabled, and the strict path
    currently admits nothing -- `proof.authority` exists on 0 of the 110,190
    stored pattern events -- so mastery would stop moving for every user the
    moment it deployed, silently, because the summary just reports zeros.

    This switch is off until a principle quality_id is actually promoted and
    games have been re-rendered so that proof exists.
    """
    return os.environ.get("MASTERY_STRICT_EVIDENCE", "false").lower() == "true"


def can_influence(quality_id: str, surface: QualitySurface | str) -> bool:
    grade = grade_for(quality_id)
    if grade == QualityGrade.DISABLED:
        return False
    if not enforcement_enabled():
        return True
    return is_authorized(quality_id, surface)


def authorized_gap_subtypes(pattern: str) -> Tuple[str, ...]:
    prefix = f"gap:{pattern}:"
    return tuple(
        quality_id[len(prefix):]
        for quality_id, auth in _AUTHORIZATIONS.items()
        if quality_id.startswith(prefix)
        and auth.grade == QualityGrade.PLAN
        and not quality_id.endswith(":*")
    )


def topic_can_be_planned(pattern: str) -> bool:
    """Whether a focus on this topic would survive the plan-surface gate.

    The picker asks this before choosing a topic. It used not to, and the
    two halves disagreed: the ranking would hand someone `threat_awareness`
    because that is what their games showed, the focus document was written,
    and then every plan-surface reader refused it because the detector behind
    it is only graded `shadow`.

    Nothing errored. The user simply had a focus nobody would act on, and the
    Home page -- which treats "no usable focus" as "I have not seen you play
    yet" -- told a player with 52 analysed games to go and play a game or two.
    Measured 2026-09-17: 11 accounts in that state, every one of them with
    analysed games.

    With enforcement off, everything is plannable and this is a no-op, which
    matches what `focus_document_is_authorized` does with an unstamped
    document.
    """
    if not enforcement_enabled():
        return True
    return bool(authorized_gap_subtypes(pattern))


def sanitize_plan_observation(observation: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a plan-safe observation while retaining shadow diagnostics.

    Neutral engine facts remain available. Detector-derived gap/concept fields
    are copied into detector_quality_shadow when they lack Plan authority,
    then removed from the fields consumed by focus/strength aggregation.
    """
    safe = dict(observation)
    shadow: Dict[str, Any] = dict(safe.get("detector_quality_shadow") or {})

    pattern = safe.get("missed_pattern")
    subtype = safe.get("subtype")
    if pattern:
        quality_id = gap_quality_id(str(pattern), str(subtype) if subtype else None)
        if not can_influence(quality_id, QualitySurface.PLAN):
            shadow["gap"] = {
                "quality_id": quality_id,
                "missed_pattern": pattern,
                "subtype": subtype,
                "severity": safe.get("severity"),
                "grade": grade_for(quality_id).value,
            }
            safe["missed_pattern"] = None
            safe["subtype"] = None
            safe["severity"] = None

    pattern_id = safe.get("tactical_pattern_executed")
    if pattern_id:
        quality_id = shape_quality_id(str(pattern_id))
        if not can_influence(quality_id, QualitySurface.PLAN):
            shadow["tactical_pattern_executed"] = {
                "quality_id": quality_id,
                "pattern_id": pattern_id,
                "grade": grade_for(quality_id).value,
            }
            safe["tactical_pattern_executed"] = None

    concept_id = safe.get("concept_used")
    if concept_id:
        quality_id = observation_concept_quality_id(str(concept_id))
        if not can_influence(quality_id, QualitySurface.PLAN):
            shadow["concept_used"] = {
                "quality_id": quality_id,
                "concept_id": concept_id,
                "grade": grade_for(quality_id).value,
            }
            safe["concept_used"] = None

    if shadow:
        safe["detector_quality_shadow"] = shadow
    return safe


def quality_id_for_focus_document(focus: Mapping[str, Any]) -> Optional[str]:
    explicit = focus.get("detector_quality_id")
    if explicit:
        return str(explicit)
    # Compatibility for the already-built, versioned PIC focus document.
    if (
        focus.get("focus_kind") == "piece_safety/simple_hang"
        and focus.get("diagnosis_detector_id")
        == "move_observation.simple_hang.v16_plus"
    ):
        return gap_quality_id("piece_safety", "simple_hang")
    return None


def focus_document_is_authorized(focus: Mapping[str, Any]) -> bool:
    quality_id = quality_id_for_focus_document(focus)
    if not quality_id:
        return not enforcement_enabled()
    return can_influence(quality_id, QualitySurface.PLAN)


def filter_authorized_events(
    events: Iterable[Mapping[str, Any]],
    *,
    id_field: str,
    namespace: str,
    surface: QualitySurface | str,
) -> Tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    """Split events into authorized and shadow lists without losing evidence."""
    allowed: list[Dict[str, Any]] = []
    shadow: list[Dict[str, Any]] = []
    for event in events:
        copied = dict(event)
        detector_id = copied.get(id_field)
        quality_id = f"{namespace}:{detector_id}" if detector_id else ""
        copied["detector_quality_id"] = quality_id or None
        copied["detector_quality_grade"] = grade_for(quality_id).value
        if quality_id and is_authorized(quality_id, surface):
            allowed.append(copied)
        else:
            shadow.append(copied)
    return allowed, shadow
