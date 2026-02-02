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

// Convert FEN to position object that react-chessboard expects
const fenToPositionObject = (fen) => {
  const position = {};
  const parts = fen.split(' ');
  const rows = parts[0].split('/');
  
  for (let row = 0; row < 8; row++) {
    let col = 0;
    for (const char of rows[row]) {
      if (char >= '1' && char <= '8') {
        col += parseInt(char);
      } else {
        const file = String.fromCharCode(97 + col);
        const rank = 8 - row;
        const square = file + rank;
        const color = char === char.toUpperCase() ? 'w' : 'b';
        const piece = char.toUpperCase();
        position[square] = color + piece;
        col++;
      }
    }
  }
  
  return position;
};

const ChessBoardViewer = ({ 
  pgn, 
  userColor = "white",
  onMoveChange,
  commentary = []
}) => {
  const [positionObject, setPositionObject] = useState(() => fenToPositionObject(START_FEN));
  const [moves, setMoves] = useState([]);
  const [currentMoveIndex, setCurrentMoveIndex] = useState(-1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [boardOrientation, setBoardOrientation] = useState(userColor);
  const [lastMoveSquares, setLastMoveSquares] = useState({});
  const [allFens, setAllFens] = useState([START_FEN]);

  // Parse PGN and pre-calculate all positions
  useEffect(() => {
    if (!pgn) {
      setMoves([]);
      setAllFens([START_FEN]);
      setPositionObject(fenToPositionObject(START_FEN));
      setCurrentMoveIndex(-1);
      return;
    }
    
    console.log("Parsing PGN...");
    const tempGame = new Chess();
    
    try {
      tempGame.loadPgn(pgn);
    } catch (e) {
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
        console.error("Failed to parse PGN");
        return;
      }
    }
    
    const history = tempGame.history({ verbose: true });
    console.log("Parsed", history.length, "moves");
    
    // Pre-calculate all FEN positions
    const fens = [START_FEN];
    const calcGame = new Chess();
    
    for (let i = 0; i < history.length; i++) {
      const m = history[i];
      calcGame.move({ from: m.from, to: m.to, promotion: m.promotion });
      fens.push(calcGame.fen());
    }
    
    console.log("Calculated", fens.length, "FENs");
    console.log("Final FEN:", fens[fens.length - 1]);
    
    setAllFens(fens);
    setMoves(history);
    setPositionObject(fenToPositionObject(START_FEN));
    setCurrentMoveIndex(-1);
    setLastMoveSquares({});
  }, [pgn]);

  useEffect(() => {
    setBoardOrientation(userColor === "black" ? "black" : "white");
  }, [userColor]);

  // Navigate to move
  const goToMove = useCallback((targetIndex) => {
    const clampedIndex = Math.max(-1, Math.min(targetIndex, moves.length - 1));
    const posIndex = clampedIndex + 1;
    const fen = allFens[posIndex] || START_FEN;
    
    console.log("goToMove:", clampedIndex, "FEN:", fen);
    
    const newPosition = fenToPositionObject(fen);
    console.log("Position object keys:", Object.keys(newPosition).length);
    
    setPositionObject(newPosition);
    setCurrentMoveIndex(clampedIndex);
    
    if (clampedIndex >= 0 && moves[clampedIndex]) {
      setLastMoveSquares({
        [moves[clampedIndex].from]: { backgroundColor: "rgba(255, 255, 0, 0.5)" },
        [moves[clampedIndex].to]: { backgroundColor: "rgba(255, 255, 0, 0.5)" }
      });
    } else {
      setLastMoveSquares({});
    }
    
    if (onMoveChange) {
      onMoveChange(Math.floor((clampedIndex + 2) / 2), clampedIndex >= 0 ? moves[clampedIndex] : null);
    }
  }, [moves, allFens, onMoveChange]);

  // Auto-play
  useEffect(() => {
    if (!isPlaying || currentMoveIndex >= moves.length - 1) {
      if (currentMoveIndex >= moves.length - 1) setIsPlaying(false);
      return;
    }
    const timer = setTimeout(() => goToMove(currentMoveIndex + 1), 600);
    return () => clearTimeout(timer);
  }, [isPlaying, currentMoveIndex, moves.length, goToMove]);

  const goToStart = useCallback(() => {
    setPositionObject(fenToPositionObject(START_FEN));
    setCurrentMoveIndex(-1);
    setLastMoveSquares({});
    setIsPlaying(false);
  }, []);

  const goToEnd = useCallback(() => {
    goToMove(moves.length - 1);
    setIsPlaying(false);
  }, [goToMove, moves.length]);

  const goBack = useCallback(() => {
    if (currentMoveIndex <= 0) goToStart();
    else goToMove(currentMoveIndex - 1);
  }, [currentMoveIndex, goToMove, goToStart]);

  const goForward = useCallback(() => {
    if (currentMoveIndex < moves.length - 1) goToMove(currentMoveIndex + 1);
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
    setBoardOrientation(p => p === "white" ? "black" : "white");
  }, []);

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

  const currentComment = useMemo(() => {
    if (currentMoveIndex < 0 || !commentary || !commentary.length) return null;
    const moveNum = Math.floor((currentMoveIndex + 2) / 2);
    return commentary.find(c => c.move_number === moveNum);
  }, [currentMoveIndex, commentary]);

  // Create a unique key that changes with every position change
  const boardKey = useMemo(() => {
    return JSON.stringify(positionObject);
  }, [positionObject]);

  return (
    <div className="space-y-4">
      <div className="relative aspect-square w-full max-w-[500px] mx-auto">
        <Chessboard
          key={boardKey}
          position={positionObject}
          boardOrientation={boardOrientation}
          customSquareStyles={lastMoveSquares}
          arePiecesDraggable={false}
          animationDuration={0}
        />
      </div>

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

      {moves.length > 0 && (
        <div className="px-4">
          <Slider
            value={[currentMoveIndex + 1]}
            min={0}
            max={moves.length}
            step={1}
            onValueChange={(v) => v[0] <= 0 ? goToStart() : goToMove(v[0] - 1)}
          />
          <p className="text-center text-sm text-muted-foreground mt-2">
            Move {currentMoveIndex + 1} of {moves.length}
          </p>
        </div>
      )}

      {movePairs.length > 0 && (
        <div className="bg-muted/50 rounded-lg p-3 max-h-48 overflow-y-auto">
          <div className="grid grid-cols-[auto_1fr_1fr] gap-x-3 gap-y-1 text-sm font-mono">
            {movePairs.map((p) => (
              <div key={p.num} className="contents">
                <span className="text-muted-foreground">{p.num}.</span>
                <button
                  type="button"
                  className={`text-left px-1 rounded hover:bg-primary/20 ${currentMoveIndex === p.wIdx ? "bg-primary/30 font-bold" : ""}`}
                  onClick={() => goToMove(p.wIdx)}
                >
                  {p.white}
                </button>
                <button
                  type="button"
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
