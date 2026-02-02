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

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

const ChessBoardViewer = ({ 
  pgn, 
  userColor = "white",
  onMoveChange,
  commentary = []
}) => {
  const [currentFen, setCurrentFen] = useState(START_FEN);
  const [moves, setMoves] = useState([]);
  const [currentMoveIndex, setCurrentMoveIndex] = useState(-1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [boardOrientation, setBoardOrientation] = useState(userColor);
  const [lastMoveSquares, setLastMoveSquares] = useState({});

  // Parse PGN on mount
  useEffect(() => {
    if (!pgn) {
      setMoves([]);
      setCurrentFen(START_FEN);
      setCurrentMoveIndex(-1);
      return;
    }
    
    console.log("ChessBoardViewer: Parsing PGN...");
    const tempGame = new Chess();
    
    try {
      tempGame.loadPgn(pgn);
    } catch (e) {
      console.log("Full PGN failed, cleaning...");
      const lines = pgn.split('\n');
      let movesText = '';
      for (const line of lines) {
        if (!line.startsWith('[') && line.trim()) {
          movesText += ' ' + line;
        }
      }
      movesText = movesText.replace(/\{[^}]*\}/g, '').replace(/\([^)]*\)/g, '').trim();
      try {
        tempGame.loadPgn(movesText);
      } catch (e2) {
        console.error("Failed to parse PGN:", e2);
        return;
      }
    }
    
    const history = tempGame.history({ verbose: true });
    console.log("ChessBoardViewer: Parsed", history.length, "moves");
    setMoves(history);
    setCurrentFen(START_FEN);
    setCurrentMoveIndex(-1);
    setLastMoveSquares({});
  }, [pgn]);

  // Update orientation
  useEffect(() => {
    setBoardOrientation(userColor === "black" ? "black" : "white");
  }, [userColor]);

  // Calculate FEN for a given move index
  const calculateFen = useCallback((targetIndex) => {
    const tempGame = new Chess();
    
    for (let i = 0; i <= targetIndex && i < moves.length; i++) {
      const m = moves[i];
      try {
        tempGame.move({ from: m.from, to: m.to, promotion: m.promotion });
      } catch (e) {
        console.error("Move error at index", i, ":", e);
        break;
      }
    }
    
    return tempGame.fen();
  }, [moves]);

  // Navigate to move
  const goToMove = useCallback((targetIndex) => {
    if (targetIndex < -1) targetIndex = -1;
    if (targetIndex >= moves.length) targetIndex = moves.length - 1;
    
    console.log("ChessBoardViewer: Going to move", targetIndex);
    
    let newFen;
    if (targetIndex < 0) {
      newFen = START_FEN;
    } else {
      newFen = calculateFen(targetIndex);
    }
    
    console.log("ChessBoardViewer: New FEN:", newFen.split(' ')[0]);
    
    // Update state
    setCurrentFen(newFen);
    setCurrentMoveIndex(targetIndex);
    
    // Highlight last move
    if (targetIndex >= 0 && moves[targetIndex]) {
      setLastMoveSquares({
        [moves[targetIndex].from]: { backgroundColor: "rgba(255, 255, 0, 0.5)" },
        [moves[targetIndex].to]: { backgroundColor: "rgba(255, 255, 0, 0.5)" }
      });
    } else {
      setLastMoveSquares({});
    }
    
    // Callback
    if (onMoveChange) {
      const moveNum = Math.floor((targetIndex + 2) / 2);
      onMoveChange(moveNum, targetIndex >= 0 ? moves[targetIndex] : null);
    }
  }, [moves, calculateFen, onMoveChange]);

  // Auto-play
  useEffect(() => {
    if (!isPlaying) return;
    if (currentMoveIndex >= moves.length - 1) {
      setIsPlaying(false);
      return;
    }
    
    const timer = setTimeout(() => {
      goToMove(currentMoveIndex + 1);
    }, 800);
    
    return () => clearTimeout(timer);
  }, [isPlaying, currentMoveIndex, moves.length, goToMove]);

  // Navigation functions
  const goToStart = useCallback(() => {
    setCurrentFen(START_FEN);
    setCurrentMoveIndex(-1);
    setLastMoveSquares({});
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

  // Format move pairs for display
  const movePairs = useMemo(() => {
    const pairs = [];
    for (let i = 0; i < moves.length; i += 2) {
      pairs.push({
        num: Math.floor(i / 2) + 1,
        white: moves[i] ? moves[i].san : "",
        black: moves[i + 1] ? moves[i + 1].san : "",
        wIdx: i,
        bIdx: i + 1
      });
    }
    return pairs;
  }, [moves]);

  // Get commentary for current move
  const currentComment = useMemo(() => {
    if (currentMoveIndex < 0 || !commentary || commentary.length === 0) return null;
    const moveNum = Math.floor((currentMoveIndex + 2) / 2);
    return commentary.find(c => c.move_number === moveNum);
  }, [currentMoveIndex, commentary]);

  return (
    <div className="space-y-4">
      {/* Chess Board */}
      <div className="relative aspect-square w-full max-w-[500px] mx-auto">
        <Chessboard
          key={currentFen}
          position={currentFen}
          boardOrientation={boardOrientation}
          customSquareStyles={lastMoveSquares}
          arePiecesDraggable={false}
          animationDuration={0}
          customBoardStyle={{
            borderRadius: "8px",
            boxShadow: "0 4px 20px rgba(0, 0, 0, 0.3)"
          }}
          customDarkSquareStyle={{ backgroundColor: "#4F46E5" }}
          customLightSquareStyle={{ backgroundColor: "#E0E7FF" }}
        />
      </div>

      {/* Navigation Controls */}
      <div className="flex items-center justify-center gap-2">
        <Button 
          variant="outline" 
          size="icon" 
          onClick={goToStart} 
          disabled={currentMoveIndex < 0}
        >
          <ChevronsLeft className="w-4 h-4" />
        </Button>
        <Button 
          variant="outline" 
          size="icon" 
          onClick={goBack} 
          disabled={currentMoveIndex < 0}
        >
          <ChevronLeft className="w-4 h-4" />
        </Button>
        <Button 
          variant="default" 
          size="icon" 
          onClick={togglePlay} 
          disabled={moves.length === 0}
        >
          {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
        </Button>
        <Button 
          variant="outline" 
          size="icon" 
          onClick={goForward} 
          disabled={currentMoveIndex >= moves.length - 1}
        >
          <ChevronRight className="w-4 h-4" />
        </Button>
        <Button 
          variant="outline" 
          size="icon" 
          onClick={goToEnd} 
          disabled={currentMoveIndex >= moves.length - 1}
        >
          <ChevronsRight className="w-4 h-4" />
        </Button>
        <Button 
          variant="ghost" 
          size="icon" 
          onClick={flipBoard}
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
            onValueChange={(values) => {
              const idx = values[0] - 1;
              if (idx < 0) {
                goToStart();
              } else {
                goToMove(idx);
              }
            }}
          />
          <p className="text-center text-sm text-muted-foreground mt-2">
            Move {currentMoveIndex + 1} of {moves.length}
          </p>
        </div>
      )}

      {/* Move List */}
      {movePairs.length > 0 && (
        <div className="bg-muted/50 rounded-lg p-3 max-h-48 overflow-y-auto">
          <div className="grid grid-cols-[auto_1fr_1fr] gap-x-3 gap-y-1 text-sm font-mono">
            {movePairs.map((pair) => (
              <div key={pair.num} className="contents">
                <span className="text-muted-foreground">{pair.num}.</span>
                <button
                  type="button"
                  className={`text-left px-1 rounded hover:bg-primary/20 transition-colors ${
                    currentMoveIndex === pair.wIdx ? "bg-primary/30 font-bold" : ""
                  }`}
                  onClick={() => goToMove(pair.wIdx)}
                >
                  {pair.white}
                </button>
                <button
                  type="button"
                  className={`text-left px-1 rounded hover:bg-primary/20 transition-colors ${
                    currentMoveIndex === pair.bIdx ? "bg-primary/30 font-bold" : ""
                  }`}
                  onClick={() => pair.black && goToMove(pair.bIdx)}
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
      {currentComment && (
        <div className={`p-3 rounded-lg border-l-4 ${
          currentComment.evaluation === "blunder" ? "border-l-red-500 bg-red-500/10" :
          currentComment.evaluation === "mistake" ? "border-l-orange-500 bg-orange-500/10" :
          currentComment.evaluation === "inaccuracy" ? "border-l-yellow-500 bg-yellow-500/10" :
          currentComment.evaluation === "good" ? "border-l-blue-500 bg-blue-500/10" :
          currentComment.evaluation === "excellent" ? "border-l-emerald-500 bg-emerald-500/10" :
          currentComment.evaluation === "brilliant" ? "border-l-cyan-500 bg-cyan-500/10" :
          "border-l-muted-foreground bg-muted/30"
        }`}>
          <p className="text-sm">{currentComment.comment}</p>
        </div>
      )}
    </div>
  );
};

export default ChessBoardViewer;
