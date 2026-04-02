/**
 * useCoachGame — Custom hook for Play with Coach game state
 * 
 * Extracted from CoachPlay.jsx to reduce its 77 state variables.
 * Handles: session management, move execution, polling, curriculum feedback.
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { toast } from "sonner";

const API = process.env.REACT_APP_BACKEND_URL + "/api";
const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

const useCoachGame = (user) => {
  // Session
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(false);
  const [gameStarted, setGameStarted] = useState(false);
  const [gameOver, setGameOver] = useState(false);
  const [gameResult, setGameResult] = useState(null);

  // Board
  const [currentFen, setCurrentFen] = useState(START_FEN);
  const [boardOrientation, setBoardOrientation] = useState("white");
  const [lastMove, setLastMove] = useState(null);
  const [isPlayerTurn, setIsPlayerTurn] = useState(true);

  // Settings
  const [selectedColor, setSelectedColor] = useState("white");

  // Coach state
  const [isCoachThinking, setIsCoachThinking] = useState(false);
  const [curriculumFeedback, setCurriculumFeedback] = useState(null);
  const [lastCoachMoveSan, setLastCoachMoveSan] = useState(null);
  const [coachIntroMessage, setCoachIntroMessage] = useState(null);

  // Polling
  const pollRef = useRef(null);

  // Start game
  const startGame = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/coach/play/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ user_color: selectedColor }),
      });
      const data = await res.json();
      if (!data.success) {
        toast.error(data.detail || "Failed to start");
        return;
      }

      setSession(data.session);
      setCurrentFen(data.current_fen || START_FEN);
      setBoardOrientation(selectedColor);
      setIsPlayerTurn(data.is_player_turn);
      setGameStarted(true);
      setGameOver(false);
      setGameResult(null);
      setCurriculumFeedback(null);
      setLastCoachMoveSan(null);

      if (data.message) {
        setCoachIntroMessage(data.message);
      }
    } catch (e) {
      toast.error("Connection error");
    } finally {
      setLoading(false);
    }
  }, [selectedColor]);

  // Play a move
  const playMove = useCallback(async (moveSan) => {
    if (!session?.session_id) return false;

    setCurriculumFeedback(null);
    setIsCoachThinking(true);

    try {
      const res = await fetch(`${API}/coach/play/move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: session.session_id,
          move: moveSan,
        }),
      });
      const data = await res.json();

      if (!res.ok || data.curriculum_redirect) {
        toast.error(data.message || data.detail || "Invalid move");
        setIsCoachThinking(false);
        return false;
      }

      if (data.curriculum_feedback) {
        setCurriculumFeedback(data.curriculum_feedback);
      }

      if (data.current_fen) {
        setCurrentFen(data.current_fen);
      }

      setIsPlayerTurn(false);

      if (data.game_over) {
        setGameOver(true);
        setGameResult(data.result);
        setIsCoachThinking(false);
        return true;
      }

      // Poll for coach response
      if (data.awaiting_coach) {
        startPolling();
      }

      return true;
    } catch (e) {
      toast.error("Connection error");
      setIsCoachThinking(false);
      return false;
    }
  }, [session?.session_id]);

  // Poll for coach move
  const startPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);

    let attempts = 0;
    pollRef.current = setInterval(async () => {
      attempts++;
      if (attempts > 30) {
        clearInterval(pollRef.current);
        setIsCoachThinking(false);
        toast.error("Coach timed out");
        return;
      }

      try {
        const res = await fetch(`${API}/coach/play/state/${session?.session_id}`, {
          credentials: "include",
        });
        const data = await res.json();
        const s = data.session;

        if (!s?.coach_move_pending) {
          clearInterval(pollRef.current);
          setCurrentFen(data.current_fen || s?.current_fen);
          setIsPlayerTurn(true);
          setIsCoachThinking(false);

          // Track coach's last move
          const lcm = s?.last_coach_move;
          if (lcm?.san || lcm?.move) {
            setLastCoachMoveSan(lcm.san || lcm.move);
          }

          if (s?.status === "completed") {
            setGameOver(true);
            setGameResult(s.result);
          }
        }
      } catch {}
    }, 1000);
  }, [session?.session_id]);

  // End game
  const endGame = useCallback(async () => {
    if (!session?.session_id) return;
    try {
      await fetch(`${API}/coach/play/end`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ session_id: session.session_id }),
      });
    } catch {}
    setGameStarted(false);
    setSession(null);
    setCurrentFen(START_FEN);
    setGameOver(false);
    setCurriculumFeedback(null);
    setLastCoachMoveSan(null);
    setCoachIntroMessage(null);
  }, [session?.session_id]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  return {
    // State
    session, loading, gameStarted, gameOver, gameResult,
    currentFen, boardOrientation, lastMove, isPlayerTurn,
    selectedColor, isCoachThinking,
    curriculumFeedback, lastCoachMoveSan, coachIntroMessage,

    // Setters
    setSelectedColor, setBoardOrientation, setCurrentFen,

    // Actions
    startGame, playMove, endGame,
  };
};

export default useCoachGame;
