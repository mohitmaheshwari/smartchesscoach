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
      className="relative"
      data-testid={"curriculum-primary-" + surface}
    >
      <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
        <div className="max-w-[560px]">
          <p className="cg-eyebrow mb-3">
            {curriculumStateLabel(primary.state)}
          </p>
          <h2 className="font-heading text-[26px] md:text-[34px] leading-[1.08] tracking-[-0.03em] text-foreground mb-3">
            {primary.title}
          </h2>
          <p className="text-[14px] leading-relaxed text-muted-foreground mb-3">
            {primary.reason}
          </p>
          <p className="text-[13px] leading-relaxed text-muted-foreground/85">
            {primary.evidence}
          </p>
          {teachingProfile && (
            <details className="mt-5 rounded-2xl border border-emerald-700/15 bg-emerald-500/[0.055]">
              <summary className="cursor-pointer px-4 py-3 text-[12.5px] font-semibold text-foreground">
                What I noticed in your games
              </summary>
              <div className="border-t border-emerald-700/10 px-4 py-4 space-y-3">
                <p className="text-[12.5px] leading-relaxed text-muted-foreground">
                  {teachingProfile.why_now}
                </p>
                <p className="text-[12px] leading-relaxed text-muted-foreground/80">
                  I’ll keep watching for the same decision when you play again. That is how we’ll know when the lesson is becoming yours.
                </p>
              </div>
            </details>
          )}
        </div>
        <button
          type="button"
          onClick={openPrimary}
          className="cg-primary-action md:shrink-0"
        >
          {curriculumCta(primary.outcome)}
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      {showReview && review && (
        <div className="mt-7 pt-6 border-t border-border/70 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="cg-eyebrow !text-[10px] mb-1.5">
              Before you move on
            </p>
            <h3 className="text-[15px] font-medium text-foreground">{review.title}</h3>
          </div>
          <button
            type="button"
            onClick={openReview}
            className="cg-secondary-action"
          >
            Revisit one position
          </button>
        </div>
      )}
    </section>
  );
}
