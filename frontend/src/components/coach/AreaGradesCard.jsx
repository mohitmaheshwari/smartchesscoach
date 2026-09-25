/**
 * AreaGradesCard - where the player stands in every part of their game.
 *
 * A player currently sees exactly one area on Home, because one topic is
 * authorised to drive a plan. Their games contain five more, plus an
 * opening/middlegame/endgame split that is computed on every move and has
 * never been shown anywhere.
 *
 * Display-only. This says where you stand, never what to do about it -- the
 * one action stays on Home so there is still a single instruction.
 *
 * Deliberately carries NO numbers. The grade comes from how this player
 * compares with others in THAT area, and the rate that produced it is never
 * rendered.
 */

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { API } from "@/App";
import { Loader2 } from "lucide-react";

// Worst reads warmest, so the eye lands on what is worth working on without
// the page turning into a wall of red.
const GRADE_STYLES = {
  "Excellent": "text-emerald-600 dark:text-emerald-400",
  "Good": "text-foreground",
  "Fair": "text-amber-600 dark:text-amber-400",
  "Needs work": "text-rose-600 dark:text-rose-400",
};

function GradeRow({ row }) {
  const grade = row.measured ? row.grade : "Not enough games yet";
  const tone = row.measured
    ? (GRADE_STYLES[row.grade] || "text-foreground")
    : "text-muted-foreground";
  return (
    <div className="flex items-baseline justify-between gap-4 py-2 border-b border-border/40 last:border-0">
      <span className="text-[14px] text-foreground">{row.label}</span>
      <span className={`text-[13px] font-medium whitespace-nowrap ${tone}`}>
        {grade}
      </span>
    </div>
  );
}

export default function AreaGradesCard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API}/progress/area-grades`, {
          credentials: "include",
        });
        if (res.ok && !cancelled) setData(await res.json());
      } catch (e) {
        // Non-fatal: the card simply does not render.
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-10">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (!data || !Array.isArray(data.areas) || data.areas.length === 0) return null;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-[17px]">Where you stand</CardTitle>
        <p className="text-[13px] text-muted-foreground">
          Compared with other players, from your own games.
        </p>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="mb-5">
          {data.areas.map((row) => <GradeRow key={row.key} row={row} />)}
        </div>
        <p className="text-[12px] uppercase tracking-wide text-muted-foreground mb-1">
          Across the game
        </p>
        <div>
          {data.phases.map((row) => <GradeRow key={row.key} row={row} />)}
        </div>
      </CardContent>
    </Card>
  );
}
