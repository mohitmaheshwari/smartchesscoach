import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  CircleDashed,
  Eye,
  Loader2,
  MessageCircleQuestion,
  Pause,
  RotateCcw,
  Sparkles,
  Target,
} from "lucide-react";
import { API } from "@/App";
import LichessBoard from "@/components/LichessBoard";
import { ANALYTICS_EVENTS, trackHomeDiagnostic } from "@/lib/analytics";

const interactionId = (prefix) =>
  globalThis.crypto?.randomUUID?.() ||
  `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;

const RESULT_COPY = {
  controlled_transfer: {
    eyebrow: "You carried it across",
    title: "That idea is available to you now.",
    body: "You handled the same decision in two different positions without coaching. That proves recognition here—not improvement in your games yet.",
    follow: "I’m moving this into watching mode. The next honest answer comes from what you do when the decision appears naturally in a game.",
    cta: "Play while I watch",
  },
  familiar_position_only: {
    eyebrow: "It did not travel yet",
    title: "You saw it once, but not in the new shape.",
    body: "That tells me the first position felt familiar. You do not yet spot the same danger when the pieces look different.",
    follow: "Next I’ll teach you to check the piece you move, the square it lands on and what your opponent can capture next—not ask you to memorize a move.",
    cta: "Teach me the signal",
  },
  prompted_recognition: {
    eyebrow: "The idea appeared with a prompt",
    title: "You can find it when I slow the moment down.",
    body: "That is useful evidence. The chess idea is beginning to make sense, but you do not yet remember to check it before moving.",
    follow: "Next we’ll turn the hint into one small question you can ask yourself over the board.",
    cta: "Build my trigger",
  },
  current_learning_need: {
    eyebrow: "Now I know where to begin",
    title: "This way of checking a move is still new.",
    body: "That is not a score and it is not a label. It tells me explanation comes before repetition here.",
    follow: "I’ll show you what changes after the move, then let you rebuild the idea in another position.",
    cta: "Teach it from the board",
  },
  no_conclusion: {
    eyebrow: "I’m not going to guess",
    title: "I could not verify this fairly.",
    body: "One of the chess checks was incomplete, so I am keeping your coaching plan unchanged.",
    follow: "We can return when two fully verified positions are ready.",
    cta: "Continue my plan",
  },
};

const LATER_MISS_COPY = {
  eyebrow: "I saw the decision again",
  title: "It returned in a real game, so we stay with it.",
  body: "You recognized the idea in practice, but later you again moved a piece to a square where it could be won. That is stronger evidence than a puzzle score.",
  follow: "We are not starting over. I’ll reconnect the real-game moment to the board question you already understood, then test it again without help.",
  cta: "Return to the board",
};

const COMPONENT_LABELS = {
  incoming_threat: "Threat recognized",
  destination_safety: "Landing square checked",
  counterattack: "Attack back noticed",
  one_recapture_calculation: "One reply calculated",
};

async function diagnosticRequest(path, body) {
  const response = await fetch(`${API}/training/personalized/diagnostic${path}`, {
    method: body === undefined ? "GET" : "POST",
    credentials: "include",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "Your coach could not open this yet.");
  return payload;
}

export default function HomeReplayDiagnostic({ diagnostic, onNavigate }) {
  const boardRef = useRef(null);
  const shownRef = useRef(false);
  const [session, setSession] = useState(diagnostic?.session || null);
  const [state, setState] = useState(diagnostic?.state || "ready");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [pendingMove, setPendingMove] = useState(
    diagnostic?.session?.pending_move_uci || ""
  );
  const [help, setHelp] = useState(null);
  const [coachMessage, setCoachMessage] = useState("");
  const [boardRevision, setBoardRevision] = useState(0);
  const result = session?.diagnostic_result || diagnostic?.session?.diagnostic_result;
  const resultDestination = result?.conclusion === "controlled_transfer"
    ? "/play-with-coach"
    : "/learn";

  useEffect(() => {
    if (shownRef.current) return;
    shownRef.current = true;
    trackHomeDiagnostic(ANALYTICS_EVENTS.HOME_DIAGNOSTIC_SHOWN, {
      surface: "home",
      state: diagnostic?.state || "ready",
    });
  }, [diagnostic?.state]);

  const start = async () => {
    if (busy) return;
    setBusy(true);
    setError("");
    setCoachMessage("");
    try {
      const payload = await diagnosticRequest("/start", { limit: 20 });
      setSession(payload);
      setState(payload.awaiting_reason ? "reflection" : "active");
      trackHomeDiagnostic(ANALYTICS_EVENTS.HOME_DIAGNOSTIC_STARTED, {
        surface: "home",
        state: payload.status === "paused" ? "resumed" : "started",
      });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  const stageMove = async (moveData) => {
    if (!session?.session_id || busy || session.awaiting_reason) return;
    const uci = `${moveData.from}${moveData.to}`;
    setBusy(true);
    setError("");
    setHelp(null);
    try {
      const payload = await diagnosticRequest("/respond", {
        session_id: session.session_id,
        move: uci,
        interaction_id: interactionId("home-stage"),
      });
      if (payload.measurement_status === "unmeasured") {
        setSession((current) => ({ ...current, ...payload }));
        setPendingMove("");
        setCoachMessage(payload.message || "");
        setState("active");
        setBoardRevision((value) => value + 1);
        return;
      }
      setPendingMove(uci);
      setSession((current) => ({ ...current, ...payload }));
      setState("reflection");
      trackHomeDiagnostic(ANALYTICS_EVENTS.HOME_DIAGNOSTIC_MOVE_STAGED, {
        surface: "home",
        position_index: (session.current_index || 0) + 1,
      });
    } catch (requestError) {
      setError(requestError.message);
      setBoardRevision((value) => value + 1);
    } finally {
      setBusy(false);
    }
  };

  const submitReason = async (reasonChoice) => {
    if (!pendingMove || busy) return;
    setBusy(true);
    setError("");
    try {
      const activeQuestion = session?.current_item?.reason_question || {
        question_id: "legacy-reason",
        progress: { current: 1, total: 1 },
      };
      const payload = await diagnosticRequest("/respond", {
        session_id: session.session_id,
        move: pendingMove,
        reason_choice: reasonChoice,
        reason_component_id: activeQuestion.question_id,
        interaction_id: interactionId("home-reason"),
      });
      const progress = activeQuestion.progress || {};
      trackHomeDiagnostic(ANALYTICS_EVENTS.HOME_DIAGNOSTIC_COMPONENT_SUBMITTED, {
        surface: "home",
        position_index: (session.current_index || 0) + 1,
        question_index: progress.current,
        question_total: progress.total,
      });
      if (payload.awaiting_reason) {
        setSession((current) => ({ ...current, ...payload }));
        setState("reflection");
      } else if (payload.awaiting_continue) {
        setSession((current) => ({ ...current, ...payload, awaiting_reason: false }));
        setPendingMove("");
        setState("connection");
      } else if (payload.complete) {
        setSession((current) => ({
          ...current,
          ...payload,
          status: "completed",
          current_item: null,
        }));
        setState("result");
        trackHomeDiagnostic(ANALYTICS_EVENTS.HOME_DIAGNOSTIC_COMPLETED, {
          surface: "home",
          conclusion: payload.diagnostic_result?.conclusion,
          separate_soundness_issue: Boolean(
            payload.diagnostic_result?.separate_soundness_issue
          ),
        });
      } else {
        setSession((current) => ({
          ...current,
          current_index: payload.current_index,
          current_item: payload.next_item,
          awaiting_reason: false,
          stage: payload.next_stage,
        }));
        setState("active");
        setPendingMove("");
        setBoardRevision((value) => value + 1);
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  const continueToTransfer = async () => {
    if (!session?.session_id || busy) return;
    setBusy(true);
    setError("");
    try {
      const payload = await diagnosticRequest("/continue", {
        session_id: session.session_id,
        interaction_id: interactionId("home-transfer"),
      });
      setSession(payload);
      setPendingMove("");
      setHelp(null);
      setState("active");
      setBoardRevision((value) => value + 1);
      trackHomeDiagnostic(ANALYTICS_EVENTS.HOME_DIAGNOSTIC_TRANSFER_STARTED, {
        surface: "home",
        position_index: (payload.current_index || 0) + 1,
      });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  const requestHelp = async (action) => {
    if (!session?.session_id || busy || session.awaiting_reason) return;
    setBusy(true);
    setError("");
    try {
      const payload = await diagnosticRequest("/help", {
        session_id: session.session_id,
        action,
        interaction_id: interactionId("home-help"),
      });
      setHelp(payload);
      if (action === "show_on_board") {
        boardRef.current?.highlightSquares(payload.highlight_squares || []);
      }
      if (action === "let_me_try") boardRef.current?.clearArrows();
      trackHomeDiagnostic(ANALYTICS_EVENTS.HOME_DIAGNOSTIC_HELP_REQUESTED, {
        surface: "home",
        help_action: action,
        position_index: (session.current_index || 0) + 1,
      });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  const pause = async () => {
    if (!session?.session_id || busy) return;
    setBusy(true);
    try {
      await diagnosticRequest("/pause", {
        session_id: session.session_id,
        choice: "pause",
      });
      setSession((current) => ({ ...current, status: "paused" }));
      trackHomeDiagnostic(ANALYTICS_EVENTS.HOME_DIAGNOSTIC_PAUSED, {
        surface: "home",
        state: "paused",
      });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  const startNextAction = () => {
    trackHomeDiagnostic(ANALYTICS_EVENTS.HOME_DIAGNOSTIC_NEXT_ACTION_STARTED, {
      surface: "home",
      conclusion: result?.conclusion,
      next_action: result?.next_action,
    });
    onNavigate(resultDestination);
  };

  if (state === "ready" || session?.status === "paused") {
    return (
      <section data-testid="home-replay-diagnostic-ready" className="relative overflow-hidden">
        <div className="pointer-events-none absolute -right-16 -top-20 h-64 w-64 rounded-full bg-lime-300/30 blur-3xl" />
        <div className="relative grid gap-8 lg:grid-cols-[minmax(0,1fr)_280px] lg:items-start">
          <div>
            <p className="cg-eyebrow mb-3">Today’s coaching move</p>
            <h2 className="max-w-[650px] font-heading text-[30px] leading-[1.04] tracking-[-0.04em] text-foreground sm:text-[44px]">
              Learn to hit back without hanging the piece.
            </h2>
            <p className="mt-4 max-w-[620px] text-[14px] leading-relaxed text-muted-foreground sm:text-[15px]">
              You already notice when one of your pieces is attacked. The next step is choosing a square that is both protected and useful.
            </p>
            <div className="mt-6 max-w-[620px] rounded-2xl border border-emerald-700/15 bg-emerald-500/[0.06] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-800">Why I chose this for you</p>
              <p className="mt-2 text-[13px] leading-relaxed text-foreground/75">
                I rebuilt one moment from your games to check the chess idea—not whether you remember the old game.
              </p>
            </div>
            <div className="mt-7 flex flex-wrap items-center gap-3">
              <button type="button" onClick={start} disabled={busy} className="cg-primary-action !bg-lime-300 !text-black hover:!bg-lime-200">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                {session?.status === "paused" ? "Continue the position" : "Try the position"}
                {!busy && <ArrowRight className="h-4 w-4" />}
              </button>
              <span className="text-[12px] text-muted-foreground">Your move comes before my explanation.</span>
            </div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-background/60 p-5">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">How this becomes yours</p>
            {[
              ["1", "Understand the connection", "See the threat, the safe square and the reply as one idea."],
              ["2", "Prove it somewhere new", "Find the same relationship on a board that looks different."],
              ["3", "Use it in your games", "I wait for a real opportunity before calling it learned."],
            ].map(([number, title, body]) => (
              <div key={number} className="mt-4 flex gap-3">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-lime-300 text-[12px] font-semibold text-black">{number}</span>
                <div>
                  <p className="text-[13px] font-medium text-foreground">{title}</p>
                  <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
        {error && <p role="alert" className="mt-4 text-sm text-red-600">{error}</p>}
      </section>
    );
  }

  if (state === "connection" || session?.awaiting_continue) {
    const summary = session?.position_summary || {};
    return (
      <section data-testid="home-replay-diagnostic-connection" className="relative overflow-hidden">
        <div className="pointer-events-none absolute -left-20 -top-24 h-60 w-60 rounded-full bg-emerald-300/25 blur-3xl" />
        <p className="cg-eyebrow mb-3">{summary.eyebrow || "Position understood"}</p>
        <h2 className="max-w-[680px] font-heading text-[29px] leading-[1.06] tracking-[-0.035em] text-foreground sm:text-[42px]">
          {summary.title || "Here is the connection your move tested."}
        </h2>
        {summary.move_san && (
          <p className="mt-3 text-[13px] text-muted-foreground">You played {summary.move_san}.</p>
        )}
        <div className="mt-6 grid gap-3 md:grid-cols-2">
          {(summary.demonstrated || []).map((item) => (
            <div key={item.kind} className="rounded-2xl border border-emerald-700/15 bg-emerald-500/[0.06] p-4">
              <div className="flex gap-3">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" />
                <p className="text-[13px] leading-relaxed text-foreground/80">{item.text}</p>
              </div>
            </div>
          ))}
          {(summary.missing || []).map((item) => (
            <div key={item.kind} className="rounded-2xl border border-amber-700/15 bg-amber-500/[0.06] p-4">
              <div className="flex gap-3">
                <CircleDashed className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" />
                <p className="text-[13px] leading-relaxed text-foreground/80">{item.text}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-5 max-w-[760px] rounded-2xl border border-border/70 bg-background/65 p-4">
          <div className="flex gap-3">
            <Target className="mt-0.5 h-4 w-4 shrink-0 text-violet-600" />
            <p className="text-[13px] leading-relaxed text-foreground/75">{summary.principle}</p>
          </div>
        </div>
        <button type="button" onClick={continueToTransfer} disabled={busy} className="cg-primary-action mt-7">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Try a different-looking position
          {!busy && <ArrowRight className="h-4 w-4" />}
        </button>
        {error && <p role="alert" className="mt-4 text-sm text-red-600">{error}</p>}
      </section>
    );
  }

  if (state === "result" || result) {
    const copy = result?.real_game_evidence === "missed"
      ? LATER_MISS_COPY
      : RESULT_COPY[result?.conclusion] || RESULT_COPY.no_conclusion;
    return (
      <section data-testid="home-replay-diagnostic-result" className="relative overflow-hidden">
        <div className="pointer-events-none absolute -left-24 -top-24 h-64 w-64 rounded-full bg-emerald-300/20 blur-3xl" />
        <p className="cg-eyebrow mb-3">{copy.eyebrow}</p>
        <h2 className="max-w-[680px] font-heading text-[28px] leading-[1.08] tracking-[-0.035em] text-foreground sm:text-[40px]">
          {copy.title}
        </h2>
        <p className="mt-4 max-w-[650px] text-[14px] leading-relaxed text-muted-foreground">{copy.body}</p>
        <div className="mt-5 max-w-[650px] rounded-2xl border border-emerald-700/15 bg-emerald-500/[0.06] p-4 text-[13px] leading-relaxed text-foreground/80">
          {copy.follow}
        </div>
        {Object.keys(result?.component_outcomes || {}).length > 0 && (
          <div className="mt-5 grid max-w-[760px] gap-2 sm:grid-cols-2">
            {Object.entries(result.component_outcomes).map(([kind, outcome]) => {
              const demonstrated = outcome.demonstrated === outcome.asked && outcome.asked > 0;
              return (
                <div key={kind} className="flex items-center gap-2 rounded-xl border border-border/70 bg-background/65 px-3 py-2.5 text-[12px] text-foreground/75">
                  {demonstrated
                    ? <CheckCircle2 className="h-4 w-4 text-emerald-700" />
                    : <CircleDashed className="h-4 w-4 text-amber-700" />}
                  {COMPONENT_LABELS[kind] || "Board relationship checked"}
                </div>
              );
            })}
          </div>
        )}
        {result?.separate_soundness_issue && (
          <p className="mt-4 max-w-[650px] text-[13px] leading-relaxed text-amber-700">
            You handled the idea I tested, but one move had a different chess problem. I kept those two findings separate.
          </p>
        )}
        <button type="button" onClick={startNextAction} className="cg-primary-action mt-7">
          {copy.cta}<ArrowRight className="h-4 w-4" />
        </button>
      </section>
    );
  }

  const current = session?.current_item;
  if (!current) return null;
  const awaitingReason = Boolean(session?.awaiting_reason);
  const reasonQuestion = current.reason_question || {
    prompt: current.reason_prompt,
    choices: current.reason_choices || [],
    progress: { current: 1, total: 1 },
  };

  return (
    <section data-testid="home-replay-diagnostic-active" className="relative">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <p className="cg-eyebrow mb-2">Position {(session.current_index || 0) + 1} of {session.total_items || 2}</p>
          <h2 className="font-heading text-[25px] leading-tight tracking-[-0.025em] text-foreground sm:text-[31px]">
            {session.current_index === 0 ? "Forget the old game. What would you play now?" : "Different board. Same test: what would you play?"}
          </h2>
          <p className="mt-2 text-[12px] text-muted-foreground">{current.source_label}</p>
        </div>
        <button type="button" onClick={pause} disabled={busy} className="inline-flex items-center gap-2 text-[12px] text-muted-foreground hover:text-foreground">
          <Pause className="h-3.5 w-3.5" /> Continue later
        </button>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(300px,460px)_1fr] lg:items-start">
        <div className="mx-auto w-full max-w-[460px] rounded-2xl bg-stone-950 p-2 shadow-[0_24px_70px_rgba(28,25,23,0.22)]">
          <LichessBoard
            key={`${current.item_id}-${boardRevision}`}
            ref={boardRef}
            fen={current.fen}
            orientation={current.orientation}
            onMove={stageMove}
            interactive={!busy && !awaitingReason}
            circles={(help?.highlight_squares || []).map((square) => [square, "yellow"])}
            disableArrows={!help?.highlight_squares?.length}
          />
        </div>

        <div className="rounded-2xl border border-border/70 bg-background/70 p-5 sm:p-6">
          {!awaitingReason ? (
            <>
              <p className="text-[15px] font-medium text-foreground">{current.prompt}</p>
              <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">
                Choose your move first. I’m checking what relationships you see—not whether you remember an answer.
              </p>
              <div className="mt-6 flex flex-col gap-2">
                <button type="button" onClick={() => requestHelp("show_on_board")} disabled={busy} className="cg-secondary-action justify-start"><Eye className="h-4 w-4" /> Show me where to look</button>
                <button type="button" onClick={() => requestHelp("ask_one_question")} disabled={busy} className="cg-secondary-action justify-start"><MessageCircleQuestion className="h-4 w-4" /> Ask me one coaching question</button>
                <button type="button" onClick={() => requestHelp("let_me_try")} disabled={busy} className="cg-secondary-action justify-start"><RotateCcw className="h-4 w-4" /> Let me think</button>
              </div>
              {help?.message && <p className="mt-4 rounded-xl bg-lime-100/70 p-3 text-[13px] leading-relaxed text-stone-800">{help.message}</p>}
              {coachMessage && <p className="mt-4 rounded-xl bg-amber-50 p-3 text-[13px] leading-relaxed text-amber-900">{coachMessage}</p>}
            </>
          ) : (
            <>
              <p className="cg-eyebrow mb-2">Move made</p>
              {current.move_san && <p className="mb-3 text-[13px] text-muted-foreground">You played {current.move_san}.</p>}
              <h3 className="text-[20px] font-semibold tracking-[-0.02em] text-foreground">{reasonQuestion.prompt}</h3>
              <p className="mt-2 text-[13px] text-muted-foreground">
                Question {reasonQuestion.progress?.current || 1} of {reasonQuestion.progress?.total || 1}. Choose what you actually saw.
              </p>
              <div className="mt-5 space-y-2">
                {(reasonQuestion.choices || []).map((choice) => (
                  <button key={choice.id} type="button" onClick={() => submitReason(choice.id)} disabled={busy} className="w-full rounded-xl border border-border bg-background px-4 py-3 text-left text-[13px] text-foreground transition hover:border-emerald-500/40 hover:bg-emerald-500/[0.05] disabled:opacity-50">
                    {choice.label}
                  </button>
                ))}
              </div>
            </>
          )}
          {busy && <div className="mt-4 flex items-center gap-2 text-[12px] text-muted-foreground"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Your coach is checking the position…</div>}
          {error && <p role="alert" className="mt-4 text-sm text-red-600">{error}</p>}
        </div>
      </div>
    </section>
  );
}
