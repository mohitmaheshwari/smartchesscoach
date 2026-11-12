/**
 * PreparedFocus: what the coach works on when the focus picker has nothing.
 *
 * Mohit, 2026-11-12: the old line "I have not settled on the one pattern to
 * work on with you yet" "should never show, coach should be very well
 * prepared". The player file always has an answer from his games (the habit
 * a trusted detector proves, else his costliest opening habit, else the move
 * that decided his last game): GET /home/prepared-focus. The first visit may
 * build the file in the background; ask again shortly.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";

import { API } from "@/App";

const POLL_MS = 5000;
const MAX_POLLS = 12;

export default function PreparedFocus() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);

  useEffect(() => {
    let alive = true;
    let polls = 0;
    let timer = null;
    const load = async () => {
      try {
        const res = await fetch(`${API}/home/prepared-focus`, { credentials: "include" });
        if (!alive || !res.ok) return;
        const body = await res.json();
        if (!alive) return;
        setData(body);
        if (body?.state === "building" && polls < MAX_POLLS) {
          polls += 1;
          timer = setTimeout(load, POLL_MS);
        }
      } catch {
        /* Home renders without it. */
      }
    };
    load();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, []);

  // "none": nothing beyond the last game, which LastGameCard already tells.
  if (!data || data.state !== "ready" || data.kind === "none" || !data.title) return null;

  // .cg-coach-card prints its own "Your coach" label; no second eyebrow.
  return (
    <div data-testid="prepared-focus" className="cg-coach-card">
      <h3 className="text-lead font-heading font-semibold text-foreground">
        {data.kind === "habit" ? <>We work on: {data.title.charAt(0).toLowerCase() + data.title.slice(1)}</> : data.title}
      </h3>
      {data.sign?.text && <p className="mt-2 text-note text-foreground/85">{data.sign.text}</p>}
      {data.rule && (
        <p className="mt-2 text-note text-foreground/85">
          <span className="font-semibold">Your rule:</span> {data.rule}
        </p>
      )}
      {data.detail && <p className="mt-2 text-note text-foreground/85">{data.detail}</p>}
      {data.kind !== "reading" && <button
        type="button"
        onClick={() => navigate(data.see_url || "/games")}
        className="cg-primary-action mt-5"
        data-testid="prepared-focus-see"
      >
        {data.see_url ? "See where it happened" : "Review your games"}
        <ArrowRight className="h-4 w-4" strokeWidth={2} />
      </button>}
    </div>
  );
}
