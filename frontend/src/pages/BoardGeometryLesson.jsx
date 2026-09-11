import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Check, ChevronRight, Eye, Loader2, RotateCcw, Shapes } from "lucide-react";
import { API } from "@/App";
import LichessBoard from "@/components/LichessBoard";
import { Button } from "@/components/ui/button";

const STAGE_LABELS = {
  baseline: "First look",
  attack_map: "See the shape",
  relationship: "Find the relationship",
  counterexample: "Real or fake?",
  create_or_avoid: "Use the shape",
  personal: "From your game",
  post_test: "Unseen check",
  delayed_recall: "Memory check",
};

const interactionId = () =>
  globalThis.crypto?.randomUUID?.() || `geometry-${Date.now()}-${Math.random()}`;

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : detail?.error || data.error || "Board Geometry is not available"
    );
  }
  return data;
}

function ModuleCatalog({ data, onStart, loadingModule }) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <main className="max-w-5xl mx-auto px-5 py-10 md:py-14">
        <Link
          to="/training"
          className="inline-flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground mb-10"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Training
        </Link>

        <div className="max-w-2xl mb-10">
          <p className="text-[10px] uppercase tracking-[0.24em] text-emerald-700 dark:text-emerald-300 font-semibold mb-3">
            Board Geometry
          </p>
          <h1 className="font-serif text-4xl md:text-5xl leading-tight mb-4">
            Learn the shapes before the tactics
          </h1>
          <p className="text-muted-foreground leading-relaxed">
            Four short visual lessons teach the board alphabet: diagonal, straight
            line, knight L, and pawn V. Then you find the same shape in your own game.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          {(data?.modules || []).map((module) => {
            const completed = (data.completed_modules || []).includes(module.module_id);
            const mastery = data?.mastery?.[module.module_id] || {};
            const delayedDue = Boolean(mastery.delayed_due);
            return (
              <article
                key={module.module_id}
                className="rounded-2xl border border-border bg-card p-5 md:p-6 flex flex-col min-h-[230px]"
              >
                <div className="flex items-start justify-between gap-4 mb-5">
                  <div className="w-11 h-11 rounded-xl bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 flex items-center justify-center">
                    <Shapes className="w-5 h-5" />
                  </div>
                  {delayedDue ? (
                    <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider text-amber-700 dark:text-amber-300">
                      Memory check due
                    </span>
                  ) : completed && (
                    <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider text-emerald-700 dark:text-emerald-300">
                      <Check className="w-3 h-3" /> Remembered
                    </span>
                  )}
                </div>
                <h2 className="font-serif text-2xl mb-2">{module.title}</h2>
                <p className="text-sm text-muted-foreground leading-relaxed mb-5">
                  {module.summary}
                </p>
                <p className="text-xs text-foreground/80 mb-6">
                  “{module.flash?.memory_line}”
                </p>
                <Button
                  className="mt-auto justify-between"
                  variant={completed && !delayedDue ? "outline" : "default"}
                  disabled={loadingModule === module.module_id}
                  onClick={() => onStart(
                    module.module_id,
                    delayedDue ? "delayed" : "learning"
                  )}
                >
                  <span>
                    {delayedDue
                      ? "Take memory check"
                      : completed
                        ? "Practice again"
                        : "Start lesson"}
                  </span>
                  {loadingModule === module.module_id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <ChevronRight className="w-4 h-4" />
                  )}
                </Button>
              </article>
            );
          })}
        </div>
      </main>
    </div>
  );
}

function FeedbackCard({ feedback, onContinue }) {
  if (!feedback) return null;
  const positive = feedback.correct || feedback.revealed;
  return (
    <div
      className={`rounded-xl border p-4 ${positive
        ? "border-emerald-500/30 bg-emerald-500/[0.07]"
        : "border-amber-500/30 bg-amber-500/[0.07]"}`}
      data-testid="geometry-feedback"
    >
      <p className="text-sm leading-relaxed">{feedback.feedback}</p>
      {(feedback.correct || feedback.revealed) && (
        <Button className="w-full mt-4" onClick={onContinue}>
          {feedback.complete ? "See your result" : "Continue"}
        </Button>
      )}
    </div>
  );
}

export default function BoardGeometryLesson({ user }) {
  const { moduleId } = useParams();
  const navigate = useNavigate();
  const [catalogData, setCatalogData] = useState(null);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingModule, setLoadingModule] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [selectedSquares, setSelectedSquares] = useState([]);
  const [hint, setHint] = useState("");
  const [feedback, setFeedback] = useState(null);
  const [boardNonce, setBoardNonce] = useState(0);

  const loadCatalog = useCallback(async () => {
    const data = await api("/training/geometry/catalog");
    setCatalogData(data);
    return data;
  }, []);

  const loadSession = useCallback(async (sessionId) => {
    const data = await api(`/training/geometry/session/${sessionId}`);
    setSession(data);
    setSelectedSquares([]);
    setHint("");
    setFeedback(null);
    setBoardNonce((n) => n + 1);
    return data;
  }, []);

  const start = useCallback(async (id, mode = "learning") => {
    if (moduleId !== id) {
      navigate(`/training/geometry/${id}`);
      return;
    }
    setLoadingModule(id);
    setError("");
    try {
      const data = await api("/training/geometry/start", {
        method: "POST",
        body: JSON.stringify({ module_id: id, mode }),
      });
      setSession(data);
      setSelectedSquares([]);
      setHint("");
      setFeedback(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingModule(null);
      setLoading(false);
    }
  }, [moduleId, navigate]);

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const data = await loadCatalog();
        if (!live) return;
        if (moduleId) {
          if (data.modules.some((m) => m.module_id === moduleId)) {
            await start(moduleId);
          } else {
            setError("Geometry module not found");
          }
        }
      } catch (e) {
        if (live) setError(e.message);
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => { live = false; };
  }, [loadCatalog, moduleId, start]);

  const act = async (response) => {
    if (!session || busy) return null;
    setBusy(true);
    setError("");
    try {
      const data = await api("/training/geometry/action", {
        method: "POST",
        body: JSON.stringify({
          session_id: session.session_id,
          interaction_id: interactionId(),
          response,
        }),
      });
      return data;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setBusy(false);
    }
  };

  const continueFlash = async () => {
    const data = await act({ action: "continue" });
    if (data) {
      setSession(data);
      setBoardNonce((n) => n + 1);
    }
  };

  const requestHint = async () => {
    const data = await act({ action: "hint" });
    if (data) setHint(data.hint || "");
  };

  const revealAnswer = async () => {
    const data = await act({ action: "reveal" });
    if (data) {
      setFeedback(data);
      setBoardNonce((n) => n + 1);
    }
  };

  const submit = async (response) => {
    const data = await act({ action: "answer", ...response });
    if (!data) return;
    setFeedback(data);
    if (!data.correct) setBoardNonce((n) => n + 1);
  };

  const continueAfterAnswer = async () => {
    if (feedback?.complete) {
      await loadSession(session.session_id);
      return;
    }
    await loadSession(session.session_id);
  };

  const item = session?.current_item;
  const showFlash = session?.display_stage === "flash";
  const complete = session?.status === "completed";
  const answerResolved = Boolean(feedback?.correct || feedback?.revealed);
  const shownFen =
    feedback?.reveal?.fen || item?.fen || session?.flash?.fen;
  const overlay = showFlash
    ? session?.flash?.overlays || {}
    : feedback?.reveal || {};
  const arrows = (overlay.arrows || []).map(([from, to]) => [from, to, "green"]);
  const circles = [
    ...(overlay.highlights || []).map((square) => [square, "green"]),
    ...selectedSquares.map((square) => [square, "yellow"]),
  ];
  const selectionKind = ["select_square", "select_piece", "select_targets"].includes(item?.kind);

  const toggleSquare = (square) => {
    if (!selectionKind || answerResolved) return;
    if (item.kind === "select_targets") {
      setSelectedSquares((current) =>
        current.includes(square)
          ? current.filter((value) => value !== square)
          : [...current, square]
      );
    } else {
      setSelectedSquares([square]);
    }
  };

  const progress = useMemo(() => {
    if (!session?.total_items) return 0;
    return Math.min(100, Math.round((session.current_index / session.total_items) * 100));
  }, [session]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted-foreground">
        <Loader2 className="w-5 h-5 animate-spin mr-2" /> Preparing the board…
      </div>
    );
  }

  if (!moduleId && catalogData) {
    return <ModuleCatalog data={catalogData} onStart={start} loadingModule={loadingModule} />;
  }

  if (error && !session) {
    return (
      <div className="max-w-xl mx-auto px-6 py-20 text-center">
        <p className="text-sm text-red-600 mb-5">{error}</p>
        <Button variant="outline" onClick={() => navigate("/training")}>Back to Training</Button>
      </div>
    );
  }

  if (complete) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center px-5">
        <div className="max-w-lg w-full rounded-2xl border border-border bg-card p-8 text-center">
          <div className="w-14 h-14 rounded-full bg-emerald-500/10 text-emerald-700 mx-auto mb-5 flex items-center justify-center">
            <Check className="w-7 h-7" />
          </div>
          <p className="text-[10px] uppercase tracking-[0.22em] text-emerald-700 font-semibold mb-3">
            {session.highest_earned_state === "remembered" ? "Remembered" : "Lesson complete"}
          </p>
          <h1 className="font-serif text-3xl mb-3">{session.title}</h1>
          <p className="text-sm text-muted-foreground leading-relaxed mb-7">
            {session.independent_passed
              ? "You found the shape on an unseen board without help. The next step is noticing it in a real game."
              : "You finished the lesson. Practice once more without a hint to make the result independent."}
          </p>
          <div className="grid gap-3">
            {session.independent_passed && catalogData?.pwc_available && (
              <Button
                onClick={() => navigate(
                  `/play-with-coach?geometry_focus=${encodeURIComponent(session.module_id)}`
                )}
              >
                Practice in Play with Coach
              </Button>
            )}
            {session.independent_passed && !catalogData?.pwc_available && (
              <p className="rounded-lg border border-border bg-muted/40 px-4 py-3 text-xs text-muted-foreground">
                Game practice will appear here after the internal lesson review.
              </p>
            )}
            <Button onClick={() => navigate("/training/geometry")}>Choose another shape</Button>
            <Button variant="outline" onClick={() => start(session.module_id)}>Practice again</Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <main className="max-w-6xl mx-auto px-5 py-6 md:py-10">
        <div className="flex items-center justify-between gap-4 mb-6">
          <button
            className="inline-flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground"
            onClick={() => navigate("/training/geometry")}
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Board Geometry
          </button>
          {!showFlash && (
            <span className="text-xs tabular-nums text-muted-foreground">
              {session.current_index + 1} of {session.total_items}
            </span>
          )}
        </div>

        <div className="h-1 rounded-full bg-muted overflow-hidden mb-8">
          <div
            className="h-full bg-emerald-500 transition-[width] duration-300"
            style={{ width: `${showFlash ? 4 : progress}%` }}
          />
        </div>

        <div className="grid lg:grid-cols-[minmax(0,620px)_minmax(300px,1fr)] gap-7 lg:gap-10 items-start">
          <section>
            <div className="rounded-2xl border border-border bg-card p-3 md:p-5 shadow-sm">
              <LichessBoard
                key={`${item?.item_id || "flash"}:${boardNonce}`}
                fen={shownFen}
                orientation={item?.orientation || session.flash?.orientation || "white"}
                onMove={item?.kind === "move" && !answerResolved ? (move) => submit({ move: move.san }) : undefined}
                onSquareClick={selectionKind && !answerResolved ? toggleSquare : undefined}
                selectionOnly={selectionKind && !answerResolved}
                interactive={!answerResolved && (item?.kind === "move" || selectionKind)}
                viewOnly={showFlash || answerResolved}
                showDests={item?.kind === "move"}
                arrows={arrows}
                circles={circles}
              />
            </div>
          </section>

          <aside className="rounded-2xl border border-border bg-card p-5 md:p-6">
            {showFlash ? (
              <>
                <p className="text-[10px] uppercase tracking-[0.23em] text-emerald-700 dark:text-emerald-300 font-semibold mb-3">
                  Geometry flash
                </p>
                <h1 className="font-serif text-3xl leading-tight mb-3">{session.title}</h1>
                <p className="text-xl leading-snug mb-4">{session.flash.memory_line}</p>
                <p className="text-sm text-muted-foreground leading-relaxed mb-7">
                  {session.flash.supporting_line}
                </p>
                <Button className="w-full" onClick={continueFlash} disabled={busy}>
                  {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : "Show me"}
                </Button>
              </>
            ) : (
              <>
                <div className="flex items-center justify-between gap-3 mb-4">
                  <p className="text-[10px] uppercase tracking-[0.22em] text-emerald-700 dark:text-emerald-300 font-semibold">
                    {STAGE_LABELS[item?.stage] || "Board check"}
                  </p>
                  {item?.stage === "personal" && (
                    <span className="text-[10px] uppercase tracking-wider text-violet-600">
                      {item.moment_type?.replace("_", " ")}
                    </span>
                  )}
                </div>
                <h1 className="font-serif text-2xl md:text-3xl leading-tight mb-6">
                  {item?.prompt}
                </h1>

                {item?.kind === "choose" && !answerResolved && (
                  <div className="grid grid-cols-2 gap-3 mb-5">
                    <Button variant="outline" onClick={() => submit({ choice: "yes" })} disabled={busy}>Yes</Button>
                    <Button variant="outline" onClick={() => submit({ choice: "no" })} disabled={busy}>No</Button>
                  </div>
                )}

                {selectionKind && !answerResolved && (
                  <Button
                    className="w-full mb-5"
                    disabled={busy || selectedSquares.length === 0}
                    onClick={() => submit({ squares: selectedSquares })}
                  >
                    Check my answer
                  </Button>
                )}

                {item?.kind === "move" && !answerResolved && (
                  <p className="text-sm text-muted-foreground mb-5">
                    Move the piece on the board. The lesson checks the legal move directly.
                  </p>
                )}

                {hint && (
                  <div className="rounded-lg bg-muted/50 border border-border px-3.5 py-3 text-sm mb-4">
                    {hint}
                  </div>
                )}
                <FeedbackCard feedback={feedback} onContinue={continueAfterAnswer} />

                {!answerResolved && (
                  <div className="flex items-center justify-between gap-3 mt-6 pt-5 border-t border-border">
                    <button
                      className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
                      onClick={requestHint}
                      disabled={busy}
                    >
                      <Eye className="w-3.5 h-3.5" /> Hint
                    </button>
                    <button
                      className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
                      onClick={revealAnswer}
                      disabled={busy}
                    >
                      <RotateCcw className="w-3.5 h-3.5" /> Show the shape
                    </button>
                  </div>
                )}
              </>
            )}
            {error && <p className="text-xs text-red-600 mt-4">{error}</p>}
          </aside>
        </div>
      </main>
    </div>
  );
}
