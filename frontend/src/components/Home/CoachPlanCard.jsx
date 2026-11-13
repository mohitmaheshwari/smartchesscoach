/**
 * CoachPlanCard: the coach's read of the player and up to three steps toward
 * the next level, in the order they cost him games (services/player_coach_plan.py).
 *
 * Top of Home for coach-pages players. Reads the player file (useCoachFile),
 * so it computes nothing. No figures: the order is said in words, and how much
 * each step cost stays on the server in `measured`.
 */
import { Link } from "react-router-dom";
import { Check, Clock, Minus, Target, TrendingDown, TrendingUp } from "lucide-react";

import { useCoachFile } from "@/lib/coachFile";

const ORDER_WORDS = ["First", "Then", "After that"];
// Rating points are the one figure the plan states: the claim Mohit asked for
// ("reach +200"), computed from the player's own games on the server.
const fmt = (n) => `${n > 0 ? "+" : ""}${n}`;
const GOAL = 200;
const STATE_ICON = { better: TrendingDown, kept: Check, worse: TrendingUp, same: Minus, waiting: Clock };

function Step({ step, index, check, notation }) {
  const Icon = STATE_ICON[step.state] || null;
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
        {step.state_title && Icon && (
          <span className="inline-flex items-center gap-1 text-meta text-muted-foreground">
            <Icon className="h-3.5 w-3.5" aria-hidden="true" /> {step.state_title}
          </span>
        )}
      </div>
      <p className="mt-2 font-heading text-lead text-foreground">{step.title}</p>
      <p className="mt-1 text-body text-foreground/90">{step.do}</p>
      {step.sign?.text && (
        <p className="mt-2 text-note text-muted-foreground">
          <span className="font-semibold text-foreground/80">{step.sign.title}.</span> {step.sign.text}
        </p>
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
      {step.training && check?.title && (
        <p className="mt-3 text-note text-foreground/85" data-testid="coach-plan-check">
          <span className="font-semibold">Since you started:</span> {check.title}. {check.words}
        </p>
      )}
      {(step.practice_url || step.learn_url) && (
        <div className="mt-4 flex flex-wrap gap-2">
          {step.practice_url && (
            <Link to={step.practice_url} className="cg-primary-action !min-h-9 !px-4 !py-2 text-note">
              <Target className="h-3.5 w-3.5" /> Practise it
            </Link>
          )}
          {step.learn_url && (
            <Link to={step.learn_url} className="inline-flex items-center rounded-full border border-border px-4 py-2 text-note font-medium text-foreground hover:bg-muted/50">
              See where it happened
            </Link>
          )}
        </div>
      )}
    </li>
  );
}

export default function CoachPlanCard() {
  const file = useCoachFile();
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
    <section className="mb-10 rounded-panel border border-border/70 bg-card p-6 shadow-e2 md:p-8" data-testid="coach-plan">
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
      <p className="mt-6 text-note font-semibold text-foreground">To reach the next level, in this order:</p>
      <ol className="mt-3 space-y-3">
        {plan.steps.map((s, i) => (
          <Step key={`${s.kind}-${s.title}`} step={s} index={i} check={plan.check} notation={notation} />
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
