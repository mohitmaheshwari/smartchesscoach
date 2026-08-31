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
        className="cg-page max-w-[960px]"
        data-testid="personal-curriculum-home"
      >
        <p className="text-[12px] text-muted-foreground mb-5">{greeting}</p>
        <header className="cg-hero mb-6">
          <p className="cg-eyebrow">I’ve been thinking about your games</p>
          <h1 className="cg-title">
            {curriculumHeadline(outcome)}
          </h1>
          <p className="cg-lede">
            I’ve chosen one clear step for today. We’ll stay with it until it begins to feel different in a real game.
          </p>
        </header>
        <div className="cg-panel p-5 sm:p-7">
          <CurriculumPrimary
            curriculum={curriculum}
            surface="home"
            onNavigate={navigate}
          />
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
