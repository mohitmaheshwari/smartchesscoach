/**
 * SkillDrill — drill positions for a single Engine 2 skill.
 *
 * Routed at /training/skill/:skillId. Fetches GET
 * /api/training/skill-puzzles/{skillId} which returns own + community
 * puzzle entries (lazy-extracted on the backend if first visit). Each
 * puzzle carries fen, source_game_id, move_number, and the skill_id.
 *
 * Grading: POST /api/training/skill-puzzle-attempt with puzzle_id +
 * move_uci. The backend runs the registered concept detector on the
 * user's move and returns {correct, verdict, detail}. Detector-graded
 * puzzles accept ANY move the detector grades as "applied" (so e.g.
 * any king move into the catch zone passes, not a single best SAN).
 *
 * Built 2026-06-01 as Piece 4 of the ROS evidence → drill track.
 * Generic over skill_id — same page is used for any skill once a
 * detector is wired. Per-skill copy lives in the SKILL_COPY map
 * below.
 */
import { useEffect, useState, useMemo, useRef } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Chess } from "chess.js";
import { API } from "@/App";
import LichessBoard from "@/components/LichessBoard";
import { ArrowLeft, RotateCcw, ChevronRight, Loader2, ExternalLink, Check, X, Lightbulb } from "lucide-react";

// Per-skill drill copy. Keep terse — most teaching is in the verdict
// line returned by the backend grader.
const SKILL_COPY = {
  endgame_rule_of_square: {
    title: "Rule of the Square",
    prompt: "Pawn race. Does the king catch the pawn? Find the move that tests it.",
    hint: "Count the squares from the pawn to promotion. If the king can step into that area on its next move, the race is on. If not, push.",
  },
};

function copyFor(skillId) {
  return SKILL_COPY[skillId] || {
    title: skillId.replace(/_/g, " "),
    prompt: "Find the right move for this position.",
    hint: "",
  };
}

const SkillDrill = ({ user }) => {
  const { skillId } = useParams();
  const navigate = useNavigate();
  const copy = useMemo(() => copyFor(skillId), [skillId]);

  const [loading, setLoading] = useState(true);
  const [puzzles, setPuzzles] = useState([]);   // own + community merged
  const [error, setError] = useState(null);
  const [idx, setIdx] = useState(0);

  // Per-puzzle state
  const [chess, setChess] = useState(null);
  const [grading, setGrading] = useState(false);
  const [verdict, setVerdict] = useState(null); // {correct, verdict, detail}
  const [playedMove, setPlayedMove] = useState(null); // {from, to, san, uci}
  const [orientation, setOrientation] = useState("white");

  // Counters across the drill session
  const [stats, setStats] = useState({ correct: 0, attempted: 0 });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(
          `${API}/training/skill-puzzles/${encodeURIComponent(skillId)}?limit=20`,
          { credentials: "include" },
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (cancelled) return;
        const merged = [
          ...(data.own_puzzles || []),
          ...(data.community_puzzles || []),
        ];
        setPuzzles(merged);
        setIdx(0);
      } catch (e) {
        if (!cancelled) setError(e.message || "Failed to load drill");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [skillId]);

  // Reset puzzle-local state whenever idx changes
  useEffect(() => {
    const p = puzzles[idx];
    if (!p?.fen) { setChess(null); return; }
    try {
      const c = new Chess(p.fen);
      setChess(c);
      // Orient by the user's color if recorded; otherwise side-to-move.
      const o = (p.user_color || "").toLowerCase();
      setOrientation(o === "black" ? "black" : o === "white" ? "white"
                     : (c.turn() === "w" ? "white" : "black"));
    } catch {
      setChess(null);
    }
    setVerdict(null);
    setPlayedMove(null);
  }, [puzzles, idx]);

  const current = puzzles[idx];
  const total = puzzles.length;
  const done = total > 0 && idx >= total;

  async function submitMove(from, to) {
    if (!current || verdict || grading || !chess) return;
    // Build UCI. Detect promotion: a pawn moving to last rank without
    // an explicit promotion piece — default to queen (the only choice
    // that matters in ROS positions; underpromotion would be a
    // separate skill).
    const movingPiece = chess.get(from);
    let uci = `${from}${to}`;
    if (movingPiece && movingPiece.type === "p") {
      const toRank = to[1];
      if (toRank === "8" || toRank === "1") uci += "q";
    }
    // Optimistically apply on a clone to show the move on the board.
    const optimisticChess = new Chess(chess.fen());
    let movePayload;
    try {
      movePayload = optimisticChess.move({ from, to, promotion: "q" });
    } catch {
      movePayload = null;
    }
    if (!movePayload) return; // illegal — onMove shouldn't fire, but defend
    setPlayedMove({ from, to, san: movePayload.san, uci });
    setChess(optimisticChess);

    setGrading(true);
    try {
      const res = await fetch(`${API}/training/skill-puzzle-attempt`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ puzzle_id: current.puzzle_id, move_uci: uci }),
      });
      const data = await res.json();
      setVerdict(data);
      setStats(s => ({
        correct: s.correct + (data.correct ? 1 : 0),
        attempted: s.attempted + 1,
      }));
    } catch (e) {
      setVerdict({ correct: false, verdict: "error", detail: "Couldn't grade — try again." });
    } finally {
      setGrading(false);
    }
  }

  function retry() {
    if (!current?.fen) return;
    try { setChess(new Chess(current.fen)); } catch { /* ignore */ }
    setVerdict(null);
    setPlayedMove(null);
  }

  function next() {
    setIdx(i => i + 1);
  }

  // ─── render ──────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin mr-2" /> Loading drill…
      </div>
    );
  }
  if (error) {
    return (
      <div className="max-w-xl mx-auto p-10 text-center">
        <p className="text-red-500 mb-4">{error}</p>
        <Link to="/progress" className="text-primary underline">Back to progress</Link>
      </div>
    );
  }
  if (total === 0) {
    return (
      <div className="max-w-xl mx-auto p-10 text-center">
        <h2 className="font-serif text-2xl mb-3">No drill positions yet</h2>
        <p className="text-muted-foreground mb-6">
          We didn't find any positions for {copy.title} in your games or the
          community pool. Play a few more games and check back.
        </p>
        <Link to="/progress" className="text-primary underline">Back to progress</Link>
      </div>
    );
  }
  if (done) {
    const pct = stats.attempted ? Math.round((stats.correct / stats.attempted) * 100) : 0;
    return (
      <div className="max-w-xl mx-auto p-10 text-center">
        <h2 className="font-serif text-2xl mb-3">Drill complete</h2>
        <p className="text-[15px] text-muted-foreground mb-6">
          You got <span className="text-foreground font-semibold">{stats.correct}</span> out
          of <span className="text-foreground font-semibold">{stats.attempted}</span> ({pct}%).
        </p>
        <div className="flex gap-3 justify-center">
          <button
            onClick={() => { setIdx(0); setStats({correct:0, attempted:0}); }}
            className="px-4 h-9 rounded-lg border border-border text-[13px] hover:bg-muted"
          >
            Run it again
          </button>
          <Link
            to="/progress"
            className="px-4 h-9 inline-flex items-center rounded-lg bg-violet-500 hover:bg-violet-400 text-white text-[13px] font-medium"
          >
            Back to progress
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <button
          onClick={() => navigate(-1)}
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-[13px]"
        >
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
        <div className="text-[12px] text-muted-foreground tabular-nums">
          {idx + 1} / {total} · {stats.correct}/{stats.attempted} correct
        </div>
      </div>

      <div className="mb-6">
        <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold">
          Skill drill
        </div>
        <h1 className="font-serif text-[26px] text-foreground mt-1">{copy.title}</h1>
        <p className="text-[14px] text-muted-foreground mt-1">{copy.prompt}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(320px,520px)_1fr] gap-8 lg:gap-12 items-start">
        {/* Board */}
        <div className="w-full">
          <div className="rounded-lg overflow-hidden ring-1 ring-border">
            {chess && (
              <LichessBoard
                fen={chess.fen()}
                orientation={orientation}
                interactive={!verdict && !grading}
                viewOnly={!!verdict || grading}
                movableColor={
                  !verdict && !grading
                    ? (chess.turn() === "w" ? "white" : "black")
                    : undefined
                }
                onMove={(moveData) => {
                  if (moveData?.from && moveData?.to) {
                    submitMove(moveData.from, moveData.to);
                  }
                }}
              />
            )}
          </div>
        </div>

        {/* Right panel */}
        <div className="space-y-4">
          {/* Source attribution + provenance */}
          {current?.source_game_id && (
            <div className="text-[12px] text-muted-foreground flex items-center gap-1.5">
              <span>From a {current.is_own ? "real game of yours" : "community game"}
                {current.opening_name ? ` · ${current.opening_name}` : ""}
                {current.move_number ? ` · move ${current.move_number}` : ""}</span>
              {current.is_own && (
                <Link
                  to={`/game/${current.source_game_id}${current.move_number ? `?move=${current.move_number}` : ""}`}
                  className="text-primary inline-flex items-center gap-0.5 hover:underline"
                >
                  see game <ExternalLink className="h-3 w-3" />
                </Link>
              )}
            </div>
          )}

          {/* Verdict card OR hint card */}
          {verdict ? (
            <div className={`rounded-lg border p-4 ${
              verdict.correct
                ? "border-emerald-500/40 bg-emerald-500/5"
                : "border-amber-500/40 bg-amber-500/5"
            }`}>
              <div className="flex items-center gap-2 mb-2">
                {verdict.correct
                  ? <Check className="h-4 w-4 text-emerald-500" />
                  : <X className="h-4 w-4 text-amber-500" />}
                <span className={`text-[13px] font-semibold ${
                  verdict.correct ? "text-emerald-500" : "text-amber-500"
                }`}>
                  {verdict.correct
                    ? (verdict.verdict === "engine_best"
                        ? "Engine-best — works"
                        : "Right idea")
                    : verdict.verdict === "missed" ? "Missed the rule" : "Doesn't engage the rule"}
                </span>
                {playedMove?.san && (
                  <span className="text-[12px] font-mono text-muted-foreground ml-auto">
                    you played {playedMove.san}
                  </span>
                )}
              </div>
              <p className="text-[13px] text-foreground/90 leading-snug">{verdict.detail}</p>
            </div>
          ) : (
            copy.hint && (
              <div className="rounded-lg border border-border/60 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Lightbulb className="h-4 w-4 text-muted-foreground" />
                  <span className="text-[10.5px] uppercase tracking-[0.18em] text-muted-foreground font-semibold">
                    Hint
                  </span>
                </div>
                <p className="text-[13px] text-muted-foreground leading-snug">{copy.hint}</p>
              </div>
            )
          )}

          {/* Actions */}
          {verdict && (
            <div className="flex gap-2 pt-1">
              {!verdict.correct && (
                <button
                  onClick={retry}
                  className="px-3 h-9 rounded-lg border border-border text-[13px] inline-flex items-center gap-1.5 hover:bg-muted"
                >
                  <RotateCcw className="h-3.5 w-3.5" /> Try again
                </button>
              )}
              <button
                onClick={next}
                className="flex-1 h-9 rounded-lg bg-violet-500 hover:bg-violet-400 text-white text-[13px] font-medium inline-flex items-center justify-center gap-1.5"
              >
                Next position <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}
          {grading && (
            <div className="text-[12px] text-muted-foreground inline-flex items-center gap-1.5">
              <Loader2 className="h-3 w-3 animate-spin" /> Grading…
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SkillDrill;
