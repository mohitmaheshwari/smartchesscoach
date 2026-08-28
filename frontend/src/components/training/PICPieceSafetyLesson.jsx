import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Loader2, ShieldCheck } from "lucide-react";
import { API } from "@/App";
import LichessBoard from "@/components/LichessBoard";
import { ANALYTICS_EVENTS, track } from "@/lib/analytics";

const newInteractionId = () =>
  globalThis.crypto?.randomUUID?.() ||
  `pic-move-${Date.now()}-${Math.random().toString(16).slice(2)}`;

export default function PICPieceSafetyLesson({ projection }) {
  const navigate = useNavigate();
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [error, setError] = useState(null);
  const [boardRevision, setBoardRevision] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await fetch(`${API}/training/pic/session/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ limit: 5 }),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "Could not start this lesson");
        if (!cancelled) {
          setSession(result);
          track(ANALYTICS_EVENTS.PIC_LESSON_STARTED, {
            resumed: result.current_index > 0,
            total_items: result.total_items,
          });
        }
      } catch (lessonError) {
        if (!cancelled) setError(lessonError.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const currentItem = session?.current_item;

  const submitMove = async (moveData) => {
    if (busy || !moveData || !currentItem) return;
    const playedUci = `${moveData.from}${moveData.to}${moveData.promotion || ""}`;
    setBusy(true);
    setFeedback(null);
    try {
      const response = await fetch(`${API}/training/pic/session/move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: session.session_id,
          move: playedUci,
          interaction_id: newInteractionId(),
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Could not check that move");
      setFeedback(result);
      track(ANALYTICS_EVENTS.PIC_LESSON_MOVE_CHECKED, {
        correct: result.correct,
        item_id: currentItem.item_id,
      });
      if (result.correct) {
        setSession((current) => ({
          ...current,
          status: result.complete ? "completed" : "active",
          current_index: result.current_index,
          completed_items: result.current_index,
          current_item: result.next_item,
        }));
        setBoardRevision((revision) => revision + 1);
      } else {
        // Chessground has already applied the rejected move. Remount from
        // the frozen lesson FEN so a retry always starts from identical data.
        setBoardRevision((revision) => revision + 1);
      }
    } catch (moveError) {
      setError(moveError.message);
      setBoardRevision((revision) => revision + 1);
    } finally {
      setBusy(false);
    }
  };

  const pause = async () => {
    if (!session?.session_id) return navigate("/home");
    setBusy(true);
    try {
      await fetch(`${API}/training/pic/session/pause`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: session.session_id,
          choice: "pause",
        }),
      });
    } finally {
      navigate("/home");
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-violet-500" />
      </div>
    );
  }

  if (error && !session) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center px-6">
        <div className="max-w-md text-center">
          <p className="text-foreground mb-4">{error}</p>
          <button onClick={() => navigate("/home")} className="text-violet-600 hover:underline">
            Return home
          </button>
        </div>
      </div>
    );
  }

  if (session?.status === "completed") {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center px-6">
        <div className="max-w-lg text-center">
          <CheckCircle2 className="w-10 h-10 text-emerald-600 mx-auto mb-4" />
          <p className="text-[11px] uppercase tracking-[0.2em] text-violet-600 font-semibold mb-2">
            {projection.learner_state?.label || "Learning"}
          </p>
          <h1 className="font-serif text-3xl text-foreground mb-3">Practice complete</h1>
          <p className="text-sm leading-relaxed text-muted-foreground mb-6">
            You worked through {session.total_items} verified piece-safety positions.
            This was assisted practice, so it does not prove the habit is retained
            or applied in games.
          </p>
          <button
            onClick={() => navigate("/home")}
            className="h-10 px-5 rounded-lg bg-violet-500 text-white font-medium"
          >
            Return to your coach
          </button>
        </div>
      </div>
    );
  }

  const orientation = currentItem?.fen?.split(" ")?.[1] === "b" ? "black" : "white";

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-5xl mx-auto px-5 py-6 md:py-10">
        <button
          onClick={pause}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-7"
        >
          <ArrowLeft className="w-4 h-4" /> Continue later
        </button>
        <div className="grid lg:grid-cols-[minmax(0,620px)_minmax(260px,1fr)] gap-8 items-start">
          <div className="w-full max-w-[620px]">
            {currentItem && (
              <LichessBoard
                key={`${currentItem.item_id}-${boardRevision}`}
                fen={currentItem.fen}
                orientation={orientation}
                onMove={submitMove}
                interactive={!busy}
                disableArrows
              />
            )}
          </div>
          <aside className="pt-1">
            <div className="flex items-center gap-2 text-violet-600 dark:text-violet-400 mb-3">
              <ShieldCheck className="w-5 h-5" />
              <span className="text-[11px] uppercase tracking-[0.18em] font-semibold">
                Keeping your pieces safe
              </span>
            </div>
            <h1 className="font-serif text-2xl text-foreground mb-3">
              Is every piece safe after your move?
            </h1>
            <p className="text-sm leading-relaxed text-muted-foreground mb-5">
              {projection.instruction_text ||
                "Before moving, check whether the piece will be safe on its new square."}
            </p>
            <p className="text-xs text-muted-foreground mb-5">
              Position {session.current_index + 1} of {session.total_items}
              {currentItem?.source === "own_game" ? " · from your game" : " · verified practice"}
            </p>
            {busy && (
              <p className="text-sm text-muted-foreground">Checking your move…</p>
            )}
            {feedback && !busy && (
              <div
                className={`rounded-lg border p-4 text-sm leading-relaxed ${
                  feedback.correct
                    ? "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-200"
                    : "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200"
                }`}
              >
                {feedback.feedback || (feedback.correct ? "Correct." : "Try again.")}
                {!feedback.correct && feedback.best_move_san && (
                  <span> A safe continuation was {feedback.best_move_san}.</span>
                )}
              </div>
            )}
            {error && <p className="text-sm text-red-600 mt-4">{error}</p>}
            <p className="text-[11.5px] leading-relaxed text-muted-foreground mt-6">
              Practice with help is recorded separately from silent checkpoints
              and real Focus Games.
            </p>
          </aside>
        </div>
      </div>
    </div>
  );
}
