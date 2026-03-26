/**
 * V5CoachingCard.jsx - Shared Coaching Component
 * 
 * This is the SINGLE source of truth for V5 coaching UI.
 * Used by BOTH:
 * - Lab (Game Decryption) - analyzing past games
 * - Play with Coach - live coaching during play
 * 
 * Features:
 * - Fun language (Horsey, Naughty Knight, Slicey Boi)
 * - Specific consequences (not generic)
 * - Clickable candidate moves from Stockfish
 * - Transferable learning / Golden Rules
 * - "I understand" button
 * 
 * This ensures: Improve one place → Both pages look better!
 */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  AlertTriangle,
  CheckCircle2,
  Lightbulb,
  GraduationCap,
  Trophy,
  Zap,
  Target,
  ArrowRight,
  Check,
  Swords,
  Eye
} from "lucide-react";
import { FlagMoveButton } from "@/components/shared/FlagMoveDialog";

// Severity colors and icons
const SEVERITY_CONFIG = {
  brilliant: { color: "cyan", icon: Zap, label: "Brilliant!" },
  great: { color: "emerald", icon: CheckCircle2, label: "Great move" },
  good: { color: "green", icon: CheckCircle2, label: "Good move" },
  book: { color: "blue", icon: CheckCircle2, label: "Book move" },
  context: { color: "zinc", icon: Eye, label: "Opponent's move" },
  inaccuracy: { color: "yellow", icon: AlertTriangle, label: "Inaccuracy" },
  mistake: { color: "orange", icon: AlertTriangle, label: "Mistake" },
  blunder: { color: "red", icon: AlertTriangle, label: "Blunder" }
};

// Move type colors for candidate moves
const MOVE_TYPE_COLORS = {
  counter_attack: "text-orange-400 border-orange-500/30",
  prophylactic: "text-purple-400 border-purple-500/30",
  development: "text-blue-400 border-blue-500/30",
  central: "text-yellow-400 border-yellow-500/30",
  tactical: "text-red-400 border-red-500/30",
  king_safety: "text-emerald-400 border-emerald-500/30",
  positional: "text-cyan-400 border-cyan-500/30",
  engine_choice: "text-zinc-400 border-zinc-500/30"
};

/**
 * Main V5 Coaching Card Component
 */
const V5CoachingCard = ({
  coaching,                    // V5Coaching object from backend
  moveSan,                     // The move in SAN notation
  moveNumber,                  // Move number for display
  onShowAlternativeMove,       // Callback to show a move on the board
  onAcknowledge,               // Callback when user clicks "I understand"
  isAcknowledged = false,      // Whether concept is already acknowledged
  showAcknowledgeButton = true, // Whether to show "I understand" button
  compact = false,             // Compact mode for live coaching
  gameId = null,               // Game ID for feedback
  sessionId = null,            // Session ID for feedback (coach mode)
  source = "lab",              // "lab" or "coach" for feedback source
}) => {
  const [acknowledging, setAcknowledging] = useState(false);
  
  if (!coaching) return null;
  
  const severity = coaching.severity || "context";
  const config = SEVERITY_CONFIG[severity] || SEVERITY_CONFIG.context;
  const SeverityIcon = config.icon;
  
  const isGoodMove = ["brilliant", "great", "good", "book"].includes(severity);
  const isMistake = ["inaccuracy", "mistake", "blunder"].includes(severity);
  const isOpponentMove = severity === "context";
  
  // Handle acknowledge click
  const handleAcknowledge = async () => {
    if (!onAcknowledge || !coaching.concept_id) return;
    setAcknowledging(true);
    try {
      await onAcknowledge(coaching.concept_id);
    } finally {
      setAcknowledging(false);
    }
  };
  
  return (
    <div 
      className={`rounded-xl border ${
        isGoodMove ? 'bg-emerald-500/5 border-emerald-500/20' :
        isMistake ? 'bg-red-500/5 border-red-500/20' :
        'bg-zinc-800/50 border-zinc-700/50'
      }`}
      data-testid="v5-coaching-card"
    >
      {/* Header - Clear indication this is about YOUR move */}
      <div className={`px-4 py-3 border-b ${
        isGoodMove ? 'border-emerald-500/20' :
        isMistake ? 'border-red-500/20' :
        'border-zinc-700/50'
      }`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xs text-zinc-500 uppercase tracking-wide">Your move</span>
            <span className="font-mono font-bold text-lg text-white">
              {moveSan}
            </span>
            <Badge 
              variant="outline" 
              className={`text-${config.color}-400 border-${config.color}-500/30`}
            >
              <SeverityIcon className="w-3 h-3 mr-1" />
              {config.label}
            </Badge>
          </div>
          {coaching.best_move && coaching.best_move !== moveSan && (
            <span className="text-xs text-zinc-400">
              Best: <span className="text-emerald-400 font-mono">{coaching.best_move}</span>
            </span>
          )}
          <FlagMoveButton
            source={source}
            gameId={gameId}
            sessionId={sessionId}
            moveNumber={moveNumber}
            fen={coaching.fen_before || ""}
            moveSan={moveSan}
            coachingText={coaching.narrative}
          />
        </div>
      </div>
      
      {/* Content */}
      <div className="p-4 space-y-4">
        {/* Main Narrative */}
        <p className={`text-sm ${
          isGoodMove ? 'text-emerald-300' :
          isMistake ? 'text-white' :
          'text-zinc-300'
        }`}>
          {coaching.narrative}
        </p>
        
        {/* Opponent Move: Your Plan Now */}
        {isOpponentMove && coaching.your_plan_now && (
          <div className="bg-blue-500/10 rounded-lg p-3 border border-blue-500/20">
            <p className="text-xs text-blue-400 mb-1 flex items-center gap-1">
              <Target className="w-3 h-3" /> Your plan now
            </p>
            <p className="text-white text-sm">{coaching.your_plan_now}</p>
          </div>
        )}
        
        {/* Mistake Details */}
        {isMistake && (
          <>
            {/* Problem */}
            {coaching.current_problem && (
              <div className="bg-red-500/10 rounded-lg p-3 border border-red-500/20">
                <p className="text-xs text-red-400 mb-1">The problem</p>
                <p className="text-white text-sm">{coaching.current_problem}</p>
              </div>
            )}
            
            {/* Consequence */}
            {coaching.consequence && (
              <div className="bg-orange-500/10 rounded-lg p-3 border border-orange-500/20">
                <p className="text-xs text-orange-400 mb-1 flex items-center gap-1">
                  <ArrowRight className="w-3 h-3" /> What happens next
                </p>
                <p className="text-white text-sm">{coaching.consequence}</p>
              </div>
            )}
            
            {/* Better Approach */}
            {coaching.better_approach && (
              <div className="bg-emerald-500/10 rounded-lg p-3 border border-emerald-500/20">
                <p className="text-xs text-emerald-400 mb-1">Better approach</p>
                <p className="text-white text-sm">{coaching.better_approach}</p>
              </div>
            )}
            
            {/* Candidate Moves - Clickable! */}
            {coaching.candidate_moves?.length > 0 && (
              <CandidateMovesSection 
                candidates={coaching.candidate_moves}
                onShowMove={onShowAlternativeMove}
              />
            )}
            
            {/* Transferable Learning */}
            {coaching.transferable_learning && (
              <TransferableLearningSection
                learning={coaching.transferable_learning}
                conceptId={coaching.concept_id}
                isAcknowledged={isAcknowledged}
                onAcknowledge={handleAcknowledge}
                acknowledging={acknowledging}
                showButton={showAcknowledgeButton && !isAcknowledged}
              />
            )}
            
            {/* Pattern Memory — "You've missed this 3 times" */}
            {coaching.pattern_memory && (
              <div
                className="bg-amber-500/10 rounded-lg p-3 border border-amber-500/20"
                data-testid="pattern-memory-note"
              >
                <p className="text-xs text-amber-300 font-medium flex items-center gap-1.5">
                  <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                  </svg>
                  {coaching.pattern_memory}
                </p>
              </div>
            )}
            
            {/* Theory Applied — "You played the book move" */}
            {coaching.theory_applied && (
              <div
                className="bg-emerald-500/10 rounded-lg p-3 border border-emerald-500/20"
                data-testid="theory-applied-note"
              >
                <p className="text-xs text-emerald-300 font-medium flex items-center gap-1.5">
                  <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                  {coaching.theory_applied}
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};


/**
 * Candidate Moves Section - Shows Stockfish alternatives with clickable moves
 */
const CandidateMovesSection = ({ candidates, onShowMove }) => {
  if (!candidates?.length) return null;
  
  return (
    <div 
      className="bg-blue-500/10 rounded-lg p-3 border border-blue-500/20"
      data-testid="candidate-moves-section"
    >
      <p className="text-xs text-blue-400 mb-2 flex items-center gap-1">
        <Lightbulb className="w-3 h-3" /> Alternative ideas in this position
      </p>
      <div className="space-y-2">
        {candidates.map((candidate, idx) => (
          <div 
            key={idx}
            className={`flex items-start gap-2 p-2 rounded cursor-pointer transition-all hover:scale-[1.01] ${
              candidate.is_best 
                ? 'bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20' 
                : 'bg-zinc-800/50 hover:bg-zinc-700/50'
            }`}
            onClick={() => onShowMove?.(candidate.move)}
            title={`Click to see ${candidate.move} on the board`}
          >
            <button
              className={`font-mono font-bold text-sm min-w-[50px] px-2 py-1 rounded hover:ring-2 ring-offset-1 ring-offset-zinc-900 ${
                candidate.is_best 
                  ? 'text-emerald-400 bg-emerald-500/20 hover:ring-emerald-500/50' 
                  : 'text-blue-400 bg-blue-500/20 hover:ring-blue-500/50'
              }`}
              onClick={(e) => {
                e.stopPropagation();
                onShowMove?.(candidate.move);
              }}
            >
              {candidate.move}
            </button>
            <div className="flex-1">
              <p className="text-sm text-zinc-200">{candidate.idea}</p>
              {candidate.type && (
                <Badge 
                  variant="outline" 
                  className={`mt-1 text-xs ${MOVE_TYPE_COLORS[candidate.type] || MOVE_TYPE_COLORS.engine_choice}`}
                >
                  {candidate.type?.replace('_', ' ')}
                </Badge>
              )}
            </div>
            {candidate.is_best && (
              <Trophy className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
};


/**
 * Transferable Learning Section - Golden rules with "I understand" button
 */
const TransferableLearningSection = ({
  learning,
  conceptId,
  isAcknowledged,
  onAcknowledge,
  acknowledging,
  showButton
}) => {
  return (
    <div 
      className="bg-amber-500/10 rounded-lg p-4 border border-amber-500/30"
      data-testid="transferable-learning-section"
    >
      <div className="flex items-center gap-2 mb-1">
        <GraduationCap className="w-4 h-4 text-amber-400" />
        <p className="text-xs font-semibold text-amber-400">Golden Rule</p>
      </div>
      <p className="text-white text-sm font-medium mb-3">{learning}</p>
      
      {showButton && conceptId && (
        <Button
          size="sm"
          variant="outline"
          className="w-full border-amber-500/30 text-amber-400 hover:bg-amber-500/10"
          onClick={onAcknowledge}
          disabled={acknowledging}
        >
          {acknowledging ? (
            <>Processing...</>
          ) : (
            <>
              <Check className="w-4 h-4 mr-2" />
              I understand
            </>
          )}
        </Button>
      )}
      
      {isAcknowledged && (
        <div className="flex items-center gap-2 text-emerald-400 text-xs mt-2">
          <CheckCircle2 className="w-4 h-4" />
          You've learned this concept!
        </div>
      )}
    </div>
  );
};


/**
 * Compact V5 Coaching Card - For live coaching with less space
 */
export const V5CoachingCardCompact = ({
  coaching,
  moveSan,
  onShowAlternativeMove,
  onAcknowledge
}) => {
  if (!coaching) return null;
  
  const severity = coaching.severity || "context";
  const config = SEVERITY_CONFIG[severity] || SEVERITY_CONFIG.context;
  const isMistake = ["inaccuracy", "mistake", "blunder"].includes(severity);
  
  return (
    <div className="bg-zinc-900/80 rounded-lg p-3 border border-zinc-700/50">
      {/* Header with move and severity */}
      <div className="flex items-center gap-2 mb-2">
        <span className="font-mono font-bold text-white">{moveSan}</span>
        <Badge variant="outline" className={`text-${config.color}-400 text-xs`}>
          {config.label}
        </Badge>
      </div>
      
      {/* Narrative */}
      <p className="text-sm text-zinc-300 mb-2">{coaching.narrative}</p>
      
      {/* Quick consequence for mistakes */}
      {isMistake && coaching.consequence && (
        <p className="text-xs text-orange-400 mb-2">
          {coaching.consequence}
        </p>
      )}
      
      {/* Best alternative */}
      {isMistake && coaching.candidate_moves?.[0] && (
        <button
          className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
          onClick={() => onShowAlternativeMove?.(coaching.candidate_moves[0].move)}
        >
          <Lightbulb className="w-3 h-3" />
          Better: {coaching.candidate_moves[0].move} - {coaching.candidate_moves[0].idea}
        </button>
      )}
      
      {/* Your plan for opponent moves */}
      {severity === "context" && coaching.your_plan_now && (
        <p className="text-xs text-blue-400 mt-2">
          <Target className="w-3 h-3 inline mr-1" />
          {coaching.your_plan_now}
        </p>
      )}
    </div>
  );
};


export default V5CoachingCard;
