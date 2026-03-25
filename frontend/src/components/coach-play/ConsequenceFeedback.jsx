/**
 * ConsequenceFeedback - Display feedback when user responds to a pedagogical move
 * 
 * Shows whether user found the opportunity and explains the consequence.
 */

import { CheckCircle2, XCircle, TrendingUp, TrendingDown, Lightbulb } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

const ConsequenceFeedback = ({ consequence, onDismiss }) => {
  if (!consequence) return null;
  
  const { 
    found_opportunity, 
    message, 
    eval_before, 
    eval_after, 
    eval_change,
    expected_move,
    user_move,
    opportunity_type
  } = consequence;
  
  const isPositive = found_opportunity;
  
  // Format opportunity type for display
  const formatOpportunityType = (type) => {
    const typeMap = {
      fork: "Fork",
      pin: "Pin",
      skewer: "Skewer",
      hanging_piece: "Hanging Piece",
      back_rank: "Back Rank",
      general: "Tactical",
    };
    return typeMap[type] || "Opportunity";
  };
  
  return (
    <Card 
      className={`${
        isPositive 
          ? "border-green-500/50 bg-green-900/20" 
          : "border-amber-500/50 bg-amber-900/20"
      } animate-in fade-in slide-in-from-top-2 duration-300`}
      data-testid="consequence-feedback"
    >
      <CardContent className="p-4">
        {/* Header */}
        <div className="flex items-center gap-2 mb-3">
          {isPositive ? (
            <CheckCircle2 className="h-5 w-5 text-green-400" />
          ) : (
            <XCircle className="h-5 w-5 text-amber-400" />
          )}
          <span className={`font-semibold ${isPositive ? "text-green-400" : "text-amber-400"}`}>
            {isPositive ? "You Found It!" : "Missed Opportunity"}
          </span>
          <span className="text-xs text-zinc-500 ml-auto">
            {formatOpportunityType(opportunity_type)}
          </span>
        </div>
        
        {/* Message */}
        <p className="text-sm text-zinc-300 mb-3">
          {message}
        </p>
        
        {/* Eval Change Indicator */}
        {eval_change !== undefined && (
          <div className={`flex items-center gap-2 text-sm ${
            eval_change >= 0 ? "text-green-400" : "text-red-400"
          }`}>
            {eval_change >= 0 ? (
              <TrendingUp className="h-4 w-4" />
            ) : (
              <TrendingDown className="h-4 w-4" />
            )}
            <span>
              Eval: {eval_before?.toFixed(1)} → {eval_after?.toFixed(1)} 
              ({eval_change >= 0 ? "+" : ""}{eval_change?.toFixed(1)})
            </span>
          </div>
        )}
        
        {/* Expected Move (if missed) */}
        {!isPositive && expected_move && (
          <div className="mt-3 p-2 rounded bg-zinc-800/50 flex items-center gap-2">
            <Lightbulb className="h-4 w-4 text-amber-400" />
            <span className="text-xs text-zinc-400">
              Better move: <span className="font-mono text-amber-300">{expected_move}</span>
            </span>
          </div>
        )}
        
        {/* Dismiss Button */}
        {onDismiss && (
          <button 
            onClick={onDismiss}
            className="mt-3 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            Dismiss
          </button>
        )}
      </CardContent>
    </Card>
  );
};

export default ConsequenceFeedback;
