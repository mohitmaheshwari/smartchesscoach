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
  commentary = [],
  highlightedMove = null
}) => {
  const [game, setGame] = useState(new Chess());
  const [moves, setMoves] = useState([]);
  const [currentMoveIndex, setCurrentMoveIndex] = useState(-1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [boardOrientation, setBoardOrientation] = useState(userColor);

  // Parse PGN and extract moves
  useEffect(() => {
    try {
      const newGame = new Chess();
      
      // Clean PGN - extract just the moves part
      let cleanPgn = pgn;
      
      // Try to load the full PGN
      try {
        newGame.loadPgn(pgn);
      } catch (e) {
        // If that fails, try to extract moves manually
        const movesMatch = pgn.match(/\d+\.\s*\S+(?:\s+\S+)?/g);
        if (movesMatch) {
          const movesOnly = movesMatch.join(' ');
          try {
            newGame.loadPgn(movesOnly);
          } catch (e2) {
            console.error("Could not parse PGN:", e2);
          }
        }
      }
      
      const history = newGame.history({ verbose: true });
      setMoves(history);
      setGame(new Chess()); // Reset to starting position
      setCurrentMoveIndex(-1);
    } catch (e) {
      console.error("Error parsing PGN:", e);
    }
  }, [pgn]);

  // Update board orientation based on user color
  useEffect(() => {
    setBoardOrientation(userColor === "black" ? "black" : "white");
  }, [userColor]);

  // Auto-play functionality
  useEffect(() => {
    let interval;
    if (isPlaying && currentMoveIndex < moves.length - 1) {
      interval = setInterval(() => {
        goToMove(currentMoveIndex + 1);
      }, 1500);
    } else if (currentMoveIndex >= moves.length - 1) {
      setIsPlaying(false);
    }
    return () => clearInterval(interval);
  }, [isPlaying, currentMoveIndex, moves.length]);

  // Navigate to specific move
  const goToMove = useCallback((index) => {
    const newGame = new Chess();
    
    for (let i = 0; i <= index && i < moves.length; i++) {
      try {
        newGame.move(moves[i]);
      } catch (e) {
        console.error("Error making move:", e);
        break;
      }
    }
    
    setGame(newGame);
    setCurrentMoveIndex(index);
    
    if (onMoveChange) {
      const moveNumber = Math.floor((index + 2) / 2);
      onMoveChange(moveNumber, moves[index]);
    }
  }, [moves, onMoveChange]);

  // Navigation handlers
  const goToStart = () => {
    setGame(new Chess());
    setCurrentMoveIndex(-1);
    setIsPlaying(false);
    if (onMoveChange) onMoveChange(0, null);
  };

  const goToEnd = () => {
    goToMove(moves.length - 1);
    setIsPlaying(false);
  };

  const goBack = () => {
    if (currentMoveIndex > -1) {
      goToMove(currentMoveIndex - 1);
    } else {
      goToStart();
    }
  };

  const goForward = () => {
    if (currentMoveIndex < moves.length - 1) {
      goToMove(currentMoveIndex + 1);
    }
  };

  const togglePlay = () => {
    if (currentMoveIndex >= moves.length - 1) {
      goToStart();
      setTimeout(() => setIsPlaying(true), 100);
    } else {
      setIsPlaying(!isPlaying);
    }
  };

  const flipBoard = () => {
    setBoardOrientation(prev => prev === "white" ? "black" : "white");
  };

  // Get current move commentary
  const currentCommentary = useMemo(() => {
    if (currentMoveIndex < 0 || !commentary.length) return null;
    
    const moveNumber = Math.floor((currentMoveIndex + 2) / 2);
    return commentary.find(c => c.move_number === moveNumber);
  }, [currentMoveIndex, commentary]);

  // Custom square styles for last move highlight
  const customSquareStyles = useMemo(() => {
    if (currentMoveIndex < 0 || !moves[currentMoveIndex]) return {};
    
    const lastMove = moves[currentMoveIndex];
    return {
      [lastMove.from]: { backgroundColor: "rgba(255, 255, 0, 0.4)" },
      [lastMove.to]: { backgroundColor: "rgba(255, 255, 0, 0.4)" }
    };
  }, [currentMoveIndex, moves]);

  // Format move list for display
  const formattedMoves = useMemo(() => {
    const pairs = [];
    for (let i = 0; i < moves.length; i += 2) {
      const moveNum = Math.floor(i / 2) + 1;
      const whiteMove = moves[i]?.san || "";
      const blackMove = moves[i + 1]?.san || "";
      pairs.push({ num: moveNum, white: whiteMove, black: blackMove, whiteIdx: i, blackIdx: i + 1 });
    }
    return pairs;
  }, [moves]);

  return (
    <div className="space-y-4">
      {/* Chess Board */}
      <div className="relative aspect-square w-full max-w-[500px] mx-auto">
        <Chessboard
          position={game.fen()}
          boardOrientation={boardOrientation}
          customSquareStyles={customSquareStyles}
          areArrowsAllowed={true}
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

      {/* Move List */}
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
    </div>
  );
};

export default ChessBoardViewer;
