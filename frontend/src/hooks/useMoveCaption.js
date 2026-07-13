/**
 * useMoveCaption — Fetch unified teaching captions for game moves
 *
 * Uses the central game_decryption_v5 pipeline (same as review pages).
 * Captions include full game context: trap history, patterns, opening detection.
 */

import { useState, useCallback } from "react";
import { API } from "@/App";

export default function useMoveCaption() {
  const [caption, setCaption] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchCaption = useCallback(async (gameId, moveNumber) => {
    setLoading(true);
    setError(null);
    setCaption(null);

    try {
      const response = await fetch(
        `${API}/move-eval/teaching-caption`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            game_id: gameId,
            move_number: moveNumber,
          }),
        }
      );

      if (response.ok) {
        const data = await response.json();
        setCaption(data);
      } else {
        setError(`Failed to fetch caption (${response.status})`);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  return { caption, loading, error, fetchCaption };
}
