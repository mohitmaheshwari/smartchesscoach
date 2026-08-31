/**
 * Daily Fix — Timed Rush-Test Drill (docs/daily_fix_scope.md)
 *
 * The drillable form of a time_management focus: replay positions the user
 * played too fast and blundered, on a clock, and prove they can find the move
 * when they slow down. Data comes from GET /api/daily-fix/today (rush_test);
 * completion posts to /api/daily-fix/complete to advance the practice streak.
 */
import { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Flame, ArrowRight, Clock } from "lucide-react";

export default function DailyFixDrill({ user }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [drills, setDrills] = useState([]);
  const [idx, setIdx] = useState(0);
  const [phase, setPhase] = useState("solving"); // solving | correct | wrong | done
  const [elapsed, setElapsed] = useState(0);
  const [streakResult, setStreakResult] = useState(null);
  const [boardFen, setBoardFen] = useState(null);
  const [completionError, setCompletionError] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API}/daily-fix/today`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          setDrills(data.drill_type === "rush_test" ? data.drills || [] : []);
        }
      } catch (e) {
        console.error("daily-fix drill load failed:", e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const drill = drills[idx];

  // Keep the board on the drill's start position; reset when the drill changes.
  useEffect(() => {
    if (drill?.fen) setBoardFen(drill.fen);
  }, [idx, drill]);

  // Clock runs while the user is solving the current position.
  useEffect(() => {
    if (phase !== "solving" || !drill) return;
    setElapsed(0);
    const t = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(t);
  }, [phase, idx, drill]);

  const orientation = useMemo(() => {
    if (!drill?.fen) return "white";
    return drill.fen.split(" ")[1] === "b" ? "black" : "white";
  }, [drill]);

  const onDrop = useCallback(
    (source, target) => {
      if (!drill || phase !== "solving") return false;
      let uci, newFen;
      try {
        const g = new Chess(drill.fen);
        const mv = g.move({ from: source, to: target, promotion: "q" }); // chess.js v1 throws on illegal
        uci = (mv.from + mv.to + (mv.promotion || "")).toLowerCase();
        newFen = g.fen();
      } catch (e) {
        return false; // illegal move — reject the drop (piece snaps back, correct)
      }
      setBoardFen(newFen); // reflect the move so the piece STAYS on the board
      fetch(`${API}/training/puzzle-attempt`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            puzzle_id: drill.puzzle_id,
            played_uci: uci,
            time_taken_ms: elapsed * 1000,
            moves_tried: [uci],
          }),
        })
        .then((response) => {
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          return response.json();
        })
        .then((grade) => setPhase(grade.correct ? "correct" : "wrong"))
        .catch((error) => {
          console.error("daily-fix grade failed:", error);
          setBoardFen(drill.fen);
          setPhase("solving");
        });
      return true;
    },
    [drill, phase, elapsed]
  );

  const next = useCallback(async () => {
    if (idx + 1 < drills.length) {
      setIdx(idx + 1);
      setPhase("solving");
      return;
    }
    try {
      const res = await fetch(`${API}/daily-fix/complete`, { method: "POST", credentials: "include" });
      if (!res.ok) {
        const problem = await res.json().catch(() => ({}));
        throw new Error(problem.detail || `HTTP ${res.status}`);
      }
      setStreakResult((await res.json()).streak);
      setPhase("done");
    } catch (e) {
      console.error("daily-fix complete failed:", e);
      setCompletionError(e.message || "The coach could not verify completion yet.");
    }
  }, [idx, drills.length]);

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="w-6 h-6 border-2 border-amber-400/30 border-t-amber-400 rounded-full animate-spin" />
        </div>
      </Layout>
    );
  }

  if (!drills.length) {
    return (
      <Layout user={user}>
        <div className="experience-page experience-learning-page experience-daily-page max-w-[620px] mx-auto px-6 py-16 text-center" data-testid="daily-fix-empty">
          <p className="text-[15px] text-muted-foreground">
            No timed drills ready right now. Play or import a few more games and the moments you rushed will show up here.
          </p>
          <button
            onClick={() => navigate("/home")}
            className="mt-6 h-9 px-4 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-[13px]"
          >
            Back home
          </button>
        </div>
      </Layout>
    );
  }

  if (phase === "done") {
    return (
      <Layout user={user}>
        <div className="experience-page experience-learning-page experience-daily-page max-w-[620px] mx-auto px-6 py-16 text-center" data-testid="daily-fix-done">
          <div className="inline-flex items-center gap-2 text-amber-600 dark:text-amber-400 font-semibold text-[18px] mb-3">
            <Flame className="h-5 w-5" strokeWidth={2} /> {streakResult?.current || 1}-day streak
          </div>
          <h1 className="font-serif text-[28px] text-foreground mb-2">Fix done for today.</h1>
          <p className="text-[14px] text-muted-foreground mb-8">
            You slowed down and looked — that's the whole habit. Come back tomorrow to keep the streak alive.
          </p>
          <button
            onClick={() => navigate("/home")}
            className="h-10 px-5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-[14px] inline-flex items-center gap-2"
          >
            Back home <ArrowRight className="h-4 w-4" strokeWidth={2} />
          </button>
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user}>
      <div className="experience-page experience-learning-page experience-daily-page max-w-[620px] mx-auto px-6 py-8" data-testid="daily-fix-drill">
        <div className="flex items-center justify-between mb-4">
          <span className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground font-semibold">
            Timed fix · {idx + 1} of {drills.length}
          </span>
          <span className="inline-flex items-center gap-1.5 text-[13px] font-mono text-foreground">
            <Clock className="h-3.5 w-3.5" strokeWidth={2} /> {elapsed}s
          </span>
        </div>

        <div className="rounded-lg border border-amber-200/60 bg-amber-50/50 dark:bg-amber-950/20 dark:border-amber-900/50 p-3 mb-4">
          <p className="text-[13px] text-foreground">
            {drill.prompt || "You rushed here last time. Take your time — find the best move."}
          </p>
        </div>

        <div className="aspect-square w-full max-w-[440px] mx-auto">
          <Chessboard
            position={boardFen || drill.fen}
            onPieceDrop={onDrop}
            boardOrientation={orientation}
            arePiecesDraggable={phase === "solving"}
          />
        </div>

        {phase === "correct" && (
          <div className="mt-4 rounded-lg border-l-4 border-l-emerald-500 bg-emerald-500/10 p-4">
            <p className="text-[14px] font-medium text-foreground mb-1">That's it — with time, you found it.</p>
            <p className="text-[12px] text-muted-foreground mb-3">{drill.teaching}</p>
            {completionError && (
              <p className="text-[12px] text-red-600 dark:text-red-400 mb-3" role="alert">
                {completionError}
              </p>
            )}
            <button
              onClick={next}
              className="h-9 px-4 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-[13px] inline-flex items-center gap-2"
            >
              {idx + 1 < drills.length ? "Next" : "Finish"} <ArrowRight className="h-3.5 w-3.5" strokeWidth={2} />
            </button>
          </div>
        )}

        {phase === "wrong" && (
          <div className="mt-4 rounded-lg border-l-4 border-l-orange-500 bg-orange-500/10 p-4">
            <p className="text-[14px] font-medium text-foreground mb-1">Not the one — slow down and look again.</p>
            <p className="text-[12px] text-muted-foreground mb-3">{drill.teaching}</p>
            <div className="flex gap-2">
              <button
                onClick={() => { setBoardFen(drill.fen); setPhase("solving"); setCompletionError(null); }}
                className="h-9 px-4 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-[13px]"
              >
                Try again
              </button>
            </div>
            {completionError && (
              <p className="text-[12px] text-red-600 dark:text-red-400 mt-2">{completionError}</p>
            )}
          </div>
        )}
      </div>
    </Layout>
  );
}
