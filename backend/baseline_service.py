"""
Baseline Profile Service

Captures user's starting point when they join the coaching system.
Tracks progress from baseline to current performance.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
import re

logger = logging.getLogger(__name__)

# Minimum games needed to establish baseline
MIN_GAMES_FOR_BASELINE = 10


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
    """
    # Check if user already has baseline
    user = await db.users.find_one({'user_id': user_id}, {'_id': 0, 'baseline_profile': 1, 'coaching_started_at': 1})
    
    if user and user.get('baseline_profile'):
        return user['baseline_profile']
    
    # Try to create baseline if we have enough analyzed games
    if len(analyses) >= MIN_GAMES_FOR_BASELINE:
        # Use oldest games for baseline (first games user imported)
        baseline_analyses = sorted(analyses, key=lambda x: x.get('created_at', ''))[:MIN_GAMES_FOR_BASELINE]
        baseline_games = sorted(games, key=lambda x: x.get('imported_at', ''))[:MIN_GAMES_FOR_BASELINE]
        
        baseline = calculate_baseline_profile(baseline_analyses, baseline_games)
        
        if baseline:
            # Save baseline to user document
            await db.users.update_one(
                {'user_id': user_id},
                {'$set': {
                    'baseline_profile': baseline,
                    'coaching_started_at': datetime.now(timezone.utc).isoformat(),
                    'games_at_baseline': len(games)
                }}
            )
            logger.info(f"Created baseline profile for user {user_id}")
            return baseline
    
    return None
