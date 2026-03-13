/**
 * InteractivePractice - Practice Opening with AI Coach
 * 
 * The coach plays the opponent's moves and provides Socratic
 * feedback when the user makes mistakes.
 * 
 * Features visual move indicators like chess.com:
 * - Green checkmark for correct/book moves
 * - Red X for wrong moves
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
  Trophy,
  MessageCircle,
  Loader2,
  X,
  XCircle
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
const MoveIndicator = ({ type, square, orientation, boardSize }) => {
  if (!type || !square || !boardSize) return null;
  
  // Calculate position based on square and board orientation
  const file = square.charCodeAt(0) - 97; // a=0, b=1, etc.
  const rank = parseInt(square[1]) - 1; // 1=0, 2=1, etc.
  
  // Adjust for board orientation
  const x = orientation === "white" ? file : 7 - file;
  const y = orientation === "white" ? 7 - rank : rank;
  
  // Position in pixels
  const squareSize = boardSize / 8;
  const left = x * squareSize + squareSize / 2;
  const top = y * squareSize + 4;
  
  const isCorrect = type === "book" || type === "correct" || type === "good";
  
  return (
    <motion.div
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      exit={{ scale: 0, opacity: 0 }}
      transition={{ type: "spring", stiffness: 500, damping: 25 }}
      className="absolute z-50 pointer-events-none"
      style={{ 
        left: `${left}px`, 
        top: `${top}px`,
        transform: "translate(-50%, 0)"
      }}
    >
      <div className={`rounded-full p-1.5 shadow-lg ${isCorrect ? 'bg-green-500' : 'bg-red-500'}`}>
        {isCorrect ? (
          <CheckCircle2 className="w-5 h-5 text-white" />
        ) : (
          <XCircle className="w-5 h-5 text-white" />
        )}
      </div>
    </motion.div>
  );
};

const InteractivePractice = ({ openingKey, openingName, userColor, onClose }) => {
  const boardRef = useRef(null);
  const boardContainerRef = useRef(null);
  const groundRef = useRef(null);
  const chessRef = useRef(new Chess());
  
  // Use refs for values needed in callbacks to avoid stale closures
  const sessionIdRef = useRef(null);
  const fenRef = useRef("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  
  const [sessionId, setSessionId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [fen, setFen] = useState("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  const [moveNumber, setMoveNumber] = useState(1);
  const [feedback, setFeedback] = useState(null);
  const [coachMessage, setCoachMessage] = useState(null);
  const [completed, setCompleted] = useState(false);
  const [hintCount, setHintCount] = useState(0);
  const [hint, setHint] = useState(null);
  const [lastMove, setLastMove] = useState(null);
  const [moveIndicator, setMoveIndicator] = useState(null);
  const [boardSize, setBoardSize] = useState(400);
  
  // Keep refs in sync with state
  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);
  
  useEffect(() => {
    fenRef.current = fen;
  }, [fen]);
  
  // Measure board size
  useEffect(() => {
    if (boardContainerRef.current) {
      const resizeObserver = new ResizeObserver((entries) => {
        for (const entry of entries) {
          setBoardSize(entry.contentRect.width);
        }
      });
      resizeObserver.observe(boardContainerRef.current);
      return () => resizeObserver.disconnect();
    }
  }, []);
  
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
        move: (orig, dest) => handleUserMove(orig, dest)
      }
    });
  }, []);
  
  // Handle user's move - uses refs to avoid stale closures
  const handleUserMove = async (orig, dest) => {
    const currentSessionId = sessionIdRef.current;
    if (!currentSessionId) {
      console.error("No session ID available");
      return;
    }
    
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
          session_id: currentSessionId,
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
          groundRef.current?.set({
            fen: data.fen,
            movable: { free: false, color: undefined }
          });
          setFeedback({
            type: "success",
            message: data.message || "Congratulations! You've mastered this opening line!"
          });
        } else if (data.correct) {
          // Correct move - show green checkmark
          console.log("Setting move indicator for square:", dest);
          setMoveIndicator({ type: "book", square: dest });
          setMoveNumber(data.move_number);
          setHintCount(0);
          
          setFeedback({
            type: "correct",
            message: data.your_move_explanation || "Correct! That's the book move."
          });
          
          // Show coach's response after a delay (keep indicator visible for 1.5s)
          if (data.coach_move) {
            setTimeout(() => {
              // Update FEN with coach's move included
              setFen(data.fen);
              
              // Parse coach move to get squares for highlight
              const tempChess = new Chess(fenRef.current);
              tempChess.move({ from: orig, to: dest, promotion: 'q' });
              const coachMoveResult = tempChess.move(data.coach_move);
              
              if (coachMoveResult) {
                setLastMove({ from: coachMoveResult.from, to: coachMoveResult.to });
              }
              
              setCoachMessage({
                move: data.coach_move,
                explanation: data.coach_explanation
              });
              
              // Hide indicator after showing coach message
              setTimeout(() => {
                setMoveIndicator(null);
              }, 500);
              
              // Set up for user's next move
              setTimeout(() => {
                setupUserMove(data.fen);
              }, 800);
            }, 1500);
          } else {
            // No coach move - just set up next move
            setFen(data.fen);
            setTimeout(() => {
              setMoveIndicator(null);
              setupUserMove(data.fen);
            }, 1000);
          }
        } else if (data.try_again) {
          // Incorrect move - keep the move visible temporarily with X icon
          // First, apply the move locally to show it on the board
          const wrongFen = chessRef.current.fen();
          const tempChess = new Chess(wrongFen);
          
          try {
            // Make the move locally to show it
            const wrongMove = tempChess.move({ from: orig, to: dest, promotion: 'q' });
            if (wrongMove) {
              // Update board to show the wrong move
              setFen(tempChess.fen());
              setLastMove({ from: orig, to: dest });
            }
          } catch (e) {
            // Move might be illegal, just show indicator
            setLastMove({ from: orig, to: dest });
          }
          
          // Show red X on destination square
          setMoveIndicator({ type: "wrong", square: dest });
          
          setFeedback({
            type: "incorrect",
            message: data.feedback?.message || "Not quite. Try again!"
          });
          
          // Reset board to original position after showing error
          setTimeout(() => {
            setMoveIndicator(null);
            setLastMove(null);
            setFen(data.fen);  // Reset to correct position
            setupUserMove(data.fen);
          }, 2000);  // Show wrong move for 2 seconds
        }
      } else {
        console.error("Move API returned error:", res.status);
        toast.error("Failed to make move");
      }
    } catch (err) {
      console.error("Error making move:", err);
      toast.error("Failed to make move");
    }
  };
  
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
        
        // Set session ID first
        setSessionId(data.session_id);
        sessionIdRef.current = data.session_id;
        
        setFen(data.fen);
        fenRef.current = data.fen;
        setMoveNumber(data.move_number);
        
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
        
        // Set up board for user's move after a brief delay
        setTimeout(() => {
          setupUserMove(data.fen);
        }, 500);
      } else {
        toast.error("Failed to start practice session");
      }
    } catch (err) {
      console.error("Error starting practice:", err);
      toast.error("Failed to start practice session");
    } finally {
      setLoading(false);
    }
  }, [openingKey, setupUserMove]);
  
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
    sessionIdRef.current = null;
    setFen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
    fenRef.current = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
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
  }, []);
  
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
          <div 
            ref={boardContainerRef}
            className="relative" 
            style={{ maxWidth: "400px", margin: "0 auto" }}
          >
            <div 
              ref={boardRef} 
              className="w-full aspect-square rounded-lg"
              data-testid="practice-board"
            />
            
            {/* Move Quality Indicator - overlays on the board */}
            <AnimatePresence>
              {moveIndicator && (
                <MoveIndicator 
                  type={moveIndicator.type}
                  square={moveIndicator.square}
                  orientation={userColor || "white"}
                  boardSize={boardSize}
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
                    <CheckCircle2 className="w-5 h-5 text-green-400 flex-shrink-0" />
                  )}
                  {feedback.type === "success" && (
                    <Trophy className="w-5 h-5 text-primary flex-shrink-0" />
                  )}
                  {feedback.type === "incorrect" && (
                    <XCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
                  )}
                  <div>
                    <p className="text-sm font-medium">
                      {feedback.type === "correct" && "✓ Book Move"}
                      {feedback.type === "incorrect" && "✗ Wrong Move"}
                      {feedback.type === "success" && "🎉 Complete!"}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">{feedback.message}</p>
                  </div>
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
            data-testid="start-practice-btn"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Play className="w-4 h-4 mr-2" />
            )}
            Start Practice
          </Button>
        ) : completed ? (
          <Button 
            onClick={startSession} 
            className="flex-1"
          >
            <RotateCcw className="w-4 h-4 mr-2" />
            Practice Again
          </Button>
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
