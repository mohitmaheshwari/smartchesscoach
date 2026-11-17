/**
 * HomeCoachLines
 *
 * The two "Before your next game" lines for a player without the coach pages
 * (docs/home_behaviour_and_clock_scope.md): how he played as a person in his
 * last game, and which clock to play. Coach-pages players see the same lines
 * inside BetweenGamesPanel, from the same server function. Renders nothing
 * until the server answers, and nothing when neither line was found true.
 */
import { useEffect, useState } from "react";
import { Clock3, UserRound } from "lucide-react";

import { API } from "@/App";
import { CoachLine } from "@/components/Home/BetweenGamesPanel";

export default function HomeCoachLines() {
  const [data, setData] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await fetch(`${API}/home/coach-lines`, { credentials: "include" });
        if (!res.ok) return;
        const body = await res.json();
        if (alive) setData(body);
      } catch {
        /* Home renders without these lines. */
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  if (!data?.behaviour?.headline && !data?.clock_advice?.headline) return null;

  return (
    <section
      data-testid="home-coach-lines"
      className="mt-6 overflow-hidden rounded-panel border border-border/70 bg-card p-6 shadow-e2 md:p-8"
    >
      <p className="cg-eyebrow">Before your next game</p>
      <div className="mt-4 space-y-4">
        <CoachLine testId="between-games-behaviour" icon={UserRound} label="You, in that game" line={data.behaviour} />
        <CoachLine testId="between-games-clock" icon={Clock3} label="What to play" line={data.clock_advice} />
      </div>
    </section>
  );
}
