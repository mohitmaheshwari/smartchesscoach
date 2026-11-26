/**
 * CoachPlanCard: the coach's read of the player and up to three steps toward
 * the next level, in the order they cost him games (services/player_coach_plan.py).
 *
 * Top of Home for coach-pages players. Reads the player file (useCoachFile),
 * so it computes nothing. No figures: the order is said in words, and how much
 * each step cost stays on the server in `measured`.
 */
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Check, CheckCircle2, Circle, Clock, Minus, Play, Target, TrendingDown, TrendingUp } from "lucide-react";

import { API } from "@/App";
import { ANALYTICS_EVENTS, track } from "@/lib/analytics";
import { playFrom, useCoachFile } from "@/lib/coachFile";
import { BETTER, Board, PLAYED } from "@/components/coachfile/CoachFileBlocks";

/** "Who is near my king?" + "." would print "?." */
const sentence = (t) => (/[.?!]$/.test(t) ? t : `${t}.`);

const ORDER_WORDS = ["First", "Then", "After that"];
// Rating points are the one figure the plan states: the claim Mohit asked for
// ("reach +200"), computed from the player's own games on the server.
const fmt = (n) => `${n > 0 ? "+" : ""}${n}`;
const GOAL = 200;
const STATE_ICON = { better: TrendingDown, kept: Check, worse: TrendingUp, same: Minus, waiting: Clock };

/** Records a piece of this week's work: the plan's adherence record.
 *  Resolves true only when the server stored it, so a rejected write never
 *  shows as done (docs/coaching_intelligence_scope.md, 1a). */
async function logWork(stepKey, action, ref) {
  track(ANALYTICS_EVENTS.PLAN_WORK_OPENED, { action_kind: action, surface: "coach_plan" });
  try {
    const res = await fetch(`${API}/coach-file/activity`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ step_key: stepKey, action, ref }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

function Tick({ done }) {
  return done
    ? <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" aria-label="done" />
    : <Circle className="h-4 w-4 shrink-0 text-muted-foreground/60" aria-label="not yet" />;
}

const ORDINAL = ["first", "second", "third"];

function WeekWork({ step, done: initial }) {
  const navigate = useNavigate();
  const [done, setDone] = useState(() => initial || { learn: false, find: [], play: [] });
  const work = step.work;
  if (!work) return null;
  const mark = (action, ref) => {
    const before = done;
    setDone((d) => (action === "learn" ? { ...d, learn: true } : { ...d, [action]: [...new Set([...(d[action] || []), ref])] }));
    logWork(step.key, action, ref).then((ok) => {
      if (!ok) setDone(before);
    });
  };
  return (
    <div className="mt-4 rounded-card border border-border/70 bg-background/60 p-4" data-testid="coach-plan-work">
      <p className="cg-eyebrow">This week's work</p>
      <ol className="mt-3 space-y-3">
        <li className="flex items-start gap-3">
          <Tick done={done.learn} />
          <div className="min-w-0">
            <p className="text-note font-semibold text-foreground">Learn it</p>
            <p className="text-note text-muted-foreground">{work.learn.text}</p>
            <Link to={work.learn.url} onClick={() => mark("learn", "learn")} className="mt-1 inline-flex text-note font-medium text-primary hover:underline">
              Open the lesson
            </Link>
          </div>
        </li>
        {work.find?.length > 0 && (
          <li className="flex items-start gap-3">
            <Tick done={(done.find || []).length >= work.find.length} />
            <div className="min-w-0">
              <p className="text-note font-semibold text-foreground">Find it in your own games</p>
              <p className="text-note text-muted-foreground">Open each moment and find the better move before you look.</p>
              <div className="mt-1 flex flex-wrap gap-3">
                {work.find.map((f, i) => (
                  <Link key={f.ref} to={f.url} onClick={() => mark("find", f.ref)}
                    className={`text-note font-medium hover:underline ${(done.find || []).includes(f.ref) ? "text-emerald-700 dark:text-emerald-400" : "text-primary"}`}>
                    The {ORDINAL[i] || "next"} game
                  </Link>
                ))}
              </div>
            </div>
          </li>
        )}
        {work.play?.length > 0 && (
          <li className="flex items-start gap-3">
            <Tick done={(done.play || []).length >= work.play.length} />
            <div className="min-w-0">
              <p className="text-note font-semibold text-foreground">Play it</p>
              <p className="text-note text-muted-foreground">Play each position against your coach until the better move is automatic.</p>
              <div className="mt-1 flex flex-wrap gap-2">
                {work.play.map((pos, i) => (
                  <button key={pos.ref} type="button"
                    onClick={() => { mark("play", pos.ref); playFrom(pos, navigate); }}
                    className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-note font-medium ${(done.play || []).includes(pos.ref) ? "border-emerald-500/40 text-emerald-700 dark:text-emerald-400" : "border-border text-foreground hover:bg-muted/50"}`}>
                    <Play className="h-3 w-3" /> The {ORDINAL[i] || "next"} position
                  </button>
                ))}
              </div>
            </div>
          </li>
        )}
        <li className="flex items-start gap-3">
          <Target className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          <p className="text-note text-foreground/90">{work.target}</p>
        </li>
      </ol>
    </div>
  );
}

function Step({ step, index, check, notation, done }) {
  // The step being trained shows "Since you started" instead: the two read
  // different windows, and side by side they said "Same as before" and
  // "Waiting for games" about the same step.
  const showCheck = step.training && check?.title;
  const Icon = showCheck ? null : STATE_ICON[step.state] || null;
  const whereUrl = step.work?.find?.[0]?.url || step.review_url;
  return (
    <li
      className={`rounded-card border p-5 ${step.this_week ? "border-primary/40 bg-primary/[0.05]" : "border-border/70"}`}
      data-testid="coach-plan-step"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="cg-eyebrow">{ORDER_WORDS[index] || "Then"}</span>
        {step.this_week && (
          <span className="rounded-full bg-primary/15 px-2 py-0.5 text-meta font-medium text-primary">This week</span>
        )}
        {step.stake?.high > 0 && (
          <span className="rounded-full bg-muted px-2 py-0.5 text-meta font-medium text-foreground/80" data-testid="coach-plan-step-stake">
            Worth up to {fmt(step.stake.high)}
          </span>
        )}
        {/* "Same as before" and "Waiting for games" say nothing about chess
            and read as system notes. Only a CHANGE is worth a player's
            attention, so the unchanged and not-enough-data states stay
            silent and the icon goes with them. */}
        {step.state_title && Icon && step.state !== "same" && step.state !== "waiting" && (
          <span className="inline-flex items-center gap-1 text-meta text-muted-foreground">
            <Icon className="h-3.5 w-3.5" aria-hidden="true" /> {step.state_title}
          </span>
        )}
      </div>
      <p className="mt-2 font-heading text-lead text-foreground">{step.title}</p>
      <p className="mt-1 text-body text-foreground/90">{step.do}</p>
      {step.sign?.text && (
        <p className="mt-2 text-note text-muted-foreground">
          <span className="font-semibold text-foreground/80">{sentence(step.sign.title)}</span> {step.sign.text}
        </p>
      )}
      {step.kind === "opening" && step.fen && step.played_from && step.better_from && (
        <div className="mt-3" data-testid="coach-plan-opening-board">
          <Board
            fen={step.fen}
            orientation={step.side}
            size={200}
            arrows={[
              [step.played_from, step.played_to, PLAYED],
              [step.better_from, step.better_to, BETTER],
            ]}
            marks={{
              [step.played_to]: { background: "rgba(180,83,9,0.25)" },
              [step.better_to]: { background: "rgba(4,120,87,0.22)" },
            }}
          />
        </div>
      )}
      {step.kind === "opening" && notation && step.san && (
        <p className="mt-2 text-note text-muted-foreground">
          You play <span className="font-mono text-amber-700 dark:text-amber-400">{step.san}</span>
          {step.better_san ? (
            <>
              {" "}there. Better is <span className="font-mono text-emerald-700 dark:text-emerald-400">{step.better_san}</span>.
            </>
          ) : "."}
        </p>
      )}
      {showCheck && (
        <p className="mt-3 text-note text-foreground/85" data-testid="coach-plan-check">
          <span className="font-semibold">Since you started:</span> {sentence(check.title)} {check.words}
        </p>
      )}
      {step.this_week && <WeekWork step={step} done={done} />}
      {!step.this_week && (step.practice_url || whereUrl) && (
        <div className="mt-4 flex flex-wrap gap-2">
          {step.practice_url && (
            <Link to={step.practice_url} className="cg-primary-action !min-h-9 !px-4 !py-2 text-note">
              <Target className="h-3.5 w-3.5" /> Practise it
            </Link>
          )}
          {whereUrl && (
            <Link to={whereUrl} className="inline-flex items-center rounded-full border border-border px-4 py-2 text-note font-medium text-foreground hover:bg-muted/50">
              See where it happened
            </Link>
          )}
        </div>
      )}
    </li>
  );
}

export default function CoachPlanCard({ flush = false }) {
  const file = useCoachFile();
  const viewed = useRef(false);
  const stepCount = file?.plan?.steps?.length || 0;
  useEffect(() => {
    if (viewed.current || !file?.enabled || file.state !== "ready") return;
    viewed.current = true;
    track(ANALYTICS_EVENTS.COACH_PLAN_VIEWED, { surface: "home", total_items: stepCount, state: stepCount ? "plan" : "no_plan" });
  }, [file?.enabled, file?.state, stepCount]);
  if (!file?.enabled) return null;
  if (file.state === "building") {
    return (
      <section className="mb-10 rounded-panel border border-border/70 bg-card p-6 md:p-8" data-testid="coach-plan-building">
        <p className="cg-eyebrow">Your coach's plan</p>
        <p className="mt-3 text-body text-muted-foreground">Your coach is reading your games. This takes a moment the first time.</p>
      </section>
    );
  }
  const plan = file.plan;
  if (!plan?.steps?.length) return null;
  const notation = file.notation !== false;
  return (
    <section
      className={flush ? "" : "mb-10 rounded-panel border border-border/70 bg-card p-6 shadow-e2 md:p-8"}
      data-testid="coach-plan"
    >
      <p className="cg-eyebrow">Your coach's plan</p>
      <h2 className="mt-2 font-heading text-title text-foreground">How you play, and the way up</h2>
      {plan.read?.length > 0 && (
        <div className="mt-4 space-y-1.5" data-testid="coach-plan-read">
          {plan.read.map((line) => (
            <p key={line} className="text-body text-foreground/90">{line}</p>
          ))}
        </div>
      )}
      {plan.stake?.high > 0 && (
        <div className="mt-5 rounded-card border border-primary/30 bg-primary/[0.05] p-4" data-testid="coach-plan-stake">
          <p className="text-body text-foreground">
            From your recent games, these steps are worth about{" "}
            <span className="font-semibold">{fmt(plan.stake.low)} to {fmt(plan.stake.high)}</span> rating points.
          </p>
          <p className="mt-1 text-note text-muted-foreground">
            {plan.stake.high >= GOAL
              ? "Fix them and the next level is within reach."
              : `That is part of the way to ${fmt(GOAL)}. As you fix these, your coach finds the next ones.`}
          </p>
        </div>
      )}
      {plan.last_week?.words && (
        <p className={`mt-4 rounded-card border p-3 text-note ${plan.last_week.status === "kept" ? "border-emerald-500/30 bg-emerald-500/[0.06] text-foreground" : "border-border/70 text-foreground/90"}`}
          data-testid="coach-plan-last-week">
          {plan.last_week.words}
        </p>
      )}
      <p className="mt-6 text-note font-semibold text-foreground">To reach the next level, in this order:</p>
      <ol className="mt-3 space-y-3">
        {plan.steps.map((s, i) => (
          <Step key={`${s.kind}-${s.title}`} step={s} index={i} check={plan.check} notation={notation}
            done={file.week?.done?.[s.key]} />
        ))}
      </ol>
      {plan.guard && (
        <p className="mt-5 text-note text-muted-foreground" data-testid="coach-plan-guard">
          <span className="font-semibold text-foreground/85">{plan.guard.title}.</span> {plan.guard.text}
        </p>
      )}
    </section>
  );
}
