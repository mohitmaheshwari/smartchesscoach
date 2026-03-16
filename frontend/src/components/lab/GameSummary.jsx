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

import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  BookOpen,
  Target,
  AlertTriangle,
  TrendingUp,
  CheckCircle2,
  Crosshair,
  ChevronRight
} from "lucide-react";

const GameSummary = ({ 
  game,
  labData,
  userColor,
  result,
  accuracy,
  deepStrategy,
  patternContext,
  onNavigateToMove
}) => {
  // Determine game outcome from user's perspective
  const isLoss = (result === "0-1" && userColor === "white") || (result === "1-0" && userColor === "black");
  const isWin = (result === "1-0" && userColor === "white") || (result === "0-1" && userColor === "black");
  const isDraw = result === "1/2-1/2";
  
  // Get the turning point - THE biggest moment
  const biggestBlunder = labData?.biggest_blunder;
  const criticalMoments = deepStrategy?.critical_moments || [];
  const biggestMoment = criticalMoments[0] || biggestBlunder;
  
  const blunderCount = labData?.blunders || 0;
  const mistakeCount = labData?.mistakes || 0;
  
  // ========== SECTION 1: Game Story ==========
  const getGameStory = () => {
    // Correctly determine opponent based on user's color
    let opponent = game?.opponent;
    if (!opponent) {
      // User played as white → opponent is black_player, and vice versa
      opponent = userColor === "white" 
        ? (game?.black_player || game?.black_username)
        : (game?.white_player || game?.white_username);
    }
    opponent = opponent || "your opponent";
    
    if (!biggestMoment) {
      if (isWin) return `A solid game against ${opponent}. No major mistakes — well played.`;
      if (isDraw) return `A balanced game against ${opponent} from start to finish.`;
      return `A tough game against ${opponent}. Let's see what happened.`;
    }
    
    const moveNum = biggestMoment.move_number;
    const threat = biggestMoment.threat || biggestMoment.insight?.what_you_missed;
    
    if (isLoss) {
      if (threat) {
        return `This game against ${opponent} came down to move ${moveNum}. You missed something there — and the position slipped away.`;
      }
      return `Against ${opponent}, the game changed on move ${moveNum}. That's where we need to focus.`;
    } else if (isWin) {
      if (blunderCount > 0) {
        return `You won against ${opponent}, but move ${moveNum} could have changed everything. Let's make sure you're winning cleanly.`;
      }
      return `A well-played win against ${opponent}. Let's see if there were any missed opportunities.`;
    } else {
      return `A balanced game against ${opponent}. Move ${moveNum} was where things could have gone differently.`;
    }
  };
  
  // ========== SECTION 3: Biggest Moment ==========
  const getBiggestMomentData = () => {
    if (!biggestMoment) return null;
    
    const moveNum = biggestMoment.move_number;
    const yourMove = biggestMoment.your_move || biggestMoment.move;
    const bestMove = biggestMoment.best_move;
    const threat = biggestMoment.threat;
    const insight = biggestMoment.insight || {};
    const fen = biggestMoment.fen;
    
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
      explanation,
      fen
    };
  };
  
  // ========== SECTION 4: Key Lesson ==========
  const getKeyLesson = () => {
    if (!biggestMoment) return null;
    
    const threat = biggestMoment.threat || "";
    const insight = biggestMoment.insight || {};
    
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
    const insight = biggestMoment?.insight || {};
    const threat = biggestMoment?.threat || "";
    
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
  const biggestMomentData = getBiggestMomentData();
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
      
      {/* SECTION 3: Biggest Moment - ONE highlighted mistake */}
      {biggestMomentData && (
        <Card className="border-red-500/30 bg-red-500/5">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <Crosshair className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs font-medium text-red-400 uppercase tracking-wide">
                    Biggest Moment
                  </h4>
                  <span className="text-xs text-muted-foreground">
                    Move {biggestMomentData.moveNum}
                  </span>
                </div>
                
                <p className="text-sm leading-relaxed mb-3">
                  {biggestMomentData.explanation}
                </p>
                
                {biggestMomentData.yourMove && biggestMomentData.bestMove && (
                  <div className="flex items-center gap-4 text-xs">
                    <span className="text-red-300">
                      You played: <span className="font-mono font-medium">{biggestMomentData.yourMove}</span>
                    </span>
                    <span className="text-emerald-300">
                      Better: <span className="font-mono font-medium">{biggestMomentData.bestMove}</span>
                    </span>
                  </div>
                )}
                
                {onNavigateToMove && biggestMomentData.moveNum && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-3 text-xs text-red-300 hover:text-red-200 p-0 h-auto"
                    onClick={() => onNavigateToMove(biggestMomentData.moveNum, biggestMomentData.yourMove, biggestMomentData.bestMove)}
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
