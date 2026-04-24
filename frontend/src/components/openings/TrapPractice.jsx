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
  ChevronRight,
  Eye
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

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
  const [lastMove, setLastMove] = useState(null);
  
  const setupMoves = trap?.setup_moves || [];
  const trapLine = trap?.trap_line || [];
  
  // Use refs to store current state for callbacks
  const currentMoveIndexRef = useRef(currentMoveIndex);
  currentMoveIndexRef.current = currentMoveIndex;
  
  // Determine user's color - user plays the color that EXECUTES the trap (the winner)
  const getUserColor = () => {
    if (trap?.trap_color) {
      return trap.trap_color;
    }
    
    const setupCount = setupMoves.length;
    const desc = (trap?.description || "").toLowerCase();
    const name = (trap?.name || "").toLowerCase();
    const successMsg = (trap?.success_message || "").toLowerCase();
    
    if (desc.includes("black wins") || desc.includes("for black") || 
        successMsg.includes("for black") || desc.includes("black sacrifices")) {
      return "black";
    }
    
    if (desc.includes("white wins") || successMsg.includes("for white")) {
      return "white";
    }
    
    if (name.includes("blackburne") || name.includes("traxler") || 
        name.includes("shilling") || name.includes("elephant") ||
        name.includes("siberian") || name.includes("stafford")) {
      return "black";
    }
    
    if (trapLine.length > 0) {
      const totalMoves = setupCount + trapLine.length;
      const lastMoveIsWhite = totalMoves % 2 === 1;
      return lastMoveIsWhite ? "white" : "black";
    }
    
    return "white";
  };
  
  const userColor = getUserColor();
  
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
  
  // Set up the board for user to make a move
  const setupUserMoveBoard = useCallback(() => {
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
    
    if (turnColor === userColor) {
      groundRef.current.set({
        turnColor,
        movable: {
          free: false,
          color: turnColor,
          dests
        },
        events: {
          move: (orig, dest) => handleMove(orig, dest)
        }
      });
    }
  }, [userColor, trapLine, trap]);
  
  // Handle user's move
  const handleMove = useCallback((orig, dest) => {
    const idx = currentMoveIndexRef.current;
    const expectedMove = trapLine[idx];
    
    if (!expectedMove) {
      setPhase("complete");
      return;
    }
    
    try {
      const result = chessRef.current.move({ from: orig, to: dest, promotion: 'q' });
      
      if (!result) {
        setFeedback({ type: "error", message: "Invalid move" });
        setupUserMoveBoard();
        return;
      }
      
      const expectedSan = expectedMove.move.replace(/[+#!?]/g, "");
      const playedSan = result.san.replace(/[+#!?]/g, "");
      
      if (playedSan.toLowerCase() === expectedSan.toLowerCase()) {
        // Correct move!
        setFen(chessRef.current.fen());
        setLastMove({ from: result.from, to: result.to });
        setFeedback({ 
          type: "correct", 
          message: expectedMove.explanation 
        });
        setHintCount(0);
        
        const nextIndex = idx + 1;
        setCurrentMoveIndex(nextIndex);
        
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
        
        // Play opponent's response
        setTimeout(() => {
          playOpponentMoveAt(nextIndex);
        }, 1000);
        
      } else {
        // Wrong move
        chessRef.current.undo();
        setFeedback({
          type: "incorrect",
          message: "Not quite! Think about what the trap is trying to achieve."
        });
        setupUserMoveBoard();
      }
    } catch (e) {
      console.error("Move error:", e);
      setFeedback({ type: "error", message: "Invalid move" });
      setupUserMoveBoard();
    }
  }, [trapLine, trap, setupUserMoveBoard]);
  
  // Play opponent's move at given index
  const playOpponentMoveAt = useCallback((index) => {
    if (index >= trapLine.length) {
      setPhase("complete");
      return;
    }
    
    const moveData = trapLine[index];
    
    try {
      const result = chessRef.current.move(moveData.move);
      if (result) {
        setFen(chessRef.current.fen());
        setLastMove({ from: result.from, to: result.to });
        setCurrentMoveIndex(index + 1);
        
        setFeedback({
          type: "opponent",
          message: `Opponent played ${moveData.move}`,
          submessage: moveData.explanation
        });
        
        if (index + 1 >= trapLine.length) {
          setTimeout(() => {
            setPhase("complete");
            setFeedback({
              type: "success",
              message: trap.success_message || "Trap complete!"
            });
          }, 1000);
          return;
        }
        
        // User's turn - show hint about expected move
        setTimeout(() => {
          const nextUserMoveIndex = index + 1;
          const nextMove = trapLine[nextUserMoveIndex];
          if (nextMove) {
            setFeedback({
              type: "info",
              message: "Your turn!",
              submessage: `Hint: ${nextMove.explanation}`
            });
          } else {
            setFeedback({
              type: "info",
              message: "Your turn! Make your move."
            });
          }
          setupUserMoveBoard();
        }, 1200);
      }
    } catch (e) {
      console.error("Invalid opponent move:", moveData.move, e);
    }
  }, [trapLine, trap, setupUserMoveBoard]);
  
  // Play setup moves one by one
  const playSetupMovesFrom = useCallback((index) => {
    if (index >= setupMoves.length) {
      // Setup complete
      setPhase("trap");
      setCurrentMoveIndex(0);
      
      const chess = chessRef.current;
      const turnColor = chess.turn() === 'w' ? 'white' : 'black';
      
      if (turnColor !== userColor && trapLine.length > 0) {
        // Opponent moves first
        setFeedback({
          type: "info",
          message: "Watch the opponent fall into the trap..."
        });
        setTimeout(() => {
          playOpponentMoveAt(0);
        }, 800);
      } else {
        // User moves first - show hint about expected move
        const firstUserMove = trapLine[0];
        if (firstUserMove) {
          setFeedback({
            type: "info",
            message: "Your turn! Execute the trap.",
            submessage: `Hint: ${firstUserMove.explanation}`
          });
        } else {
          setFeedback({
            type: "info",
            message: "Your turn! Execute the trap."
          });
        }
        setupUserMoveBoard();
      }
      return;
    }
    
    const move = setupMoves[index];
    
    setTimeout(() => {
      try {
        const result = chessRef.current.move(move);
        if (result) {
          setFen(chessRef.current.fen());
          setLastMove({ from: result.from, to: result.to });
          playSetupMovesFrom(index + 1);
        }
      } catch (e) {
        console.error("Invalid setup move:", move, e);
      }
    }, 600);
  }, [setupMoves, userColor, trapLine, playOpponentMoveAt, setupUserMoveBoard]);
  
  // Start the practice
  const startPractice = useCallback(() => {
    chessRef.current.reset();
    setFen(chessRef.current.fen());
    setPhase("setup");
    setCurrentMoveIndex(0);
    setFeedback(null);
    setHintCount(0);
    setLastMove(null);

    playSetupMovesFrom(0);
  }, [playSetupMovesFrom]);

  // Watch-first demo: plays the full setup + trap line automatically so the
  // user can LEARN the pattern before being asked to execute it. Critical
  // for first-time encounters — previously users were dropped straight
  // into "execute the trap" with no idea what the trap looked like.
  const runDemo = useCallback(() => {
    chessRef.current.reset();
    setFen(chessRef.current.fen());
    setPhase("demo");
    setCurrentMoveIndex(0);
    setLastMove(null);
    setHintCount(0);
    setFeedback({
      type: "info",
      message: "Watch how the trap plays out.",
    });

    // Lock the board — no user input during demo.
    if (groundRef.current) {
      groundRef.current.set({
        movable: { free: false, color: undefined, dests: new Map() },
      });
    }

    const fullSequence = [
      ...setupMoves.map((m) => ({ move: m, note: "" })),
      ...trapLine.map((m) => ({ move: m.move, note: m.explanation || "" })),
    ];

    const DEMO_STEP_MS = 1100;

    const step = (i) => {
      if (i >= fullSequence.length) {
        // End of demo — reset and invite practice.
        setTimeout(() => {
          chessRef.current.reset();
          setFen(chessRef.current.fen());
          setLastMove(null);
          setPhase("ready");
          setFeedback({
            type: "info",
            message: "Now you try. Execute the trap yourself.",
          });
        }, DEMO_STEP_MS + 400);
        return;
      }
      const entry = fullSequence[i];
      try {
        const result = chessRef.current.move(entry.move);
        if (result) {
          setFen(chessRef.current.fen());
          setLastMove({ from: result.from, to: result.to });
          if (entry.note) {
            setFeedback({ type: "info", message: entry.note });
          }
        }
      } catch (e) {
        console.warn("demo move failed:", entry.move, e);
      }
      setTimeout(() => step(i + 1), DEMO_STEP_MS);
    };

    // Slight delay before starting so the opening-message is readable.
    setTimeout(() => step(0), 600);
  }, [setupMoves, trapLine]);
  
  // Get a hint
  const getHint = useCallback(() => {
    const currentMove = trapLine[currentMoveIndex];
    if (!currentMove) return;
    
    setHintCount(prev => {
      const newCount = prev + 1;
      
      if (newCount === 1) {
        setFeedback({
          type: "hint",
          message: currentMove.explanation
        });
      } else if (newCount === 2) {
        const move = currentMove.move;
        const piece = move[0].toUpperCase() === move[0] ? move[0] : "Pawn";
        const pieceName = piece === 'N' ? 'Knight' : piece === 'B' ? 'Bishop' : 
                         piece === 'R' ? 'Rook' : piece === 'Q' ? 'Queen' : 
                         piece === 'K' ? 'King' : 'Pawn';
        setFeedback({
          type: "hint",
          message: `Move your ${pieceName}. ${currentMove.explanation}`
        });
      } else {
        setFeedback({
          type: "hint",
          message: `The correct move is ${currentMove.move}. ${currentMove.explanation}`
        });
      }
      
      return newCount;
    });
  }, [currentMoveIndex, trapLine]);
  
  // Reset
  const resetPractice = useCallback(() => {
    chessRef.current.reset();
    setFen(chessRef.current.fen());
    setPhase("ready");
    setCurrentMoveIndex(0);
    setFeedback(null);
    setHintCount(0);
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
            data-testid="trap-practice-board"
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
                  feedback.type === "info" ? "bg-blue-500/10 border border-blue-500/30" :
                  feedback.type === "opponent" ? "bg-amber-500/10 border border-amber-500/30" :
                  feedback.type === "incorrect" ? "bg-amber-500/10 border border-amber-500/30" :
                  "bg-red-500/10 border border-red-500/30"
                }`}
              >
                <div className="flex items-start gap-2">
                  {feedback.type === "correct" && <CheckCircle2 className="w-5 h-5 text-green-400 flex-shrink-0" />}
                  {feedback.type === "success" && <Trophy className="w-5 h-5 text-purple-400 flex-shrink-0" />}
                  {feedback.type === "hint" && <Lightbulb className="w-5 h-5 text-blue-400 flex-shrink-0" />}
                  {feedback.type === "info" && <Lightbulb className="w-5 h-5 text-blue-400 flex-shrink-0" />}
                  {feedback.type === "opponent" && <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0" />}
                  {feedback.type === "incorrect" && <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0" />}
                  <div>
                    <p className="text-sm">{feedback.message}</p>
                    {feedback.submessage && (
                      <p className="text-xs text-muted-foreground mt-1">{feedback.submessage}</p>
                    )}
                  </div>
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
      
      {/* Trap Moves Guide - shows the sequence user needs to play */}
      {phase === "trap" && (
        <Card className="bg-muted/30">
          <CardContent className="p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-muted-foreground">Trap Sequence</span>
              <Badge variant="outline" className="text-xs">
                {userColor === "white" ? "You play White" : "You play Black"}
              </Badge>
            </div>
            <div className="space-y-1 max-h-[180px] overflow-y-auto">
              {trapLine.map((moveData, i) => {
                const isUserMove = (i % 2 === 0) === (userColor === "white" ? 
                  (setupMoves.length % 2 === 0) : (setupMoves.length % 2 === 1));
                const isCompleted = i < currentMoveIndex;
                const isCurrent = i === currentMoveIndex;
                
                return (
                  <div 
                    key={i}
                    className={`flex items-center gap-2 p-1.5 rounded text-xs transition-all ${
                      isCompleted 
                        ? "bg-green-500/10 text-green-400" 
                        : isCurrent 
                        ? "bg-amber-500/10 text-amber-400 border border-amber-500/30" 
                        : "text-muted-foreground opacity-50"
                    }`}
                  >
                    <span className="w-5 text-center flex-shrink-0">
                      {isCompleted ? (
                        <CheckCircle2 className="w-3 h-3 inline" />
                      ) : (
                        <span className={`${isUserMove ? "font-bold" : ""}`}>{i + 1}</span>
                      )}
                    </span>
                    <span className={`font-mono ${isUserMove ? "font-bold text-primary" : ""}`}>
                      {moveData.move}
                    </span>
                    <span className={`text-xs truncate flex-1 ${isUserMove ? "" : "italic"}`}>
                      {isUserMove ? "(You)" : "(Opp)"}
                    </span>
                    {isCurrent && isUserMove && (
                      <span className="text-amber-400 text-xs">← Play this</span>
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* Controls */}
      <div className="flex gap-2">
        {phase === "ready" && (
          <>
            <Button variant="outline" onClick={runDemo} className="flex-1" data-testid="watch-trap-demo">
              <Eye className="w-4 h-4 mr-2" />
              Watch first
            </Button>
            <Button onClick={startPractice} className="flex-1" data-testid="start-trap-practice">
              <Play className="w-4 h-4 mr-2" />
              Start Practice
            </Button>
          </>
        )}

        {phase === "demo" && (
          <Button disabled className="flex-1">
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            Playing trap demo...
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
            <Button variant="outline" onClick={getHint} className="flex-1" data-testid="trap-hint-btn">
              <Lightbulb className="w-4 h-4 mr-2" />
              Hint {hintCount > 0 ? `(${hintCount})` : ""}
            </Button>
            <Button variant="outline" onClick={resetPractice} data-testid="trap-reset-btn">
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
