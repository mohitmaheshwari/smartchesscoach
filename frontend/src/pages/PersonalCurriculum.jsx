import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { ArrowRight, Loader2 } from "lucide-react";
import Layout from "@/components/Layout";
import CurriculumPrimary from "@/components/curriculum/CurriculumPrimary";
import { API } from "@/App";
import { ANALYTICS_EVENTS, trackCurriculum } from "@/lib/analytics";
import {
  EXPLORE_DESTINATIONS,
  loadPersonalCurriculum,
} from "@/lib/personalCurriculum";

export default function PersonalCurriculum({ user }) {
  const navigate = useNavigate();
  const [curriculum, setCurriculum] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    loadPersonalCurriculum(API, user?.user_id)
      .then((data) => {
        if (cancelled) return;
        setCurriculum(data);
        if (data.enabled) {
          trackCurriculum(ANALYTICS_EVENTS.LEARN_VIEWED, {
            surface: "learn",
            decision_id: data.decision?.decision_id,
            decision_source: "personal_curriculum",
            recommendation_kind: data.decision?.primary?.outcome,
            flag_state: "enabled",
          });
        }
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user?.user_id]);

  if (loading) {
    return (
      <Layout user={user}>
        <div className="h-[60vh] grid place-items-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </Layout>
    );
  }

  if (!error && curriculum && !curriculum.enabled) {
    return <Navigate to="/lab" replace />;
  }

  if (error || !curriculum?.decision?.primary) {
    return (
      <Layout user={user}>
        <main className="cg-page max-w-[720px]">
          <section className="cg-hero">
          <p className="cg-eyebrow">Your coach</p>
          <h1 className="cg-title !text-[clamp(2rem,5vw,3.4rem)]">Your plan is taking a moment.</h1>
          <p className="cg-lede mb-6">
            I cannot reach your recommendation just now, but nothing you have learned is lost. Your lessons are still ready.
          </p>
          <button
            type="button"
            onClick={() => navigate("/lab")}
            className="cg-primary-action"
          >
            Open my lessons
          </button>
          </section>
        </main>
      </Layout>
    );
  }

  const naturallyNext = curriculum.naturally_next;

  return (
    <Layout user={user}>
      <main
        className="cg-page max-w-[940px]"
        data-testid="personal-curriculum-page"
      >
        <header className="cg-hero mb-10">
          <p className="cg-eyebrow">Your coaching plan</p>
          <h1 className="cg-title">One lesson at a time.</h1>
          <p className="cg-lede">
            I’ll keep one lesson in focus until it begins showing up in your games. You can still explore anything without losing your place.
          </p>
        </header>

        <section className="cg-panel p-5 sm:p-7">
          <CurriculumPrimary
            curriculum={curriculum}
            surface="learn"
            onNavigate={navigate}
          />
        </section>

        {naturallyNext && (
          <section
            className="cg-panel mt-5 px-5 sm:px-7"
            aria-label="Next lesson in your coaching plan"
          >
            <div className="grid gap-3 md:grid-cols-[140px_1fr_auto] md:items-center py-6">
              <p className="cg-eyebrow !text-[10px]">When this feels natural</p>
              <div>
                <h2 className="text-[16px] font-medium mb-1">{naturallyNext.title}</h2>
                <p className="text-[13px] leading-relaxed text-muted-foreground">{naturallyNext.reason || "We’ll come back to this when your current lesson is settled."}</p>
              </div>
              <button
                type="button"
                onClick={() => navigate(naturallyNext.destination.href)}
                className="cg-secondary-action"
              >
                Take a look
              </button>
            </div>
          </section>
        )}

        <section className="mt-14" aria-labelledby="curriculum-explore-heading">
          <p className="cg-eyebrow mb-3">Your wider chess education</p>
          <h2 id="curriculum-explore-heading" className="font-heading text-[30px] md:text-[38px] tracking-[-0.035em] mb-2">Curious about something else?</h2>
          <p className="text-[14px] leading-relaxed text-muted-foreground mb-5">
            Explore openings, traps, endgames, tactics, and positional ideas. Your main lesson will still be here when you return.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {EXPLORE_DESTINATIONS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  trackCurriculum(ANALYTICS_EVENTS.EXPLORE_OPENED, {
                    surface: "learn",
                    decision_id: curriculum.decision.decision_id,
                    decision_source: "personal_curriculum",
                    content_type: item.id,
                    origin: "explore",
                    flag_state: "enabled",
                    is_recommended: false,
                  });
                  navigate(item.href);
                }}
                className="cg-panel group min-h-[72px] px-5 text-left flex items-center justify-between gap-4 transition-all hover:-translate-y-0.5 hover:border-emerald-700/25"
              >
                <span className="text-[14px] font-medium">{item.label}</span>
                <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-foreground" aria-hidden="true" />
              </button>
            ))}
          </div>
        </section>
      </main>
    </Layout>
  );
}
