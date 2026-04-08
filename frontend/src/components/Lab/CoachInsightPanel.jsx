/**
 * CoachInsightPanel — Habits review for a game
 *
 * Shows:
 * 1. Active pattern check — did your main weakness show up?
 * 2. Failed habits — what you need to fix (shown first)
 * 3. Passed habits — what you did well (collapsed)
 *
 * No score. No Chess DNA. Just behavior.
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import {
  AlertTriangle, CheckCircle2, XCircle,
  Brain, Loader2, Zap, ChevronRight, ChevronDown
} from "lucide-react";

const CoachInsightPanel = ({ gameId, onMoveClick }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showPassed, setShowPassed] = useState(false);

  useEffect(() => {
    if (!gameId) return;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${API}/lab/${gameId}/coach-insight`, { credentials: "include" });
        if (!res.ok) throw new Error("Failed to load");
        setData(await res.json());
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, [gameId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 animate-spin text-primary mr-3" />
        <span className="text-sm text-muted-foreground">Analyzing habits...</span>
      </div>
    );
  }

  if (error || !data?.habits) {
    return (
      <div className="text-center py-16 text-muted-foreground">
        <AlertTriangle className="w-8 h-8 mx-auto mb-3 opacity-50" />
        <p className="text-sm">{error || "No habit data available"}</p>
      </div>
    );
  }

  const habits = data.habits;
  const failed = (habits.habits || []).filter(h => !h.passed);
  const passed = (habits.habits || []).filter(h => h.passed);

  return (
    <div className="space-y-5">

      {/* Active pattern check — did your main weakness show up? */}
      {habits.focus_habit && (
        <div className="p-4 rounded-xl border border-red-500/15 bg-red-500/[0.03]">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="w-3.5 h-3.5 text-red-400" strokeWidth={2.5} />
            <p className="text-xs font-bold uppercase tracking-wider text-red-400">Your pattern showed up</p>
          </div>
          <p className="text-sm text-foreground font-medium mb-1">{habits.focus_habit.name}</p>
          <p className="text-xs text-muted-foreground">{habits.focus_habit.evidence}</p>
          {habits.focus_habit.impact && (
            <p className="text-xs text-red-400/80 mt-1">{habits.focus_habit.impact}</p>
          )}
        </div>
      )}

      {/* Failed habits — what you need to fix (shown first, always visible) */}
      {failed.length > 0 && (
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-red-400/70 mb-2">
            What went wrong
          </p>
          <div className="space-y-2">
            {failed.map((habit, i) => (
              <div key={i} className="p-3 rounded-lg border border-red-500/10 bg-red-500/[0.02]">
                <div className="flex items-start gap-2.5">
                  <XCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" strokeWidth={2} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground">{habit.name}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{habit.evidence}</p>
                    {habit.impact && (
                      <p className="text-xs text-red-400/70 mt-0.5">{habit.impact}</p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* No failed habits — clean game */}
      {failed.length === 0 && (
        <div className="p-4 rounded-xl border border-emerald-500/15 bg-emerald-500/[0.03] text-center">
          <CheckCircle2 className="w-6 h-6 text-emerald-500 mx-auto mb-2" strokeWidth={2} />
          <p className="text-sm text-emerald-500 font-medium">All habits passed. Clean game.</p>
        </div>
      )}

      {/* Passed habits — collapsed by default */}
      {passed.length > 0 && (
        <div>
          <button
            onClick={() => setShowPassed(!showPassed)}
            className="flex items-center gap-2 text-xs text-muted-foreground/50 hover:text-muted-foreground transition-colors mb-2"
          >
            <CheckCircle2 className="w-3 h-3 text-emerald-500/50" strokeWidth={2} />
            What you did well ({passed.length})
            {showPassed
              ? <ChevronDown className="w-3 h-3" />
              : <ChevronRight className="w-3 h-3" />
            }
          </button>
          {showPassed && (
            <div className="space-y-1.5">
              {passed.map((habit, i) => (
                <div key={i} className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-emerald-500/[0.02] border border-emerald-500/10">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500/60 flex-shrink-0" strokeWidth={2} />
                  <p className="text-sm text-foreground/60">{habit.name}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default CoachInsightPanel;
