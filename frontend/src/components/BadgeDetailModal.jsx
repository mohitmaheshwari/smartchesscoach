import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Chessboard } from "react-chessboard";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Loader2,
  X,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  CheckCircle2,
  Target,
  Swords,
  Brain,
  Crown,
  Shield,
  Trophy,
  Eye,
  Clock,
  ExternalLink
} from "lucide-react";

// Badge icon mapping
const BADGE_ICONS = {
  opening: Target,
  tactical: Swords,
  positional: Brain,
  endgame: Crown,
  defense: Shield,
  converting: Trophy,
  focus: Eye,
  time: Clock
};

// Star rating component
const StarRating = ({ score, size = "lg" }) => {
  const fullStars = Math.floor(score);
  const hasHalf = score - fullStars >= 0.3 && score - fullStars < 0.8;
  const sizeClass = size === "lg" ? "text-xl" : "text-base";
  
  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <span 
          key={star} 
          className={`${sizeClass} ${
            star <= fullStars 
              ? "text-yellow-500" 
              : star === fullStars + 1 && hasHalf 
                ? "text-yellow-500/50" 
                : "text-gray-300 dark:text-gray-600"
          }`}
        >
          ★
        </span>
      ))}
      <span className="ml-2 text-lg font-bold">{score.toFixed(1)}</span>
    </div>
  );
};

// Single game card with board and moves
const GameCard = ({ game, badgeKey, onViewGame }) => {
  const [expanded, setExpanded] = useState(false);
  const [selectedMove, setSelectedMove] = useState(game.moves?.[0] || null);
  
  const getMoveTypeColor = (type) => {
    switch(type) {
      case "mistake":
      case "missed":
      case "positional_error":
      case "endgame_error":
      case "defensive_collapse":
      case "threw_advantage":
      case "focus_error":
      case "time_trouble_blunder":
        return "text-red-500 bg-red-500/10 border-red-500/30";
      case "good":
      case "found":
      case "good_positional":
      case "good_defense":
        return "text-green-500 bg-green-500/10 border-green-500/30";
      default:
        return "text-muted-foreground bg-muted border-border";
    }
  };

  const getMoveTypeLabel = (type) => {
    switch(type) {
      case "mistake": return "Opening Mistake";
      case "missed": return "Missed Tactic";
      case "found": return "Found Tactic!";
      case "positional_error": return "Positional Error";
      case "good_positional": return "Good Position";
      case "endgame_error": return "Endgame Error";
      case "defensive_collapse": return "Defense Failed";
      case "good_defense": return "Good Defense";
      case "threw_advantage": return "Threw Advantage";
      case "focus_error": return "Focus Error";
      case "time_trouble_blunder": return "Time Trouble";
      default: return type;
    }
  };

  const hasPositiveMoves = game.moves?.some(m => 
    ["found", "good", "good_positional", "good_defense"].includes(m.type)
  );
  const hasNegativeMoves = game.moves?.some(m => 
    ["mistake", "missed", "positional_error", "endgame_error", "defensive_collapse", "threw_advantage", "focus_error", "time_trouble_blunder"].includes(m.type)
  );

  return (
    <Card className="overflow-hidden border">
      <div 
        className="p-4 cursor-pointer hover:bg-muted/50 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
              game.converted === false ? "bg-red-500/20 text-red-500" :
              game.saved_game ? "bg-green-500/20 text-green-500" :
              hasNegativeMoves && !hasPositiveMoves ? "bg-red-500/20 text-red-500" :
              "bg-amber-500/20 text-amber-500"
            }`}>
              {game.converted === false || (hasNegativeMoves && !hasPositiveMoves) ? (
                <AlertTriangle className="w-4 h-4" />
              ) : game.saved_game ? (
                <CheckCircle2 className="w-4 h-4" />
              ) : (
                <Target className="w-4 h-4" />
              )}
            </div>
            <div>
              <p className="font-medium text-sm">vs {game.opponent}</p>
              <p className="text-xs text-muted-foreground">
                {game.result} • {game.moves?.length || 0} notable moments
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {game.was_winning && !game.converted && (
              <span className="text-xs px-2 py-0.5 rounded bg-red-500/10 text-red-500">
                Thrown
              </span>
            )}
            {game.saved_game && (
              <span className="text-xs px-2 py-0.5 rounded bg-green-500/10 text-green-500">
                Saved
              </span>
            )}
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </div>
      </div>
      
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="p-4 pt-0 border-t">
              {game.moves && game.moves.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Chess Board */}
                  <div className="flex flex-col items-center">
                    <div className="w-full max-w-[280px] aspect-square rounded-lg overflow-hidden border">
                      <Chessboard 
                        position={selectedMove?.fen || "start"}
                        boardWidth={280}
                        arePiecesDraggable={false}
                        customBoardStyle={{
                          borderRadius: "4px"
                        }}
                      />
                    </div>
                    {selectedMove && (
                      <div className="mt-2 text-center">
                        <p className="text-sm font-medium">
                          Move {selectedMove.move_number}: {selectedMove.move_played}
                        </p>
                        {selectedMove.best_move && selectedMove.move_played !== selectedMove.best_move && (
                          <p className="text-xs text-muted-foreground">
                            Best: <span className="text-green-500 font-medium">{selectedMove.best_move}</span>
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                  
                  {/* Moves List */}
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-muted-foreground mb-2">
                      Key Moments:
                    </p>
                    {game.moves.map((move, idx) => (
                      <div
                        key={idx}
                        onClick={() => setSelectedMove(move)}
                        className={`p-3 rounded-lg border cursor-pointer transition-all ${
                          selectedMove === move 
                            ? "ring-2 ring-amber-500 " + getMoveTypeColor(move.type)
                            : getMoveTypeColor(move.type) + " hover:opacity-80"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-medium">
                            Move {move.move_number}
                          </span>
                          <span className="text-xs px-2 py-0.5 rounded-full bg-background">
                            {getMoveTypeLabel(move.type)}
                          </span>
                        </div>
                        <p className="text-xs opacity-80 line-clamp-2">
                          {move.explanation}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No specific moves to highlight for this badge
                </p>
              )}
              
              {/* View Full Game Button */}
              <div className="mt-4 pt-4 border-t">
                <Button 
                  variant="outline" 
                  size="sm"
                  className="w-full"
                  onClick={(e) => {
                    e.stopPropagation();
                    onViewGame(game.game_id, badgeKey);
                  }}
                >
                  View Full Game Analysis
                  <ExternalLink className="w-3 h-3 ml-2" />
                </Button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
};

const BadgeDetailModal = ({ isOpen, onClose, badgeKey, badgeName }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  
  const Icon = BADGE_ICONS[badgeKey] || Target;

  useEffect(() => {
    if (isOpen && badgeKey) {
      fetchBadgeDetails();
    }
  }, [isOpen, badgeKey]);

  const fetchBadgeDetails = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(`${API}/badges/${badgeKey}/details`, {
        credentials: "include"
      });
      
      if (!response.ok) {
        throw new Error("Failed to fetch badge details");
      }
      
      const result = await response.json();
      setData(result);
    } catch (err) {
      console.error("Badge details fetch error:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleViewGame = (gameId, focus) => {
    onClose();
    navigate(`/game/${gameId}?focus=${focus}`);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="badge-detail-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-amber-500/20">
              <Icon className="w-5 h-5 text-amber-500" />
            </div>
            <div>
              <span className="block">{data?.badge_name || badgeName}</span>
              <span className="text-sm font-normal text-muted-foreground">
                {data?.badge_description}
              </span>
            </div>
          </DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
          </div>
        ) : error ? (
          <div className="text-center py-8">
            <AlertTriangle className="w-10 h-10 text-red-500 mx-auto mb-3" />
            <p className="text-muted-foreground">{error}</p>
            <Button variant="outline" className="mt-4" onClick={fetchBadgeDetails}>
              Retry
            </Button>
          </div>
        ) : data ? (
          <div className="space-y-6">
            {/* Score and Why */}
            <div className="p-4 rounded-lg bg-muted/50 border">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium">Your Score</span>
                <StarRating score={data.score || 2.5} />
              </div>
              <div className="p-3 rounded bg-background">
                <p className="text-sm font-medium mb-1">Why this score?</p>
                <p className="text-sm text-muted-foreground">
                  {data.why_this_score}
                </p>
              </div>
            </div>

            {/* Summary Stats */}
            {data.summary && (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {Object.entries(data.summary).map(([key, value]) => (
                  <div key={key} className="p-3 rounded-lg bg-muted/30 text-center">
                    <p className="text-2xl font-bold">{typeof value === "boolean" ? (value ? "Yes" : "No") : value}</p>
                    <p className="text-xs text-muted-foreground capitalize">
                      {key.replace(/_/g, " ")}
                    </p>
                  </div>
                ))}
              </div>
            )}

            {/* Insight */}
            {data.insight && (
              <div className="p-4 rounded-lg border border-amber-500/30 bg-amber-500/5">
                <p className="text-sm">{data.insight}</p>
              </div>
            )}

            {/* Relevant Games */}
            <div>
              <h3 className="text-sm font-medium mb-3 flex items-center gap-2">
                <span>Games That Affected This Score</span>
                <span className="text-xs text-muted-foreground">
                  ({data.relevant_games?.length || 0} games)
                </span>
              </h3>
              
              {data.relevant_games && data.relevant_games.length > 0 ? (
                <div className="space-y-3">
                  {data.relevant_games.map((game, idx) => (
                    <GameCard 
                      key={game.game_id || idx} 
                      game={game} 
                      badgeKey={badgeKey}
                      onViewGame={handleViewGame}
                    />
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <p>No specific games to show yet.</p>
                  <p className="text-sm">Analyze more games for detailed insights.</p>
                </div>
              )}
            </div>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
};

export default BadgeDetailModal;
