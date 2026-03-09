/**
 * CriticalMoments - Interactive Learning Section
 * 
 * The heart of the coaching session.
 * Uses Socratic approach: "What would you play?" before revealing.
 * 
 * Flow:
 * 1. Show position
 * 2. Ask "What would you play?"
 * 3. Let user think/guess
 * 4. Reveal best move with explanation
 * 5. Show why their move failed
 * 6. Pattern to remember
 */

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Eye,
  EyeOff,
  Play,
  ChevronRight,
  ChevronLeft,
  Lightbulb,
  XCircle,
  CheckCircle2,
  HelpCircle,
  ThumbsUp,
  ThumbsDown
} from "lucide-react";

const CriticalMoments = ({ 
  moments = [],
  userColor,
  onNavigateToMove,
  onFeedback,
  gameId
}) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [revealed, setRevealed] = useState({});
  const [userGuess, setUserGuess] = useState({});
  
  if (!moments || moments.length === 0) {
    return (
      <Card className="border-0 bg-slate-800/30">
        <CardContent className="p-6 text-center">
          <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto mb-3" />
          <h3 className="font-semibold mb-2">No Critical Moments</h3>
          <p className="text-sm text-muted-foreground">
            Great game! No major mistakes to review.
          </p>
        </CardContent>
      </Card>
    );
  }
  
  const moment = moments[currentIndex];
  const isRevealed = revealed[currentIndex];
  const insight = moment.insight || {};
  
  // Convert cp_loss to plain language
  const getMistakeSeverity = (cpLoss) => {
    const loss = Math.abs(cpLoss || 0);
    if (loss >= 300) return { label: "Serious mistake", color: "bg-red-500" };
    if (loss >= 200) return { label: "Mistake", color: "bg-amber-500" };
    if (loss >= 100) return { label: "Inaccuracy", color: "bg-yellow-500" };
    return { label: "Minor slip", color: "bg-slate-500" };
  };
  
  const severity = getMistakeSeverity(moment.cp_loss);
  
  const handleReveal = () => {
    setRevealed(prev => ({ ...prev, [currentIndex]: true }));
    // Navigate to the position on the board
    if (onNavigateToMove) {
      onNavigateToMove(moment.move_number);
    }
  };
  
  const handleNext = () => {
    if (currentIndex < moments.length - 1) {
      setCurrentIndex(currentIndex + 1);
    }
  };
  
  const handlePrev = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }
  };
  
  const handleFeedbackClick = (section, content) => {
    if (onFeedback) {
      onFeedback({
        explanation: content,
        positionFen: moment.fen || "",
        movePlayed: moment.your_move,
        bestMove: moment.best_move,
        classification: section,
        gameId: gameId,
        moveNumber: moment.move_number,
        userColor: userColor,
        sectionType: section
      });
    }
  };
  
  return (
    <div className="space-y-4">
      {/* Header with navigation */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold">Critical Moments</h3>
          <Badge variant="outline">{moments.length} to review</Badge>
        </div>
        
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={handlePrev}
            disabled={currentIndex === 0}
            className="h-8 w-8 p-0"
          >
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <span className="text-sm text-muted-foreground">
            {currentIndex + 1} / {moments.length}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleNext}
            disabled={currentIndex === moments.length - 1}
            className="h-8 w-8 p-0"
          >
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </div>
      
      {/* Main moment card */}
      <Card className="border-0 bg-slate-800/50 overflow-hidden">
        <CardContent className="p-0">
          {/* Moment header */}
          <div className="flex items-center justify-between p-4 border-b border-border/30">
            <div className="flex items-center gap-3">
              <Badge className={severity.color}>
                Move {moment.move_number}
              </Badge>
              <span className="text-sm text-muted-foreground">
                {severity.label}
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onNavigateToMove?.(moment.move_number)}
              className="text-primary"
            >
              <Play className="w-3 h-3 mr-1" />
              See on board
            </Button>
          </div>
          
          {/* Pre-reveal state: Socratic prompt */}
          {!isRevealed && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="p-6 text-center"
            >
              <div className="mb-6">
                <HelpCircle className="w-12 h-12 text-primary mx-auto mb-3 opacity-50" />
                <h4 className="text-lg font-medium mb-2">
                  Pause here.
                </h4>
                <p className="text-muted-foreground">
                  Look at the board. What would you play?
                </p>
              </div>
              
              <div className="flex gap-3 justify-center">
                <Button
                  onClick={handleReveal}
                  className="gap-2"
                >
                  <Eye className="w-4 h-4" />
                  Reveal Best Move
                </Button>
              </div>
            </motion.div>
          )}
          
          {/* Post-reveal state: Full explanation */}
          <AnimatePresence>
            {isRevealed && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="divide-y divide-border/30"
              >
                {/* Best Move Reveal */}
                <div className="p-4 bg-emerald-500/5">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                      <span className="text-xs font-medium text-emerald-400 uppercase tracking-wide">
                        Best Move
                      </span>
                    </div>
                  </div>
                  <p className="text-xl font-bold text-emerald-400 mb-2">
                    {moment.best_move}
                  </p>
                  
                  {/* Why it works */}
                  {insight.what_best_move_achieves && (
                    <div className="mt-3 p-3 rounded-lg bg-emerald-500/10">
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-xs font-medium text-emerald-400">
                          Why it works
                        </p>
                        <button
                          onClick={() => handleFeedbackClick("what_best_achieves", insight.what_best_move_achieves)}
                          className="text-xs text-muted-foreground hover:text-foreground"
                        >
                          Not helpful?
                        </button>
                      </div>
                      <p className="text-sm text-emerald-200">
                        {insight.what_best_move_achieves}
                      </p>
                    </div>
                  )}
                </div>
                
                {/* Your Move */}
                <div className="p-4 bg-red-500/5">
                  <div className="flex items-center gap-2 mb-2">
                    <XCircle className="w-4 h-4 text-red-400" />
                    <span className="text-xs font-medium text-red-400 uppercase tracking-wide">
                      Your Move
                    </span>
                  </div>
                  <p className="text-xl font-bold text-red-400 mb-2">
                    {moment.your_move}
                  </p>
                  
                  {/* Why it failed */}
                  {insight.why_your_move_failed && (
                    <div className="mt-3 p-3 rounded-lg bg-red-500/10">
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-xs font-medium text-red-400">
                          Why it didn't work
                        </p>
                        <button
                          onClick={() => handleFeedbackClick("why_move_failed", insight.why_your_move_failed)}
                          className="text-xs text-muted-foreground hover:text-foreground"
                        >
                          Not helpful?
                        </button>
                      </div>
                      <p className="text-sm text-red-200">
                        {insight.why_your_move_failed}
                      </p>
                    </div>
                  )}
                </div>
                
                {/* What you missed */}
                {insight.what_you_missed && (
                  <div className="p-4 bg-amber-500/5">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Eye className="w-4 h-4 text-amber-400" />
                        <span className="text-xs font-medium text-amber-400 uppercase tracking-wide">
                          What You Didn't See
                        </span>
                      </div>
                      <button
                        onClick={() => handleFeedbackClick("what_you_missed", insight.what_you_missed)}
                        className="text-xs text-muted-foreground hover:text-foreground"
                      >
                        Not helpful?
                      </button>
                    </div>
                    <p className="text-sm text-amber-200">
                      {insight.what_you_missed}
                    </p>
                  </div>
                )}
                
                {/* Pattern to Remember - The takeaway */}
                {insight.pattern_to_remember && (
                  <div className="p-4 bg-violet-500/5">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Lightbulb className="w-4 h-4 text-violet-400" />
                        <span className="text-xs font-medium text-violet-400 uppercase tracking-wide">
                          Pattern to Remember
                        </span>
                      </div>
                    </div>
                    <p className="text-sm font-medium text-violet-200">
                      {insight.pattern_to_remember}
                    </p>
                    
                    {/* Optional: Ask yourself prompt */}
                    {insight.ask_yourself && (
                      <p className="text-sm text-muted-foreground mt-2 italic">
                        Ask yourself: "{insight.ask_yourself}"
                      </p>
                    )}
                  </div>
                )}
                
                {/* Feedback prompt */}
                <div className="p-3 bg-slate-900/50 flex items-center justify-between">
                  <p className="text-xs text-muted-foreground">
                    Did this explanation help?
                  </p>
                  <div className="flex gap-2">
                    <Button variant="ghost" size="sm" className="h-7 text-xs gap-1">
                      <ThumbsUp className="w-3 h-3" />
                      Yes, I get it
                    </Button>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="h-7 text-xs gap-1"
                      onClick={() => handleFeedbackClick("confused", "Still confused about this position")}
                    >
                      <ThumbsDown className="w-3 h-3" />
                      Still confused
                    </Button>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </CardContent>
      </Card>
      
      {/* Navigation hint */}
      {currentIndex < moments.length - 1 && isRevealed && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center"
        >
          <Button
            variant="outline"
            onClick={handleNext}
            className="gap-2"
          >
            Next Moment
            <ChevronRight className="w-4 h-4" />
          </Button>
        </motion.div>
      )}
    </div>
  );
};

export default CriticalMoments;
