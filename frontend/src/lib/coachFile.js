/**
 * The player file, read once and shared by every coach page.
 *
 * docs/coach_pages_scope.md. Home, Learn, Progress and the academy view all
 * read the same server document (GET /coach-file, or the academy's
 * /academy/student/:id/coach-file), so they never disagree and none of them
 * computes anything. The first visit may answer {state: "building"}: the
 * server makes the file in the background, so ask again shortly.
 */
import { useEffect, useState } from "react";

import { API } from "@/App";

const POLL_MS = 6000;
const MAX_POLLS = 10;
const cache = new Map();

export function useCoachFile(path = "/coach-file", enabled = true) {
  const [data, setData] = useState(() => cache.get(path) || null);

  useEffect(() => {
    if (!enabled) return undefined;
    let alive = true;
    let polls = 0;
    let timer = null;
    const load = async () => {
      try {
        const res = await fetch(`${API}${path}`, { credentials: "include" });
        if (!alive || !res.ok) return;
        const body = await res.json();
        if (!alive) return;
        if (body?.state === "ready") cache.set(path, body);
        setData(body);
        if (body?.enabled && body.state === "building" && polls < MAX_POLLS) {
          polls += 1;
          timer = setTimeout(load, POLL_MS);
        }
      } catch {
        /* A page must render without the file. */
      }
    };
    load();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [path, enabled]);

  return enabled ? data : null;
}

/** Start Play with Coach from a position of his own games (practice mode). */
export function playFrom(position, navigate) {
  if (!position?.fen) return;
  try {
    sessionStorage.setItem(
      "practice_position",
      JSON.stringify({
        fen: position.fen,
        userColor: position.user_color || position.color || "white",
        source: "coach_file",
        gameId: position.source_game_id || position.game_id || null,
      }),
    );
  } catch {
    /* private mode: the game still starts, from the normal position */
  }
  navigate("/play-with-coach?mode=practice");
}
