import { useState } from "react";
import { Button } from "@/components/ui/button";
import { 
  Eye, 
  Target,
  TrendingDown,
  AlertTriangle,
  Zap,
  Clock,
  ChevronDown,
  ChevronUp,
  Lightbulb
} from "lucide-react";

/**
 * KeyMomentCard - Shows a critical teaching moment with GM-style coaching
 * 
 * This is NOT just showing data - it EXPLAINS:
 * 1. What went wrong (the mistake)
 * 2. Why it's wrong (the principle violated)
 * 3. What to do instead (the correction)
 * 4. How to think (the lesson)
 */
const KeyMomentCard = ({ 
  moment, 
  onViewOnBoard, 
  onTryAgain,
  isActive = false 
}) => {
  const [expanded, setExpanded] = useState(false);
  
  const {
    label = "Key Moment",
    moveNumber,
    move,
    evalSwing = 0,
    fen,
    category = "tactical",
    description = "",
    bestMove,
    bestMoveExplanation,
    coachExplanation,
    thinkingError,
    lesson
  } = moment;

  // Generate coach explanation if not provided
  const generateCoachExplanation = () => {
    // If we have a custom explanation, use it
    if (coachExplanation) return coachExplanation;
    
    // Otherwise generate based on category and data
    const explanations = {
      hanging_piece: {
        whatWentWrong: `You played ${move}, but your piece was left undefended.`,
        whyItMatters: "Before moving ANY piece, always ask: 'Will my piece be safe on this square?' This is the #1 rule at every level.",
        thinkingError: "You moved without checking if the destination square was attacked.",
        correction: bestMove ? `${bestMove} keeps all your pieces protected.` : "Look for a move that doesn't leave pieces hanging."
      },
      advantage_collapse: {
        whatWentWrong: `You had a winning position, but ${move} let your opponent back in the game.`,
        whyItMatters: "When ahead, simplify! Trade pieces, don't complicate. A smaller advantage that's easy to convert beats a big advantage you might blunder.",
        thinkingError: "You got ambitious when you should have played safe.",
        correction: bestMove ? `${bestMove} maintains your advantage while keeping things simple.` : "Look for trades that keep your advantage."
      },
      tactical_miss: {
        whatWentWrong: `${move} missed a tactical opportunity.`,
        whyItMatters: "Before every move, scan for Checks, Captures, and Threats (CCT) - both yours AND your opponent's.",
        thinkingError: "You didn't scan for all tactical possibilities in the position.",
        correction: bestMove ? `${bestMove} was the tactical shot.` : "Take an extra 10 seconds to look for forcing moves."
      },
      time_pressure: {
        whatWentWrong: `Under time pressure, ${move} was a costly mistake.`,
        whyItMatters: "In time trouble, play solid moves you can calculate quickly. Don't try to find the 'best' move - find a SAFE move.",
        thinkingError: "Time pressure led to a hasty decision.",
        correction: bestMove ? `${bestMove} was simpler and safer.` : "When low on time, prioritize piece safety over finding brilliancies."
      },
      positional: {
        whatWentWrong: `${move} weakened your position.`,
        whyItMatters: "Every pawn move creates permanent weaknesses. Every piece retreat loses tempo. Think twice before these commitments.",
        thinkingError: "You didn't consider the long-term consequences of this move.",
        correction: bestMove ? `${bestMove} maintains a healthier position.` : "Consider how each move affects your pawn structure and piece coordination."
      }
    };
    
    return explanations[category] || explanations.tactical_miss;
  };

  const explanation = generateCoachExplanation();

  // Category icons and colors
  const categoryConfig = {
    hanging_piece: { icon: AlertTriangle, color: "red", bgClass: "bg-red-500/20", textClass: "text-red-400", borderClass: "border-red-500/50" },
    advantage_collapse: { icon: TrendingDown, color: "orange", bgClass: "bg-orange-500/20", textClass: "text-orange-400", borderClass: "border-orange-500/50" },
    tactical_miss: { icon: Zap, color: "amber", bgClass: "bg-amber-500/20", textClass: "text-amber-400", borderClass: "border-amber-500/50" },
    time_pressure: { icon: Clock, color: "blue", bgClass: "bg-blue-500/20", textClass: "text-blue-400", borderClass: "border-blue-500/50" },
    positional: { icon: Target, color: "purple", bgClass: "bg-purple-500/20", textClass: "text-purple-400", borderClass: "border-purple-500/50" },
    default: { icon: AlertTriangle, color: "slate", bgClass: "bg-slate-500/20", textClass: "text-slate-400", borderClass: "border-slate-500/50" }
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
      className={`rounded-lg border transition-all overflow-hidden ${
        isActive 
          ? `${config.borderClass} bg-zinc-900/80` 
          : 'border-border/50 bg-background/50 hover:border-border'
      }`}
      data-testid={`key-moment-${moveNumber}`}
    >
      {/* Header - Always visible */}
      <div className="p-4">
        <div className="flex items-start justify-between mb-2">
          <div className="flex items-center gap-2">
            <div className={`p-1.5 rounded ${config.bgClass}`}>
              <IconComponent className={`w-4 h-4 ${config.textClass}`} />
            </div>
            <div>
              <span className="text-sm font-semibold">{label}</span>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span>Move {moveNumber}</span>
                {move && <span className="font-mono bg-muted/50 px-1 rounded">{move}</span>}
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

        {/* Coach Explanation - The Key Part! */}
        <div className="space-y-2 mb-3">
          {/* What went wrong */}
          <p className="text-sm">
            {explanation.whatWentWrong || description}
          </p>
          
          {/* Why it matters - The Lesson */}
          <div className="flex items-start gap-2 p-2 rounded bg-amber-500/10 border border-amber-500/20">
            <Lightbulb className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
            <p className="text-xs text-amber-200/90">
              {explanation.whyItMatters}
            </p>
          </div>
        </div>

        {/* Expand for more details */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors mb-3"
        >
          {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          {expanded ? "Less details" : "More details"}
        </button>

        {/* Expanded content */}
        {expanded && (
          <div className="space-y-2 mb-3 pl-2 border-l-2 border-muted/50">
            {/* Thinking Error */}
            {explanation.thinkingError && (
              <div className="text-xs">
                <span className="text-muted-foreground">The thinking error: </span>
                <span className="text-foreground">{explanation.thinkingError}</span>
              </div>
            )}
            
            {/* Better Move */}
            {bestMove && (
              <div className="text-xs">
                <span className="text-muted-foreground">Better was: </span>
                <span className="font-mono text-emerald-400">{bestMove}</span>
                {bestMoveExplanation && (
                  <span className="text-muted-foreground"> - {bestMoveExplanation}</span>
                )}
              </div>
            )}
            
            {/* Correction */}
            {explanation.correction && (
              <div className="text-xs">
                <span className="text-muted-foreground">Correction: </span>
                <span className="text-foreground">{explanation.correction}</span>
              </div>
            )}
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
            View Position
          </Button>
          <Button
            variant="default"
            size="sm"
            className="flex-1 gap-1.5 bg-amber-500 hover:bg-amber-600 text-black"
            onClick={() => onTryAgain && onTryAgain(moment)}
            data-testid={`try-moment-${moveNumber}`}
          >
            <Target className="w-3.5 h-3.5" />
            Try Again
          </Button>
        </div>
      </div>
    </div>
  );
};

export default KeyMomentCard;
