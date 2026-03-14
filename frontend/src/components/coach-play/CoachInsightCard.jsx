/**
 * CoachInsightCard - The CORE teaching element
 * 
 * One move → one insight → one next action
 * 
 * Structure:
 * 1) Reaction line (tiny emotional framing)
 * 2) Main insight (one sentence)
 * 3) Why it matters (one short sentence)
 * 4) Next idea (one short instruction)
 * 
 * Rules:
 * - Max 3 short text blocks
 * - No nested cards inside
 * - No trap explanation inside
 * - No opening tutorial inside
 * - No stats badges inside
 * - No engine notation inside by default
 */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { 
  ChevronDown, 
  ChevronUp,
  HelpCircle,
  Eye,
  Loader2
} from "lucide-react";

// Reaction emojis based on move quality
const REACTIONS = {
  excellent: { emoji: "🔥", text: "Excellent" },
  good: { emoji: "🙂", text: "Nice move" },
  interesting: { emoji: "🤔", text: "Interesting idea" },
  inaccuracy: { emoji: "🤔", text: "Interesting idea" },
  careful: { emoji: "⚠️", text: "Careful here" },
  mistake: { emoji: "⚠️", text: "Careful here" },
  blunder: { emoji: "😬", text: "Oh no" },
  neutral: { emoji: "👀", text: "Let's see" }
};

const CoachInsightCard = ({ 
  insight,
  isLoading = false,
  onAskWhy,
  onShowBetterMove,
  showActions = true,
  coachingMode = "intermediate"  // "beginner" | "intermediate" | "advanced"
}) => {
  const [expanded, setExpanded] = useState(false);
  
  // Mode-specific configuration
  const modeConfig = {
    beginner: {
      showReaction: true,
      showWhy: true,
      showNextIdea: true,
      autoExpand: true,       // Beginners get more info by default
      showEngineNotation: false
    },
    intermediate: {
      showReaction: true,
      showWhy: false,         // Click "Why?" to see
      showNextIdea: true,
      autoExpand: false,
      showEngineNotation: false
    },
    advanced: {
      showReaction: false,    // Advanced players just want the facts
      showWhy: false,
      showNextIdea: false,
      autoExpand: false,
      showEngineNotation: true  // Show engine evaluation
    }
  };
  
  const config = modeConfig[coachingMode] || modeConfig.intermediate;
  
  // Loading state - coach is analyzing
  if (isLoading) {
    return (
      <div className="p-4 rounded-lg bg-card border border-border">
        <div className="flex items-center gap-3">
          <div className="animate-pulse">
            <Loader2 className="w-5 h-5 animate-spin text-primary" />
          </div>
          <span className="text-sm text-muted-foreground">Coach analyzing...</span>
        </div>
      </div>
    );
  }
  
  // No insight yet - welcome state
  if (!insight) {
    return (
      <div className="p-4 rounded-lg bg-card border border-border">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="text-lg">🎯</span>
          <span>Make a move. I'll share my thoughts.</span>
        </div>
      </div>
    );
  }
  
  // Get reaction based on move quality
  const getReaction = () => {
    const quality = insight.quality?.toLowerCase() || "neutral";
    if (quality.includes("excellent") || quality.includes("brilliant")) return REACTIONS.excellent;
    if (quality.includes("good") || quality.includes("nice")) return REACTIONS.good;
    if (quality.includes("blunder")) return REACTIONS.blunder;
    if (quality.includes("mistake") || quality.includes("bad")) return REACTIONS.mistake;
    if (quality.includes("inaccurac")) return REACTIONS.inaccuracy;
    return REACTIONS.neutral;
  };
  
  const reaction = getReaction();
  
  return (
    <div className="rounded-lg bg-card border border-border overflow-hidden">
      {/* Main insight area */}
      <div className="p-4 space-y-3">
        {/* 1) Reaction line - configurable per mode */}
        {config.showReaction && (
          <div className="flex items-center gap-2">
            <span className="text-xl">{reaction.emoji}</span>
            <span className="text-sm font-medium text-muted-foreground">{reaction.text}</span>
          </div>
        )}
        
        {/* 2) Main insight - ONE sentence */}
        <p className="text-sm leading-relaxed">
          {insight.main_insight || insight.message}
        </p>
        
        {/* 3) Why it matters - if available and mode allows */}
        {insight.why && (config.showWhy || config.autoExpand) && (
          <p className="text-xs text-muted-foreground">
            {insight.why}
          </p>
        )}
        
        {/* 4) Next idea - the most important part (configurable) */}
        {insight.next_idea && config.showNextIdea && (
          <div className="pt-2 border-t border-border/50">
            <p className="text-sm">
              <span className="text-primary font-medium">Next idea:</span>{" "}
              {insight.next_idea}
            </p>
          </div>
        )}
        
        {/* Best move suggestion - when there was a better option */}
        {insight.has_better_move && insight.best_move && (
          <div className="pt-2 border-t border-border/50">
            <p className="text-sm text-amber-600 dark:text-amber-400">
              <span className="font-medium">Better was:</span> {insight.best_move}
              {insight.why && <span className="text-muted-foreground"> — {insight.why}</span>}
            </p>
          </div>
        )}
        
        {/* Encouragement */}
        {insight.encouragement && config.showReaction && (
          <p className="text-xs text-muted-foreground mt-2">
            {insight.encouragement}
          </p>
        )}
        
        {/* Advanced mode: Engine notation */}
        {config.showEngineNotation && insight.evaluation && (
          <div className="pt-2 text-xs font-mono text-muted-foreground">
            Eval: {typeof insight.evaluation === 'number' 
              ? (insight.evaluation > 0 ? '+' : '') + insight.evaluation.toFixed(2)
              : insight.evaluation}
          </div>
        )}
      </div>
      
      {/* Actions - contextual, not always shown */}
      {showActions && (insight.has_better_move || insight.can_explain) && (
        <div className="px-4 pb-4 flex gap-2">
          {insight.can_explain && onAskWhy && (
            <Button 
              variant="ghost" 
              size="sm" 
              className="h-7 text-xs"
              onClick={onAskWhy}
            >
              <HelpCircle className="w-3 h-3 mr-1" />
              Why?
            </Button>
          )}
          {insight.has_better_move && onShowBetterMove && (
            <Button 
              variant="ghost" 
              size="sm" 
              className="h-7 text-xs"
              onClick={onShowBetterMove}
            >
              <Eye className="w-3 h-3 mr-1" />
              Show better move
            </Button>
          )}
        </div>
      )}
      
      {/* Expandable deeper explanation - hidden by default */}
      {insight.deeper_explanation && (
        <>
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full px-4 py-2 text-xs text-muted-foreground hover:bg-muted/50 flex items-center justify-center gap-1 border-t border-border/50"
          >
            {expanded ? "Less" : "More details"}
            {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
          
          {expanded && (
            <div className="px-4 pb-4 text-xs text-muted-foreground space-y-2 border-t border-border/50 pt-3">
              {insight.deeper_explanation}
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default CoachInsightCard;
