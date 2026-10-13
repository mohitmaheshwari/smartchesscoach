/**
 * The home page as a coaching session, in three movements.
 *
 * docs/home_as_a_coach_scope.md
 *
 * Mohit, 2026-10-07, after four rounds of card layouts: *"it is still not
 * looking like a coach, it looks like a report"*, and then the process itself —
 * when you hire a coach he reads five or ten of your games, tells you what is
 * good and what is bad, and **plays you, teaching through the game**.
 *
 * The page kept failing because it was shaped like the work that produced it:
 * three features, three cards, eight labels, five bars. So this is not another
 * card. It is one column read top to bottom:
 *
 *   1. WHAT I KNOW ABOUT YOU — the good thing first, then the costly one
 *   2. TODAY — his board, his move, and a question BEFORE any answer
 *   3. PLAY ME — the part a puzzle cannot do
 *
 * MOVEMENT 2 IS THE PRODUCT. A puzzle app shows a position and marks the
 * answer. This shows YOUR position, names the move YOU played, and asks what
 * you were checking before it says a word. A conclusion handed over is nodded
 * at and forgotten; a belief you committed to and got wrong is remembered.
 * That is why the answer is not in the page payload at all — it is behind
 * POST /home/today/answer, and arrives only once he has committed.
 *
 * THE WHOLE THING IS ONE REQUEST. FindingCard, SessionCard and the focus-why
 * lookup each fetched /home/session separately, which was three identical
 * round trips for one page. The fetch lives here and the movements read it.
 *
 * A movement with nothing to say renders NOTHING. Three sections with one real
 * sentence between them is the report again.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Chessboard } from "react-chessboard";
import { API } from "@/App";

/* ------------------------------------------------ 1. what I know about you */

function Known({ known, assessment }) {
  const navigate = useNavigate();
  // The assessment alone is still movement one, so a player with no strength
  // and no finding yet keeps their chances reading.
  if (!known?.lines?.length && !known?.good_game) {
    return assessment ? (
      <section data-testid="coach-known" className="mb-10">{assessment}</section>
    ) : null;
  }
  return (
    <section data-testid="coach-known" className="mb-10">
      {known.lead && <p className="cg-eyebrow !text-xs font-mono font-bold tracking-wider">{known.lead}</p>}
      <div className="mt-4 space-y-4">
        {(known.lines || []).map((line, i) => (
          <p
            key={line.kind + i}
            data-testid={`coach-known-${line.kind}`}
            className={
              line.kind === "strength"
                ? // The good thing leads and is set largest. A coach who only
                  // names faults loses the client in three sessions, and every
                  // element of the page this replaces was a deficit.
                  "max-w-[720px] font-heading text-lg md:text-xl font-bold leading-snug tracking-tight text-foreground"
                : "max-w-[640px] border-l-2 border-amber-600/50 pl-3.5 text-sm sm:text-base leading-relaxed text-foreground"
            }
          >
            {line.text}
          </p>
        ))}
      </div>

      {/* A position they played WELL. The only thing the retired session card
          carried that nothing else does, and it reached 29% of players. It
          belongs in this movement because this movement is the good and the
          bad, and because a board they can see beats any sentence about them. */}
      {known.good_game?.fen && (
        <div
          data-testid="coach-known-good-game"
          className="mt-7 flex flex-col gap-5 rounded-[24px] border border-emerald-500/25 bg-emerald-500/[0.05] p-5 sm:flex-row sm:items-center sm:gap-6"
        >
          <div className="aspect-square w-full max-w-[180px] shrink-0">
            <Chessboard
              position={known.good_game.fen}
              arePiecesDraggable={false}
              customBoardStyle={{ borderRadius: "8px" }}
            />
          </div>
          <div className="min-w-0">
            <p className="text-[15px] font-semibold leading-snug text-foreground">
              {known.good_game.headline}
            </p>
            {known.good_game.line && (
              <p className="mt-2 text-[14px] leading-relaxed text-muted-foreground">
                {known.good_game.line}
              </p>
            )}
            {known.good_game.href && (
              <button
                type="button"
                onClick={() => navigate(known.good_game.href)}
                className="cg-secondary-action mt-4"
              >
                See the game
              </button>
            )}
          </div>
        </div>
      )}

      {/* The chances reading, inside this movement rather than below it. */}
      {assessment && <div className="mt-7">{assessment}</div>}
    </section>
  );
}

/* --------------------------------------------------------------- 2. today */

function Today({ today }) {
  const [chosen, setChosen] = useState(null);
  const [answer, setAnswer] = useState(null);
  const [sending, setSending] = useState(false);

  // A new position must clear the previous answer, or the old correction sits
  // under the new board looking like it belongs to it.
  useEffect(() => {
    setChosen(null);
    setAnswer(null);
  }, [today?.position_id]);

  if (!today?.fen || !today?.played_move) return null;

  const commit = async (optionId) => {
    if (sending || answer) return;
    setChosen(optionId);
    setSending(true);
    try {
      const response = await fetch(`${API}/home/today/answer`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        // `position_id` is what retires this board so tomorrow is a different
        // one. Without it the same position comes back forever — which is
        // exactly what the first version of this did.
        body: JSON.stringify({
          topic: today.topic,
          reason_id: optionId,
          position_id: today.position_id,
        }),
      });
      setAnswer(response.ok ? await response.json() : null);
    } catch {
      // Losing the reply must not lose the board. He can pick again.
      setChosen(null);
    } finally {
      setSending(false);
    }
  };

  return (
    <section
      data-testid="coach-today"
      className="mb-10 overflow-hidden rounded-[28px] border border-border/70 bg-card p-6 shadow-[0_24px_70px_-50px_rgba(15,23,42,0.35)] md:p-8"
    >
      <div className="flex flex-col gap-7 md:flex-row md:items-start md:gap-9">
        <div className="aspect-square w-full max-w-[320px] shrink-0">
          <Chessboard
            position={today.fen}
            arePiecesDraggable={false}
            boardOrientation={today.user_color === "black" ? "black" : "white"}
            customBoardStyle={{ borderRadius: "10px" }}
          />
        </div>

        <div className="min-w-0 flex-1">
          <p className="cg-eyebrow !text-[10px]">From one of your games</p>
          <h2 className="mt-2 font-heading text-lg md:text-xl font-bold leading-snug tracking-tight text-foreground">
            You played {today.played_move} here.
          </h2>

          {!answer && (
            <>
              {/* THE CONTINUITY BEAT. This is what makes it the second session
                  rather than the first one again — not because the fact is
                  interesting, but because being remembered is the difference
                  between a coach and a worksheet. Absent on the first visit,
                  which is correct: there is nothing to remember yet. */}
              {today.last_time?.said && (
                <p
                  data-testid="coach-today-last-time"
                  className="mt-5 border-l-2 border-muted pl-4 text-[14px] leading-relaxed text-muted-foreground"
                >
                  Last time you told me: “{today.last_time.said}”
                </p>
              )}
              {/* Asked before anything is explained, and about his thinking
                  rather than about the position. */}
              <p className="mt-5 text-[15px] leading-relaxed text-foreground">
                {today.last_time?.said
                  ? `Same question on this one — ${lowerFirst(today.ask)}`
                  : `Before I tell you anything — ${lowerFirst(today.ask)}`}
              </p>
              <div className="mt-4 space-y-2">
                {today.options.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    disabled={sending}
                    onClick={() => commit(option.id)}
                    data-testid="coach-today-option"
                    className={`w-full rounded-2xl border px-4 py-3 text-left text-[14px] leading-snug transition ${
                      chosen === option.id
                        ? "border-primary/60 bg-primary/10 text-foreground"
                        : "border-border/70 bg-background text-foreground hover:border-primary/40 hover:bg-primary/[0.04]"
                    } disabled:opacity-60`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </>
          )}

          {answer && (
            <div className="mt-5" data-testid="coach-today-answer">
              {/* What he believed, named back to him. He picked a real rule
                  that works most of the time, not a wrong answer. */}
              {answer.belief && (
                <p className="text-[15px] leading-relaxed text-foreground">
                  {answer.belief}
                </p>
              )}
              {/* And where that belief breaks. Absent when he was right, which
                  is why the right answer gets no correction rather than a
                  congratulation. */}
              {answer.correction && (
                <p className="mt-4 border-l-2 border-primary/50 pl-4 text-[15px] leading-relaxed text-foreground">
                  {answer.correction}
                </p>
              )}
              {/* When it is the same belief as last time, the coach notices
                  rather than repeating itself. No count is ever printed —
                  "that is the third time" is a failure scoreboard. */}
              {answer.repeat && (
                <p
                  data-testid="coach-today-repeat"
                  className="mt-4 text-[14px] leading-relaxed text-muted-foreground"
                >
                  {answer.repeat}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

// The prompt is authored as a sentence ("What did you check before choosing
// the move?") and is being joined onto a lead-in, so it stops being one.
function lowerFirst(text) {
  if (!text) return text;
  return text.charAt(0).toLowerCase() + text.slice(1);
}

/* -------------------------------------------------------------- 3. play me */

function Play({ play }) {
  const navigate = useNavigate();
  if (!play?.href) return null;
  return (
    <section
      data-testid="coach-play"
      className="mb-6 overflow-hidden rounded-2xl border border-slate-200/90 dark:border-cyan-500/25 bg-white dark:bg-gradient-to-r dark:from-[#0d2232]/90 dark:via-[#102433]/90 dark:to-[#0c1622]/90 p-5 sm:p-6 shadow-[0_10px_30px_rgba(0,0,0,0.06)] dark:shadow-[0_15px_35px_rgba(0,0,0,0.5)] backdrop-blur-2xl relative"
    >
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-5">
        <div>
          <h2 className="font-heading font-bold text-2xl sm:text-3xl tracking-tight text-slate-900 dark:text-white">
            {play.lead}
          </h2>
          <p className="mt-2 max-w-2xl text-sm sm:text-base font-normal leading-relaxed text-slate-600 dark:text-slate-300">
            {play.line}
          </p>
        </div>
        <button
          type="button"
          onClick={() => navigate(play.href)}
          className="h-11 px-7 rounded-xl bg-gradient-to-r from-cyan-400 via-cyan-500 to-blue-600 hover:from-cyan-300 hover:to-blue-500 text-slate-950 font-heading font-bold text-xs sm:text-sm uppercase tracking-wider transition-all inline-flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(56,189,248,0.4)] cursor-pointer hover:scale-[1.02] active:scale-[0.98] shrink-0"
        >
          <span>{play.cta}</span>
        </button>
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------- the page */

/**
 * Two slots, because the order on screen is the argument:
 *
 *   `assessment` goes INSIDE movement one, after the sentences. The chances
 *   reading is Mohit's own ask — *"quality of moves vs chances provided"* — and
 *   it is an assessment, so it reads as part of what I know about you rather
 *   than as a fourth card. Taking it off the page would have undone something
 *   he asked for; moving it is the fix.
 *
 *   `children` goes BETWEEN movements two and three, which is where the lesson
 *   belongs. The invitation has to come last: asking someone to sit down for a
 *   game before telling them what to work on is the nav tile with a bigger
 *   button on it.
 *
 * Both slots render even when the session payload is missing, so a player whose
 * coach data has not been computed yet still gets their lesson.
 */
export default function CoachMovements({ assessment, children }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/home/session`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const coach = data?.coach;

  return (
    <div data-testid="coach-movements">
      <Known known={coach?.known} assessment={assessment} />
      <Today today={coach?.today} />
      {children}
      <Play play={coach?.play} />
    </div>
  );
}
