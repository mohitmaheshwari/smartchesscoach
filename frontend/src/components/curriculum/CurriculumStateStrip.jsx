import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Loader2 } from "lucide-react";
import { API } from "../../App";
import {
  curriculumStateLabel,
  loadPersonalCurriculum,
} from "../../lib/personalCurriculum";

export default function CurriculumStateStrip({ user, surface }) {
  const navigate = useNavigate();
  const [curriculum, setCurriculum] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    loadPersonalCurriculum(API, user?.user_id)
      .then((payload) => {
        if (!cancelled) setCurriculum(payload);
      })
      .catch(() => null)
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user?.user_id]);

  if (loading) {
    return (
      <div className="min-h-16 rounded-xl border border-border/60 bg-card/50 grid place-items-center" aria-label="Loading coaching plan">
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const primary = curriculum?.enabled ? curriculum?.decision?.primary : null;
  if (!primary) return null;
  const state = curriculumStateLabel(primary.state);
  const applicationMeasured = primary.state === "used_in_games";

  return (
    <section
      className="cg-coach-card px-4 py-3.5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
      data-testid={`curriculum-state-${surface}`}
    >
      <div className="min-w-0">
        <p className="cg-eyebrow !text-[10px] mb-1">
          Your current lesson · {state}
        </p>
        <p className="text-sm font-medium text-foreground truncate">{primary.title}</p>
        <p className="text-[11.5px] text-muted-foreground mt-0.5">
          {applicationMeasured
            ? "I’ve seen you use this in a game. I’ll keep watching until it holds under pressure."
            : "We’re still making this feel natural. I’ll watch for it the next time you play."}
        </p>
      </div>
      <button
        type="button"
        onClick={() => navigate(primary.destination?.href || "/learn")}
        className="cg-secondary-action shrink-0"
      >
        Continue
        <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </section>
  );
}
