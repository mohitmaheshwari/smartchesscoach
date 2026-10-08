/**
 * MasteryPanel — Table-based Studio Syllabus & Skill Matrix.
 *
 * Provides a structured, high-contrast, filterable data table for all 77+ Engine 2
 * chess skills across Openings, Concepts, Endgames, Mate Patterns, Traps, and Coached Play.
 *
 * Openings are prioritized first so users establish an opening foundation.
 * Other topics require completing an opening first to unlock.
 *
 * Reads GET /api/engine2/mastery-summary — four-state roll-up:
 * studied | learning | stale | unseen | demonstrated.
 */

import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";
import {
  Check,
  RotateCcw,
  Circle,
  Loader2,
  ArrowRight,
  X,
  ExternalLink,
  Search,
  Sparkles,
  BookOpen,
  Shield,
  Target,
  Swords,
  Layers,
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
  ChevronLeft,
  ChevronRight,
  Lock,
  Unlock,
  AlertCircle
} from "lucide-react";
import LichessBoard from "@/components/LichessBoard";

const KIND_TITLE = {
  opening: "Openings",
  concept: "Concepts",
  endgame: "Endgames",
  mate_pattern: "Mate Patterns",
  trap_set: "Traps",
  coached_play: "Coached Play",
};

const KIND_ICONS = {
  opening: BookOpen,
  concept: Shield,
  endgame: Target,
  mate_pattern: Sparkles,
  trap_set: Swords,
  coached_play: Layers,
};

// Openings are first in order
const KIND_ORDER = [
  "opening",
  "concept",
  "endgame",
  "mate_pattern",
  "trap_set",
  "coached_play",
];

const DRILLABLE_SKILLS = new Set([
  "endgame_rule_of_square",
  "defend_scholars_mate",
  "mate_kq_vs_k",
  "mate_kr_vs_k",
  "defend_fried_liver",
  "endgame_opposition",
  "endgame_lucena",
  "endgame_philidor",
]);

function StateBadge({ state, demonstrated_slipping, isLocked }) {
  if (isLocked) {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold uppercase tracking-wider bg-slate-900/95 border border-slate-700/80 text-amber-300 shadow-[0_0_10px_rgba(245,158,11,0.15)]">
        <Lock className="h-3 w-3 text-amber-400" />
        <span>Locked</span>
      </span>
    );
  }
  if (state === "studied") {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold uppercase tracking-wider bg-emerald-950/90 border border-emerald-500/50 text-emerald-300 shadow-[0_0_12px_rgba(16,185,129,0.25)]">
        <Check className="h-3.5 w-3.5 text-emerald-400" strokeWidth={3} />
        <span>Studied</span>
      </span>
    );
  }
  if (state === "demonstrated") {
    return demonstrated_slipping ? (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold uppercase tracking-wider bg-amber-950/90 border border-amber-500/50 text-amber-300 shadow-[0_0_12px_rgba(245,158,11,0.25)]">
        <RotateCcw className="h-3.5 w-3.5 text-amber-400" strokeWidth={2.5} />
        <span>Recent Slip</span>
      </span>
    ) : (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold uppercase tracking-wider bg-cyan-950/90 border border-cyan-500/50 text-cyan-300 shadow-[0_0_12px_rgba(56,189,248,0.25)]">
        <Sparkles className="h-3.5 w-3.5 text-cyan-400" />
        <span>Demonstrated</span>
      </span>
    );
  }
  if (state === "stale") {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold uppercase tracking-wider bg-amber-950/90 border border-amber-500/50 text-amber-300 shadow-[0_0_12px_rgba(245,158,11,0.25)]">
        <RotateCcw className="h-3.5 w-3.5 text-amber-400" strokeWidth={2.5} />
        <span>To Refresh</span>
      </span>
    );
  }
  if (state === "learning") {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold uppercase tracking-wider bg-violet-950/90 border border-violet-500/50 text-violet-300 shadow-[0_0_12px_rgba(139,92,246,0.25)]">
        <Circle className="h-2.5 w-2.5 text-violet-400 fill-violet-400 animate-pulse" />
        <span>In Progress</span>
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-semibold uppercase tracking-wider bg-white/5 border border-white/10 text-slate-400">
      <Circle className="h-2.5 w-2.5 text-slate-500" strokeWidth={2} />
      <span>Not Started</span>
    </span>
  );
}

function meta(record, isLocked) {
  if (isLocked) {
    return "Complete Opening to unlock";
  }
  if (record.state === "studied") {
    const d = record.days_since_studied;
    if (d == null) return "Just studied";
    if (d === 0) return "Studied today";
    if (d === 1) return "Studied yesterday";
    return `Studied ${d} days ago`;
  }
  if (record.state === "demonstrated") {
    return record.progress_hint || "Demonstrated in your games";
  }
  if (record.state === "stale") {
    const d = record.days_since_studied;
    return d != null
      ? `Worth a refresher · ${d}d since clean`
      : "Worth a refresher";
  }
  if (record.state === "learning") {
    return record.progress_hint || "In active training";
  }
  return "Ready to explore";
}

/**
 * Modal shown when user tries to access a locked skill before completing an opening
 */
function PrerequisiteModal({ skill, suggestedOpening, onClose, onGoToOpening, onFilterOpenings }) {
  if (!skill) return null;

  return (
    <div
      className="fixed inset-0 bg-black/85 backdrop-blur-md z-50 flex items-center justify-center p-4 sm:p-6 animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="bg-gradient-to-b from-[#1b2633] via-[#131d27] to-[#0b1118] border border-amber-500/40 rounded-3xl max-w-lg w-full p-6 sm:p-8 shadow-2xl text-white backdrop-blur-2xl relative overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="absolute top-0 right-0 w-64 h-64 bg-amber-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="flex items-start justify-between mb-5 pb-4 border-b border-white/10 relative z-10">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-2xl bg-amber-500/20 border border-amber-500/40 text-amber-300">
              <Lock className="h-6 w-6" />
            </div>
            <div>
              <div className="text-xs font-mono uppercase tracking-[0.22em] text-amber-400 font-bold">
                Prerequisite Required
              </div>
              <h3 className="font-heading font-extrabold text-xl sm:text-2xl text-white mt-0.5">
                Complete Opening First
              </h3>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white hover:bg-white/10 rounded-full transition-colors cursor-pointer"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4 mb-6 relative z-10">
          <div className="p-3.5 rounded-2xl bg-white/[0.04] border border-white/10">
            <div className="text-xs font-mono text-slate-400 uppercase tracking-wider mb-1">Target Skill</div>
            <div className="font-heading font-bold text-base text-white">{skill.label}</div>
            <div className="text-xs text-slate-400 mt-0.5">{KIND_TITLE[skill.kind] || skill.kind}</div>
          </div>

          <p className="text-sm text-slate-300 leading-relaxed font-medium">
            You must first complete your opening foundation (such as{" "}
            <strong className="text-cyan-300 font-bold">{suggestedOpening?.label || "London System"}</strong>
            ) before unlocking this topic.
          </p>

          <div className="p-3.5 rounded-2xl bg-amber-950/40 border border-amber-500/30 flex items-start gap-2.5">
            <AlertCircle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
            <p className="text-xs text-amber-200/90 leading-relaxed font-mono">
              Once you finish this opening lesson, all advanced concepts, tactics, and endgames will unlock automatically!
            </p>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 relative z-10">
          <button
            type="button"
            onClick={() => {
              onClose();
              onGoToOpening(suggestedOpening);
            }}
            className="flex-1 py-3 px-4 rounded-2xl bg-gradient-to-r from-cyan-400 via-cyan-500 to-blue-600 hover:from-cyan-300 hover:to-blue-500 text-slate-950 font-heading font-extrabold text-xs uppercase tracking-wider transition-all inline-flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(56,189,248,0.35)] cursor-pointer"
          >
            <BookOpen className="h-4 w-4" />
            <span>Start Opening: {suggestedOpening?.label || "London System"}</span>
            <ArrowRight className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => {
              onClose();
              onFilterOpenings();
            }}
            className="py-3 px-4 rounded-2xl bg-white/10 hover:bg-white/20 border border-white/20 text-white font-heading font-bold text-xs uppercase tracking-wider transition-all cursor-pointer whitespace-nowrap"
          >
            View All Openings
          </button>
        </div>
      </div>
    </div>
  );
}

function EvidenceModal({ skill, onClose, onDemote }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const isConceptEvidence = Boolean(skill?.mapped_concept_id);

  useEffect(() => {
    if (!skill) return;
    setLoading(true);
    const url = isConceptEvidence
      ? `${API}/coach/concepts/evidence/${skill.mapped_concept_id}`
      : `${API}/engine2/skill-evidence/${skill.skill_id}`;
    fetch(url, { credentials: "include" })
      .then((r) => r.json())
      .then((j) => {
        if (isConceptEvidence && j && Array.isArray(j.evidence)) {
          const OUTCOME_MAP = { clean: "applied", violated: "wrong" };
          const normalized = j.evidence.map((ev) => ({
            ...ev,
            outcome: OUTCOME_MAP[ev.outcome] || ev.outcome,
            game: {
              opening_name: ev.opening_name,
              date_played: ev.date_played,
              platform: ev.platform,
              result: ev.result,
            },
          }));
          setData({ ...j, evidence: normalized });
        } else {
          setData(j);
        }
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [skill, isConceptEvidence]);

  if (!skill) return null;

  const openEvidenceInGame = (ev) => {
    if (!ev?.game_id) return;
    const moveQuery = ev.move_number != null ? `?move=${ev.move_number}` : "";
    navigate(`/game/${ev.game_id}${moveQuery}`);
    onClose();
  };

  return (
    <div
      className="fixed inset-0 bg-black/85 backdrop-blur-md z-50 flex items-center justify-center p-4 sm:p-6 animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="bg-gradient-to-b from-[#1b2633] via-[#131d27] to-[#0b1118] border border-white/20 rounded-3xl max-w-xl w-full max-h-[85vh] overflow-auto p-6 sm:p-8 shadow-2xl text-white backdrop-blur-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-6 pb-4 border-b border-white/10">
          <div>
            <div className="text-xs font-mono uppercase tracking-[0.22em] text-cyan-400 font-bold">
              Skill Evidence & Verification
            </div>
            <h3 className="font-heading font-extrabold text-2xl text-white mt-1">
              {skill.label}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white hover:bg-white/10 rounded-full transition-colors cursor-pointer"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center gap-3 text-sm text-cyan-300 py-12 font-mono">
            <Loader2 className="h-5 w-5 animate-spin text-cyan-400" /> Loading in-game evidence…
          </div>
        ) : (
          <>
            {(!data || !data.evidence || data.evidence.length === 0) ? (
              <div className="rounded-2xl bg-white/5 border border-white/10 p-6 text-sm text-slate-300 leading-relaxed text-center mb-6">
                No individual game moves recorded yet. This skill was credited through guided lesson completion.
              </div>
            ) : (
              <ul className="space-y-3.5 mb-6">
                {data.evidence.map((ev, i) => {
                  const isGameEvidence = Boolean(
                    ev.move_san && ev.fen_before && ev.game_id
                  );
                  const headline = ev.move_san
                    ? `${ev.move_san} on move ${ev.move_number ?? "?"}`
                    : ev.source === "lesson_completion"
                      ? `Lesson: ${ev.lesson_ref ?? "completed"}`
                      : ev.source === "user_demotion"
                        ? "You said: 'I don't get this yet'"
                        : ev.source;

                  return (
                    <li
                      key={i}
                      className={`rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm ${
                        isGameEvidence
                          ? "cursor-pointer hover:border-cyan-400/50 hover:bg-cyan-500/[0.05] transition-all"
                          : ""
                      }`}
                      onClick={
                        isGameEvidence
                          ? () => openEvidenceInGame(ev)
                          : undefined
                      }
                    >
                      <div className="flex items-baseline justify-between gap-3">
                        <div className="font-mono font-bold text-white flex items-center gap-2">
                          {headline}
                          {isGameEvidence && (
                            <ExternalLink className="h-3.5 w-3.5 text-cyan-400" />
                          )}
                        </div>
                        <span
                          className={`text-xs font-mono font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full ${
                            ev.outcome === "applied" || ev.outcome === "correct"
                              ? "bg-emerald-950/80 border border-emerald-500/40 text-emerald-300"
                              : ev.outcome === "wrong"
                                ? "bg-amber-950/80 border border-amber-500/40 text-amber-300"
                                : "bg-white/10 text-slate-300"
                          }`}
                        >
                          {ev.outcome}
                        </span>
                      </div>
                      {ev.game && (
                        <div className="text-xs text-slate-400 mt-1 font-medium">
                          {ev.game.opening_name || ev.game.platform || "Game"}
                          {ev.game.date_played ? ` · ${ev.game.date_played}` : ""}
                          {ev.game.result ? ` · ${ev.game.result}` : ""}
                        </div>
                      )}
                      {isGameEvidence && (
                        <div className="mt-3 flex gap-4 items-center">
                          <div
                            className="w-[110px] h-[110px] flex-none rounded-xl overflow-hidden border border-white/20 shadow-md"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <LichessBoard
                              fen={ev.fen_before}
                              viewOnly={true}
                              interactive={false}
                            />
                          </div>
                          <div className="flex-1 text-xs text-slate-300 leading-relaxed">
                            Click to open this game in analysis and inspect this exact board state.
                          </div>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}

            {DRILLABLE_SKILLS.has(skill.skill_id) && (
              <div className="border-t border-white/10 pt-5 mb-5">
                <button
                  onClick={() => {
                    onClose();
                    navigate(`/training/skill/${skill.skill_id}`);
                  }}
                  className="w-full py-3.5 rounded-2xl bg-gradient-to-r from-cyan-400 via-cyan-500 to-blue-600 hover:from-cyan-300 hover:to-blue-500 text-slate-950 text-sm font-heading font-extrabold uppercase tracking-wider transition-all inline-flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(56,189,248,0.4)] cursor-pointer"
                >
                  <Sparkles className="h-4 w-4" />
                  <span>Drill These Positions</span>
                  <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            )}

            <div className="border-t border-white/10 pt-5 flex flex-col gap-3">
              <p className="text-xs text-slate-400 leading-relaxed font-medium">
                Do you fully understand this concept, or did this occur by chance? You can request to re-learn it anytime.
              </p>
              <div className="flex gap-3">
                <button
                  onClick={onClose}
                  className="flex-1 py-2.5 rounded-xl bg-white/10 hover:bg-white/20 border border-white/20 text-white text-xs font-heading font-bold uppercase tracking-wider transition-all cursor-pointer"
                >
                  Yes, I Understand
                </button>
                <button
                  onClick={() =>
                    onDemote(
                      isConceptEvidence
                        ? { conceptId: skill.mapped_concept_id }
                        : { skillId: skill.skill_id }
                    )
                  }
                  className="flex-1 py-2.5 rounded-xl bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/40 text-amber-300 text-xs font-heading font-bold uppercase tracking-wider transition-all cursor-pointer"
                >
                  Not Yet — Re-teach Me
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function MasteryPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [evidenceSkill, setEvidenceSkill] = useState(null);
  const [lockedModalSkill, setLockedModalSkill] = useState(null);
  const [selectedKind, setSelectedKind] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortField, setSortField] = useState("default");
  const [sortOrder, setSortOrder] = useState("asc"); // "asc" | "desc"
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(15);
  const navigate = useNavigate();

  const refreshMastery = async () => {
    try {
      const res = await fetch(`${API}/engine2/mastery-summary`, {
        credentials: "include",
      });
      if (res.ok) setData(await res.json());
    } catch {}
  };

  const handleDemote = async (target) => {
    try {
      if (target && target.conceptId) {
        await fetch(`${API}/coach/concepts/demote/${target.conceptId}`, {
          method: "POST",
          credentials: "include",
        });
      } else if (target && target.skillId) {
        await fetch(`${API}/engine2/skill-demote`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ skill_id: target.skillId, outcome: "wrong" }),
        });
      }
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

  // Reset page to 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [selectedKind, statusFilter, searchQuery, pageSize]);

  // Flatten all skill records with Openings first
  const allRecords = useMemo(() => {
    if (!data?.by_kind) return [];
    const list = [];
    KIND_ORDER.forEach((kind) => {
      const items = data.by_kind[kind] || [];
      items.forEach((item) => {
        list.push({ ...item, kind });
      });
    });
    return list;
  }, [data]);

  // Check if the user has completed/studied any opening
  const hasStudiedOpening = useMemo(() => {
    return allRecords.some(
      (r) => r.kind === "opening" && (r.state === "studied" || r.state === "demonstrated")
    );
  }, [allRecords]);

  // Suggested opening to study first
  const suggestedOpening = useMemo(() => {
    return (
      allRecords.find((r) => r.kind === "opening" && r.lesson_url) ||
      allRecords.find((r) => r.kind === "opening") || {
        label: "London System (White)",
        lesson_url: "/openings/london_system",
      }
    );
  }, [allRecords]);

  // Filter records
  const filteredRecords = useMemo(() => {
    return allRecords.filter((r) => {
      if (selectedKind !== "all" && r.kind !== selectedKind) return false;
      if (statusFilter !== "all" && r.state !== statusFilter) return false;
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchesLabel = r.label?.toLowerCase().includes(query);
        const matchesKind = KIND_TITLE[r.kind]?.toLowerCase().includes(query);
        const matchesReason = r.reason?.toLowerCase().includes(query);
        if (!matchesLabel && !matchesKind && !matchesReason) return false;
      }
      return true;
    });
  }, [allRecords, selectedKind, statusFilter, searchQuery]);

  // Sort records
  const sortedRecords = useMemo(() => {
    const records = [...filteredRecords];
    if (sortField === "default") return records;

    const STATE_WEIGHTS = { studied: 4, demonstrated: 3, learning: 2, stale: 1, unseen: 0 };

    records.sort((a, b) => {
      let comparison = 0;
      if (sortField === "label") {
        comparison = (a.label || "").localeCompare(b.label || "");
      } else if (sortField === "category") {
        comparison = (KIND_TITLE[a.kind] || a.kind).localeCompare(KIND_TITLE[b.kind] || b.kind);
      } else if (sortField === "tier") {
        comparison = (a.tier || 0) - (b.tier || 0);
      } else if (sortField === "status") {
        comparison = (STATE_WEIGHTS[a.state] || 0) - (STATE_WEIGHTS[b.state] || 0);
      }
      return sortOrder === "asc" ? comparison : -comparison;
    });

    return records;
  }, [filteredRecords, sortField, sortOrder]);

  // Paginated records
  const totalPages = Math.ceil(sortedRecords.length / pageSize) || 1;
  const paginatedRecords = useMemo(() => {
    if (pageSize === 0) return sortedRecords; // Show all
    const start = (currentPage - 1) * pageSize;
    return sortedRecords.slice(start, start + pageSize);
  }, [sortedRecords, currentPage, pageSize]);

  // Counts per category
  const categoryCounts = useMemo(() => {
    const counts = { all: allRecords.length };
    KIND_ORDER.forEach((k) => {
      counts[k] = (data?.by_kind?.[k] || []).length;
    });
    return counts;
  }, [allRecords, data]);

  const handleSort = (field) => {
    if (sortField === field) {
      if (sortOrder === "asc") {
        setSortOrder("desc");
      } else {
        setSortField("default");
        setSortOrder("asc");
      }
    } else {
      setSortField(field);
      setSortOrder("asc");
    }
  };

  const clearFilters = () => {
    setSelectedKind("all");
    setStatusFilter("all");
    setSearchQuery("");
    setSortField("default");
    setCurrentPage(1);
  };

  const handleGoToOpening = (op) => {
    if (op?.lesson_url) {
      navigate(op.lesson_url);
    } else {
      setSelectedKind("opening");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-3 text-sm text-cyan-300 py-16 font-mono bg-gradient-to-b from-[#1c2938]/80 to-[#131d27]/90 rounded-3xl border border-white/10">
        <Loader2 className="h-5 w-5 animate-spin text-cyan-400" />
        <span>Loading your complete chess syllabus…</span>
      </div>
    );
  }

  if (error || !data) {
    return null;
  }

  const { summary } = data;
  const studiedTotal = summary.studied || 0;
  const totalSkills = summary.total_skills || allRecords.length || 77;
  const progressPercent = Math.min(100, Math.round((studiedTotal / (totalSkills || 1)) * 100));

  return (
    <section className="mb-16 md:mb-20" data-testid="mastery-panel">
      {/* ─── Top Header & Summary ─── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-cyan-950/80 border border-cyan-500/40 text-xs font-mono font-bold uppercase tracking-wider text-cyan-300 mb-2 shadow-[0_0_15px_rgba(56,189,248,0.25)]">
            <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
            Skills & Curriculum Matrix
          </div>
          <h2 className="font-heading font-extrabold text-2xl sm:text-3xl text-white tracking-tight">
            What You've Studied & Mastered
          </h2>
          <p className="text-xs sm:text-sm text-slate-400 font-medium mt-1">
            Complete syllabus covering Openings, Concepts, Endgames, Mate Patterns, and Traps.
          </p>
        </div>

        {/* Global Progress Pill */}
        <div className="flex items-center gap-4 bg-gradient-to-r from-[#18232e] to-[#111922] p-4 rounded-2xl border border-white/15 shadow-xl">
          <div className="space-y-1.5 min-w-[150px]">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-slate-400 font-bold uppercase tracking-wider">Overall Progress</span>
              <span className="font-extrabold text-cyan-300">{studiedTotal}/{totalSkills}</span>
            </div>
            <div className="w-full h-2.5 rounded-full bg-white/10 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-cyan-400 via-cyan-500 to-blue-600 shadow-[0_0_12px_rgba(56,189,248,0.6)] transition-all duration-500"
                style={{ width: `${Math.max(5, progressPercent)}%` }}
              />
            </div>
          </div>
          <div className="text-2xl font-heading font-black text-cyan-400 font-mono tracking-tight">
            {progressPercent}%
          </div>
        </div>
      </div>

      {/* ─── Master Table Card ─── */}
      <div className="rounded-3xl border border-white/15 bg-gradient-to-b from-[#1b2633] via-[#131d27] to-[#0b1118] p-5 sm:p-7 shadow-[0_20px_50px_rgba(0,0,0,0.7)] backdrop-blur-2xl">
        {/* ─── Prerequisite Notice Banner (when opening not studied yet) ─── */}
        {!hasStudiedOpening && (
          <div className="mb-6 p-4 rounded-2xl bg-gradient-to-r from-amber-950/60 via-[#231a12]/80 to-[#1b1f28]/90 border border-amber-500/40 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-[0_0_20px_rgba(245,158,11,0.15)]">
            <div className="flex items-center gap-3.5">
              <div className="p-2.5 rounded-2xl bg-amber-500/20 border border-amber-500/40 text-amber-300 shrink-0">
                <BookOpen className="h-5 w-5" />
              </div>
              <div>
                <div className="font-heading font-extrabold text-white text-sm tracking-tight flex items-center gap-2">
                  <span>Openings Are Unlocked First</span>
                  <span className="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 text-[10px] font-mono font-bold uppercase tracking-wider">
                    Step 1
                  </span>
                </div>
                <div className="text-slate-300 text-xs mt-0.5 leading-relaxed font-medium">
                  Study an Opening lesson (e.g. <strong className="text-cyan-300">{suggestedOpening.label}</strong>) to unlock all advanced Concepts, Endgames, and Traps.
                </div>
              </div>
            </div>
            <button
              type="button"
              onClick={() => handleGoToOpening(suggestedOpening)}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-400 via-cyan-500 to-blue-600 hover:from-cyan-300 hover:to-blue-500 text-slate-950 font-heading font-extrabold text-xs uppercase tracking-wider transition-all inline-flex items-center gap-2 shadow-[0_0_15px_rgba(56,189,248,0.35)] cursor-pointer shrink-0 self-end sm:self-center"
            >
              <span>Start Opening Lesson</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {/* ─── Category Filter Tabs (Openings First) ─── */}
        <div className="flex items-center gap-2 overflow-x-auto pb-3 mb-5 border-b border-white/10 scrollbar-none">
          <button
            type="button"
            onClick={() => setSelectedKind("all")}
            className={`px-4 py-2.5 rounded-xl text-xs font-heading font-extrabold uppercase tracking-wider transition-all whitespace-nowrap cursor-pointer flex items-center gap-2 ${
              selectedKind === "all"
                ? "bg-gradient-to-r from-cyan-400 to-cyan-500 text-slate-950 shadow-[0_0_15px_rgba(56,189,248,0.4)]"
                : "bg-white/5 hover:bg-white/10 text-slate-300 border border-white/10"
            }`}
          >
            <span>All Topics</span>
            <span className={`text-[10px] px-1.5 py-0.5 rounded-md font-mono font-bold ${
              selectedKind === "all" ? "bg-slate-950/40 text-slate-950" : "bg-white/10 text-slate-400"
            }`}>
              {categoryCounts.all}
            </span>
          </button>

          {KIND_ORDER.map((kind) => {
            const Icon = KIND_ICONS[kind] || Layers;
            const isSelected = selectedKind === kind;
            return (
              <button
                key={kind}
                type="button"
                onClick={() => setSelectedKind(kind)}
                className={`px-3.5 py-2.5 rounded-xl text-xs font-heading font-extrabold uppercase tracking-wider transition-all whitespace-nowrap cursor-pointer flex items-center gap-2 ${
                  isSelected
                    ? "bg-gradient-to-r from-cyan-400 to-cyan-500 text-slate-950 shadow-[0_0_15px_rgba(56,189,248,0.4)]"
                    : "bg-white/5 hover:bg-white/10 text-slate-300 border border-white/10"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{KIND_TITLE[kind]}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded-md font-mono font-bold ${
                  isSelected ? "bg-slate-950/40 text-slate-950" : "bg-white/10 text-slate-400"
                }`}>
                  {categoryCounts[kind] || 0}
                </span>
              </button>
            );
          })}
        </div>

        {/* ─── Search, State Filters & Controls ─── */}
        <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-4 mb-6">
          {/* Search Box */}
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by topic, skill name, or concept…"
              className="w-full pl-10 pr-9 py-2.5 rounded-xl bg-white/[0.04] border border-white/15 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/60 transition-colors font-medium shadow-inner"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* State Filter Buttons */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 lg:pb-0 scrollbar-none">
            {[
              { id: "all", label: "All States" },
              { id: "studied", label: "Studied" },
              { id: "learning", label: "In Progress" },
              { id: "stale", label: "Needs Refresh" },
              { id: "unseen", label: "To Explore" },
            ].map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => setStatusFilter(f.id)}
                className={`px-3 py-1.5 rounded-xl text-xs font-mono font-bold transition-all whitespace-nowrap cursor-pointer ${
                  statusFilter === f.id
                    ? "bg-cyan-950/90 text-cyan-300 border border-cyan-500/50 shadow-[0_0_10px_rgba(56,189,248,0.2)]"
                    : "text-slate-400 hover:text-white hover:bg-white/5 border border-transparent"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Active Filter Clear */}
          {(selectedKind !== "all" || statusFilter !== "all" || searchQuery || sortField !== "default") && (
            <button
              type="button"
              onClick={clearFilters}
              className="inline-flex items-center gap-1.5 text-xs font-mono text-cyan-400 hover:text-cyan-300 transition-colors cursor-pointer self-start lg:self-center"
            >
              <X className="h-3.5 w-3.5" />
              <span>Reset Filters</span>
            </button>
          )}
        </div>

        {/* ─── Table View ─── */}
        {sortedRecords.length === 0 ? (
          <div className="py-16 text-center text-slate-400 border border-white/10 rounded-2xl bg-white/[0.02]">
            <Search className="h-8 w-8 mx-auto mb-3 text-slate-500" />
            <p className="font-heading font-extrabold text-lg text-white mb-1">No matching skills found</p>
            <p className="text-xs mb-4">Try clearing your filters or changing your search query.</p>
            <button
              onClick={clearFilters}
              className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-xs font-mono font-bold text-white transition-all cursor-pointer"
            >
              Reset All Filters
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-2xl border border-white/15 bg-black/30 shadow-inner">
            <table className="w-full text-left border-collapse min-w-[760px]">
              <thead>
                <tr className="border-b border-white/15 bg-white/[0.04] text-[11px] font-mono uppercase tracking-[0.2em] text-cyan-400/90">
                  {/* Status Header */}
                  <th
                    className="py-4 px-5 font-bold cursor-pointer select-none hover:text-cyan-300 transition-colors"
                    onClick={() => handleSort("status")}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Status</span>
                      {sortField === "status" ? (
                        sortOrder === "asc" ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />
                      ) : (
                        <ChevronsUpDown className="h-3.5 w-3.5 opacity-40" />
                      )}
                    </div>
                  </th>

                  {/* Skill Topic Header */}
                  <th
                    className="py-4 px-5 font-bold cursor-pointer select-none hover:text-cyan-300 transition-colors"
                    onClick={() => handleSort("label")}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Skill / Curriculum Topic</span>
                      {sortField === "label" ? (
                        sortOrder === "asc" ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />
                      ) : (
                        <ChevronsUpDown className="h-3.5 w-3.5 opacity-40" />
                      )}
                    </div>
                  </th>

                  {/* Category Header */}
                  <th
                    className="py-4 px-4 font-bold cursor-pointer select-none hover:text-cyan-300 transition-colors"
                    onClick={() => handleSort("category")}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Category</span>
                      {sortField === "category" ? (
                        sortOrder === "asc" ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />
                      ) : (
                        <ChevronsUpDown className="h-3.5 w-3.5 opacity-40" />
                      )}
                    </div>
                  </th>

                  {/* Tier Header */}
                  <th
                    className="py-4 px-4 font-bold cursor-pointer select-none hover:text-cyan-300 transition-colors"
                    onClick={() => handleSort("tier")}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Tier</span>
                      {sortField === "tier" ? (
                        sortOrder === "asc" ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />
                      ) : (
                        <ChevronsUpDown className="h-3.5 w-3.5 opacity-40" />
                      )}
                    </div>
                  </th>

                  {/* Progress Header */}
                  <th className="py-4 px-5 font-bold">
                    <span>Progress & Record</span>
                  </th>

                  {/* Action Header */}
                  <th className="py-4 px-5 font-bold text-right">
                    <span>Action</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-sm">
                {paginatedRecords.map((record) => {
                  const isOpening = record.kind === "opening";
                  // Non-openings are locked if user has not studied any opening yet
                  const isLocked =
                    !isOpening &&
                    !hasStudiedOpening &&
                    record.state !== "studied" &&
                    record.state !== "demonstrated";

                  const hasLesson = Boolean(record.lesson_url);
                  const showEvidence =
                    !isLocked &&
                    (record.state === "studied" ||
                      record.state === "stale" ||
                      record.state === "demonstrated");
                  const hideStudyButton = record.state === "demonstrated";
                  const isDrillable = DRILLABLE_SKILLS.has(record.skill_id);

                  return (
                    <tr
                      key={record.skill_id}
                      onClick={() => {
                        if (isLocked) setLockedModalSkill(record);
                      }}
                      className={`transition-colors group ${
                        isLocked
                          ? "hover:bg-amber-500/[0.04] cursor-pointer opacity-85"
                          : "hover:bg-white/[0.05]"
                      }`}
                    >
                      {/* Status Column */}
                      <td className="py-4 px-5 whitespace-nowrap">
                        <StateBadge
                          state={record.state}
                          demonstrated_slipping={record.demonstrated_slipping}
                          isLocked={isLocked}
                        />
                      </td>

                      {/* Skill Name Column */}
                      <td className="py-4 px-5 max-w-[280px] sm:max-w-md lg:max-w-xl">
                        <div className="font-heading font-extrabold text-white text-base group-hover:text-cyan-300 transition-colors tracking-tight flex items-center gap-2">
                          <span>{record.label}</span>
                          {isOpening && (
                            <span className="px-2 py-0.5 rounded-full bg-cyan-950/80 border border-cyan-500/40 text-cyan-300 text-[10px] font-mono font-bold uppercase tracking-wider">
                              Opening
                            </span>
                          )}
                        </div>
                        {record.reason && (
                          <div className="text-xs text-slate-400 mt-0.5 line-clamp-2 font-medium">
                            {record.reason}
                          </div>
                        )}
                      </td>

                      {/* Category Badge */}
                      <td className="py-4 px-4 whitespace-nowrap">
                        <span className={`text-xs font-mono font-bold px-2.5 py-1 rounded-lg border ${
                          isOpening
                            ? "bg-cyan-950/60 border-cyan-500/40 text-cyan-300"
                            : "bg-white/5 border-white/10 text-slate-300"
                        }`}>
                          {KIND_TITLE[record.kind] || record.kind}
                        </span>
                      </td>

                      {/* Tier Column */}
                      <td className="py-4 px-4 whitespace-nowrap">
                        {record.tier > 0 ? (
                          <span className={`text-xs font-mono font-bold px-2.5 py-1 rounded-lg border ${
                            record.tier === 1
                              ? "bg-cyan-950/70 border-cyan-500/40 text-cyan-300"
                              : record.tier === 2
                                ? "bg-amber-950/70 border-amber-500/40 text-amber-300"
                                : "bg-violet-950/70 border-violet-500/40 text-violet-300"
                          }`}>
                            Tier {record.tier}
                          </span>
                        ) : (
                          <span className="text-xs font-mono text-slate-600">—</span>
                        )}
                      </td>

                      {/* Progress / Proof Column */}
                      <td className="py-4 px-5 whitespace-nowrap">
                        <div className={`text-xs font-mono font-medium ${isLocked ? "text-amber-300/90" : "text-slate-300"}`}>
                          {meta(record, isLocked)}
                        </div>
                      </td>

                      {/* Action Buttons */}
                      <td className="py-4 px-5 text-right whitespace-nowrap">
                        <div className="inline-flex items-center justify-end gap-2">
                          {isLocked ? (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setLockedModalSkill(record);
                              }}
                              className="px-3.5 py-1.5 rounded-xl bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/40 text-amber-300 font-heading font-extrabold text-xs uppercase tracking-wider inline-flex items-center gap-1.5 transition-all shadow-[0_0_10px_rgba(245,158,11,0.15)] cursor-pointer"
                              title="Locked — Complete Opening foundation first"
                            >
                              <Lock className="h-3.5 w-3.5 text-amber-400" />
                              <span>Locked</span>
                            </button>
                          ) : (
                            <>
                              {showEvidence && (
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setEvidenceSkill(record);
                                  }}
                                  className="px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/15 border border-white/15 text-slate-300 hover:text-white font-mono text-xs font-bold transition-all cursor-pointer"
                                  title="Inspect in-game evidence and board positions"
                                >
                                  Why?
                                </button>
                              )}

                              {hasLesson && !hideStudyButton ? (
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    if (record.lesson_url) navigate(record.lesson_url);
                                  }}
                                  className="px-4 py-1.5 rounded-xl bg-gradient-to-r from-cyan-500/20 to-blue-500/20 hover:from-cyan-500/30 hover:to-blue-500/30 border border-cyan-400/60 text-cyan-200 font-heading font-extrabold text-xs uppercase tracking-wider inline-flex items-center gap-1.5 transition-all shadow-[0_0_12px_rgba(56,189,248,0.25)] cursor-pointer"
                                >
                                  <span>Study</span>
                                  <ArrowRight className="h-3.5 w-3.5 text-cyan-300" />
                                </button>
                              ) : isDrillable ? (
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    navigate(`/training/skill/${record.skill_id}`);
                                  }}
                                  className="px-3.5 py-1.5 rounded-xl bg-violet-500/20 hover:bg-violet-500/30 border border-violet-400/50 text-violet-200 font-heading font-extrabold text-xs uppercase tracking-wider inline-flex items-center gap-1.5 transition-all cursor-pointer"
                                >
                                  <span>Drill</span>
                                  <Sparkles className="h-3.5 w-3.5 text-violet-300" />
                                </button>
                              ) : null}
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* ─── Pagination & Table Summary Footer ─── */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mt-5 pt-4 border-t border-white/10 text-xs text-slate-400 font-mono">
          <div className="flex items-center gap-2">
            <span>Showing</span>
            <span className="font-bold text-white">
              {sortedRecords.length === 0
                ? "0"
                : `${(currentPage - 1) * pageSize + 1}–${Math.min(currentPage * pageSize, sortedRecords.length)}`}
            </span>
            <span>of</span>
            <span className="font-bold text-white">{sortedRecords.length}</span>
            <span>topics</span>
          </div>

          <div className="flex items-center gap-4">
            {/* Page Size Selector */}
            <div className="flex items-center gap-2">
              <span>Rows per page:</span>
              <select
                value={pageSize}
                onChange={(e) => setPageSize(Number(e.target.value))}
                className="bg-white/5 border border-white/15 rounded-lg px-2.5 py-1 text-white text-xs font-mono focus:outline-none focus:border-cyan-500/50 cursor-pointer"
              >
                <option value={10} className="bg-slate-900 text-white">10</option>
                <option value={15} className="bg-slate-900 text-white">15</option>
                <option value={25} className="bg-slate-900 text-white">25</option>
                <option value={50} className="bg-slate-900 text-white">50</option>
                <option value={0} className="bg-slate-900 text-white">All</option>
              </select>
            </div>

            {/* Pagination Controls */}
            {pageSize > 0 && totalPages > 1 && (
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  className="p-1.5 rounded-lg border border-white/10 hover:bg-white/10 disabled:opacity-30 disabled:pointer-events-none text-white transition-colors cursor-pointer"
                  aria-label="Previous page"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <span className="px-2 font-bold text-white">
                  {currentPage} / {totalPages}
                </span>
                <button
                  type="button"
                  disabled={currentPage === totalPages}
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  className="p-1.5 rounded-lg border border-white/10 hover:bg-white/10 disabled:opacity-30 disabled:pointer-events-none text-white transition-colors cursor-pointer"
                  aria-label="Next page"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ─── Prerequisite Locked Modal ─── */}
      <PrerequisiteModal
        skill={lockedModalSkill}
        suggestedOpening={suggestedOpening}
        onClose={() => setLockedModalSkill(null)}
        onGoToOpening={handleGoToOpening}
        onFilterOpenings={() => setSelectedKind("opening")}
      />

      {/* ─── Evidence Modal ─── */}
      <EvidenceModal
        skill={evidenceSkill}
        onClose={() => setEvidenceSkill(null)}
        onDemote={handleDemote}
      />
    </section>
  );
}


