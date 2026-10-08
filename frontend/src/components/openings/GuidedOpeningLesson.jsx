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
  nextOpening,
  onComplete,
  onStartPractice,
  onNextLesson,
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

  // The spine unlocks as you go, so something has to do the unlocking.
  // goToChapter was the only writer of chapterIndex and its only caller is a
  // spine button guarded by `reached` (i <= chapterIndex) -- so the index
  // could never rise above 0 and every chapter after the first was
  // unreachable in all 36 multi-chapter openings. Finishing a chapter is what
  // earns the next one.
  const goToNextChapter = useCallback(() => {
    setChapterIndex((prev) => {
      const next = Math.min(prev + 1, Math.max(chapters.length - 1, 0));
      return next;
    });
    setCurrentMoveIndex(-1);
    setShowIntro(true);
    setIsPlaying(false);
  }, [chapters.length]);

  const nextChapterTitle = !isLastChapter
    ? String(chapters[chapterIndex + 1]?.title || "").trim()
    : "";

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
    <div className="guided-opening-lesson space-y-5 font-sans">
      {/* The spine. It shows where the student is and what is coming, and it
          is deliberately not a menu: a chapter only becomes clickable once it
          has been reached, so you can go back over something but you are
          never asked to choose between lines you have not seen yet. */}
      {chapters.length > 1 && (
        <div className="flex flex-wrap items-center justify-between gap-2" data-testid="lesson-spine">
          <div className="flex flex-wrap items-center gap-2">
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
                  className={`group flex items-center gap-2 rounded-full border px-4 py-1.5 text-xs font-heading font-bold transition-all duration-200 sm:text-sm ${
                    current
                      ? "border-primary/60 bg-primary/15 text-primary shadow-[0_0_15px_rgba(16,185,129,0.25)] ring-2 ring-primary/20"
                      : reached
                      ? "border-slate-700/80 bg-slate-900/70 text-slate-200 hover:border-primary/40 hover:bg-slate-800/80"
                      : "border-slate-800/50 bg-slate-950/30 text-slate-500/50 cursor-default"
                  }`}
                >
                  <span
                    className={`h-2 w-2 rounded-full transition-all ${
                      current
                        ? "bg-primary shadow-[0_0_8px_rgba(52,211,153,0.9)]"
                        : reached
                        ? "bg-primary/60"
                        : "bg-slate-700"
                    }`}
                  />
                  {c.title}
                </button>
              );
            })}
          </div>

          {nextOpening && onNextLesson && (
            <button
              type="button"
              onClick={onNextLesson}
              className="flex items-center gap-1.5 rounded-full border border-cyan-500/40 bg-cyan-950/50 hover:bg-cyan-900/70 text-cyan-300 hover:text-white px-4 py-1.5 text-xs sm:text-sm font-heading font-black shadow-[0_0_15px_rgba(6,182,212,0.25)] transition-all cursor-pointer active:scale-95 ml-auto"
              data-testid="spine-next-lesson"
            >
              <span>Next: {nextOpening.name}</span>
              <ChevronRight className="w-4 h-4 text-cyan-400" />
            </button>
          )}
        </div>
      )}

      {chapter?.coach_intro && (
        <p className="text-sm sm:text-base font-medium text-slate-300/90 leading-relaxed" data-testid="chapter-intro">
          {chapter.coach_intro}
        </p>
      )}

      <div className="grid min-w-0 items-stretch gap-6 lg:grid-cols-[1.1fr_0.9fr] xl:grid-cols-[1.15fr_0.85fr] lg:gap-8 w-full">
        {/* Left Column: Big Chessboard Card */}
        <div className="min-w-0 flex flex-col justify-between space-y-4">
          {/* Board Frame Card */}
          <div className="relative mx-auto w-full max-w-[720px] rounded-3xl p-4 sm:p-6 bg-gradient-to-b from-slate-800/95 via-slate-900/98 to-slate-950 border border-slate-700/80 shadow-[0_25px_60px_-15px_rgba(0,0,0,0.9),0_0_35px_rgba(16,185,129,0.08)] flex flex-col justify-between">
            <div className="relative aspect-square w-full overflow-hidden rounded-2xl border border-black/40 shadow-2xl">
              <LichessBoard
                ref={boardRef}
                fen={currentFen}
                orientation={userColor}
                lastMove={lastMoveSquares}
                viewOnly={true}
                interactive={false}
              />

              {/* Move badge overlay */}
              {currentMoveIndex >= 0 && coachMessage && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="absolute left-3.5 top-3.5 z-30 pointer-events-none"
                >
                  <div className="flex items-center gap-2 rounded-2xl bg-black/90 px-4 py-2 text-sm sm:text-base font-heading font-black text-white backdrop-blur-md border border-white/25 shadow-2xl">
                    <span className="text-primary font-bold">
                      {coachMessage.moveNumber}.{coachMessage.isWhite ? "" : ".."}
                    </span>
                    <span className="font-mono font-black tracking-wide text-white">{coachMessage.move}</span>
                  </div>
                </motion.div>
              )}
            </div>

            {/* Progress bar and move count */}
            <div className="mt-4 flex w-full items-center gap-4 px-1">
              <span className="text-xs sm:text-sm font-heading font-black tabular-nums text-slate-300 min-w-[50px]">
                {currentMoveIndex + 1} / {mainLine.length}
              </span>
              <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-800/90 border border-slate-700/50">
                <motion.div
                  className="h-full bg-gradient-to-r from-emerald-500 via-teal-400 to-cyan-400 shadow-[0_0_15px_rgba(45,212,191,0.6)]"
                  initial={{ width: 0 }}
                  animate={{
                    width: `${((currentMoveIndex + 1) / Math.max(mainLine.length, 1)) * 100}%`
                  }}
                  transition={{ duration: 0.3 }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Coach & Narration Card (Large Height & Width) */}
        <div className="min-w-0 flex flex-col justify-between space-y-4">
          {/* Coach Message Panel */}
          <Card className="min-h-[580px] sm:min-h-[640px] lg:min-h-[660px] h-full flex flex-col justify-between overflow-hidden border border-slate-700/80 bg-slate-900/95 shadow-[0_25px_60px_-15px_rgba(0,0,0,0.85)] backdrop-blur-2xl rounded-3xl">
            <div className="flex items-center justify-between border-b border-slate-800 bg-slate-950/70 px-6 py-4">
              <div className="flex items-center gap-2.5">
                <span className="relative flex h-3 w-3">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex h-3 w-3 rounded-full bg-emerald-500" />
                </span>
                <p className="text-xs font-heading font-black uppercase tracking-widest text-emerald-400">
                  Your Coach
                </p>
              </div>
              <Badge variant="outline" className="border-slate-700 bg-slate-800/80 px-3 py-1 text-xs font-heading font-bold text-slate-200">
                {userColor === "white" ? "Playing White" : "Playing Black"}
              </Badge>
            </div>
            
            <CardContent className="p-6 sm:p-8 flex-1 flex flex-col justify-between space-y-6">
              <AnimatePresence mode="wait">
                {showIntro ? (
                  <motion.div
                    key="intro"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="flex-1 flex flex-col justify-between space-y-6"
                  >
                    <div className="space-y-4">
                      <div className="flex items-start gap-4">
                        <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-2xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.25)]">
                          <MessageCircle className="h-6 w-6" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-lg sm:text-xl font-heading font-black text-white">Ready when you are</p>
                          <p className="mt-2 text-base sm:text-lg lg:text-xl font-medium leading-relaxed text-slate-200">
                            {introMessage}
                          </p>
                        </div>
                      </div>
                      
                      {keyIdeas.length > 0 && (
                        <div className="mt-5 space-y-3 rounded-2xl border border-slate-800/90 bg-slate-950/60 p-4 sm:p-5">
                          <p className="text-xs sm:text-sm font-heading font-black uppercase tracking-wider text-slate-300 flex items-center gap-2">
                            <Target className="h-4 w-4 text-emerald-400" />
                            Key ideas to watch for
                          </p>
                          <div className="space-y-2.5">
                            {keyIdeas.map((idea, i) => (
                              <div 
                                key={i} 
                                className="flex items-start gap-3 rounded-xl border border-slate-800 bg-slate-900/70 p-3 sm:p-3.5 text-xs sm:text-sm font-semibold text-slate-200 shadow-sm"
                              >
                                <div className="mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full bg-emerald-500/20 text-[11px] font-black text-emerald-400">
                                  {i + 1}
                                </div>
                                <span className="leading-relaxed">{idea}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                    
                    <div className="mt-4 flex flex-col sm:flex-row gap-3">
                      <Button 
                        onClick={startLesson} 
                        className="h-14 flex-1 text-base sm:text-lg font-heading font-black bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 hover:from-emerald-400 hover:to-cyan-400 text-slate-950 shadow-[0_0_28px_rgba(16,185,129,0.4)] rounded-2xl transition-all duration-200 active:scale-[0.98]"
                      >
                        <Play className="w-5 h-5 mr-2 fill-current" />
                        Start Lesson
                      </Button>
                      {nextOpening && onNextLesson && (
                        <Button
                          onClick={onNextLesson}
                          variant="outline"
                          className="h-14 px-5 text-sm sm:text-base font-heading font-black border-cyan-500/40 bg-cyan-950/40 hover:bg-cyan-900/60 text-cyan-300 hover:text-white shadow-[0_0_20px_rgba(6,182,212,0.25)] rounded-2xl transition-all active:scale-[0.98] whitespace-nowrap"
                          data-testid="intro-next-lesson"
                        >
                          <span>Next: {nextOpening.name}</span>
                          <ChevronRight className="w-4 h-4 ml-1" />
                        </Button>
                      )}
                    </div>
                  </motion.div>
                ) : coachMessage ? (
                  <motion.div
                    key={`move-${currentMoveIndex}`}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="flex-1 flex flex-col justify-between space-y-6"
                  >
                    <div className="space-y-4">
                      <div className="flex items-start gap-4">
                        <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-2xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.25)]">
                          <MessageCircle className="h-6 w-6" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="mb-1 text-xs sm:text-sm font-heading font-black uppercase tracking-wider text-emerald-400">
                            {coachMessage.transition}
                          </p>
                          <p className="text-2xl sm:text-3xl lg:text-4xl font-heading font-black text-white">
                            <span className="text-emerald-400 font-mono">
                              {coachMessage.moveNumber}.{coachMessage.isWhite ? "" : ".."}
                            </span>
                            <span className="ml-1.5 font-mono font-black text-white">{coachMessage.move}</span>
                          </p>
                          <p className="mt-3 text-base sm:text-lg lg:text-xl font-medium leading-relaxed text-slate-200">
                            {coachMessage.explanation}
                          </p>
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
                              <div className="flex items-center gap-2.5 rounded-2xl border border-indigo-500/20 bg-indigo-950/30 p-5 text-indigo-300">
                                <Loader2 className="w-5 h-5 animate-spin text-indigo-400" />
                                <span className="text-sm font-semibold">Thinking deeper...</span>
                              </div>
                            ) : deeperExplanation && (
                              <div className="mt-3 rounded-2xl border border-indigo-500/30 bg-indigo-950/40 p-5 sm:p-6 shadow-xl">
                                <div className="flex items-start gap-3.5">
                                  <Brain className="mt-0.5 h-6 w-6 flex-shrink-0 text-indigo-400" />
                                  <div>
                                    <p className="mb-2 text-sm sm:text-base font-heading font-bold text-indigo-300">
                                      {deeperExplanation.question}
                                    </p>
                                    <p className="text-sm sm:text-base lg:text-lg font-medium leading-relaxed text-slate-200">
                                      {deeperExplanation.insight}
                                    </p>
                                    {deeperExplanation.keyPoint && (
                                      <p className="mt-3 text-xs sm:text-sm font-semibold text-emerald-300/90 flex items-center gap-2">
                                        <Lightbulb className="h-4 w-4 text-emerald-400 flex-shrink-0" />
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
                    </div>
                    
                    {/* Action buttons */}
                    <div className="flex flex-wrap items-center gap-3 pt-2">
                      {!showingWhy && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={getWhyExplanation}
                          className="h-11 px-4 border-indigo-500/30 bg-indigo-950/30 text-indigo-300 hover:bg-indigo-900/50 hover:text-white font-heading font-black text-xs sm:text-sm rounded-xl"
                        >
                          <HelpCircle className="w-4 h-4 mr-2 text-indigo-400" />
                          Why this move?
                        </Button>
                      )}

                      {isComplete && !isLastChapter && (
                        <Button
                          size="sm"
                          onClick={goToNextChapter}
                          className="h-11 px-5 font-heading font-black text-sm bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 shadow-[0_0_24px_rgba(16,185,129,0.35)] rounded-xl"
                          data-testid="lesson-next-chapter"
                        >
                          <Play className="mr-2 h-4 w-4 fill-current" />
                          Next: {nextChapterTitle || "keep going"}
                        </Button>
                      )}

                      {isComplete && isLastChapter && onStartPractice && (
                        <Button
                          size="sm"
                          onClick={onStartPractice}
                          className="h-11 px-5 font-heading font-black text-sm bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 shadow-[0_0_24px_rgba(16,185,129,0.35)] rounded-xl"
                          data-testid="lesson-start-practice"
                        >
                          <Play className="mr-2 h-4 w-4 fill-current" />
                          Practice Now
                        </Button>
                      )}

                      {isComplete && isLastChapter && onNextLesson && (
                        <Button
                          size="sm"
                          onClick={onNextLesson}
                          className="h-11 px-5 font-heading font-black text-sm bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white shadow-[0_0_24px_rgba(6,182,212,0.35)] rounded-xl"
                          data-testid="lesson-next-opening"
                        >
                          <ChevronRight className="mr-1.5 h-4 w-4" />
                          Next Lesson {nextOpening?.name ? `: ${nextOpening.name}` : ""} →
                        </Button>
                      )}
                    </div>
                  </motion.div>
                ) : isComplete ? (
                  <motion.div
                    key="complete"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex-1 flex flex-col justify-between space-y-6"
                  >
                    <div className="flex items-start gap-4">
                      <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-2xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
                        <Target className="h-6 w-6" />
                      </div>
                      <div>
                        <p className="text-xl sm:text-2xl font-heading font-black text-emerald-400">
                          {isLastChapter ? "Lesson complete" : "Section complete"}
                        </p>
                        <p className="mt-2 text-base sm:text-lg font-medium text-slate-300">
                          {isLastChapter
                            ? (nextOpening?.name 
                                ? `That's the whole lesson. Ready for the next opening: ${nextOpening.name}?` 
                                : "That's the whole lesson. Ready to test yourself?")
                            : `Next: ${nextChapterTitle}.`}
                        </p>
                      </div>
                    </div>

                    <div className="space-y-2.5 pt-4">
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                        <Button
                          onClick={reset}
                          variant="outline"
                          className="h-12 border-slate-700 bg-slate-800/60 font-heading font-black text-slate-200 hover:bg-slate-700/80 rounded-xl text-base"
                        >
                          <RotateCcw className="w-4 h-4 mr-2" />
                          Watch Again
                        </Button>
                        {onStartPractice && (
                          <Button
                            onClick={onStartPractice}
                            className="h-12 font-heading font-black bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 shadow-[0_0_24px_rgba(16,185,129,0.35)] rounded-xl text-base"
                          >
                            <Play className="w-4 h-4 mr-2 fill-current" />
                            Practice Now
                          </Button>
                        )}
                      </div>
                      {onNextLesson && (
                        <Button
                          onClick={onNextLesson}
                          className="w-full h-12 font-heading font-black bg-gradient-to-r from-cyan-500 via-teal-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white shadow-[0_0_24px_rgba(6,182,212,0.35)] rounded-xl text-base"
                        >
                          <ChevronRight className="w-5 h-5 mr-1" />
                          Next Lesson: {nextOpening?.name || "Continue Learning"} →
                        </Button>
                      )}
                    </div>
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </CardContent>
          </Card>
          
          {/* Controls Bar */}
          {!showIntro && (
            <div className="space-y-3 pt-1">
              <div className="grid grid-cols-[auto_auto_minmax(0,1fr)_auto] items-center gap-2.5">
                <Button
                  variant="outline"
                  size="icon"
                  onClick={reset}
                  className="h-12 w-12 border-slate-700/80 bg-slate-900/80 text-slate-300 hover:bg-slate-800 hover:text-white rounded-2xl shadow-md"
                  title="Reset to start"
                >
                  <RotateCcw className="h-5 w-5" />
                </Button>

                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => goToMove(currentMoveIndex - 1)}
                  disabled={currentMoveIndex <= 0}
                  className="h-12 w-12 border-slate-700/80 bg-slate-900/80 text-slate-300 hover:bg-slate-800 hover:text-white disabled:opacity-40 rounded-2xl shadow-md"
                  title="Previous move"
                >
                  <SkipBack className="h-5 w-5" />
                </Button>

                <Button
                  onClick={togglePlay}
                  className={`h-12 min-w-0 px-5 font-heading font-black text-base rounded-2xl transition-all duration-200 ${
                    isPlaying 
                      ? "bg-amber-500/20 border border-amber-500/40 text-amber-300 hover:bg-amber-500/30" 
                      : "bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 shadow-[0_0_24px_rgba(16,185,129,0.35)]"
                  }`}
                >
                  {isPlaying ? (
                    <>
                      <Pause className="mr-2 h-5 w-5 fill-current" />
                      Pause
                    </>
                  ) : (
                    <>
                      <Play className="mr-2 h-5 w-5 fill-current" />
                      {isComplete ? "Replay" : "Continue"}
                    </>
                  )}
                </Button>

                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => goToMove(currentMoveIndex + 1)}
                  disabled={currentMoveIndex >= mainLine.length - 1}
                  className="h-12 w-12 border-slate-700/80 bg-slate-900/80 text-slate-300 hover:bg-slate-800 hover:text-white disabled:opacity-40 rounded-2xl shadow-md"
                  title="Next move"
                >
                  <SkipForward className="h-5 w-5" />
                </Button>
              </div>

              {/* Speed control */}
              <div className="flex items-center justify-between gap-3 rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-3">
                <span className="text-xs font-heading font-black text-slate-400">Auto-play speed</span>
                <div className="flex items-center gap-2.5">
                  <Volume2 className="h-4 w-4 text-slate-400" />
                  <Slider
                    value={[playSpeed]}
                    onValueChange={([val]) => setPlaySpeed(val)}
                    min={1000}
                    max={5000}
                    step={500}
                    className="w-24 sm:w-32"
                  />
                  <span className="text-xs font-mono font-bold text-slate-300 w-10 text-right">
                    {(playSpeed / 1000).toFixed(1)}s
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default GuidedOpeningLesson;


