/**
 * TacticsMasteryPanel — the fork / pin / skewer mastery view.
 *
 * Companion to MasteryPanel (fundamentals skill tree). This one covers the
 * TACTICS half of mastery, which the engine-2 skill tree does NOT track:
 *   - GET /api/motif-recognition → per-motif mastery ladder (Learning →
 *     Developing → Solid → Sharp → Mastered) + trend + two-sided attack/defense.
 *   - GET /api/motif-profile     → patterns you find (strengths) vs patterns
 *     that catch you (weaknesses), each weakness with a lesson + drill link.
 *
 * Lives on the Lab (the mastery + learning-path home) alongside MasteryPanel.
 * Extracted from UnifiedProgress 2026-07-08 so both pages share ONE renderer
 * instead of duplicating the JSX (single-source). Mohit: "I don't see anything
 * for pins or forks" — they were tracked, but in a separate card on a separate
 * page from the skill tree he was looking at. This unifies them.
 *
 * Auto-hides entirely when the user has no motif data.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";

const TREND = {
  up:     { dot: "bg-emerald-500", label: "Improving lately", icon: "↗", cls: "text-emerald-600 dark:text-emerald-400" },
  down:   { dot: "bg-amber-500",   label: "Slipped a little",  icon: "↘", cls: "text-amber-600 dark:text-amber-400" },
  steady: { dot: "bg-sky-500",     label: "Holding steady",    icon: "→", cls: "text-sky-600 dark:text-sky-400" },
  new:    { dot: "bg-muted-foreground/40", label: "Just getting going", icon: "·", cls: "text-muted-foreground" },
};

export default function TacticsMasteryPanel() {
  const navigate = useNavigate();
  const [reco, setReco] = useState(null);
  const [motif, setMotif] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const [recoRes, motifRes] = await Promise.all([
          fetch(`${API}/motif-recognition`, { credentials: "include" }),
          fetch(`${API}/motif-profile`, { credentials: "include" }),
        ]);
        if (recoRes.ok) setReco(await recoRes.json());
        if (motifRes.ok) setMotif(await motifRes.json());
      } catch (e) {
        console.error(e);
      }
    })();
  }, []);

  const hasReco = reco && (reco.rows || []).length > 0;
  const hasMotif =
    motif && ((motif.strengths || []).length > 0 || (motif.weaknesses || []).length > 0);
  if (!hasReco && !hasMotif) return null;

  return (
    <div className="space-y-14">
      {/* ─── Tactics mastery ladder: your level + which way you're moving ─── */}
      {hasReco && (
        <section>
          <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-2">
            Your tactics · where you are, where you're heading
          </div>
          <div className="text-[12px] text-muted-foreground mb-5">
            Your level on the path to mastering each tactic — and whether you're climbing.
          </div>
          <div className="space-y-5">
            {(reco.rows || []).map((r) => {
              const trend = TREND[(r.trend || {}).dir] || {};
              return (
                <div key={r.motif} className="rounded-xl border border-border p-5">
                  <div className="flex items-baseline justify-between mb-3">
                    <div className="text-[15px] font-semibold text-foreground">{r.label}</div>
                    <div className={`text-[12px] font-medium inline-flex items-center gap-1 ${trend.cls}`}>
                      <span className="text-[14px] leading-none">{trend.icon}</span> {trend.label}
                    </div>
                  </div>
                  {/* tier ladder */}
                  <div className="flex items-center justify-between mb-1.5">
                    {(r.tiers || []).map((name, i) => (
                      <div
                        key={name}
                        className={`text-[10px] tracking-wide ${
                          i === r.tier_index ? "text-foreground font-semibold" : "text-muted-foreground/50"
                        }`}
                      >
                        {name}
                      </div>
                    ))}
                  </div>
                  <div className="relative h-2.5 rounded-full bg-muted overflow-hidden">
                    <div className={`h-full rounded-full ${trend.dot}`} style={{ width: `${r.fill_pct}%` }} />
                    {[20, 40, 60, 80].map((x) => (
                      <div key={x} className="absolute top-0 h-full w-px bg-background/70" style={{ left: `${x}%` }} />
                    ))}
                  </div>
                  <div className="flex items-center justify-between gap-3 mt-2.5">
                    <div className="text-[12.5px] text-muted-foreground">
                      You're at <span className="text-foreground font-medium">{r.tier}</span>
                      {r.next_tier ? <> · next rung: {r.next_tier}</> : <> — top of the ladder.</>}
                      {r.trust === "rough" && <span className="text-[11px] opacity-60"> · rough read</span>}
                      {r.two_sided_note && (
                        <div className="mt-1.5 text-[12px]">
                          <span className="text-emerald-600 dark:text-emerald-400">Attack: {r.attack?.tier}</span>
                          <span className="opacity-40"> · </span>
                          <span className="text-amber-600 dark:text-amber-400">Defense: {r.defense?.tier ?? "—"}</span>
                          <div className="text-foreground/70 mt-0.5">{r.two_sided_note}</div>
                        </div>
                      )}
                    </div>
                    {/* Drill lives on the Lab — the drill-down back where work happens. */}
                    {r.drill && (
                      <button
                        onClick={() => navigate(`/training/pattern/${r.motif}`)}
                        className="shrink-0 text-[12.5px] font-medium text-violet-600 dark:text-violet-400 hover:underline whitespace-nowrap"
                      >
                        Practice →
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ─── Tactics profile: patterns you find vs patterns that catch you ─── */}
      {hasMotif && (
        <section>
          <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-5">
            Your tactics · patterns you find vs patterns that catch you
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div className="rounded-xl border border-border p-5">
              <div className="text-[11px] uppercase tracking-wide text-emerald-500 dark:text-emerald-400 font-semibold mb-3">
                You identify easily
              </div>
              {(motif.strengths || []).length ? (
                (motif.strengths || []).map((s) => (
                  <div key={s.motif} className="mb-3 last:mb-0">
                    <div className="text-[14px] font-medium text-foreground">{s.label} ✓</div>
                    <div className="text-[12.5px] text-muted-foreground leading-relaxed">{s.lesson}</div>
                  </div>
                ))
              ) : (
                <div className="text-[12.5px] text-muted-foreground">Keep playing — your strengths will surface here.</div>
              )}
            </div>
            <div className="rounded-xl border border-border p-5">
              <div className="text-[11px] uppercase tracking-wide text-rose-500 dark:text-rose-400 font-semibold mb-3">
                Patterns giving you trouble
              </div>
              {(motif.weaknesses || []).length ? (
                (motif.weaknesses || []).map((w) => (
                  <div key={w.motif} className="mb-4 last:mb-0">
                    <div className="text-[14px] font-medium text-foreground">{w.label} — keeps catching you</div>
                    <div className="text-[12.5px] text-muted-foreground leading-relaxed mb-2">💡 {w.lesson}</div>
                    {(w.drill_pattern || w.motif) && (
                      <button
                        onClick={() => navigate(`/training/pattern/${w.drill_pattern || w.motif}`)}
                        className="text-[12.5px] font-medium text-violet-600 dark:text-violet-400 hover:underline"
                      >
                        Practice {w.label?.toLowerCase() || "this"}
                        {w.drill_count ? ` · ${w.drill_count} positions` : ""} →
                      </button>
                    )}
                  </div>
                ))
              ) : (
                <div className="text-[12.5px] text-muted-foreground">No recurring tactical weakness yet — nice.</div>
              )}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
