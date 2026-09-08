/**
 * GuidedOpeningLesson.jsx - Interactive Guided Opening Walkthrough
 * 
 * This replaces the static text dump with an engaging, coach-led experience.
 * The coach walks you through each move, explaining WHY it's played.
 * 
 * Features:
 * - Auto-play mode with move-by-move narration
 * - Coach voice explains each move naturally
 * - "Why?" button for deeper explanations
 * - Position-aware context from our coaching engine
 */

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Chess } from "chess.js";
import { motion, AnimatePresence } from "framer-motion";
import {
  Play,
  Pause,
  SkipForward,
  SkipBack,
  RotateCcw,
  MessageCircle,
  Volume2,
  ChevronRight,
  Brain,
  Lightbulb,
  Target,
  HelpCircle,
  Loader2
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import LichessBoard from "@/components/LichessBoard";
import { API } from "@/App";

// Coach personality messages for different situations
const COACH_INTROS = {
  white: [
    "Let me show you how to play this opening as White. Watch the board and I'll explain each move.",
    "Ready to learn? I'll walk you through every move and tell you exactly why we play it.",
    "This is one of my favorite openings to teach. Let's go through it together, move by move."
  ],
  black: [
    "When your opponent opens, here's how you respond. Watch closely!",
    "Playing Black means reacting smartly. Let me show you the key ideas.",
    "Defense doesn't mean passive - I'll show you how to fight back effectively."
  ]
};

const COACH_TRANSITIONS = [
  "Now watch this...",
  "Here's the key idea...",
  "This is important...",
  "Pay attention here...",
  "Notice how we...",
  "The reason for this move..."
];

const GuidedOpeningLesson = ({
  openingKey,
  opening,
  plan,
  onComplete,
  onStartPractice
}) => {
  const boardRef = useRef(null);
  const chessRef = useRef(new Chess());
  const autoPlayRef = useRef(null);
  const completionTimerRef = useRef(null);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;
  
  const [currentMoveIndex, setCurrentMoveIndex] = useState(-1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playSpeed, setPlaySpeed] = useState(3000); // 3 seconds per move
  const [coachMessage, setCoachMessage] = useState(null);
  const [showingWhy, setShowingWhy] = useState(false);
  const [deeperExplanation, setDeeperExplanation] = useState(null);
  const [loadingDeeper, setLoadingDeeper] = useState(false);
  const [lastMoveSquares, setLastMoveSquares] = useState(null);
  const [showIntro, setShowIntro] = useState(true);
  const [currentFen, setCurrentFen] = useState("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  
  // The coach's running order. Each chapter carries a move list that starts
  // from the initial position, because a trap or a variation begins part-way
  // down a branch and the board replays from move zero.
  const [chapterIndex, setChapterIndex] = useState(0);
  const chapters = useMemo(() => plan?.chapters || [], [plan]);
  const chapter = chapters.length ? chapters[Math.min(chapterIndex, chapters.length - 1)] : null;

  const mainLine = useMemo(() => {
    if (chapter) {
      return (chapter.play || []).map((m) => ({
        move: m.move,
        explanation: m.say || "",
        ask: m.ask || null,
        ifWrong: m.if_wrong || null,
      }));
    }
    // No plan yet, or an opening without one: fall back to the plain line
    // rather than show an empty board.
    return opening?.main_line || [];
  }, [chapter, opening?.main_line]);

  const isLastChapter = !chapters.length || chapterIndex >= chapters.length - 1;

  const goToChapter = useCallback((index) => {
    const next = Math.max(0, Math.min(index, Math.max(chapters.length - 1, 0)));
    setChapterIndex(next);
    setCurrentMoveIndex(-1);
    setShowIntro(true);
    setIsPlaying(false);
  }, [chapters.length]);
  const keyIdeas = opening?.key_ideas || [];
  const userColor = opening?.color || "white";
  const introMessage = useMemo(() => {
    const messages = COACH_INTROS[userColor] || COACH_INTROS.white;
    return messages[Math.floor(Math.random() * messages.length)];
  }, [userColor]);
  
  // Update board position
  const updateBoard = useCallback((moveIndex) => {
    chessRef.current.reset();
    let lastMove = null;
    
    for (let i = 0; i <= moveIndex && i < mainLine.length; i++) {
      const moveData = mainLine[i];
      const move = chessRef.current.move(moveData.move);
      if (move) {
        lastMove = { from: move.from, to: move.to };
      }
    }
    
    setCurrentFen(chessRef.current.fen());
    setLastMoveSquares(lastMove ? [lastMove.from, lastMove.to] : null);
    
    // Update coach message
    if (moveIndex >= 0 && moveIndex < mainLine.length) {
      const moveData = mainLine[moveIndex];
      const moveNum = Math.floor(moveIndex / 2) + 1;
      const isWhite = moveIndex % 2 === 0;
      
      setCoachMessage({
        move: moveData.move,
        moveNumber: moveNum,
        isWhite,
        explanation: moveData.explanation || "A key move in this opening.",
        transition: COACH_TRANSITIONS[Math.floor(Math.random() * COACH_TRANSITIONS.length)]
      });
    } else {
      setCoachMessage(null);
    }
    
    setDeeperExplanation(null);
    setShowingWhy(false);
  }, [mainLine]);
  
  // Go to specific move
  const goToMove = useCallback((index) => {
    const newIndex = Math.max(-1, Math.min(index, mainLine.length - 1));
    setCurrentMoveIndex(newIndex);
    setShowIntro(newIndex === -1);
    updateBoard(newIndex);
    
    // Reaching the end of a chapter is not the end of the lesson. Only the
    // last one finishes; the rest hand over to the next.
    if (newIndex === mainLine.length - 1 && mainLine.length > 0) {
      if (completionTimerRef.current) clearTimeout(completionTimerRef.current);
      completionTimerRef.current = setTimeout(() => {
        setIsPlaying(false);
        completionTimerRef.current = null;
        if (isLastChapter && onCompleteRef.current) {
          onCompleteRef.current();
        }
      }, 1000);
    }
  }, [mainLine.length, updateBoard, isLastChapter]);
  
  // Auto-play logic
  useEffect(() => {
    if (isPlaying) {
      autoPlayRef.current = setInterval(() => {
        setCurrentMoveIndex(prev => {
          const next = prev + 1;
          if (next >= mainLine.length) {
            setIsPlaying(false);
            return prev;
          }
          goToMove(next);
          return next;
        });
      }, playSpeed);
    } else {
      if (autoPlayRef.current) {
        clearInterval(autoPlayRef.current);
      }
    }
    
    return () => {
      if (autoPlayRef.current) {
        clearInterval(autoPlayRef.current);
      }
      if (completionTimerRef.current) {
        clearTimeout(completionTimerRef.current);
        completionTimerRef.current = null;
      }
    };
  }, [isPlaying, playSpeed, mainLine.length, goToMove]);
  
  // Start lesson
  const startLesson = () => {
    setShowIntro(false);
    goToMove(0);
    setIsPlaying(true);
  };
  
  // Toggle play/pause
  const togglePlay = () => {
    if (currentMoveIndex === -1) {
      startLesson();
    } else {
      setIsPlaying(!isPlaying);
    }
  };
  
  // Get deeper explanation from AI
  const getWhyExplanation = async () => {
    if (!coachMessage || loadingDeeper) return;
    
    setLoadingDeeper(true);
    setShowingWhy(true);
    
    try {
      // Try to get a deeper explanation from thinking coach
      const res = await fetch(`${API}/thinking-coach/mindset-prompt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          fen: chessRef.current.fen(),
          move_history: mainLine.slice(0, currentMoveIndex + 1).map(m => m.move),
          user_color: userColor,
          context: {
            opening_name: opening?.name,
            move_just_played: coachMessage.move
          }
        })
      });
      
      if (res.ok) {
        const data = await res.json();
        setDeeperExplanation({
          question: data.question || "What's the idea behind this move?",
          insight: data.insight || coachMessage.explanation,
          keyPoint: data.key_point || null
        });
      } else {
        // Fallback to basic explanation
        setDeeperExplanation({
          question: "Why this move?",
          insight: coachMessage.explanation,
          keyPoint: keyIdeas[0] || null
        });
      }
    } catch (err) {
      console.error("Error getting deeper explanation:", err);
      setDeeperExplanation({
        question: "Why this move?",
        insight: coachMessage.explanation,
        keyPoint: null
      });
    } finally {
      setLoadingDeeper(false);
    }
  };
  
  // Reset to beginning
  const reset = () => {
    setIsPlaying(false);
    setCurrentMoveIndex(-1);
    setShowIntro(true);
    setCoachMessage(null);
    setDeeperExplanation(null);
    setShowingWhy(false);
    chessRef.current.reset();
    setCurrentFen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
    setLastMoveSquares(null);
  };
  
  const isComplete = currentMoveIndex === mainLine.length - 1;
  return (
    <div className="guided-opening-lesson space-y-4">
      {/* The spine. It shows where the student is and what is coming, and it
          is deliberately not a menu: a chapter only becomes clickable once it
          has been reached, so you can go back over something but you are
          never asked to choose between lines you have not seen yet. */}
      {chapters.length > 1 && (
        <div className="flex flex-wrap items-center gap-x-2 gap-y-2" data-testid="lesson-spine">
          {chapters.map((c, i) => {
            const reached = i <= chapterIndex;
            const current = i === chapterIndex;
            return (
              <button
                key={c.key || i}
                type="button"
                disabled={!reached}
                onClick={() => reached && goToChapter(i)}
                data-testid={`lesson-chapter-${i}`}
                className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] transition-colors sm:text-xs ${
                  current
                    ? "border-primary bg-primary/10 text-primary"
                    : reached
                    ? "border-border bg-background/60 text-foreground hover:border-primary/45"
                    : "border-border/50 bg-background/30 text-muted-foreground/50 cursor-default"
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    reached ? "bg-primary" : "bg-muted-foreground/40"
                  }`}
                />
                {c.title}
              </button>
            );
          })}
        </div>
      )}

      {chapter?.coach_intro && (
        <p className="text-sm text-muted-foreground" data-testid="chapter-intro">
          {chapter.coach_intro}
        </p>
      )}

      <div className="grid min-w-0 items-start gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(340px,0.72fr)] lg:gap-7">
      <div className="min-w-0 space-y-3">
        {/* Board */}
        <Card className="experience-board-stage max-w-full overflow-hidden border-border/70 bg-card p-1.5 shadow-[0_24px_64px_hsl(var(--experience-shadow)/0.18)] sm:p-3">
          <CardContent className="p-0">
            <div className="relative overflow-hidden rounded-md sm:rounded-lg">
              <div className="aspect-square w-full max-w-full">
                <LichessBoard
                  ref={boardRef}
                  fen={currentFen}
                  orientation={userColor}
                  lastMove={lastMoveSquares}
                  viewOnly={true}
                  interactive={false}
                />
              </div>

              {/* Move badge overlay */}
              {currentMoveIndex >= 0 && coachMessage && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="absolute left-2 top-2"
                >
                  <Badge className="bg-black/70 px-2 py-1 text-[11px] text-white backdrop-blur sm:px-3 sm:text-xs">
                    {coachMessage.moveNumber}.
                    {coachMessage.isWhite ? "" : "..."}
                    <span className="ml-1 font-mono font-bold">{coachMessage.move}</span>
                  </Badge>
                </motion.div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Progress bar */}
        <div className="flex items-center gap-3 px-1">
          <span className="text-xs font-medium tabular-nums text-muted-foreground">
            {currentMoveIndex + 1} / {mainLine.length}
          </span>
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
            <motion.div
              className="h-full bg-primary"
              initial={{ width: 0 }}
              animate={{
                width: `${((currentMoveIndex + 1) / mainLine.length) * 100}%`
              }}
              transition={{ duration: 0.3 }}
            />
          </div>
        </div>
      </div>

      <div className="min-w-0 space-y-4 lg:sticky lg:top-6">
      {/* Coach Message Panel */}
      <Card className="experience-surface overflow-hidden border-border/70 bg-card shadow-[0_18px_48px_hsl(var(--experience-shadow)/0.08)]">
        <div className="border-b border-border/60 bg-muted/40 px-4 py-3 sm:px-5">
          <p className="experience-eyebrow text-[10px] font-bold uppercase">Your coach</p>
        </div>
        <CardContent className="p-4 sm:p-6">
          <AnimatePresence mode="wait">
            {showIntro ? (
              <motion.div
                key="intro"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="space-y-3"
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-primary/10">
                    <MessageCircle className="h-5 w-5 text-primary" />
                  </div>
                  <div className="min-w-0">
                    <p className="mb-1 text-sm font-semibold text-foreground">Ready when you are</p>
                    <p className="experience-coach-copy text-base leading-relaxed text-foreground sm:text-lg">{introMessage}</p>
                  </div>
                </div>
                
                {keyIdeas.length > 0 && (
                  <div className="mt-4 sm:pl-13">
                    <p className="mb-2 text-xs font-medium text-muted-foreground">Key ideas to watch for</p>
                    <div className="flex flex-wrap gap-2">
                      {keyIdeas.slice(0, 3).map((idea, i) => (
                        <Badge 
                          key={i} 
                          variant="outline" 
                          className="max-w-full border-border bg-muted/60 text-xs font-normal text-foreground"
                        >
                          <Target className="mr-1 h-3 w-3 text-primary" />
                          {idea.length > 40 ? idea.substring(0, 40) + "..." : idea}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
                
                <Button 
                  onClick={startLesson} 
                  className="experience-primary mt-4 h-11 w-full"
                >
                  <Play className="w-4 h-4 mr-2" />
                  Start Lesson
                </Button>
              </motion.div>
            ) : coachMessage ? (
              <motion.div
                key={`move-${currentMoveIndex}`}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="space-y-3"
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-primary/10">
                    <MessageCircle className="h-5 w-5 text-primary" />
                  </div>
                  <div className="flex-1">
                    <p className="mb-1 text-xs font-semibold uppercase tracking-[0.12em] text-primary">{coachMessage.transition}</p>
                    <p className="text-lg text-foreground">
                      <span className="font-mono font-bold text-primary">
                        {coachMessage.moveNumber}.{coachMessage.isWhite ? "" : ".."}{coachMessage.move}
                      </span>
                    </p>
                    <p className="experience-coach-copy mt-2 leading-relaxed text-foreground">{coachMessage.explanation}</p>
                  </div>
                </div>
                
                {/* Deeper explanation */}
                <AnimatePresence>
                  {showingWhy && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      className="overflow-hidden"
                    >
                      {loadingDeeper ? (
                        <div className="flex items-center gap-2 p-3 text-muted-foreground">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          <span className="text-sm">Thinking deeper...</span>
                        </div>
                      ) : deeperExplanation && (
                        <div className="mt-2 rounded-xl border border-accent/20 bg-accent/10 p-3 sm:p-4">
                          <div className="flex items-start gap-2">
                            <Brain className="mt-0.5 h-4 w-4 text-accent-foreground" />
                            <div>
                              <p className="mb-1 text-xs font-semibold text-accent-foreground">
                                {deeperExplanation.question}
                              </p>
                              <p className="text-sm leading-relaxed text-foreground">
                                {deeperExplanation.insight}
                              </p>
                              {deeperExplanation.keyPoint && (
                                <p className="mt-2 text-xs text-muted-foreground">
                                  <Lightbulb className="mr-1 inline h-3 w-3 text-primary" />
                                  {deeperExplanation.keyPoint}
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>
                
                {/* Why button */}
                {!showingWhy && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={getWhyExplanation}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <HelpCircle className="w-4 h-4 mr-1" />
                    Why this move?
                  </Button>
                )}
              </motion.div>
            ) : isComplete ? (
              <motion.div
                key="complete"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-4"
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-primary/10">
                    <Target className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <p className="font-semibold text-primary">Lesson complete</p>
                    <p className="mt-1 text-muted-foreground">
                      Now you know the main line. Ready to test yourself?
                    </p>
                  </div>
                </div>
                
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <Button 
                    onClick={reset}
                    variant="outline"
                    className="w-full border-border"
                  >
                    <RotateCcw className="w-4 h-4 mr-2" />
                    Watch Again
                  </Button>
                  {onStartPractice && (
                    <Button 
                      onClick={onStartPractice}
                      className="experience-primary w-full"
                    >
                      <Play className="w-4 h-4 mr-2" />
                      Practice Now
                    </Button>
                  )}
                </div>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </CardContent>
      </Card>
      
      {/* Controls */}
      {!showIntro && (
        <div className="space-y-3">
          <div className="grid grid-cols-[auto_auto_minmax(0,1fr)_auto] items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              onClick={reset}
              className="border-border"
            >
              <RotateCcw className="h-4 w-4" />
            </Button>

            <Button
              variant="outline"
              size="icon"
              onClick={() => goToMove(currentMoveIndex - 1)}
              disabled={currentMoveIndex <= 0}
              className="border-border"
            >
              <SkipBack className="h-4 w-4" />
            </Button>

            <Button
              onClick={togglePlay}
              className={`min-w-0 px-2 sm:px-4 ${isPlaying ? "bg-secondary text-secondary-foreground hover:bg-secondary/90" : "experience-primary"}`}
            >
              {isPlaying ? (
                <>
                  <Pause className="mr-1.5 h-4 w-4 sm:mr-2" />
                  Pause
                </>
              ) : (
                <>
                  <Play className="mr-1.5 h-4 w-4 sm:mr-2" />
                  {isComplete ? "Replay" : "Continue"}
                </>
              )}
            </Button>

            <Button
              variant="outline"
              size="icon"
              onClick={() => goToMove(currentMoveIndex + 1)}
              disabled={currentMoveIndex >= mainLine.length - 1}
              className="border-border"
            >
              <SkipForward className="h-4 w-4" />
            </Button>
          </div>

          {/* Speed control */}
          <div className="flex items-center justify-end gap-2 rounded-lg border border-border/60 bg-muted/35 px-3 py-2">
            <span className="text-xs text-muted-foreground">Playback speed</span>
            <Volume2 className="h-4 w-4 text-muted-foreground" />
            <Slider
              value={[playSpeed]}
              onValueChange={([val]) => setPlaySpeed(val)}
              min={1000}
              max={5000}
              step={500}
              className="w-24 sm:w-28"
            />
          </div>
        </div>
      )}
      </div>
    </div>
    </div>
  );
};

export default GuidedOpeningLesson;
