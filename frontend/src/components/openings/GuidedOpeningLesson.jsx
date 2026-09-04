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

import { useState, useEffect, useRef, useCallback } from "react";
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
  onComplete,
  onStartPractice 
}) => {
  const boardRef = useRef(null);
  const chessRef = useRef(new Chess());
  const autoPlayRef = useRef(null);
  
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
  
  const mainLine = opening?.main_line || [];
  const keyIdeas = opening?.key_ideas || [];
  const userColor = opening?.color || "white";
  
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
    
    // Check if completed
    if (newIndex === mainLine.length - 1 && onComplete) {
      setTimeout(() => {
        setIsPlaying(false);
      }, 1000);
    }
  }, [mainLine.length, updateBoard, onComplete]);
  
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
  const introMessage = COACH_INTROS[userColor][Math.floor(Math.random() * 3)];
  
  return (
    <div className="guided-opening-lesson grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(340px,0.72fr)] lg:gap-7">
      <div className="min-w-0 space-y-3">
        {/* Board */}
        <Card className="experience-board-stage overflow-hidden border-border/70 bg-card p-2 shadow-[0_24px_64px_hsl(var(--experience-shadow)/0.18)] sm:p-3">
          <CardContent className="p-0">
            <div className="relative overflow-hidden rounded-lg">
              <div className="aspect-square w-full">
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
                  <Badge className="bg-black/70 px-3 py-1 text-white backdrop-blur">
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
        <div className="border-b border-border/60 bg-muted/40 px-5 py-3">
          <p className="experience-eyebrow text-[10px] font-bold uppercase">Your coach</p>
        </div>
        <CardContent className="p-5 sm:p-6">
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
                  <div>
                    <p className="mb-1 text-sm font-semibold text-foreground">Ready when you are</p>
                    <p className="experience-coach-copy text-lg leading-relaxed text-foreground">{introMessage}</p>
                  </div>
                </div>
                
                {keyIdeas.length > 0 && (
                  <div className="mt-4 pl-13">
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
                  className="experience-primary mt-4 w-full"
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
                        <div className="mt-2 rounded-xl border border-accent/20 bg-accent/10 p-4">
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
                
                <div className="flex gap-2">
                  <Button 
                    onClick={reset}
                    variant="outline"
                    className="flex-1 border-border"
                  >
                    <RotateCcw className="w-4 h-4 mr-2" />
                    Watch Again
                  </Button>
                  {onStartPractice && (
                    <Button 
                      onClick={onStartPractice}
                      className="experience-primary flex-1"
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
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="icon"
            onClick={reset}
            className="border-border"
          >
            <RotateCcw className="w-4 h-4" />
          </Button>
          
          <Button
            variant="outline"
            size="icon"
            onClick={() => goToMove(currentMoveIndex - 1)}
            disabled={currentMoveIndex <= 0}
            className="border-border"
          >
            <SkipBack className="w-4 h-4" />
          </Button>
          
          <Button
            onClick={togglePlay}
            className={`flex-1 ${isPlaying ? "bg-secondary text-secondary-foreground hover:bg-secondary/90" : "experience-primary"}`}
          >
            {isPlaying ? (
              <>
                <Pause className="w-4 h-4 mr-2" />
                Pause
              </>
            ) : (
              <>
                <Play className="w-4 h-4 mr-2" />
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
            <SkipForward className="w-4 h-4" />
          </Button>
          
          {/* Speed control */}
          <div className="flex items-center gap-2 ml-2">
            <Volume2 className="h-4 w-4 text-muted-foreground" />
            <Slider
              value={[playSpeed]}
              onValueChange={([val]) => setPlaySpeed(val)}
              min={1000}
              max={5000}
              step={500}
              className="w-20"
            />
          </div>
        </div>
      )}
      </div>
    </div>
  );
};

export default GuidedOpeningLesson;
