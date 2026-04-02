/**
 * usePlayerData — Pre-game data fetching, streak tracking, development tracking
 *
 * Manages data that lives outside the active game session:
 * past games history, player identity, streak data, castling/development tracking.
 */

import { useState, useEffect, useCallback } from "react";
import { API } from "@/App";

const usePlayerData = ({ user, session, gameOver, selectedColor }) => {
  // ── Pre-game data ──
  const [pastGamesHistory, setPastGamesHistory] = useState(null);
  const [playerIdentityData, setPlayerIdentityData] = useState(null);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // ── Emotional state ──
  const [blundersThisGame, setBlundersThisGame] = useState(0);
  const [recentResults, setRecentResults] = useState([]);

  // ── Streak ──
  const [streakData, setStreakData] = useState(null);
  const [showPreGameStreakPopup, setShowPreGameStreakPopup] = useState(false);
  const [showPostGameStreakResult, setShowPostGameStreakResult] = useState(false);
  const [postGameStreakResult, setPostGameStreakResult] = useState(null);

  // ── Development tracking (pre-move checklist) ──
  const [hasCastled, setHasCastled] = useState(false);
  const [developedPieces, setDevelopedPieces] = useState(0);
  const [playerWeaknesses, setPlayerWeaknesses] = useState([]);
  const [showChecklist, setShowChecklist] = useState(true);

  // ── Pedagogical opponent ──
  const [hideEvalBar, setHideEvalBar] = useState(false);
  const [opportunitiesFound, setOpportunitiesFound] = useState(0);
  const [opportunitiesMissed, setOpportunitiesMissed] = useState(0);

  // ── Fetch past games + identity + streak on mount ──
  const fetchPastGamesAndIdentity = useCallback(async () => {
    setLoadingHistory(true);
    try {
      const [historyRes, identityRes, streakRes] = await Promise.all([
        fetch(`${API}/coach/play/history?limit=5`, { credentials: "include" }),
        fetch(`${API}/coach/play/identity`, { credentials: "include" }),
        fetch(`${API}/streak/status?user_id=${user?.user_id}`, {
          credentials: "include",
        }),
      ]);

      if (historyRes.ok) {
        const historyData = await historyRes.json();
        setPastGamesHistory(historyData);
      }

      if (identityRes.ok) {
        const identityData = await identityRes.json();
        if (identityData.has_identity) {
          setPlayerIdentityData(identityData.identity);
          if (identityData.identity?.behavioral_patterns) {
            const weaknesses = identityData.identity.behavioral_patterns
              .filter((p) => p.pattern && p.frequency >= 2)
              .map((p) => p.pattern);
            setPlayerWeaknesses(weaknesses);
          }
        }
      }

      if (streakRes.ok) {
        const data = await streakRes.json();
        setStreakData(data);

        const focusToWeakness = {
          THREAT_VERIFICATION: "hope_chess",
          FORCING_BLIND: "missed_tactics",
          STOPPED_CALCULATION_EARLY: "impulsive_play",
          HANGING_PIECE: "hanging_pieces",
          TACTICAL_MISS: "missed_tactics",
        };

        const focusMistake = data.focus_mistake_type;
        const mappedWeakness = focusToWeakness[focusMistake];

        if (mappedWeakness) {
          setPlayerWeaknesses((prev) => [
            mappedWeakness,
            ...prev.filter((w) => w !== mappedWeakness),
          ]);
        }
      }
    } catch (error) {
      console.error("Error fetching coach play history:", error);
    } finally {
      setLoadingHistory(false);
    }
  }, [user?.user_id]);

  useEffect(() => {
    fetchPastGamesAndIdentity();
  }, [fetchPastGamesAndIdentity]);

  // ── Fetch streak result after game ends ──
  const fetchStreakResultAfterGame = useCallback(async () => {
    if (!session?.session_id || !user?.user_id) return;

    try {
      const response = await fetch(
        `${API}/streak/status?user_id=${user.user_id}`,
        { credentials: "include" }
      );

      if (response.ok) {
        const data = await response.json();
        const hadMistake = data.last_game_had_mistake;
        const currentStreak = data.current_streak || 0;
        const bestStreak = data.best_streak || 0;

        let result;
        if (hadMistake) {
          result = {
            result: "broken",
            headline: "Streak Broken",
            message:
              "You repeated your core mistake. This is exactly why you're stuck.",
            streak: 0,
            best: bestStreak,
            previous_streak: currentStreak,
            tone: "warning",
          };
        } else if (currentStreak > 0) {
          result = {
            result:
              currentStreak === bestStreak ? "new_best" : "continued",
            headline:
              currentStreak === bestStreak
                ? `New Best: ${currentStreak} Games!`
                : `Streak: ${currentStreak} Games`,
            message: "Clean game. This is how your rating improves.",
            streak: currentStreak,
            best: bestStreak,
            tone: currentStreak === bestStreak ? "celebration" : "success",
          };
        }

        if (result) {
          setPostGameStreakResult(result);
          setShowPostGameStreakResult(true);
        }
      }
    } catch (error) {
      console.error("Error fetching streak result:", error);
    }
  }, [session?.session_id, user?.user_id]);

  useEffect(() => {
    if (gameOver && session && user?.user_id && !postGameStreakResult) {
      setTimeout(fetchStreakResultAfterGame, 1500);
    }
  }, [gameOver, session?.session_id]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Track castling and development from move history ──
  useEffect(() => {
    if (!session?.move_history) return;

    const moves = session.move_history.map((m) => m.move);
    const userMoves = moves.filter((_, i) => {
      const isWhite = i % 2 === 0;
      return (
        (selectedColor === "white" && isWhite) ||
        (selectedColor === "black" && !isWhite)
      );
    });

    const castled = userMoves.some((m) => m === "O-O" || m === "O-O-O");
    setHasCastled(castled);

    const knightMoves = userMoves.filter((m) => m.startsWith("N")).length;
    const bishopMoves = userMoves.filter((m) => m.startsWith("B")).length;
    const developed = Math.min(knightMoves, 2) + Math.min(bishopMoves, 2);
    setDevelopedPieces(developed);

    if (moves.length === 0) {
      setShowChecklist(true);
    }
  }, [session?.move_history, selectedColor]);

  // ── Reset for new game ──
  const resetPlayerData = useCallback(() => {
    setBlundersThisGame(0);
    setHasCastled(false);
    setDevelopedPieces(0);
    setShowChecklist(true);
  }, []);

  return {
    // Pre-game
    pastGamesHistory,
    playerIdentityData,
    loadingHistory,
    // Emotional
    blundersThisGame,
    setBlundersThisGame,
    recentResults,
    // Streak
    streakData,
    showPreGameStreakPopup,
    setShowPreGameStreakPopup,
    showPostGameStreakResult,
    setShowPostGameStreakResult,
    postGameStreakResult,
    // Development tracking
    hasCastled,
    developedPieces,
    playerWeaknesses,
    setPlayerWeaknesses,
    showChecklist,
    setShowChecklist,
    // Pedagogical
    hideEvalBar,
    setHideEvalBar,
    opportunitiesFound,
    setOpportunitiesFound,
    opportunitiesMissed,
    setOpportunitiesMissed,
    // Utilities
    resetPlayerData,
  };
};

export default usePlayerData;
