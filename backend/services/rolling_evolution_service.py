"""
Rolling Evolution Service
=========================

Provides rolling window comparisons for tracking player evolution.
Replaces static baseline with continuous improvement tracking.

Windows:
- Macro: 25 vs 25 (monthly trend)
- Medium: 10 vs 10 (bi-weekly trend)
- Micro: 5 vs 5 (weekly trend)

All metrics are "recent vs previous" - always evolving.
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class WindowMetrics:
    """Metrics for a single time window"""
    games_count: int
    wins: int
    losses: int
    draws: int
    avg_accuracy: float
    blunders_per_game: float
    mistakes_per_game: float
    avg_cp_loss: float
    openings_played: List[str]
    
    @property
    def win_rate(self) -> float:
        if self.games_count == 0:
            return 0
        return self.wins / self.games_count
    
    @property
    def score_pct(self) -> float:
        if self.games_count == 0:
            return 0
        return ((self.wins + self.draws * 0.5) / self.games_count) * 100
    
    def to_dict(self) -> Dict:
        return {
            "games_count": self.games_count,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "win_rate": round(self.win_rate, 2),
            "score_pct": round(self.score_pct, 1),
            "avg_accuracy": round(self.avg_accuracy, 1),
            "blunders_per_game": round(self.blunders_per_game, 2),
            "mistakes_per_game": round(self.mistakes_per_game, 2),
            "avg_cp_loss": round(self.avg_cp_loss, 1),
            "openings_played": self.openings_played[:5],  # Top 5
        }


@dataclass
class EvolutionDelta:
    """Change between two windows"""
    accuracy_delta: float
    blunders_delta: float
    win_rate_delta: float
    trend: str  # "improving", "declining", "stable"
    confidence: str  # "high", "medium", "low" based on sample size
    
    def to_dict(self) -> Dict:
        return {
            "accuracy_delta": round(self.accuracy_delta, 1),
            "blunders_delta": round(self.blunders_delta, 2),
            "win_rate_delta": round(self.win_rate_delta, 2),
            "trend": self.trend,
            "confidence": self.confidence,
        }


def calculate_window_metrics(games: List[Dict], analyses: List[Dict]) -> WindowMetrics:
    """Calculate metrics for a window of games"""
    if not games:
        return WindowMetrics(
            games_count=0, wins=0, losses=0, draws=0,
            avg_accuracy=0, blunders_per_game=0, mistakes_per_game=0,
            avg_cp_loss=0, openings_played=[]
        )
    
    # Create analysis lookup
    analysis_map = {a.get("game_id"): a for a in analyses}
    
    wins = 0
    losses = 0
    draws = 0
    accuracies = []
    blunders = []
    mistakes = []
    cp_losses = []
    opening_counts = {}
    
    for game in games:
        game_id = game.get("game_id")
        analysis = analysis_map.get(game_id, {})
        user_color = game.get("user_color", "white")
        result = game.get("result", "")
        
        # Win/loss/draw
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
        
        # Accuracy - try multiple sources
        acc = analysis.get("accuracy")
        if not acc:
            acc = analysis.get("user_accuracy")
        if not acc:
            # Try stockfish_analysis
            sf = analysis.get("stockfish_analysis", {})
            acc = sf.get("accuracy")
        if acc is not None and acc > 0:
            accuracies.append(acc)
        
        # Blunders and mistakes
        b = analysis.get("blunders", 0)
        m = analysis.get("mistakes", 0)
        if isinstance(b, int):
            blunders.append(b)
        elif isinstance(b, list):
            blunders.append(len(b))
        if isinstance(m, int):
            mistakes.append(m)
        elif isinstance(m, list):
            mistakes.append(len(m))
        
        # Average CP loss
        cp = analysis.get("avg_cp_loss", analysis.get("average_cp_loss"))
        if cp is not None:
            cp_losses.append(cp)
        
        # Opening
        opening = game.get("opening_name", game.get("opening", "Unknown"))
        if opening:
            opening_counts[opening] = opening_counts.get(opening, 0) + 1
    
    # Sort openings by frequency
    sorted_openings = sorted(opening_counts.items(), key=lambda x: x[1], reverse=True)
    top_openings = [o[0] for o in sorted_openings]
    
    return WindowMetrics(
        games_count=len(games),
        wins=wins,
        losses=losses,
        draws=draws,
        avg_accuracy=sum(accuracies) / len(accuracies) if accuracies else 0,
        blunders_per_game=sum(blunders) / len(blunders) if blunders else 0,
        mistakes_per_game=sum(mistakes) / len(mistakes) if mistakes else 0,
        avg_cp_loss=sum(cp_losses) / len(cp_losses) if cp_losses else 0,
        openings_played=top_openings,
    )


def calculate_evolution_delta(recent: WindowMetrics, previous: WindowMetrics) -> EvolutionDelta:
    """Calculate the change between two windows"""
    if previous.games_count == 0 or recent.games_count == 0:
        return EvolutionDelta(
            accuracy_delta=0, blunders_delta=0, win_rate_delta=0,
            trend="insufficient_data", confidence="low"
        )
    
    accuracy_delta = recent.avg_accuracy - previous.avg_accuracy
    blunders_delta = recent.blunders_per_game - previous.blunders_per_game
    win_rate_delta = recent.win_rate - previous.win_rate
    
    # Determine trend
    score = 0
    if accuracy_delta > 2:
        score += 1
    elif accuracy_delta < -2:
        score -= 1
    
    if blunders_delta < -0.2:  # Fewer blunders
        score += 1
    elif blunders_delta > 0.2:
        score -= 1
    
    if win_rate_delta > 0.1:
        score += 1
    elif win_rate_delta < -0.1:
        score -= 1
    
    if score >= 2:
        trend = "improving"
    elif score <= -2:
        trend = "declining"
    else:
        trend = "stable"
    
    # Confidence based on sample size
    min_games = min(recent.games_count, previous.games_count)
    if min_games >= 10:
        confidence = "high"
    elif min_games >= 5:
        confidence = "medium"
    else:
        confidence = "low"
    
    return EvolutionDelta(
        accuracy_delta=accuracy_delta,
        blunders_delta=blunders_delta,
        win_rate_delta=win_rate_delta,
        trend=trend,
        confidence=confidence,
    )


async def get_rolling_evolution(db, user_id: str) -> Dict:
    """
    Get full rolling evolution data for a user.
    
    Returns metrics at three granularities:
    - macro: 25 vs 25 games
    - medium: 10 vs 10 games
    - micro: 5 vs 5 games
    
    This replaces the old baseline-based progress system.
    """
    # Get all games sorted by date
    games = await db.games.find(
        {"user_id": user_id}
    ).sort("imported_at", -1).to_list(100)
    
    # Get all analyses
    game_ids = [g.get("game_id") for g in games]
    analyses = await db.game_analyses.find(
        {"game_id": {"$in": game_ids}}
    ).to_list(len(game_ids))
    
    result = {
        "macro": {},
        "medium": {},
        "micro": {},
        "total_games": len(games),
    }
    
    # Macro: 25 vs 25
    if len(games) >= 30:  # Need at least 30 for meaningful macro
        recent_25 = games[:25]
        previous_25 = games[25:50]
        recent_metrics = calculate_window_metrics(recent_25, analyses)
        previous_metrics = calculate_window_metrics(previous_25, analyses)
        delta = calculate_evolution_delta(recent_metrics, previous_metrics)
        
        result["macro"] = {
            "window_size": 25,
            "recent": recent_metrics.to_dict(),
            "previous": previous_metrics.to_dict(),
            "delta": delta.to_dict(),
            "label": "Last 25 games vs previous 25",
        }
    
    # Medium: 10 vs 10
    if len(games) >= 15:
        recent_10 = games[:10]
        previous_10 = games[10:20]
        recent_metrics = calculate_window_metrics(recent_10, analyses)
        previous_metrics = calculate_window_metrics(previous_10, analyses)
        delta = calculate_evolution_delta(recent_metrics, previous_metrics)
        
        result["medium"] = {
            "window_size": 10,
            "recent": recent_metrics.to_dict(),
            "previous": previous_metrics.to_dict(),
            "delta": delta.to_dict(),
            "label": "Last 10 games vs previous 10",
        }
    
    # Micro: 5 vs 5
    if len(games) >= 8:
        recent_5 = games[:5]
        previous_5 = games[5:10]
        recent_metrics = calculate_window_metrics(recent_5, analyses)
        previous_metrics = calculate_window_metrics(previous_5, analyses)
        delta = calculate_evolution_delta(recent_metrics, previous_metrics)
        
        result["micro"] = {
            "window_size": 5,
            "recent": recent_metrics.to_dict(),
            "previous": previous_metrics.to_dict(),
            "delta": delta.to_dict(),
            "label": "Last 5 games vs previous 5",
        }
    
    # Overall assessment
    result["assessment"] = generate_evolution_assessment(result)
    
    return result


def generate_evolution_assessment(evolution_data: Dict) -> Dict:
    """Generate human-readable assessment from evolution data"""
    
    # Use medium window as primary (most balanced)
    medium = evolution_data.get("medium", {})
    delta = medium.get("delta", {})
    
    if not delta:
        return {
            "headline": "Play more games to see your evolution",
            "detail": "We need at least 15 games to show meaningful trends.",
            "trend": "insufficient_data",
        }
    
    trend = delta.get("trend", "stable")
    accuracy_delta = delta.get("accuracy_delta", 0)
    blunders_delta = delta.get("blunders_delta", 0)
    
    if trend == "improving":
        headline = "You're improving!"
        if accuracy_delta > 5:
            detail = f"Your accuracy is up {accuracy_delta:.0f}% in your last 10 games."
        elif blunders_delta < -0.5:
            detail = f"You're making {abs(blunders_delta):.1f} fewer blunders per game."
        else:
            detail = "Your overall play is getting sharper."
    
    elif trend == "declining":
        headline = "Let's work on this"
        if accuracy_delta < -5:
            detail = f"Accuracy dropped {abs(accuracy_delta):.0f}% - slow down on critical moves."
        elif blunders_delta > 0.5:
            detail = f"Blunders up {blunders_delta:.1f} per game - use the decision protocol."
        else:
            detail = "Results slipping - time for focused training."
    
    else:
        headline = "Steady progress"
        detail = "Your play is consistent. Focus on specific weak areas to break through."
    
    return {
        "headline": headline,
        "detail": detail,
        "trend": trend,
    }


async def get_phase_evolution(db, user_id: str) -> Dict:
    """
    Get evolution by game phase (opening, middlegame, endgame).
    
    Shows which phase is improving/declining.
    """
    # This would require tagged critical moments by phase
    # For now, return placeholder
    return {
        "opening": {"trend": "stable", "detail": "Opening accuracy consistent"},
        "middlegame": {"trend": "improving", "detail": "Tactical vision improving"},
        "endgame": {"trend": "needs_attention", "detail": "Endgame technique needs work"},
    }
