"""
Baseline Profile Service

Captures user's starting point when they join the coaching system.
Tracks progress from baseline to current performance.

Now also captures PATTERNS (weaknesses, blunder context) for Before/After comparison.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
import re

logger = logging.getLogger(__name__)

# Minimum games needed to establish baseline
MIN_GAMES_FOR_BASELINE = 10


# =============================================================================
# PATTERN ANALYSIS - For Before/After Coach Comparison
# =============================================================================

def calculate_blunder_context_stats(analyses: List[Dict]) -> Dict:
    """
    Calculate when blunders happen (winning/equal/losing positions).
    
    Returns breakdown of blunder context for pattern analysis.
    """
    winning_blunders = 0
    equal_blunders = 0
    losing_blunders = 0
    total_blunders = 0
    
    examples = {
        "when_winning": [],
        "when_equal": [],
        "when_losing": []
    }
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        game_id = analysis.get("game_id")
        
        for m in moves:
            if m.get("evaluation") == "blunder":
                total_blunders += 1
                eval_before = m.get("eval_before", 0)
                
                example = {
                    "game_id": game_id,
                    "move_number": m.get("move_number"),
                    "cp_loss": m.get("cp_loss", 0)
                }
                
                if eval_before > 100:
                    winning_blunders += 1
                    if len(examples["when_winning"]) < 3:
                        examples["when_winning"].append(example)
                elif eval_before < -100:
                    losing_blunders += 1
                    if len(examples["when_losing"]) < 3:
                        examples["when_losing"].append(example)
                else:
                    equal_blunders += 1
                    if len(examples["when_equal"]) < 3:
                        examples["when_equal"].append(example)
    
    if total_blunders == 0:
        return {
            "when_winning": {"count": 0, "percentage": 0},
            "when_equal": {"count": 0, "percentage": 0},
            "when_losing": {"count": 0, "percentage": 0},
            "total_blunders": 0,
            "insight": "No blunders detected"
        }
    
    result = {
        "when_winning": {
            "count": winning_blunders,
            "percentage": round((winning_blunders / total_blunders) * 100),
            "examples": examples["when_winning"]
        },
        "when_equal": {
            "count": equal_blunders,
            "percentage": round((equal_blunders / total_blunders) * 100),
            "examples": examples["when_equal"]
        },
        "when_losing": {
            "count": losing_blunders,
            "percentage": round((losing_blunders / total_blunders) * 100),
            "examples": examples["when_losing"]
        },
        "total_blunders": total_blunders,
        "insight": ""
    }
    
    # Generate insight
    max_context = max(
        ("winning", result["when_winning"]["percentage"]),
        ("equal", result["when_equal"]["percentage"]),
        ("losing", result["when_losing"]["percentage"]),
        key=lambda x: x[1]
    )
    
    if max_context[0] == "winning" and max_context[1] > 40:
        result["insight"] = f"You relax when winning. {max_context[1]}% of blunders happen in + positions."
    elif max_context[0] == "losing" and max_context[1] > 40:
        result["insight"] = f"You struggle under pressure. {max_context[1]}% of blunders happen when behind."
    elif max_context[0] == "equal" and max_context[1] > 40:
        result["insight"] = f"You lose focus in equal positions. {max_context[1]}% of blunders happen when the position is balanced."
    else:
        result["insight"] = "Your blunders are spread across different position types."
    
    return result


def detect_weakness_patterns(analyses: List[Dict], games: List[Dict]) -> List[Dict]:
    """
    Detect weakness patterns from a set of games.
    
    Returns a list of weaknesses with severity and evidence.
    """
    if not analyses:
        return []
    
    n = len(analyses)
    weaknesses = []
    
    # === RELAXES WHEN WINNING (Advantage Collapse) ===
    collapse_count = 0
    collapse_pawns_lost = 0
    collapse_examples = []
    
    for a in analyses:
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        game_id = a.get("game_id")
        
        for m in moves:
            eval_before = m.get("eval_before", 0)
            eval_after = m.get("eval_after", 0)
            cp_loss = m.get("cp_loss", 0)
            
            if eval_before >= 150 and eval_before - eval_after > 150:
                collapse_count += 1
                collapse_pawns_lost += cp_loss
                if len(collapse_examples) < 3:
                    collapse_examples.append({
                        "game_id": game_id,
                        "move_number": m.get("move_number"),
                        "cp_loss": cp_loss
                    })
                break
    
    collapse_pct = round((collapse_count / n) * 100) if n > 0 else 0
    if collapse_pct >= 30:
        weaknesses.append({
            "id": "relaxes_when_winning",
            "label": "Relaxes when winning",
            "description": "You lose focus immediately after gaining advantage.",
            "severity": "high" if collapse_pct >= 50 else "medium",
            "occurrence_pct": collapse_pct,
            "occurrence_count": collapse_count,
            "total_games": n,
            "pawns_lost": round(collapse_pawns_lost / 100, 1),
            "examples": collapse_examples,
            "trend": None  # Will be calculated when comparing
        })
    
    # === PIECE SAFETY ISSUES ===
    hung_piece_count = 0
    hung_pawns_lost = 0
    hung_examples = []
    
    for a in analyses:
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        game_id = a.get("game_id")
        
        for m in moves:
            if m.get("evaluation") == "blunder" and m.get("cp_loss", 0) >= 300:
                hung_piece_count += 1
                hung_pawns_lost += m.get("cp_loss", 0)
                if len(hung_examples) < 3:
                    hung_examples.append({
                        "game_id": game_id,
                        "move_number": m.get("move_number"),
                        "cp_loss": m.get("cp_loss", 0)
                    })
                break
    
    hung_pct = round((hung_piece_count / n) * 100) if n > 0 else 0
    if hung_pct >= 25:
        weaknesses.append({
            "id": "piece_safety",
            "label": "Piece safety issues",
            "description": "You leave pieces undefended or in danger.",
            "severity": "high" if hung_pct >= 40 else "medium",
            "occurrence_pct": hung_pct,
            "occurrence_count": hung_piece_count,
            "total_games": n,
            "pawns_lost": round(hung_pawns_lost / 100, 1),
            "examples": hung_examples,
            "trend": None
        })
    
    # === TACTICAL BLINDNESS ===
    total_blunders = sum(a.get("blunders", 0) for a in analyses)
    avg_blunders = total_blunders / n if n > 0 else 0
    
    if avg_blunders >= 1.5:
        weaknesses.append({
            "id": "tactical_blindness",
            "label": "Misses tactics",
            "description": "You frequently miss tactical opportunities or threats.",
            "severity": "high" if avg_blunders >= 2.5 else "medium",
            "occurrence_pct": round(avg_blunders * 100 / 4),  # Normalize to percentage (4 blunders = 100%)
            "occurrence_count": total_blunders,
            "total_games": n,
            "avg_per_game": round(avg_blunders, 2),
            "examples": [],
            "trend": None
        })
    
    # === TIME TROUBLE ===
    late_blunder_games = 0
    late_examples = []
    
    for a in analyses:
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        game_id = a.get("game_id")
        
        late_blunders = [m for m in moves if m.get("move_number", 0) > 40 and m.get("evaluation") == "blunder"]
        if late_blunders:
            late_blunder_games += 1
            if len(late_examples) < 3:
                late_examples.append({
                    "game_id": game_id,
                    "move_number": late_blunders[0].get("move_number"),
                    "cp_loss": late_blunders[0].get("cp_loss", 0)
                })
    
    late_pct = round((late_blunder_games / n) * 100) if n > 0 else 0
    if late_pct >= 25:
        weaknesses.append({
            "id": "time_trouble",
            "label": "Time trouble blunders",
            "description": "You make critical mistakes late in the game.",
            "severity": "high" if late_pct >= 40 else "medium",
            "occurrence_pct": late_pct,
            "occurrence_count": late_blunder_games,
            "total_games": n,
            "examples": late_examples,
            "trend": None
        })
    
    # Sort by severity and occurrence
    severity_order = {"high": 0, "medium": 1, "low": 2}
    weaknesses.sort(key=lambda x: (severity_order.get(x["severity"], 2), -x["occurrence_pct"]))
    
    return weaknesses


def calculate_pattern_snapshot(analyses: List[Dict], games: List[Dict]) -> Dict:
    """
    Calculate a complete pattern snapshot for a set of games.
    
    This is used for both baseline and current pattern comparison.
    """
    weaknesses = detect_weakness_patterns(analyses, games)
    blunder_context = calculate_blunder_context_stats(analyses)
    
    # Calculate fundamentals scores (simplified badge-like scores)
    total_accuracy = 0
    accuracy_count = 0
    total_best_moves = 0
    total_moves = 0
    
    for a in analyses:
        sf = a.get("stockfish_analysis", {})
        acc = sf.get("accuracy", 0)
        if acc > 0:
            total_accuracy += acc
            accuracy_count += 1
        total_best_moves += sf.get("best_moves", 0)
        total_moves += len(sf.get("move_evaluations", []))
    
    avg_accuracy = round(total_accuracy / accuracy_count, 1) if accuracy_count > 0 else 0
    best_move_ratio = round((total_best_moves / total_moves) * 100) if total_moves > 0 else 0
    
    # Calculate endgame performance
    endgame_performance = calculate_endgame_stats(analyses)
    
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "games_analyzed": len(analyses),
        "weaknesses": weaknesses,
        "blunder_context": blunder_context,
        "fundamentals": {
            "accuracy": avg_accuracy,
            "best_move_ratio": best_move_ratio,
            "endgame_score": endgame_performance.get("score", 50)
        },
        "endgame": endgame_performance
    }


def calculate_endgame_stats(analyses: List[Dict]) -> Dict:
    """Calculate endgame-specific performance stats."""
    endgame_games = 0
    endgame_accuracy_sum = 0
    endgame_blunders = 0
    
    for a in analyses:
        sf = a.get("stockfish_analysis", {})
        moves = sf.get("move_evaluations", [])
        
        # Consider move 40+ as endgame
        endgame_moves = [m for m in moves if m.get("move_number", 0) >= 40]
        if endgame_moves:
            endgame_games += 1
            
            # Count endgame blunders
            endgame_blunders += sum(1 for m in endgame_moves if m.get("evaluation") == "blunder")
            
            # Approximate endgame accuracy
            good_moves = sum(1 for m in endgame_moves if m.get("evaluation") in ["best", "excellent", "good"])
            if len(endgame_moves) > 0:
                endgame_accuracy_sum += (good_moves / len(endgame_moves)) * 100
    
    avg_endgame_accuracy = round(endgame_accuracy_sum / endgame_games) if endgame_games > 0 else 50
    
    # Score: 0-100 based on endgame accuracy and blunders
    score = min(100, max(0, avg_endgame_accuracy - (endgame_blunders * 5)))
    
    return {
        "games_with_endgame": endgame_games,
        "avg_accuracy": avg_endgame_accuracy,
        "blunders": endgame_blunders,
        "score": round(score)
    }


def compare_patterns(baseline_patterns: Dict, current_patterns: Dict) -> Dict:
    """
    Compare baseline patterns with current patterns to calculate improvement.
    
    Returns delta and trend for each weakness.
    """
    if not baseline_patterns or not current_patterns:
        return None
    
    comparison = {
        "weaknesses": [],
        "blunder_context": {},
        "fundamentals": {},
        "overall_improvement": None
    }
    
    # Compare weaknesses
    baseline_weaknesses = {w["id"]: w for w in baseline_patterns.get("weaknesses", [])}
    current_weaknesses = {w["id"]: w for w in current_patterns.get("weaknesses", [])}
    
    all_weakness_ids = set(baseline_weaknesses.keys()) | set(current_weaknesses.keys())
    
    improvement_count = 0
    regression_count = 0
    
    for wid in all_weakness_ids:
        baseline_w = baseline_weaknesses.get(wid)
        current_w = current_weaknesses.get(wid)
        
        if baseline_w and current_w:
            # Both exist - compare
            delta = current_w["occurrence_pct"] - baseline_w["occurrence_pct"]
            trend = "improved" if delta < -10 else ("regressed" if delta > 10 else "stable")
            
            if trend == "improved":
                improvement_count += 1
            elif trend == "regressed":
                regression_count += 1
            
            comparison["weaknesses"].append({
                "id": wid,
                "label": current_w["label"],
                "baseline_pct": baseline_w["occurrence_pct"],
                "current_pct": current_w["occurrence_pct"],
                "delta": delta,
                "trend": trend,
                "baseline_pawns_lost": baseline_w.get("pawns_lost", 0),
                "current_pawns_lost": current_w.get("pawns_lost", 0)
            })
        elif baseline_w and not current_w:
            # Fixed! Was a weakness, no longer is
            improvement_count += 1
            comparison["weaknesses"].append({
                "id": wid,
                "label": baseline_w["label"],
                "baseline_pct": baseline_w["occurrence_pct"],
                "current_pct": 0,
                "delta": -baseline_w["occurrence_pct"],
                "trend": "fixed",
                "baseline_pawns_lost": baseline_w.get("pawns_lost", 0),
                "current_pawns_lost": 0
            })
        elif current_w and not baseline_w:
            # New weakness
            regression_count += 1
            comparison["weaknesses"].append({
                "id": wid,
                "label": current_w["label"],
                "baseline_pct": 0,
                "current_pct": current_w["occurrence_pct"],
                "delta": current_w["occurrence_pct"],
                "trend": "new",
                "baseline_pawns_lost": 0,
                "current_pawns_lost": current_w.get("pawns_lost", 0)
            })
    
    # Compare blunder context
    baseline_bc = baseline_patterns.get("blunder_context", {})
    current_bc = current_patterns.get("blunder_context", {})
    
    for context in ["when_winning", "when_equal", "when_losing"]:
        baseline_val = baseline_bc.get(context, {}).get("percentage", 0)
        current_val = current_bc.get(context, {}).get("percentage", 0)
        delta = current_val - baseline_val
        
        comparison["blunder_context"][context] = {
            "baseline": baseline_val,
            "current": current_val,
            "delta": delta,
            "trend": "improved" if delta < -10 else ("regressed" if delta > 10 else "stable")
        }
    
    # Compare fundamentals
    baseline_fund = baseline_patterns.get("fundamentals", {})
    current_fund = current_patterns.get("fundamentals", {})
    
    for key in ["accuracy", "best_move_ratio", "endgame_score"]:
        baseline_val = baseline_fund.get(key, 0)
        current_val = current_fund.get(key, 0)
        delta = current_val - baseline_val
        
        comparison["fundamentals"][key] = {
            "baseline": baseline_val,
            "current": current_val,
            "delta": round(delta, 1),
            "trend": "improved" if delta > 3 else ("regressed" if delta < -3 else "stable")
        }
    
    # Overall assessment
    if improvement_count > regression_count:
        comparison["overall_improvement"] = "improving"
    elif regression_count > improvement_count:
        comparison["overall_improvement"] = "needs_attention"
    else:
        comparison["overall_improvement"] = "stable"
    
    return comparison


def extract_opening_from_pgn(pgn: str) -> Optional[str]:
    """Extract opening name from PGN."""
    # Try ECOUrl first (chess.com format)
    ecourl_match = re.search(r'openings/([^"]+)', pgn)
    if ecourl_match:
        name = ecourl_match.group(1).replace('-', ' ')
        # Clean up the name - take first 2-3 words
        parts = name.split()
        if len(parts) > 3:
            name = ' '.join(parts[:3])
        return name.title()
    
    # Try Opening tag
    opening_match = re.search(r'\[Opening "([^"]+)"\]', pgn)
    if opening_match:
        return opening_match.group(1)
    
    return None


def calculate_opening_stats(games: List[Dict]) -> Dict:
    """Calculate win rates by opening from a list of games."""
    openings = {}
    
    for game in games:
        pgn = game.get('pgn', '')
        opening = extract_opening_from_pgn(pgn)
        if not opening:
            continue
        
        user_color = game.get('user_color', 'white')
        result = game.get('result', '*')
        
        # Determine outcome
        if result == '*':
            continue
        
        is_win = (result == '1-0' and user_color == 'white') or (result == '0-1' and user_color == 'black')
        is_loss = (result == '0-1' and user_color == 'white') or (result == '1-0' and user_color == 'black')
        
        key = f"{opening}_{user_color}"
        if key not in openings:
            openings[key] = {
                'name': opening,
                'color': user_color,
                'wins': 0,
                'losses': 0,
                'draws': 0,
                'games': 0
            }
        
        openings[key]['games'] += 1
        if is_win:
            openings[key]['wins'] += 1
        elif is_loss:
            openings[key]['losses'] += 1
        else:
            openings[key]['draws'] += 1
    
    # Calculate win rates
    for key in openings:
        total = openings[key]['games']
        wins = openings[key]['wins']
        openings[key]['win_rate'] = round((wins / total) * 100) if total > 0 else 0
    
    return openings


def calculate_baseline_profile(analyses: List[Dict], games: List[Dict]) -> Dict:
    """
    Calculate baseline profile from initial games.
    
    Returns a snapshot of the user's performance when they started coaching.
    """
    if len(analyses) < MIN_GAMES_FOR_BASELINE:
        return None
    
    # Calculate accuracy stats
    accuracies = []
    total_blunders = 0
    total_mistakes = 0
    total_best_moves = 0
    
    for analysis in analyses:
        sf = analysis.get('stockfish_analysis', {})
        acc = sf.get('accuracy', 0)
        if acc > 0:  # Only count valid analyses
            accuracies.append(acc)
            total_blunders += sf.get('blunders', 0)
            total_mistakes += sf.get('mistakes', 0)
            total_best_moves += sf.get('best_moves', 0)
    
    if not accuracies:
        return None
    
    avg_accuracy = round(sum(accuracies) / len(accuracies), 1)
    games_count = len(accuracies)
    blunders_per_game = round(total_blunders / games_count, 2) if games_count > 0 else 0
    mistakes_per_game = round(total_mistakes / games_count, 2) if games_count > 0 else 0
    best_moves_per_game = round(total_best_moves / games_count, 2) if games_count > 0 else 0
    
    # Calculate opening stats
    opening_stats = calculate_opening_stats(games)
    
    # Get top openings by game count
    sorted_openings = sorted(opening_stats.values(), key=lambda x: x['games'], reverse=True)
    top_openings = sorted_openings[:5]  # Keep top 5 openings
    
    # Calculate win/loss record
    wins = sum(1 for g in games if 
               (g.get('result') == '1-0' and g.get('user_color') == 'white') or
               (g.get('result') == '0-1' and g.get('user_color') == 'black'))
    losses = sum(1 for g in games if 
                 (g.get('result') == '0-1' and g.get('user_color') == 'white') or
                 (g.get('result') == '1-0' and g.get('user_color') == 'black'))
    draws = len([g for g in games if g.get('result') == '1/2-1/2'])
    
    overall_win_rate = round((wins / len(games)) * 100) if games else 0
    
    return {
        'captured_at': datetime.now(timezone.utc).isoformat(),
        'games_analyzed': games_count,
        'total_games': len(games),
        'avg_accuracy': avg_accuracy,
        'blunders_per_game': blunders_per_game,
        'mistakes_per_game': mistakes_per_game,
        'best_moves_per_game': best_moves_per_game,
        'wins': wins,
        'losses': losses,
        'draws': draws,
        'win_rate': overall_win_rate,
        'top_openings': top_openings
    }


def calculate_current_stats(analyses: List[Dict], games: List[Dict]) -> Dict:
    """Calculate current performance stats from recent games."""
    if not analyses:
        return None
    
    # Calculate accuracy stats
    accuracies = []
    total_blunders = 0
    total_mistakes = 0
    total_best_moves = 0
    
    for analysis in analyses:
        sf = analysis.get('stockfish_analysis', {})
        acc = sf.get('accuracy', 0)
        if acc > 0:
            accuracies.append(acc)
            total_blunders += sf.get('blunders', 0)
            total_mistakes += sf.get('mistakes', 0)
            total_best_moves += sf.get('best_moves', 0)
    
    if not accuracies:
        return None
    
    avg_accuracy = round(sum(accuracies) / len(accuracies), 1)
    games_count = len(accuracies)
    blunders_per_game = round(total_blunders / games_count, 2) if games_count > 0 else 0
    mistakes_per_game = round(total_mistakes / games_count, 2) if games_count > 0 else 0
    best_moves_per_game = round(total_best_moves / games_count, 2) if games_count > 0 else 0
    
    # Calculate opening stats
    opening_stats = calculate_opening_stats(games)
    sorted_openings = sorted(opening_stats.values(), key=lambda x: x['games'], reverse=True)
    top_openings = sorted_openings[:5]
    
    # Win/loss record
    wins = sum(1 for g in games if 
               (g.get('result') == '1-0' and g.get('user_color') == 'white') or
               (g.get('result') == '0-1' and g.get('user_color') == 'black'))
    losses = sum(1 for g in games if 
                 (g.get('result') == '0-1' and g.get('user_color') == 'white') or
                 (g.get('result') == '1-0' and g.get('user_color') == 'black'))
    draws = len([g for g in games if g.get('result') == '1/2-1/2'])
    
    overall_win_rate = round((wins / len(games)) * 100) if games else 0
    
    return {
        'games_analyzed': games_count,
        'total_games': len(games),
        'avg_accuracy': avg_accuracy,
        'blunders_per_game': blunders_per_game,
        'mistakes_per_game': mistakes_per_game,
        'best_moves_per_game': best_moves_per_game,
        'wins': wins,
        'losses': losses,
        'draws': draws,
        'win_rate': overall_win_rate,
        'top_openings': top_openings
    }


def calculate_progress(baseline: Dict, current: Dict) -> Dict:
    """
    Calculate progress from baseline to current.
    
    Returns deltas and improvement indicators.
    """
    if not baseline or not current:
        return None
    
    accuracy_delta = round(current['avg_accuracy'] - baseline['avg_accuracy'], 1)
    blunders_delta = round(current['blunders_per_game'] - baseline['blunders_per_game'], 2)
    mistakes_delta = round(current['mistakes_per_game'] - baseline['mistakes_per_game'], 2)
    win_rate_delta = current['win_rate'] - baseline['win_rate']
    
    # Opening progress - compare same openings
    opening_progress = []
    baseline_openings = {f"{o['name']}_{o['color']}": o for o in baseline.get('top_openings', [])}
    
    for current_opening in current.get('top_openings', []):
        key = f"{current_opening['name']}_{current_opening['color']}"
        if key in baseline_openings:
            baseline_opening = baseline_openings[key]
            delta = current_opening['win_rate'] - baseline_opening['win_rate']
            opening_progress.append({
                'name': current_opening['name'],
                'color': current_opening['color'],
                'baseline_win_rate': baseline_opening['win_rate'],
                'current_win_rate': current_opening['win_rate'],
                'delta': delta,
                'improved': delta > 0
            })
    
    return {
        'accuracy': {
            'baseline': baseline['avg_accuracy'],
            'current': current['avg_accuracy'],
            'delta': accuracy_delta,
            'improved': accuracy_delta > 0
        },
        'blunders_per_game': {
            'baseline': baseline['blunders_per_game'],
            'current': current['blunders_per_game'],
            'delta': blunders_delta,
            'improved': blunders_delta < 0  # Lower is better
        },
        'mistakes_per_game': {
            'baseline': baseline['mistakes_per_game'],
            'current': current['mistakes_per_game'],
            'delta': mistakes_delta,
            'improved': mistakes_delta < 0  # Lower is better
        },
        'win_rate': {
            'baseline': baseline['win_rate'],
            'current': current['win_rate'],
            'delta': win_rate_delta,
            'improved': win_rate_delta > 0
        },
        'openings': opening_progress,
        'games_since_baseline': current['total_games']
    }


async def get_or_create_baseline(db, user_id: str, analyses: List[Dict], games: List[Dict]) -> Optional[Dict]:
    """
    Get existing baseline or create one if user has enough games.
    
    Returns baseline profile if exists or was just created.
    Now also captures baseline_patterns for Before/After comparison.
    """
    # Check if user already has baseline
    user = await db.users.find_one({'user_id': user_id}, {'_id': 0, 'baseline_profile': 1, 'baseline_patterns': 1, 'coaching_started_at': 1})
    
    if user and user.get('baseline_profile'):
        return user['baseline_profile']
    
    # Try to create baseline if we have enough analyzed games
    if len(analyses) >= MIN_GAMES_FOR_BASELINE:
        # Use oldest games for baseline (first games user imported)
        baseline_analyses = sorted(analyses, key=lambda x: x.get('created_at', ''))[:MIN_GAMES_FOR_BASELINE]
        baseline_games = sorted(games, key=lambda x: x.get('imported_at', ''))[:MIN_GAMES_FOR_BASELINE]
        
        baseline = calculate_baseline_profile(baseline_analyses, baseline_games)
        
        # Also calculate baseline patterns (weaknesses, blunder context) for Before/After comparison
        baseline_patterns = calculate_pattern_snapshot(baseline_analyses, baseline_games)
        
        if baseline:
            # Save baseline AND baseline_patterns to user document
            await db.users.update_one(
                {'user_id': user_id},
                {'$set': {
                    'baseline_profile': baseline,
                    'baseline_patterns': baseline_patterns,  # NEW: Store patterns snapshot
                    'coaching_started_at': datetime.now(timezone.utc).isoformat(),
                    'games_at_baseline': len(games)
                }}
            )
            logger.info(f"Created baseline profile and patterns for user {user_id}")
            return baseline
    
    return None


async def get_baseline_patterns(db, user_id: str) -> Optional[Dict]:
    """Get stored baseline patterns for a user."""
    user = await db.users.find_one(
        {'user_id': user_id}, 
        {'_id': 0, 'baseline_patterns': 1}
    )
    return user.get('baseline_patterns') if user else None
