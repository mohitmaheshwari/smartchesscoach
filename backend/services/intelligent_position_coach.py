"""
Intelligent Position-Based Coaching
====================================

Connects all existing position analysis systems to provide
contextual coaching for ANY position, not just recognized openings.

This module integrates:
- PawnStructureClassifier (30+ structures)
- StructurePlanDatabase (strategic plans)
- DetectorRegistry (18+ tactical/strategic detectors)
- Position Strategy Analyzer (deep analysis)

Usage:
    result = await analyze_position_and_suggest(
        board=board,
        move_history=moves,
        user_color="white",
        user_id="user123",
        db=db
    )
"""

import chess
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


def _detect_game_phase(board: chess.Board, move_count: int = 0) -> str:
    """Determine the current game phase based on material and position."""
    # Count total pieces (excluding pawns and kings)
    piece_count = 0
    
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece:
            if piece.piece_type not in [chess.PAWN, chess.KING]:
                piece_count += 1
    
    # Determine phase based on both pieces and moves
    # Opening: lots of pieces AND early moves
    # Middlegame: transitional
    # Endgame: few pieces
    
    if piece_count <= 4:
        return "endgame"
    elif piece_count <= 8:
        return "late_middlegame"
    elif move_count < 10 and piece_count >= 14:
        return "opening"
    elif move_count < 20 and piece_count >= 10:
        return "middlegame"
    else:
        return "late_middlegame" if piece_count <= 10 else "middlegame"


async def analyze_position_and_suggest(
    board: chess.Board,
    move_history: List[str],
    user_color: str,
    user_id: str,
    db,
    skip_if_opening_offered: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Analyze position using all available systems and generate suggestions.
    
    Returns teaching offer with:
    - Structure/opening identification
    - Strategic plans
    - Tactical themes
    - Warnings
    - Interactive options
    
    Returns None if position is too simple or no interesting features.
    
    Args:
        board: Current chess board position
        move_history: List of moves played in SAN notation
        user_color: "white" or "black"
        user_id: User ID for personalization
        db: Database connection
        skip_if_opening_offered: If True, skip analysis if opening teaching was already offered
    """
    try:
        from services.pawn_structure_service import PawnStructureClassifier
        from services.structure_plan_database import StructurePlanDatabase
        from services.position_strategy_analyzer import analyze_position_deeply
        
        fen = board.fen()
        move_count = len(move_history)
        game_phase = _detect_game_phase(board, move_count)
        
        # Don't offer position coaching in very early opening (let opening detection handle it)
        # Unless explicitly requested via skip_if_opening_offered=False (on-demand analysis)
        if skip_if_opening_offered and move_count < 6:
            logger.debug(f"Too early for position coaching (move {move_count})")
            return None
        
        # 1. Analyze pawn structure
        classifier = PawnStructureClassifier()
        structure_analysis = classifier.analyze(board)
        
        # Even without a specific structure, we can provide tactical analysis
        structure_type = None
        structure_name = "Complex Position"
        structure_teaching = None
        
        if structure_analysis:
            structure_type = structure_analysis.structure_type
            structure_name = structure_analysis.structure_name
            logger.info(f"Structure detected: {structure_name} ({structure_type})")
            
            # 2. Get strategic plans from database
            plan_db = StructurePlanDatabase()
            structure_teaching = plan_db.get_structure(structure_type.value if hasattr(structure_type, 'value') else structure_type)
        
        # 3. Deep position analysis (always run this)
        position_analysis = analyze_position_deeply(fen, user_color)
        
        # 4. Run tactical detectors for additional insights
        tactical_insights = []
        try:
            from services.chess_brain.detector_registry import get_detector_registry
            registry = get_detector_registry()
            
            # Run detectors without a specific move (general position analysis)
            # We pass empty strings since we're analyzing the position, not a move
            context = {
                "game_phase": game_phase,
                "move_number": move_count // 2 + 1
            }
            
            tactical_results, strategic_results, behavioral_results = registry.run_all(
                board=board,
                user_move="",  # No specific move
                best_move="",  # No comparison
                context=context
            )
            
            # Collect insights from detectors
            for result in strategic_results:
                if result.detected and result.teaching_hook:
                    tactical_insights.append({
                        "type": result.pattern_type,
                        "message": result.teaching_hook,
                        "confidence": result.confidence,
                        "key_squares": result.key_squares
                    })
        except Exception as e:
            logger.warning(f"Tactical detector analysis failed: {e}")
        
        # 5. Build teaching message based on what we found
        if structure_teaching:
            main_message = f"Position Type: {structure_name}"
        elif game_phase == "endgame":
            main_message = "Endgame Position"
        else:
            main_message = f"Position Analysis ({game_phase.replace('_', ' ').title()})"
        
        # 6. Get plans for user's color (if structure teaching available)
        user_plans = []
        if structure_teaching:
            user_plans = (structure_teaching.white_plans if user_color == "white" 
                         else structure_teaching.black_plans)
        
        # 7. Build interactive options
        options = []
        
        if user_plans and len(user_plans) > 0:
            # Offer to learn strategic plan
            plan = user_plans[0]  # Get primary plan
            options.append({
                "id": "learn_strategic_plan",
                "label": f"📚 Learn: {plan.name}",
                "description": plan.description[:80] + "..." if len(plan.description) > 80 else plan.description
            })
        
        # Check for tactical features from position analysis
        threats = position_analysis.get("threats", [])
        if threats and len(threats) > 0:
            options.append({
                "id": "see_tactical_themes",
                "label": "⚡ See Tactical Themes",
                "description": f"You have {len(threats)} tactical opportunities"
            })
        
        # Check for undefended pieces (warning)
        undefended = position_analysis.get("piece_activity", {}).get("undefended", [])
        if undefended and len(undefended) > 0:
            options.append({
                "id": "check_piece_safety",
                "label": "⚠️ Check Piece Safety",
                "description": f"You have {len(undefended)} undefended pieces"
            })
        
        # Add strategic insights as options if we found any
        for insight in tactical_insights[:2]:  # Limit to top 2
            if insight.get("message"):
                options.append({
                    "id": f"insight_{insight['type']}",
                    "label": f"💡 {insight['message'][:40]}...",
                    "description": insight["message"]
                })
        
        # Always offer to continue
        options.append({
            "id": "just_play",
            "label": "⚔️ Just play",
            "description": "Continue without lesson"
        })
        
        # 8. Don't return if nothing interesting to teach
        # We should return coaching if we have: structure teaching, tactical features, detected structure, or insights
        has_structure_info = structure_analysis is not None
        has_tactical_info = (threats and len(threats) > 0) or (undefended and len(undefended) > 0) or len(tactical_insights) > 0
        
        if not has_structure_info and not has_tactical_info:
            logger.debug("No interesting features to coach on")
            return None
        
        # 9. Build complete teaching offer
        # Determine main idea - prefer structure teaching, else fall back to a
        # concrete phase prompt. The old middle case ("This position has a
        # {structure_name} character. ...") was 94% RED in the voice audit —
        # it labelled the structure without teaching anything, while the
        # structure_name is already shown as the heading downstream
        # (format_position_coaching_message). Don't repeat the label —
        # let the phase prompt do the actual coaching work.
        if structure_teaching:
            main_idea = structure_teaching.main_idea
        else:
            main_idea = _get_phase_main_idea(game_phase)
        
        result = {
            "type": "position_coaching",
            "structure_name": structure_name,
            "structure_type": structure_type.value if hasattr(structure_type, 'value') else (structure_type or "complex"),
            "game_phase": game_phase,
            "message": main_message,
            "main_idea": main_idea,
            "key_characteristics": structure_teaching.key_characteristics[:3] if structure_teaching else [],
            "strategic_plans": [
                {
                    "name": plan.name,
                    "description": plan.description,
                    "key_moves": plan.key_moves[:5],
                    "teaching_explanation": plan.teaching_explanation
                }
                for plan in user_plans[:2]
            ] if user_plans else [],
            "tactical_features": {
                "threats": len(threats),
                "undefended_pieces": len(undefended),
                "has_tactical_motifs": len(position_analysis.get("tactical_motifs", [])) > 0
            },
            "tactical_insights": tactical_insights[:3],  # Top 3 insights
            "teaching_points": structure_teaching.teaching_points[:3] if structure_teaching else [],
            "options": options,
            "critical_squares": structure_teaching.critical_squares[:5] if structure_teaching else [],
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Position analysis failed: {e}", exc_info=True)
        return None


def _get_phase_main_idea(game_phase: str) -> str:
    """Phase-specific coach voice when no structure teaching is available.

    Voice rules: concrete action prompts, no fluffy abstractions. The old
    middlegame line ("Look for tactical opportunities and strategic
    imbalances") was the single biggest RED contributor in the PwC voice
    audit — abstract, no checklist, no verb the player can act on.
    Replaced with a loose-piece scan, which is concrete and matches the
    1200 reading level.
    """
    phase_ideas = {
        "opening": "Get your pieces out, fight for the centre, castle before move 10.",
        "middlegame": "Find the loose pieces — yours undefended, theirs hanging.",
        "late_middlegame": "Pieces are thinning out — start walking your king forward.",
        "endgame": "Your king is a fighter now — bring it forward. Passed pawns are gold.",
    }
    return phase_ideas.get(game_phase, "Pick your weakest piece and ask: what is it doing?")


def format_position_coaching_message(coaching: Dict[str, Any]) -> str:
    """
    Format position coaching into human-readable message.
    
    Args:
        coaching: Result from analyze_position_and_suggest()
        
    Returns:
        Formatted coaching message
    """
    message_parts = []
    
    # Structure identification
    message_parts.append(f"🎯 {coaching['structure_name']}")
    message_parts.append("")
    
    # Main idea
    if coaching.get("main_idea"):
        message_parts.append(f"Main Idea: {coaching['main_idea']}")
        message_parts.append("")
    
    # Key characteristics
    if coaching.get("key_characteristics"):
        message_parts.append("Key Features:")
        for char in coaching["key_characteristics"]:
            message_parts.append(f"  • {char}")
        message_parts.append("")
    
    # Strategic plans
    if coaching.get("strategic_plans"):
        plan = coaching["strategic_plans"][0]  # Show first plan
        message_parts.append(f"Strategic Plan: {plan['name']}")
        message_parts.append(plan['description'])
        message_parts.append("")
    
    # Tactical features
    tactical = coaching.get("tactical_features", {})
    if tactical.get("threats", 0) > 0:
        message_parts.append(f"⚡ Tactical: {tactical['threats']} opportunities available")
    if tactical.get("undefended_pieces", 0) > 0:
        message_parts.append(f"⚠️ Warning: {tactical['undefended_pieces']} undefended pieces")
    
    return "\n".join(message_parts)


async def get_position_teaching_content(
    db,
    structure_type: str,
    plan_id: str,
    user_color: str
) -> Optional[Dict[str, Any]]:
    """
    Get detailed teaching content for a specific plan.
    
    Called when user clicks "Learn Strategic Plan" option.
    
    Returns:
        Detailed teaching content with examples, key moves, etc.
    """
    try:
        from services.structure_plan_database import StructurePlanDatabase
        
        plan_db = StructurePlanDatabase()
        structure = plan_db.get_structure(structure_type)
        
        if not structure:
            return None
        
        # Get plans for user's color
        plans = (structure.white_plans if user_color == "white" 
                else structure.black_plans)
        
        # Find the specific plan
        plan = next((p for p in plans if p.name.lower().replace(" ", "_") == plan_id), None)
        if not plan:
            plan = plans[0] if plans else None
        
        if not plan:
            return None
        
        return {
            "plan_name": plan.name,
            "description": plan.description,
            "teaching_explanation": plan.teaching_explanation,
            "key_moves": plan.key_moves,
            "piece_maneuvers": plan.piece_maneuvers,
            "pawn_breaks": plan.pawn_breaks,
            "when_to_use": plan.when_to_use,
            "what_to_avoid": plan.what_to_avoid,
            "structure_name": structure.structure_name,
            "critical_squares": structure.critical_squares,
            "common_mistakes": structure.common_mistakes
        }
        
    except Exception as e:
        logger.error(f"Failed to get teaching content: {e}")
        return None
