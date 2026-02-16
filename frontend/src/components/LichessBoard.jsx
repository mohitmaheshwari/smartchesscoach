import { useEffect, useRef, useState, forwardRef, useImperativeHandle } from "react";
import { Chessground } from "chessground";
import { Chess } from "chess.js";
import "chessground/assets/chessground.base.css";
import "chessground/assets/chessground.brown.css";
import "chessground/assets/chessground.cburnett.css";

/**
 * Lichess Chessground Board Component
 * 
 * This uses the same board library as Lichess.org for:
 * - Better arrow rendering
 * - Smooth animations
 * - Move destinations highlighting
 * - Professional look and feel
 */
const LichessBoard = forwardRef(({
  fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  orientation = "white",
  onMove,
  interactive = true,
  showDests = true,
  arrows = [],
  highlights = [],
  lastMove = null,
  viewOnly = false,
}, ref) => {
  const boardRef = useRef(null);
  const groundRef = useRef(null);
  const chessRef = useRef(new Chess(fen));

  // Expose methods via ref
  useImperativeHandle(ref, () => ({
    setPosition: (newFen) => {
      if (groundRef.current) {
        chessRef.current = new Chess(newFen);
        groundRef.current.set({
          fen: newFen,
          turnColor: getTurnColor(newFen),
          movable: {
            dests: interactive ? getMovableDests(chessRef.current) : new Map(),
          },
        });
      }
    },
    drawArrows: (arrowList) => {
      if (groundRef.current) {
        // Convert to chessground format: [brush, orig, dest]
        const shapes = arrowList.map(([from, to, color]) => ({
          orig: from,
          dest: to,
          brush: color?.includes("green") ? "green" : color?.includes("red") ? "red" : "blue",
        }));
        groundRef.current.setAutoShapes(shapes);
      }
    },
    clearArrows: () => {
      if (groundRef.current) {
        groundRef.current.setAutoShapes([]);
      }
    },
    highlightSquares: (squares) => {
      if (groundRef.current) {
        const shapes = squares.map(sq => ({
          orig: sq,
          brush: "yellow",
        }));
        groundRef.current.setAutoShapes(shapes);
      }
    },
    getGround: () => groundRef.current,
  }));

  // Get turn color from FEN
  const getTurnColor = (fenStr) => {
    return fenStr.includes(" w ") ? "white" : "black";
  };

  // Get legal moves for chessground
  const getMovableDests = (chess) => {
    const dests = new Map();
    const moves = chess.moves({ verbose: true });
    
    for (const move of moves) {
      const from = move.from;
      const to = move.to;
      
      if (dests.has(from)) {
        dests.get(from).push(to);
      } else {
        dests.set(from, [to]);
      }
    }
    
    return dests;
  };

  // Initialize chessground
  useEffect(() => {
    if (boardRef.current && !groundRef.current) {
      chessRef.current = new Chess(fen);
      
      groundRef.current = Chessground(boardRef.current, {
        fen: fen,
        orientation: orientation,
        turnColor: getTurnColor(fen),
        viewOnly: viewOnly || !interactive,
        movable: {
          free: false,
          color: interactive ? "both" : undefined,
          dests: interactive && showDests ? getMovableDests(chessRef.current) : new Map(),
          showDests: showDests,
        },
        draggable: {
          enabled: interactive && !viewOnly,
          showGhost: true,
        },
        highlight: {
          lastMove: true,
          check: true,
        },
        animation: {
          enabled: true,
          duration: 200,
        },
        premovable: {
          enabled: false,
        },
        drawable: {
          enabled: true,
          visible: true,
          autoShapes: [],
        },
        events: {
          move: (orig, dest) => {
            if (onMove) {
              const chess = chessRef.current;
              const move = chess.move({ from: orig, to: dest, promotion: "q" });
              
              if (move) {
                onMove({
                  from: orig,
                  to: dest,
                  san: move.san,
                  fen: chess.fen(),
                  isCapture: move.captured !== undefined,
                  isCheck: chess.inCheck(),
                  isCheckmate: chess.isCheckmate(),
                });
                
                // Update board state
                groundRef.current.set({
                  fen: chess.fen(),
                  turnColor: getTurnColor(chess.fen()),
                  movable: {
                    dests: getMovableDests(chess),
                  },
                  lastMove: [orig, dest],
                });
              } else {
                // Invalid move - reset position
                groundRef.current.set({ fen: chess.fen() });
              }
            }
          },
        },
      });
    }

    return () => {
      if (groundRef.current) {
        groundRef.current.destroy();
        groundRef.current = null;
      }
    };
  }, []);

  // Update position when fen changes
  useEffect(() => {
    if (groundRef.current && fen) {
      chessRef.current = new Chess(fen);
      groundRef.current.set({
        fen: fen,
        turnColor: getTurnColor(fen),
        movable: {
          dests: interactive && showDests ? getMovableDests(chessRef.current) : new Map(),
        },
        lastMove: lastMove || undefined,
      });
    }
  }, [fen, interactive, showDests, lastMove]);

  // Update orientation
  useEffect(() => {
    if (groundRef.current) {
      groundRef.current.set({ orientation });
    }
  }, [orientation]);

  // Update arrows
  useEffect(() => {
    if (groundRef.current && arrows.length > 0) {
      const shapes = arrows.map(([from, to, color]) => ({
        orig: from,
        dest: to,
        brush: color?.includes("green") ? "green" : color?.includes("red") ? "red" : "blue",
      }));
      groundRef.current.setAutoShapes(shapes);
    } else if (groundRef.current) {
      groundRef.current.setAutoShapes([]);
    }
  }, [arrows]);

  return (
    <div 
      ref={boardRef} 
      className="w-full aspect-square rounded-lg overflow-hidden"
      style={{ 
        maxWidth: "100%",
      }}
    />
  );
});

LichessBoard.displayName = "LichessBoard";

export default LichessBoard;
