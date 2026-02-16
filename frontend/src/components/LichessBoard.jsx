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
  planMode = false,  // NEW: Allow moving both colors
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

  // Get ALL possible moves for both colors (for plan mode)
  const getAllPossibleDests = (chess) => {
    const dests = new Map();
    
    // Get current turn's moves
    const currentMoves = chess.moves({ verbose: true });
    for (const move of currentMoves) {
      if (dests.has(move.from)) {
        dests.get(move.from).push(move.to);
      } else {
        dests.set(move.from, [move.to]);
      }
    }
    
    // Also add opposite color's moves by switching turn
    const fen = chess.fen();
    const parts = fen.split(' ');
    parts[1] = parts[1] === 'w' ? 'b' : 'w'; // Switch turn
    try {
      const tempChess = new Chess(parts.join(' '));
      const oppMoves = tempChess.moves({ verbose: true });
      for (const move of oppMoves) {
        if (dests.has(move.from)) {
          if (!dests.get(move.from).includes(move.to)) {
            dests.get(move.from).push(move.to);
          }
        } else {
          dests.set(move.from, [move.to]);
        }
      }
    } catch (e) {
      // If switching turns creates invalid position (e.g., king in check), ignore
      console.warn("Could not get opposite color moves:", e);
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
          color: (interactive || planMode) ? "both" : undefined,
          dests: (interactive || planMode) && showDests 
            ? (planMode ? getAllPossibleDests(chessRef.current) : getMovableDests(chessRef.current)) 
            : new Map(),
          showDests: showDests,
        },
        draggable: {
          enabled: (interactive || planMode) && !viewOnly,
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
              let move = null;
              
              // Try to make the move normally
              try {
                move = chess.move({ from: orig, to: dest, promotion: "q" });
              } catch (e) {
                // If move fails (wrong turn), try switching turn in plan mode
                if (planMode) {
                  const fen = chess.fen();
                  const parts = fen.split(' ');
                  parts[1] = parts[1] === 'w' ? 'b' : 'w';
                  try {
                    chessRef.current = new Chess(parts.join(' '));
                    move = chessRef.current.move({ from: orig, to: dest, promotion: "q" });
                  } catch (e2) {
                    console.warn("Could not make move in plan mode:", e2);
                  }
                }
              }
              
              if (move) {
                onMove({
                  from: orig,
                  to: dest,
                  san: move.san,
                  fen: chessRef.current.fen(),
                  isCapture: move.captured !== undefined,
                  isCheck: chessRef.current.inCheck(),
                  isCheckmate: chessRef.current.isCheckmate(),
                });
                
                // Update board state - in plan mode, show moves for both colors
                const newDests = planMode 
                  ? getAllPossibleDests(chessRef.current) 
                  : getMovableDests(chessRef.current);
                
                groundRef.current.set({
                  fen: chessRef.current.fen(),
                  turnColor: getTurnColor(chessRef.current.fen()),
                  movable: {
                    dests: newDests,
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

  // Update interactivity when interactive/viewOnly changes
  useEffect(() => {
    if (groundRef.current) {
      // Check planMode first - if planMode is true, we want the board interactive
      // regardless of the interactive prop
      const shouldBeInteractive = planMode || (interactive && !viewOnly);
      
      // Update chess instance with current FEN
      try {
        if (fen) {
          chessRef.current = new Chess(fen);
        }
      } catch (e) {
        console.warn("Could not sync chess instance:", e);
      }
      
      // For plan mode, get moves for BOTH colors
      // For normal mode, only get moves for current turn
      const dests = shouldBeInteractive && showDests 
        ? (planMode ? getAllPossibleDests(chessRef.current) : getMovableDests(chessRef.current))
        : new Map();
      
      console.log("LichessBoard interactivity update:", { shouldBeInteractive, planMode, interactive, destsSize: dests.size, fenStart: fen?.substring(0, 30) });
      
      // Apply configuration - key fix: ensure viewOnly is false and draggable is enabled
      groundRef.current.set({
        viewOnly: !shouldBeInteractive,
        movable: {
          free: false,  // Don't use free mode - use dests instead for better control
          color: shouldBeInteractive ? "both" : undefined,
          dests: dests,
          showDests: showDests && shouldBeInteractive,
        },
        draggable: {
          enabled: shouldBeInteractive,
          showGhost: true,
        },
      });
    }
  }, [interactive, viewOnly, showDests, fen, planMode]);

  // Update orientation
  useEffect(() => {
    if (groundRef.current) {
      groundRef.current.set({ orientation });
    }
  }, [orientation]);

  // Update arrows
  useEffect(() => {
    if (groundRef.current && arrows.length > 0) {
      const shapes = arrows.map(([from, to, color]) => {
        // Determine brush based on color - chessground uses named brushes
        let brush = "blue";  // default
        if (color) {
          const colorLower = color.toLowerCase();
          if (colorLower.includes("red") || colorLower.includes("239")) {
            brush = "red";
          } else if (colorLower.includes("green") || colorLower.includes("34,") || colorLower.includes("200, 83")) {
            brush = "green";
          } else if (colorLower.includes("yellow") || colorLower.includes("255, 200")) {
            brush = "yellow";
          }
        }
        return {
          orig: from,
          dest: to,
          brush: brush,
        };
      });
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
