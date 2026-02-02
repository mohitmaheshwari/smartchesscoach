import { useState, useEffect, useCallback, useMemo } from "react";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { 
  ChevronLeft, 
  ChevronRight, 
  ChevronsLeft, 
  ChevronsRight,
  Play,
  Pause,
  RotateCcw
} from "lucide-react";

const ChessBoardViewer = ({ 
  pgn, 
  userColor = "white",
  onMoveChange,
  commentary = []
}) => {
  const [currentPosition, setCurrentPosition] = useState("start");
  const [moves, setMoves] = useState([]);
  const [currentMoveIndex, setCurrentMoveIndex] = useState(-1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [boardOrientation, setBoardOrientation] = useState(userColor);
  const [lastMove, setLastMove] = useState(null);

  // Parse PGN and extract moves on mount
  useEffect(() => {
    if (!pgn) return;
    
    try {
      const tempGame = new Chess();
      
      // Try to load full PGN first
      let loaded = false;
      try {
        tempGame.loadPgn(pgn);
        loaded = true;
      } catch (e) {
        console.log("Full PGN load failed, trying to extract moves");
      }
      
      // If that fails, extract moves manually
      if (!loaded) {
        // Find the moves section (after headers)
        const lines = pgn.split('\n');
        let movesText = '';
        let inMoves = false;
        
        for (const line of lines) {
          if (line.startsWith('[')) continue;
          if (line.trim() === '') {
            inMoves = true;
            continue;
          }
          if (inMoves || !line.startsWith('[')) {
            movesText += ' ' + line;
          }
        }
        
        // Clean up the moves text
        movesText = movesText
          .replace(/\{[^}]*\}/g, '') // Remove comments
          .replace(/\([^)]*\)/g, '') // Remove variations
          .replace(/\$\d+/g, '') // Remove NAGs
          .replace(/\d+\.\.\./g, '') // Remove continuation dots
          .trim();
        
        if (movesText) {
          try {
            tempGame.loadPgn(movesText);
            loaded = true;
          } catch (e2) {
            console.log("Cleaned PGN load failed:", e2);
          }
        }
      }
      
      // Get the move history
      const history = tempGame.history({ verbose: true });
      console.log("Parsed moves:", history.length);
      setMoves(history);
      
      // Reset to starting position
      setCurrentPosition("start");
      setCurrentMoveIndex(-1);
      setLastMove(null);
      
    } catch (e) {
      console.error("Error parsing PGN:", e);
    }
  }, [pgn]);

  // Update board orientation
  useEffect(() => {
    setBoardOrientation(userColor === "black" ? "black" : "white");
  }, [userColor]);

  // Navigate to a specific move index
  const goToMove = useCallback((targetIndex) => {
    if (targetIndex < -1 || targetIndex >= moves.length) return;
    
    const tempGame = new Chess();
    
    // Replay moves up to target index
    for (let i = 0; i <= targetIndex; i++) {
      const move = moves[i];
      if (move) {
        try {
          tempGame.move({
            from: move.from,
            to: move.to,
            promotion: move.promotion
          });
        } catch (e) {
          console.error("Error replaying move:", i, move, e);
          break;
        }
      }
    }
    
    setCurrentPosition(tempGame.fen());
    setCurrentMoveIndex(targetIndex);
    
    // Set last move highlight
    if (targetIndex >= 0 && moves[targetIndex]) {
      setLastMove({
        from: moves[targetIndex].from,
        to: moves[targetIndex].to
      });
    } else {
      setLastMove(null);
    }
    
    // Callback
    if (onMoveChange) {
      const moveNumber = Math.floor((targetIndex + 2) / 2);
      onMoveChange(moveNumber, moves[targetIndex]);
    }
  }, [moves, onMoveChange]);

  // Auto-play functionality
  useEffect(() => {
    if (!isPlaying) return;
    
    if (currentMoveIndex >= moves.length - 1) {
      setIsPlaying(false);
      return;
    }
    
    const timer = setTimeout(() => {
      goToMove(currentMoveIndex + 1);
    }, 1000);
    
    return () => clearTimeout(timer);
  }, [isPlaying, currentMoveIndex, moves.length, goToMove]);

  // Navigation handlers
  const goToStart = useCallback(() => {
    setCurrentPosition("start");
    setCurrentMoveIndex(-1);
    setLastMove(null);
    setIsPlaying(false);
    if (onMoveChange) onMoveChange(0, null);
  }, [onMoveChange]);

  const goToEnd = useCallback(() => {
    goToMove(moves.length - 1);
    setIsPlaying(false);
  }, [goToMove, moves.length]);

  const goBack = useCallback(() => {
    if (currentMoveIndex <= 0) {
      goToStart();
    } else {
      goToMove(currentMoveIndex - 1);
    }
  }, [currentMoveIndex, goToMove, goToStart]);

  const goForward = useCallback(() => {
    if (currentMoveIndex < moves.length - 1) {
      goToMove(currentMoveIndex + 1);
    }
  }, [currentMoveIndex, moves.length, goToMove]);

  const togglePlay = useCallback(() => {
    if (currentMoveIndex >= moves.length - 1) {
      goToStart();
      setTimeout(() => setIsPlaying(true), 100);
    } else {
      setIsPlaying(prev => !prev);
    }
  }, [currentMoveIndex, moves.length, goToStart]);

  const flipBoard = useCallback(() => {
    setBoardOrientation(prev => prev === "white" ? "black" : "white");
  }, []);

  // Square styles for last move highlight
  const customSquareStyles = useMemo(() => {
    if (!lastMove) return {};
    return {
      [lastMove.from]: { backgroundColor: "rgba(255, 255, 0, 0.4)" },
      [lastMove.to]: { backgroundColor: "rgba(255, 255, 0, 0.4)" }
    };
  }, [lastMove]);

  // Format move list for display
  const formattedMoves = useMemo(() => {
    const pairs = [];
    for (let i = 0; i < moves.length; i += 2) {
      const moveNum = Math.floor(i / 2) + 1;
      const whiteMove = moves[i] ? moves[i].san : "";
      const blackMove = moves[i + 1] ? moves[i + 1].san : "";
      pairs.push({ 
        num: moveNum, 
        white: whiteMove, 
        black: blackMove, 
        whiteIdx: i, 
        blackIdx: i + 1 
      });
    }
    return pairs;
  }, [moves]);

  // Get current move commentary
  const currentCommentary = useMemo(() => {
    if (currentMoveIndex < 0 || !commentary || commentary.length === 0) return null;
    const moveNumber = Math.floor((currentMoveIndex + 2) / 2);
    return commentary.find(c => c.move_number === moveNumber);
  }, [currentMoveIndex, commentary]);

  return (
    <div className="space-y-4">
      {/* Chess Board */}
      <div className="relative aspect-square w-full max-w-[500px] mx-auto">
        <Chessboard
          position={currentPosition}
          boardOrientation={boardOrientation}
          customSquareStyles={customSquareStyles}
          arePiecesDraggable={false}
          customBoardStyle={{
            borderRadius: "8px",
            boxShadow: "0 4px 20px rgba(0, 0, 0, 0.3)"
          }}
          customDarkSquareStyle={{ backgroundColor: "#4F46E5" }}
          customLightSquareStyle={{ backgroundColor: "#E0E7FF" }}
        />
      </div>

      {/* Controls */}
      <div className="flex items-center justify-center gap-2">
        <Button 
          variant="outline" 
          size="icon" 
          onClick={goToStart}
          disabled={currentMoveIndex < 0}
          data-testid="board-start-btn"
        >
          <ChevronsLeft className="w-4 h-4" />
        </Button>
        <Button 
          variant="outline" 
          size="icon" 
          onClick={goBack}
          disabled={currentMoveIndex < 0}
          data-testid="board-back-btn"
        >
          <ChevronLeft className="w-4 h-4" />
        </Button>
        <Button 
          variant="default" 
          size="icon" 
          onClick={togglePlay}
          disabled={moves.length === 0}
          data-testid="board-play-btn"
        >
          {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
        </Button>
        <Button 
          variant="outline" 
          size="icon" 
          onClick={goForward}
          disabled={currentMoveIndex >= moves.length - 1}
          data-testid="board-forward-btn"
        >
          <ChevronRight className="w-4 h-4" />
        </Button>
        <Button 
          variant="outline" 
          size="icon" 
          onClick={goToEnd}
          disabled={currentMoveIndex >= moves.length - 1}
          data-testid="board-end-btn"
        >
          <ChevronsRight className="w-4 h-4" />
        </Button>
        <Button 
          variant="ghost" 
          size="icon" 
          onClick={flipBoard}
          data-testid="board-flip-btn"
        >
          <RotateCcw className="w-4 h-4" />
        </Button>
      </div>

      {/* Move Slider */}
      {moves.length > 0 && (
        <div className="px-4">
          <Slider
            value={[currentMoveIndex + 1]}
            min={0}
            max={moves.length}
            step={1}
            onValueChange={(value) => {
              const idx = value[0] - 1;
              if (idx < 0) {
                goToStart();
              } else {
                goToMove(idx);
              }
            }}
            data-testid="move-slider"
          />
          <p className="text-center text-sm text-muted-foreground mt-2">
            Move {currentMoveIndex + 1} of {moves.length}
          </p>
        </div>
      )}

      {/* Move List */}
      {formattedMoves.length > 0 && (
        <div className="bg-muted/50 rounded-lg p-3 max-h-48 overflow-y-auto">
          <div className="grid grid-cols-[auto_1fr_1fr] gap-x-3 gap-y-1 text-sm font-mono">
            {formattedMoves.map((pair) => (
              <div key={pair.num} className="contents">
                <span className="text-muted-foreground">{pair.num}.</span>
                <button
                  className={`text-left px-1 rounded hover:bg-primary/20 transition-colors ${
                    currentMoveIndex === pair.whiteIdx ? "bg-primary/30 font-bold" : ""
                  }`}
                  onClick={() => goToMove(pair.whiteIdx)}
                >
                  {pair.white}
                </button>
                <button
                  className={`text-left px-1 rounded hover:bg-primary/20 transition-colors ${
                    currentMoveIndex === pair.blackIdx ? "bg-primary/30 font-bold" : ""
                  }`}
                  onClick={() => pair.black && goToMove(pair.blackIdx)}
                  disabled={!pair.black}
                >
                  {pair.black}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Current Move Commentary */}
      {currentCommentary && (
        <div className={`p-3 rounded-lg border-l-4 ${
          currentCommentary.evaluation === "blunder" ? "border-l-red-500 bg-red-500/10" :
          currentCommentary.evaluation === "mistake" ? "border-l-orange-500 bg-orange-500/10" :
          currentCommentary.evaluation === "inaccuracy" ? "border-l-yellow-500 bg-yellow-500/10" :
          currentCommentary.evaluation === "good" ? "border-l-blue-500 bg-blue-500/10" :
          currentCommentary.evaluation === "excellent" ? "border-l-emerald-500 bg-emerald-500/10" :
          currentCommentary.evaluation === "brilliant" ? "border-l-cyan-500 bg-cyan-500/10" :
          "border-l-muted-foreground bg-muted/30"
        }`}>
          <p className="text-sm">{currentCommentary.comment}</p>
        </div>
      )}

      {/* Debug info */}
      {moves.length === 0 && (
        <p className="text-center text-sm text-muted-foreground">
          No moves loaded. PGN may be invalid.
        </p>
      )}
    </div>
  );
};

export default ChessBoardViewer;
