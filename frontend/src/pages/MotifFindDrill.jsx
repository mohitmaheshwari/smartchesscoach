/**
 * SPOTTING a pin or skewer (docs/pin_skewer_drill_scope.md)
 *
 * THE OTHER HALF of pages/MotifDrill.jsx, and the difference is the whole
 * reason both exist. That page teaches AVOIDING these shapes: it replays
 * positions the player walked into, non-interactively, from
 * motif_profile_service.get_drills(). This page teaches FINDING them: positions
 * where the engine's best move was a pin or a skewer and the player did not
 * play it, from the opportunity gate. Two sides of one shape, which is what the
 * motif-profile backlog asked for.
 *
 * Routed at /training/find/:motif. Do not merge the two into one page with a
 * mode flag -- one is a replay and one is a question, and they share no state.
 *
 * Positions come from GET /api/training/motif-drill/:motif -- his own games
 * first, then other players' games, then Lichess. The answer is never in that
 * payload; POST /api/training/motif-drill/attempt grades the move and is the
 * only place the answer appears.
 *
 * The question names the shape on purpose. This drill is given to a player
 * already measured as missing these, so asking him to notice unaided would
 * reproduce the miss. Telling him where to look and making him execute is the
 * drill.
 *
 * NO NUMBERS anywhere the player can see -- not a score, not a count, not
 * "3 of 10". A test asserts it, because an authored string that drifts never
 * errors on its own.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { ArrowRight, Check, X } from "lucide-react";

const TITLES = {
  pin: "Pins",
  skewer: "Skewers",
};

export default function MotifFindDrill({ user }) {
  const navigate = useNavigate();
  const { motif: raw } = useParams();
  const motif = String(raw || "").toLowerCase();

  const [loading, setLoading] = useState(true);
  const [state, setState] = useState("ready");
  const [positions, setPositions] = useState([]);
  const [idx, setIdx] = useState(0);
  const [phase, setPhase] = useState("solving");   // solving | reason | done
  const [verdict, setVerdict] = useState(null);
  const [moveUci, setMoveUci] = useState("");
  const [boardFen, setBoardFen] = useState("");
  const [error, setError] = useState("");

  const position = positions[idx] || null;

  useEffect(() => {
    let live = true;
    setLoading(true);
    fetch(`${API}/training/motif-drill/${motif}?count=10`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("unavailable"))))
      .then((data) => {
        if (!live) return;
        setPositions(data.positions || []);
        setState(data.state || "ready");
      })
      .catch(() => live && setError("This drill could not be loaded."))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, [motif]);

  // The board shows the position until a move is made, then the move, so the
  // player sees what they played while they read the verdict.
  const shownFen = boardFen || position?.fen || "";

  const orientation = useMemo(
    () => (position?.to_move === "black" ? "black" : "white"),
    [position]
  );

  const onDrop = useCallback(
    (from, to) => {
      if (!position || phase !== "solving") return false;
      const game = new Chess(position.fen);
      let played;
      try {
        played = game.move({ from, to, promotion: "q" });
      } catch {
        return false;
      }
      if (!played) return false;
      setBoardFen(game.fen());
      const uci = `${played.from}${played.to}${played.promotion || ""}`;
      setMoveUci(uci);
      setPhase("reason");
      return true;
    },
    [position, phase]
  );

  const submit = useCallback(
    async (reasonId) => {
      if (!position) return;
      setError("");
      try {
        const res = await fetch(`${API}/training/motif-drill/attempt`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            position_id: position.position_id,
            move_uci: moveUci,
            reason_id: reasonId || null,
          }),
        });
        if (!res.ok) throw new Error("rejected");
        setVerdict(await res.json());
        setPhase("done");
      } catch {
        setError("That answer could not be sent. Try again.");
      }
    },
    [position, moveUci]
  );

  const next = useCallback(() => {
    setVerdict(null);
    setMoveUci("");
    setBoardFen("");
    setPhase("solving");
    setIdx((i) => i + 1);
  }, []);

  if (!TITLES[motif]) {
    return (
      <Layout user={user}>
        <div className="max-w-[620px] mx-auto px-6 py-8">
          <p className="text-[14px] text-foreground">There is no drill for that.</p>
        </div>
      </Layout>
    );
  }

  if (loading) {
    return (
      <Layout user={user}>
        <div className="max-w-[620px] mx-auto px-6 py-8">
          <p className="text-[14px] text-muted-foreground">Loading…</p>
        </div>
      </Layout>
    );
  }

  // "Nothing tagged yet" and "you have solved these" are different things and
  // are told apart, so a migration that has not run cannot look like a
  // finished drill.
  if (!position) {
    const message =
      state === "exhausted"
        ? "You have worked through the ones we have. Play some games and we will find more."
        : state === "not_tagged"
        ? "This drill is not ready yet."
        : "There is nothing to practise here right now.";
    return (
      <Layout user={user}>
        <div className="max-w-[620px] mx-auto px-6 py-8" data-testid="motif-find-drill-empty">
          <p className="text-[14px] text-foreground mb-4">{message}</p>
          <button
            onClick={() => navigate("/lab")}
            className="h-10 px-5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-[14px] inline-flex items-center gap-2"
          >
            Back to the lab <ArrowRight className="h-4 w-4" strokeWidth={2} />
          </button>
        </div>
      </Layout>
    );
  }

  const fromOwnGame = position.source === "own_game";

  return (
    <Layout user={user}>
      <div
        className="experience-page experience-learning-page max-w-[620px] mx-auto px-6 py-8"
        data-testid="motif-find-drill"
      >
        <span className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground font-semibold">
          {TITLES[motif]}
        </span>

        <div className="mt-4 rounded-lg border border-amber-200/60 bg-amber-50/50 dark:bg-amber-950/20 dark:border-amber-900/50 p-3 mb-4">
          <p className="text-[14px] text-foreground">{position.question}</p>
        </div>

        <div className="aspect-square w-full max-w-[440px] mx-auto">
          <Chessboard
            position={shownFen}
            onPieceDrop={onDrop}
            boardOrientation={orientation}
            arePiecesDraggable={phase === "solving"}
            customBoardStyle={{ borderRadius: "6px" }}
          />
        </div>

        {phase === "solving" && (
          <p className="mt-3 text-[12px] text-muted-foreground text-center">
            {position.task_line}
          </p>
        )}

        {fromOwnGame && (
          <p className="mt-3 text-[12px] text-muted-foreground text-center">
            This one came from one of your own games.
          </p>
        )}

        {phase === "reason" && (
          <div className="mt-5 rounded-lg border border-border p-4" data-testid="motif-find-drill-reason">
            <p className="text-[14px] text-foreground mb-3">{position.reason_prompt}</p>
            <div className="space-y-2">
              {(position.reason_options || []).map((option) => (
                <button
                  key={option.id}
                  onClick={() => submit(option.id)}
                  className="w-full text-left px-3 py-2.5 rounded-lg border border-border hover:border-amber-500 text-[13px] text-foreground"
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {phase === "done" && verdict && (
          <div
            className={`mt-5 rounded-lg border-l-4 p-4 ${
              verdict.correct
                ? "border-l-emerald-500 bg-emerald-500/10"
                : "border-l-amber-500 bg-amber-500/10"
            }`}
            data-testid="motif-find-drill-verdict"
          >
            <p className="text-[14px] font-medium text-foreground mb-1 inline-flex items-center gap-2">
              {verdict.correct ? (
                <Check className="h-4 w-4 text-emerald-600" strokeWidth={2.5} />
              ) : (
                <X className="h-4 w-4 text-amber-600" strokeWidth={2.5} />
              )}
              {verdict.correct
                ? verdict.accepted_as === "also_works"
                  ? "That works too — it makes the same line."
                  : "That is the move."
                : "Not this one."}
            </p>

            {verdict.belief_lead && (
              <p className="text-[13px] text-foreground mt-2">{verdict.belief_lead}</p>
            )}
            {verdict.correction && (
              <p className="text-[13px] text-foreground mt-2">{verdict.correction}</p>
            )}
            {!verdict.correct && verdict.answer_san && (
              <p className="text-[13px] text-foreground mt-2">
                The move was {verdict.answer_san}.
              </p>
            )}

            <p className="text-[12px] text-muted-foreground mt-3">{verdict.teaching}</p>

            <button
              onClick={next}
              className="mt-4 h-10 px-5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-[14px] inline-flex items-center gap-2"
            >
              Next one <ArrowRight className="h-4 w-4" strokeWidth={2} />
            </button>
          </div>
        )}

        {error && (
          <p className="mt-4 text-[12px] text-red-600 dark:text-red-400" role="alert">
            {error}
          </p>
        )}
      </div>
    </Layout>
  );
}
