/**
 * The home page, as a coaching session. docs/home_as_a_coach_scope.md
 *
 * Mohit, 2026-10-07, after four rounds of layouts: *"it is still not looking
 * like a coach, it looks like a report"* — and then the process itself: a coach
 * reads your games, tells you what is good and what is bad, trains the bad, and
 * plays you.
 *
 * So this page is now read top to bottom as one session rather than scanned as
 * a stack of cards:
 *
 *   what I know about you   (the good thing first, then the costly one)
 *   today                   (your board, your move, a question before an answer)
 *   now go and do it        (the lesson, which is the only part with a drill)
 *   play me                 (the part a puzzle cannot do)
 *
 * WHAT WAS REMOVED AND WHERE IT WENT. FindingCard, SessionCard and ChancesCard
 * each fetched /home/session separately — three identical round trips for one
 * page — and each added a card. The finding and the focus-why are now the
 * second line of movement one; the good move the session card celebrated is the
 * board inside movement one; the chances reading sits inside movement one too,
 * because it is an assessment and Mohit asked for it specifically — *"quality
 * of moves vs chances provided"* — so taking it off the page would have undone
 * his own ask. Nothing was dropped; three cards became one movement.
 *
 * IF THIS GROWS A FOURTH AND FIFTH CARD it has turned back into the report it
 * was built to replace, which has now happened twice.
 */
import { useNavigate } from "react-router-dom";
import Layout from "@/components/Layout";
import CurriculumPrimary from "@/components/curriculum/CurriculumPrimary";
import CoachMovements from "@/components/coach/CoachMovements";
import ChancesCard from "@/components/coach/ChancesCard";

export default function CurriculumHome({ user, curriculum, greeting }) {
  const navigate = useNavigate();

  return (
    <Layout user={user}>
      <main
        className="cg-page"
        data-testid="personal-curriculum-home"
      >
        <p className="text-[12px] text-muted-foreground mb-7">{greeting}</p>

        {/* Movements one and two, then the lesson, then the invitation last.
            CoachMovements renders its children between movements two and
            three, so the order on screen is know → think → practise → play. */}
        <CoachMovements assessment={<ChancesCard />}>
          {/* The lesson. Movement two asks the question; this is the only part
              of the page with positions to actually practise behind it, so it
              stays — a coach does not ask what you were thinking and then leave
              you with nothing to do about it. */}
          <div className="cg-panel mb-10 p-5 sm:p-7">
            <CurriculumPrimary
              curriculum={curriculum}
              surface="home"
              onNavigate={navigate}
            />
          </div>
        </CoachMovements>

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
