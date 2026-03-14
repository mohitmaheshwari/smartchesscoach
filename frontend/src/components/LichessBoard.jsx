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
  fen: fenProp = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  orientation = "white",
  onMove,
  interactive = true,
  showDests = true,
  arrows = [],
  highlights = [],
  lastMove = null,
  viewOnly = false,
  planMode = false,  // Allow moving both colors (for analysis)
  movableColor = null, // Specific color that can move (overrides turn-based logic)
}, ref) => {
  // Ensure fen is never null/undefined
  const fen = fenProp || "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
  
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

  // Get moves for a specific color (regardless of whose turn it is)
  const getMovesForColor = (chess, color) => {
    const dests = new Map();
    const currentTurn = chess.turn(); // 'w' or 'b'
    const targetTurn = color === 'white' ? 'w' : 'b';
    
    let tempChess = chess;
    
    // If it's not the target color's turn, switch it temporarily
    if (currentTurn !== targetTurn) {
      const currentFen = chess.fen();
      const parts = currentFen.split(' ');
      parts[1] = targetTurn;
      try {
        tempChess = new Chess(parts.join(' '));
      } catch (e) {
        console.warn("Could not switch turn for color:", e);
        return dests;
      }
    }
    
    const moves = tempChess.moves({ verbose: true });
    for (const move of moves) {
      if (dests.has(move.from)) {
        dests.get(move.from).push(move.to);
      } else {
        dests.set(move.from, [move.to]);
      }
    }
    
    return dests;
  };

  // Use ref for onMove to avoid recreating the board when callback changes
  const onMoveRef = useRef(onMove);
  useEffect(() => {
    onMoveRef.current = onMove;
  }, [onMove]);
  
  // Key to force re-creation when interactivity changes
  const shouldBeInteractive = planMode || movableColor || (interactive && !viewOnly);
  
  // Initialize and recreate chessground when interactivity mode changes
  useEffect(() => {
    // Destroy existing instance
    if (groundRef.current) {
      groundRef.current.destroy();
      groundRef.current = null;
    }
    
    if (boardRef.current) {
      chessRef.current = new Chess(fen);
      
      // Calculate movable destinations based on mode
      let dests = new Map();
      if (shouldBeInteractive && showDests) {
        if (movableColor) {
          // Only show moves for the specified color
          dests = getMovesForColor(chessRef.current, movableColor);
        } else if (planMode) {
          // Plan mode: show moves for both colors
          dests = getAllPossibleDests(chessRef.current);
        } else {
          // Normal mode: only current turn's moves
          dests = getMovableDests(chessRef.current);
        }
      }
      
      console.log("LichessBoard dests check:", "size=" + dests.size, "movableColor=" + movableColor);
      
      console.log("LichessBoard creating instance:", { 
        shouldBeInteractive, planMode, interactive, viewOnly, movableColor,
        fen: fen?.substring(0, 50)
      });
      
      groundRef.current = Chessground(boardRef.current, {
        fen: fen,
        orientation: orientation,
        turnColor: getTurnColor(fen),
        viewOnly: !shouldBeInteractive,
        events: {
          select: (key) => {
            console.log("LichessBoard piece selected:", key);
          }
        },
        movable: {
          free: false,
          color: shouldBeInteractive ? (movableColor || (planMode ? "both" : getTurnColor(fen))) : undefined,
          dests: dests,
          showDests: showDests && shouldBeInteractive,
          events: {
            after: (orig, dest, metadata) => {
              console.log("LichessBoard movable.events.after:", { orig, dest, metadata });
              const currentOnMove = onMoveRef.current;
              if (currentOnMove) {
                const chess = chessRef.current;
                let move = null;
                
                // Try to make the move normally
                try {
                  move = chess.move({ from: orig, to: dest, promotion: "q" });
                } catch (e) {
                  // If move fails (wrong turn), try switching turn in plan mode
                  if (planMode) {
                    const currentFen = chess.fen();
                    const parts = currentFen.split(' ');
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
                  currentOnMove({
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
            }
          }
        },
        draggable: {
          enabled: shouldBeInteractive,
          showGhost: true,
          // No auto-cancel timeout
          distance: 3,
        },
        selectable: {
          enabled: shouldBeInteractive,
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
        predroppable: {
          enabled: false,
        },
        drawable: {
          enabled: true,
          visible: true,
          autoShapes: arrows.length > 0 ? arrows.map(([from, to, color]) => {
            let brush = "blue";
            if (color) {
              const colorLower = color.toLowerCase();
              if (colorLower.includes("red") || colorLower.includes("239")) brush = "red";
              else if (colorLower.includes("green")) brush = "green";
            }
            return { orig: from, dest: to, brush };
          }) : [],
        },
      });
    }

    return () => {
      if (groundRef.current) {
        groundRef.current.destroy();
        groundRef.current = null;
      }
    };
  }, [shouldBeInteractive, planMode, movableColor]);  // Re-create only when interactivity mode changes

  // Track the previous fen to detect if we need to update it
  const prevFenRef = useRef(fen);
  const prevInteractiveRef = useRef(interactive);
  const prevViewOnlyRef = useRef(viewOnly);
  const prevPlanModeRef = useRef(planMode);
  
  // Update position when fen changes AND update interactivity
  // Combined effect to avoid race conditions between fen updates and interactivity changes
  useEffect(() => {
    if (groundRef.current) {
      const shouldBeInteractive = planMode || movableColor || (interactive && !viewOnly);
      const fenChanged = prevFenRef.current !== fen;
      const interactivityChanged = prevInteractiveRef.current !== interactive || 
                                   prevViewOnlyRef.current !== viewOnly ||
                                   prevPlanModeRef.current !== planMode;
      
      console.log("LichessBoard update effect:", {
        fenChanged,
        interactivityChanged,
        prevFen: prevFenRef.current?.substring(0, 30),
        newFen: fen?.substring(0, 30)
      });
      
      // If nothing changed, don't update the board (this preserves selection state)
      if (!fenChanged && !interactivityChanged && !lastMove) {
        return;  // Early return WITHOUT updating refs
      }
      
      // NOW update refs AFTER we know we're proceeding with the update
      prevFenRef.current = fen;
      prevInteractiveRef.current = interactive;
      prevViewOnlyRef.current = viewOnly;
      prevPlanModeRef.current = planMode;
      
      // If nothing changed, don't update the board (this preserves selection state)
      if (!fenChanged && !interactivityChanged && !lastMove) {
        return;
      }
      
      // Update chess instance with current FEN only if FEN actually changed
      if (fenChanged) {
        try {
          if (fen) {
            chessRef.current = new Chess(fen);
          }
        } catch (e) {
          console.warn("Could not sync chess instance:", e);
        }
      }
      
      // For plan mode, get moves for BOTH colors
      // For normal mode, only get moves for current turn
      const dests = shouldBeInteractive && showDests 
        ? (planMode ? getAllPossibleDests(chessRef.current) : getMovableDests(chessRef.current))
        : new Map();
      
      // Build config - only include properties that need updating
      const config = {};
      
      // Set fen if it changed OR if interactivity changed (board may need FEN re-applied)
      if (fenChanged || interactivityChanged) {
        config.fen = fen;
        config.turnColor = getTurnColor(chessRef.current.fen());
      }
      
      // Only update movable/draggable if interactivity changed or fen changed
      if (interactivityChanged || fenChanged) {
        config.viewOnly = !shouldBeInteractive;
        config.movable = {
          free: false,
          color: shouldBeInteractive ? "both" : undefined,
          dests: dests,
          showDests: showDests && shouldBeInteractive,
        };
        config.draggable = {
          enabled: shouldBeInteractive,
          showGhost: true,
        };
        config.selectable = {
          enabled: shouldBeInteractive,
        };
      }
      
      // Only set lastMove if it changed
      if (lastMove) {
        config.lastMove = lastMove;
      }
      
      // Only call set if we have something to update
      if (Object.keys(config).length > 0) {
        groundRef.current.set(config);
      }
    }
  }, [fen, interactive, viewOnly, showDests, lastMove, planMode]);

  // Update orientation
  useEffect(() => {
    if (groundRef.current) {
      groundRef.current.set({ orientation });
    }
  }, [orientation]);

  // Track previous arrows to avoid unnecessary updates
  const prevArrowsRef = useRef([]);
  
  // Update arrows - only when they actually change
  useEffect(() => {
    // Convert arrows to comparable string
    const arrowsKey = JSON.stringify(arrows);
    const prevArrowsKey = JSON.stringify(prevArrowsRef.current);
    
    if (arrowsKey === prevArrowsKey) return; // No change
    
    prevArrowsRef.current = arrows;
    
    const applyArrows = () => {
      if (!groundRef.current) {
        // Board not ready yet, retry after a short delay
        setTimeout(applyArrows, 50);
        return;
      }
      
      if (arrows.length > 0) {
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
      } else {
        groundRef.current.setAutoShapes([]);
      }
    };
    
    applyArrows();
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
