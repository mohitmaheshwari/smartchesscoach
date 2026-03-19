/**
 * GameSummary - The Coach Opens the Session
 * 
 * Strict 6-section structure:
 * 1. Game Story - narrative of what happened
 * 2. Accuracy - one number, simple
 * 3. Biggest Moment - ONE highlighted mistake (the learning anchor)
 * 4. Key Lesson - ONE takeaway
 * 5. Habit to Build - actionable steps
 * 6. Pattern Notice - cross-game insight (only if data exists)
 * 
 * Tone: Human coach speaking to student
 * NO engine numbers. NO multiple lessons. Focus.
 */

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { API } from "@/App";
import PrincipleFeedback from "./PrincipleFeedback";
import BehavioralIntervention from "./BehavioralIntervention";
import {
  BookOpen,
  Target,
  AlertTriangle,
  TrendingUp,
  CheckCircle2,
  Crosshair,
  ChevronRight,
  Clock,
  ChevronDown,
  ChevronUp,
  Lightbulb,
  Loader2,
  Brain
} from "lucide-react";

const GameSummary = ({ 
  game,
  labData,
  analysis,  // NEW: enriched analysis with coach layer
  userColor,
  result,
  accuracy,
  deepStrategy,
  patternContext,
  onNavigateToMove
}) => {
  // State for expandable explanations
  const [showTurningPointExplain, setShowTurningPointExplain] = useState(false);
  const [showBlunderExplain, setShowBlunderExplain] = useState(false);
  const [blunderExplanation, setBlunderExplanation] = useState(null);
  const [loadingBlunderExplain, setLoadingBlunderExplain] = useState(false);
  const [showBehavioralInsight, setShowBehavioralInsight] = useState(false);

  // Extract coach layer data from enriched analysis
  const coachSummary = analysis?.coach_summary || {};
  const crossGameContext = analysis?.cross_game_context || {};
  const behavioralData = analysis?.turning_point?.behavioral || {};

  // Fetch on-demand explanation for biggest blunder
  const fetchBlunderExplanation = async (blunderData) => {
    if (blunderExplanation || loadingBlunderExplain) return;
    setLoadingBlunderExplain(true);
    try {
      const res = await fetch(`${API}/explain-mistake`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          fen_before: blunderData.fen,
          move: blunderData.yourMove,
          best_move: blunderData.bestMove,
          cp_loss: Math.abs(blunderData.cpLoss || 0),
          user_color: userColor,
          move_number: blunderData.moveNum
        })
      });
      if (res.ok) {
        const data = await res.json();
        setBlunderExplanation(data);
      }
    } catch (e) {
      console.log("Failed to fetch blunder explanation:", e);
    } finally {
      setLoadingBlunderExplain(false);
      setShowBlunderExplain(true);
    }
  };
  
  // Determine game outcome from user's perspective
  const isLoss = (result === "0-1" && userColor === "white") || (result === "1-0" && userColor === "black");
  const isWin = (result === "1-0" && userColor === "white") || (result === "0-1" && userColor === "black");
  const isDraw = result === "1/2-1/2";
  
  // Termination info
  const termination = labData?.termination || {};
  const isTimeoutWin = termination.is_timeout_win;
  const isTimeoutLoss = termination.is_timeout_loss;
  
  // Get turning point and missed recovery from backend
  const turningPoint = labData?.turning_point;
  const missedRecovery = labData?.missed_recovery;
  
  // Get the biggest blunder (highest cp_loss) for learning
  const biggestBlunder = labData?.biggest_blunder;
  const criticalMoments = deepStrategy?.critical_moments || [];
  
  // Find the moment with highest cp_loss from critical moments
  const biggestFromMoments = criticalMoments.length > 0
    ? criticalMoments.reduce((biggest, current) => 
        (Math.abs(current.cp_loss || 0) > Math.abs(biggest.cp_loss || 0)) ? current : biggest
      )
    : null;
  
  // Use turning point as primary "biggest moment" if it exists, otherwise highest cp_loss
  const primaryMoment = turningPoint || biggestFromMoments || biggestBlunder;
  
  const blunderCount = labData?.blunders || 0;
  const mistakeCount = labData?.mistakes || 0;
  
  // ========== SECTION 1: Game Story ==========
  const getGameStory = () => {
    // If we have enriched coach summary, use it
    if (coachSummary.opening_line) {
      return coachSummary.opening_line;
    }
    
    // Correctly determine opponent based on user's color
    let opponent = game?.opponent;
    if (!opponent) {
      // User played as white → opponent is black_player, and vice versa
      opponent = userColor === "white" 
        ? (game?.black_player || game?.black_username)
        : (game?.white_player || game?.white_username);
    }
    opponent = opponent || "your opponent";
    
    // Handle timeout wins/losses first - most important acknowledgment
    if (isTimeoutWin) {
      return `You won on time against ${opponent}, but you were in a losing position. Let's see where things went wrong so you can win cleanly next time.`;
    }
    
    if (isTimeoutLoss) {
      return `You lost on time against ${opponent}. Time management is part of the game — let's see if there were positions where you spent too long.`;
    }
    
    if (!primaryMoment && !turningPoint) {
      if (isWin) return `A solid game against ${opponent}. No major mistakes — well played.`;
      if (isDraw) return `A balanced game against ${opponent} from start to finish.`;
      return `A tough game against ${opponent}. Let's see what happened.`;
    }
    
    // Use turning point for story if available
    const storyMoment = turningPoint || primaryMoment;
    const moveNum = storyMoment?.move_number;
    
    if (isLoss) {
      if (turningPoint) {
        return `Against ${opponent}, the game was decided on move ${moveNum}. After that move, you never recovered.`;
      }
      return `Against ${opponent}, move ${moveNum} was critical. That's where we need to focus.`;
    } else if (isWin) {
      if (blunderCount > 0) {
        return `You won against ${opponent}, but move ${moveNum} could have changed everything. Let's make sure you're winning cleanly.`;
      }
      return `A well-played win against ${opponent}. Let's see if there were any missed opportunities.`;
    } else {
      return `A balanced game against ${opponent}. Move ${moveNum} was where things could have gone differently.`;
    }
  };
  
  // ========== SECTION 3: Turning Point & Biggest Blunder ==========
  const getTurningPointData = () => {
    if (!turningPoint) return null;
    
    return {
      moveNum: turningPoint.move_number,
      yourMove: turningPoint.move,
      bestMove: turningPoint.best_move,
      yourMoveUci: turningPoint.move_uci,  // For arrow display
      bestMoveUci: turningPoint.best_move_uci,  // For arrow display
      explanation: turningPoint.description || "After this move, you never recovered.",
      fen: turningPoint.fen_before,
      type: "turning_point",
      // Rich explanation fields (from adaptive explainer)
      missedIdea: turningPoint.missed_idea,
      opponentIdea: turningPoint.opponent_idea,
      thinkingError: turningPoint.thinking_error,
      trainingTip: turningPoint.training_tip,
      severity: turningPoint.severity,
      // NEW: Pattern categorization
      category: turningPoint.category,
      categoryLabel: turningPoint.category_label,
      patternName: turningPoint.pattern_name,
      howToSpot: turningPoint.how_to_spot || [],
      trainingFocus: turningPoint.training_focus
    };
  };
  
  const getMissedRecoveryData = () => {
    if (!missedRecovery) return null;
    
    return {
      moveNum: missedRecovery.move_number,
      yourMove: missedRecovery.move,
      bestMove: missedRecovery.best_move,
      explanation: missedRecovery.description || "You had a chance to get back in the game here.",
      fen: missedRecovery.fen_before,
      type: "missed_recovery"
    };
  };
  
  const getBiggestBlunderData = () => {
    // Get highest cp_loss moment for learning (separate from turning point)
    const blunderMoment = biggestFromMoments || biggestBlunder;
    if (!blunderMoment) return null;
    
    // Skip if it's the same as turning point
    if (turningPoint && blunderMoment.move_number === turningPoint.move_number) {
      return null;
    }
    
    const moveNum = blunderMoment.move_number;
    const yourMove = blunderMoment.your_move || blunderMoment.move;
    const bestMove = blunderMoment.best_move;
    const yourMoveUci = blunderMoment.move_uci || "";
    const bestMoveUci = blunderMoment.best_move_uci || "";
    const threat = blunderMoment.threat;
    const insight = blunderMoment.insight || {};
    const fen = blunderMoment.fen || blunderMoment.fen_before;
    
    // Build the explanation
    let explanation = "";
    if (insight.what_you_missed) {
      explanation = insight.what_you_missed;
    } else if (threat) {
      explanation = `You played ${yourMove}, but this ${threat.toLowerCase().includes("ignore") ? "ignored" : "allowed"} ${threat}.`;
    } else if (yourMove && bestMove) {
      explanation = `You played ${yourMove}. ${bestMove} would have been stronger.`;
    }
    
    return {
      moveNum,
      yourMove,
      bestMove,
      yourMoveUci,
      bestMoveUci,
      explanation,
      fen,
      cpLoss: blunderMoment.cp_loss || 0,
      type: "biggest_blunder"
    };
  };
  
  // ========== SECTION 4: Key Lesson ==========
  const getKeyLesson = () => {
    if (!primaryMoment && !turningPoint) return null;
    
    const moment = turningPoint || primaryMoment;
    const threat = moment?.threat || "";
    const insight = moment?.insight || {};
    
    // Prioritize pattern_to_remember from insight
    if (insight.pattern_to_remember) {
      return insight.pattern_to_remember;
    }
    
    // Derive lesson from threat type
    const threatLower = threat.toLowerCase();
    if (threatLower.includes("fork")) {
      return "Watch for piece forks — especially knight forks after checks.";
    }
    if (threatLower.includes("pin")) {
      return "Pinned pieces can't move freely. Always check for pins before moving.";
    }
    if (threatLower.includes("mate") || threatLower.includes("checkmate")) {
      return "King safety comes first. Always scan for mating threats.";
    }
    if (threatLower.includes("loose") || threatLower.includes("hanging") || threatLower.includes("undefended")) {
      return "Loose pieces lose games. Before each move, check: is everything protected?";
    }
    if (threatLower.includes("back rank")) {
      return "Never forget the back rank. Create an escape square for your king.";
    }
    
    // Generic but useful
    return "Before every move, ask: What is my opponent threatening?";
  };
  
  // ========== SECTION 5: Habit to Build ==========
  const getHabitToBuild = () => {
    const moment = turningPoint || primaryMoment;
    const insight = moment?.insight || {};
    const threat = moment?.threat || "";
    
    // Derive habit from the type of mistake
    const threatLower = threat.toLowerCase();
    
    if (threatLower.includes("loose") || threatLower.includes("hanging") || threatLower.includes("capture")) {
      return {
        habit: "Before every move, run this check",
        steps: ["Are any of my pieces undefended?", "Can my opponent capture something?", "Is my move safe?"]
      };
    }
    
    if (threatLower.includes("fork") || threatLower.includes("tactic")) {
      return {
        habit: "Before moving, scan for tactics",
        steps: ["Checks — can I give check?", "Captures — can I take something?", "Threats — can I create a threat?"]
      };
    }
    
    if (threatLower.includes("king") || threatLower.includes("mate")) {
      return {
        habit: "Before attacking, verify safety",
        steps: ["Is my king safe?", "Are my pieces defended?", "What can my opponent do to me?"]
      };
    }
    
    // Default thinking habit
    return {
      habit: "Before every move, ask yourself",
      steps: ["What is my opponent threatening?", "What changed after their last move?", "Is my move safe?"]
    };
  };
  
  // ========== SECTION 6: Pattern Notice ==========
  const getPatternNotice = () => {
    if (!patternContext) return null;
    
    // Check for cross-game data
    const history = patternContext.history || {};
    const mostRecurring = history.most_recurring;
    const occurrenceCount = history.count || patternContext.occurrence_count || 0;
    
    // STRICT RULE: Only show if we have cross-game evidence
    if (mostRecurring && occurrenceCount >= 2) {
      const patternLabel = mostRecurring.replace(/_/g, ' ');
      return {
        hasEvidence: true,
        message: `This type of mistake (${patternLabel}) has appeared in ${occurrenceCount} of your recent games.`
      };
    }
    
    // Check summary for cross-game info
    const summary = patternContext.summary;
    if (typeof summary === 'string' && (summary.includes("games") || summary.includes("appeared"))) {
      return {
        hasEvidence: true,
        message: summary
      };
    }
    
    // No cross-game evidence - don't show false patterns
    return null;
  };
  
  const gameStory = getGameStory();
  const turningPointData = getTurningPointData();
  const missedRecoveryData = getMissedRecoveryData();
  const biggestBlunderData = getBiggestBlunderData();
  const keyLesson = getKeyLesson();
  const habit = getHabitToBuild();
  const patternNotice = getPatternNotice();
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-4"
      data-testid="game-summary"
    >
      {/* TIMEOUT BANNER - Show when game ended on time */}
      {(isTimeoutWin || isTimeoutLoss) && (
        <Card className={`${isTimeoutWin ? 'border-amber-500/30 bg-amber-500/10' : 'border-slate-500/30 bg-slate-500/10'}`}>
          <CardContent className="p-3">
            <div className="flex items-center gap-2">
              <Clock className={`w-4 h-4 ${isTimeoutWin ? 'text-amber-400' : 'text-slate-400'}`} />
              <span className={`text-sm font-medium ${isTimeoutWin ? 'text-amber-200' : 'text-slate-300'}`}>
                {isTimeoutWin 
                  ? "Won on Time — You were losing when opponent's clock ran out"
                  : "Lost on Time — You ran out of clock time"
                }
              </span>
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* SECTION 1: Game Story */}
      <Card className="border-0 bg-slate-800/30">
        <CardContent className="p-5">
          <div className="flex items-start gap-3">
            <BookOpen className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="text-xs font-medium text-primary uppercase tracking-wide mb-2">
                Game Story
              </h3>
              <p className="text-base leading-relaxed">
                {gameStory}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
      
      {/* SECTION 2: Accuracy - Simple, one line */}
      <div className="flex items-center justify-between px-2 py-1 text-sm">
        <span className="text-muted-foreground">Your accuracy</span>
        <span className="font-semibold text-lg">
          {accuracy?.toFixed(0) || '--'}%
        </span>
      </div>
      
      {/* SECTION 3a: Turning Point - Where the game was decided */}
      {turningPointData && (
        <Card className="border-red-500/30 bg-red-500/5">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <Crosshair className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <h4 className="text-xs font-medium text-red-400 uppercase tracking-wide">
                      Turning Point
                    </h4>
                    {turningPointData.categoryLabel && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-red-500/20 rounded text-red-300">
                        {turningPointData.categoryLabel}
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground">
                    Move {turningPointData.moveNum}
                  </span>
                </div>
                
                {/* Pattern name */}
                {turningPointData.patternName && (
                  <p className="text-sm font-medium text-red-200 mb-2">
                    {turningPointData.patternName}
                  </p>
                )}
                
                {/* Main explanation */}
                <p className="text-sm leading-relaxed mb-3 text-muted-foreground">
                  {turningPointData.explanation}
                </p>
                
                {/* Moves comparison */}
                {turningPointData.yourMove && turningPointData.bestMove && (
                  <div className="flex items-center gap-4 text-xs mb-3">
                    <span className="text-red-300">
                      You played: <span className="font-mono font-medium">{turningPointData.yourMove}</span>
                    </span>
                    <span className="text-emerald-300">
                      Better: <span className="font-mono font-medium">{turningPointData.bestMove}</span>
                    </span>
                  </div>
                )}
                
                {/* EXPLAIN THIS MOVE button */}
                {(turningPointData.missedIdea || turningPointData.opponentIdea || turningPointData.thinkingError || (turningPointData.howToSpot && turningPointData.howToSpot.length > 0)) && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-xs text-amber-300 hover:text-amber-200 hover:bg-amber-500/10 p-0 h-auto mb-2"
                    onClick={() => setShowTurningPointExplain(!showTurningPointExplain)}
                    data-testid="explain-turning-point-btn"
                  >
                    <Lightbulb className="w-3.5 h-3.5 mr-1.5" />
                    {showTurningPointExplain ? "Hide explanation" : "Explain this move"}
                    {showTurningPointExplain ? <ChevronUp className="w-3 h-3 ml-1" /> : <ChevronDown className="w-3 h-3 ml-1" />}
                  </Button>
                )}
                
                {/* Expandable Explanation Panel */}
                <AnimatePresence>
                  {showTurningPointExplain && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.2 }}
                      className="overflow-hidden"
                      data-testid="turning-point-explanation-panel"
                    >
                      <div className="space-y-3 pt-2 border-t border-red-500/20">
                        {/* What you missed */}
                        {turningPointData.missedIdea && (
                          <div className="p-2.5 bg-red-500/10 rounded-md">
                            <p className="text-xs text-red-200/90">
                              <span className="font-medium text-red-300">What you missed:</span> {turningPointData.missedIdea}
                            </p>
                          </div>
                        )}
                        
                        {/* Opponent's idea */}
                        {turningPointData.opponentIdea && (
                          <div className="p-2.5 bg-slate-500/10 rounded-md">
                            <p className="text-xs text-muted-foreground">
                              <span className="font-medium text-slate-300">Opponent's idea:</span> {turningPointData.opponentIdea}
                            </p>
                          </div>
                        )}
                        
                        {/* Thinking error + Training tip */}
                        {turningPointData.thinkingError && (
                          <div className="p-2.5 bg-red-500/10 rounded-md">
                            <p className="text-xs text-red-200/90 mb-1">
                              <span className="font-medium text-red-300">Thinking habit:</span> {turningPointData.thinkingError}
                            </p>
                            {turningPointData.trainingTip && (
                              <p className="text-xs text-emerald-300/80">
                                <span className="font-medium">Tip:</span> {turningPointData.trainingTip}
                              </p>
                            )}
                          </div>
                        )}
                        
                        {/* HOW TO SPOT THIS */}
                        {turningPointData.howToSpot && turningPointData.howToSpot.length > 0 && (
                          <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                            <h5 className="text-xs font-medium text-amber-400 uppercase tracking-wide mb-2">
                              How to spot this next time
                            </h5>
                            <ul className="space-y-1.5">
                              {turningPointData.howToSpot.map((tip, i) => (
                                <li key={i} className="text-xs text-amber-200/80 flex items-start gap-2">
                                  <span className="text-amber-400 mt-0.5">{i + 1}.</span>
                                  <span>{tip}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
                
                {onNavigateToMove && turningPointData.moveNum && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-3 text-xs text-red-300 hover:text-red-200 p-0 h-auto"
                    onClick={() => onNavigateToMove(
                      turningPointData.moveNum, 
                      turningPointData.yourMoveUci || turningPointData.yourMove, 
                      turningPointData.bestMoveUci || turningPointData.bestMove
                    )}
                    data-testid="view-position-turning-point-btn"
                  >
                    View position <ChevronRight className="w-3 h-3 ml-1" />
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* NEW: BEHAVIORAL INSIGHT - Why did you make this mistake? */}
      {behavioralData && behavioralData.tag && (
        <Card className="border-purple-500/30 bg-purple-500/5">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <Brain className="w-5 h-5 text-purple-400 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs font-medium text-purple-400 uppercase tracking-wide">
                    Why This Happened
                  </h4>
                  <span className="text-xs text-muted-foreground px-2 py-0.5 bg-purple-500/20 rounded">
                    {behavioralData.tag.replace(/_/g, ' ')}
                  </span>
                </div>
                
                <p className="text-sm font-medium text-purple-200 mb-2">
                  {behavioralData.short_explanation}
                </p>
                
                {behavioralData.long_explanation && (
                  <p className="text-sm text-muted-foreground mb-3">
                    {behavioralData.long_explanation}
                  </p>
                )}
                
                {/* Reflection question - like a real coach would ask */}
                {behavioralData.reflection_question && (
                  <div className="p-3 bg-purple-500/10 border border-purple-500/20 rounded-lg">
                    <p className="text-xs text-purple-300 italic">
                      "{behavioralData.reflection_question}"
                    </p>
                  </div>
                )}
                
                {/* Cross-game pattern */}
                {behavioralData.recurring_pattern && (
                  <div className="mt-3 p-2.5 bg-red-500/10 border border-red-500/20 rounded">
                    <p className="text-xs text-red-300">
                      <span className="font-medium">Pattern Alert:</span> {behavioralData.recurring_pattern.message}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* SECTION 3b: Missed Recovery - Chance to come back that was missed */}
      {missedRecoveryData && (
        <Card className="border-orange-500/30 bg-orange-500/5">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-orange-400 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs font-medium text-orange-400 uppercase tracking-wide">
                    Missed Recovery
                  </h4>
                  <span className="text-xs text-muted-foreground">
                    Move {missedRecoveryData.moveNum}
                  </span>
                </div>
                
                <p className="text-sm leading-relaxed mb-3">
                  {missedRecoveryData.explanation}
                </p>
                
                {missedRecoveryData.yourMove && missedRecoveryData.bestMove && (
                  <div className="flex items-center gap-4 text-xs">
                    <span className="text-orange-300">
                      You played: <span className="font-mono font-medium">{missedRecoveryData.yourMove}</span>
                    </span>
                    <span className="text-emerald-300">
                      Would have saved: <span className="font-mono font-medium">{missedRecoveryData.bestMove}</span>
                    </span>
                  </div>
                )}
                
                {onNavigateToMove && missedRecoveryData.moveNum && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-3 text-xs text-orange-300 hover:text-orange-200 p-0 h-auto"
                    onClick={() => onNavigateToMove(missedRecoveryData.moveNum, missedRecoveryData.yourMove, missedRecoveryData.bestMove)}
                  >
                    View position <ChevronRight className="w-3 h-3 ml-1" />
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* SECTION 3c: Biggest Blunder - Largest single error (if different from turning point) */}
      {biggestBlunderData && (
        <Card className="border-yellow-500/30 bg-yellow-500/5">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <Crosshair className="w-5 h-5 text-yellow-400 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs font-medium text-yellow-400 uppercase tracking-wide">
                    Biggest Blunder
                  </h4>
                  <span className="text-xs text-muted-foreground">
                    Move {biggestBlunderData.moveNum}
                  </span>
                </div>
                
                <p className="text-sm leading-relaxed mb-3">
                  {biggestBlunderData.explanation}
                </p>
                
                {biggestBlunderData.yourMove && biggestBlunderData.bestMove && (
                  <div className="flex items-center gap-4 text-xs mb-3">
                    <span className="text-yellow-300">
                      You played: <span className="font-mono font-medium">{biggestBlunderData.yourMove}</span>
                    </span>
                    <span className="text-emerald-300">
                      Better: <span className="font-mono font-medium">{biggestBlunderData.bestMove}</span>
                    </span>
                  </div>
                )}
                
                {/* EXPLAIN THIS MOVE button for blunder */}
                {biggestBlunderData.fen && biggestBlunderData.yourMove && biggestBlunderData.bestMove && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-xs text-amber-300 hover:text-amber-200 hover:bg-amber-500/10 p-0 h-auto mb-2"
                    onClick={() => {
                      if (showBlunderExplain) {
                        setShowBlunderExplain(false);
                      } else {
                        fetchBlunderExplanation(biggestBlunderData);
                      }
                    }}
                    disabled={loadingBlunderExplain}
                    data-testid="explain-blunder-btn"
                  >
                    {loadingBlunderExplain ? (
                      <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                    ) : (
                      <Lightbulb className="w-3.5 h-3.5 mr-1.5" />
                    )}
                    {loadingBlunderExplain ? "Analyzing..." : showBlunderExplain ? "Hide explanation" : "Explain this move"}
                    {!loadingBlunderExplain && (showBlunderExplain ? <ChevronUp className="w-3 h-3 ml-1" /> : <ChevronDown className="w-3 h-3 ml-1" />)}
                  </Button>
                )}
                
                {/* Expandable Blunder Explanation Panel */}
                <AnimatePresence>
                  {showBlunderExplain && blunderExplanation && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.2 }}
                      className="overflow-hidden"
                      data-testid="blunder-explanation-panel"
                    >
                      <div className="space-y-3 pt-2 border-t border-yellow-500/20">
                        {/* Main explanation text */}
                        {blunderExplanation.explanation && (
                          <div className="p-2.5 bg-yellow-500/10 rounded-md">
                            <p className="text-xs text-yellow-200/90">
                              {blunderExplanation.explanation}
                            </p>
                          </div>
                        )}
                        
                        {/* Mistake type and thinking habit */}
                        {blunderExplanation.thinking_habit && (
                          <div className="p-2.5 bg-red-500/10 rounded-md">
                            <p className="text-xs text-red-200/90">
                              <span className="font-medium text-red-300">Thinking habit:</span> {blunderExplanation.thinking_habit}
                            </p>
                          </div>
                        )}
                        
                        {/* Details from analysis */}
                        {blunderExplanation.details?.threat_description && (
                          <div className="p-2.5 bg-slate-500/10 rounded-md">
                            <p className="text-xs text-muted-foreground">
                              <span className="font-medium text-slate-300">The threat:</span> {blunderExplanation.details.threat_description}
                            </p>
                          </div>
                        )}
                        
                        {blunderExplanation.details?.why_best_is_better && (
                          <div className="p-2.5 bg-emerald-500/10 rounded-md">
                            <p className="text-xs text-emerald-200/90">
                              <span className="font-medium text-emerald-300">Why the better move works:</span> {blunderExplanation.details.why_best_is_better}
                            </p>
                          </div>
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
                
                {onNavigateToMove && biggestBlunderData.moveNum && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-3 text-xs text-yellow-300 hover:text-yellow-200 p-0 h-auto"
                    onClick={() => onNavigateToMove(biggestBlunderData.moveNum, biggestBlunderData.yourMoveUci || biggestBlunderData.yourMove, biggestBlunderData.bestMoveUci || biggestBlunderData.bestMove)}
                    data-testid="view-position-blunder-btn"
                  >
                    View position <ChevronRight className="w-3 h-3 ml-1" />
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* SECTION 4: Key Lesson - ONE takeaway */}
      {keyLesson && (
        <Card className="border-amber-500/30 bg-amber-500/5">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <Target className="w-5 h-5 text-amber-500 mt-0.5 flex-shrink-0" />
              <div>
                <h4 className="text-xs font-medium text-amber-400 uppercase tracking-wide mb-2">
                  Key Lesson
                </h4>
                <p className="text-sm font-medium text-amber-200 leading-relaxed">
                  {keyLesson}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* NEW: Principle-Based Feedback for biggest blunder */}
      {primaryMoment && (primaryMoment.fen_before || primaryMoment.fen) && (primaryMoment.move || primaryMoment.your_move) && primaryMoment.best_move && (
        <PrincipleFeedback
          mistakeType={primaryMoment.category || "positional_error"}
          fen={primaryMoment.fen_before || primaryMoment.fen}
          movePlayed={primaryMoment.move || primaryMoment.your_move}
          bestMove={primaryMoment.best_move}
          autoFetch={true}
          compact={true}
        />
      )}

      {/* NEW: Behavioral Intervention if cross-game patterns exist */}
      {crossGameContext?.dominant_pattern && (
        <BehavioralIntervention
          pattern={crossGameContext.dominant_pattern}
          examples={crossGameContext.examples || []}
          autoFetch={true}
          compact={true}
        />
      )}
      
      {/* SECTION 5: Habit to Build */}
      {habit && (
        <Card className="border-emerald-500/30 bg-emerald-500/5">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-500 mt-0.5 flex-shrink-0" />
              <div>
                <h4 className="text-xs font-medium text-emerald-400 uppercase tracking-wide mb-2">
                  Habit to Build
                </h4>
                <p className="text-sm font-medium mb-3">{habit.habit}:</p>
                <ol className="text-sm text-muted-foreground space-y-2">
                  {habit.steps.map((step, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 text-xs flex items-center justify-center flex-shrink-0 mt-0.5">
                        {i + 1}
                      </span>
                      <span>{step}</span>
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* SECTION 6: Pattern Notice - ONLY if cross-game evidence exists */}
      {patternNotice && patternNotice.hasEvidence && (
        <Card className="border-violet-500/30 bg-violet-500/5">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-violet-500 mt-0.5 flex-shrink-0" />
              <div>
                <h4 className="text-xs font-medium text-violet-400 uppercase tracking-wide mb-2">
                  Coach Notice
                </h4>
                <p className="text-sm text-violet-200 leading-relaxed">
                  {patternNotice.message}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </motion.div>
  );
};

export default GameSummary;
