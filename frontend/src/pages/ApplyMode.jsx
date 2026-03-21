/**
 * ApplyMode.jsx - The Bridge Between Puzzles and Real Games
 * 
 * This is where real improvement happens.
 * Uses LichessBoard component for consistent board rendering.
 */

import { useState, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Chess } from "chess.js";
import {
  Target,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Shield,
  Trophy,
  ArrowRight,
  RotateCcw,
  Zap,
  Brain,
  Eye
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import LichessBoard from "@/components/LichessBoard";

// Simple AI responses
const getSimpleAIMove = (chess) => {
  const moves = chess.moves();
  if (moves.length === 0) return null;
  
  const captures = moves.filter(m => m.includes('x'));
  const checks = moves.filter(m => m.includes('+'));
  
  if (captures.length > 0) return captures[Math.floor(Math.random() * captures.length)];
  if (checks.length > 0) return checks[Math.floor(Math.random() * checks.length)];
  return moves[Math.floor(Math.random() * moves.length)];
};

const ApplyMode = ({ user }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const blocker = location.state?.blocker;
  const rule = blocker?.rule || "Before EVERY move, ask: What is my opponent threatening?";
  
  const boardRef = useRef(null);
  const chessRef = useRef(new Chess());
  
  const [currentFen, setCurrentFen] = useState("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  const [lastMove, setLastMove] = useState(null);
  const [gameState, setGameState] = useState("intro"); // intro, playing, ruleCheck, feedback, complete, failed
  const [moveCount, setMoveCount] = useState(0);
  const [mistakesInGame, setMistakesInGame] = useState(0);
  const [pendingMove, setPendingMove] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [gameResult, setGameResult] = useState(null);
  const [canMove, setCanMove] = useState(false);
  
  const maxMoves = 15;
  const maxMistakes = 2;
  
  const startGame = () => {
    chessRef.current.reset();
    setCurrentFen(chessRef.current.fen());
    setLastMove(null);
    setGameState("ruleCheck");
    setMoveCount(0);
    setMistakesInGame(0);
    setCanMove(false);
  };
  
  const acknowledgeRule = () => {
    setGameState("playing");
    setCanMove(true);
  };
  
  const showRuleCheck = () => {
    setGameState("ruleCheck");
    setCanMove(false);
  };
  
  const onMove = (moveData) => {
    if (!canMove || !moveData) return;
    
    const { from, to } = moveData;
    
    // Try to make the move
    const move = chessRef.current.move({ from, to, promotion: 'q' });
    if (!move) return;
    
    // Update state
    const newMoveCount = moveCount + 1;
    setMoveCount(newMoveCount);
    setCurrentFen(chessRef.current.fen());
    setLastMove([from, to]);
    setCanMove(false);
    
    // Check game over
    if (chessRef.current.isGameOver()) {
      handleGameOver();
      return;
    }
    
    // Check move limit
    if (newMoveCount >= maxMoves) {
      handleGameComplete();
      return;
    }
    
    // AI makes a move
    setTimeout(() => makeAIMove(), 500);
  };
  
  const makeAIMove = () => {
    const aiMove = getSimpleAIMove(chessRef.current);
    if (!aiMove) {
      handleGameOver();
      return;
    }
    
    const move = chessRef.current.move(aiMove);
    if (!move) return;
    
    setCurrentFen(chessRef.current.fen());
    setLastMove([move.from, move.to]);
    
    if (chessRef.current.isGameOver()) {
      handleGameOver();
      return;
    }
    
    // Require rule check before next move
    showRuleCheck();
  };
  
  const handleGameOver = () => {
    const result = chessRef.current.isCheckmate() ? 
      (chessRef.current.turn() === 'b' ? 'win' : 'loss') : 'draw';
    
    setGameState("complete");
    setGameResult({
      success: mistakesInGame < maxMistakes,
      result,
      mistakes: mistakesInGame,
      moves: moveCount
    });
  };
  
  const handleGameComplete = () => {
    setGameState("complete");
    setGameResult({
      success: mistakesInGame < maxMistakes,
      result: 'completed',
      mistakes: mistakesInGame,
      moves: moveCount
    });
  };
  
  const handleFinish = () => {
    localStorage.setItem(`apply_mode_${user?.user_id}`, JSON.stringify({
      completed: true,
      mistakes: mistakesInGame,
      moves: moveCount,
      completedAt: new Date().toISOString()
    }));
    navigate("/plateau-breaker");
  };
  
  const handleRetry = () => {
    chessRef.current.reset();
    setCurrentFen(chessRef.current.fen());
    setLastMove(null);
    setGameState("intro");
    setMoveCount(0);
    setMistakesInGame(0);
    setFeedback(null);
    setPendingMove(null);
    setGameResult(null);
    setCanMove(false);
  };
  
  // INTRO SCREEN
  if (gameState === "intro") {
    return (
      <div className="min-h-screen bg-zinc-950 text-white flex items-center justify-center p-6">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="max-w-md w-full"
        >
          <Card className="bg-amber-950/30 border-amber-500/50">
            <CardContent className="p-8">
              <div className="text-center mb-6">
                <div className="w-16 h-16 bg-amber-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Zap className="w-8 h-8 text-amber-400" />
                </div>
                <h2 className="text-2xl font-bold text-amber-400 mb-2">
                  Apply Mode
                </h2>
                <p className="text-zinc-400">
                  Puzzles are easy. Real games are hard.
                </p>
              </div>
              
              <div className="space-y-4 mb-6">
                <div className="bg-zinc-900/50 rounded-lg p-4">
                  <h3 className="font-semibold text-white mb-2">What happens now:</h3>
                  <ul className="space-y-2 text-sm text-zinc-300">
                    <li className="flex items-start gap-2">
                      <span className="text-amber-400">1.</span>
                      Play a mini-game ({maxMoves} moves)
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-amber-400">2.</span>
                      Before EACH move, confirm you applied your rule
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-amber-400">3.</span>
                      {maxMistakes} mistakes max or you restart
                    </li>
                  </ul>
                </div>
                
                <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
                  <p className="text-sm text-red-400 font-medium mb-1">Your Rule:</p>
                  <p className="text-white font-semibold">{rule}</p>
                </div>
              </div>
              
              <Button
                onClick={startGame}
                className="w-full h-12 text-lg bg-amber-600 hover:bg-amber-700"
              >
                <Target className="w-5 h-5 mr-2" />
                Start Game
              </Button>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    );
  }
  
  // FAILED SCREEN
  if (gameState === "failed") {
    return (
      <div className="min-h-screen bg-zinc-950 text-white flex items-center justify-center p-6">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="max-w-md w-full"
        >
          <Card className="bg-red-950/50 border-red-500/50">
            <CardContent className="p-8 text-center">
              <div className="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <XCircle className="w-8 h-8 text-red-400" />
              </div>
              
              <h2 className="text-2xl font-bold text-red-400 mb-4">
                Apply Mode Failed
              </h2>
              
              <div className="bg-red-900/30 rounded-lg p-4 mb-6 text-left">
                <p className="text-white font-semibold mb-2">
                  You made {gameResult?.mistakes} mistakes in {gameResult?.moves} moves.
                </p>
                <p className="text-zinc-400 text-sm">
                  This is exactly what happens in your real games. You know the rule, 
                  but under game pressure, you forget it.
                </p>
              </div>
              
              <Button
                onClick={handleRetry}
                className="w-full h-12 bg-red-600 hover:bg-red-700"
              >
                <RotateCcw className="w-5 h-5 mr-2" />
                Try Again
              </Button>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    );
  }
  
  // COMPLETE SCREEN
  if (gameState === "complete") {
    return (
      <div className="min-h-screen bg-zinc-950 text-white flex items-center justify-center p-6">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="max-w-md w-full"
        >
          <Card className="bg-green-950/30 border-green-500/50">
            <CardContent className="p-8 text-center">
              <div className="w-16 h-16 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Trophy className="w-8 h-8 text-green-400" />
              </div>
              
              <h2 className="text-2xl font-bold text-green-400 mb-2">
                Apply Mode Complete!
              </h2>
              
              <p className="text-zinc-300 mb-4">
                You played {gameResult?.moves} moves with only {gameResult?.mistakes} mistake(s).
              </p>
              
              <div className="bg-zinc-900/50 rounded-lg p-4 mb-6 text-left">
                <div className="flex items-center gap-2 text-green-400 mb-2">
                  <CheckCircle className="w-4 h-4" />
                  <span className="font-semibold">This is real improvement.</span>
                </div>
                <p className="text-zinc-400 text-sm">
                  You applied your rule under game pressure. Keep doing this in your 
                  real games and you'll see results.
                </p>
              </div>
              
              <Button
                onClick={handleFinish}
                className="w-full h-12 bg-green-600 hover:bg-green-700"
              >
                Continue
                <ArrowRight className="w-5 h-5 ml-2" />
              </Button>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    );
  }
  
  // GAME SCREEN
  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      {/* Header */}
      <div className="border-b border-zinc-800 p-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Zap className="w-5 h-5 text-amber-500" />
              <span className="font-semibold">Apply Mode</span>
            </div>
            <div className="flex items-center gap-4 text-sm">
              <span className="text-zinc-500">Move {moveCount} / {maxMoves}</span>
              <span className={`${mistakesInGame > 0 ? 'text-red-400' : 'text-green-400'}`}>
                Mistakes: {mistakesInGame} / {maxMistakes}
              </span>
            </div>
          </div>
          <Progress value={(moveCount / maxMoves) * 100} className="h-1" />
        </div>
      </div>
      
      {/* Main Content */}
      <div className="max-w-4xl mx-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          
          {/* Board */}
          <Card className="bg-zinc-900/50 border-zinc-800">
            <CardContent className="p-4">
              <div className="aspect-square">
                <LichessBoard
                  ref={boardRef}
                  fen={currentFen}
                  orientation="white"
                  lastMove={lastMove}
                  onMove={onMove}
                  interactive={canMove}
                  viewOnly={!canMove}
                  showDests={canMove}
                />
              </div>
            </CardContent>
          </Card>
          
          {/* Control Panel */}
          <div className="space-y-4">
            {/* Rule Reminder */}
            <Card className="bg-red-500/10 border-red-500/30">
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <Target className="w-5 h-5 text-red-400 mt-0.5" />
                  <div>
                    <p className="text-red-400 text-xs font-medium mb-1">YOUR RULE</p>
                    <p className="text-white font-bold">{rule}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            {/* Rule Check Modal */}
            <AnimatePresence>
              {gameState === "ruleCheck" && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                >
                  <Card className="bg-amber-950/30 border-amber-500/50">
                    <CardContent className="p-6">
                      <div className="flex items-center gap-3 mb-4">
                        <Brain className="w-8 h-8 text-amber-400" />
                        <div>
                          <h3 className="font-semibold text-amber-400">Before you move...</h3>
                          <p className="text-sm text-zinc-400">Apply your rule first</p>
                        </div>
                      </div>
                      
                      <div className="bg-zinc-900/50 rounded-lg p-4 mb-4">
                        <p className="text-white text-center font-semibold">
                          "{rule.split(',')[0]}"
                        </p>
                      </div>
                      
                      <Button
                        onClick={acknowledgeRule}
                        className="w-full bg-amber-600 hover:bg-amber-700"
                      >
                        <Eye className="w-4 h-4 mr-2" />
                        I've checked. Let me move.
                      </Button>
                    </CardContent>
                  </Card>
                </motion.div>
              )}
            </AnimatePresence>
            
            {/* Game Status */}
            {gameState === "playing" && canMove && (
              <Card className="bg-zinc-900/50 border-zinc-800">
                <CardContent className="p-4">
                  <p className="text-center text-zinc-400">
                    Your turn. Make your move.
                  </p>
                </CardContent>
              </Card>
            )}
            
            {gameState === "playing" && !canMove && (
              <Card className="bg-zinc-900/50 border-zinc-800">
                <CardContent className="p-4">
                  <p className="text-center text-zinc-500">
                    Opponent is thinking...
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ApplyMode;
