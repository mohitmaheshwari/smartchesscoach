import { useState, useEffect, useCallback, useMemo, useRef } from "react";
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
  const [fen, setFen] = useState("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  const [moves, setMoves] = useState([]);
  const [currentMoveIndex, setCurrentMoveIndex] = useState(-1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [boardOrientation, setBoardOrientation] = useState(userColor);
  const [lastMove, setLastMove] = useState(null);
  const gameRef = useRef(new Chess());

  // Parse PGN once on mount
  useEffect(() => {
    if (!pgn) return;
    
    console.log("Parsing PGN...");
    const tempGame = new Chess();
    
    try {
      // Try to load full PGN
      tempGame.loadPgn(pgn);
    } catch (e) {
      console.log("Full PGN failed, trying cleanup");
      // Clean and retry
      const lines = pgn.split('\n');
      let movesText = '';
      for (const line of lines) {
        if (!line.startsWith('[') && line.trim()) {
          movesText += ' ' + line;
        }
      }
      movesText = movesText
        .replace(/\{[^}]*\}/g, '')
        .replace(/\([^)]*\)/g, '')
        .replace(/\$\d+/g, '')
        .trim();
      
      try {
        tempGame.loadPgn(movesText);
      } catch (e2) {
        console.error("PGN parse failed:", e2);
        return;
      }
    }
    
    const history = tempGame.history({ verbose: true });
    console.log("Parsed", history.length, "moves");
    setMoves(history);
    
    // Reset to start
    gameRef.current = new Chess();
    setFen(gameRef.current.fen());
    setCurrentMoveIndex(-1);
    setLastMove(null);
  }, [pgn]);

  // Update orientation
  useEffect(() => {
    setBoardOrientation(userColor === "black" ? "black" : "white");
  }, [userColor]);

  // Navigate to move
  const goToMove = useCallback((targetIndex) => {
    console.log("Going to move:", targetIndex);
    
    // Reset game
    const newGame = new Chess();
    
    // Replay moves
    for (let i = 0; i <= targetIndex && i < moves.length; i++) {
      const m = moves[i];
      try {
        newGame.move({ from: m.from, to: m.to, promotion: m.promotion });
      } catch (e) {
        console.error("Move error at", i, m, e);
        break;
      }
    }
    
    // Update state
    const newFen = newGame.fen();
    console.log("New FEN:", newFen);
    gameRef.current = newGame;
    setFen(newFen);
    setCurrentMoveIndex(targetIndex);
    
    if (targetIndex >= 0 && moves[targetIndex]) {
      setLastMove({ from: moves[targetIndex].from, to: moves[targetIndex].to });
    } else {
      setLastMove(null);
    }
    
    if (onMoveChange) {
      onMoveChange(Math.floor((targetIndex + 2) / 2), moves[targetIndex]);
    }
  }, [moves, onMoveChange]);

  // Auto-play
  useEffect(() => {
    if (!isPlaying || currentMoveIndex >= moves.length - 1) {
      if (currentMoveIndex >= moves.length - 1) setIsPlaying(false);
      return;
    }
    
    const timer = setTimeout(() => goToMove(currentMoveIndex + 1), 800);
    return () => clearTimeout(timer);
  }, [isPlaying, currentMoveIndex, moves.length, goToMove]);

  const goToStart = useCallback(() => {
    const newGame = new Chess();
    gameRef.current = newGame;
    setFen(newGame.fen());
    setCurrentMoveIndex(-1);
    setLastMove(null);
    setIsPlaying(false);
  }, []);

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
      setIsPlaying(p => !p);
    }
  }, [currentMoveIndex, moves.length, goToStart]);

  const flipBoard = useCallback(() => {
    setBoardOrientation(o => o === "white" ? "black" : "white");
  }, []);

  // Highlight squares
  const squareStyles = useMemo(() => {
    if (!lastMove) return {};
    return {
      [lastMove.from]: { backgroundColor: "rgba(255, 255, 0, 0.4)" },
      [lastMove.to]: { backgroundColor: "rgba(255, 255, 0, 0.4)" }
    };
  }, [lastMove]);

  // Move list
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

  // Current commentary
  const currComment = useMemo(() => {
    if (currentMoveIndex < 0 || !commentary.length) return null;
    const moveNum = Math.floor((currentMoveIndex + 2) / 2);
    return commentary.find(c => c.move_number === moveNum);
  }, [currentMoveIndex, commentary]);

  return (
    <div className="space-y-4">
      {/* Board */}
      <div className="relative aspect-square w-full max-w-[500px] mx-auto">
        <Chessboard
          id="analysis-board"
          position={fen}
          boardOrientation={boardOrientation}
          customSquareStyles={squareStyles}
          arePiecesDraggable={false}
          animationDuration={200}
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
        <Button variant="outline" size="icon" onClick={goToStart} disabled={currentMoveIndex < 0}>
          <ChevronsLeft className="w-4 h-4" />
        </Button>
        <Button variant="outline" size="icon" onClick={goBack} disabled={currentMoveIndex < 0}>
          <ChevronLeft className="w-4 h-4" />
        </Button>
        <Button variant="default" size="icon" onClick={togglePlay} disabled={moves.length === 0}>
          {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
        </Button>
        <Button variant="outline" size="icon" onClick={goForward} disabled={currentMoveIndex >= moves.length - 1}>
          <ChevronRight className="w-4 h-4" />
        </Button>
        <Button variant="outline" size="icon" onClick={goToEnd} disabled={currentMoveIndex >= moves.length - 1}>
          <ChevronsRight className="w-4 h-4" />
        </Button>
        <Button variant="ghost" size="icon" onClick={flipBoard}>
          <RotateCcw className="w-4 h-4" />
        </Button>
      </div>

      {/* Slider */}
      {moves.length > 0 && (
        <div className="px-4">
          <Slider
            value={[currentMoveIndex + 1]}
            min={0}
            max={moves.length}
            step={1}
            onValueChange={(v) => {
              const idx = v[0] - 1;
              if (idx < 0) goToStart();
              else goToMove(idx);
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
            {movePairs.map((p) => (
              <div key={p.num} className="contents">
                <span className="text-muted-foreground">{p.num}.</span>
                <button
                  className={`text-left px-1 rounded hover:bg-primary/20 ${currentMoveIndex === p.wIdx ? "bg-primary/30 font-bold" : ""}`}
                  onClick={() => goToMove(p.wIdx)}
                >
                  {p.white}
                </button>
                <button
                  className={`text-left px-1 rounded hover:bg-primary/20 ${currentMoveIndex === p.bIdx ? "bg-primary/30 font-bold" : ""}`}
                  onClick={() => p.black && goToMove(p.bIdx)}
                  disabled={!p.black}
                >
                  {p.black}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Commentary */}
      {currComment && (
        <div className={`p-3 rounded-lg border-l-4 ${
          currComment.evaluation === "blunder" ? "border-l-red-500 bg-red-500/10" :
          currComment.evaluation === "mistake" ? "border-l-orange-500 bg-orange-500/10" :
          currComment.evaluation === "inaccuracy" ? "border-l-yellow-500 bg-yellow-500/10" :
          currComment.evaluation === "good" ? "border-l-blue-500 bg-blue-500/10" :
          currComment.evaluation === "excellent" ? "border-l-emerald-500 bg-emerald-500/10" :
          currComment.evaluation === "brilliant" ? "border-l-cyan-500 bg-cyan-500/10" :
          "border-l-muted-foreground bg-muted/30"
        }`}>
          <p className="text-sm">{currComment.comment}</p>
        </div>
      )}
    </div>
  );
};

export default ChessBoardViewer;
