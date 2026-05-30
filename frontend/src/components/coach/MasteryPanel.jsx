/**
 * MasteryPanel — what the user has studied across the Engine 2 skill tree.
 *
 * Pairs with the "ledger" view (UnifiedProgress): that page tracks what
 * you're still working on; this panel surfaces what you've cleared at
 * least once. We say "studied" not "learned" on purpose — the current
 * graduation rule for most kinds is "completed the guided lesson", which
 * doesn't prove retention. In-game application detectors will upgrade
 * specific skills to a real "learned" label once they ship.
 *
 * Reads GET /api/engine2/mastery-summary — four-state roll-up:
 * studied | learning | stale | unseen.
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";
import { Check, RotateCcw, Circle, Loader2, ArrowRight, X } from "lucide-react";

const KIND_TITLE = {
  endgame: "Endgames",
  mate_pattern: "Mate patterns",
  opening: "Openings",
  trap_set: "Traps",
  concept: "Concepts",
  coached_play: "Coached play",
};

// Render order: knowledge skills first, then craft skills.
const KIND_ORDER = [
  "concept",
  "endgame",
  "mate_pattern",
  "opening",
  "trap_set",
  "coached_play",
];

function StateIcon({ state }) {
  if (state === "studied") {
    return <Check className="h-3.5 w-3.5 text-emerald-500" strokeWidth={2.4} />;
  }
  if (state === "stale") {
    return <RotateCcw className="h-3.5 w-3.5 text-amber-500" strokeWidth={2.2} />;
  }
  if (state === "learning") {
    return <Circle className="h-3 w-3 text-violet-500 fill-violet-500/30" strokeWidth={2} />;
  }
  return <Circle className="h-3 w-3 text-muted-foreground/40" strokeWidth={1.5} />;
}

function meta(record) {
  if (record.state === "studied") {
    const d = record.days_since_studied;
    if (d == null) return "Just studied";
    if (d === 0) return "Studied today";
    if (d === 1) return "Studied yesterday";
    return `Studied ${d} days ago`;
  }
  if (record.state === "stale") {
    const d = record.days_since_studied;
    return d != null
      ? `Worth a refresher · ${d} days since last clean`
      : "Worth a refresher";
  }
  if (record.state === "learning") {
    return record.progress_hint || "In progress";
  }
  return "Not started";
}

function SkillRow({ record, onOpenEvidence }) {
  const navigate = useNavigate();
  const dimmed = record.state === "unseen";
  const hasLesson = !!record.lesson_url;
  const showEvidence = record.state === "studied" || record.state === "stale";

  const goToLesson = (e) => {
    e.stopPropagation();
    if (record.lesson_url) navigate(record.lesson_url);
  };
  const openEvidence = (e) => {
    e.stopPropagation();
    onOpenEvidence(record);
  };

  return (
    <div
      className={`grid grid-cols-[auto_1fr_auto_auto] gap-3 items-center py-2.5 border-b border-border/30 last:border-b-0 ${
        dimmed ? "opacity-60" : ""
      }`}
    >
      <div className="w-4 flex items-center justify-center">
        <StateIcon state={record.state} />
      </div>
      <div className="min-w-0">
        <div className="font-serif text-[14.5px] text-foreground leading-snug truncate">
          {record.label}
        </div>
        <div className="text-[11px] text-muted-foreground mt-0.5 leading-snug">
          {meta(record)}
        </div>
      </div>
      <div className="flex items-center gap-2">
        {showEvidence && (
          <button
            onClick={openEvidence}
            className="text-[11px] text-muted-foreground hover:text-violet-500 dark:hover:text-violet-300 transition-colors"
            title="See why we credited you"
          >
            why?
          </button>
        )}
        {hasLesson && (
          <button
            onClick={goToLesson}
            className="text-[11px] text-violet-500 hover:text-violet-400 transition-colors inline-flex items-center gap-1"
          >
            Study <ArrowRight className="h-3 w-3" strokeWidth={2} />
          </button>
        )}
      </div>
      {record.tier > 0 && (
        <span className="text-[10px] text-muted-foreground/60 font-mono tabular-nums">
          T{record.tier}
        </span>
      )}
    </div>
  );
}

function EvidenceModal({ skill, onClose, onDemote }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!skill) return;
    setLoading(true);
    fetch(`${API}/engine2/skill-evidence/${skill.skill_id}`, {
      credentials: "include",
    })
      .then((r) => r.json())
      .then((j) => setData(j))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [skill]);

  if (!skill) return null;

  return (
    <div
      className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-6"
      onClick={onClose}
    >
      <div
        className="bg-background border border-border rounded-2xl max-w-lg w-full max-h-[80vh] overflow-auto p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-5">
          <div>
            <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold">
              Why we credited you
            </div>
            <h3 className="font-serif text-[20px] text-foreground mt-1">
              {skill.label}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 text-[12px] text-muted-foreground py-6">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading evidence…
          </div>
        ) : (
          <>
            {(!data || !data.evidence || data.evidence.length === 0) ? (
              <p className="text-[13px] text-muted-foreground">
                No detailed evidence recorded yet. The skill graduated
                via lesson completion or older data without per-move
                provenance.
              </p>
            ) : (
              <ul className="space-y-3 mb-5">
                {data.evidence.map((ev, i) => (
                  <li
                    key={i}
                    className="rounded-lg border border-border/50 p-3 text-[12.5px]"
                  >
                    <div className="flex items-baseline justify-between gap-3">
                      <div className="font-mono text-foreground">
                        {ev.move_san
                          ? `${ev.move_san} on move ${ev.move_number ?? "?"}`
                          : ev.source === "lesson_completion"
                            ? `Lesson: ${ev.lesson_ref ?? "completed"}`
                            : ev.source === "user_demotion"
                              ? "You said: 'I don't get this yet'"
                              : ev.source}
                      </div>
                      <span
                        className={`text-[10.5px] font-semibold ${
                          ev.outcome === "applied" || ev.outcome === "correct"
                            ? "text-emerald-500"
                            : ev.outcome === "wrong"
                              ? "text-amber-500"
                              : "text-muted-foreground"
                        }`}
                      >
                        {ev.outcome}
                      </span>
                    </div>
                    {ev.game && (
                      <div className="text-[11px] text-muted-foreground mt-1">
                        {ev.game.opening_name || ev.game.platform || "Game"}
                        {ev.game.date_played ? ` · ${ev.game.date_played}` : ""}
                        {ev.game.result ? ` · ${ev.game.result}` : ""}
                      </div>
                    )}
                    {ev.fen_before && (
                      <div className="text-[10px] font-mono text-muted-foreground/70 mt-1 truncate">
                        FEN: {ev.fen_before}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}

            <div className="border-t border-border/50 pt-4 flex flex-col gap-3">
              <p className="text-[12px] text-muted-foreground leading-relaxed">
                Do you actually get this, or did the right move happen for
                another reason? If you don't really see it yet, drop the
                credit and we'll re-teach.
              </p>
              <div className="flex gap-2">
                <button
                  onClick={onClose}
                  className="flex-1 h-9 rounded-lg bg-violet-500 hover:bg-violet-400 text-white text-[13px] font-medium transition-colors"
                >
                  Yes, I get it
                </button>
                <button
                  onClick={() => onDemote(skill.skill_id)}
                  className="flex-1 h-9 rounded-lg border border-border text-foreground hover:bg-muted text-[13px] font-medium transition-colors"
                >
                  Not really — re-teach me
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}


function KindSection({ kind, records, onOpenEvidence }) {
  if (!records || records.length === 0) return null;

  const counts = records.reduce(
    (acc, r) => {
      acc[r.state] = (acc[r.state] || 0) + 1;
      return acc;
    },
    { studied: 0, learning: 0, stale: 0, unseen: 0 }
  );

  const summary = [
    counts.studied && `${counts.studied} studied`,
    counts.learning && `${counts.learning} in progress`,
    counts.stale && `${counts.stale} to refresh`,
    counts.unseen && `${counts.unseen} to explore`,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="mb-8">
      <div className="flex items-baseline justify-between mb-3">
        <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold">
          {KIND_TITLE[kind] || kind}
        </div>
        <div className="text-[10.5px] text-muted-foreground/70 tabular-nums">
          {summary}
        </div>
      </div>
      <div>
        {records.map((r) => (
          <SkillRow
            key={r.skill_id}
            record={r}
            onOpenEvidence={onOpenEvidence}
          />
        ))}
      </div>
    </div>
  );
}

export default function MasteryPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [evidenceSkill, setEvidenceSkill] = useState(null);

  const refreshMastery = async () => {
    try {
      const res = await fetch(`${API}/engine2/mastery-summary`, {
        credentials: "include",
      });
      if (res.ok) setData(await res.json());
    } catch {}
  };

  const handleDemote = async (skillId) => {
    try {
      await fetch(`${API}/engine2/skill-demote`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ skill_id: skillId, outcome: "wrong" }),
      });
      setEvidenceSkill(null);
      await refreshMastery();
    } catch {
      setEvidenceSkill(null);
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API}/engine2/mastery-summary`, {
          credentials: "include",
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!cancelled) setData(json);
      } catch (e) {
        if (!cancelled) setError(e.message || "Failed to load");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-[12px] text-muted-foreground py-6">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading what you've learned…
      </div>
    );
  }

  if (error || !data) {
    return null;
  }

  const { summary, by_kind } = data;
  const hasAnyActivity =
    summary.studied + summary.learning + summary.stale > 0;

  return (
    <section className="mb-16 md:mb-20" data-testid="mastery-panel">
      <div className="flex items-baseline justify-between mb-5 flex-wrap gap-2">
        <div className="text-[10.5px] uppercase tracking-[0.22em] text-emerald-600 dark:text-emerald-400 font-semibold">
          Skills · what you've studied
        </div>
        <div className="text-[11px] text-muted-foreground tabular-nums">
          {summary.studied} of {summary.total_skills} studied
          {summary.stale > 0 && ` · ${summary.stale} to refresh`}
        </div>
      </div>

      {!hasAnyActivity ? (
        <div className="rounded-2xl border border-border/40 p-6 text-[13px] text-muted-foreground leading-relaxed">
          You haven't worked through any lessons yet. Open a trap, an
          endgame, or a coached game and the skills you pick up will show
          up here.
        </div>
      ) : (
        <div className="rounded-2xl border border-border/40 bg-gradient-to-b from-emerald-500/[0.02] to-transparent p-6 md:p-7">
          {KIND_ORDER.map((kind) => (
            <KindSection
              key={kind}
              kind={kind}
              records={by_kind[kind] || []}
              onOpenEvidence={setEvidenceSkill}
            />
          ))}
        </div>
      )}
      <EvidenceModal
        skill={evidenceSkill}
        onClose={() => setEvidenceSkill(null)}
        onDemote={handleDemote}
      />
    </section>
  );
}
