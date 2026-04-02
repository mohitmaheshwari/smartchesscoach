"""
Opening Evolution Service
=========================

Tracks user's performance in different chess openings over time.
Provides insights like:
- "Your Sicilian has improved from 45% to 62% accuracy"
- "King's Indian isn't working - 3 losses in last 5"

Uses rolling window comparisons, not static baselines.
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class OpeningStats:
    """Statistics for a single opening"""
    opening_name: str
    eco_code: str
    games_played: int
    wins: int
    losses: int
    draws: int
    avg_accuracy: float
    avg_blunders: float
    best_game_id: Optional[str]
    worst_game_id: Optional[str]
    
    @property
    def win_rate(self) -> float:
        if self.games_played == 0:
            return 0
        return (self.wins + self.draws * 0.5) / self.games_played
    
    @property
    def score_pct(self) -> float:
        """Score percentage (wins + 0.5*draws) / total"""
        if self.games_played == 0:
            return 0
        return ((self.wins + self.draws * 0.5) / self.games_played) * 100
    
    def to_dict(self) -> Dict:
        return {
            "opening_name": self.opening_name,
            "eco_code": self.eco_code,
            "games_played": self.games_played,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "win_rate": round(self.win_rate, 2),
            "score_pct": round(self.score_pct, 1),
            "avg_accuracy": round(self.avg_accuracy, 1),
            "avg_blunders": round(self.avg_blunders, 2),
            "best_game_id": self.best_game_id,
            "worst_game_id": self.worst_game_id,
        }


@dataclass
class OpeningComparison:
    """Comparison of opening performance between two periods"""
    opening_name: str
    eco_code: str
    recent_stats: OpeningStats
    previous_stats: OpeningStats
    win_rate_delta: float
    accuracy_delta: float
    blunders_delta: float
    trend: str  # "improving", "declining", "stable"
    
    def to_dict(self) -> Dict:
        return {
            "opening_name": self.opening_name,
            "eco_code": self.eco_code,
            "recent": self.recent_stats.to_dict(),
            "previous": self.previous_stats.to_dict(),
            "win_rate_delta": round(self.win_rate_delta, 2),
            "accuracy_delta": round(self.accuracy_delta, 1),
            "blunders_delta": round(self.blunders_delta, 2),
            "trend": self.trend,
        }


def extract_opening_name(game: Dict) -> Tuple[str, str]:
    """
    Extract opening name and ECO code from game data.
    Returns (opening_name, eco_code)
    """
    import re
    
    # Try different fields where opening might be stored
    # Note: Game model uses 'opening', but some stores use 'opening_name'
    opening = game.get("opening_name") or game.get("opening") or game.get("eco_name") or ""
    eco = game.get("eco") or game.get("eco_code") or ""
    
    # Handle "None" string or actual None
    if opening in [None, "None", "none", ""]:
        opening = ""
    if eco in [None, "None", "none"]:
        eco = ""
    
    # If opening looks like an ECO code (e.g., "B01"), use ECO map
    if opening and len(opening) <= 4 and re.match(r'^[A-E]\d{2}$', opening):
        eco = opening
        opening = ""
    
    # If opening is empty, try to extract from PGN
    if not opening:
        pgn = game.get("pgn", "")
        if pgn:
            # Try to extract Opening from PGN header
            opening_match = re.search(r'\[Opening\s+"([^"]+)"\]', pgn)
            if opening_match:
                opening = opening_match.group(1)
            
            # Try to extract ECO from PGN header
            if not eco:
                eco_match = re.search(r'\[ECO\s+"([^"]+)"\]', pgn)
                if eco_match:
                    eco = eco_match.group(1)
    
    # Clean up opening name
    if not opening and eco:
        # Map common ECO codes to names
        ECO_MAP = {
            "B01": "Scandinavian Defense",
            "B20": "Sicilian Defense",
            "B21": "Sicilian Defense",
            "B30": "Sicilian Defense",
            "B50": "Sicilian Defense",
            "C00": "French Defense",
            "C01": "French Defense",
            "C20": "King's Pawn Game",
            "C40": "King's Knight Opening",
            "C44": "King's Knight Opening",
            "C50": "Italian Game",
            "C54": "Italian Game",
            "C55": "Italian Game",
            "C60": "Ruy Lopez",
            "D00": "Queen's Pawn Game",
            "D30": "Queen's Gambit Declined",
            "E00": "Indian Defense",
            "E60": "King's Indian Defense",
            "A00": "Uncommon Opening",
            "A40": "Queen's Pawn Game",
            "A45": "Queen's Pawn Game",
        }
        eco_prefix = eco[:3] if len(eco) >= 3 else eco
        opening = ECO_MAP.get(eco_prefix, ECO_MAP.get(eco[:2] + "0", f"ECO {eco}"))
    
    # Simplify opening name (remove variations for grouping)
    if opening:
        # Keep main opening, remove specific variation names
        parts = opening.split(":")
        if len(parts) > 1:
            opening = parts[0].strip()
    
    return opening or "Unknown", eco


def calculate_opening_stats(games: List[Dict], analyses: List[Dict]) -> Dict[str, OpeningStats]:
    """
    Calculate statistics for each opening from a list of games.
    
    Args:
        games: List of game documents
        analyses: List of analysis documents (for accuracy data)
        
    Returns:
        Dict mapping opening name to OpeningStats
    """
    # Create analysis lookup
    analysis_map = {a.get("game_id"): a for a in analyses}
    
    # Group games by opening
    opening_games: Dict[str, List[Dict]] = {}
    
    for game in games:
        opening_name, eco_code = extract_opening_name(game)
        key = opening_name
        
        if key not in opening_games:
            opening_games[key] = []
        
        # Attach analysis data to game
        game_id = game.get("game_id")
        analysis = analysis_map.get(game_id, {})
        game["_analysis"] = analysis
        game["_eco"] = eco_code
        opening_games[key].append(game)
    
    # Calculate stats for each opening
    stats: Dict[str, OpeningStats] = {}
    
    for opening_name, games_list in opening_games.items():
        wins = 0
        losses = 0
        draws = 0
        accuracies = []
        blunder_counts = []
        best_game = None
        worst_game = None
        best_accuracy = 0
        worst_accuracy = 100
        eco_code = ""
        
        for game in games_list:
            eco_code = game.get("_eco", eco_code)
            result = game.get("result", "").lower()
            user_color = game.get("user_color", "white")
            
            # Determine win/loss/draw
            if result == "1-0":
                if user_color == "white":
                    wins += 1
                else:
                    losses += 1
            elif result == "0-1":
                if user_color == "black":
                    wins += 1
                else:
                    losses += 1
            elif result in ["1/2-1/2", "draw"]:
                draws += 1
            
            # Get accuracy from analysis
            analysis = game.get("_analysis", {})
            accuracy = analysis.get("accuracy", analysis.get("user_accuracy"))
            if accuracy is not None:
                accuracies.append(accuracy)
                if accuracy > best_accuracy:
                    best_accuracy = accuracy
                    best_game = game.get("game_id")
                if accuracy < worst_accuracy:
                    worst_accuracy = accuracy
                    worst_game = game.get("game_id")
            
            # Get blunder count
            blunders = analysis.get("blunders", 0)
            if isinstance(blunders, int):
                blunder_counts.append(blunders)
            elif isinstance(blunders, list):
                blunder_counts.append(len(blunders))
        
        stats[opening_name] = OpeningStats(
            opening_name=opening_name,
            eco_code=eco_code,
            games_played=len(games_list),
            wins=wins,
            losses=losses,
            draws=draws,
            avg_accuracy=sum(accuracies) / len(accuracies) if accuracies else 0,
            avg_blunders=sum(blunder_counts) / len(blunder_counts) if blunder_counts else 0,
            best_game_id=best_game,
            worst_game_id=worst_game,
        )
    
    return stats


def compare_opening_evolution(
    recent_games: List[Dict],
    recent_analyses: List[Dict],
    previous_games: List[Dict],
    previous_analyses: List[Dict],
    min_games: int = 2
) -> Dict:
    """
    Compare opening performance between two time periods.
    
    Args:
        recent_games: Recent games (e.g., last 25)
        recent_analyses: Analyses for recent games
        previous_games: Previous games (e.g., 25 before that)
        previous_analyses: Analyses for previous games
        min_games: Minimum games in both periods to include opening
        
    Returns:
        {
            "improving": [OpeningComparison, ...],
            "declining": [OpeningComparison, ...],
            "stable": [OpeningComparison, ...],
            "new_openings": [opening_name, ...],
            "dropped_openings": [opening_name, ...],
        }
    """
    recent_stats = calculate_opening_stats(recent_games, recent_analyses)
    previous_stats = calculate_opening_stats(previous_games, previous_analyses)
    
    improving = []
    declining = []
    stable = []
    new_openings = []
    dropped_openings = []
    
    # Find openings in both periods
    all_openings = set(recent_stats.keys()) | set(previous_stats.keys())
    
    for opening in all_openings:
        recent = recent_stats.get(opening)
        previous = previous_stats.get(opening)
        
        if recent and not previous:
            new_openings.append(opening)
            continue
        
        if previous and not recent:
            dropped_openings.append(opening)
            continue
        
        # Both exist - compare
        if recent.games_played < min_games or previous.games_played < min_games:
            continue
        
        win_rate_delta = recent.win_rate - previous.win_rate
        accuracy_delta = recent.avg_accuracy - previous.avg_accuracy
        blunders_delta = recent.avg_blunders - previous.avg_blunders
        
        # Determine trend
        # Positive: higher win rate, higher accuracy, fewer blunders
        score = 0
        if win_rate_delta > 0.1:
            score += 1
        elif win_rate_delta < -0.1:
            score -= 1
        
        if accuracy_delta > 3:  # 3% accuracy improvement
            score += 1
        elif accuracy_delta < -3:
            score -= 1
        
        if blunders_delta < -0.3:  # 0.3 fewer blunders per game
            score += 1
        elif blunders_delta > 0.3:
            score -= 1
        
        if score >= 2:
            trend = "improving"
        elif score <= -2:
            trend = "declining"
        else:
            trend = "stable"
        
        comparison = OpeningComparison(
            opening_name=opening,
            eco_code=recent.eco_code,
            recent_stats=recent,
            previous_stats=previous,
            win_rate_delta=win_rate_delta,
            accuracy_delta=accuracy_delta,
            blunders_delta=blunders_delta,
            trend=trend,
        )
        
        if trend == "improving":
            improving.append(comparison)
        elif trend == "declining":
            declining.append(comparison)
        else:
            stable.append(comparison)
    
    # Sort by magnitude of change
    improving.sort(key=lambda x: x.accuracy_delta, reverse=True)
    declining.sort(key=lambda x: x.accuracy_delta)
    
    return {
        "improving": [c.to_dict() for c in improving],
        "declining": [c.to_dict() for c in declining],
        "stable": [c.to_dict() for c in stable],
        "new_openings": new_openings,
        "dropped_openings": dropped_openings,
    }


def get_opening_recommendations(evolution_data: Dict, user_rating: int) -> List[Dict]:
    """
    Generate actionable recommendations based on opening evolution.
    
    Returns list of recommendations like:
    {
        "type": "keep_playing" | "needs_study" | "try_alternative",
        "opening": "Sicilian Defense",
        "message": "Your Sicilian accuracy is up 8%! Keep it up.",
        "action": "Continue with this opening"
    }
    """
    recommendations = []
    
    # Positive recommendations for improving openings
    for opening in evolution_data.get("improving", [])[:2]:
        name = opening.get("opening_name")
        accuracy_delta = opening.get("accuracy_delta", 0)
        recommendations.append({
            "type": "keep_playing",
            "opening": name,
            "message": f"Your {name} accuracy is up {accuracy_delta:.0f}%! Keep it up.",
            "action": "Continue with this opening",
            "priority": "positive",
        })
    
    # Warnings for declining openings
    for opening in evolution_data.get("declining", [])[:2]:
        name = opening.get("opening_name")
        recent = opening.get("recent", {})
        losses = recent.get("losses", 0)
        games = recent.get("games_played", 1)
        
        if losses >= 3:
            recommendations.append({
                "type": "needs_study",
                "opening": name,
                "message": f"{name} isn't working - {losses} losses in last {games} games.",
                "action": "Review your games and study this opening",
                "priority": "warning",
            })
        else:
            recommendations.append({
                "type": "try_alternative",
                "opening": name,
                "message": f"Your {name} results are declining. Consider an alternative.",
                "action": "Try a different response or study the variations",
                "priority": "suggestion",
            })
    
    return recommendations


async def get_user_opening_evolution(db, user_id: str, window_size: int = 25) -> Dict:
    """
    Get user's opening evolution data from database.
    
    Compares:
    - Last {window_size} games vs previous {window_size} games
    """
    # Get all games sorted by date
    games = await db.games.find(
        {"user_id": user_id}
    ).sort("imported_at", -1).to_list(window_size * 2 + 10)
    
    # Get all analyses
    game_ids = [g.get("game_id") for g in games]
    analyses = await db.game_analyses.find(
        {"game_id": {"$in": game_ids}}
    ).to_list(len(game_ids))
    
    # Split into recent and previous
    recent_games = games[:window_size]
    previous_games = games[window_size:window_size*2]
    
    # Get analyses for each period
    recent_ids = {g.get("game_id") for g in recent_games}
    previous_ids = {g.get("game_id") for g in previous_games}
    
    recent_analyses = [a for a in analyses if a.get("game_id") in recent_ids]
    previous_analyses = [a for a in analyses if a.get("game_id") in previous_ids]
    
    # Compare
    evolution = compare_opening_evolution(
        recent_games, recent_analyses,
        previous_games, previous_analyses,
        min_games=2
    )
    
    # Get user rating for recommendations
    user = await db.users.find_one({"user_id": user_id}, {"rating": 1})
    user_rating = user.get("rating", 1200) if user else 1200
    
    # Add recommendations
    evolution["recommendations"] = get_opening_recommendations(evolution, user_rating)
    evolution["window_size"] = window_size
    evolution["recent_games_count"] = len(recent_games)
    evolution["previous_games_count"] = len(previous_games)
    
    return evolution
