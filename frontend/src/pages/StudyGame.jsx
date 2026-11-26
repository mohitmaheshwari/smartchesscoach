/**
 * StudyGame — a real game that teaches an idea he does not know yet
 * (docs/daily_coach_plan_scope.md, section 9).
 *
 * Plays through a game from his own opening, near his level, stops at the
 * moment, and asks what he would play. The move is graded on the server
 * (POST /training/theme/attempt, which also ticks the day card). Then the idea
 * is shown working on the board, then what was really played in the game.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Chess } from "chess.js";
import LichessBoard from "@/components/LichessBoard";
import { ArrowRight, Check, ChevronRight, X } from "lucide-react";

import { API } from "@/App";
import Layout from "@/components/Layout";
import { ANALYTICS_EVENTS, track } from "@/lib/analytics";

const RESULT_WORDS = { "1-0": "White won the game.", "0-1": "Black won the game.", "1/2-1/2": "The game was drawn." };

/** FEN after playing `sans` from `startFen` (or the start position). */
function fenAfter(sans, startFen) {
  const g = startFen ? new Chess(startFen) : new Chess();
  for (const san of sans) {
    try {
      g.move(san);
    } catch {
      break;
    }
  }
  return g.fen();
}

export default function StudyGame({ user }) {
  const { puzzleId } = useParams();
  const [searchParams] = useSearchParams();
  const fromToday = searchParams.get("from") === "today";
  const navigate = useNavigate();

  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [step, setStep] = useState(0);            // moves of the game shown so far
  const [phase, setPhase] = useState("replay");  // replay | ask | verdict | idea | game
  const [verdict, setVerdict] = useState(null);
  const [tried, setTried] = useState("");
  const [lineStep, setLineStep] = useState(0);

  useEffect(() => {
    let live = true;
    fetch(`${API}/study/${encodeURIComponent(puzzleId)}`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("unavailable"))))
      .then((body) => {
        if (!live) return;
        setData(body);
        track(ANALYTICS_EVENTS.STUDY_GAME_VIEWED, { surface: fromToday ? "day_card" : "direct" });
      })
      .catch(() => live && setError("This game could not be loaded."));
    return () => { live = false; };
  }, [puzzleId, fromToday]);

  const total = data?.moves_before?.length || 0;
  const fen = useMemo(() => {
    if (!data) return "start";
    if (phase === "replay") return fenAfter(data.moves_before.slice(0, step));
    if (phase === "ask") return data.pause_fen;
    if (phase === "verdict") return tried || data.pause_fen;
    if (phase === "idea") return fenAfter(data.solution.slice(0, lineStep), data.pause_fen);
    return fenAfter(data.game_after.slice(0, lineStep), data.pause_fen);
  }, [data, phase, step, tried, lineStep]);

  const onDrop = useCallback((from, to) => {
    if (phase !== "ask" || !data) return false;
    const g = new Chess(data.pause_fen);
    let played;
    try {
      played = g.move({ from, to, promotion: "q" });
    } catch {
      return false;
    }
    if (!played) return false;
    setTried(g.fen());
    fetch(`${API}/training/theme/attempt`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ position_id: data.position_id, move_uci: `${played.from}${played.to}${played.promotion || ""}`, topic: data.topic }),
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("rejected"))))
      .then((v) => {
        setVerdict(v);
        setPhase("verdict");
        track(ANALYTICS_EVENTS.STUDY_GAME_ANSWERED, { outcome: v.correct ? "correct" : "incorrect" });
      })
      .catch(() => setError("That answer could not be sent. Try again."));
    return true;
  }, [phase, data]);

  if (error) {
    return (
      <Layout user={user}>
        <div className="mx-auto max-w-[620px] px-6 py-8"><p className="text-body text-foreground">{error}</p></div>
      </Layout>
    );
  }
  if (!data) {
    return (
      <Layout user={user}>
        <div className="mx-auto max-w-[620px] px-6 py-8"><p className="text-body text-muted-foreground">Loading…</p></div>
      </Layout>
    );
  }

  const nextButton = (label, onClick, testId) => (
    <button type="button" onClick={onClick} data-testid={testId}
      className="cg-secondary-action mt-4 inline-flex items-center gap-2">
      {label} <ChevronRight className="h-4 w-4" />
    </button>
  );

  return (
    <Layout user={user}>
      <div className="experience-page mx-auto max-w-[620px] px-6 py-8" data-testid="study-game">
        <p className="cg-eyebrow">A game to study</p>
        <h1 className="mt-2 font-heading text-title text-foreground">{data.idea_title}</h1>
        <p className="mt-2 text-note text-muted-foreground">
          {data.opening}. Players near your level.
        </p>

        {/* The product's own board, not a second library. This page shipped
            with react-chessboard while LichessBoard is used in 95 other
            files, so the one screen that teaches a pattern showed different
            squares and different pieces from every screen around it.
            LichessBoard hands onMove a {from, to}; onDrop still takes the
            two squares, so the handler is unchanged. */}
        <div className="mt-5 w-full max-w-[440px] mx-auto">
          <div className="experience-board-stage">
            <div className="aspect-square w-full overflow-hidden">
              <LichessBoard
                fen={fen}
                orientation={data.solver === "black" ? "black" : "white"}
                interactive={phase === "ask"}
                viewOnly={phase !== "ask"}
                showDests={phase === "ask"}
                onMove={(m) => m && onDrop(m.from, m.to)}
              />
            </div>
          </div>
        </div>

        <div className="mt-5 rounded-card border border-border/70 bg-card p-5" data-testid={`study-${phase}`}>
          {phase === "replay" && (
            <>
              <p className="text-body text-foreground">
                Watch the game. It stops at the moment that matters.
              </p>
              <div className="flex flex-wrap gap-3">
                {nextButton(step < total ? "Next move" : "To the moment", () => (step < total ? setStep(step + 1) : setPhase("ask")), "study-next")}
                {step < total && nextButton("Skip to the moment", () => { setStep(total); setPhase("ask"); }, "study-skip")}
              </div>
            </>
          )}
          {phase === "ask" && (
            <>
              <p className="text-body font-semibold text-foreground">What would you play here?</p>
              <p className="mt-1 text-note text-muted-foreground">{data.idea_text}</p>
            </>
          )}
          {phase === "verdict" && verdict && (
            <>
              <p className="inline-flex items-center gap-2 text-body font-semibold text-foreground">
                {verdict.correct ? <Check className="h-4 w-4 text-emerald-600" /> : <X className="h-4 w-4 text-amber-600" />}
                {verdict.correct ? "That is the move." : `Not this one. The move was ${verdict.answer_san}.`}
              </p>
              {nextButton("See the idea work", () => { setLineStep(0); setPhase("idea"); }, "study-to-idea")}
            </>
          )}
          {phase === "idea" && (
            <>
              <p className="text-body text-foreground">
                {lineStep < data.solution.length ? data.idea_text : "That is the idea at work."}
              </p>
              {lineStep < data.solution.length
                ? nextButton("Next", () => setLineStep(lineStep + 1), "study-idea-next")
                : nextButton("What happened in the game", () => { setLineStep(0); setPhase("game"); }, "study-to-game")}
            </>
          )}
          {phase === "game" && (
            <>
              <p className="text-body text-foreground">
                {data.found_in_game
                  ? "In the game, the player found it."
                  : `In the game, the player missed it and played ${data.game_after[0] || "something else"}.`}
                {" "}{RESULT_WORDS[data.result] || ""}
              </p>
              {lineStep < data.game_after.length && nextButton("Next move in the game", () => setLineStep(lineStep + 1), "study-game-next")}
              {fromToday && (
                <button type="button" onClick={() => navigate("/home")} className="cg-primary-action mt-4 inline-flex items-center gap-2">
                  Back to today <ArrowRight className="h-4 w-4" />
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </Layout>
  );
}
