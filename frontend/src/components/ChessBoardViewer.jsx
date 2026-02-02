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
  const [position, setPosition] = useState({});
  const [moves, setMoves] = useState([]);
  const [currentMoveIndex, setCurrentMoveIndex] = useState(-1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [boardOrientation, setBoardOrientation] = useState(userColor);
  const [lastMove, setLastMove] = useState(null);
  const [boardKey, setBoardKey] = useState(0);

  // Parse PGN on mount
  useEffect(() => {
    if (!pgn) return;
    
    console.log("Parsing PGN...");
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
        console.error("Failed to parse PGN");
        return;
      }
    }
    
    const history = tempGame.history({ verbose: true });
    console.log("Parsed", history.length, "moves");
    setMoves(history);
    
    // Set initial position
    const startGame = new Chess();
    setPosition(fenToPosition(startGame.fen()));
    setCurrentMoveIndex(-1);
    setLastMove(null);
    setBoardKey(k => k + 1);
  }, [pgn]);

  useEffect(() => {
    setBoardOrientation(userColor === "black" ? "black" : "white");
  }, [userColor]);

  // Convert FEN to position object for react-chessboard
  const fenToPosition = (fen) => {
    const game = new Chess(fen);
    const board = game.board();
    const pos = {};
    
    for (let row = 0; row < 8; row++) {
      for (let col = 0; col < 8; col++) {
        const piece = board[row][col];
        if (piece) {
          const file = String.fromCharCode(97 + col);
          const rank = 8 - row;
          const square = file + rank;
          const color = piece.color === 'w' ? 'w' : 'b';
          const type = piece.type.toUpperCase();
          pos[square] = color + type;
        }
      }
    }
    return pos;
  };

  // Navigate to move
  const goToMove = useCallback((targetIndex) => {
    console.log("Going to move:", targetIndex);
    
    const newGame = new Chess();
    
    for (let i = 0; i <= targetIndex && i < moves.length; i++) {
      const m = moves[i];
      try {
        newGame.move({ from: m.from, to: m.to, promotion: m.promotion });
      } catch (e) {
        console.error("Move error:", i, e);
        break;
      }
    }
    
    const newPosition = fenToPosition(newGame.fen());
    console.log("New position squares:", Object.keys(newPosition).length);
    
    setPosition(newPosition);
    setCurrentMoveIndex(targetIndex);
    setBoardKey(k => k + 1);
    
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
    const startGame = new Chess();
    setPosition(fenToPosition(startGame.fen()));
    setCurrentMoveIndex(-1);
    setLastMove(null);
    setIsPlaying(false);
    setBoardKey(k => k + 1);
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

  const squareStyles = useMemo(() => {
    if (!lastMove) return {};
    return {
      [lastMove.from]: { backgroundColor: "rgba(255, 255, 0, 0.4)" },
      [lastMove.to]: { backgroundColor: "rgba(255, 255, 0, 0.4)" }
    };
  }, [lastMove]);

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

  const currComment = useMemo(() => {
    if (currentMoveIndex < 0 || !commentary.length) return null;
    const moveNum = Math.floor((currentMoveIndex + 2) / 2);
    return commentary.find(c => c.move_number === moveNum);
  }, [currentMoveIndex, commentary]);

  return (
    <div className="space-y-4">
      <div className="relative aspect-square w-full max-w-[500px] mx-auto">
        <Chessboard
          key={boardKey}
          id="game-board"
          position={position}
          boardOrientation={boardOrientation}
          customSquareStyles={squareStyles}
          arePiecesDraggable={false}
          animationDuration={150}
          customBoardStyle={{
            borderRadius: "8px",
            boxShadow: "0 4px 20px rgba(0, 0, 0, 0.3)"
          }}
          customDarkSquareStyle={{ backgroundColor: "#4F46E5" }}
          customLightSquareStyle={{ backgroundColor: "#E0E7FF" }}
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
