/**
 * MotifDrill — drill positions for pin/skewer/fork weaknesses.
 *
 * Routed at /training/motif/:motif (fork|pin|skewer). Fetches GET
 * /api/player/motif-drill/:motif which returns the user's own positions
 * where they walked into the motif + community positions (motif-tagged).
 *
 * Each position carries:
 *   fen: position before the user's blunder
 *   solution: best move user should have played
 *   opp_creates_motif: opponent's move that creates the trap
 *
 * Teaching flow: Shows the position → best move → what happens if user
 * plays wrong (opponent creates the motif). Non-interactive (no move grading).
 *
 * Built 2026-06-24 as UI wiring for motif_drill backend (stores both
 * the decision point and the opponent's creating move).
 */
import { useEffect, useState, useMemo } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Chess } from "chess.js";
import { API } from "@/App";
import LichessBoard from "@/components/LichessBoard";
import { ArrowLeft, ChevronRight, Loader2, BookOpen, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

const MOTIF_COPY = {
  fork: {
    title: "Forks",
    prompt: "Learn to avoid walking into forks — where one enemy piece hits two of yours.",
    lesson: "Before each move, scan: can a knight (or queen/bishop/rook) hit two of your pieces at once?",
  },
  pin: {
    title: "Pins",
    prompt: "Learn to avoid pinned pieces — where a piece can't move without exposing something more valuable.",
    lesson: "Watch your lines: don't let a piece get stuck in front of your king or queen.",
  },
  skewer: {
    title: "Skewers",
    prompt: "Learn to avoid skewers — where a valuable piece must move, exposing a piece behind it.",
    lesson: "Don't line up a valuable piece in front of a weaker one on the same line.",
  },
};

function copyFor(motif) {
  return MOTIF_COPY[motif] || {
    title: (motif || "").replace(/_/g, " "),
    prompt: "Learn to avoid this tactical weakness.",
    lesson: "Study the position to see how the motif is created.",
  };
}

const MotifDrill = ({ user }) => {
  const { motif } = useParams();
  const navigate = useNavigate();
  const copy = useMemo(() => copyFor(motif), [motif]);

  const [loading, setLoading] = useState(true);
  const [drills, setDrills] = useState([]);
  const [error, setError] = useState(null);
  const [idx, setIdx] = useState(0);

  const [chess, setChess] = useState(null);
  const [chessAfterOpp, setChessAfterOpp] = useState(null);
  const [showTrap, setShowTrap] = useState(false);
  const [orientation, setOrientation] = useState("white");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${API}/player/motif-drill/${encodeURIComponent(motif)}`, {
          credentials: "include",
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (cancelled) return;
        setDrills(data.drills || []);
        setIdx(0);
      } catch (e) {
        if (!cancelled) setError(e.message || "Failed to load drill positions");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [motif]);

  useEffect(() => {
    const d = drills[idx];
    if (!d?.fen) {
      setChess(null);
      setChessAfterOpp(null);
      return;
    }
    try {
      const c = new Chess(d.fen);
      setChess(c);

      // Build the position after opponent creates the motif
      if (d.opp_creates_motif) {
        const c2 = new Chess(d.fen);
        c2.move(d.opp_creates_motif);
        setChessAfterOpp(c2);
      } else {
        setChessAfterOpp(null);
      }

      // Orient by side to move
      setOrientation(c.turn() === "w" ? "white" : "black");
      setShowTrap(false);
    } catch {
      setChess(null);
      setChessAfterOpp(null);
    }
  }, [drills, idx]);

  const current = drills[idx];
  const total = drills.length;
  const done = total > 0 && idx >= total;

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin mr-2" /> Loading drill positions…
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto p-10">
        <div className="flex items-start gap-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded p-4 mb-6">
          <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-red-700 dark:text-red-200 font-medium">Error loading drills</p>
            <p className="text-red-600 dark:text-red-300 text-sm mt-1">{error}</p>
          </div>
        </div>
        <Link to="/progress" className="inline-flex items-center gap-2 text-primary hover:underline">
          <ArrowLeft className="h-4 w-4" /> Back to progress
        </Link>
      </div>
    );
  }

  if (total === 0) {
    return (
      <div className="max-w-2xl mx-auto p-10 text-center">
        <BookOpen className="h-12 w-12 text-muted-foreground mx-auto mb-4 opacity-50" />
        <h2 className="font-serif text-2xl mb-3">No {copy.title.toLowerCase()} drills yet</h2>
        <p className="text-muted-foreground mb-6 max-w-md mx-auto">
          We didn't find positions where you walked into {copy.title.toLowerCase()} in your games.
          Play a few more games to build up your drill collection.
        </p>
        <Link to="/progress" className="inline-flex items-center gap-2 text-primary hover:underline">
          <ArrowLeft className="h-4 w-4" /> Back to progress
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white dark:from-slate-950 dark:to-slate-900">
      <div className="max-w-5xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate("/progress")}
              className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
              aria-label="Back"
            >
              <ArrowLeft className="h-5 w-5" />
            </button>
            <div>
              <h1 className="font-serif text-3xl font-bold">{copy.title}</h1>
              <p className="text-muted-foreground mt-1">{copy.prompt}</p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold text-primary">{done ? total : idx + 1}</p>
            <p className="text-sm text-muted-foreground">of {total}</p>
          </div>
        </div>

        {done ? (
          <div className="max-w-xl mx-auto text-center py-20">
            <div className="h-16 w-16 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center mx-auto mb-6">
              <span className="text-3xl">✓</span>
            </div>
            <h2 className="font-serif text-2xl mb-3">Drill complete!</h2>
            <p className="text-muted-foreground mb-6">
              You've reviewed all {total} positions where you walked into {copy.title.toLowerCase()}.
            </p>
            <button
              onClick={() => setIdx(0)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-primary/90 transition-colors"
            >
              Start over
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Boards */}
            <div className="lg:col-span-2 space-y-6">
              {/* Position before */}
              <div className="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-6">
                <h3 className="text-lg font-bold mb-4">Your position</h3>
                <p className="text-sm text-muted-foreground mb-4">{copy.lesson}</p>
                {chess && (
                  <div className="flex justify-center mb-6">
                    <div className="w-full max-w-sm">
                      <LichessBoard fen={chess.fen()} orientation={orientation} interactive={false} />
                    </div>
                  </div>
                )}
                <div className="space-y-3 bg-slate-50 dark:bg-slate-900 p-4 rounded border border-slate-200 dark:border-slate-700">
                  <div>
                    <p className="text-xs font-medium text-muted-foreground uppercase">Best move:</p>
                    <p className="text-lg font-bold font-mono">{current?.solution || "—"}</p>
                  </div>
                  <p className="text-xs text-muted-foreground italic">
                    This move avoids the {motif} your opponent creates.
                  </p>
                </div>
              </div>

              {/* What happens if wrong */}
              {chessAfterOpp && (
                <div className={cn(
                  "bg-white dark:bg-slate-800 rounded-lg shadow-lg p-6 border-2 transition-all",
                  showTrap ? "border-amber-400 dark:border-amber-500 bg-amber-50 dark:bg-amber-900/20" : "border-transparent"
                )}>
                  <button
                    onClick={() => setShowTrap(!showTrap)}
                    className="w-full text-left mb-4 flex items-center justify-between hover:opacity-80 transition-opacity"
                  >
                    <h3 className="text-lg font-bold">See what happens if you blunder</h3>
                    <ChevronRight className={cn("h-5 w-5 transition-transform", showTrap && "rotate-90")} />
                  </button>

                  {showTrap && (
                    <>
                      <p className="text-sm text-amber-700 dark:text-amber-300 mb-4 bg-amber-100 dark:bg-amber-900/40 p-3 rounded">
                        Opponent plays <span className="font-bold font-mono">{current?.opp_creates_motif}</span> — creating a {motif}!
                      </p>
                      <div className="flex justify-center mb-6">
                        <div className="w-full max-w-sm">
                          <LichessBoard fen={chessAfterOpp.fen()} orientation={orientation} interactive={false} />
                        </div>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        Now your pieces are vulnerable. Remember this pattern to avoid it next time.
                      </p>
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Sidebar */}
            <div className="space-y-4">
              <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
                <p className="text-xs font-medium text-muted-foreground uppercase mb-3">Position {idx + 1} of {total}</p>
                <div className="aspect-square bg-white dark:bg-slate-900 rounded mb-4 overflow-hidden">
                  {chess && (
                    <LichessBoard fen={chess.fen()} orientation={orientation} interactive={false} size="small" />
                  )}
                </div>
              </div>

              {/* Navigation */}
              <div className="space-y-2">
                <button
                  onClick={() => setIdx(Math.max(0, idx - 1))}
                  disabled={idx === 0}
                  className="w-full px-4 py-2 bg-slate-200 dark:bg-slate-700 text-slate-900 dark:text-slate-100 rounded hover:bg-slate-300 dark:hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Previous
                </button>
                <button
                  onClick={() => setIdx(Math.min(total - 1, idx + 1))}
                  disabled={idx >= total - 1}
                  className="w-full px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                >
                  Next <ChevronRight className="h-4 w-4" />
                </button>
              </div>

              <div className="text-xs text-muted-foreground p-3 bg-slate-50 dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700">
                <p className="font-medium mb-2">How to use:</p>
                <ul className="space-y-1 list-disc list-inside">
                  <li>Study each position</li>
                  <li>Memorize the best move</li>
                  <li>See how opponent creates the trap</li>
                  <li>Apply in your games</li>
                </ul>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MotifDrill;
