import { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Eye,
  Loader2,
  RotateCcw,
  Sparkles,
} from "lucide-react";

import { API } from "../../App";
import { ANALYTICS_EVENTS, track } from "../../lib/analytics";
import CandidateComparisonCard from "./CandidateComparisonCard";


const ROLE_LABELS = Object.freeze({
  turning_point: "The moment that changed the game",
  demonstrated_knowledge: "What you understood",
  opponent_plan: "What your opponent was trying",
  missed_opportunity: "An opportunity you didn't notice",
  knowledge_gap: "A new idea for you",
  recurring_connection: "A pattern I recognize",
  reflection: "Before I explain",
});


const eventMap = (events) => new Map(
  (events || []).map((event) => [event.event_id, event])
);


export const boardArrowsForReviewVisual = (visual = {}) => {
  if (visual.relationship_arrows?.length) {
    return visual.relationship_arrows.map((arrow) => [
      arrow.from,
      arrow.to,
      arrow.role === "safe_move"
        ? "green"
        : arrow.role === "opportunity"
          ? "blue"
          : "amber",
    ]);
  }
  return (visual.arrows || []).map(([from, to]) => [from, to, "amber"]);
};


export default function PersonalizedReviewCoach({
  gameId,
  plan,
  events,
  prompts,
  reflectionResponses,
  onChapterSelect,
  onShowVisual,
  onNavigate,
  onReplay,
  moves,
  onCompareCandidate,
  comparisonPlayingPly,
}) {
  const eventsById = useMemo(() => eventMap(events), [events]);
  const promptsByEvent = useMemo(
    () => new Map((prompts || []).map((prompt) => [prompt.event_id, prompt])),
    [prompts]
  );
  const [activeIndex, setActiveIndex] = useState(-1);
  const [answers, setAnswers] = useState(() => Object.fromEntries(
    (reflectionResponses || []).map((item) => [item.event_id, item])
  ));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const openedAtRef = useRef(Date.now());
  const chapters = plan?.chapters || [];

  useEffect(() => {
    setAnswers(Object.fromEntries(
      (reflectionResponses || []).map((item) => [item.event_id, item])
    ));
  }, [reflectionResponses]);

  if (!plan || !chapters.length) return null;

  const showChapter = (index) => {
    const chapter = chapters[index];
    const event = chapter ? eventsById.get(chapter.event_id) : null;
    if (!chapter || !event) return;
    openedAtRef.current = Date.now();
    setError("");
    setActiveIndex(index);
    onChapterSelect?.(event, index);
  };

  const submitReflection = async (event, prompt, optionId) => {
    if (submitting || answers[event.event_id]) return;
    setSubmitting(true);
    setError("");
    try {
      const response = await fetch(`${API}/reflect/v2/game-review-event`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          game_id: gameId,
          event_id: event.event_id,
          prompt_id: prompt.prompt_id,
          shown_option_ids: prompt.options.map((option) => option.id),
          selected_option_id: optionId,
          elapsed_ms: Math.max(0, Date.now() - openedAtRef.current),
          answered_before_reveal: true,
        }),
      });
      if (!response.ok) throw new Error("reflection was not saved");
      const receipt = await response.json();
      setAnswers((current) => ({
        ...current,
        [event.event_id]: {
          event_id: event.event_id,
          prompt_id: prompt.prompt_id,
          selected_option_id: receipt.selected_option_id || optionId,
          answered_before_reveal: true,
        },
      }));
      track(ANALYTICS_EVENTS.REVIEW_COACH_REFLECTION_SUBMITTED, {
        chapter_role: chapters[activeIndex]?.role,
        chapter_index: activeIndex,
      });
    } catch (_error) {
      setError("I couldn't save that answer. Please try once more.");
    } finally {
      setSubmitting(false);
    }
  };

  if (activeIndex === -1) {
    return (
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden rounded-[24px] border border-[#2a221b] bg-gradient-to-br from-[#181410] via-[#13100d] to-[#1c1713] p-6 md:p-8 shadow-2xl"
        data-testid="personalized-review-intro"
      >
        <div className="absolute -right-16 -top-20 h-52 w-52 rounded-full bg-[#d0ae6d]/10 blur-3xl" />
        <div className="absolute -bottom-20 -left-12 h-48 w-48 rounded-full bg-[#84b872]/10 blur-3xl" />
        <div className="relative">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[#d0ae6d]/30 bg-[#d0ae6d]/10 px-3.5 py-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#d0ae6d]">
            <Sparkles className="h-3.5 w-3.5" />
            Your coach's game plan
          </div>
          <h2 className="max-w-xl font-serif text-3xl leading-tight tracking-[-0.025em] text-[#f4efe6] md:text-[42px]">
            {plan.opening}
          </h2>
          <p className="mt-5 max-w-xl text-[16px] leading-relaxed text-stone-300">
            {plan.game_arc}
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <button
              type="button"
              onClick={() => {
                track(ANALYTICS_EVENTS.REVIEW_COACH_STARTED, {
                  chapter_count: chapters.length,
                });
                showChapter(0);
              }}
              className="group inline-flex min-h-12 items-center gap-3 rounded-full bg-gradient-to-r from-[#84b872] to-[#6da35b] px-6 py-3 text-sm font-bold text-[#0c0a08] shadow-lg transition hover:-translate-y-0.5 hover:brightness-110 focus:outline-none"
              data-testid="personalized-review-start"
            >
              Review this game with me
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </button>
            <span className="text-sm text-stone-400">
              {chapters.length === 1 ? "One useful moment" : `${chapters.length} useful moments`}
            </span>
          </div>
        </div>
      </motion.section>
    );
  }

  if (activeIndex >= chapters.length) {
    return (
      <motion.section
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-[24px] border border-[#2a221b] bg-gradient-to-br from-[#181410] to-[#13100d] p-6 md:p-8 shadow-2xl"
        data-testid="personalized-review-takeaway"
      >
        <div className="mb-5 flex h-11 w-11 items-center justify-center rounded-2xl bg-[#84b872] text-[#0c0a08] shadow-lg shadow-[#84b872]/20">
          <Check className="h-5 w-5 stroke-[2.5]" />
        </div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#84b872]">
          What I want you to take forward
        </p>
        <h2 className="mt-3 font-serif text-3xl leading-tight tracking-[-0.02em] text-[#f4efe6]">
          {plan.takeaway}
        </h2>
        <div className="mt-8 flex flex-wrap gap-3">
          {plan.next_action && (
            <button
              type="button"
              onClick={() => {
                track(ANALYTICS_EVENTS.REVIEW_COACH_NEXT_ACTION_STARTED, {
                  action_kind: plan.next_action.action_kind,
                  content_kind: plan.next_action.content_kind,
                });
                onNavigate?.(plan.next_action.href);
              }}
              className="inline-flex min-h-11 items-center gap-2 rounded-full bg-[#84b872] px-5 py-3 text-sm font-bold text-[#0c0a08] transition hover:-translate-y-0.5 hover:brightness-110 focus:outline-none"
              data-testid="personalized-review-next-action"
            >
              Practise this idea
              <ArrowRight className="h-4 w-4" />
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              setActiveIndex(-1);
              onReplay?.();
            }}
            className="inline-flex min-h-11 items-center gap-2 rounded-full border border-[#2a221b] bg-[#1a1511] px-5 py-3 text-sm font-semibold text-stone-300 transition hover:border-[#d0ae6d]/40 hover:text-white"
            data-testid="personalized-review-replay"
          >
            <RotateCcw className="h-4 w-4" />
            Replay the game
          </button>
        </div>
      </motion.section>
    );
  }

  const chapter = chapters[activeIndex];
  const event = eventsById.get(chapter.event_id);
  if (!event) return null;
  const prompt = promptsByEvent.get(event.event_id);
  const answer = answers[event.event_id];
  const selectedLabel = prompt?.options?.find(
    (option) => option.id === answer?.selected_option_id
  )?.label;
  const canReveal = !prompt || Boolean(answer);
  const visual = event.teaching?.visual || {};
  const moveRecord = (moves || [])[Number(event.move?.ply) - 1] || {};
  const candidateComparison = moveRecord.candidate_comparison || null;
  const hasVisual = Boolean(
    visual.relationship_arrows?.length
    || visual.arrows?.length
    || visual.highlights?.length
  );

  return (
    <section
      className="rounded-[24px] border border-[#2a221b] bg-[#13100d] p-5 md:p-7 shadow-2xl"
      data-testid="personalized-review-chapter"
    >
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#d0ae6d]">
            {ROLE_LABELS[chapter.role] || "A moment worth understanding"}
          </p>
          <p className="mt-1 text-sm text-stone-400">
            Move {event.move.number} · {event.move.san}
          </p>
        </div>
        <span className="rounded-full bg-[#1c1713] border border-[#2a221b] px-3 py-1 text-xs font-mono font-medium text-stone-300">
          {activeIndex + 1} of {chapters.length}
        </span>
      </div>

      <AnimatePresence mode="wait">
        {!canReveal ? (
          <motion.div
            key="reflection"
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
          >
            {event.teaching?.headline && (
              <div className="mb-6 rounded-2xl border border-[#d0ae6d]/30 bg-[#d0ae6d]/10 px-5 py-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#d0ae6d]">
                  Your position
                </p>
                <h2 className="mt-2 font-serif text-2xl leading-snug text-[#f4efe6]">
                  {event.teaching.headline}
                </h2>
                {event.teaching.practical_lead && (
                  <p className="mt-2 text-sm leading-relaxed text-stone-300">
                    {event.teaching.practical_lead}
                  </p>
                )}
              </div>
            )}
            <h2 className="font-serif text-2xl leading-snug text-[#f4efe6] md:text-[30px]">
              {prompt.question}
            </h2>
            <div className="mt-6 grid gap-2.5" role="group" aria-label={prompt.question}>
              {prompt.options.map((option) => (
                <button
                  type="button"
                  key={option.id}
                  disabled={submitting}
                  onClick={() => submitReflection(event, prompt, option.id)}
                  className="group flex min-h-12 w-full items-center justify-between rounded-2xl border border-[#2a221b] bg-[#181410] px-4 py-3 text-left text-sm font-medium text-stone-200 transition hover:border-[#d0ae6d]/60 hover:bg-[#201914] focus:outline-none disabled:cursor-wait disabled:opacity-60"
                  data-testid={`personalized-reflection-option-${option.id}`}
                >
                  <span>{option.label}</span>
                  {submitting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <ArrowRight className="h-4 w-4 text-[#d0ae6d] opacity-50 transition group-hover:translate-x-0.5 group-hover:opacity-100" />
                  )}
                </button>
              ))}
            </div>
            {error && (
              <p className="mt-3 text-sm text-rose-400" role="alert">
                {error}
              </p>
            )}
          </motion.div>
        ) : (
          <motion.div
            key="reveal"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
          >
            {event.teaching?.headline && (
              <div className="mb-5">
                <h2 className="font-serif text-3xl leading-tight text-[#f4efe6]">
                  {event.teaching.headline}
                </h2>
                {event.teaching.practical_lead && (
                  <p className="mt-2 text-sm leading-relaxed text-stone-300">
                    {event.teaching.practical_lead}
                  </p>
                )}
              </div>
            )}
            {selectedLabel && (
              <div className="mb-5 rounded-2xl border border-violet-500/30 bg-violet-500/10 px-4 py-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-violet-300">
                  What you told me
                </p>
                <p className="mt-1 text-sm text-violet-100">{selectedLabel}</p>
              </div>
            )}
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#84b872]">
              What actually happened
            </p>
            <p className="mt-3 text-[16px] leading-relaxed text-stone-200">
              {event.teaching.caption}
            </p>
            {event.teaching.principle && event.teaching.principle !== event.teaching.caption && (
              <div className="mt-5 rounded-2xl border border-[#84b872]/30 bg-[#84b872]/10 px-4 py-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#84b872]">
                  Keep this with you
                </p>
                <p className="mt-1.5 text-sm leading-relaxed text-emerald-100">
                  {event.teaching.principle}
                </p>
              </div>
            )}
            <CandidateComparisonCard
              comparison={candidateComparison}
              playing={comparisonPlayingPly === Number(event.move?.ply)}
              onCompare={(comparison) => {
                onCompareCandidate?.(
                  comparison,
                  moveRecord.fen_before,
                  Number(event.move?.ply) - 1,
                );
              }}
            />
            {hasVisual && (
              <button
                type="button"
                onClick={() => {
                  track(ANALYTICS_EVENTS.REVIEW_COACH_VISUAL_SHOWN, {
                    chapter_role: chapter.role,
                    chapter_index: activeIndex,
                  });
                  onShowVisual?.(visual);
                }}
                className="mt-5 inline-flex min-h-10 items-center gap-2 rounded-full border border-[#2a221b] bg-[#181410] px-4 py-2 text-sm font-semibold text-stone-300 transition hover:border-[#d0ae6d]/60 hover:text-white"
                data-testid="personalized-review-show-visual"
              >
                <Eye className="h-4 w-4 text-[#d0ae6d]" />
                Show the relationship
              </button>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {canReveal && (
        <div className="mt-8 flex items-center justify-between border-t border-[#2a221b] pt-5">
          <button
            type="button"
            disabled={activeIndex === 0}
            onClick={() => showChapter(activeIndex - 1)}
            className="inline-flex min-h-10 items-center gap-2 rounded-full px-3 py-2 text-sm font-medium text-stone-400 transition hover:text-white disabled:invisible"
          >
            <ArrowLeft className="h-4 w-4" />
            Previous
          </button>
          <button
            type="button"
            onClick={() => {
              if (activeIndex + 1 < chapters.length) {
                showChapter(activeIndex + 1);
              } else {
                track(ANALYTICS_EVENTS.REVIEW_COACH_COMPLETED, {
                  chapter_count: chapters.length,
                });
                setActiveIndex(chapters.length);
              }
            }}
            className="group inline-flex min-h-11 items-center gap-2 rounded-full bg-[#84b872] px-5 py-2.5 text-sm font-bold text-[#0c0a08] transition hover:brightness-110"
            data-testid="personalized-review-continue"
          >
            {activeIndex + 1 < chapters.length ? "Next moment" : "What to take forward"}
            <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
          </button>
        </div>
      )}
    </section>
  );
}
