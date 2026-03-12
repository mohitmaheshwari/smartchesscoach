/**
 * MoveFeedbackPanel - Comprehensive move feedback display
 * Shows detailed analysis of user's move and coach's response
 */

import { Badge } from "@/components/ui/badge";
import {
  Brain,
  CheckCircle2,
  Lightbulb,
  Target,
  Sparkles,
  ArrowRight
} from "lucide-react";

const MoveFeedbackPanel = ({ feedback, onDismiss }) => {
  if (!feedback) return null;
  
  const { 
    user_move, 
    user_move_quality, 
    best_move, 
    best_move_explanation,
    coach_move,
    coach_move_explanation,
    coaching_message,
    relates_to_weakness,
    encouragement,
    trap_suggestion
  } = feedback;
  
  // Quality colors
  const qualityColors = {
    excellent: "text-green-400 bg-green-500/10 border-green-500/30",
    good: "text-blue-400 bg-blue-500/10 border-blue-500/30",
    inaccuracy: "text-amber-400 bg-amber-500/10 border-amber-500/30",
    mistake: "text-orange-400 bg-orange-500/10 border-orange-500/30",
    blunder: "text-red-400 bg-red-500/10 border-red-500/30"
  };
  
  const qualityEmoji = {
    excellent: "🎯",
    good: "👍",
    inaccuracy: "🤔",
    mistake: "⚠️",
    blunder: "❌"
  };
  
  const isGoodMove = ["excellent", "good"].includes(user_move_quality);
  
  return (
    <div 
      className={`p-4 rounded-lg border ${qualityColors[user_move_quality] || qualityColors.inaccuracy}`}
      data-testid="move-feedback-panel"
    >
      {/* Header with move quality */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">{qualityEmoji[user_move_quality]}</span>
          <span className="font-semibold capitalize">{user_move_quality}</span>
          <Badge variant="outline" className="text-xs">
            {user_move}
          </Badge>
        </div>
        <button 
          onClick={onDismiss}
          className="text-muted-foreground hover:text-foreground text-xs"
        >
          Dismiss
        </button>
      </div>
      
      {/* Main coaching message */}
      <p className="text-sm mb-3">
        {coaching_message}
      </p>
      
      {/* Trap Suggestion - NEW! */}
      {trap_suggestion && trap_suggestion.moves_until_trap <= 3 && (
        <div className="mb-3 p-2 rounded bg-purple-500/10 border border-purple-500/30">
          <div className="flex items-center gap-2 text-xs mb-1">
            <Sparkles className="w-3 h-3 text-purple-400" />
            <span className="font-medium text-purple-400">
              Trap Alert: {trap_suggestion.name}
            </span>
          </div>
          <p className="text-xs text-muted-foreground pl-5 mb-2">
            {trap_suggestion.description}
          </p>
          {trap_suggestion.setup_remaining?.length > 0 && (
            <div className="pl-5 flex items-center gap-1 text-xs">
              <span className="text-purple-300">Play:</span>
              {trap_suggestion.setup_remaining.map((move, i) => (
                <span key={i} className="font-mono text-purple-400">
                  {move}{i < trap_suggestion.setup_remaining.length - 1 ? "," : ""}
                </span>
              ))}
              <ArrowRight className="w-3 h-3 text-purple-400 mx-1" />
              <span className="text-purple-300">then spring the trap!</span>
            </div>
          )}
        </div>
      )}
      
      {/* Best move explanation - only if move wasn't excellent */}
      {!isGoodMove && best_move && best_move !== user_move && (
        <div className="mb-3 p-2 rounded bg-background/50">
          <div className="flex items-center gap-2 text-xs mb-1">
            <Target className="w-3 h-3 text-primary" />
            <span className="font-medium text-primary">Best was {best_move}</span>
          </div>
          {best_move_explanation && (
            <p className="text-xs text-muted-foreground pl-5">
              {best_move_explanation}
            </p>
          )}
        </div>
      )}
      
      {/* Coach's response */}
      {coach_move && (
        <div className="p-2 rounded bg-background/50 mb-3">
          <div className="flex items-center gap-2 text-xs">
            <Brain className="w-3 h-3 text-primary" />
            <span className="font-medium">
              Coach played {coach_move}
            </span>
          </div>
          {coach_move_explanation && (
            <p className="text-xs text-muted-foreground pl-5 mt-1">
              {coach_move_explanation}
            </p>
          )}
        </div>
      )}
      
      {/* Personal feedback */}
      {relates_to_weakness && (
        <div className="text-xs text-amber-400 border-t border-border/50 pt-2 mt-2">
          <Lightbulb className="w-3 h-3 inline mr-1" />
          {relates_to_weakness}
        </div>
      )}
      
      {encouragement && isGoodMove && (
        <div className="text-xs text-green-400 border-t border-border/50 pt-2 mt-2">
          <CheckCircle2 className="w-3 h-3 inline mr-1" />
          {encouragement}
        </div>
      )}
    </div>
  );
};

export default MoveFeedbackPanel;
