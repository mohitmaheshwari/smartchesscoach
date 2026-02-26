/**
 * CoachGameReviewCard
 * Shows when a new game has been analyzed - prompts for review
 * Only displayed when last_game.is_new is true
 */

import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { 
  BarChart3, 
  ChevronRight, 
  AlertTriangle,
  CheckCircle2,
  Minus
} from "lucide-react";
import { Button } from "@/components/ui/button";

const CoachGameReviewCard = ({ lastGame, auditData }) => {
  const navigate = useNavigate();
  
  if (!lastGame) return null;
  
  const { game_id, result, opponent, blunders, mistakes } = lastGame;
  
  // Determine outcome color
  const resultColors = {
    win: "text-emerald-500",
    loss: "text-red-500",
    draw: "text-muted-foreground",
    unknown: "text-muted-foreground",
  };
  
  const resultLabels = {
    win: "Won",
    loss: "Lost",
    draw: "Drew",
    unknown: "Played",
  };
  
  const resultColor = resultColors[result] || resultColors.unknown;
  const resultLabel = resultLabels[result] || "Played";
  
  // Quality assessment
  const hasIssues = blunders > 0 || mistakes >= 2;
  const isClean = blunders === 0 && mistakes <= 1;
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`rounded-xl border bg-card p-5 ${
        hasIssues ? "border-amber-500/30" : "border-border"
      }`}
      data-testid="coach-game-review-card"
    >
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-muted-foreground" />
            <span className="text-sm font-medium text-muted-foreground">
              Last Game
            </span>
          </div>
          <span className={`text-sm font-medium ${resultColor}`}>
            {resultLabel} vs {opponent || "Opponent"}
          </span>
        </div>
        
        {/* Quick Stats */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            {blunders > 0 ? (
              <AlertTriangle className="w-4 h-4 text-red-500" />
            ) : (
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
            )}
            <span className="text-sm">
              {blunders} blunder{blunders !== 1 ? "s" : ""}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {mistakes >= 2 ? (
              <AlertTriangle className="w-4 h-4 text-amber-500" />
            ) : (
              <Minus className="w-4 h-4 text-muted-foreground" />
            )}
            <span className="text-sm">
              {mistakes} mistake{mistakes !== 1 ? "s" : ""}
            </span>
          </div>
        </div>
        
        {/* Coach Message */}
        <div className={`p-3 rounded-lg ${
          isClean ? "bg-emerald-500/5 border border-emerald-500/20" : 
          hasIssues ? "bg-amber-500/5 border border-amber-500/20" : 
          "bg-muted/30"
        }`}>
          <p className="text-sm">
            {isClean 
              ? "Clean game. Good discipline. Keep it up." 
              : hasIssues && blunders > 0
              ? `There's something to learn from this game. Let's look at what happened.`
              : "Solid play overall. A few moments worth reviewing."}
          </p>
        </div>
        
        {/* CTA */}
        <Button 
          variant={hasIssues ? "default" : "outline"}
          className="w-full"
          onClick={() => navigate(`/game/${game_id}`)}
          data-testid="review-game-btn"
        >
          Review This Game
          <ChevronRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </motion.div>
  );
};

export default CoachGameReviewCard;
