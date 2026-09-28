/**
 * TacticalEyeCard - does this player SEE the tactical shapes their games offer,
 * and if not, which of the two reasons is it?
 *
 * The same missed forks mean two different things. A player who misses them
 * while taking his time does not know the shape; one who misses them while
 * moving fast knows it and is not looking. Same symptom, opposite
 * prescriptions - so the drill link differs by layer, and a looking habit must
 * NOT send anyone to more puzzles of the shape they already know.
 *
 * NOT the daily instruction. Home still names exactly one thing to do today;
 * this is something a player reads and may choose to act on. That is why it
 * lives on the progress page beside "How you play" rather than on Home.
 *
 * The attention card deliberately offers a hypothesis rather than a cause. The
 * verdict comes from the player's GENERAL tempo, and the speed of these
 * particular misses does not support a causal claim - measured across 42
 * players, mistakes are LESS rushed than ordinary moves.
 */

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { API } from "@/App";
import { Loader2 } from "lucide-react";
import { Link } from "react-router-dom";

export default function TacticalEyeCard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API}/progress/tactical-eye`, {
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

  // "He finds them" and "not enough chances yet" both render nothing. A card
  // that says everything is fine is a card nobody needs.
  if (!data || !data.measured) return null;

  return (
    <Card data-testid="tactical-eye-card">
      <CardHeader className="pb-3">
        <CardTitle className="text-[17px]">{data.headline}</CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <p className="text-[14px] leading-relaxed text-foreground mb-4">
          {data.body}
        </p>
        <p className="text-[13px] leading-relaxed text-muted-foreground mb-4">
          {data.next}
        </p>
        {data.drill?.href && (
          <Link
            to={data.drill.href}
            className="inline-flex items-center text-[13px] font-medium text-emerald-700 dark:text-emerald-400 hover:underline"
            data-testid="tactical-eye-drill"
          >
            {data.drill.label} →
          </Link>
        )}
      </CardContent>
    </Card>
  );
}
