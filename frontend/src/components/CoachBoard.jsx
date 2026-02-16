import { useState, useEffect, useCallback, forwardRef, useImperativeHandle, useRef } from "react";
import { Chess } from "chess.js";
import LichessBoard from "./LichessBoard";
import { Button } from "@/components/ui/button";
import { 
  RotateCcw,
  Target,
} from "lucide-react";

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

/**
 * CoachBoard - A sticky, interactive chessboard for the Board-First Coach UI
 * Now using Lichess's Chessground for better UX
 * 
 * Features:
 * - Jump to any position by FEN or move number
 * - Highlight squares (for showing threats, key squares)
 * - Draw arrows (for showing attack lines)
 * - "Try Move" drill mode - user plays and we validate
 * - Play through move sequences
 */
const CoachBoard = forwardRef(({
  initialFen = START_FEN,
  position,  // Alias for initialFen
  userColor = "white",
  onUserMove,
  drillMode = false,
  expectedMoves = [],  // Array of acceptable moves in SAN notation
  onDrillResult,
  showControls = true,
  size = "full",
  interactive,  // Alias for drillMode
  customArrows = [],  // Arrows to draw: [[from, to, color], ...]
}, ref) => {
  // Support both position and initialFen props
  const effectiveFen = position || initialFen;
  const effectiveDrillMode = interactive !== undefined ? interactive : drillMode;
  
  const [fen, setFen] = useState(effectiveFen);
  const [boardOrientation, setBoardOrientation] = useState(userColor);
  const [arrows, setArrows] = useState([]);
  const [isDrillActive, setIsDrillActive] = useState(effectiveDrillMode);
  const [drillFeedback, setDrillFeedback] = useState(null);
  const [lastMove, setLastMove] = useState(null);
  
  const chessRef = useRef(new Chess(effectiveFen));
  const lichessBoardRef = useRef(null);

  // Update board when position/initialFen changes
  useEffect(() => {
    const newFen = position || initialFen;
    setFen(newFen);
    chessRef.current = new Chess(newFen);
    setDrillFeedback(null);
    setLastMove(null);
  }, [initialFen, position]);

  useEffect(() => {
    setBoardOrientation(userColor === "black" ? "black" : "white");
  }, [userColor]);

  useEffect(() => {
    const newDrillMode = interactive !== undefined ? interactive : drillMode;
    setIsDrillActive(newDrillMode);
    if (!newDrillMode) {
      setDrillFeedback(null);
    }
  }, [drillMode, interactive]);

  // Handle move from LichessBoard
  const handleLichessMove = useCallback((moveData) => {
    if (!isDrillActive) return;

    const { san, from, to } = moveData;
    const isCorrect = expectedMoves.length === 0 || expectedMoves.includes(san);
    
    // Update chess ref with the move
    chessRef.current = new Chess(moveData.fen);
    setFen(moveData.fen);
    setLastMove([from, to]);
    
    // Show feedback
    if (isCorrect) {
      setDrillFeedback({ type: 'success', message: 'Correct!' });
    } else {
      setDrillFeedback({ 
        type: 'error', 
        message: `Try again. ${expectedMoves.length > 0 ? `Hint: Consider ${expectedMoves[0]}` : ''}` 
      });
      // Undo the wrong move - reset to previous position
      const prevFen = position || initialFen;
      chessRef.current = new Chess(prevFen);
      setTimeout(() => {
        setFen(prevFen);
        setLastMove(null);
      }, 1000);
    }

    if (onDrillResult) {
      onDrillResult({ correct: isCorrect, playedMove: san, expectedMoves });
    }

    if (onUserMove) {
      onUserMove(moveData);
    }
  }, [isDrillActive, expectedMoves, onDrillResult, onUserMove, position, initialFen]);

  // Expose methods to parent
  useImperativeHandle(ref, () => ({
    // Jump to a specific FEN position
    jumpToFen: (newFen, options = {}) => {
      setFen(newFen);
      chessRef.current = new Chess(newFen);
      setDrillFeedback(null);
      setLastMove(null);
      
      if (options.arrows) {
        setArrows(options.arrows);
      } else {
        setArrows([]);
      }
      
      // Use LichessBoard's highlight capability
      if (lichessBoardRef.current && options.highlight) {
        lichessBoardRef.current.highlightSquares(options.highlight);
      }
    },

    // Highlight specific squares
    highlightSquares: (squares) => {
      if (lichessBoardRef.current) {
        lichessBoardRef.current.highlightSquares(squares);
      }
    },

    // Clear all highlights
    clearHighlights: () => {
      setArrows([]);
      if (lichessBoardRef.current) {
        lichessBoardRef.current.clearArrows();
      }
    },

    // Draw arrows on the board
    drawArrows: (arrowsArray) => {
      setArrows(arrowsArray);
    },

    // Enable drill mode
    startDrill: () => {
      setIsDrillActive(true);
      setDrillFeedback(null);
    },

    // Disable drill mode  
    stopDrill: () => {
      setIsDrillActive(false);
      setDrillFeedback(null);
    },

    // Play a sequence of moves with animation
    playMoveSequence: async (moves, delayMs = 800) => {
      const chess = new Chess(fen);
      
      for (const moveStr of moves) {
        await new Promise(resolve => setTimeout(resolve, delayMs));
        try {
          const move = chess.move(moveStr);
          if (move) {
            setFen(chess.fen());
            setLastMove([move.from, move.to]);
          }
        } catch (e) {
          console.error("Invalid move:", moveStr);
        }
      }
      chessRef.current = chess;
    },

    // Get current FEN
    getFen: () => fen,

    // Reset to initial position
    reset: () => {
      const resetFen = position || initialFen;
      setFen(resetFen);
      chessRef.current = new Chess(resetFen);
      setArrows([]);
      setDrillFeedback(null);
      setLastMove(null);
    },

    // Flip the board
    flipBoard: () => {
      setBoardOrientation(prev => prev === "white" ? "black" : "white");
    },

    // Show threat with arrow
    showThreat: (threatMove) => {
      if (!threatMove) return;
      try {
        const chess = new Chess(fen);
        const move = chess.move(threatMove);
        if (move) {
          setArrows([[move.from, move.to, "rgb(239, 68, 68)"]]);
          chess.undo();
        }
      } catch (e) {
        console.error("Invalid threat move:", threatMove);
      }
    },

    // Clear arrows
    clearArrows: () => {
      setArrows([]);
    },

    // Play a single move and show result
    playSingleMove: (moveStr) => {
      try {
        const move = chessRef.current.move(moveStr);
        if (move) {
          const newFen = chessRef.current.fen();
          setFen(newFen);
          setLastMove([move.from, move.to]);
          return { success: true, move };
        }
      } catch (e) {
        console.error("Invalid move:", moveStr);
      }
      return { success: false };
    },

    // Go back one move
    undoMove: () => {
      const move = chessRef.current.undo();
      if (move) {
        const newFen = chessRef.current.fen();
        setFen(newFen);
        setLastMove(null);
        return true;
      }
      return false;
    },

    // Get position after sequence (for preview)
    getPositionAfterMoves: (moves, startFen = null) => {
      const chess = new Chess(startFen || (position || initialFen));
      for (const moveStr of moves) {
        try {
          chess.move(moveStr);
        } catch (e) {
          break;
        }
      }
      return chess.fen();
    },

    // Set position directly via LichessBoard
    setPosition: (newFen) => {
      setFen(newFen);
      chessRef.current = new Chess(newFen);
      if (lichessBoardRef.current) {
        lichessBoardRef.current.setPosition(newFen);
      }
    }
  }), [fen, initialFen, position]);

  const flipBoard = useCallback(() => {
    setBoardOrientation(p => p === "white" ? "black" : "white");
  }, []);

  return (
    <div className="space-y-3" data-testid="coach-board">
      {/* Drill Mode Indicator */}
      {isDrillActive && (
        <div className="flex items-center gap-2 px-3 py-2 bg-amber-500/10 border border-amber-500/30 rounded-lg">
          <Target className="w-4 h-4 text-amber-500" />
          <span className="text-sm font-medium text-amber-400">
            Your turn - Find the best move
          </span>
        </div>
      )}

      {/* Drill Feedback */}
      {drillFeedback && (
        <div className={`flex items-center gap-2 px-3 py-2 rounded-lg ${
          drillFeedback.type === 'success' 
            ? 'bg-emerald-500/10 border border-emerald-500/30' 
            : 'bg-red-500/10 border border-red-500/30'
        }`} data-testid="drill-feedback">
          <span className={`text-sm font-medium ${
            drillFeedback.type === 'success' ? 'text-emerald-400' : 'text-red-400'
          }`}>
            {drillFeedback.message}
          </span>
        </div>
      )}

      {/* Lichess Chessground Board */}
      <div className={`relative ${size === "full" ? "w-full" : "w-[320px]"} aspect-square`}>
        <LichessBoard
          ref={lichessBoardRef}
          fen={fen}
          orientation={boardOrientation}
          onMove={handleLichessMove}
          interactive={isDrillActive}
          viewOnly={!isDrillActive}
          arrows={[...arrows, ...customArrows]}
          showDests={isDrillActive}
          lastMove={lastMove}
        />
      </div>

      {/* Controls */}
      {showControls && (
        <div className="flex items-center justify-center gap-1">
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={flipBoard}
            className="text-muted-foreground hover:text-foreground"
            data-testid="flip-board-btn"
          >
            <RotateCcw className="w-4 h-4" />
          </Button>
        </div>
      )}
    </div>
  );
});

CoachBoard.displayName = "CoachBoard";

export default CoachBoard;
