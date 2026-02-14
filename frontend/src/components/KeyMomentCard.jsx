import { useState } from "react";
import { Button } from "@/components/ui/button";
import { 
  Eye, 
  Target,
  TrendingDown,
  AlertTriangle,
  Zap,
  Clock
} from "lucide-react";

/**
 * KeyMomentCard - Shows a critical teaching moment from the game
 * 
 * Each card represents a mistake that cost evaluation points.
 * User can "View on Board" to see the position or "Try Again" for a mini-drill.
 */
const KeyMomentCard = ({ 
  moment, 
  onViewOnBoard, 
  onTryAgain,
  isActive = false 
}) => {
  const {
    label = "Key Moment",
    moveNumber,
    move,
    evalSwing = 0,
    fen,
    category = "tactical",
    description = "",
    bestMove,
    bestMoveExplanation
  } = moment;

  // Category icons and colors
  const categoryConfig = {
    hanging_piece: { icon: AlertTriangle, color: "red", label: "Hanging Piece" },
    advantage_collapse: { icon: TrendingDown, color: "orange", label: "Lost Advantage" },
    tactical_miss: { icon: Zap, color: "amber", label: "Missed Tactic" },
    time_pressure: { icon: Clock, color: "blue", label: "Time Trouble" },
    positional: { icon: Target, color: "purple", label: "Positional Error" },
    default: { icon: AlertTriangle, color: "slate", label: "Key Moment" }
  };

  const config = categoryConfig[category] || categoryConfig.default;
  const IconComponent = config.icon;

  // Format eval swing (negative = lost points)
  const formatEvalSwing = (swing) => {
    const pawns = Math.abs(swing / 100).toFixed(1);
    return swing < 0 ? `-${pawns}` : `+${pawns}`;
  };

  return (
    <div 
      className={`p-4 rounded-lg border transition-all ${
        isActive 
          ? `border-${config.color}-500/50 bg-${config.color}-500/10` 
          : 'border-border/50 bg-background/50 hover:border-border'
      }`}
      data-testid={`key-moment-${moveNumber}`}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={`p-1.5 rounded bg-${config.color}-500/20`}>
            <IconComponent className={`w-4 h-4 text-${config.color}-400`} />
          </div>
          <div>
            <span className="text-sm font-medium">{label}</span>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>Move {moveNumber}</span>
              {move && <span className="font-mono">{move}</span>}
            </div>
          </div>
        </div>
        
        {/* Eval Swing Badge */}
        {evalSwing !== 0 && (
          <div className={`px-2 py-0.5 rounded text-xs font-bold ${
            evalSwing < -200 ? 'bg-red-500/20 text-red-400' :
            evalSwing < -100 ? 'bg-orange-500/20 text-orange-400' :
            evalSwing < 0 ? 'bg-amber-500/20 text-amber-400' :
            'bg-muted text-muted-foreground'
          }`}>
            {formatEvalSwing(evalSwing)}
          </div>
        )}
      </div>

      {/* Description */}
      {description && (
        <p className="text-sm text-muted-foreground mb-3">
          {description}
        </p>
      )}

      {/* Best Move Hint (collapsed by default) */}
      {bestMove && (
        <div className="text-xs text-muted-foreground mb-3 p-2 bg-muted/30 rounded">
          <span className="font-medium">Better:</span> {bestMove}
          {bestMoveExplanation && <span> - {bestMoveExplanation}</span>}
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          className="flex-1 gap-1.5"
          onClick={() => onViewOnBoard && onViewOnBoard(moment)}
          data-testid={`view-moment-${moveNumber}`}
        >
          <Eye className="w-3.5 h-3.5" />
          View
        </Button>
        <Button
          variant="default"
          size="sm"
          className="flex-1 gap-1.5 bg-amber-500 hover:bg-amber-600"
          onClick={() => onTryAgain && onTryAgain(moment)}
          data-testid={`try-moment-${moveNumber}`}
        >
          <Target className="w-3.5 h-3.5" />
          Try Again
        </Button>
      </div>
    </div>
  );
};

export default KeyMomentCard;
