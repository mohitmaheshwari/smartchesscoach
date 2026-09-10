/**
 * PROGRESS — evidence that teaching changed play.
 *
 * Learn owns the curriculum. This page owns one different question:
 * did the decision change later, in a real game, without help?
 */

import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Chessboard } from "react-chessboard";
import { motion } from "framer-motion";
import {
  ArrowRight,
  BookOpenCheck,
  Check,
  Circle,
  Clock3,
  Eye,
  Loader2,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";
import Layout from "@/components/Layout";
import { API } from "@/App";
import { ANALYTICS_EVENTS, trackCurriculum } from "@/lib/analytics";
import { loadPersonalCurriculum } from "@/lib/personalCurriculum";
import {
  fadeInUp,
  revealOnScroll,
  staggerContainer,
} from "@/lib/motion";

const FALLBACK_TITLE = "your current lesson";

const evidenceSentence = (item, recent = false) => {
  if (!item) return "";
  const piece = item.piece || "piece";
  const square = item.destination || "that square";
  if (item.outcome === "handled") {
    return `This time, your ${piece} stayed safe on ${square}.`;
  }
  return recent
    ? `The same decision returned: your ${piece} could still be won on ${square}.`
    : `You moved your ${piece} to ${square}, where it could be won.`;
};

const evidenceMeta = (item) => {
  if (!item) return "";
  const parts = [];
  if (item.opponent) parts.push(`against ${item.opponent}`);
  if (item.move_number) parts.push(`move ${item.move_number}`);
  return parts.join(" · ");
};

export const buildProgressView = ({ journey, curriculum }) => {
  const primary = curriculum?.enabled ? curriculum?.decision?.primary : null;
  const focusTitle = primary?.title || FALLBACK_TITLE;
  const lessonHref = primary?.destination?.href || "/learn";
  const enabled = journey?.enabled === true;
  const paused = journey?.paused === true;
  const transfer = enabled ? journey?.transfer || {} : {};
  const practice = enabled ? journey?.practice || {} : {};
  const steps = enabled ? journey?.steps || {} : {};
  const recent = journey?.evidence_examples?.recent || null;

  if (paused) {
    return {
      tone: "waiting",
      eyebrow: "Your progress is saved",
      headline: "Nothing you learned has disappeared.",
      body:
        journey?.message ||
        "Your coach is preparing the next step. Your lessons and game evidence are still here.",
      focusTitle,
      watch:
        "I will not make a new progress claim while this coaching cycle is paused.",
      action: { label: "Review my games", href: "/games" },
      steps: {},
    };
  }

  if (!enabled) {
    return {
      tone: "waiting",
      eyebrow: "I’m gathering proof",
      headline: "I’m not ready to claim a change yet.",
      body:
        "I need to see you work through the lesson, then face the same kind of choice in one of your later games. Until both happen, I would only be guessing.",
      focusTitle,
      watch:
        "Practice can show that an idea makes sense. Only a later unassisted game can show that it is becoming part of your chess.",
      action: { label: primary ? "Continue my lesson" : "Open Learn", href: lessonHref },
      steps: {},
    };
  }

  if (transfer.verdict === "improved") {
    return {
      tone: "improved",
      eyebrow: "A real change",
      headline: "This lesson is beginning to hold in your games.",
      body: transfer.message,
      focusTitle,
      watch:
        "I have seen this work later without help. I’ll keep watching for the same kind of choice before calling it automatic.",
      action: { label: "Choose what I learn next", href: "/learn" },
      steps,
    };
  }

  if (transfer.verdict === "still_recurring") {
    return {
      tone: "recurring",
      eyebrow: "The coach is still watching",
      headline: "The old mistake showed up again.",
      body: transfer.message,
      focusTitle,
      watch:
        "The idea may make sense during practice, but it returned when you had to find it alone. That is why it stays in your plan.",
      action: recent?.game_id
        ? {
            label: "Review what returned",
            href: `/game/${encodeURIComponent(recent.game_id)}`,
          }
        : { label: "Continue this lesson", href: lessonHref },
      steps,
    };
  }

  if (!practice.completed) {
    return {
      tone: "waiting",
      eyebrow: "Building the evidence",
      headline: "First, show me you understand the idea.",
      body:
        "I know what we are working on, but the lesson is not complete yet. Finishing it will not prove improvement—it only gives me something precise to watch for later.",
      focusTitle,
      watch:
        "After the lesson, I’ll wait for the same kind of decision to appear naturally in one of your games.",
      action: { label: "Continue this lesson", href: lessonHref },
      steps,
    };
  }

  return {
    tone: "waiting",
    eyebrow: "Practice is recorded",
    headline: "You understand this in practice. I can’t call it improvement yet.",
    body:
      transfer.message ||
      "I need to see the same decision in a later unassisted game before I can judge improvement.",
    focusTitle,
    watch:
      "I need the same kind of choice to appear in a later game without help. Nothing you do with help can replace that evidence.",
    action: { label: "Import my latest games", href: "/import" },
    steps,
  };
};

function EvidenceBoard({ item, label, recent, onReview }) {
  if (!item) return null;
  const orientation = item.fen?.split(" ")[1] === "b" ? "black" : "white";
  return (
    <article className="overflow-hidden rounded-2xl border border-border/65 bg-background/75">
      <div className="flex items-center justify-between gap-3 border-b border-border/60 px-4 py-3">
        <p className="cg-eyebrow !text-[10px]">{label}</p>
        <p className="text-[11px] text-muted-foreground">{evidenceMeta(item)}</p>
      </div>
      <div className="grid gap-4 p-4 sm:grid-cols-[minmax(150px,220px)_1fr] sm:items-center">
        <div className="aspect-square w-full overflow-hidden rounded-xl shadow-sm">
          <Chessboard
            position={item.fen}
            boardOrientation={orientation}
            arePiecesDraggable={false}
          />
        </div>
        <div>
          <p className="text-[15px] font-medium leading-relaxed text-foreground">
            {evidenceSentence(item, recent)}
          </p>
          <p className="mt-2 text-[12px] leading-relaxed text-muted-foreground">
            You played {item.move_san}. The board is the proof. A rating change or
            puzzle score cannot tell me that you handled this decision.
          </p>
          {item.game_id && (
            <button
              type="button"
              onClick={() => onReview(item.game_id)}
              className="cg-secondary-action mt-4"
            >
              Review the game
              <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          )}
        </div>
      </div>
    </article>
  );
}

function ProofPath({ view, journey }) {
  const transfer = journey?.enabled ? journey.transfer || {} : {};
  const stages = [
    {
      label: "Coach noticed it",
      complete: Boolean(view.steps?.baseline_frozen || view.steps?.home_focus_served),
      Icon: Eye,
    },
    {
      label: "Practice recorded",
      complete: Boolean(
        (journey?.practice?.lesson_evidence_events || 0) > 0 ||
        (journey?.coach_games?.assisted_practice || 0) > 0
      ),
      Icon: BookOpenCheck,
    },
    {
      label: "Seen in a later game",
      complete: Boolean(view.steps?.later_unassisted_opportunity),
      Icon: Clock3,
    },
    {
      label: "Holding in games",
      complete: transfer.verdict === "improved",
      failed: transfer.verdict === "still_recurring",
      Icon: ShieldCheck,
    },
  ];

  return (
    <section aria-labelledby="progress-path-heading">
      <p className="cg-eyebrow mb-4">How this becomes yours</p>
      <div
        id="progress-path-heading"
        className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4"
      >
        {stages.map(({ label, complete, failed, Icon }) => (
          <div
            key={label}
            className={`rounded-2xl border p-4 transition-colors ${
              complete
                ? "border-emerald-500/25 bg-emerald-500/[0.06]"
                : failed
                  ? "border-amber-500/30 bg-amber-500/[0.07]"
                  : "border-border/60 bg-card/45"
            }`}
          >
            <div className="mb-3 flex items-center justify-between">
              <Icon
                className={`h-4 w-4 ${
                  complete
                    ? "text-emerald-600 dark:text-emerald-400"
                    : failed
                      ? "text-amber-600 dark:text-amber-400"
                      : "text-muted-foreground"
                }`}
                aria-hidden="true"
              />
              {complete ? (
                <Check className="h-3.5 w-3.5 text-emerald-600" aria-hidden="true" />
              ) : (
                <Circle className="h-3 w-3 text-muted-foreground/50" aria-hidden="true" />
              )}
            </div>
            <p className="text-[13px] font-medium text-foreground">{label}</p>
          </div>
        ))}
      </div>
      <p className="mt-3 text-[11.5px] text-muted-foreground">
        Practice is recorded, but it never changes the real-game verdict by itself.
      </p>
    </section>
  );
}

function CoachGameEvidence({ evidence }) {
  if (!evidence?.opportunities) return null;

  const checkpoint = evidence.checkpoint || {};
  const practice = evidence.practice || {};
  let message =
    "I noticed the same kind of decision while you played against the coach. I saved it as practice, not proof from one of your real games.";
  if (checkpoint.handled > 0 && checkpoint.missed > 0) {
    message =
      "Across your test games, you handled this decision sometimes and missed it sometimes. It isn’t steady yet, so we keep practising it.";
  } else if (checkpoint.missed > 0) {
    message =
      "In your test game, the same decision still caught you. That is useful: we keep the lesson, practise it differently, and test it again.";
  } else if (checkpoint.handled > 0) {
    message =
      "In your test game, you handled this decision without help. That is a strong rehearsal; now I’m waiting to see it hold in one of your real games.";
  } else if (practice.opportunities > 0) {
    message =
      "During coached play, you faced this decision again. I saved what happened as assisted practice, so it helps me teach you without pretending the habit is fixed.";
  }

  return (
    <div
      className="mb-8 rounded-2xl border border-violet-500/20 bg-violet-500/[0.06] p-5 md:p-6"
      data-testid="progress-coach-game-evidence"
    >
      <p className="cg-eyebrow !text-[10px]">What I saw in Play with Coach</p>
      <p className="mt-3 max-w-[760px] text-[13.5px] leading-relaxed text-foreground/90">
        {message}
      </p>
    </div>
  );
}

export default function UnifiedProgress({ user }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [journey, setJourney] = useState(null);
  const [curriculum, setCurriculum] = useState(null);

  useEffect(() => {
    trackCurriculum(ANALYTICS_EVENTS.PROGRESS_VIEWED, {
      surface: "progress",
      decision_source: "complete_coaching_journey",
    });
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([
      loadPersonalCurriculum(API, user?.user_id, "progress"),
      fetch(`${API}/progress/complete-coaching`, {
        credentials: "include",
      }).then((response) => (response.ok ? response.json() : null)),
    ])
      .then(([curriculumResult, journeyResult]) => {
        if (cancelled) return;
        if (curriculumResult.status === "fulfilled") {
          setCurriculum(curriculumResult.value);
        }
        if (journeyResult.status === "fulfilled") {
          setJourney(journeyResult.value);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user?.user_id]);

  const view = useMemo(
    () => buildProgressView({ journey, curriculum }),
    [journey, curriculum]
  );

  if (loading) {
    return (
      <Layout user={user}>
        <div className="grid h-[60vh] place-items-center" aria-label="Loading progress">
          <Loader2 className="h-6 w-6 animate-spin text-emerald-600" />
        </div>
      </Layout>
    );
  }

  const before = journey?.evidence_examples?.before || null;
  const recent = journey?.evidence_examples?.recent || null;
  const hasEvidenceBoard = Boolean(before || recent);

  const reviewGame = (gameId) => {
    navigate(`/game/${encodeURIComponent(gameId)}`);
  };

  return (
    <Layout user={user}>
      <motion.main
        variants={staggerContainer}
        initial="initial"
        animate="animate"
        className="experience-page experience-progress-page cg-page max-w-[1040px]"
        data-testid="progress-page"
      >
        <motion.header variants={fadeInUp} className="cg-hero mb-8 md:mb-10">
          <p className="cg-eyebrow">Progress · what is changing in your chess</p>
          <h1 className="cg-title !max-w-[780px] !text-[clamp(2.2rem,5vw,4.2rem)]">
            {view.headline}
          </h1>
          <p
            className="cg-lede !max-w-[720px]"
            data-testid={journey?.enabled ? "phase8-transfer-verdict" : undefined}
          >
            {view.body}
          </p>
        </motion.header>

        <motion.section
          variants={fadeInUp}
          className={`mb-8 overflow-hidden rounded-[28px] border p-6 shadow-[0_24px_70px_-42px_rgba(15,23,42,0.35)] md:p-8 ${
            view.tone === "improved"
              ? "border-emerald-500/25 bg-gradient-to-br from-emerald-500/[0.11] via-card to-lime-300/[0.08]"
              : view.tone === "recurring"
                ? "border-amber-500/30 bg-gradient-to-br from-amber-500/[0.10] via-card to-rose-400/[0.05]"
                : "border-sky-500/20 bg-gradient-to-br from-sky-500/[0.08] via-card to-violet-400/[0.06]"
          }`}
        >
          <div className="grid gap-6 md:grid-cols-[1fr_auto] md:items-start">
            <div>
              <p className="cg-eyebrow !text-[10px]">{view.eyebrow}</p>
              <h2 className="mt-2 font-heading text-[25px] tracking-[-0.025em] text-foreground md:text-[30px]">
                {view.focusTitle}
              </h2>
              <p className="mt-3 max-w-[650px] text-[13.5px] leading-relaxed text-muted-foreground">
                Learn tells you what to study. This page waits for your games to
                show whether the lesson changed a real decision.
              </p>
            </div>
            <button
              type="button"
              onClick={() => navigate(view.action.href)}
              className="cg-primary-action md:shrink-0"
              data-testid="progress-next-action"
            >
              {view.action.label}
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </motion.section>

        <motion.section variants={fadeInUp} className="mb-10 md:mb-14">
          <div className="mb-4 flex items-end justify-between gap-4">
            <div>
              <p className="cg-eyebrow">The evidence</p>
              <h2 className="mt-2 font-heading text-[27px] tracking-[-0.03em] md:text-[34px]">
                Your games, not a report.
              </h2>
            </div>
          </div>
          {hasEvidenceBoard ? (
            <div className="grid gap-4 lg:grid-cols-2" data-testid="progress-evidence">
              <EvidenceBoard
                item={before}
                label="Earlier"
                recent={false}
                onReview={reviewGame}
              />
              <EvidenceBoard
                item={recent}
                label="Recently"
                recent
                onReview={reviewGame}
              />
            </div>
          ) : (
            <div
              className="cg-panel flex items-start gap-3 p-5 md:p-6"
              data-testid="progress-evidence-empty"
            >
              <Eye className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <div>
                <p className="text-[14px] font-medium text-foreground">
                  No game-level proof is ready yet.
                </p>
                <p className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground">
                  I won’t fill this space with a vaguely similar position. When an
                  exact earlier and later decision is verified, both boards will
                  appear here.
                </p>
              </div>
            </div>
          )}
        </motion.section>

        <motion.div variants={fadeInUp} className="mb-10 md:mb-14">
          <CoachGameEvidence evidence={journey?.coach_games} />
          <ProofPath view={view} journey={journey} />
        </motion.div>

        <motion.section
          {...revealOnScroll}
          className="grid gap-4 md:grid-cols-[1.25fr_0.75fr]"
        >
          <div className="cg-coach-card">
            <div className="flex items-start gap-3">
              <RotateCcw className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" aria-hidden="true" />
              <div>
                <p className="cg-eyebrow !text-[10px]">What I am still watching</p>
                <p className="mt-3 text-[14px] leading-relaxed text-foreground/90">
                  {view.watch}
                </p>
              </div>
            </div>
          </div>
          <div className="cg-panel p-5 md:p-6">
            <p className="cg-eyebrow !text-[10px]">What happens next</p>
            <p className="mt-3 text-[13px] leading-relaxed text-muted-foreground">
              I’ll update this page only when the evidence changes—not because
              another day passed or another puzzle was opened.
            </p>
            <button
              type="button"
              onClick={() => navigate(view.action.href)}
              className="cg-secondary-action mt-5"
            >
              {view.action.label}
              <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          </div>
        </motion.section>
      </motion.main>
    </Layout>
  );
}
