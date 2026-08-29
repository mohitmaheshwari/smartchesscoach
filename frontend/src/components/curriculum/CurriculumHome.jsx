import { useNavigate } from "react-router-dom";
import Layout from "@/components/Layout";
import CurriculumPrimary from "@/components/curriculum/CurriculumPrimary";
import { curriculumHeadline } from "@/lib/personalCurriculum";

export default function CurriculumHome({ user, curriculum, greeting }) {
  const navigate = useNavigate();
  const outcome = curriculum?.decision?.primary?.outcome;

  return (
    <Layout user={user}>
      <main
        className="max-w-[780px] mx-auto px-5 sm:px-7 py-11 md:py-16"
        data-testid="personal-curriculum-home"
      >
        <p className="text-[12px] text-muted-foreground mb-12">{greeting}</p>
        <p className="text-[11px] uppercase tracking-[0.2em] text-emerald-700 dark:text-emerald-300 font-semibold mb-4">
          Today with your coach
        </p>
        <h1 className="font-serif text-[35px] md:text-[48px] leading-[1.05] tracking-[-0.025em] font-medium text-foreground mb-5 max-w-[680px]">
          {curriculumHeadline(outcome)}
        </h1>
        <p className="text-[16px] leading-relaxed text-muted-foreground mb-8 max-w-[650px]">
          One clear step today. Your full lesson library is always available in Learn.
        </p>
        <CurriculumPrimary
          curriculum={curriculum}
          surface="home"
          onNavigate={navigate}
        />
        <button
          type="button"
          onClick={() => navigate("/learn")}
          className="mt-7 text-[13px] text-muted-foreground hover:text-foreground hover:underline"
        >
          See your full coaching plan
        </button>
      </main>
    </Layout>
  );
}
