import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { ArrowRight, Loader2 } from "lucide-react";
import Layout from "@/components/Layout";
import CurriculumPrimary from "@/components/curriculum/CurriculumPrimary";
import { API } from "@/App";
import { ANALYTICS_EVENTS, trackCurriculum } from "@/lib/analytics";
import { EXPLORE_DESTINATIONS } from "@/lib/personalCurriculum";

export default function PersonalCurriculum({ user }) {
  const navigate = useNavigate();
  const [curriculum, setCurriculum] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(API + "/coach/personal-curriculum", { credentials: "include" })
      .then(async (response) => {
        if (!response.ok) throw new Error("curriculum unavailable");
        return response.json();
      })
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
  }, []);

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
        <main className="max-w-[620px] mx-auto px-5 py-16">
          <h1 className="font-serif text-3xl mb-4">Your plan is taking a moment.</h1>
          <p className="text-muted-foreground mb-6">
            Your lessons are still available while the coach reconnects.
          </p>
          <button
            type="button"
            onClick={() => navigate("/lab")}
            className="min-h-11 px-5 rounded-xl bg-emerald-700 text-white"
          >
            Open Learn
          </button>
        </main>
      </Layout>
    );
  }

  const primary = curriculum.decision.primary;
  const naturallyNext = curriculum.naturally_next;

  return (
    <Layout user={user}>
      <main
        className="max-w-[820px] mx-auto px-5 sm:px-7 py-11 md:py-16"
        data-testid="personal-curriculum-page"
      >
        <p className="text-[11px] uppercase tracking-[0.2em] text-emerald-700 dark:text-emerald-300 font-semibold mb-4">
          Your coaching plan
        </p>
        <h1 className="font-serif text-[35px] md:text-[48px] leading-[1.05] tracking-[-0.025em] font-medium mb-5">
          One lesson at a time.
        </h1>
        <p className="text-[16px] leading-relaxed text-muted-foreground mb-9 max-w-[680px]">
          Your coach keeps the plan focused. You can explore anything without losing your place.
        </p>

        <CurriculumPrimary
          curriculum={curriculum}
          surface="learn"
          onNavigate={navigate}
        />

        <section className="mt-10 border-t border-border/70" aria-label="Coaching plan sequence">
          <div className="grid gap-3 md:grid-cols-[140px_1fr_auto] md:items-center py-6">
            <p className="text-[12px] font-semibold text-emerald-700 dark:text-emerald-300">Learning now</p>
            <div>
              <h2 className="text-[16px] font-medium mb-1">{primary.title}</h2>
              <p className="text-[13px] text-muted-foreground">{primary.reason}</p>
            </div>
            <span className="text-[12px] text-muted-foreground">In your plan</span>
          </div>

          {naturallyNext && (
            <div className="grid gap-3 md:grid-cols-[140px_1fr_auto] md:items-center py-6 border-t border-border/70">
              <p className="text-[12px] font-semibold text-muted-foreground">Naturally next</p>
              <div>
                <h2 className="text-[16px] font-medium mb-1">{naturallyNext.title}</h2>
                <p className="text-[13px] text-muted-foreground">{naturallyNext.reason}</p>
              </div>
              <button
                type="button"
                onClick={() => navigate(naturallyNext.destination.href)}
                className="min-h-10 px-4 rounded-lg border border-border hover:bg-muted/60 text-[13px]"
              >
                View lesson
              </button>
            </div>
          )}
        </section>

        <section className="mt-12" aria-labelledby="curriculum-explore-heading">
          <h2 id="curriculum-explore-heading" className="font-serif text-[27px] mb-2">Explore</h2>
          <p className="text-[14px] leading-relaxed text-muted-foreground mb-5">
            Choose what you are curious about. Your coach's recommendation stays in place.
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
                className="min-h-12 px-4 rounded-xl bg-muted/55 hover:bg-muted text-left flex items-center justify-between gap-4 transition-colors"
              >
                <span className="text-[14px] font-medium">{item.label}</span>
                <ArrowRight className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              </button>
            ))}
          </div>
        </section>
      </main>
    </Layout>
  );
}
