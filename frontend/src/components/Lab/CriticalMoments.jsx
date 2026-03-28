/**
 * CriticalMoments - Interactive Training Loop
 * 
 * Each moment follows this guided sequence:
 * 1. Coach Prompt → introduces the situation
 * 2. Thinking Lens → what type of idea to look for
 * 3. Thinking Questions → guide the player's thought process
 * 4. User attempts a move on the board
 * 5. Reveal best move + explanation
 * 6. Reflection prompt
 * 7. Lesson takeaway
 * 
 * The best move is NEVER shown before the user interacts.
 */

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Chess } from "chess.js";
import ThoughtProcessWalkthrough from "./ThoughtProcessWalkthrough";
import {
  Eye,
  Play,
  ChevronRight,
  ChevronLeft,
  Lightbulb,
  XCircle,
  CheckCircle2,
  HelpCircle,
  ThumbsUp,
  Zap,
  AlertTriangle,
  BookOpen,
  Brain,
  Shield,
  Crown,
  Flag,
  Clock,
  Lock,
  Layers,
  TrendingUp,
  Target,
  MessageCircle
} from "lucide-react";

// Map icon names from backend to Lucide components
const ICON_MAP = {
  "zap": Zap,
  "alert-triangle": AlertTriangle,
  "brain": Brain,
  "book-open": BookOpen,
  "shield": Shield,
  "crown": Crown,
  "flag": Flag,
  "clock": Clock,
  "lock": Lock,
  "layers": Layers,
  "trending-up": TrendingUp,
  "move": Target,
  "eye": Eye,
};

// Moment stages for the guided flow
const STAGES = {
  INTRO: "intro",           // Coach prompt + thinking lens
  THINKING: "thinking",     // Questions + try move  
  ATTEMPT_RESULT: "result", // After user attempts a move
  REVEAL: "reveal",         // Best move + explanation
  REFLECTION: "reflection", // What did you overlook?
  LESSON: "lesson",         // Takeaway
};

const CriticalMoments = ({ 
  moments = [],
  userColor,
  onNavigateToMove,
  onFeedback,
  onPlayBestLine,
  onStartInteractive,
  onClearInteractive,
  onTryAgain,
  userAttemptResult,
  gameId,
  playerLevel = "casual",
  playerLevelDisplay = "Player",
  playerLevelEmoji,
  coachingVoice = {},
  chessUnderstanding = null
}) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [stage, setStage] = useState(STAGES.INTRO);
  const [reflectionAnswer, setReflectionAnswer] = useState(null);
  const [completedMoments, setCompletedMoments] = useState(new Set());
  const [showThoughtProcess, setShowThoughtProcess] = useState(false);

  // Navigate to position when moment changes
  useEffect(() => {
    if (moments.length > 0 && onNavigateToMove) {
      const m = moments[currentIndex];
      if (m) onNavigateToMove(m.move_number, null, null);
    }
    setStage(STAGES.INTRO);
    setReflectionAnswer(null);
  }, [currentIndex, moments.length]);

  // When user makes an attempt, transition to result stage
  useEffect(() => {
    if (userAttemptResult) {
      setStage(STAGES.ATTEMPT_RESULT);
    }
  }, [userAttemptResult]);

  if (!moments || moments.length === 0) {
    return (
      <Card className="border-0 bg-slate-800/30">
        <CardContent className="p-6 text-center" data-testid="no-moments">
          <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto mb-3" />
          <h3 className="font-semibold mb-2">Clean Game</h3>
          <p className="text-sm text-muted-foreground">
            No critical moments to review. Well played!
          </p>
        </CardContent>
      </Card>
    );
  }

  const moment = moments[currentIndex];
  const coaching = moment.coaching || {};
  const thinkingLens = coaching.thinking_lens || {};
  const insight = moment.insight || {};
  const LensIcon = ICON_MAP[thinkingLens.icon] || HelpCircle;

  const goToMoment = (idx) => {
    setCurrentIndex(idx);
    setShowThoughtProcess(false);
    if (onClearInteractive) onClearInteractive();
  };

  const handleReveal = () => {
    setStage(STAGES.REVEAL);
    if (onNavigateToMove) {
      // Show arrows on the board
      let yourMoveUci = null;
      let bestMoveUci = null;
      try {
        const chess = new Chess(moment.fen);
        if (moment.best_move) {
          const bm = chess.move(moment.best_move, { sloppy: true });
          if (bm) { bestMoveUci = bm.from + bm.to; chess.undo(); }
        }
        if (moment.your_move) {
          const ym = chess.move(moment.your_move, { sloppy: true });
          if (ym) { yourMoveUci = ym.from + ym.to; }
        }
      } catch (e) { /* ignore */ }
      onNavigateToMove(moment.move_number, yourMoveUci, bestMoveUci);
    }
  };

  const handleNext = () => {
    setCompletedMoments(prev => new Set([...prev, currentIndex]));
    if (currentIndex < moments.length - 1) {
      goToMoment(currentIndex + 1);
    }
  };

  const handlePrev = () => {
    if (currentIndex > 0) goToMoment(currentIndex - 1);
  };

  const severity = (() => {
    const loss = Math.abs(moment.cp_loss || 0);
    if (loss >= 300) return { label: "Serious mistake", color: "bg-red-500/80", text: "text-red-400" };
    if (loss >= 200) return { label: "Mistake", color: "bg-amber-500/80", text: "text-amber-400" };
    if (loss >= 100) return { label: "Inaccuracy", color: "bg-yellow-500/80", text: "text-yellow-400" };
    return { label: "Minor slip", color: "bg-slate-500/80", text: "text-slate-400" };
  })();

  return (
    <div className="space-y-4" data-testid="moments-training">
      {/* Progress bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h3 className="font-semibold text-sm">Training Session</h3>
          <div className="flex gap-1">
            {moments.map((_, i) => (
              <button
                key={i}
                onClick={() => goToMoment(i)}
                className={`w-2.5 h-2.5 rounded-full transition-all ${
                  i === currentIndex 
                    ? "bg-primary scale-125" 
                    : completedMoments.has(i) 
                      ? "bg-emerald-500/60" 
                      : "bg-slate-600"
                }`}
                data-testid={`moment-dot-${i}`}
              />
            ))}
          </div>
          <span className="text-xs text-muted-foreground">
            {currentIndex + 1} of {moments.length}
          </span>
        </div>
        <div className="flex gap-1">
          <Button variant="ghost" size="sm" onClick={handlePrev} disabled={currentIndex === 0} className="h-7 w-7 p-0" data-testid="moment-prev-btn">
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="sm" onClick={handleNext} disabled={currentIndex === moments.length - 1} className="h-7 w-7 p-0" data-testid="moment-next-btn">
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Main moment card */}
      <Card className="border-0 bg-slate-800/50 overflow-hidden">
        <CardContent className="p-0">
          {/* Moment header with severity + move number */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border/20 bg-slate-800/80">
            <div className="flex items-center gap-2">
              <Badge className={`${severity.color} text-[10px] px-2 py-0.5`}>
                Move {moment.move_number}
              </Badge>
              <span className={`text-xs ${severity.text}`}>{severity.label}</span>
            </div>
            {stage !== STAGES.INTRO && stage !== STAGES.THINKING && (
              <Badge variant="outline" className="text-[10px] text-muted-foreground">
                {stage === STAGES.REVEAL ? "Review" : stage === STAGES.REFLECTION ? "Reflect" : stage === STAGES.LESSON ? "Lesson" : "Result"}
              </Badge>
            )}
          </div>

          {/* ============ STAGE: INTRO ============ */}
          {stage === STAGES.INTRO && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-5">
              {/* Coach prompt */}
              <div className="flex items-start gap-3 mb-5">
                <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <MessageCircle className="w-4 h-4 text-primary" />
                </div>
                <p className="text-sm leading-relaxed text-foreground" data-testid="coach-prompt">
                  {coaching.coach_prompt || "Look at this position carefully."}
                </p>
              </div>

              {/* Thinking Lens */}
              <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg mb-5" data-testid="thinking-lens">
                <div className="flex items-center gap-2 mb-1.5">
                  <LensIcon className="w-4 h-4 text-amber-400" />
                  <span className="text-xs font-semibold text-amber-400 uppercase tracking-wider">
                    {thinkingLens.label || "Key Moment"}
                  </span>
                </div>
                <p className="text-sm text-amber-200/90">
                  {thinkingLens.text || "Study this position carefully."}
                </p>
              </div>

              <Button
                onClick={() => setStage(STAGES.THINKING)}
                className="w-full gap-2"
                data-testid="continue-to-thinking-btn"
              >
                <Brain className="w-4 h-4" />
                Start Thinking
              </Button>
            </motion.div>
          )}

          {/* ============ STAGE: THINKING ============ */}
          {stage === STAGES.THINKING && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-5">
              {/* Thinking Lens reminder (compact) */}
              <div className="flex items-center gap-2 mb-4 px-3 py-2 bg-amber-500/10 rounded-md" data-testid="thinking-lens-compact">
                <LensIcon className="w-3.5 h-3.5 text-amber-400" />
                <span className="text-xs text-amber-300 font-medium">{thinkingLens.label}</span>
              </div>

              {/* Thinking Questions */}
              <div className="space-y-2.5 mb-6" data-testid="thinking-questions">
                {(coaching.thinking_questions || []).map((q, i) => (
                  <div key={i} className="flex items-start gap-2.5 text-sm">
                    <span className="w-5 h-5 rounded-full bg-slate-700 text-slate-300 flex items-center justify-center text-xs flex-shrink-0 mt-0.5">
                      {i + 1}
                    </span>
                    <p className="text-muted-foreground leading-relaxed">{q}</p>
                  </div>
                ))}
              </div>

              {/* Action buttons */}
              <div className="flex gap-3">
                <Button
                  variant="outline"
                  onClick={() => onStartInteractive?.(moment)}
                  className="flex-1 gap-2"
                  data-testid="try-move-btn"
                >
                  <Play className="w-4 h-4" />
                  Try move on board
                </Button>
                <Button
                  variant="ghost"
                  onClick={handleReveal}
                  className="text-muted-foreground gap-2"
                  data-testid="reveal-btn"
                >
                  <Eye className="w-4 h-4" />
                  Reveal
                </Button>
              </div>

              {/* User attempt feedback */}
              <AnimatePresence>
                {userAttemptResult && stage === STAGES.THINKING && (
                  <MoveAttemptFeedback
                    result={userAttemptResult}
                    onReveal={handleReveal}
                    onTryAgain={onTryAgain}
                  />
                )}
              </AnimatePresence>
            </motion.div>
          )}

          {/* ============ STAGE: ATTEMPT RESULT ============ */}
          {stage === STAGES.ATTEMPT_RESULT && userAttemptResult && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-5">
              <MoveAttemptFeedback
                result={userAttemptResult}
                onReveal={handleReveal}
                onTryAgain={onTryAgain}
                standalone
              />
            </motion.div>
          )}

          {/* ============ STAGE: REVEAL ============ */}
          {stage === STAGES.REVEAL && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="divide-y divide-border/20">
              {/* Best Move */}
              <div className="p-4 bg-emerald-500/5">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                  <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">Best Move</span>
                </div>
                <p className="text-xl font-bold text-emerald-400 mb-1" data-testid="best-move-text">
                  {moment.best_move}
                </p>
                {insight.what_best_move_achieves && (
                  <p className="text-sm text-emerald-200/80 leading-relaxed" data-testid="best-move-why">
                    {insight.what_best_move_achieves}
                  </p>
                )}
                {onPlayBestLine && (
                  <Button variant="ghost" size="sm" onClick={() => onPlayBestLine(moment)} className="mt-2 text-xs text-emerald-400 hover:text-emerald-300 p-0 h-auto gap-1">
                    <Play className="w-3 h-3" /> Play this line
                  </Button>
                )}
              </div>

              {/* Your Move */}
              <div className="p-4 bg-red-500/5">
                <div className="flex items-center gap-2 mb-2">
                  <XCircle className="w-4 h-4 text-red-400" />
                  <span className="text-xs font-semibold text-red-400 uppercase tracking-wider">You played</span>
                </div>
                <p className="text-xl font-bold text-red-400 mb-1" data-testid="your-move-text">
                  {moment.your_move}
                </p>
                {insight.why_your_move_failed && (
                  <p className="text-sm text-red-200/80 leading-relaxed">
                    {insight.why_your_move_failed}
                  </p>
                )}
              </div>

              {/* What you missed */}
              {insight.what_you_missed && (
                <div className="p-4 bg-amber-500/5">
                  <div className="flex items-center gap-2 mb-2">
                    <Eye className="w-4 h-4 text-amber-400" />
                    <span className="text-xs font-semibold text-amber-400 uppercase tracking-wider">What You Missed</span>
                  </div>
                  <p className="text-sm text-amber-200/90 leading-relaxed">
                    {insight.what_you_missed}
                  </p>
                </div>
              )}

              {/* How to Think (Thought Process Walkthrough) */}
              <div className="p-4">
                {!showThoughtProcess ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowThoughtProcess(true)}
                    className="w-full justify-between bg-blue-500/10 border-blue-500/30 hover:bg-blue-500/20 text-blue-300"
                    data-testid="show-thought-process-btn"
                  >
                    <div className="flex items-center gap-2">
                      <Brain className="w-4 h-4" />
                      <span className="text-xs">How Should I Have Thought Here?</span>
                    </div>
                    <ChevronRight className="w-4 h-4" />
                  </Button>
                ) : (
                  <ThoughtProcessWalkthrough
                    fen={moment.fen}
                    bestMove={moment.best_move}
                    playedMove={moment.your_move}
                    compact={false}
                    autoFetch={true}
                  />
                )}
              </div>

              <div className="p-3 flex justify-end border-t border-border/20">
                <Button size="sm" onClick={() => setStage(STAGES.REFLECTION)} className="gap-2" data-testid="continue-to-reflection-btn">
                  Continue
                  <ChevronRight className="w-3 h-3" />
                </Button>
              </div>
            </motion.div>
          )}

          {/* ============ STAGE: REFLECTION ============ */}
          {stage === STAGES.REFLECTION && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-5">
              <div className="flex items-center gap-2 mb-4">
                <HelpCircle className="w-4 h-4 text-violet-400" />
                <span className="text-xs font-semibold text-violet-400 uppercase tracking-wider">Reflection</span>
              </div>
              <p className="text-sm font-medium mb-4" data-testid="reflection-prompt">
                {coaching.reflection?.prompt || "What did you overlook?"}
              </p>
              <div className="grid grid-cols-2 gap-2 mb-4" data-testid="reflection-options">
                {(coaching.reflection?.options || []).map((opt) => (
                  <Button
                    key={opt.id}
                    variant={reflectionAnswer === opt.id ? "default" : "outline"}
                    size="sm"
                    className={`text-xs justify-start h-auto py-2 px-3 whitespace-normal text-left ${
                      reflectionAnswer === opt.id ? "ring-2 ring-violet-500/50" : ""
                    }`}
                    onClick={() => {
                      setReflectionAnswer(opt.id);
                      // Reflections are stored silently — no modal needed
                    }}
                    data-testid={`reflection-option-${opt.id}`}
                  >
                    {opt.label}
                  </Button>
                ))}
              </div>
              <Button
                size="sm"
                onClick={() => setStage(STAGES.LESSON)}
                disabled={!reflectionAnswer}
                className="w-full gap-2"
                data-testid="continue-to-lesson-btn"
              >
                See Lesson
                <ChevronRight className="w-3 h-3" />
              </Button>
            </motion.div>
          )}

          {/* ============ STAGE: LESSON ============ */}
          {stage === STAGES.LESSON && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-5">
              <div className="p-4 bg-violet-500/10 border border-violet-500/20 rounded-lg mb-5" data-testid="lesson-takeaway">
                <div className="flex items-center gap-2 mb-2">
                  <Lightbulb className="w-4 h-4 text-violet-400" />
                  <span className="text-xs font-semibold text-violet-400 uppercase tracking-wider">Lesson</span>
                </div>
                <p className="text-sm font-medium text-violet-200 leading-relaxed">
                  {coaching.lesson_takeaway || insight.pattern_to_remember || "Learn from this position."}
                </p>
                {insight.ask_yourself && (
                  <p className="text-xs text-muted-foreground mt-2 italic">
                    Ask yourself: "{insight.ask_yourself}"
                  </p>
                )}
              </div>

              {/* Navigation */}
              <div className="flex items-center justify-between">
                <Button variant="ghost" size="sm" className="text-xs gap-1" onClick={handleNext}>
                  <ThumbsUp className="w-3 h-3" /> Got it
                </Button>
                {currentIndex < moments.length - 1 ? (
                  <Button size="sm" onClick={handleNext} className="gap-2" data-testid="next-moment-btn">
                    Next Moment
                    <ChevronRight className="w-4 h-4" />
                  </Button>
                ) : (
                  <div className="flex items-center gap-2 text-sm text-emerald-400">
                    <CheckCircle2 className="w-4 h-4" />
                    <span className="font-medium">Session Complete</span>
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

/**
 * Sub-component: Feedback after user tries a move
 */
const MoveAttemptFeedback = ({ result, onReveal, onTryAgain, standalone = false }) => {
  if (!result) return null;

  const isCorrect = result.correct;
  const quality = result.quality;
  const isGood = isCorrect || quality === "excellent" || quality === "best";
  const isOkay = quality === "okay" || quality === "inaccuracy";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`${standalone ? "" : "mt-4"} p-4 rounded-lg ${
        isGood ? "bg-emerald-500/10 border border-emerald-500/20"
        : isOkay ? "bg-yellow-500/10 border border-yellow-500/20"
        : "bg-red-500/10 border border-red-500/20"
      }`}
      data-testid="attempt-feedback"
    >
      <div className="flex items-start gap-3">
        {isGood ? (
          <CheckCircle2 className="w-5 h-5 text-emerald-400 mt-0.5 flex-shrink-0" />
        ) : isOkay ? (
          <AlertTriangle className="w-5 h-5 text-yellow-400 mt-0.5 flex-shrink-0" />
        ) : (
          <XCircle className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" />
        )}
        <div className="flex-1 space-y-2">
          <p className={`font-medium text-sm ${
            isGood ? "text-emerald-400" : isOkay ? "text-yellow-400" : "text-red-400"
          }`}>
            {result.message || (isGood ? "Well done!" : isOkay ? "Close, but there's better." : "Not quite.")}
          </p>
          {result.feedback && (
            <p className="text-xs text-muted-foreground">{result.feedback}</p>
          )}
          {!isCorrect && result.punishingMove && result.showPunishment && (
            <p className="text-xs text-orange-400">
              <Zap className="w-3 h-3 inline mr-1" />
              Opponent punishes with {result.punishingMove}
            </p>
          )}
          <div className="flex gap-2 pt-1">
            {!isCorrect && result.showTryAgain && onTryAgain && (
              <Button variant="outline" size="sm" onClick={onTryAgain} className="text-xs gap-1" data-testid="try-again-btn">
                <Play className="w-3 h-3" /> Try Again
              </Button>
            )}
            <Button size="sm" onClick={onReveal} className="text-xs gap-1" data-testid="reveal-after-attempt-btn">
              <Eye className="w-3 h-3" /> {isCorrect ? "See Full Analysis" : "Reveal Coach Explanation"}
            </Button>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default CriticalMoments;
