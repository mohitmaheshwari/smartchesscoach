/**
 * The curriculum home. docs/home_merge_scope.md
 *
 * THE RULE: the curriculum decides what you do, the evidence proves it is
 * working. One instruction, then one card of proof, in that order.
 *
 * This page answered "what do I do today" better than the dashboard ever did,
 * and had no answer at all to "is any of this working" — a player did the one
 * thing and left, and nothing told them it was moving. That is the retention
 * hole, because "did it work" is the only reason to come back.
 *
 * The evidence is ONE card, below the instruction, and must never compete with
 * it. If it grows a second and a third, this page has turned back into the
 * scrolling report it was built to replace.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";
import Layout from "@/components/Layout";
import CurriculumPrimary from "@/components/curriculum/CurriculumPrimary";
import ChancesCard from "@/components/coach/ChancesCard";
import FindingCard from "@/components/coach/FindingCard";
import SessionCard from "@/components/coach/SessionCard";
import { curriculumHeadline } from "@/lib/personalCurriculum";

export default function CurriculumHome({ user, curriculum, greeting }) {
  const navigate = useNavigate();

  // Why this topic, fetched once and shown NEXT TO THE TOPIC rather than in a
  // card further down. Mohit, 2026-10-07: "nothing has changed on home page" --
  // it had, but only below the fold, and the part he reads was untouched.
  const [focusWhy, setFocusWhy] = useState(null);
  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/home/session`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (!cancelled) setFocusWhy(d?.focus_why || null); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);
  const outcome = curriculum?.decision?.primary?.outcome;

  return (
    <Layout user={user}>
      <main
        className="cg-page"
        data-testid="personal-curriculum-home"
      >
        <p className="text-[12px] text-muted-foreground mb-5">{greeting}</p>
        {/* The one thing worth interrupting them with, above everything else.
            A weekly summary is something a player can work out for themselves;
            this is not. services/striking_finding.py */}
        <FindingCard />
        <header className="cg-hero mb-6">
          <p className="cg-eyebrow">I’ve been thinking about your games</p>
          <h1 className="cg-title">
            {curriculumHeadline(outcome)}
          </h1>
          <p className="cg-lede">
            Here's today's one thing. We'll keep working on it until it shows up differently in a real game.
          </p>
        </header>
        <div className="cg-panel p-5 sm:p-7">
          <CurriculumPrimary
            curriculum={curriculum}
            surface="home"
            onNavigate={navigate}
            focusWhy={focusWhy}
          />
        </div>
        {/* Today's session: what the coach chose and why. Above the proof,
            because the decision is the point of the page and the evidence is
            the reason to believe it. docs/home_session_scope.md */}
        <div className="mt-6">
          {/* The lesson card above already carries the why, directly under the
              topic it explains. */}
          <SessionCard showFocusWhy={false} />
        </div>
        {/* The proof, under the instruction and never above it. Renders
            nothing at all when the player has not been offered enough
            chances, so a new account still sees a single clean task. */}
        <div className="mt-6">
          <ChancesCard />
        </div>
        <button
          type="button"
          onClick={() => navigate("/learn")}
          className="cg-secondary-action mt-6"
        >
          See the rest of my plan
        </button>
      </main>
    </Layout>
  );
}
