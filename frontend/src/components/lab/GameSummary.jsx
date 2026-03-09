/**
 * GameSummary - The Coach Opens the Session
 * 
 * Tells the story of the game in plain language.
 * Shows key lesson, habit to build, and recurring pattern notice.
 * 
 * NO engine numbers. Just coach talk.
 */

import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  BookOpen,
  Target,
  AlertTriangle,
  TrendingUp,
  CheckCircle2
} from "lucide-react";

const GameSummary = ({ 
  game,
  labData,
  userColor,
  result,
  accuracy,
  deepStrategy,
  patternContext
}) => {
  // Determine game outcome from user's perspective
  const isLoss = (result === "0-1" && userColor === "white") || (result === "1-0" && userColor === "black");
  const isWin = (result === "1-0" && userColor === "white") || (result === "0-1" && userColor === "black");
  const isDraw = result === "1/2-1/2";
  
  // Get the turning point
  const biggestBlunder = labData?.biggest_blunder;
  const blunderCount = labData?.blunders || 0;
  const mistakeCount = labData?.mistakes || 0;
  
  // Build the game story
  const getGameStory = () => {
    if (!biggestBlunder) {
      if (isWin) return "A solid game with no major mistakes. Well played!";
      if (isDraw) return "A balanced game from start to finish.";
      return "A tough game. Let's see what happened.";
    }
    
    const moveNum = biggestBlunder.move_number;
    const threat = biggestBlunder.threat;
    const isCheckmate = biggestBlunder.is_checkmate_level;
    
    if (isLoss) {
      if (isCheckmate && threat) {
        return `This game came down to one move. You missed ${threat} — and that was checkmate.`;
      } else if (isCheckmate) {
        return `This game came down to one critical moment. A missed threat on move ${moveNum} ended the game.`;
      } else if (blunderCount === 1 && threat) {
        return `Close game. One moment changed everything on move ${moveNum} — you missed ${threat}.`;
      } else if (blunderCount === 1) {
        return `You were competitive until move ${moveNum}. That's when the position slipped away.`;
      } else {
        return `A challenging game with ${blunderCount + mistakeCount} critical moments. Let's focus on the biggest one.`;
      }
    } else if (isWin) {
      if (blunderCount > 0) {
        return `You won, but there were moments where the game could have gone differently. Let's make sure you're winning cleanly.`;
      }
      return "A well-played game. Let's see if there were any missed opportunities.";
    } else {
      return `A balanced game. Move ${moveNum || 'the turning point'} was where the game could have changed.`;
    }
  };
  
  // Get key lesson
  const getKeyLesson = () => {
    if (!biggestBlunder) return null;
    
    const threat = biggestBlunder.threat;
    const insight = deepStrategy?.critical_moments?.[0]?.insight;
    
    if (insight?.pattern_to_remember) {
      return insight.pattern_to_remember;
    }
    
    if (threat) {
      if (threat.toLowerCase().includes("fork")) {
        return "Watch for piece forks - especially knight forks.";
      }
      if (threat.toLowerCase().includes("pin")) {
        return "Pinned pieces can't move freely. Always check for pins.";
      }
      if (threat.toLowerCase().includes("mate") || threat.toLowerCase().includes("checkmate")) {
        return "King safety comes first. Always check for mating threats.";
      }
      if (threat.toLowerCase().includes("loose") || threat.toLowerCase().includes("hanging")) {
        return "Loose pieces lose games. Scan for undefended pieces before each move.";
      }
    }
    
    // Generic but useful lessons
    const cp_loss = Math.abs(biggestBlunder.cp_loss || 0);
    if (cp_loss >= 300) {
      return "Before every move, ask: What is my opponent threatening?";
    }
    return "Slow down at critical moments. Check, capture, threat - in that order.";
  };
  
  // Get habit to build
  const getHabitToBuild = () => {
    const insight = deepStrategy?.critical_moments?.[0]?.insight;
    
    if (insight?.pattern_to_remember) {
      // Extract habit from pattern
      const pattern = insight.pattern_to_remember.toLowerCase();
      if (pattern.includes("capture") || pattern.includes("loose")) {
        return {
          habit: "Before moving, check",
          steps: ["Checks", "Captures", "Threats"]
        };
      }
      if (pattern.includes("king") || pattern.includes("safety")) {
        return {
          habit: "Before attacking, verify",
          steps: ["Is my king safe?", "Are my pieces defended?", "What can opponent do?"]
        };
      }
    }
    
    // Default habit
    return {
      habit: "Before every move, ask",
      steps: ["What is threatened?", "Can I capture something?", "Is my move safe?"]
    };
  };
  
  // Check for recurring pattern
  const getRecurringPattern = () => {
    if (!patternContext?.summary) return null;
    
    const summary = patternContext.summary;
    // Check if summary is a string before using includes
    if (typeof summary === 'string') {
      if (summary.includes("appeared") || summary.includes("recurring") || summary.includes("games")) {
        return summary;
      }
    }
    
    // Check pattern history
    const mostRecurring = patternContext?.history?.most_recurring;
    if (mostRecurring) {
      return `This type of mistake (${mostRecurring.replace(/_/g, ' ')}) has appeared in your recent games.`;
    }
    
    return null;
  };
  
  const gameStory = getGameStory();
  const keyLesson = getKeyLesson();
  const habit = getHabitToBuild();
  const recurringPattern = getRecurringPattern();
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-4"
    >
      {/* Game Story */}
      <Card className="border-0 bg-slate-800/30">
        <CardContent className="p-5">
          <div className="flex items-start gap-3 mb-4">
            <BookOpen className="w-5 h-5 text-primary mt-0.5" />
            <div>
              <h3 className="text-xs font-medium text-primary uppercase tracking-wide mb-1">
                Game Summary
              </h3>
              <p className="text-base leading-relaxed">
                {gameStory}
              </p>
            </div>
          </div>
          
          {/* Quick Stats - Simple, no cp values */}
          <div className="flex items-center gap-4 text-sm text-muted-foreground border-t border-border/30 pt-3 mt-3">
            <span>Accuracy: {accuracy?.toFixed(0) || '--'}%</span>
            {blunderCount > 0 && (
              <span className="text-red-400">{blunderCount} blunder{blunderCount > 1 ? 's' : ''}</span>
            )}
            {mistakeCount > 0 && (
              <span className="text-amber-400">{mistakeCount} mistake{mistakeCount > 1 ? 's' : ''}</span>
            )}
          </div>
        </CardContent>
      </Card>
      
      {/* Key Lesson */}
      {keyLesson && (
        <Card className="border-amber-500/30 bg-amber-500/5">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <Target className="w-5 h-5 text-amber-500 mt-0.5 flex-shrink-0" />
              <div>
                <h4 className="text-xs font-medium text-amber-400 uppercase tracking-wide mb-1">
                  Key Lesson
                </h4>
                <p className="text-sm font-medium text-amber-200">
                  {keyLesson}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* Habit to Build */}
      {habit && (
        <Card className="border-emerald-500/30 bg-emerald-500/5">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-500 mt-0.5 flex-shrink-0" />
              <div>
                <h4 className="text-xs font-medium text-emerald-400 uppercase tracking-wide mb-2">
                  Habit to Build
                </h4>
                <p className="text-sm font-medium mb-2">{habit.habit}:</p>
                <ol className="text-sm text-muted-foreground space-y-1">
                  {habit.steps.map((step, i) => (
                    <li key={i} className="flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 text-xs flex items-center justify-center">
                        {i + 1}
                      </span>
                      {step}
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* Recurring Pattern Notice */}
      {recurringPattern && (
        <Card className="border-violet-500/30 bg-violet-500/5">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-violet-500 mt-0.5 flex-shrink-0" />
              <div>
                <h4 className="text-xs font-medium text-violet-400 uppercase tracking-wide mb-1">
                  Coach Notice
                </h4>
                <p className="text-sm text-violet-200">
                  {recurringPattern}
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
