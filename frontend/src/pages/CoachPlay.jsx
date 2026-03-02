/**
 * CoachPlay.jsx - Play With Coach Feature (P2)
 * 
 * A training mode where users play full games against a pedagogical coach engine.
 * Now with Live Socratic Coaching - the coach asks WHY you played each move!
 * 
 * Features:
 * - Pre-move guardian: Catches blunders before they happen
 * - Live reflection: Coach asks "Why did you play that?" after each move
 * - Socratic feedback: Targeted coaching based on your reasoning
 * - Eval bar: Real-time position evaluation
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Chess } from "chess.js";
import LichessBoard from "@/components/LichessBoard";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import Layout from "@/components/Layout";
import { toast } from "sonner";
import {
  Play,
  Pause,
  RotateCcw,
  Flag,
  Clock,
  Trophy,
  Loader2,
  ArrowLeft,
  Swords,
  Brain,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ShieldAlert,
  Lightbulb,
  TrendingUp,
  TrendingDown,
  MessageCircle,
  Send,
  Sparkles,
  ThumbsUp,
  Target
} from "lucide-react";

/**
 * EvalBar - Visual evaluation bar showing position advantage
 * 
 * Props:
 * - evaluation: { score: number, mate_in: number|null }
 *   - score: Centipawn evaluation from white's perspective (-10 to +10)
 *   - mate_in: Number of moves to mate (positive=white wins, negative=black wins)
 * - userColor: "white" | "black" - which color the user is playing
 * - gameOver: boolean - if the game has ended
 */
const EvalBar = ({ evaluation, userColor, gameOver }) => {
  const { score, mate_in } = evaluation || { score: 0, mate_in: null };
  
  // Calculate percentage for the bar (50% = equal, >50% = white advantage)
  // Score is capped at ±10, map to 5-95% range for visual clarity
  const getBarPercentage = () => {
    if (mate_in !== null) {
      return mate_in > 0 ? 95 : 5; // Forced mate
    }
    // Map score from [-10, 10] to [5, 95]
    const clamped = Math.max(-10, Math.min(10, score));
    return 50 + (clamped * 4.5);
  };
  
  const whitePercent = getBarPercentage();
  const blackPercent = 100 - whitePercent;
  
  // Determine display text
  const getEvalText = () => {
    if (mate_in !== null) {
      return `M${Math.abs(mate_in)}`;
    }
    if (score === 0) return "0.0";
    const sign = score > 0 ? "+" : "";
    return `${sign}${score.toFixed(1)}`;
  };
  
  // Determine who is winning and if it's the user
  const isWhiteWinning = score > 0.3 || mate_in > 0;
  const isBlackWinning = score < -0.3 || (mate_in !== null && mate_in < 0);
  const userWinning = (userColor === "white" && isWhiteWinning) || 
                      (userColor === "black" && isBlackWinning);
  const opponentWinning = (userColor === "white" && isBlackWinning) || 
                          (userColor === "black" && isWhiteWinning);
  
  return (
    <div 
      className="w-6 h-full min-h-[400px] flex flex-col rounded-lg overflow-hidden relative"
      data-testid="eval-bar"
      title={`Evaluation: ${getEvalText()}`}
    >
      {/* Black portion (top) */}
      <div 
        className="bg-gray-800 transition-all duration-300 ease-out"
        style={{ height: `${blackPercent}%` }}
      />
      
      {/* White portion (bottom) */}
      <div 
        className="bg-gray-100 transition-all duration-300 ease-out flex-1"
        style={{ height: `${whitePercent}%` }}
      />
      
      {/* Eval text overlay */}
      <div 
        className={`absolute left-1/2 transform -translate-x-1/2 px-1 py-0.5 rounded text-xs font-bold ${
          isWhiteWinning 
            ? "top-auto bottom-1 bg-gray-100 text-gray-900" 
            : isBlackWinning
              ? "top-1 bottom-auto bg-gray-800 text-gray-100"
              : "top-1/2 -translate-y-1/2 bg-gray-500 text-white"
        }`}
        data-testid="eval-text"
      >
        {getEvalText()}
      </div>
      
      {/* Advantage indicator icons */}
      {!gameOver && (userWinning || opponentWinning) && (
        <div className={`absolute left-1/2 transform -translate-x-1/2 ${
          userWinning ? "bottom-8" : "top-8"
        }`}>
          {userWinning ? (
            <TrendingUp className="w-3 h-3 text-green-500" />
          ) : (
            <TrendingDown className="w-3 h-3 text-red-500" />
          )}
        </div>
      )}
    </div>
  );
};

const CoachPlay = ({ user }) => {
  const navigate = useNavigate();
  const boardRef = useRef(null);
  
  // Session state
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(false);
  const [gameStarted, setGameStarted] = useState(false);
  
  // Board state
  const [currentFen, setCurrentFen] = useState("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  const [boardOrientation, setBoardOrientation] = useState("white");
  const [lastMove, setLastMove] = useState(null);
  const [isPlayerTurn, setIsPlayerTurn] = useState(true);
  
  // Game settings
  const [selectedColor, setSelectedColor] = useState("white");
  const [timeControl, setTimeControl] = useState("15+10");
  
  // Timer state
  const [moveStartTime, setMoveStartTime] = useState(null);
  
  // Game over state
  const [gameOver, setGameOver] = useState(false);
  const [gameResult, setGameResult] = useState(null);
  const [summary, setSummary] = useState(null);
  const [cprResult, setCprResult] = useState(null);
  const [playerIdentity, setPlayerIdentity] = useState(null);
  
  // Evaluation state for eval bar
  const [evaluation, setEvaluation] = useState({ score: 0.0, mate_in: null });
  
  // Chat state (replaces popup modal)
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [isSendingChat, setIsSendingChat] = useState(false);
  const chatEndRef = useRef(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  // Check for active session on mount
  useEffect(() => {
    checkActiveSession();
  }, []);

  const checkActiveSession = async () => {
    try {
      const response = await fetch(`${API}/coach/play/active`, {
        credentials: "include"
      });
      if (response.ok) {
        const data = await response.json();
        if (data.active_sessions && data.active_sessions.length > 0) {
          // Resume existing session
          const activeSession = data.active_sessions[0];
          await resumeSession(activeSession.session_id);
        }
      }
    } catch (error) {
      console.error("Error checking active session:", error);
    }
  };

  const resumeSession = async (sessionId) => {
    try {
      const response = await fetch(`${API}/coach/play/state/${sessionId}`, {
        credentials: "include"
      });
      if (response.ok) {
        const data = await response.json();
        setSession(data.session);
        setCurrentFen(data.current_fen);
        setBoardOrientation(data.session.user_color);
        setSelectedColor(data.session.user_color);
        setIsPlayerTurn(data.is_player_turn);
        setGameStarted(true);
        setGameOver(data.game_over);
        
        // Set evaluation for eval bar
        if (data.evaluation) {
          setEvaluation(data.evaluation);
        }
        
        // Highlight last move
        if (data.session.move_history?.length > 0) {
          const lastMoveData = data.session.move_history[data.session.move_history.length - 1];
          if (lastMoveData.uci) {
            setLastMove([lastMoveData.uci.slice(0, 2), lastMoveData.uci.slice(2, 4)]);
          }
        }
        
        if (data.is_player_turn) {
          setMoveStartTime(Date.now());
        }
        
        toast.success("Resumed your game!");
      }
    } catch (error) {
      console.error("Error resuming session:", error);
    }
  };

  const startGame = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API}/coach/play/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          user_color: selectedColor,
          time_control: timeControl
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to start game");
      }

      const data = await response.json();
      setSession(data.session);
      setCurrentFen(data.current_fen);
      setBoardOrientation(selectedColor);
      setIsPlayerTurn(data.is_player_turn);
      setGameStarted(true);
      setMoveStartTime(Date.now());
      
      // Set initial evaluation
      if (data.evaluation) {
        setEvaluation(data.evaluation);
      }
      
      // If playing black, coach already made first move
      if (selectedColor === "black" && data.session.move_history?.length > 0) {
        const coachMove = data.session.move_history[0];
        if (coachMove.uci) {
          setLastMove([coachMove.uci.slice(0, 2), coachMove.uci.slice(2, 4)]);
        }
      }
      
      toast.success(data.message);
    } catch (error) {
      toast.error(error.message || "Failed to start game");
    } finally {
      setLoading(false);
    }
  };

  const highlightMove = (uci) => {
    if (!uci || uci.length < 4) return;
    const from = uci.slice(0, 2);
    const to = uci.slice(2, 4);
    setLastMove([from, to]);
  };

  // Guardian intervention state
  const [guardianIntervention, setGuardianIntervention] = useState(null);
  const [pendingMove, setPendingMove] = useState(null);
  const [remainingInterventions, setRemainingInterventions] = useState(3);

  // Evaluate move with guardian before making it
  const evaluateMove = async (moveSan) => {
    try {
      const response = await fetch(`${API}/coach/play/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: session.session_id,
          move: moveSan
        })
      });

      if (response.ok) {
        return await response.json();
      }
    } catch (error) {
      console.error("Guardian evaluation error:", error);
    }
    return null;
  };

  // Execute the move (called after guardian check passes or user confirms)
  const executeMove = async (moveSan, timeSpent, isOverride = false, riskType = null) => {
    const endpoint = isOverride ? `${API}/coach/play/move/confirm` : `${API}/coach/play/move`;
    
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: session.session_id,
          move: moveSan,
          time_spent: timeSpent,
          ...(isOverride && { risk_acknowledged: riskType })
        })
      });

      if (!response.ok) {
        const error = await response.json();
        toast.error(error.detail || "Invalid move");
        return false;
      }

      const data = await response.json();
      setSession(data.session);
      
      // Update remaining interventions
      if (data.remaining_interventions !== undefined) {
        setRemainingInterventions(data.remaining_interventions);
      }
      
      // Update evaluation for eval bar
      if (data.evaluation) {
        setEvaluation(data.evaluation);
      }

      // Check if game is over
      if (data.game_over) {
        setGameOver(true);
        setGameResult(data.result);
        setCurrentFen(data.session.current_fen);
        
        if (data.result === "win") {
          toast.success("You won! Great game!");
        } else if (data.result === "loss") {
          toast.info(`Game over: ${data.termination_reason}`);
        } else {
          toast.info(`Draw: ${data.termination_reason}`);
        }
        return true;
      }

      // Update with coach's response
      if (data.coach_move) {
        setCurrentFen(data.session.current_fen);
        highlightMove(data.coach_move.uci);
        
        if (data.game_over) {
          setGameOver(true);
          setGameResult(data.result);
        } else {
          setIsPlayerTurn(true);
          setMoveStartTime(Date.now());
        }
      }
      
      // Add coach message to chat if triggered
      if (data.coach_message) {
        setChatMessages(prev => [...prev, {
          type: "coach",
          message: data.coach_message,
          trigger: data.coach_trigger,
          move: moveSan,
          timestamp: Date.now()
        }]);
      }

      return true;
    } catch (error) {
      console.error("Move error:", error);
      toast.error("Connection error. Please try again.");
      return false;
    }
  };
  
  // Send chat message to coach
  const sendChatMessage = async () => {
    if (!chatInput.trim() || !session) return;
    
    const userMessage = chatInput.trim();
    setChatInput("");
    
    // Add user message to chat
    setChatMessages(prev => [...prev, {
      type: "user",
      message: userMessage,
      timestamp: Date.now()
    }]);
    
    setIsSendingChat(true);
    
    try {
      const response = await fetch(`${API}/coach/play/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: session.session_id,
          message: userMessage
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        setChatMessages(prev => [...prev, {
          type: "coach",
          message: data.response,
          timestamp: Date.now()
        }]);
      }
    } catch (error) {
      console.error("Chat error:", error);
    } finally {
      setIsSendingChat(false);
    }
  };

  // Handle user confirming a risky move
  const confirmRiskyMove = async () => {
    if (!pendingMove) return;
    
    const { moveSan, timeSpent, riskType, chess } = pendingMove;
    
    // Update board
    setCurrentFen(chess.fen());
    setIsPlayerTurn(false);
    
    // Clear intervention state
    setGuardianIntervention(null);
    setPendingMove(null);
    
    // Execute with override
    const success = await executeMove(moveSan, timeSpent, true, riskType);
    
    if (!success) {
      // Revert
      setCurrentFen(currentFen);
      setIsPlayerTurn(true);
    }
  };

  // Handle user canceling a risky move
  const cancelRiskyMove = () => {
    // Reset the board to the position before the attempted move
    if (pendingMove?.originalFen) {
      const originalFen = pendingMove.originalFen;
      // Directly set the FEN - LichessBoard will update
      setCurrentFen(originalFen);
      setLastMove(null); // Clear last move highlight
      setIsPlayerTurn(true);
      
      // Force LichessBoard to re-render by using ref if needed
      if (boardRef.current?.setPosition) {
        boardRef.current.setPosition(originalFen);
      }
    }
    
    setGuardianIntervention(null);
    setPendingMove(null);
    toast.info("Move cancelled. Choose a different move.");
  };

  const makeMove = useCallback(async (sourceSquare, targetSquare, piece) => {
    if (!session || !isPlayerTurn || gameOver) return false;

    // Try to make the move locally first
    const chess = new Chess(currentFen);
    let moveObj;
    try {
      moveObj = chess.move({
        from: sourceSquare,
        to: targetSquare,
        promotion: piece?.[1]?.toLowerCase() === "p" ? "q" : undefined
      });
    } catch {
      return false;
    }

    if (!moveObj) return false;

    // Calculate time spent
    const timeSpent = moveStartTime ? (Date.now() - moveStartTime) / 1000 : 0;

    // GUARDIAN CHECK: Evaluate move before making it
    const guardianResult = await evaluateMove(moveObj.san);
    
    if (guardianResult?.should_intervene) {
      // Show intervention modal - don't make the move yet
      // Store the original FEN so we can reset if user cancels
      setGuardianIntervention(guardianResult);
      setPendingMove({
        moveSan: moveObj.san,
        moveObj: moveObj,
        timeSpent: timeSpent,
        riskType: guardianResult.risk_type,
        chess: chess,
        originalFen: currentFen  // Store original position to reset if cancelled
      });
      return false; // Don't complete the move yet
    }

    // No intervention needed - proceed with move
    setCurrentFen(chess.fen());
    setIsPlayerTurn(false);
    highlightMove(moveObj.from + moveObj.to);

    const success = await executeMove(moveObj.san, timeSpent);
    
    if (!success) {
      // Revert
      setCurrentFen(currentFen);
      setIsPlayerTurn(true);
      return false;
    }

    return true;
  }, [session, currentFen, isPlayerTurn, gameOver, moveStartTime]);

  const resignGame = async () => {
    if (!session) return;

    try {
      const response = await fetch(`${API}/coach/play/end`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: session.session_id,
          reason: "resigned"
        })
      });

      if (response.ok) {
        const data = await response.json();
        setGameOver(true);
        setGameResult("loss");
        setSummary(data.summary);
        setCprResult(data.cpr);
        setPlayerIdentity(data.identity);
        toast.info("You resigned. Better luck next time!");
      }
    } catch (error) {
      toast.error("Failed to resign");
    }
  };

  const flipBoard = () => {
    setBoardOrientation(prev => prev === "white" ? "black" : "white");
  };

  const newGame = () => {
    setSession(null);
    setGameStarted(false);
    setGameOver(false);
    setGameResult(null);
    setSummary(null);
    setCprResult(null);
    setPlayerIdentity(null);
    setCurrentFen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
    setLastMove(null);
    setIsPlayerTurn(true);
    setGuardianIntervention(null);
    setPendingMove(null);
  };

  // Pre-game setup screen
  if (!gameStarted) {
    return (
      <Layout user={user}>
        <div className="max-w-2xl mx-auto py-8 px-4" data-testid="coach-play-setup">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/")}
            className="mb-6"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Home
          </Button>

          <Card className="border-primary/20">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-full bg-primary/10">
                  <Swords className="w-8 h-8 text-primary" />
                </div>
                <div>
                  <CardTitle className="text-2xl">Play With Coach</CardTitle>
                  <p className="text-muted-foreground">
                    Train against an intelligent opponent
                  </p>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Color Selection */}
              <div>
                <label className="text-sm font-medium mb-3 block">
                  Choose Your Color
                </label>
                <div className="flex gap-3">
                  <Button
                    variant={selectedColor === "white" ? "default" : "outline"}
                    onClick={() => setSelectedColor("white")}
                    className="flex-1"
                    data-testid="select-white"
                  >
                    <div className="w-6 h-6 rounded-full bg-white border mr-2" />
                    White
                  </Button>
                  <Button
                    variant={selectedColor === "black" ? "default" : "outline"}
                    onClick={() => setSelectedColor("black")}
                    className="flex-1"
                    data-testid="select-black"
                  >
                    <div className="w-6 h-6 rounded-full bg-gray-900 border mr-2" />
                    Black
                  </Button>
                </div>
              </div>

              {/* Time Control */}
              <div>
                <label className="text-sm font-medium mb-3 block">
                  Time Control
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {["3+2", "10+5", "15+10"].map((tc) => (
                    <Button
                      key={tc}
                      variant={timeControl === tc ? "default" : "outline"}
                      onClick={() => setTimeControl(tc)}
                      size="sm"
                      data-testid={`time-${tc.replace("+", "-")}`}
                    >
                      <Clock className="w-4 h-4 mr-1" />
                      {tc}
                    </Button>
                  ))}
                </div>
              </div>

              {/* Start Button */}
              <Button
                onClick={startGame}
                disabled={loading}
                className="w-full h-12 text-lg"
                data-testid="start-game-btn"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                    Starting...
                  </>
                ) : (
                  <>
                    <Play className="w-5 h-5 mr-2" />
                    Start Game
                  </>
                )}
              </Button>

              {/* Info */}
              <div className="p-4 rounded-lg bg-muted/50 text-sm text-muted-foreground">
                <Brain className="w-4 h-4 inline mr-2" />
                The coach will adapt to your play and help you improve.
                Future updates will add real-time interventions when you're
                about to make mistakes.
              </div>
            </CardContent>
          </Card>
        </div>
      </Layout>
    );
  }

  // Game screen
  return (
    <Layout user={user}>
      <div className="h-[calc(100vh-80px)] flex" data-testid="coach-play-game">
        {/* Left: Board + Eval Bar */}
        <div className="flex-1 flex flex-col items-center justify-center p-4">
          <div className="w-full max-w-[600px] flex gap-3">
            {/* Eval Bar */}
            <EvalBar 
              evaluation={evaluation} 
              userColor={selectedColor}
              gameOver={gameOver}
            />
            
            <div className="flex-1 max-w-[560px]">
              {/* Coach info bar */}
              <div className="flex items-center justify-between mb-3 p-3 rounded-lg bg-muted/50">
                <div className="flex items-center gap-2">
                  <Brain className="w-5 h-5 text-primary" />
                  <span className="font-medium">Coach</span>
                  <Badge variant="secondary" className="text-xs">
                    Level {session?.coach_skill_level || 8}
                  </Badge>
                </div>
                <Badge variant="outline">
                  <Clock className="w-3 h-3 mr-1" />
                  {Math.floor((session?.coach_time_remaining || 900) / 60)}:
                  {String(Math.floor((session?.coach_time_remaining || 900) % 60)).padStart(2, "0")}
                </Badge>
              </div>

              {/* Chessboard - Using Lichess Board */}
              <div className="rounded-lg overflow-hidden" style={{ boxShadow: "0 4px 20px rgba(0,0,0,0.3)" }}>
                <LichessBoard
                  ref={boardRef}
                  fen={currentFen}
                  orientation={boardOrientation}
                  lastMove={lastMove}
                  onMove={(moveData) => {
                    if (isPlayerTurn && !gameOver && moveData) {
                      makeMove(moveData.from, moveData.to);
                    }
                  }}
                  interactive={isPlayerTurn && !gameOver}
                  viewOnly={!isPlayerTurn || gameOver}
                  showDests={true}
                />
              </div>

              {/* Player info bar */}
              <div className="flex items-center justify-between mt-3 p-3 rounded-lg bg-muted/50">
                <div className="flex items-center gap-2">
                  <div className={`w-4 h-4 rounded-full ${selectedColor === "white" ? "bg-white border" : "bg-gray-900"}`} />
                  <span className="font-medium">You</span>
                  {isPlayerTurn && !gameOver && (
                    <Badge className="bg-green-500/20 text-green-500 border-green-500/30">
                      Your turn
                    </Badge>
                  )}
                </div>
                <Badge variant="outline">
                  <Clock className="w-3 h-3 mr-1" />
                  {Math.floor((session?.user_time_remaining || 900) / 60)}:
                  {String(Math.floor((session?.user_time_remaining || 900) % 60)).padStart(2, "0")}
              </Badge>
            </div>

            {/* Controls */}
            <div className="flex items-center justify-center gap-2 mt-4">
              <Button variant="outline" size="sm" onClick={flipBoard}>
                <RotateCcw className="w-4 h-4 mr-1" />
                Flip
              </Button>
              {!gameOver && (
                <Button 
                  variant="destructive" 
                  size="sm" 
                  onClick={resignGame}
                  data-testid="resign-btn"
                >
                  <Flag className="w-4 h-4 mr-1" />
                  Resign
                </Button>
              )}
              {gameOver && (
                <Button 
                  variant="default" 
                  size="sm" 
                  onClick={newGame}
                  data-testid="new-game-btn"
                >
                  <Play className="w-4 h-4 mr-1" />
                  New Game
                </Button>
              )}
            </div>
            </div>
          </div>
        </div>

        {/* Right: Coach Chat Panel */}
        <div className="w-[380px] border-l border-border flex flex-col h-full" data-testid="coach-chat-panel">
          {/* Header */}
          <div className="p-4 border-b border-border">
            <h2 className="text-lg font-bold flex items-center gap-2">
              <Brain className="w-5 h-5 text-primary" />
              Coach Chat
            </h2>
            <p className="text-xs text-muted-foreground mt-1">
              Ask questions anytime. Coach speaks on teachable moments.
            </p>
          </div>
          
          {/* Chat Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3" data-testid="chat-messages">
            {/* Welcome message */}
            {chatMessages.length === 0 && !gameOver && (
              <div className="p-3 rounded-lg bg-primary/10 border border-primary/20">
                <div className="flex items-start gap-2">
                  <Brain className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
                  <div className="text-sm">
                    <p className="font-medium text-primary">Let's play!</p>
                    <p className="text-muted-foreground mt-1">
                      I'll give you feedback on interesting moves. Feel free to ask me anything!
                    </p>
                  </div>
                </div>
              </div>
            )}
            
            {/* Chat history */}
            {chatMessages.map((msg, i) => (
              <div
                key={i}
                className={`p-3 rounded-lg ${
                  msg.type === "coach"
                    ? "bg-primary/10 border border-primary/20"
                    : "bg-muted/50 ml-6"
                }`}
              >
                <div className="flex items-start gap-2">
                  {msg.type === "coach" ? (
                    <Brain className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
                  ) : (
                    <MessageCircle className="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                  )}
                  <div className="text-sm flex-1">
                    {msg.type === "coach" && msg.trigger && (
                      <Badge variant="outline" className="text-xs mb-1 capitalize">
                        {msg.trigger === "encouragement" ? "👏" : 
                         msg.trigger === "warning" ? "⚠️" : 
                         msg.trigger === "teaching" ? "💡" : "💬"} {msg.trigger}
                      </Badge>
                    )}
                    {msg.type === "coach" && msg.move && (
                      <span className="text-xs text-muted-foreground block">
                        After {msg.move}:
                      </span>
                    )}
                    <p className={msg.type === "coach" ? "" : "text-muted-foreground"}>
                      {msg.message}
                    </p>
                  </div>
                </div>
              </div>
            ))}
            
            {/* Loading indicator */}
            {isSendingChat && (
              <div className="p-3 rounded-lg bg-primary/10 border border-primary/20">
                <div className="flex items-center gap-2">
                  <Loader2 className="w-4 h-4 text-primary animate-spin" />
                  <span className="text-sm text-muted-foreground">Coach is thinking...</span>
                </div>
              </div>
            )}
            
            <div ref={chatEndRef} />
          </div>
          
          {/* Game over summary */}
          {gameOver && (
            <div className="p-4 border-t border-border">
              <Card className={`${
                gameResult === "win" ? "border-green-500/30 bg-green-500/5" :
                gameResult === "loss" ? "border-red-500/30 bg-red-500/5" :
                "border-yellow-500/30 bg-yellow-500/5"
              }`}>
                <CardContent className="p-3">
                  <div className="flex items-center gap-2">
                    {gameResult === "win" ? (
                      <Trophy className="w-5 h-5 text-green-500" />
                    ) : gameResult === "loss" ? (
                      <XCircle className="w-5 h-5 text-red-500" />
                    ) : (
                      <CheckCircle2 className="w-5 h-5 text-yellow-500" />
                    )}
                    <span className="font-medium capitalize">{gameResult || "Draw"}</span>
                  </div>
                  {summary && (
                    <p className="text-xs text-muted-foreground mt-1">
                      {summary.total_moves} moves • {Math.floor(summary.duration_seconds / 60)}m
                    </p>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
          
          {/* Chat Input */}
          {!gameOver && (
            <div className="p-4 border-t border-border">
              <div className="flex gap-2">
                <Textarea
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Ask the coach anything..."
                  className="min-h-[60px] max-h-[100px] resize-none"
                  data-testid="chat-input"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey && chatInput.trim()) {
                      e.preventDefault();
                      sendChatMessage();
                    }
                  }}
                />
                <Button
                  size="icon"
                  onClick={sendChatMessage}
                  disabled={!chatInput.trim() || isSendingChat}
                  data-testid="send-chat-btn"
                >
                  {isSendingChat ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                </Button>
              </div>
            </div>
          )}
          
          {/* Move History (collapsed) */}
          <details className="border-t border-border">
            <summary className="p-3 text-sm cursor-pointer hover:bg-muted/50 flex items-center gap-2">
              <Swords className="w-4 h-4" />
              Move History ({session?.move_history?.length || 0} moves)
            </summary>
            <div className="px-3 pb-3 max-h-[150px] overflow-y-auto font-mono text-xs">
              {session?.move_history?.length > 0 ? (
                <div className="space-y-1">
                  {Array.from({ length: Math.ceil(session.move_history.length / 2) }).map((_, i) => {
                    const whiteMove = session.move_history[i * 2];
                    const blackMove = session.move_history[i * 2 + 1];
                    return (
                      <div key={i} className="flex gap-2">
                        <span className="text-muted-foreground w-5">{i + 1}.</span>
                        <span className={whiteMove?.by === "player" ? "text-primary" : ""}>
                          {whiteMove?.move || ""}
                        </span>
                        <span className={blackMove?.by === "player" ? "text-primary" : ""}>
                          {blackMove?.move || ""}
                        </span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-muted-foreground text-center py-2">No moves yet</p>
              )}
            </div>
          </details>
          
          {/* Guardian Status */}
          <div className="p-3 border-t border-border text-xs">
            <ShieldAlert className="w-3 h-3 inline mr-1 text-primary" />
            <span className="text-muted-foreground">
              Guardian: {remainingInterventions} intervention{remainingInterventions !== 1 ? "s" : ""} remaining
            </span>
          </div>
        </div>
      </div>

      {/* Guardian Intervention Modal */}
      {guardianIntervention && pendingMove && (
        <div 
          className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
          data-testid="guardian-intervention-modal"
        >
          <Card className={`max-w-md w-full border-2 ${
            guardianIntervention.risk_level === "critical" ? "border-red-500" :
            guardianIntervention.risk_level === "high" ? "border-orange-500" :
            "border-yellow-500"
          }`}>
            <CardHeader className={`pb-3 ${
              guardianIntervention.risk_level === "critical" ? "bg-red-500/10" :
              guardianIntervention.risk_level === "high" ? "bg-orange-500/10" :
              "bg-yellow-500/10"
            }`}>
              <div className="flex items-center gap-3">
                <AlertTriangle className={`w-8 h-8 ${
                  guardianIntervention.risk_level === "critical" ? "text-red-500" :
                  guardianIntervention.risk_level === "high" ? "text-orange-500" :
                  "text-yellow-500"
                }`} />
                <div>
                  <CardTitle className="text-lg">
                    {guardianIntervention.intervention_type === "block" ? "Wait!" : "Think Again"}
                  </CardTitle>
                  <p className="text-sm text-muted-foreground">
                    Coach Guardian detected a potential mistake
                  </p>
                </div>
              </div>
            </CardHeader>
            <CardContent className="pt-4 space-y-4">
              {/* Warning Message */}
              <div className="text-base font-medium">
                {guardianIntervention.message}
              </div>
              
              {/* Explanation */}
              <p className="text-sm text-muted-foreground">
                {guardianIntervention.explanation}
              </p>
              
              {/* Alternative Moves */}
              {guardianIntervention.alternative_moves?.length > 0 && (
                <div className="p-3 rounded-lg bg-muted/50">
                  <div className="flex items-center gap-2 mb-2 text-sm font-medium">
                    <Lightbulb className="w-4 h-4 text-primary" />
                    Better alternatives:
                  </div>
                  <div className="flex gap-2">
                    {guardianIntervention.alternative_moves.map((move, i) => (
                      <Badge key={i} variant="outline" className="font-mono">
                        {move}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Pending Move */}
              <div className="text-sm text-muted-foreground">
                Your move: <span className="font-mono font-medium text-foreground">{pendingMove.moveSan}</span>
              </div>
              
              {/* Actions */}
              <div className="flex gap-3 pt-2">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={cancelRiskyMove}
                  data-testid="guardian-cancel-btn"
                >
                  <RotateCcw className="w-4 h-4 mr-2" />
                  Choose Different Move
                </Button>
                <Button
                  variant={guardianIntervention.risk_level === "critical" ? "destructive" : "default"}
                  className="flex-1"
                  onClick={confirmRiskyMove}
                  data-testid="guardian-confirm-btn"
                >
                  Play Anyway
                </Button>
              </div>
              
              {/* Interventions remaining */}
              <p className="text-xs text-center text-muted-foreground pt-2">
                {remainingInterventions > 1 
                  ? `${remainingInterventions - 1} intervention${remainingInterventions - 1 !== 1 ? "s" : ""} remaining after this`
                  : "This is your last intervention warning"}
              </p>
            </CardContent>
          </Card>
        </div>
      )}
      
      {/* Reflection Modal - Socratic Coaching */}
      {showReflectionModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50" data-testid="reflection-modal">
          <Card className="w-[500px] max-h-[80vh] overflow-auto border-primary/30 shadow-lg">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-lg">
                <MessageCircle className="w-5 h-5 text-primary" />
                Coach wants to know...
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Move being discussed */}
              <div className="p-3 rounded-lg bg-muted/50">
                <p className="text-sm text-muted-foreground mb-1">You just played:</p>
                <p className="font-mono text-lg font-bold">
                  {session?.move_history?.[reflectionMoveIndex]?.move}
                </p>
              </div>
              
              {/* Coach's question */}
              {!coachFeedback && (
                <>
                  <div className="flex items-start gap-3 p-4 rounded-lg bg-primary/10 border border-primary/20">
                    <Brain className="w-6 h-6 text-primary flex-shrink-0 mt-1" />
                    <div>
                      <p className="font-medium text-primary mb-1">Why did you play this move?</p>
                      <p className="text-sm text-muted-foreground">
                        Tell me what you were thinking. What were you trying to achieve?
                      </p>
                    </div>
                  </div>
                  
                  <Textarea
                    value={reflectionInput}
                    onChange={(e) => setReflectionInput(e.target.value)}
                    placeholder="I played this move because..."
                    className="min-h-[100px]"
                    data-testid="reflection-input"
                    disabled={isGettingFeedback}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey && reflectionInput.trim()) {
                        e.preventDefault();
                        submitReflection();
                      }
                    }}
                  />
                  
                  <div className="flex gap-3">
                    <Button 
                      variant="outline" 
                      className="flex-1"
                      onClick={closeReflection}
                      disabled={isGettingFeedback}
                    >
                      Skip
                    </Button>
                    <Button 
                      className="flex-1"
                      onClick={submitReflection}
                      disabled={!reflectionInput.trim() || isGettingFeedback}
                      data-testid="submit-reflection-btn"
                    >
                      {isGettingFeedback ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Thinking...
                        </>
                      ) : (
                        <>
                          <Send className="w-4 h-4 mr-2" />
                          Tell Coach
                        </>
                      )}
                    </Button>
                  </div>
                </>
              )}
              
              {/* Coach's Feedback */}
              {coachFeedback && (
                <div className="space-y-4" data-testid="coach-feedback">
                  {/* Move Quality Badge */}
                  <div className="flex items-center gap-2">
                    {coachFeedback.move_quality === "brilliant" && <Sparkles className="w-5 h-5 text-purple-500" />}
                    {coachFeedback.move_quality === "great" && <Sparkles className="w-5 h-5 text-green-500" />}
                    {coachFeedback.move_quality === "good" && <CheckCircle2 className="w-5 h-5 text-green-500" />}
                    {coachFeedback.move_quality === "okay" && <CheckCircle2 className="w-5 h-5 text-yellow-500" />}
                    {coachFeedback.move_quality === "inaccuracy" && <AlertTriangle className="w-5 h-5 text-yellow-500" />}
                    {coachFeedback.move_quality === "mistake" && <AlertTriangle className="w-5 h-5 text-orange-500" />}
                    {coachFeedback.move_quality === "blunder" && <XCircle className="w-5 h-5 text-red-500" />}
                    <Badge variant={
                      ["brilliant", "great", "good"].includes(coachFeedback.move_quality) ? "default" :
                      ["okay", "inaccuracy"].includes(coachFeedback.move_quality) ? "secondary" : "destructive"
                    } className="capitalize">
                      {coachFeedback.move_quality}
                    </Badge>
                    {coachFeedback.was_best_move && (
                      <Badge variant="outline" className="bg-green-500/10 text-green-500 border-green-500/30">
                        <Target className="w-3 h-3 mr-1" />
                        Best move!
                      </Badge>
                    )}
                  </div>
                  
                  {/* Main Message */}
                  <div className="p-4 rounded-lg bg-primary/10 border border-primary/20">
                    <div className="flex items-start gap-3">
                      <Brain className="w-6 h-6 text-primary flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="font-medium">{coachFeedback.main_message}</p>
                        {coachFeedback.reasoning_feedback && (
                          <p className="text-sm text-muted-foreground mt-2">
                            {coachFeedback.reasoning_feedback}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  {/* Position Insight */}
                  {coachFeedback.position_insight && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <div className="flex items-center gap-2 mb-1">
                        <Lightbulb className="w-4 h-4 text-yellow-500" />
                        <span className="text-sm font-medium">Position Insight</span>
                      </div>
                      <p className="text-sm text-muted-foreground">{coachFeedback.position_insight}</p>
                    </div>
                  )}
                  
                  {/* Improvement Tip */}
                  {coachFeedback.improvement_tip && (
                    <div className="p-3 rounded-lg bg-orange-500/10 border border-orange-500/20">
                      <div className="flex items-center gap-2 mb-1">
                        <Target className="w-4 h-4 text-orange-500" />
                        <span className="text-sm font-medium text-orange-500">For Next Time</span>
                      </div>
                      <p className="text-sm">{coachFeedback.improvement_tip}</p>
                    </div>
                  )}
                  
                  {/* Opening Comment */}
                  {coachFeedback.opening_name && (
                    <div className="text-xs text-muted-foreground">
                      Opening: {coachFeedback.opening_name}
                    </div>
                  )}
                  
                  {/* Continue Button */}
                  <Button 
                    className="w-full"
                    onClick={closeReflection}
                    data-testid="close-reflection-btn"
                  >
                    {coachFeedback.encouragement ? (
                      <>
                        <ThumbsUp className="w-4 h-4 mr-2" />
                        Got it! Continue
                      </>
                    ) : (
                      <>
                        <ArrowLeft className="w-4 h-4 mr-2" />
                        Continue Playing
                      </>
                    )}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </Layout>
  );
};

export default CoachPlay;
