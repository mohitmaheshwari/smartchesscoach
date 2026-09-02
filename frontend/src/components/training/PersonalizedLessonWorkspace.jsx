import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  Eye,
  HelpCircle,
  Loader2,
  MessageCircleQuestion,
  RotateCcw,
} from "lucide-react";
import { API } from "../../App";
import LichessBoard from "../LichessBoard";
import Layout from "../Layout";
import {
  curriculumStateLabel,
  invalidatePersonalCurriculum,
} from "../../lib/personalCurriculum";

const interactionId = (prefix) =>
  globalThis.crypto?.randomUUID?.() ||
  `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;

const STAGE_LABELS = {
  diagnose: "First, show me what you notice",
  explain: "Make the idea clear",
  guide: "Try it with your coach",
  recall: "Find it again",
  mix: "Spot it among other ideas",
  transfer: "New position · no answer shown",
  apply: "Use it in a game",
  retain: "Check that it stayed with you",
};

const HELP_ACTIONS = [
  { id: "show_on_board", label: "Show it on the board", icon: Eye },
  { id: "ask_one_question", label: "Ask me one question", icon: MessageCircleQuestion },
  { id: "let_me_try", label: "Let me try", icon: RotateCcw },
];

function EvidencePanel({ session, evidence, onLoadEvidence }) {
  const profile = session?.teaching_profile || {};
  return (
    <details
      className="rounded-xl border border-border/70 bg-card/70"
      onToggle={(event) => {
        if (event.currentTarget.open && evidence === null) onLoadEvidence();
      }}
    >
      <summary className="cursor-pointer list-none px-4 py-3 flex items-center justify-between gap-3 text-sm font-medium text-foreground">
        What I noticed in your games
        <ChevronDown className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
      </summary>
      <div className="border-t border-border/70 px-4 py-4 space-y-4">
        <p className="text-sm leading-relaxed text-muted-foreground">
          {profile.why_now || "I need one answer from you before I can personalize this further."}
        </p>
        {(profile.anchors || []).map((anchor, index) => (
          <div key={`${anchor.type}-${index}`} className="text-xs leading-relaxed">
            <p className="text-foreground">{anchor.message}</p>
          </div>
        ))}
        {evidence === undefined && (
          <p className="text-xs text-muted-foreground">I’m checking the games that led me here…</p>
        )}
        {Array.isArray(evidence) && evidence.length > 0 && (
          <p className="text-xs text-muted-foreground">
            I chose this lesson from decisions I have already seen in your chess.
          </p>
        )}
      </div>
    </details>
  );
}

export default function PersonalizedLessonWorkspace({
  contentKind,
  contentId,
  reviewMode = false,
  variation = "",
  mode = "",
  user = null,
}) {
  const navigate = useNavigate();
  const boardRef = useRef(null);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [help, setHelp] = useState(null);
  const [reasonChoice, setReasonChoice] = useState("");
  const [pendingMove, setPendingMove] = useState(null);
  const [boardRevision, setBoardRevision] = useState(0);
  const [evidence, setEvidence] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await fetch(`${API}/training/personalized/session/start`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            content_kind: contentKind,
            content_id: contentId,
            review: reviewMode,
            variation: variation || undefined,
            mode: mode || undefined,
          }),
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || "Could not start this lesson");
        if (!cancelled) setSession(payload);
      } catch (lessonError) {
        if (!cancelled) setError(lessonError.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [contentKind, contentId, reviewMode, variation, mode]);

  const pause = async () => {
    if (session?.session_id) {
      await fetch(`${API}/training/personalized/session/pause`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: session.session_id, choice: "pause" }),
      }).catch(() => null);
    }
    navigate("/learn");
  };

  const askForHelp = async (action) => {
    if (!session?.session_id || busy) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${API}/training/personalized/session/help`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: session.session_id,
          action,
          interaction_id: interactionId("help"),
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Could not open that help");
      setHelp(payload);
      setSession((currentSession) => ({
        ...currentSession,
        stage: payload.stage || currentSession.stage,
      }));
      if (action === "show_on_board") {
        boardRef.current?.highlightSquares(payload.highlight_squares || []);
      } else if (action === "let_me_try") {
        boardRef.current?.clearArrows();
      }
    } catch (helpError) {
      setError(helpError.message);
    } finally {
      setBusy(false);
    }
  };

  const stageMove = (moveData) => {
    const current = session?.current_item;
    if (!current || busy || pendingMove) return;
    setPendingMove({
      uci: `${moveData.from}${moveData.to}${moveData.promotion || ""}`,
      san: moveData.san || "",
    });
    setReasonChoice("");
    setFeedback(null);
    setError(null);
    setHelp(null);
  };

  const submitMove = async (selectedReason) => {
    const current = session?.current_item;
    if (!current || busy || !pendingMove || !selectedReason) return;
    setBusy(true);
    setError(null);
    setFeedback(null);
    setReasonChoice(selectedReason);
    try {
      const response = await fetch(`${API}/training/personalized/session/respond`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: session.session_id,
          move: pendingMove.uci,
          reason_choice: selectedReason,
          interaction_id: interactionId("answer"),
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Could not check that move");
      setFeedback(payload);
      setHelp(null);
      if (payload.complete) invalidatePersonalCurriculum();
      setSession((currentSession) => ({
        ...currentSession,
        status: payload.complete ? "completed" : "active",
        current_index: payload.current_index,
        completed_items: payload.current_index,
        current_item: payload.next_item,
        stage: payload.next_stage || payload.next_item?.stage || "retain",
        learner_state: {
          ...currentSession.learner_state,
          state: payload.highest_earned_state,
        },
        teaching_profile: payload.teaching_profile || currentSession.teaching_profile,
      }));
      setPendingMove(null);
      setReasonChoice("");
      setBoardRevision((revision) => revision + 1);
    } catch (moveError) {
      setError(moveError.message);
      setPendingMove(null);
      setReasonChoice("");
      setBoardRevision((revision) => revision + 1);
    } finally {
      setBusy(false);
    }
  };

  const chooseDifferentMove = () => {
    if (busy) return;
    setPendingMove(null);
    setReasonChoice("");
    setFeedback(null);
    setError(null);
    setBoardRevision((revision) => revision + 1);
  };

  const loadEvidence = async () => {
    if (!session?.session_id || evidence !== null) return;
    setEvidence(undefined);
    try {
      const response = await fetch(
        `${API}/training/personalized/session/${session.session_id}/evidence`,
        { credentials: "include" }
      );
      const payload = await response.json();
      setEvidence(response.ok ? payload.evidence || [] : []);
    } catch {
      setEvidence([]);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-emerald-700" />
      </div>
    );
  }

  if (error && !session) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center px-6">
        <div className="max-w-md text-center">
          <p className="text-foreground mb-4">{error}</p>
          <button className="text-emerald-700 hover:underline" onClick={() => navigate("/learn")}>Return to Learn</button>
        </div>
      </div>
    );
  }

  if (session?.status === "completed") {
    const state = session.learner_state?.state || "learning";
    return (
      <div className="min-h-screen bg-background flex items-center justify-center px-6 py-10">
        <div className="w-full max-w-xl text-center">
          <CheckCircle2 className="h-11 w-11 text-emerald-700 mx-auto mb-4" />
          <p className="text-[11px] uppercase tracking-[0.18em] text-emerald-700 font-semibold mb-2">
            {curriculumStateLabel(state)}
          </p>
          <h1 className="font-heading text-3xl text-foreground mb-3">You found the idea.</h1>
          <p className="text-sm leading-relaxed text-muted-foreground mb-6">
            Now I want to see whether the same thought appears when nobody tells you this is the lesson.
          </p>
          <EvidencePanel session={session} evidence={evidence} onLoadEvidence={loadEvidence} />
          <button onClick={() => navigate("/learn")} className="cg-primary-action mt-6">
            Return to your plan
          </button>
        </div>
      </div>
    );
  }

  const item = session?.current_item;
  const stage = item?.stage || session?.stage || "guide";
  const isReady = !pendingMove && !busy;
  const preferredHelp = session?.teaching_profile?.delivery?.preferred_help;
  const helpActions = [...HELP_ACTIONS].sort((left, right) => (
    left.id === preferredHelp ? -1 : right.id === preferredHelp ? 1 : 0
  ));

  const workspace = (
    <div className="experience-page experience-lesson-page min-h-screen bg-background">
      <main className="cg-page cg-page--wide">
        <button onClick={pause} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-7">
          <ArrowLeft className="h-4 w-4" /> Continue later
        </button>
        <div className="grid lg:grid-cols-[minmax(0,620px)_minmax(300px,1fr)] gap-8 items-start">
          <div className="w-full max-w-[620px]">
            {item && (
              <LichessBoard
                ref={boardRef}
                key={`${item.item_id}-${boardRevision}`}
                fen={item.fen}
                orientation={item.orientation || "white"}
                onMove={stageMove}
                interactive={isReady}
                arrows={[]}
              />
            )}
            {!pendingMove && (
              <p className="mt-3 text-xs text-center text-muted-foreground">
                Make your move first. Then your coach will ask what you saw.
              </p>
            )}
          </div>

          <aside className="cg-panel p-5 md:p-6">
            <p className="cg-eyebrow mb-2">
              {STAGE_LABELS[stage] || "Work through the position"}
            </p>
            <h1 className="font-heading text-3xl leading-tight tracking-[-0.03em] text-foreground mb-3">
              {session?.lesson?.title}
            </h1>
            <p className="text-sm leading-relaxed text-muted-foreground mb-4">
              {session?.teaching_profile?.why_now}
            </p>
            <div className="rounded-xl border border-emerald-700/20 bg-emerald-50/60 dark:bg-emerald-950/20 p-4 mb-5">
              <p className="text-[10px] uppercase tracking-[0.16em] text-emerald-800 dark:text-emerald-300 font-semibold mb-1.5">The idea</p>
              <p className="text-sm leading-relaxed text-foreground">{session?.lesson?.rule}</p>
            </div>
            <p className="text-sm font-medium text-foreground mb-1">{item?.prompt}</p>
            <p className="text-xs text-muted-foreground mb-4">
              {item?.source === "own_game"
                ? "This position comes from one of your games."
                : "This is a new position chosen for the same idea."}
            </p>

            {!pendingMove ? (
              <div className="mb-5 rounded-xl border border-border/70 bg-muted/25 p-4">
                <p className="text-sm font-medium text-foreground">Make the move you would choose.</p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  I’ll ask what you noticed after the piece lands, so your explanation cannot steer the move.
                </p>
              </div>
            ) : (
              <fieldset className="mb-5">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs text-muted-foreground">
                    You played {pendingMove.san || pendingMove.uci}.
                  </p>
                  <button
                    type="button"
                    onClick={chooseDifferentMove}
                    disabled={busy}
                    className="text-xs font-medium text-emerald-800 hover:underline disabled:opacity-50"
                  >
                    Choose a different move
                  </button>
                </div>
                <legend className="text-sm font-medium text-foreground mb-2">{item?.reason_prompt}</legend>
                <div className="space-y-2">
                  {(item?.reason_choices || []).map((choice) => (
                    <button
                      type="button"
                      key={choice.id}
                      aria-pressed={reasonChoice === choice.id}
                      disabled={busy}
                      onClick={() => submitMove(choice.id)}
                      className={`w-full text-left rounded-lg border px-3 py-2.5 text-sm transition-colors disabled:opacity-50 ${
                        reasonChoice === choice.id
                          ? "border-[#B7F34A] bg-[#B7F34A]/15 text-foreground"
                          : "border-border hover:bg-muted/60 text-foreground"
                      }`}
                    >
                      {choice.label}
                    </button>
                  ))}
                </div>
              </fieldset>
            )}

            <div className="flex flex-wrap gap-2 mb-5" aria-label="Lesson help">
              {helpActions.map(({ id, label, icon: Icon }) => (
                <button
                  type="button"
                  key={id}
                  onClick={() => askForHelp(id)}
                  disabled={busy}
                  className="min-h-9 px-3 rounded-lg border border-border hover:bg-muted/60 disabled:opacity-50 text-xs font-medium inline-flex items-center gap-1.5"
                >
                  <Icon className="h-3.5 w-3.5" aria-hidden="true" /> {label}
                  {id === preferredHelp ? " · try this first" : ""}
                </button>
              ))}
            </div>

            {help?.message && (
              <div className="rounded-lg border border-violet-200 bg-violet-50 p-3 text-sm leading-relaxed text-violet-950 dark:border-violet-900 dark:bg-violet-950/30 dark:text-violet-100 mb-4">
                {help.message}
              </div>
            )}
            {feedback && (
              <div className={`rounded-lg border p-4 text-sm leading-relaxed mb-4 ${
                feedback.correct
                  ? "border-emerald-200 bg-emerald-50 text-emerald-950 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-100"
                  : "border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100"
              }`}>
                <p>{feedback.feedback || (feedback.correct ? "You found it." : "Look once more.")}</p>
                {!feedback.correct && feedback.answer_san && (
                  <p className="mt-2">With your coach helping, the move is {feedback.answer_san}. Reset the board and explain what it fixes.</p>
                )}
                {!feedback.correct && !feedback.answer_san && (
                  <p className="mt-2">The answer stays hidden on this new position. Use the correction and try again.</p>
                )}
              </div>
            )}
            {error && <p className="text-sm text-red-600 mb-4">{error}</p>}
            {busy && <p className="text-sm text-muted-foreground mb-4">Your coach is checking the move and the reason…</p>}
            <EvidencePanel session={session} evidence={evidence} onLoadEvidence={loadEvidence} />
            <div className="mt-4 flex items-start gap-2 text-[11.5px] leading-relaxed text-muted-foreground">
              <HelpCircle className="h-4 w-4 shrink-0 mt-0.5" aria-hidden="true" />
              I’ll use this help for today’s lesson only. You can choose a different kind of help whenever you need it.
            </div>
          </aside>
        </div>
      </main>
    </div>
  );

  return user ? <Layout user={user}>{workspace}</Layout> : workspace;
}
