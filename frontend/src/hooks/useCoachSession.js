/**
 * useCoachSession - Custom hook for managing Play With Coach session
 * 
 * Extracts session state management logic from CoachPlay.jsx
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { API } from "@/App";
import { toast } from "sonner";

export const useCoachSession = () => {
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
  
  // Timer
  const [moveStartTime, setMoveStartTime] = useState(null);
  
  // Game over state
  const [gameOver, setGameOver] = useState(false);
  const [gameResult, setGameResult] = useState(null);
  const [summary, setSummary] = useState(null);
  
  // Evaluation
  const [evaluation, setEvaluation] = useState({ score: 0.0, mate_in: null });
  
  // Practice mode
  const [practiceMode, setPracticeMode] = useState(false);
  const [practicePosition, setPracticePosition] = useState(null);
  
  // Guardian state
  const [guardianIntervention, setGuardianIntervention] = useState(null);
  const [pendingMove, setPendingMove] = useState(null);
  const [remainingInterventions, setRemainingInterventions] = useState(3);
  
  // Coach thinking
  const [coachThinking, setCoachThinking] = useState(false);
  const [thinkingMessage, setThinkingMessage] = useState("");
  
  // Move feedback
  const [moveFeedback, setMoveFeedback] = useState(null);
  const [loadingFeedback, setLoadingFeedback] = useState(false);
  
  // Blunder counter
  const [blundersThisGame, setBlundersThisGame] = useState(0);
  
  /**
   * Start a new game with the coach
   */
  const startGame = useCallback(async (options = {}) => {
    const { color = selectedColor, position = null } = options;
    
    setLoading(true);
    setGameOver(false);
    setGameResult(null);
    setSummary(null);
    setBlundersThisGame(0);
    setMoveFeedback(null);
    
    try {
      const body = { user_color: color };
      
      if (position) {
        body.starting_fen = position;
        body.practice_mode = true;
        setPracticeMode(true);
        setPracticePosition(position);
      }
      
      const res = await fetch(`${API}/coach/play/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(body)
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to start game");
      }
      
      const data = await res.json();
      
      setSession(data.session);
      setCurrentFen(data.current_fen);
      setBoardOrientation(color);
      setIsPlayerTurn(data.is_player_turn);
      setEvaluation(data.evaluation || { score: 0.0, mate_in: null });
      setGameStarted(true);
      setLastMove(null);
      setMoveStartTime(Date.now());
      
      return data;
      
    } catch (err) {
      console.error("Error starting game:", err);
      toast.error(err.message || "Failed to start game");
      return null;
    } finally {
      setLoading(false);
    }
  }, [selectedColor]);
  
  /**
   * End the current game (resign)
   */
  const resignGame = useCallback(async () => {
    if (!session?.session_id) return;
    
    try {
      const res = await fetch(`${API}/coach/play/end`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: session.session_id,
          reason: "resigned"
        })
      });
      
      if (res.ok) {
        const data = await res.json();
        setGameOver(true);
        setGameResult("resigned");
        setSummary(data.summary);
        return data;
      }
    } catch (err) {
      console.error("Error resigning:", err);
      toast.error("Failed to resign game");
    }
  }, [session]);
  
  /**
   * Reset the session for a new game
   */
  const resetSession = useCallback(() => {
    setSession(null);
    setGameStarted(false);
    setCurrentFen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
    setLastMove(null);
    setIsPlayerTurn(true);
    setGameOver(false);
    setGameResult(null);
    setSummary(null);
    setBlundersThisGame(0);
    setPracticeMode(false);
    setPracticePosition(null);
    setMoveFeedback(null);
    setGuardianIntervention(null);
    setPendingMove(null);
  }, []);
  
  /**
   * Fetch move feedback for the current session
   */
  const fetchMoveFeedback = useCallback(async () => {
    if (!session?.session_id) return;
    
    setLoadingFeedback(true);
    
    try {
      const res = await fetch(
        `${API}/coach/play/move-feedback/${session.session_id}`,
        { credentials: "include" }
      );
      
      if (res.ok) {
        const data = await res.json();
        if (data.feedback) {
          setMoveFeedback(data.feedback);
          
          // Track blunders
          if (data.feedback.move_quality === "blunder") {
            setBlundersThisGame(prev => prev + 1);
          }
        }
      }
    } catch (err) {
      console.error("Error fetching move feedback:", err);
    } finally {
      setLoadingFeedback(false);
    }
  }, [session]);
  
  /**
   * Evaluate a move before making it (Pre-Move Guardian)
   */
  const evaluateMove = useCallback(async (move) => {
    if (!session?.session_id) return null;
    
    try {
      const res = await fetch(`${API}/coach/play/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: session.session_id,
          move: move
        })
      });
      
      if (res.ok) {
        const data = await res.json();
        return data;
      }
    } catch (err) {
      console.error("Error evaluating move:", err);
    }
    return null;
  }, [session]);
  
  /**
   * Confirm a risky move after guardian warning
   */
  const confirmRiskyMove = useCallback(async (move, riskLevel) => {
    if (!session?.session_id) return;
    
    try {
      const res = await fetch(`${API}/coach/play/move/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: session.session_id,
          move: move,
          risk_level: riskLevel
        })
      });
      
      if (res.ok) {
        const data = await res.json();
        setRemainingInterventions(data.remaining_interventions);
        return data;
      }
    } catch (err) {
      console.error("Error confirming move:", err);
    }
  }, [session]);
  
  return {
    // State
    session,
    loading,
    gameStarted,
    currentFen,
    boardOrientation,
    lastMove,
    isPlayerTurn,
    selectedColor,
    timeControl,
    moveStartTime,
    gameOver,
    gameResult,
    summary,
    evaluation,
    practiceMode,
    practicePosition,
    guardianIntervention,
    pendingMove,
    remainingInterventions,
    coachThinking,
    thinkingMessage,
    moveFeedback,
    loadingFeedback,
    blundersThisGame,
    
    // Setters
    setSession,
    setCurrentFen,
    setBoardOrientation,
    setLastMove,
    setIsPlayerTurn,
    setSelectedColor,
    setTimeControl,
    setMoveStartTime,
    setGameOver,
    setGameResult,
    setSummary,
    setEvaluation,
    setGuardianIntervention,
    setPendingMove,
    setRemainingInterventions,
    setCoachThinking,
    setThinkingMessage,
    setMoveFeedback,
    setBlundersThisGame,
    
    // Actions
    startGame,
    resignGame,
    resetSession,
    fetchMoveFeedback,
    evaluateMove,
    confirmRiskyMove,
  };
};

export default useCoachSession;
