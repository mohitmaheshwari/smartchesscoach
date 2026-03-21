/**
 * ApplyMode.jsx - The Bridge Between Puzzles and Real Games
 * 
 * This is where real improvement happens.
 * 
 * After completing 5 puzzles, user MUST play a mini-game:
 * - 15 moves maximum
 * - Same rule enforced before EVERY move
 * - Cannot move until rule acknowledged
 * - If they repeat the mistake → immediate call-out
 * - Success = actually applying the rule under game pressure
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Chess } from "chess.js";
import { Chessground } from "chessground";
import {
  Target,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Shield,
  Trophy,
  ArrowRight,
  RotateCcw,
  Clock,
  Zap,
  Brain,
  Eye
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

import "chessground/assets/chessground.base.css";
import "chessground/assets/chessground.brown.css";
import "chessground/assets/chessground.cburnett.css";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

// Simple AI responses (in real implementation, use Stockfish)
const getSimpleAIMove = (chess) => {
  const moves = chess.moves();
  if (moves.length === 0) return null;
  
  // Prefer captures, then checks, then random
  const captures = moves.filter(m => m.includes('x'));
  const checks = moves.filter(m => m.includes('+'));
  
  if (captures.length > 0) return captures[Math.floor(Math.random() * captures.length)];
  if (checks.length > 0) return checks[Math.floor(Math.random() * checks.length)];
  return moves[Math.floor(Math.random() * moves.length)];
};

// Check if a move is a blunder (piece left hanging)
const isHangingPiece = (chess, move) => {
  // Make the move temporarily
  const testChess = new Chess(chess.fen());
  testChess.move(move);
  
  // Check if any of our pieces are now attacked and undefended
  const board = testChess.board();
  const turn = testChess.turn(); // Now opponent's turn
  const ourColor = turn === 'w' ? 'b' : 'w';
  
  for (let r = 0; r < 8; r++) {
    for (let c = 0; c < 8; c++) {
      const piece = board[r][c];
      if (piece && piece.color === ourColor) {
        const square = String.fromCharCode(97 + c) + (8 - r);
        const attackers = testChess.attackers(square, turn);
        const defenders = testChess.attackers(square, ourColor);
        
        // If attacked and not defended (or less defended), it's hanging
        if (attackers.length > 0 && defenders.length < attackers.length) {
          // Check piece value
          const pieceValues = { 'p': 1, 'n': 3, 'b': 3, 'r': 5, 'q': 9, 'k': 0 };
          if (pieceValues[piece.type] >= 3) {
            return { square, piece: piece.type };
          }
        }
      }
    }
  }
  return null;
};

const ApplyMode = ({ user }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const blocker = location.state?.blocker;
  const rule = blocker?.rule || "Before EVERY move, ask: What is my opponent threatening?";
  
  const boardRef = useRef(null);
  const groundRef = useRef(null);
  const chessRef = useRef(new Chess());
  
  const [gameState, setGameState] = useState("intro"); // intro, playing, ruleCheck, feedback, complete, failed
  const [moveCount, setMoveCount] = useState(0);
  const [mistakesInGame, setMistakesInGame] = useState(0);
  const [ruleAcknowledged, setRuleAcknowledged] = useState(false);
  const [pendingMove, setPendingMove] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [gameResult, setGameResult] = useState(null);
  
  const maxMoves = 15;
  const maxMistakes = 2; // Fail if 2 mistakes in the mini-game
  
  useEffect(() => {
    if (boardRef.current && !groundRef.current) {
      initializeBoard();
    }
    return () => {
      if (groundRef.current) {
        groundRef.current.destroy();
        groundRef.current = null;
      }
    };
  }, []);
  
  const initializeBoard = () => {
    groundRef.current = Chessground(boardRef.current, {
      fen: chessRef.current.fen(),
      orientation: "white",
      turnColor: "white",
      movable: {
        free: false,
        color: "white",
        dests: new Map(),
        events: {
          after: onMoveAttempt
        }
      },
      animation: { duration: 300 }
    });
  };
  
  const getLegalMoves = () => {
    const dests = new Map();
    const moves = chessRef.current.moves({ verbose: true });
    
    for (const move of moves) {
      if (!dests.has(move.from)) {
        dests.set(move.from, []);
      }
      dests.get(move.from).push(move.to);
    }
    return dests;
  };
  
  const updateBoard = useCallback(() => {
    if (!groundRef.current) return;
    
    const turn = chessRef.current.turn();
    const isOurTurn = turn === 'w';
    
    groundRef.current.set({
      fen: chessRef.current.fen(),
      turnColor: isOurTurn ? 'white' : 'black',
      movable: {
        color: isOurTurn ? 'white' : undefined,
        dests: isOurTurn ? getLegalMoves() : new Map()
      }
    });
  }, []);
  
  const startGame = () => {
    chessRef.current.reset();
    setGameState("playing");
    setMoveCount(0);
    setMistakesInGame(0);
    setRuleAcknowledged(false);
    updateBoard();
    
    // Enable moves but require rule acknowledgment
    showRuleCheck();
  };
  
  const showRuleCheck = () => {
    setGameState("ruleCheck");
    setRuleAcknowledged(false);
    
    // Disable board until rule is acknowledged
    if (groundRef.current) {
      groundRef.current.set({
        movable: { dests: new Map() }
      });
    }
  };
  
  const acknowledgeRule = () => {
    setRuleAcknowledged(true);
    setGameState("playing");
    
    // Enable moves
    if (groundRef.current) {
      groundRef.current.set({
        movable: { dests: getLegalMoves() }
      });
    }
  };
  
  const onMoveAttempt = (orig, dest) => {
    // Store the pending move
    const moveObj = { from: orig, to: dest };
    setPendingMove(moveObj);
    
    // Check if this creates a hanging piece (applying their weakness)
    const hanging = isHangingPiece(chessRef.current, moveObj);
    
    if (hanging) {
      // CAUGHT! They're about to repeat their mistake
      setFeedback({
        type: "warning",
        title: "STOP! You're about to repeat your mistake!",
        message: `Your ${hanging.piece === 'n' ? 'knight' : hanging.piece === 'b' ? 'bishop' : hanging.piece === 'r' ? 'rook' : hanging.piece === 'q' ? 'queen' : 'piece'} on ${hanging.square} will be undefended.`,
        subtext: "This is EXACTLY what you do in your games. Think again."
      });
      setGameState("feedback");
      
      // Don't make the move yet - let them reconsider
      // Revert the board
      updateBoard();
    } else {
      // Good move - proceed
      executeMove(moveObj);
    }
  };
  
  const executeMove = (moveObj) => {
    const move = chessRef.current.move(moveObj);
    if (!move) return;
    
    const newMoveCount = moveCount + 1;
    setMoveCount(newMoveCount);
    
    // Update board
    if (groundRef.current) {
      groundRef.current.set({
        fen: chessRef.current.fen(),
        lastMove: [move.from, move.to]
      });
    }
    
    // Check game over conditions
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
    
    // Update board with AI move
    if (groundRef.current) {
      groundRef.current.set({
        fen: chessRef.current.fen(),
        lastMove: [move.from, move.to]
      });
    }
    
    // Check game over
    if (chessRef.current.isGameOver()) {
      handleGameOver();
      return;
    }
    
    // Require rule check before next move
    showRuleCheck();
  };
  
  const handleProceedAnyway = () => {
    // They chose to make the bad move anyway
    const newMistakes = mistakesInGame + 1;
    setMistakesInGame(newMistakes);
    
    if (newMistakes >= maxMistakes) {
      // FAILED - Too many mistakes
      setGameState("failed");
      setGameResult({
        success: false,
        mistakes: newMistakes,
        moves: moveCount,
        reason: "You repeated your mistake too many times."
      });
    } else {
      // Allow the move but track the mistake
      if (pendingMove) {
        const actualMove = chessRef.current.move(pendingMove);
        if (actualMove) {
          setMoveCount(moveCount + 1);
          updateBoard();
          
          // Show mistake feedback
          setFeedback({
            type: "mistake",
            title: "Mistake made.",
            message: `You have ${maxMistakes - newMistakes} mistake(s) left.`,
            subtext: "Next time, apply your rule."
          });
          setGameState("feedback");
          
          // After delay, continue
          setTimeout(() => {
            setFeedback(null);
            if (chessRef.current.isGameOver()) {
              handleGameOver();
            } else {
              makeAIMove();
            }
          }, 2000);
        }
      }
    }
  };
  
  const handleReconsider = () => {
    // Good choice - they reconsidered
    setFeedback(null);
    setPendingMove(null);
    setGameState("playing");
    updateBoard();
    
    // Re-enable moves
    if (groundRef.current) {
      groundRef.current.set({
        movable: { dests: getLegalMoves() }
      });
    }
  };
  
  const handleGameOver = () => {
    const result = chessRef.current.isCheckmate() ? 
      (chessRef.current.turn() === 'b' ? 'win' : 'loss') :
      'draw';
    
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
    // Save completion and return to dashboard
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
    setGameState("intro");
    setMoveCount(0);
    setMistakesInGame(0);
    setRuleAcknowledged(false);
    setFeedback(null);
    setPendingMove(null);
    setGameResult(null);
    updateBoard();
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
                      If you repeat your mistake → we'll catch you
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-amber-400">4.</span>
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
                  You repeated your mistake {gameResult?.mistakes} times.
                </p>
                <p className="text-zinc-400 text-sm">
                  This is exactly what happens in your real games. You know the rule, 
                  but under game pressure, you forget it.
                </p>
              </div>
              
              <p className="text-zinc-500 text-sm mb-6">
                Understanding is not enough. You need repetition until it's automatic.
              </p>
              
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
              <div 
                ref={boardRef} 
                className="w-full aspect-square rounded-lg overflow-hidden"
              />
            </CardContent>
          </Card>
          
          {/* Control Panel */}
          <div className="space-y-4">
            {/* Rule Reminder - Always Visible */}
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
            
            {/* Warning/Feedback Modal */}
            <AnimatePresence>
              {gameState === "feedback" && feedback && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0 }}
                >
                  <Card className={`${
                    feedback.type === "warning" 
                      ? "bg-red-950/50 border-red-500/50" 
                      : "bg-amber-950/30 border-amber-500/50"
                  }`}>
                    <CardContent className="p-6">
                      <div className="flex items-center gap-3 mb-4">
                        <AlertTriangle className={`w-8 h-8 ${
                          feedback.type === "warning" ? "text-red-400" : "text-amber-400"
                        }`} />
                        <div>
                          <h3 className={`font-semibold ${
                            feedback.type === "warning" ? "text-red-400" : "text-amber-400"
                          }`}>
                            {feedback.title}
                          </h3>
                        </div>
                      </div>
                      
                      <p className="text-white mb-2">{feedback.message}</p>
                      <p className="text-zinc-500 text-sm mb-4">{feedback.subtext}</p>
                      
                      {feedback.type === "warning" && (
                        <div className="flex gap-2">
                          <Button
                            onClick={handleReconsider}
                            className="flex-1 bg-green-600 hover:bg-green-700"
                          >
                            <Shield className="w-4 h-4 mr-2" />
                            Reconsider
                          </Button>
                          <Button
                            onClick={handleProceedAnyway}
                            variant="outline"
                            className="flex-1 border-red-500/50 text-red-400 hover:bg-red-500/10"
                          >
                            Move Anyway
                          </Button>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </motion.div>
              )}
            </AnimatePresence>
            
            {/* Game Status */}
            {gameState === "playing" && (
              <Card className="bg-zinc-900/50 border-zinc-800">
                <CardContent className="p-4">
                  <p className="text-center text-zinc-400">
                    Your turn. Make your move.
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
