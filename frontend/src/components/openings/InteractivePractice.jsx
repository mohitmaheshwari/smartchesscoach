/**
 * InteractivePractice - Practice Opening with AI Coach
 * 
 * The coach plays the opponent's moves and provides Socratic
 * feedback when the user makes mistakes.
 * 
 * Features visual move indicators like chess.com:
 * - Green checkmark for correct/book moves
 * - Red X for wrong moves
 * - Question mark for inaccuracies
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { Chess } from "chess.js";
import { Chessground } from "chessground";
import { motion, AnimatePresence } from "framer-motion";
import {
  Play,
  RotateCcw,
  Lightbulb,
  CheckCircle2,
  AlertTriangle,
  Trophy,
  MessageCircle,
  Loader2,
  X,
  BookOpen,
  XCircle,
  HelpCircle
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

import "chessground/assets/chessground.base.css";
import "chessground/assets/chessground.brown.css";
import "chessground/assets/chessground.cburnett.css";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

// Move quality indicator component - shows on the board
const MoveIndicator = ({ type, square, orientation }) => {
  if (!type || !square) return null;
  
  // Calculate position based on square and board orientation
  const file = square.charCodeAt(0) - 97; // a=0, b=1, etc.
  const rank = parseInt(square[1]) - 1; // 1=0, 2=1, etc.
  
  // Adjust for board orientation
  const x = orientation === "white" ? file : 7 - file;
  const y = orientation === "white" ? 7 - rank : rank;
  
  // Position as percentage (each square is 12.5%)
  const left = `${x * 12.5 + 6.25}%`;
  const top = `${y * 12.5 + 1}%`;
  
  const indicatorConfig = {
    book: {
      icon: BookOpen,
      color: "text-green-400",
      bg: "bg-green-500/90",
      label: "Book Move"
    },
    correct: {
      icon: CheckCircle2,
      color: "text-green-400",
      bg: "bg-green-500/90",
      label: "Correct!"
    },
    good: {
      icon: CheckCircle2,
      color: "text-green-400",
      bg: "bg-green-500/90",
      label: "Good"
    },
    inaccuracy: {
      icon: HelpCircle,
      color: "text-yellow-400",
      bg: "bg-yellow-500/90",
      label: "Inaccuracy"
    },
    mistake: {
      icon: AlertTriangle,
      color: "text-orange-400",
      bg: "bg-orange-500/90",
      label: "Mistake"
    },
    wrong: {
      icon: XCircle,
      color: "text-red-400",
      bg: "bg-red-500/90",
      label: "Wrong"
    }
  };
  
  const config = indicatorConfig[type] || indicatorConfig.wrong;
  const Icon = config.icon;
  
  return (
    <motion.div
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      exit={{ scale: 0, opacity: 0 }}
      transition={{ type: "spring", stiffness: 500, damping: 25 }}
      className="absolute z-20 pointer-events-none"
      style={{ 
        left, 
        top,
        transform: "translate(-50%, 0)"
      }}
    >
      <div className={`${config.bg} rounded-full p-1 shadow-lg`}>
        <Icon className={`w-5 h-5 text-white`} />
      </div>
    </motion.div>
  );
};

const InteractivePractice = ({ openingKey, openingName, userColor, onClose }) => {
  const boardRef = useRef(null);
  const groundRef = useRef(null);
  const chessRef = useRef(new Chess());
  
  const [sessionId, setSessionId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [fen, setFen] = useState("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  const [isUserTurn, setIsUserTurn] = useState(true);
  const [moveNumber, setMoveNumber] = useState(1);
  const [feedback, setFeedback] = useState(null);
  const [coachMessage, setCoachMessage] = useState(null);
  const [completed, setCompleted] = useState(false);
  const [hintCount, setHintCount] = useState(0);
  const [hint, setHint] = useState(null);
  const [lastMove, setLastMove] = useState(null);
  
  // Move indicator state - shows visual feedback on board
  const [moveIndicator, setMoveIndicator] = useState(null); // { type: 'correct'|'wrong'|'book', square: 'e4' }
  
  // Initialize board
  useEffect(() => {
    if (boardRef.current && !groundRef.current) {
      groundRef.current = Chessground(boardRef.current, {
        fen: fen,
        orientation: userColor || "white",
        movable: {
          free: false,
          color: undefined
        },
        animation: { duration: 300 }
      });
    }
    
    return () => {
      if (groundRef.current) {
        groundRef.current.destroy();
        groundRef.current = null;
      }
    };
  }, []);
  
  // Update board when FEN changes
  useEffect(() => {
    if (groundRef.current) {
      chessRef.current.load(fen);
      groundRef.current.set({ 
        fen,
        lastMove: lastMove ? [lastMove.from, lastMove.to] : undefined
      });
    }
  }, [fen, lastMove]);
  
  // Start practice session
  const startSession = useCallback(async () => {
    setLoading(true);
    setFeedback(null);
    setCoachMessage(null);
    setCompleted(false);
    setHint(null);
    setHintCount(0);
    setMoveIndicator(null);
    setLastMove(null);
    
    try {
      const res = await fetch(`${API}/openings/${openingKey}/practice/start`, {
        method: "POST",
        credentials: "include"
      });
      
      if (res.ok) {
        const data = await res.json();
        setSessionId(data.session_id);
        setFen(data.fen);
        setMoveNumber(data.move_number);
        setIsUserTurn(data.is_user_turn);
        
        if (data.coach_move) {
          setCoachMessage({
            move: data.coach_move,
            explanation: data.coach_explanation
          });
          
          // Show the coach's move with a highlight
          const chess = new Chess();
          const move = chess.move(data.coach_move);
          if (move) {
            setLastMove({ from: move.from, to: move.to });
          }
        }
        
        if (data.hint) {
          setHint(data.hint);
        }
        
        // Set up board for user's move
        if (data.is_user_turn) {
          setupUserMove(data.fen);
        }
      } else {
        toast.error("Failed to start practice session");
      }
    } catch (err) {
      console.error("Error starting practice:", err);
      toast.error("Failed to start practice session");
    } finally {
      setLoading(false);
    }
  }, [openingKey]);
  
  // Set up board for user to make a move
  const setupUserMove = useCallback((currentFen) => {
    if (!groundRef.current) return;
    
    const chess = new Chess(currentFen);
    const dests = new Map();
    
    for (const move of chess.moves({ verbose: true })) {
      if (!dests.has(move.from)) {
        dests.set(move.from, []);
      }
      dests.get(move.from).push(move.to);
    }
    
    const turnColor = chess.turn() === 'w' ? 'white' : 'black';
    
    groundRef.current.set({
      fen: currentFen,
      turnColor,
      movable: {
        free: false,
        color: turnColor,
        dests
      },
      events: {
        move: handleUserMove
      }
    });
  }, []);
  
  // Handle user's move
  const handleUserMove = useCallback(async (orig, dest) => {
    if (!sessionId) return;
    
    setFeedback(null);
    setHint(null);
    setMoveIndicator(null);
    
    const moveUci = orig + dest;
    
    // Show the move on board immediately
    setLastMove({ from: orig, to: dest });
    
    try {
      const res = await fetch(`${API}/openings/practice/move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: sessionId,
          move: moveUci
        })
      });
      
      if (res.ok) {
        const data = await res.json();
        
        if (data.complete) {
          // Practice completed!
          setCompleted(true);
          setFen(data.fen);
          setMoveIndicator({ type: "book", square: dest });
          groundRef.current.set({
            fen: data.fen,
            movable: { free: false, color: undefined }
          });
          setFeedback({
            type: "success",
            message: data.message || "Congratulations! You've mastered this opening line!"
          });
        } else if (data.correct) {
          // Correct move - show green checkmark
          setFen(data.fen);
          setMoveNumber(data.move_number);
          setHintCount(0);
          setMoveIndicator({ type: "book", square: dest });
          
          // Show coach's response
          if (data.coach_move) {
            // After showing user's correct move, show coach's response
            setTimeout(() => {
              setMoveIndicator(null);
              setCoachMessage({
                move: data.coach_move,
                explanation: data.coach_explanation
              });
              
              // Parse coach move to get destination square for highlight
              const tempChess = new Chess(fen);
              tempChess.move({ from: orig, to: dest, promotion: 'q' });
              const coachMoveResult = tempChess.move(data.coach_move);
              if (coachMoveResult) {
                setLastMove({ from: coachMoveResult.from, to: coachMoveResult.to });
              }
            }, 800);
          }
          
          setFeedback({
            type: "correct",
            message: data.your_move_explanation || "Correct! That's the book move."
          });
          
          // Set up for next move after showing feedback
          setTimeout(() => {
            setupUserMove(data.fen);
          }, 1500);
        } else if (data.try_again) {
          // Incorrect move - show red X
          setMoveIndicator({ type: "wrong", square: dest });
          
          setFeedback({
            type: "incorrect",
            message: data.feedback?.message || "Not quite. Try again!",
            socratic: true
          });
          
          // Reset board to original position after showing error
          setTimeout(() => {
            setMoveIndicator(null);
            setLastMove(null);
            setupUserMove(data.fen);
          }, 1500);
        }
      }
    } catch (err) {
      console.error("Error making move:", err);
      toast.error("Failed to make move");
    }
  }, [sessionId, setupUserMove, fen]);
  
  // Get hint
  const getHint = useCallback(async () => {
    if (!sessionId) return;
    
    setHintCount(prev => prev + 1);
    
    try {
      const res = await fetch(`${API}/openings/practice/hint`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: sessionId,
          hint_level: hintCount + 1
        })
      });
      
      if (res.ok) {
        const data = await res.json();
        setHint(data.hint);
      }
    } catch (err) {
      console.error("Error getting hint:", err);
    }
  }, [sessionId, hintCount]);
  
  // Reset session
  const resetSession = useCallback(() => {
    setSessionId(null);
    setFen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
    setMoveNumber(1);
    setFeedback(null);
    setCoachMessage(null);
    setCompleted(false);
    setHint(null);
    setHintCount(0);
    setMoveIndicator(null);
    setLastMove(null);
    
    if (groundRef.current) {
      groundRef.current.set({
        fen: "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        movable: { free: false, color: undefined },
        lastMove: undefined
      });
    }
  }, [sessionId]);
  
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MessageCircle className="w-5 h-5 text-primary" />
          <h3 className="font-semibold">Practice with Coach</h3>
          {moveNumber > 0 && !completed && (
            <Badge variant="outline" className="ml-2">
              Move {moveNumber}
            </Badge>
          )}
        </div>
        {onClose && (
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        )}
      </div>
      
      {/* Board with Move Indicator Overlay */}
      <Card>
        <CardContent className="p-4">
          <div className="relative" style={{ maxWidth: "400px", margin: "0 auto" }}>
            <div 
              ref={boardRef} 
              className="w-full aspect-square rounded-lg overflow-hidden"
              data-testid="practice-board"
            />
            
            {/* Move Quality Indicator - overlays on the board */}
            <AnimatePresence>
              {moveIndicator && (
                <MoveIndicator 
                  type={moveIndicator.type}
                  square={moveIndicator.square}
                  orientation={userColor || "white"}
                />
              )}
            </AnimatePresence>
          </div>
          
          {/* Coach Message */}
          <AnimatePresence>
            {coachMessage && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="mt-4 p-3 rounded-lg bg-primary/10 border border-primary/30"
              >
                <div className="flex items-start gap-2">
                  <div className="p-1 rounded-full bg-primary/20">
                    <MessageCircle className="w-4 h-4 text-primary" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">
                      Coach played: <span className="font-mono">{coachMessage.move}</span>
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {coachMessage.explanation}
                    </p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          
          {/* Feedback with Icon */}
          <AnimatePresence>
            {feedback && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className={`mt-4 p-3 rounded-lg ${
                  feedback.type === "correct" ? "bg-green-500/10 border border-green-500/30" :
                  feedback.type === "success" ? "bg-primary/10 border border-primary/30" :
                  "bg-red-500/10 border border-red-500/30"
                }`}
              >
                <div className="flex items-start gap-2">
                  {feedback.type === "correct" && (
                    <div className="flex items-center gap-1">
                      <BookOpen className="w-5 h-5 text-green-400 flex-shrink-0" />
                      <span className="text-xs text-green-400 font-medium">Book Move</span>
                    </div>
                  )}
                  {feedback.type === "success" && <Trophy className="w-5 h-5 text-primary flex-shrink-0" />}
                  {feedback.type === "incorrect" && (
                    <div className="flex items-center gap-1">
                      <XCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
                      <span className="text-xs text-red-400 font-medium">Wrong Move</span>
                    </div>
                  )}
                </div>
                <div className="mt-2">
                  <p className="text-sm">{feedback.message}</p>
                  {feedback.socratic && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Think about it and try again!
                    </p>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          
          {/* Hint */}
          <AnimatePresence>
            {hint && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="mt-3 p-3 rounded-lg bg-blue-500/10 border border-blue-500/30"
              >
                <div className="flex items-start gap-2">
                  <Lightbulb className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-blue-200">{hint}</p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </CardContent>
      </Card>
      
      {/* Controls */}
      <div className="flex gap-2">
        {!sessionId ? (
          <Button 
            onClick={startSession} 
            className="flex-1"
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Play className="w-4 h-4 mr-2" />
            )}
            Start Practice
          </Button>
        ) : completed ? (
          <>
            <Button 
              onClick={startSession} 
              className="flex-1"
            >
              <RotateCcw className="w-4 h-4 mr-2" />
              Practice Again
            </Button>
          </>
        ) : (
          <>
            <Button 
              variant="outline"
              onClick={getHint}
              className="flex-1"
            >
              <Lightbulb className="w-4 h-4 mr-2" />
              Hint {hintCount > 0 ? `(${hintCount})` : ""}
            </Button>
            <Button 
              variant="outline"
              onClick={resetSession}
            >
              <RotateCcw className="w-4 h-4 mr-2" />
              Reset
            </Button>
          </>
        )}
      </div>
      
      {/* Instructions */}
      {!sessionId && (
        <p className="text-xs text-muted-foreground text-center">
          Practice the {openingName} with your AI coach. The coach will play the opponent's 
          moves and give you feedback when you make mistakes.
        </p>
      )}
    </div>
  );
};

export default InteractivePractice;
