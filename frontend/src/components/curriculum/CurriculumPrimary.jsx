import { useEffect, useRef } from "react";
import { ArrowRight } from "lucide-react";
import { ANALYTICS_EVENTS, trackCurriculum } from "../../lib/analytics";
import { curriculumCta, curriculumStateLabel } from "../../lib/personalCurriculum";

const eventProps = (curriculum, surface) => {
  const decision = curriculum?.decision;
  const primary = decision?.primary;
  return {
    surface,
    decision_id: decision?.decision_id,
    decision_source: "personal_curriculum",
    recommendation_kind: primary?.outcome,
    content_type: primary?.destination?.lesson_kind,
    content_id: primary?.destination?.lesson_id,
    origin: "recommendation",
    flag_state: "enabled",
    is_recommended: true,
  };
};

export default function CurriculumPrimary({
  curriculum,
  surface,
  onNavigate,
  showReview = true,
}) {
  const primary = curriculum?.decision?.primary;
  const review = curriculum?.decision?.review;
  const teachingProfile = curriculum?.personalized_teaching?.enabled
    ? curriculum?.personalized_teaching?.profile
    : null;
  const shownRef = useRef(null);

  useEffect(() => {
    const decisionId = curriculum?.decision?.decision_id;
    if (!decisionId || shownRef.current === decisionId) return;
    shownRef.current = decisionId;
    trackCurriculum(
      ANALYTICS_EVENTS.CURRICULUM_DECISION_SHOWN,
      eventProps(curriculum, surface)
    );
  }, [curriculum, surface]);

  if (!primary) return null;

  const openPrimary = () => {
    trackCurriculum(
      ANALYTICS_EVENTS.CURRICULUM_PRIMARY_CLICKED,
      eventProps(curriculum, surface)
    );
    onNavigate(primary.destination.href);
  };

  const openReview = () => {
    if (!review) return;
    trackCurriculum(ANALYTICS_EVENTS.CURRICULUM_REVIEW_CLICKED, {
      surface,
      decision_id: curriculum.decision.decision_id,
      decision_source: "personal_curriculum",
      recommendation_kind: review.outcome,
      content_type: review.destination?.lesson_kind,
      content_id: review.destination?.lesson_id,
      origin: "recommendation",
      flag_state: "enabled",
      is_recommended: true,
    });
    onNavigate(review.destination.href);
  };

  return (
    <section
      className="rounded-2xl border border-border/70 bg-card/70 p-5 md:p-7 shadow-sm"
      data-testid={"curriculum-primary-" + surface}
    >
      <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
        <div className="max-w-[560px]">
          <p className="text-[11px] uppercase tracking-[0.18em] text-emerald-600 dark:text-emerald-300 font-semibold mb-3">
            {curriculumStateLabel(primary.state)}
          </p>
          <h2 className="font-serif text-[25px] md:text-[30px] leading-tight text-foreground mb-3">
            {primary.title}
          </h2>
          <p className="text-[14px] leading-relaxed text-muted-foreground mb-3">
            {primary.reason}
          </p>
          <p className="text-[12.5px] leading-relaxed text-muted-foreground/80">
            {primary.evidence}
          </p>
          {teachingProfile && (
            <details className="mt-4 rounded-lg border border-border/70 bg-muted/20">
              <summary className="cursor-pointer px-3.5 py-2.5 text-[12.5px] font-medium text-foreground">
                Why this lesson is for you
              </summary>
              <div className="border-t border-border/70 px-3.5 py-3 space-y-3">
                <p className="text-[12.5px] leading-relaxed text-muted-foreground">
                  {teachingProfile.why_now}
                </p>
                <div className="grid grid-cols-2 gap-2 text-[11.5px]">
                  <div className="rounded-md bg-background/70 p-2.5">
                    <p className="text-muted-foreground">Used in your games</p>
                    <p className="mt-0.5 font-medium text-foreground">Not measured</p>
                  </div>
                  <div className="rounded-md bg-background/70 p-2.5">
                    <p className="text-muted-foreground">Remembered later</p>
                    <p className="mt-0.5 font-medium text-foreground">Not measured</p>
                  </div>
                </div>
              </div>
            </details>
          )}
        </div>
        <button
          type="button"
          onClick={openPrimary}
          className="min-h-11 px-5 rounded-xl bg-emerald-700 hover:bg-emerald-600 text-white font-medium text-[13.5px] transition-colors inline-flex items-center justify-center gap-2 md:shrink-0"
        >
          {curriculumCta(primary.outcome)}
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      {showReview && review && (
        <div className="mt-6 pt-5 border-t border-border/70 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-[10px] uppercase tracking-[0.17em] text-amber-600 dark:text-amber-300 font-semibold mb-1.5">
              One quick review
            </p>
            <h3 className="text-[15px] font-medium text-foreground">{review.title}</h3>
          </div>
          <button
            type="button"
            onClick={openReview}
            className="min-h-10 px-4 rounded-lg border border-border hover:bg-muted/60 text-[13px] font-medium transition-colors"
          >
            Review one position
          </button>
        </div>
      )}
    </section>
  );
}
