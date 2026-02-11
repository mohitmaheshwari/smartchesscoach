import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Chessboard } from "react-chessboard";
import { Chess } from "chess.js";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import {
  Brain,
  CheckCircle2,
  XCircle,
  ChevronRight,
  RotateCcw,
  Trophy,
  Target,
  Lightbulb,
  Loader2
} from "lucide-react";

/**
 * DrillMode - "What would you play here?" training from user's own games
 * 
 * Props:
 * - pattern: string - Behavioral pattern to train (e.g., "attacks_before_checking_threats")
 * - state: string - Optional game state filter ("winning", "equal", "losing")
 * - onComplete: () => void - Called when drill session is complete
 * - onClose: () => void - Close the drill mode
 */
const DrillMode = ({ 
  pattern = null, 
  state = null, 
  onComplete,
  onClose,
  patternLabel = "this pattern"
}) => {
  const navigate = useNavigate();
  const [positions, setPositions] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [userMove, setUserMove] = useState(null);
  const [showResult, setShowResult] = useState(false);
  const [isCorrect, setIsCorrect] = useState(false);
  const [score, setScore] = useState({ correct: 0, total: 0 });
  const [chess] = useState(new Chess());
  const [boardPosition, setBoardPosition] = useState("start");

  // Fetch drill positions
  useEffect(() => {
    const fetchPositions = async () => {
      try {
        const response = await fetch(`${API}/drill/positions`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ 
            pattern, 
            state, 
            limit: 5 
          })
        });
        
        if (!response.ok) throw new Error('Failed to fetch positions');
        
        const data = await response.json();
        setPositions(data.positions || []);
        
        // Set initial board position
        if (data.positions?.length > 0 && data.positions[0].fen_before) {
          setBoardPosition(data.positions[0].fen_before);
        }
        
        if (data.positions?.length === 0) {
          toast.error("No positions found for training");
        }
      } catch (err) {
        console.error("Drill fetch error:", err);
        toast.error("Failed to load training positions");
      } finally {
        setLoading(false);
      }
    };

    fetchPositions();
  }, [pattern, state]);

  // Get current position
  const currentPosition = positions[currentIndex];

  // Load position into chess.js and update board
  useEffect(() => {
    if (currentPosition?.fen_before) {
      try {
        chess.load(currentPosition.fen_before);
        setBoardPosition(currentPosition.fen_before);
      } catch (e) {
        console.error("Failed to load FEN:", e);
      }
    }
  }, [currentPosition, chess]);

  // Handle piece drop (user's move attempt)
  const onDrop = useCallback((sourceSquare, targetSquare) => {
    if (showResult) return false;
    
    // Try the move
    try {
      const move = chess.move({
        from: sourceSquare,
        to: targetSquare,
        promotion: 'q' // Auto-promote to queen for simplicity
      });
      
      if (!move) return false;
      
      // Check if it matches the best move
      const bestMove = currentPosition.best_move;
      const moveNotation = move.san;
      
      // Normalize for comparison (remove check/mate symbols)
      const normalizeMove = (m) => m?.replace(/[+#]/g, '').toLowerCase();
      const isMatch = normalizeMove(moveNotation) === normalizeMove(bestMove);
      
      setUserMove(moveNotation);
      setIsCorrect(isMatch);
      setShowResult(true);
      setScore(prev => ({
        correct: prev.correct + (isMatch ? 1 : 0),
        total: prev.total + 1
      }));
      
      // Reset the board to show the position before the move
      chess.load(currentPosition.fen_before);
      setBoardPosition(currentPosition.fen_before);
      
      return false; // Don't update board visually - we'll show result
    } catch (e) {
      return false;
    }
  }, [chess, currentPosition, showResult]);

  // Move to next position
  const nextPosition = () => {
    if (currentIndex < positions.length - 1) {
      setCurrentIndex(prev => prev + 1);
      setShowResult(false);
      setUserMove(null);
      setIsCorrect(false);
    } else {
      // Drill complete
      if (onComplete) onComplete();
      toast.success(`Drill complete! Score: ${score.correct}/${score.total}`);
    }
  };

  // Retry current position
  const retryPosition = () => {
    setShowResult(false);
    setUserMove(null);
    setIsCorrect(false);
    if (currentPosition?.fen_before) {
      chess.load(currentPosition.fen_before);
      setBoardPosition(currentPosition.fen_before);
    }
  };

  // Go to full game analysis
  const goToGame = () => {
    if (currentPosition) {
      navigate(`/games/dashboard/${currentPosition.game_id}?move=${currentPosition.move_number}`);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (positions.length === 0) {
    return (
      <Card className="border-dashed">
        <CardContent className="py-12 text-center">
          <Target className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
          <h3 className="text-lg font-medium mb-2">No Positions Available</h3>
          <p className="text-muted-foreground text-sm mb-4">
            We couldn't find enough training positions for this pattern.
            Play and analyze more games to unlock training!
          </p>
          <Button variant="outline" onClick={onClose}>
            Go Back
          </Button>
        </CardContent>
      </Card>
    );
  }

  const progress = ((currentIndex + (showResult ? 1 : 0)) / positions.length) * 100;

  return (
    <div className="space-y-4" data-testid="drill-mode">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold flex items-center gap-2">
            <Brain className="w-5 h-5 text-primary" />
            Pattern Drill
          </h2>
          <p className="text-sm text-muted-foreground">
            Train: {patternLabel}
          </p>
        </div>
        <div className="text-right">
          <p className="text-sm font-medium">
            {currentIndex + 1} / {positions.length}
          </p>
          <p className="text-xs text-muted-foreground">
            Score: {score.correct}/{score.total}
          </p>
        </div>
      </div>

      {/* Progress */}
      <Progress value={progress} className="h-2" />

      {/* Main Content */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Board */}
        <div className="flex flex-col items-center">
          <div className="w-full max-w-[320px]">
            <Chessboard
              position={boardPosition}
              boardWidth={320}
              onPieceDrop={onDrop}
              arePiecesDraggable={!showResult}
              boardOrientation={currentPosition?.user_color || "white"}
              customBoardStyle={{
                borderRadius: '8px',
                boxShadow: '0 4px 20px rgba(0,0,0,0.3)'
              }}
            />
          </div>
          
          {/* Context */}
          <div className="mt-3 text-center">
            <p className="text-sm text-muted-foreground">
              vs {currentPosition?.opponent || "Opponent"} • Move {currentPosition?.move_number}
            </p>
            <p className="text-sm">
              You had <span className={`font-bold ${
                currentPosition?.eval_before > 1 ? 'text-green-500' :
                currentPosition?.eval_before < -1 ? 'text-red-500' :
                'text-yellow-500'
              }`}>
                {currentPosition?.eval_before >= 0 ? '+' : ''}{currentPosition?.eval_before?.toFixed(1)}
              </span>
            </p>
          </div>
        </div>

        {/* Instructions / Result */}
        <div className="flex flex-col justify-center">
          <AnimatePresence mode="wait">
            {!showResult ? (
              <motion.div
                key="instructions"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
              >
                <Card className="border-primary/30 bg-primary/5">
                  <CardContent className="py-6 text-center">
                    <Target className="w-10 h-10 mx-auto mb-3 text-primary" />
                    <h3 className="text-lg font-bold mb-2">What would you play?</h3>
                    <p className="text-sm text-muted-foreground">
                      Drag a piece to make your move.
                      Try to find the best move in this position.
                    </p>
                    <p className="text-xs text-muted-foreground mt-4">
                      This is a position from your own game where you made a mistake.
                    </p>
                  </CardContent>
                </Card>
              </motion.div>
            ) : (
              <motion.div
                key="result"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
              >
                <Card className={`border-2 ${
                  isCorrect 
                    ? 'border-green-500/50 bg-green-500/10' 
                    : 'border-red-500/50 bg-red-500/10'
                }`}>
                  <CardContent className="py-6">
                    <div className="flex items-center gap-3 mb-4">
                      {isCorrect ? (
                        <CheckCircle2 className="w-8 h-8 text-green-500" />
                      ) : (
                        <XCircle className="w-8 h-8 text-red-500" />
                      )}
                      <div>
                        <h3 className={`text-lg font-bold ${
                          isCorrect ? 'text-green-500' : 'text-red-500'
                        }`}>
                          {isCorrect ? "Correct!" : "Not quite"}
                        </h3>
                        <p className="text-sm text-muted-foreground">
                          You played: <span className="font-mono">{userMove}</span>
                        </p>
                      </div>
                    </div>

                    {/* Show the answer */}
                    <div className="p-3 rounded-lg bg-background/50 mb-4">
                      <div className="flex items-center gap-2 mb-2">
                        <Lightbulb className="w-4 h-4 text-yellow-500" />
                        <span className="text-sm font-medium">Best Move</span>
                      </div>
                      <p className="font-mono text-emerald-500 font-bold">
                        {currentPosition?.best_move}
                      </p>
                      
                      {/* What you actually played in the game */}
                      <p className="text-xs text-muted-foreground mt-2">
                        In the game, you played <span className="font-mono text-red-400">{currentPosition?.move_played}</span> (−{currentPosition?.cp_loss} cp)
                      </p>
                    </div>

                    {/* Actions */}
                    <div className="flex gap-2">
                      <Button 
                        variant="outline" 
                        size="sm" 
                        onClick={retryPosition}
                        className="flex-1 gap-1"
                      >
                        <RotateCcw className="w-4 h-4" />
                        Retry
                      </Button>
                      <Button 
                        variant="outline" 
                        size="sm" 
                        onClick={goToGame}
                        className="flex-1"
                      >
                        Full Game
                      </Button>
                      <Button 
                        size="sm" 
                        onClick={nextPosition}
                        className="flex-1 gap-1"
                      >
                        {currentIndex < positions.length - 1 ? (
                          <>Next <ChevronRight className="w-4 h-4" /></>
                        ) : (
                          <>Finish <Trophy className="w-4 h-4" /></>
                        )}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Close button */}
      <div className="flex justify-center pt-2">
        <Button variant="ghost" size="sm" onClick={onClose}>
          Exit Drill
        </Button>
      </div>
    </div>
  );
};

export default DrillMode;
