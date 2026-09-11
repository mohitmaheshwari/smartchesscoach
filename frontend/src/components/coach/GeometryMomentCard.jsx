import { useEffect, useState } from "react";
import { Eye, Loader2, Shapes } from "lucide-react";
import { API } from "@/App";

const GeometryMomentCard = ({ moment, sessionId, onReveal, onDismiss }) => {
  const [current, setCurrent] = useState(moment);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setCurrent(moment);
  }, [moment]);

  if (!current) return null;

  const respond = async (action) => {
    if (busy) return;
    setBusy(true);
    try {
      const response = await fetch(`${API}/coach/play/geometry-moment/respond`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          event_id: current.event_id,
          action,
        }),
      });
      if (!response.ok) return;
      const data = await response.json();
      if (action === "reveal" && data.moment) {
        setCurrent(data.moment);
        onReveal?.(data.moment);
      } else {
        onDismiss?.();
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <article
      className="rounded-2xl border border-emerald-500/30 bg-emerald-500/[0.06] p-5"
      data-testid="geometry-moment-card"
    >
      <div className="flex items-center gap-2 mb-3">
        <Shapes className="w-4 h-4 text-emerald-700 dark:text-emerald-300" />
        <p className="text-[10px] uppercase tracking-[0.22em] text-emerald-700 dark:text-emerald-300 font-semibold">
          {current.eyebrow || "Geometry moment"}
        </p>
      </div>

      {!current.revealed ? (
        <>
          <p className="font-serif text-[17px] leading-snug text-foreground mb-5">
            {current.prompt}
          </p>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => respond("reveal")}
              disabled={busy}
              className="rounded-lg bg-emerald-600 text-white px-3 py-2.5 text-xs font-semibold hover:bg-emerald-500 disabled:opacity-60 inline-flex items-center justify-center gap-1.5"
            >
              {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Eye className="w-3.5 h-3.5" />}
              Show geometry
            </button>
            <button
              type="button"
              onClick={() => respond("skip")}
              disabled={busy}
              className="rounded-lg border border-border px-3 py-2.5 text-xs font-semibold hover:bg-muted/50 disabled:opacity-60"
            >
              Continue playing
            </button>
          </div>
        </>
      ) : (
        <>
          <p className="text-sm leading-relaxed text-foreground">{current.explanation}</p>
          <p className="text-sm leading-relaxed text-emerald-800 dark:text-emerald-200 mt-3 font-medium">
            {current.lesson}
          </p>
          <button
            type="button"
            onClick={() => respond("acknowledge")}
            disabled={busy}
            className="w-full mt-5 rounded-lg bg-foreground text-background px-3 py-2.5 text-xs font-semibold hover:opacity-90 disabled:opacity-60"
          >
            Keep playing
          </button>
        </>
      )}
    </article>
  );
};

export default GeometryMomentCard;
