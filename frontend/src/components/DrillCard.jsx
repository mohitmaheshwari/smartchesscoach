import { useState } from "react";
import { Button } from "@/components/ui/button";
import { 
  Play,
  Target,
  CheckCircle2,
  ChevronRight,
  Dumbbell
} from "lucide-react";

/**
 * DrillCard - Interactive drill position from the Plan tab
 * 
 * Shows a position where the user needs to find the correct move.
 * Links back to the user's own games for context.
 */
const DrillCard = ({ 
  drill, 
  index,
  onStartDrill,
  isCompleted = false 
}) => {
  const {
    id,
    fen,
    targetWeakness = "tactics",
    description = "Find the best move",
    difficulty = "medium",
    correctMoves = [],
    gameId,
    moveNumber,
    hint
  } = drill;

  const difficultyConfig = {
    easy: { color: "emerald", label: "Easy" },
    medium: { color: "amber", label: "Medium" },
    hard: { color: "red", label: "Hard" }
  };

  const config = difficultyConfig[difficulty] || difficultyConfig.medium;

  return (
    <div 
      className={`p-4 rounded-lg border transition-all ${
        isCompleted 
          ? 'border-emerald-500/30 bg-emerald-500/5' 
          : 'border-border/50 bg-background/50 hover:border-border'
      }`}
      data-testid={`drill-card-${index}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
            isCompleted 
              ? 'bg-emerald-500/20 text-emerald-400' 
              : 'bg-muted text-muted-foreground'
          }`}>
            {isCompleted ? <CheckCircle2 className="w-4 h-4" /> : index + 1}
          </div>
          <span className="text-sm font-medium">
            Drill {index + 1}
          </span>
        </div>
        
        {/* Difficulty Badge */}
        <span className={`px-2 py-0.5 rounded text-xs font-medium bg-${config.color}-500/20 text-${config.color}-400`}>
          {config.label}
        </span>
      </div>

      {/* Description */}
      <p className="text-sm text-muted-foreground mb-3">
        {description}
      </p>

      {/* Weakness Target */}
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-3">
        <Target className="w-3 h-3" />
        <span>Targets: {targetWeakness.replace(/_/g, ' ')}</span>
      </div>

      {/* Hint (optional) */}
      {hint && !isCompleted && (
        <div className="text-xs text-muted-foreground/70 italic mb-3 p-2 bg-muted/20 rounded">
          Hint: {hint}
        </div>
      )}

      {/* Source Game Reference */}
      {gameId && (
        <div className="text-xs text-muted-foreground/60 mb-3">
          From your game • Move {moveNumber}
        </div>
      )}

      {/* Action Button */}
      <Button
        variant={isCompleted ? "outline" : "default"}
        size="sm"
        className={`w-full gap-1.5 ${
          isCompleted 
            ? '' 
            : 'bg-blue-500 hover:bg-blue-600'
        }`}
        onClick={() => onStartDrill && onStartDrill(drill)}
        data-testid={`start-drill-${index}`}
      >
        {isCompleted ? (
          <>
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            Completed
          </>
        ) : (
          <>
            <Dumbbell className="w-3.5 h-3.5" />
            Start Drill
          </>
        )}
      </Button>
    </div>
  );
};

/**
 * OpeningLineDrill - Special drill for practicing opening lines
 */
export const OpeningLineDrill = ({ 
  opening, 
  moves = [], 
  onStartDrill,
  isCompleted = false 
}) => {
  return (
    <div 
      className={`p-4 rounded-lg border ${
        isCompleted 
          ? 'border-emerald-500/30 bg-emerald-500/5' 
          : 'border-blue-500/30 bg-blue-500/5'
      }`}
      data-testid="opening-line-drill"
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Play className="w-4 h-4 text-blue-400" />
          <span className="text-sm font-medium">Opening Line</span>
        </div>
        {isCompleted && (
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
        )}
      </div>

      <h4 className="font-semibold mb-1">{opening?.name || "Your Opening"}</h4>
      
      {/* Show first few moves */}
      <div className="text-sm font-mono text-muted-foreground mb-3">
        {moves.slice(0, 6).map((m, i) => (
          <span key={i}>
            {i % 2 === 0 && <span className="text-muted-foreground/50">{Math.floor(i/2) + 1}.</span>}
            {m}{' '}
          </span>
        ))}
        {moves.length > 6 && <span>...</span>}
      </div>

      <Button
        variant={isCompleted ? "outline" : "default"}
        size="sm"
        className={`w-full gap-1.5 ${isCompleted ? '' : 'bg-blue-500 hover:bg-blue-600'}`}
        onClick={() => onStartDrill && onStartDrill({ type: 'opening', moves, opening })}
      >
        {isCompleted ? (
          <>
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            Line Memorized
          </>
        ) : (
          <>
            <Play className="w-3.5 h-3.5" />
            Practice Line
          </>
        )}
      </Button>
    </div>
  );
};

/**
 * HabitCard - Shows a habit to focus on with linked drill
 */
export const HabitCard = ({ 
  habit, 
  onDrillClick,
  index = 0 
}) => {
  const { name, description, drillId, isActive = false } = habit;

  return (
    <div 
      className={`p-3 rounded-lg border ${
        isActive 
          ? 'border-amber-500/40 bg-amber-500/5' 
          : 'border-border/30 bg-background/50'
      }`}
      data-testid={`habit-card-${index}`}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <Target className={`w-4 h-4 ${isActive ? 'text-amber-400' : 'text-muted-foreground'}`} />
            <span className="text-sm font-medium">{name}</span>
          </div>
          <p className="text-xs text-muted-foreground">
            {description}
          </p>
        </div>
        
        {drillId && (
          <Button
            variant="ghost"
            size="sm"
            className="text-xs"
            onClick={() => onDrillClick && onDrillClick(drillId)}
          >
            <ChevronRight className="w-4 h-4" />
          </Button>
        )}
      </div>
    </div>
  );
};

export default DrillCard;
