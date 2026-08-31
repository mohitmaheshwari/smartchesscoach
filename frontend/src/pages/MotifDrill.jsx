/**
 * MotifDrill — drill positions for pin/skewer/fork weaknesses.
 *
 * Routed at /training/motif/:motif (fork|pin|skewer). Fetches GET
 * /api/player/motif-drill/:motif which returns the user's own positions
 * where they walked into the motif + community positions (motif-tagged).
 *
 * Each position carries (normalized contract, 2026-08-13):
 *   position_fen:      the board to DISPLAY — before the user's blunder, user to move
 *   solution_san:      best move, LEGAL IN position_fen
 *   user_blunder_move: what the user actually played, legal in position_fen
 *   opp_creates_motif: opponent's reply — legal only AFTER user_blunder_move
 *
 * This header previously documented `fen` as "position before the user's blunder".
 * It was not: the service stored fen_AFTER, so the printed solution was illegal in the
 * displayed position for 92% of own-game rows, and the trap panel could never render.
 * Fixed together with services/motif_profile_service.py get_drills().
 *
 * Teaching flow: Shows the position → best move → what happens if user
 * plays wrong (replay blunder, then opponent creates the motif). Non-interactive.
 *
 * Built 2026-06-24 as UI wiring for motif_drill backend (stores both
 * the decision point and the opponent's creating move).
 */
import { useEffect, useState, useMemo } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { API } from "@/App";
import LichessBoard from "@/components/LichessBoard";
import { ArrowLeft, ChevronRight, Loader2, BookOpen, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { buildDrillBoards, usableDrills } from "@/lib/motifDrill";

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
        // Defence in depth: the endpoint already drops unresolved rows, but never
        // render a drill whose advertised solution is not playable on its own board.
        if (data.gated) {
          setDrills([]);
          setError(data.gated_reason || "This drill is paused.");
          return;
        }
        setDrills(usableDrills(data.drills));
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
    // 2026-08-13 contract fix — see lib/motifDrill.js. `position_fen` is the board to
    // show (user to move, solution_san legal here); the trap board replays the blunder
    // before the opponent's motif move. Logic lives in the lib so the legality
    // invariant is covered by lib/motifDrill.test.js.
    const { board, trapBoard, orientation: o } = buildDrillBoards(drills[idx]);
    setChess(board);
    setChessAfterOpp(trapBoard);
    setOrientation(o);
    setShowTrap(false);
  }, [drills, idx]);

  const current = drills[idx];
  const total = drills.length;
  const done = total > 0 && idx >= total;

  if (loading) {
    return (
      <div className="experience-page experience-learning-page min-h-screen flex items-center justify-center text-muted-foreground">
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
    <div className="experience-page experience-learning-page experience-drill-page min-h-screen">
      <div className="cg-page cg-page--wide">
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
          <p className="text-sm text-muted-foreground">Take the positions one at a time.</p>
        </div>

        {done ? (
          <div className="max-w-xl mx-auto text-center py-20">
            <div className="h-16 w-16 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center mx-auto mb-6">
              <span className="text-3xl">✓</span>
            </div>
            <h2 className="font-serif text-2xl mb-3">Drill complete!</h2>
            <p className="text-muted-foreground mb-6">
              You have seen this geometry from several angles. Now watch for it before it appears in a real game.
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
              <div className="cg-panel">
                <h3 className="font-serif text-xl font-medium mb-4">Read the position first</h3>
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
                    <p className="text-lg font-bold font-mono" data-testid="motif-solution">{current?.solution_san || "—"}</p>
                  </div>
                  <p className="text-xs text-muted-foreground italic">
                    {/* Was: "This move avoids the {motif} your opponent creates."
                        Unproven -- `solution` is the ENGINE'S BEST MOVE, and the
                        engine's best sometimes ACCEPTS the motif because it is
                        best overall (2 of 18 stratified fork positions). We can
                        only claim what we verified: it is the strongest move. */}
                    This is a strong move because it keeps the opponent’s idea from taking over the position.
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
                        You played <span className="font-bold font-mono">{current?.user_blunder_move}</span>.
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
                <p className="text-xs font-medium text-muted-foreground uppercase mb-3">Look once without moving</p>
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
                  <li>Understand why the move works</li>
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
