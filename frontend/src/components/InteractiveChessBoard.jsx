import { useState, useEffect, useMemo, useCallback } from "react";
import { Chess } from "chess.js";
import { ChevronLeft, ChevronRight, SkipBack, SkipForward, Play, Pause } from "lucide-react";
import { Button } from "@/components/ui/button";

// Piece symbols for display
const PIECE_SYMBOLS = {
  'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
  'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟'
};

const FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
const RANKS = ['8', '7', '6', '5', '4', '3', '2', '1'];

/**
 * Interactive Chess Board for showing opening moves
 */
const InteractiveChessBoard = ({ 
  moves = [],  // Array of moves in SAN notation: ["e4", "e5", "Nf3", "Nc6", "Bc4"]
  startingFen = null,  // Optional starting FEN position
  size = 320,  // Board size in pixels
  autoPlay = false,  // Auto-play through moves
  autoPlaySpeed = 1500,  // Speed in ms
  showMoveList = true,
  showCoaching = null,  // Coaching text for current move
  flipBoard = false,
}) => {
  const [currentMoveIndex, setCurrentMoveIndex] = useState(-1);
  const [isPlaying, setIsPlaying] = useState(autoPlay);
  const [highlightSquares, setHighlightSquares] = useState([]);
  
  const squareSize = size / 8;
  
  // Parse moves and build position history
  const { positions, moveHistory, error } = useMemo(() => {
    const chess = new Chess(startingFen || undefined);
    const positions = [chess.fen()];
    const history = [];
    
    for (const move of moves) {
      try {
        const result = chess.move(move);
        if (result) {
          positions.push(chess.fen());
          history.push({
            san: result.san,
            from: result.from,
            to: result.to,
            piece: result.piece,
            captured: result.captured,
          });
        }
      } catch (e) {
        console.warn(`Invalid move: ${move}`, e);
      }
    }
    
    return { positions, moveHistory: history, error: null };
  }, [moves, startingFen]);
  
  // Get current board state
  const currentFen = positions[currentMoveIndex + 1] || positions[0];
  const currentMove = currentMoveIndex >= 0 ? moveHistory[currentMoveIndex] : null;
  
  // Parse FEN to get board array
  const board = useMemo(() => {
    const chess = new Chess(currentFen);
    return chess.board();
  }, [currentFen]);
  
  // Update highlights when move changes
  useEffect(() => {
    if (currentMove) {
      setHighlightSquares([currentMove.from, currentMove.to]);
    } else {
      setHighlightSquares([]);
    }
  }, [currentMove]);
  
  // Auto-play functionality
  useEffect(() => {
    if (!isPlaying) return;
    
    if (currentMoveIndex >= moveHistory.length - 1) {
      setIsPlaying(false);
      return;
    }
    
    const timer = setTimeout(() => {
      setCurrentMoveIndex(prev => Math.min(prev + 1, moveHistory.length - 1));
    }, autoPlaySpeed);
    
    return () => clearTimeout(timer);
  }, [isPlaying, currentMoveIndex, moveHistory.length, autoPlaySpeed]);
  
  // Navigation handlers
  const goToStart = useCallback(() => {
    setCurrentMoveIndex(-1);
    setIsPlaying(false);
  }, []);
  
  const goBack = useCallback(() => {
    setCurrentMoveIndex(prev => Math.max(-1, prev - 1));
  }, []);
  
  const goForward = useCallback(() => {
    setCurrentMoveIndex(prev => Math.min(moveHistory.length - 1, prev + 1));
  }, [moveHistory.length]);
  
  const goToEnd = useCallback(() => {
    setCurrentMoveIndex(moveHistory.length - 1);
    setIsPlaying(false);
  }, [moveHistory.length]);
  
  const togglePlay = useCallback(() => {
    if (currentMoveIndex >= moveHistory.length - 1) {
      setCurrentMoveIndex(-1);
    }
    setIsPlaying(prev => !prev);
  }, [currentMoveIndex, moveHistory.length]);
  
  // Render a single square
  const renderSquare = (row, col) => {
    const displayRow = flipBoard ? 7 - row : row;
    const displayCol = flipBoard ? 7 - col : col;
    
    const file = FILES[displayCol];
    const rank = RANKS[displayRow];
    const squareName = file + rank;
    
    const isLight = (displayRow + displayCol) % 2 === 0;
    const isHighlighted = highlightSquares.includes(squareName);
    
    const piece = board[displayRow]?.[displayCol];
    
    // Colors
    const lightColor = '#f0d9b5';
    const darkColor = '#b58863';
    const highlightColor = 'rgba(255, 255, 0, 0.5)';
    
    return (
      <div
        key={squareName}
        style={{
          width: squareSize,
          height: squareSize,
          backgroundColor: isHighlighted ? highlightColor : (isLight ? lightColor : darkColor),
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
          transition: 'background-color 0.2s ease',
        }}
      >
        {piece && (
          <span
            style={{
              fontSize: squareSize * 0.75,
              color: piece.color === 'w' ? '#fff' : '#000',
              textShadow: piece.color === 'w' 
                ? '1px 1px 2px #000, -1px -1px 2px #000' 
                : '1px 1px 2px #fff, -1px -1px 2px #fff',
              lineHeight: 1,
              userSelect: 'none',
            }}
          >
            {PIECE_SYMBOLS[piece.color === 'w' ? piece.type.toUpperCase() : piece.type]}
          </span>
        )}
        
        {/* Coordinates */}
        {col === 0 && (
          <span style={{
            position: 'absolute',
            top: 2,
            left: 3,
            fontSize: squareSize * 0.2,
            fontWeight: 'bold',
            color: isLight ? darkColor : lightColor,
          }}>
            {rank}
          </span>
        )}
        {row === 7 && (
          <span style={{
            position: 'absolute',
            bottom: 1,
            right: 3,
            fontSize: squareSize * 0.2,
            fontWeight: 'bold',
            color: isLight ? darkColor : lightColor,
          }}>
            {file}
          </span>
        )}
      </div>
    );
  };
  
  return (
    <div className="flex flex-col items-center gap-3">
      {/* Chess Board */}
      <div 
        style={{ 
          width: size, 
          height: size,
          display: 'grid',
          gridTemplateColumns: `repeat(8, ${squareSize}px)`,
          borderRadius: 4,
          overflow: 'hidden',
          boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
        }}
      >
        {Array(8).fill(0).map((_, row) => (
          Array(8).fill(0).map((_, col) => renderSquare(row, col))
        ))}
      </div>
      
      {/* Current Move Display */}
      <div className="text-center">
        {currentMoveIndex >= 0 ? (
          <div className="flex items-center justify-center gap-2">
            <span className="text-muted-foreground text-sm">
              Move {currentMoveIndex + 1}:
            </span>
            <span className="font-mono font-bold text-lg text-primary">
              {currentMove?.san}
            </span>
          </div>
        ) : (
          <span className="text-muted-foreground text-sm">Starting Position</span>
        )}
      </div>
      
      {/* Navigation Controls */}
      <div className="flex items-center gap-1">
        <Button 
          variant="outline" 
          size="icon" 
          className="h-8 w-8"
          onClick={goToStart}
          disabled={currentMoveIndex === -1}
        >
          <SkipBack className="h-4 w-4" />
        </Button>
        <Button 
          variant="outline" 
          size="icon" 
          className="h-8 w-8"
          onClick={goBack}
          disabled={currentMoveIndex === -1}
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <Button 
          variant="outline" 
          size="icon" 
          className="h-9 w-9"
          onClick={togglePlay}
        >
          {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
        </Button>
        <Button 
          variant="outline" 
          size="icon" 
          className="h-8 w-8"
          onClick={goForward}
          disabled={currentMoveIndex >= moveHistory.length - 1}
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
        <Button 
          variant="outline" 
          size="icon" 
          className="h-8 w-8"
          onClick={goToEnd}
          disabled={currentMoveIndex >= moveHistory.length - 1}
        >
          <SkipForward className="h-4 w-4" />
        </Button>
      </div>
      
      {/* Move List */}
      {showMoveList && moveHistory.length > 0 && (
        <div className="flex flex-wrap gap-1 justify-center max-w-xs">
          {moveHistory.map((move, idx) => {
            const moveNum = Math.floor(idx / 2) + 1;
            const isWhite = idx % 2 === 0;
            const isActive = idx === currentMoveIndex;
            
            return (
              <button
                key={idx}
                onClick={() => setCurrentMoveIndex(idx)}
                className={`px-2 py-0.5 text-xs rounded font-mono transition-colors ${
                  isActive 
                    ? 'bg-primary text-primary-foreground' 
                    : 'bg-muted hover:bg-muted/80'
                }`}
              >
                {isWhite && <span className="text-muted-foreground mr-0.5">{moveNum}.</span>}
                {move.san}
              </button>
            );
          })}
        </div>
      )}
      
      {/* Coaching text for current position */}
      {showCoaching && (
        <div className="text-center text-sm text-muted-foreground max-w-xs">
          {showCoaching}
        </div>
      )}
    </div>
  );
};

export default InteractiveChessBoard;
