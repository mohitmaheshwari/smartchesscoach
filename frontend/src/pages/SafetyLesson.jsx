/**
 * SafetyLesson — the piece-safety lesson, rebuilt to show rather than ask.
 *
 * docs/show_dont_ask_lesson_scope.md.
 *
 * The old lesson asked the player which of three canned thoughts was closest
 * to what he checked before moving. Nobody can answer that honestly — people
 * do not recall what they checked, they reconstruct a reason that fits the
 * outcome. So there is no question here at all. He watches his own move get
 * punished, then plays a safe one with his own hand, then does it again on a
 * different board.
 *
 * Every wrong attempt is answered by an arrow, never by a verdict. He cannot
 * fail; he can only keep trying until the piece is safe, which is the
 * behaviour the lesson exists to build.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Chess } from "chess.js";
import LichessBoard from "@/components/LichessBoard";
import { API } from "@/App";
import { Loader2, ArrowLeft, RotateCcw } from "lucide-react";

const STEP = {
  MOMENT: "moment",
  RETRY: "retry",
  TRANSFER: "transfer",
  DONE: "done",
};

function Eyebrow({ children }) {
  return (
    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground mb-2">
      {children}
    </p>
  );
}

export default function SafetyLesson() {
  const navigate = useNavigate();
  const [lesson, setLesson] = useState(null);
  const [loading, setLoading] = useState(true);
  const [step, setStep] = useState(STEP.MOMENT);

  // Screen 1 plays his move, pauses, then plays the punishment.
  const [momentFen, setMomentFen] = useState(null);
  const [momentArrows, setMomentArrows] = useState([]);
  const [punished, setPunished] = useState(false);

  // Screens 3 and 4.
  const [boardFen, setBoardFen] = useState(null);
  const [attemptArrows, setAttemptArrows] = useState([]);
  const [attemptMessage, setAttemptMessage] = useState("");
  const [solved, setSolved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API}/training/safety-lesson`, {
          credentials: "include",
        });
        if (!res.ok) return;
        const data = await res.json();
        if (cancelled) return;
        setLesson(data);
        if (data?.available) setMomentFen(data.moment.fen_before);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  /* Screen 1: play his move, hold, then let it be taken. Watching it happen
     is the point — a still picture of the aftermath is a different, weaker
     thing. */
  const playMoment = useCallback(() => {
    if (!lesson?.moment) return;
    const { fen_before, played_uci, reply_uci, arrows } = lesson.moment;
    setPunished(false);
    setMomentArrows([]);
    setMomentFen(fen_before);
    const board = new Chess(fen_before);
    setTimeout(() => {
      try {
        board.move({ from: played_uci.slice(0, 2), to: played_uci.slice(2, 4), promotion: "q" });
        setMomentFen(board.fen());
      } catch (e) { /* position refused the move; leave the board as it was */ }
    }, 600);
    setTimeout(() => {
      try {
        board.move({ from: reply_uci.slice(0, 2), to: reply_uci.slice(2, 4), promotion: "q" });
        setMomentFen(board.fen());
      } catch (e) { /* same */ }
      setMomentArrows(arrows || []);
      setPunished(true);
    }, 1700);
  }, [lesson]);

  useEffect(() => {
    if (lesson?.available && step === STEP.MOMENT) playMoment();
  }, [lesson, step, playMoment]);

  const startBoard = useCallback((fen) => {
    setBoardFen(fen);
    setAttemptArrows([]);
    setAttemptMessage("");
    setSolved(false);
  }, []);

  const attempt = useCallback(async (from, to) => {
    if (!boardFen || solved) return;
    const res = await fetch(`${API}/training/safety-lesson/attempt`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ fen: boardFen, move: `${from}${to}` }),
    });
    if (!res.ok) return;
    const out = await res.json();
    if (out.accepted) {
      setSolved(true);
      setAttemptArrows([[from, to, "green"]]);
      setAttemptMessage("");
    } else {
      /* No verdict word. The arrow is the answer, and he tries again. */
      setAttemptArrows(out.arrows || []);
      setAttemptMessage(out.message || "");
    }
  }, [boardFen, solved]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!lesson?.available) {
    return (
      <div className="mx-auto max-w-[560px] px-4 py-16 text-center">
        <p className="text-[15px] text-muted-foreground">
          Nothing to work on here yet. Play a few games and come back.
        </p>
      </div>
    );
  }

  const onTransfer = step === STEP.TRANSFER;
  const activeFen = step === STEP.MOMENT ? momentFen : boardFen;
  const activeArrows = step === STEP.MOMENT ? momentArrows : attemptArrows;

  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8">
      <button
        onClick={() => navigate("/learn")}
        className="mb-6 flex items-center gap-2 text-[13px] text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> Continue later
      </button>

      <div className="grid gap-8 md:grid-cols-[minmax(0,1fr)_380px]">
        <div>
          <LichessBoard
            fen={activeFen}
            arrows={activeArrows}
            interactive={step === STEP.RETRY || step === STEP.TRANSFER}
            viewOnly={step === STEP.MOMENT}
            onMove={(m) => m && attempt(m.from, m.to)}
          />
          {step === STEP.MOMENT && punished && (
            <button
              onClick={playMoment}
              className="mt-3 flex items-center gap-2 text-[12px] text-muted-foreground hover:text-foreground"
            >
              <RotateCcw className="h-3.5 w-3.5" /> Watch it again
            </button>
          )}
        </div>

        <div className="rounded-2xl border border-border/60 bg-card p-6">
          {step === STEP.MOMENT && (
            <>
              <Eyebrow>From your game</Eyebrow>
              <p className="text-[17px] leading-relaxed text-foreground">
                {lesson.moment.line_one}
              </p>
              <p className="text-[17px] leading-relaxed text-foreground mb-6">
                {punished ? lesson.moment.line_two : " "}
              </p>
              {punished && (
                <>
                  <p className="text-[15px] leading-relaxed text-foreground mb-8">
                    {lesson.cause}
                  </p>
                  <button
                    onClick={() => { setStep(STEP.RETRY); startBoard(lesson.retry.fen); }}
                    className="rounded-full bg-primary px-5 py-2.5 text-[14px] font-medium text-primary-foreground"
                  >
                    Try it again
                  </button>
                </>
              )}
            </>
          )}

          {(step === STEP.RETRY || onTransfer) && (
            <>
              <Eyebrow>
                {onTransfer ? lesson.transfer.label : "Same position"}
              </Eyebrow>
              <p className="text-[17px] leading-relaxed text-foreground mb-2">
                {onTransfer ? lesson.transfer.task : lesson.retry.task}
              </p>
              <p className="text-[13px] text-muted-foreground mb-6">
                {(onTransfer ? lesson.transfer.safe_move_count
                             : lesson.retry.safe_move_count)} moves work here.
              </p>

              {attemptMessage && !solved && (
                <p className="mb-6 rounded-lg bg-muted/60 px-4 py-3 text-[14px] text-foreground">
                  {attemptMessage}
                </p>
              )}

              {solved && (
                <>
                  <p className="mb-6 text-[14px] text-emerald-600 dark:text-emerald-400">
                    Nothing can take it there.
                  </p>
                  {!onTransfer && lesson.transfer ? (
                    <button
                      onClick={() => { setStep(STEP.TRANSFER); startBoard(lesson.transfer.fen); }}
                      className="rounded-full bg-primary px-5 py-2.5 text-[14px] font-medium text-primary-foreground"
                    >
                      One more, different board
                    </button>
                  ) : (
                    <button
                      onClick={() => setStep(STEP.DONE)}
                      className="rounded-full bg-primary px-5 py-2.5 text-[14px] font-medium text-primary-foreground"
                    >
                      Finish
                    </button>
                  )}
                </>
              )}
            </>
          )}

          {step === STEP.DONE && (
            <>
              <Eyebrow>Take this with you</Eyebrow>
              <p className="text-[17px] leading-relaxed text-foreground mb-8">
                {lesson.habit}
              </p>
              <button
                onClick={() => navigate("/learn")}
                className="rounded-full bg-primary px-5 py-2.5 text-[14px] font-medium text-primary-foreground"
              >
                Done
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
