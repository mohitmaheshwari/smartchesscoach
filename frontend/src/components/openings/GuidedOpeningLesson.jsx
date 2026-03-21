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

const API = process.env.REACT_APP_BACKEND_URL + "/api";

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
    <div className="space-y-4">
      {/* Board */}
      <Card className="overflow-hidden">
        <CardContent className="p-0">
          <div className="relative">
            <div className="w-full aspect-square">
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
                className="absolute top-2 left-2"
              >
                <Badge className="bg-black/70 backdrop-blur text-white px-3 py-1">
                  {coachMessage.moveNumber}. 
                  {coachMessage.isWhite ? "" : "..."} 
                  <span className="font-mono font-bold ml-1">{coachMessage.move}</span>
                </Badge>
              </motion.div>
            )}
          </div>
        </CardContent>
      </Card>
      
      {/* Progress bar */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-zinc-500">
          {currentMoveIndex + 1} / {mainLine.length}
        </span>
        <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-amber-500"
            initial={{ width: 0 }}
            animate={{ 
              width: `${((currentMoveIndex + 1) / mainLine.length) * 100}%` 
            }}
            transition={{ duration: 0.3 }}
          />
        </div>
      </div>
      
      {/* Coach Message Panel */}
      <Card className="bg-zinc-900/50 border-zinc-800">
        <CardContent className="p-4">
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
                  <div className="w-10 h-10 rounded-full bg-amber-500/20 flex items-center justify-center flex-shrink-0">
                    <MessageCircle className="w-5 h-5 text-amber-500" />
                  </div>
                  <div>
                    <p className="text-sm text-zinc-300 font-medium mb-1">Your Coach</p>
                    <p className="text-white">{introMessage}</p>
                  </div>
                </div>
                
                {keyIdeas.length > 0 && (
                  <div className="mt-4 pl-13">
                    <p className="text-xs text-zinc-500 mb-2">Key ideas to watch for:</p>
                    <div className="flex flex-wrap gap-2">
                      {keyIdeas.slice(0, 3).map((idea, i) => (
                        <Badge 
                          key={i} 
                          variant="outline" 
                          className="text-xs bg-zinc-800/50 border-zinc-700"
                        >
                          <Target className="w-3 h-3 mr-1 text-amber-500" />
                          {idea.length > 40 ? idea.substring(0, 40) + "..." : idea}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
                
                <Button 
                  onClick={startLesson} 
                  className="w-full mt-4 bg-amber-600 hover:bg-amber-700"
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
                  <div className="w-10 h-10 rounded-full bg-amber-500/20 flex items-center justify-center flex-shrink-0">
                    <MessageCircle className="w-5 h-5 text-amber-500" />
                  </div>
                  <div className="flex-1">
                    <p className="text-xs text-amber-500/80 mb-1">{coachMessage.transition}</p>
                    <p className="text-white text-lg">
                      <span className="font-mono font-bold text-amber-400">
                        {coachMessage.moveNumber}.{coachMessage.isWhite ? "" : ".."}{coachMessage.move}
                      </span>
                    </p>
                    <p className="text-zinc-300 mt-2">{coachMessage.explanation}</p>
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
                        <div className="flex items-center gap-2 text-zinc-500 p-3">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          <span className="text-sm">Thinking deeper...</span>
                        </div>
                      ) : deeperExplanation && (
                        <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3 mt-2">
                          <div className="flex items-start gap-2">
                            <Brain className="w-4 h-4 text-blue-400 mt-0.5" />
                            <div>
                              <p className="text-xs text-blue-400 font-medium mb-1">
                                {deeperExplanation.question}
                              </p>
                              <p className="text-sm text-zinc-300">
                                {deeperExplanation.insight}
                              </p>
                              {deeperExplanation.keyPoint && (
                                <p className="text-xs text-zinc-500 mt-2">
                                  <Lightbulb className="w-3 h-3 inline mr-1 text-amber-400" />
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
                    className="text-zinc-500 hover:text-white"
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
                  <div className="w-10 h-10 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
                    <Target className="w-5 h-5 text-green-500" />
                  </div>
                  <div>
                    <p className="text-green-400 font-medium">Lesson Complete!</p>
                    <p className="text-zinc-300 mt-1">
                      Now you know the main line. Ready to test yourself?
                    </p>
                  </div>
                </div>
                
                <div className="flex gap-2">
                  <Button 
                    onClick={reset}
                    variant="outline"
                    className="flex-1 border-zinc-700"
                  >
                    <RotateCcw className="w-4 h-4 mr-2" />
                    Watch Again
                  </Button>
                  {onStartPractice && (
                    <Button 
                      onClick={onStartPractice}
                      className="flex-1 bg-amber-600 hover:bg-amber-700"
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
            className="border-zinc-700"
          >
            <RotateCcw className="w-4 h-4" />
          </Button>
          
          <Button
            variant="outline"
            size="icon"
            onClick={() => goToMove(currentMoveIndex - 1)}
            disabled={currentMoveIndex <= 0}
            className="border-zinc-700"
          >
            <SkipBack className="w-4 h-4" />
          </Button>
          
          <Button
            onClick={togglePlay}
            className={`flex-1 ${isPlaying ? 'bg-zinc-700' : 'bg-amber-600 hover:bg-amber-700'}`}
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
            className="border-zinc-700"
          >
            <SkipForward className="w-4 h-4" />
          </Button>
          
          {/* Speed control */}
          <div className="flex items-center gap-2 ml-2">
            <Volume2 className="w-4 h-4 text-zinc-500" />
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
  );
};

export default GuidedOpeningLesson;
