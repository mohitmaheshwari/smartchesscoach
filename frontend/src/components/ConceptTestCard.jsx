/**
 * ConceptTestCard — the proof step.
 *
 * docs/teaching_loop_scope.md
 *
 * The review teaches a concept. This is where the player proves he
 * understood it, on five positions he has not seen. Passing is what moves
 * him on — not a self-report button, and not a clean streak that might only
 * mean the concept stopped coming up.
 *
 * Voice rules that apply here: plain words, one idea per sentence, no chess
 * jargon, and failing is never a scoreboard. A miss routes him back to
 * teaching, it does not tell him off.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Chess } from "chess.js";
import LichessBoard from "@/components/LichessBoard";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const API = process.env.REACT_APP_BACKEND_URL || "";

const STATE_IDLE = "idle";
const STATE_LOADING = "loading";
const STATE_TESTING = "testing";
const STATE_SUBMITTING = "submitting";
const STATE_DONE = "done";
const STATE_DISMISSED = "dismissed";

export default function ConceptTestCard({ conceptId, conceptText }) {
  const [phase, setPhase] = useState(STATE_IDLE);
  const [shouldOffer, setShouldOffer] = useState(false);
  const [test, setTest] = useState(null);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Ask the server whether this concept is still worth testing. It says no
  // once he has proven it, or once he has said "not now" twice — we offer,
  // we do not nag.
  useEffect(() => {
    if (!conceptId) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(
          `${API}/api/coach/concept-test/${encodeURIComponent(conceptId)}/offer`,
          { credentials: "include" },
        );
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled) setShouldOffer(Boolean(data.should_offer));
      } catch {
        /* silent: the card simply does not appear */
      }
    })();
    return () => { cancelled = true; };
  }, [conceptId]);

  const start = useCallback(async () => {
    setPhase(STATE_LOADING);
    setError(null);
    try {
      const res = await fetch(
        `${API}/api/coach/concept-test/${encodeURIComponent(conceptId)}`,
        { credentials: "include" },
      );
      if (!res.ok) {
        setError("We don't have enough positions for this one yet.");
        setPhase(STATE_IDLE);
        return;
      }
      const data = await res.json();
      setTest(data);
      setAnswers([]);
      setIndex(0);
      setPhase(STATE_TESTING);
    } catch {
      setError("Couldn't load the positions. Try again in a moment.");
      setPhase(STATE_IDLE);
    }
  }, [conceptId]);

  const decline = useCallback(async () => {
    setPhase(STATE_DISMISSED);
    try {
      await fetch(
        `${API}/api/coach/concept-test/${encodeURIComponent(conceptId)}/decline`,
        { method: "POST", credentials: "include" },
      );
    } catch {
      /* declining is best-effort; the UI has already moved on */
    }
  }, [conceptId]);

  const submit = useCallback(async (finalAnswers) => {
    setPhase(STATE_SUBMITTING);
    try {
      const res = await fetch(
        `${API}/api/coach/concept-test/${encodeURIComponent(test.test_id)}/submit`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ answers: finalAnswers }),
        },
      );
      const data = await res.json();
      setResult(data);
      setPhase(STATE_DONE);
    } catch {
      setError("Couldn't save your answers. Nothing was lost — try again.");
      setPhase(STATE_TESTING);
    }
  }, [test]);

  const onMove = useCallback((move) => {
    if (phase !== STATE_TESTING || !move) return;
    const uci = `${move.from}${move.to}${move.promotion || ""}`;
    const next = [...answers, uci];
    setAnswers(next);
    if (next.length >= (test?.positions?.length || 0)) {
      submit(next);
    } else {
      setIndex(next.length);
    }
  }, [phase, answers, test, submit]);

  const position = test?.positions?.[index];
  const total = test?.positions?.length || 0;

  // The side to move is the side he is being asked to play.
  const orientation = useMemo(() => {
    if (!position?.fen) return "white";
    try {
      return new Chess(position.fen).turn() === "w" ? "white" : "black";
    } catch {
      return "white";
    }
  }, [position]);

  if (!conceptId || phase === STATE_DISMISSED) return null;
  if (phase === STATE_IDLE && !shouldOffer) return null;

  return (
    <Card className="border-amber-300 dark:border-amber-700 bg-amber-50/60 dark:bg-amber-950/20">
      <CardContent className="p-5 space-y-4">

        {(phase === STATE_IDLE || phase === STATE_LOADING) && (
          <>
            <p className="text-sm text-gray-700 dark:text-gray-200 leading-relaxed">
              {conceptText
                || "This one came up again in your game."}
            </p>
            {error && (
              <p className="text-sm text-amber-700 dark:text-amber-400">{error}</p>
            )}
            <div className="flex items-center gap-3">
              <Button onClick={start} disabled={phase === STATE_LOADING}>
                {phase === STATE_LOADING ? "Setting up…" : "Test me on this — 5 positions"}
              </Button>
              <button
                onClick={decline}
                className="text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
              >
                Not now
              </button>
            </div>
          </>
        )}

        {(phase === STATE_TESTING || phase === STATE_SUBMITTING) && position && (
          <>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
                Position {index + 1} of {total}
              </span>
              <span className="text-xs text-gray-500">
                {orientation === "white" ? "You are White" : "You are Black"}
              </span>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-300">
              Find the best move. Just play it on the board.
            </p>
            <div className="max-w-[360px]">
              <LichessBoard
                fen={position.fen}
                orientation={orientation}
                onMove={onMove}
                interactive={phase === STATE_TESTING}
              />
            </div>
            {phase === STATE_SUBMITTING && (
              <p className="text-sm text-gray-500">Checking your answers…</p>
            )}
          </>
        )}

        {phase === STATE_DONE && result && (
          <>
            <p className="text-lg font-semibold text-gray-900 dark:text-gray-50">
              {result.score} out of {result.out_of}.
            </p>
            {result.passed ? (
              <p className="text-sm text-gray-700 dark:text-gray-200 leading-relaxed">
                You've got it. We'll stop bringing this up, and just keep an
                eye on it in your next games.
              </p>
            ) : (
              <div className="space-y-3">
                <p className="text-sm text-gray-700 dark:text-gray-200 leading-relaxed">
                  Not yet — and that's useful to know. Let's look at this one
                  again rather than move on.
                </p>
                {result.review_position && (
                  <div className="space-y-2">
                    <p className="text-sm text-gray-600 dark:text-gray-300">
                      Here the move was{" "}
                      <span className="font-mono font-medium">
                        {result.review_position.solution_san}
                      </span>.
                    </p>
                    <div className="max-w-[300px]">
                      <LichessBoard
                        fen={result.review_position.fen}
                        interactive={false}
                      />
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}

      </CardContent>
    </Card>
  );
}
