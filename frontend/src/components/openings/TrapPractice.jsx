/**
 * TrapPractice - Practice executing chess traps
 * 
 * The user practices springing traps:
 * 1. Coach plays the victim's setup moves
 * 2. User plays the trap moves with guidance
 * 3. Celebrates when trap is completed
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
  Sparkles,
  Loader2,
  X,
  ChevronRight
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

import "chessground/assets/chessground.base.css";
import "chessground/assets/chessground.brown.css";
import "chessground/assets/chessground.cburnett.css";

const TrapPractice = ({ trap, onClose, onComplete }) => {
  const boardRef = useRef(null);
  const groundRef = useRef(null);
  const chessRef = useRef(new Chess());
  
  const [phase, setPhase] = useState("ready"); // ready, setup, trap, complete
  const [currentMoveIndex, setCurrentMoveIndex] = useState(0);
  const [fen, setFen] = useState("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  const [feedback, setFeedback] = useState(null);
  const [hintCount, setHintCount] = useState(0);
  const [showHint, setShowHint] = useState(false);
  const [lastMove, setLastMove] = useState(null);
  
  const setupMoves = trap?.setup_moves || [];
  const trapLine = trap?.trap_line || [];
  
  // Determine user's color based on trap (user is the one who benefits from the trap)
  // For traps in black openings, user plays black; for white openings, user plays white
  const isBlackOpening = ['sicilian-defense', 'french-defense', 'caro-kann', 'scandinavian-defense',
    'petrov-defense', 'philidor-defense', 'kings-indian-defense', 'nimzo-indian',
    'queens-indian', 'grunfeld-defense', 'benoni-defense', 'slav-defense',
    'dutch-defense', 'budapest-gambit'].includes(trap?.opening_key);
  const userColor = isBlackOpening ? "black" : "white";
  
  // Initialize board
  useEffect(() => {
    if (boardRef.current && !groundRef.current) {
      groundRef.current = Chessground(boardRef.current, {
        fen: fen,
        orientation: userColor,
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
  }, [userColor]);
  
  // Update board when FEN changes
  useEffect(() => {
    if (groundRef.current) {
      groundRef.current.set({ 
        fen,
        lastMove: lastMove ? [lastMove.from, lastMove.to] : undefined
      });
    }
  }, [fen, lastMove]);
  
  // Start the practice
  const startPractice = useCallback(() => {
    chessRef.current.reset();
    setFen(chessRef.current.fen());
    setPhase("setup");
    setCurrentMoveIndex(0);
    setFeedback(null);
    setHintCount(0);
    setShowHint(false);
    
    // Play setup moves with animation
    playSetupMoves(0);
  }, []);
  
  // Play setup moves one by one
  const playSetupMoves = useCallback((index) => {
    if (index >= setupMoves.length) {
      // Setup complete, start trap phase
      setPhase("trap");
      setCurrentMoveIndex(0);
      setupUserMove();
      return;
    }
    
    const move = setupMoves[index];
    
    setTimeout(() => {
      try {
        const result = chessRef.current.move(move);
        if (result) {
          setFen(chessRef.current.fen());
          setLastMove({ from: result.from, to: result.to });
          setCurrentMoveIndex(index + 1);
          
          // Continue to next move
          playSetupMoves(index + 1);
        }
      } catch (e) {
        console.error("Invalid setup move:", move, e);
      }
    }, 600);
  }, [setupMoves]);
  
  // Set up the board for user to make a trap move
  const setupUserMove = useCallback(() => {
    if (!groundRef.current) return;
    
    const chess = chessRef.current;
    const dests = new Map();
    
    for (const move of chess.moves({ verbose: true })) {
      if (!dests.has(move.from)) {
        dests.set(move.from, []);
      }
      dests.get(move.from).push(move.to);
    }
    
    const turnColor = chess.turn() === 'w' ? 'white' : 'black';
    
    // Only allow moves if it's user's turn
    if (turnColor === userColor) {
      groundRef.current.set({
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
    }
  }, [userColor]);
  
  // Handle user's move
  const handleUserMove = useCallback((orig, dest) => {
    const moveUci = orig + dest;
    const expectedMove = trapLine[currentMoveIndex];
    
    if (!expectedMove) {
      setPhase("complete");
      return;
    }
    
    // Try to make the move
    try {
      const result = chessRef.current.move({ from: orig, to: dest, promotion: 'q' });
      
      if (!result) {
        setFeedback({ type: "error", message: "Invalid move" });
        setupUserMove();
        return;
      }
      
      // Check if this is the expected move
      const expectedSan = expectedMove.move.replace("+", "").replace("#", "").replace("!", "").replace("?", "");
      const playedSan = result.san.replace("+", "").replace("#", "").replace("!", "").replace("?", "");
      
      if (playedSan.toLowerCase() === expectedSan.toLowerCase()) {
        // Correct move!
        setFen(chessRef.current.fen());
        setLastMove({ from: result.from, to: result.to });
        setFeedback({ 
          type: "correct", 
          message: expectedMove.explanation 
        });
        setHintCount(0);
        setShowHint(false);
        
        const nextIndex = currentMoveIndex + 1;
        
        // Check if trap is complete
        if (nextIndex >= trapLine.length) {
          setTimeout(() => {
            setPhase("complete");
            setFeedback({
              type: "success",
              message: trap.success_message || "You executed the trap!"
            });
          }, 1000);
          return;
        }
        
        // Play opponent's response (next move in trap line)
        setTimeout(() => {
          playOpponentResponse(nextIndex);
        }, 1000);
        
      } else {
        // Wrong move - undo and try again
        chessRef.current.undo();
        setFeedback({
          type: "incorrect",
          message: "Not quite! Think about what the trap is trying to achieve."
        });
        setupUserMove();
      }
    } catch (e) {
      console.error("Move error:", e);
      setFeedback({ type: "error", message: "Invalid move" });
      setupUserMove();
    }
  }, [currentMoveIndex, trapLine, trap]);
  
  // Play opponent's response
  const playOpponentResponse = useCallback((index) => {
    if (index >= trapLine.length) {
      setPhase("complete");
      return;
    }
    
    const move = trapLine[index];
    
    try {
      const result = chessRef.current.move(move.move);
      if (result) {
        setFen(chessRef.current.fen());
        setLastMove({ from: result.from, to: result.to });
        setCurrentMoveIndex(index + 1);
        
        // Check if trap is complete
        if (index + 1 >= trapLine.length) {
          setTimeout(() => {
            setPhase("complete");
            setFeedback({
              type: "success",
              message: trap.success_message || "You executed the trap!"
            });
          }, 500);
          return;
        }
        
        // Set up for user's next move
        setTimeout(() => {
          setFeedback(null);
          setupUserMove();
        }, 800);
      }
    } catch (e) {
      console.error("Opponent move error:", move.move, e);
    }
  }, [trapLine, trap, setupUserMove]);
  
  // Get a hint
  const getHint = useCallback(() => {
    const currentMove = trapLine[currentMoveIndex];
    if (!currentMove) return;
    
    setHintCount(prev => prev + 1);
    
    if (hintCount === 0) {
      setShowHint(true);
      setFeedback({
        type: "hint",
        message: currentMove.explanation
      });
    } else if (hintCount === 1) {
      // More specific hint
      const move = currentMove.move;
      const piece = move[0].toUpperCase() === move[0] ? move[0] : "Pawn";
      setFeedback({
        type: "hint",
        message: `Move your ${piece === 'N' ? 'Knight' : piece === 'B' ? 'Bishop' : piece === 'R' ? 'Rook' : piece === 'Q' ? 'Queen' : piece === 'K' ? 'King' : 'Pawn'}. ${currentMove.explanation}`
      });
    } else {
      // Give the answer
      setFeedback({
        type: "hint",
        message: `The correct move is ${currentMove.move}. ${currentMove.explanation}`
      });
    }
  }, [currentMoveIndex, trapLine, hintCount]);
  
  // Reset
  const resetPractice = useCallback(() => {
    chessRef.current.reset();
    setFen(chessRef.current.fen());
    setPhase("ready");
    setCurrentMoveIndex(0);
    setFeedback(null);
    setHintCount(0);
    setShowHint(false);
    setLastMove(null);
    
    if (groundRef.current) {
      groundRef.current.set({
        fen: "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        movable: { free: false, color: undefined },
        lastMove: undefined
      });
    }
  }, []);
  
  if (!trap) return null;
  
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-purple-400" />
          <h3 className="font-semibold">Practice: {trap.name}</h3>
        </div>
        {onClose && (
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        )}
      </div>
      
      {/* Phase indicator */}
      <div className="flex items-center gap-2 text-sm">
        <Badge variant={phase === "setup" ? "default" : "outline"}>
          1. Setup
        </Badge>
        <ChevronRight className="w-4 h-4 text-muted-foreground" />
        <Badge variant={phase === "trap" ? "default" : "outline"}>
          2. Execute Trap
        </Badge>
        <ChevronRight className="w-4 h-4 text-muted-foreground" />
        <Badge variant={phase === "complete" ? "default" : "outline"}>
          3. Victory!
        </Badge>
      </div>
      
      {/* Board */}
      <Card>
        <CardContent className="p-4">
          <div 
            ref={boardRef} 
            className="w-full aspect-square rounded-lg overflow-hidden"
            style={{ maxWidth: "400px", margin: "0 auto" }}
          />
          
          {/* Feedback */}
          <AnimatePresence>
            {feedback && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className={`mt-4 p-3 rounded-lg ${
                  feedback.type === "correct" ? "bg-green-500/10 border border-green-500/30" :
                  feedback.type === "success" ? "bg-purple-500/10 border border-purple-500/30" :
                  feedback.type === "hint" ? "bg-blue-500/10 border border-blue-500/30" :
                  feedback.type === "incorrect" ? "bg-amber-500/10 border border-amber-500/30" :
                  "bg-red-500/10 border border-red-500/30"
                }`}
              >
                <div className="flex items-start gap-2">
                  {feedback.type === "correct" && <CheckCircle2 className="w-5 h-5 text-green-400 flex-shrink-0" />}
                  {feedback.type === "success" && <Trophy className="w-5 h-5 text-purple-400 flex-shrink-0" />}
                  {feedback.type === "hint" && <Lightbulb className="w-5 h-5 text-blue-400 flex-shrink-0" />}
                  {feedback.type === "incorrect" && <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0" />}
                  <p className="text-sm">{feedback.message}</p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          
          {/* Current move indicator */}
          {phase === "trap" && currentMoveIndex < trapLine.length && (
            <div className="mt-3 text-xs text-muted-foreground text-center">
              Move {currentMoveIndex + 1} of {trapLine.length} in trap sequence
            </div>
          )}
        </CardContent>
      </Card>
      
      {/* Controls */}
      <div className="flex gap-2">
        {phase === "ready" && (
          <Button onClick={startPractice} className="flex-1">
            <Play className="w-4 h-4 mr-2" />
            Start Practice
          </Button>
        )}
        
        {phase === "setup" && (
          <Button disabled className="flex-1">
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            Setting up position...
          </Button>
        )}
        
        {phase === "trap" && (
          <>
            <Button variant="outline" onClick={getHint} className="flex-1">
              <Lightbulb className="w-4 h-4 mr-2" />
              Hint {hintCount > 0 ? `(${hintCount})` : ""}
            </Button>
            <Button variant="outline" onClick={resetPractice}>
              <RotateCcw className="w-4 h-4 mr-2" />
              Reset
            </Button>
          </>
        )}
        
        {phase === "complete" && (
          <>
            <Button onClick={startPractice} className="flex-1">
              <RotateCcw className="w-4 h-4 mr-2" />
              Practice Again
            </Button>
            {onComplete && (
              <Button variant="outline" onClick={onComplete}>
                Done
              </Button>
            )}
          </>
        )}
      </div>
      
      {/* Trap info */}
      {phase === "ready" && (
        <div className="text-xs text-muted-foreground text-center space-y-1">
          <p>{trap.description}</p>
          <p className="text-purple-400">
            Result: {trap.result_type?.replace("_", " ")} • 
            Difficulty: {trap.difficulty}
          </p>
        </div>
      )}
    </div>
  );
};

export default TrapPractice;
