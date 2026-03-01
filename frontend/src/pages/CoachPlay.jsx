/**
 * CoachPlay.jsx - Play With Coach Feature (P2)
 * 
 * A training mode where users play full games against a pedagogical coach engine.
 * 
 * Step 1: Basic playable game with session management.
 * Later phases will add: Pre-move guardian, behavior extraction, CPR, identity.
 */

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
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
  Lightbulb
} from "lucide-react";

// Convert FEN to position object for react-chessboard
const fenToPositionObject = (fen) => {
  const position = {};
  const parts = fen.split(" ");
  const rows = parts[0].split("/");

  for (let row = 0; row < 8; row++) {
    let col = 0;
    for (const char of rows[row]) {
      if (char >= "1" && char <= "8") {
        col += parseInt(char);
      } else {
        const file = String.fromCharCode(97 + col);
        const rank = 8 - row;
        const square = file + rank;
        const color = char === char.toUpperCase() ? "w" : "b";
        const piece = char.toUpperCase();
        position[square] = color + piece;
        col++;
      }
    }
  }
  return position;
};

const CoachPlay = ({ user }) => {
  const navigate = useNavigate();
  
  // Session state
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(false);
  const [gameStarted, setGameStarted] = useState(false);
  
  // Board state
  const [position, setPosition] = useState({});
  const [currentFen, setCurrentFen] = useState("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  const [boardOrientation, setBoardOrientation] = useState("white");
  const [lastMoveSquares, setLastMoveSquares] = useState({});
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
        setPosition(fenToPositionObject(data.current_fen));
        setBoardOrientation(data.session.user_color);
        setSelectedColor(data.session.user_color);
        setIsPlayerTurn(data.is_player_turn);
        setGameStarted(true);
        setGameOver(data.game_over);
        
        // Highlight last move
        if (data.session.move_history?.length > 0) {
          const lastMove = data.session.move_history[data.session.move_history.length - 1];
          if (lastMove.uci) {
            const from = lastMove.uci.slice(0, 2);
            const to = lastMove.uci.slice(2, 4);
            setLastMoveSquares({
              [from]: { backgroundColor: "rgba(255, 255, 0, 0.4)" },
              [to]: { backgroundColor: "rgba(255, 255, 0, 0.4)" }
            });
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
      setPosition(fenToPositionObject(data.current_fen));
      setBoardOrientation(selectedColor);
      setIsPlayerTurn(data.is_player_turn);
      setGameStarted(true);
      setMoveStartTime(Date.now());
      
      // If playing black, coach already made first move
      if (selectedColor === "black" && data.session.move_history?.length > 0) {
        const coachMove = data.session.move_history[0];
        highlightMove(coachMove.uci);
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
    setLastMoveSquares({
      [from]: { backgroundColor: "rgba(255, 255, 0, 0.4)" },
      [to]: { backgroundColor: "rgba(255, 255, 0, 0.4)" }
    });
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

      // Check if game is over
      if (data.game_over) {
        setGameOver(true);
        setGameResult(data.result);
        setCurrentFen(data.session.current_fen);
        setPosition(fenToPositionObject(data.session.current_fen));
        
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
        setPosition(fenToPositionObject(data.session.current_fen));
        highlightMove(data.coach_move.uci);
        
        if (data.game_over) {
          setGameOver(true);
          setGameResult(data.result);
        } else {
          setIsPlayerTurn(true);
          setMoveStartTime(Date.now());
        }
      }

      return true;
    } catch (error) {
      console.error("Move error:", error);
      toast.error("Connection error. Please try again.");
      return false;
    }
  };

  // Handle user confirming a risky move
  const confirmRiskyMove = async () => {
    if (!pendingMove) return;
    
    const { moveSan, timeSpent, riskType, chess } = pendingMove;
    
    // Update board
    setPosition(fenToPositionObject(chess.fen()));
    setCurrentFen(chess.fen());
    setIsPlayerTurn(false);
    
    // Clear intervention state
    setGuardianIntervention(null);
    setPendingMove(null);
    
    // Execute with override
    const success = await executeMove(moveSan, timeSpent, true, riskType);
    
    if (!success) {
      // Revert
      setPosition(fenToPositionObject(currentFen));
      setIsPlayerTurn(true);
    }
  };

  // Handle user canceling a risky move
  const cancelRiskyMove = () => {
    setGuardianIntervention(null);
    setPendingMove(null);
    // Board already shows current position, no need to revert
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
      setGuardianIntervention(guardianResult);
      setPendingMove({
        moveSan: moveObj.san,
        moveObj: moveObj,
        timeSpent: timeSpent,
        riskType: guardianResult.risk_type,
        chess: chess
      });
      return false; // Don't complete the move yet
    }

    // No intervention needed - proceed with move
    setPosition(fenToPositionObject(chess.fen()));
    setCurrentFen(chess.fen());
    setIsPlayerTurn(false);
    highlightMove(moveObj.from + moveObj.to);

    const success = await executeMove(moveObj.san, timeSpent);
    
    if (!success) {
      // Revert
      setPosition(fenToPositionObject(currentFen));
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
    setPosition(fenToPositionObject("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"));
    setLastMoveSquares({});
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
        {/* Left: Board */}
        <div className="flex-1 flex flex-col items-center justify-center p-4">
          <div className="w-full max-w-[560px]">
            {/* Coach info bar */}
            <div className="flex items-center justify-between mb-3 p-3 rounded-lg bg-muted/50">
              <div className="flex items-center gap-2">
                <Brain className="w-5 h-5 text-primary" />
                <span className="font-medium">Coach</span>
              </div>
              <Badge variant="outline">
                <Clock className="w-3 h-3 mr-1" />
                {Math.floor((session?.coach_time_remaining || 900) / 60)}:
                {String(Math.floor((session?.coach_time_remaining || 900) % 60)).padStart(2, "0")}
              </Badge>
            </div>

            {/* Chessboard */}
            <Chessboard
              position={position}
              onPieceDrop={makeMove}
              boardOrientation={boardOrientation}
              customSquareStyles={lastMoveSquares}
              arePiecesDraggable={isPlayerTurn && !gameOver}
              customBoardStyle={{
                borderRadius: "8px",
                boxShadow: "0 4px 20px rgba(0,0,0,0.3)"
              }}
            />

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

        {/* Right: Game Info Panel */}
        <div className="w-[350px] border-l border-border p-4 flex flex-col">
          <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
            <Swords className="w-5 h-5" />
            Game Info
          </h2>

          {/* Game status */}
          {gameOver ? (
            <Card className={`mb-4 ${gameResult === "win" ? "border-green-500/30" : gameResult === "loss" ? "border-red-500/30" : "border-yellow-500/30"}`}>
              <CardContent className="p-4">
                <div className="flex items-center gap-3 mb-3">
                  {gameResult === "win" ? (
                    <>
                      <Trophy className="w-8 h-8 text-green-500" />
                      <div>
                        <p className="font-bold text-green-500">Victory!</p>
                        <p className="text-sm text-muted-foreground">Great game!</p>
                      </div>
                    </>
                  ) : gameResult === "loss" ? (
                    <>
                      <XCircle className="w-8 h-8 text-red-500" />
                      <div>
                        <p className="font-bold text-red-500">Defeat</p>
                        <p className="text-sm text-muted-foreground">
                          {session?.termination_reason || "Keep practicing!"}
                        </p>
                      </div>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-8 h-8 text-yellow-500" />
                      <div>
                        <p className="font-bold text-yellow-500">Draw</p>
                        <p className="text-sm text-muted-foreground">
                          {session?.termination_reason}
                        </p>
                      </div>
                    </>
                  )}
                </div>
                
                {summary && (
                  <div className="space-y-2 text-sm border-t pt-3">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Total Moves</span>
                      <span className="font-medium">{summary.total_moves}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Avg Time/Move</span>
                      <span className="font-medium">{summary.avg_time_per_move}s</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Duration</span>
                      <span className="font-medium">
                        {Math.floor(summary.duration_seconds / 60)}m {Math.floor(summary.duration_seconds % 60)}s
                      </span>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card className="mb-4">
              <CardContent className="p-4">
                <p className="text-sm text-muted-foreground">
                  {isPlayerTurn ? "Your turn to move" : "Coach is thinking..."}
                </p>
              </CardContent>
            </Card>
          )}

          {/* Move History */}
          <div className="flex-1 overflow-hidden">
            <h3 className="text-sm font-medium mb-2">Move History</h3>
            <div className="bg-muted/30 rounded-lg p-3 h-[300px] overflow-y-auto font-mono text-sm">
              {session?.move_history?.length > 0 ? (
                <div className="space-y-1">
                  {Array.from({ length: Math.ceil(session.move_history.length / 2) }).map((_, i) => {
                    const whiteMove = session.move_history[i * 2];
                    const blackMove = session.move_history[i * 2 + 1];
                    return (
                      <div key={i} className="flex gap-2">
                        <span className="text-muted-foreground w-6">{i + 1}.</span>
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
                <p className="text-muted-foreground text-center py-4">
                  No moves yet
                </p>
              )}
            </div>
          </div>

          {/* Guardian Status */}
          <div className="mt-4 p-3 rounded-lg bg-primary/5 border border-primary/20 text-xs">
            <ShieldAlert className="w-3 h-3 inline mr-1 text-primary" />
            <span className="text-muted-foreground">
              Guardian active: {remainingInterventions} intervention{remainingInterventions !== 1 ? "s" : ""} remaining
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
    </Layout>
  );
};

export default CoachPlay;
