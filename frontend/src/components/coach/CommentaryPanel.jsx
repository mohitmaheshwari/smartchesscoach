/**
 * CommentaryPanel — Position reading + Opening guidance + Trap warnings
 *
 * Three sections:
 *   1. Opening Guidance (when learning an opening — move ideas, phase)
 *   2. Trap Warning (when approaching a known trap)
 *   3. Board Reading (pins, forks, activity, structure)
 */

import { useRef } from "react";
import { AlertTriangle, BookOpen, Eye, Target, Zap, Shield, Crown } from "lucide-react";

const CATEGORY_CONFIG = {
  tactics: { icon: Zap, color: "text-red-500", bg: "bg-red-500/5", border: "border-red-500/10" },
  king_safety: { icon: Shield, color: "text-amber-500", bg: "bg-amber-500/5", border: "border-amber-500/10" },
  piece_activity: { icon: Crown, color: "text-blue-500", bg: "bg-blue-500/5", border: "border-blue-500/10" },
  development: { icon: Target, color: "text-emerald-500", bg: "bg-emerald-500/5", border: "border-emerald-500/10" },
  center: { icon: Target, color: "text-purple-500", bg: "bg-purple-500/5", border: "border-purple-500/10" },
  pawn_structure: { icon: Eye, color: "text-orange-500", bg: "bg-orange-500/5", border: "border-orange-500/10" },
};

const CommentaryPanel = ({ commentary, openingGuidance, trapWarning, openingDeviation, activeBranch, openingComplete, coachMoveExplanation, lastCoachMoveSan, coachMoveCoaching }) => {
  const hasContent = commentary || openingGuidance || trapWarning || openingDeviation || openingComplete || coachMoveExplanation;
  const prevObsTitles = useRef(new Set());

  // Filter out observations that were shown on the previous move
  const filteredCommentary = commentary ? {
    ...commentary,
    observations: (commentary.observations || []).filter(obs => {
      return !prevObsTitles.current.has(obs.title);
    }),
  } : null;

  // Update tracking for next render
  if (commentary?.observations) {
    const currentTitles = new Set(commentary.observations.map(o => o.title));
    prevObsTitles.current = currentTitles;
  }

  if (!hasContent) return null;

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-3 py-2.5 border-b border-border/50">
        <div className="flex items-center gap-1.5">
          <BookOpen className="w-3.5 h-3.5 text-muted-foreground/50" />
          <span className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground/50">
            Coach
          </span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">

        {/* ─── Coach Move Explanation (v2 intent-driven) ─── */}
        {(coachMoveCoaching || coachMoveExplanation) && (
          <div className="rounded-lg bg-muted/40 border border-border/50 px-3 py-2 space-y-2">
            <div className="flex items-center gap-1.5">
              <Zap className="w-3 h-3 text-muted-foreground/60" strokeWidth={2} />
              <span className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground/50">
                Opponent{lastCoachMoveSan ? ` played ${lastCoachMoveSan}` : ""}
              </span>
              {coachMoveCoaching?.v2_label && (
                <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${
                  coachMoveCoaching.v2_intent === 'fork_opportunity'
                    ? 'bg-red-100 text-red-700'
                    : coachMoveCoaching.v2_intent === 'hanging_piece_punishment'
                      ? 'bg-amber-100 text-amber-700'
                      : 'bg-purple-100 text-purple-700'
                }`}>
                  {coachMoveCoaching.v2_label}
                </span>
              )}
            </div>

            <p className="text-xs text-foreground/80 leading-snug">
              {coachMoveCoaching?.explanation || coachMoveExplanation}
            </p>

            {coachMoveCoaching?.hint_for_user && (
              <p className="text-xs text-amber-700 font-medium">
                {coachMoveCoaching.hint_for_user}
              </p>
            )}

            {coachMoveCoaching?.opponent_opportunity && (
              <div className="rounded bg-emerald-50 border border-emerald-200 px-2 py-1.5">
                <p className="text-xs text-emerald-800 font-medium">
                  {coachMoveCoaching.opponent_opportunity.message}
                </p>
              </div>
            )}

            {coachMoveCoaching?.plan && (
              <p className="text-[11px] text-muted-foreground italic">
                {coachMoveCoaching.plan}
              </p>
            )}
          </div>
        )}

        {/* ─── Opening Line Complete ─── */}
        {openingComplete && (
          <div className="rounded-xl border-2 border-emerald-400/30 bg-emerald-500/[0.04] p-3">
            <div className="flex items-center gap-2 mb-2">
              <Target className="w-4 h-4 text-emerald-500" strokeWidth={2.5} />
              <span className="text-[10px] uppercase tracking-widest font-bold text-emerald-500">
                {openingComplete.branchName} Complete
              </span>
            </div>
            <p className="text-sm text-foreground mb-2">
              Well done! {openingComplete.evalText}. Play actively from here.
            </p>
            {openingComplete.otherBranches?.length > 0 && (
              <div className="rounded-lg bg-muted/50 border border-border/50 px-3 py-2">
                <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-bold mb-1">
                  More to learn
                </p>
                <p className="text-xs text-foreground/70">
                  {openingComplete.otherBranches.length === 1
                    ? `The ${openingComplete.otherBranches[0]} is another variation — play again to learn it.`
                    : `${openingComplete.otherBranches.join(" and ")} are other variations — play again to learn them.`
                  }
                </p>
              </div>
            )}
          </div>
        )}

        {/* ─── Opening Deviation: Rejected (bad move) ─── */}
        {openingDeviation?.rejected && (
          <div className="rounded-xl border-2 border-red-400/40 bg-red-500/[0.06] p-3">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="w-4 h-4 text-red-500" strokeWidth={2.5} />
              <span className="text-[10px] uppercase tracking-widest font-bold text-red-500">
                Move Reset
              </span>
            </div>
            <p className="text-sm font-medium text-foreground mb-1.5">
              <span className="font-mono">{openingDeviation.played}</span> is not the right move here.
            </p>
            {openingDeviation.reason && (
              <p className="text-xs text-foreground/70 leading-snug mb-2">
                {openingDeviation.reason}
              </p>
            )}
            <div className="rounded-lg bg-primary/10 border border-primary/20 px-3 py-2">
              <p className="text-[9px] uppercase tracking-widest text-primary font-bold mb-0.5">
                {openingDeviation.branch || "Opening"} plan
              </p>
              <p className="text-xs text-foreground">
                Play <span className="font-mono font-semibold">{openingDeviation.expected}</span>
                {openingDeviation.idea ? ` — ${openingDeviation.idea.toLowerCase()}` : ""}
              </p>
            </div>
          </div>
        )}

        {/* ─── Opening Deviation: Accepted (ok move, off-book) ─── */}
        {openingDeviation?.accepted && (
          <div className="rounded-xl border-2 border-amber-400/30 bg-amber-500/[0.04] p-3">
            <div className="flex items-center gap-2 mb-2">
              <BookOpen className="w-4 h-4 text-amber-500" strokeWidth={2} />
              <span className="text-[10px] uppercase tracking-widest font-bold text-amber-500">
                Off-Book
              </span>
            </div>
            <p className="text-sm text-foreground mb-1.5">
              <span className="font-mono font-semibold">{openingDeviation.played}</span> is fine, but it leaves the {openingDeviation.branch || "opening"} line.
            </p>
            {openingDeviation.reason && (
              <p className="text-xs text-foreground/70 leading-snug mb-2">
                {openingDeviation.reason}
              </p>
            )}
            <p className="text-[11px] text-muted-foreground italic">
              The {openingDeviation.branch || "opening"} plan was <span className="font-mono">{openingDeviation.expected}</span>{openingDeviation.idea ? ` — ${openingDeviation.idea.toLowerCase()}` : ""}.
            </p>
            <p className="text-[10px] text-muted-foreground/60 mt-2">
              Opening guidance ended — playing freely now.
            </p>
          </div>
        )}

        {/* ─── New Variation Intro ─── */}
        {activeBranch?.intro && openingGuidance && !openingDeviation && (
          <div className="rounded-xl border-2 border-blue-400/20 bg-blue-500/[0.03] p-3">
            <div className="flex items-center gap-2 mb-2">
              <BookOpen className="w-4 h-4 text-blue-500" strokeWidth={2} />
              <span className="text-[10px] uppercase tracking-widest font-bold text-blue-500">
                {activeBranch.name || "Variation"}
              </span>
            </div>
            <p className="text-xs text-foreground/80 leading-snug">
              {activeBranch.intro}
            </p>
          </div>
        )}

        {/* ─── Opening Guidance (when learning) ─── */}
        {openingGuidance && (
          <div className="rounded-xl border-2 border-primary/20 bg-primary/[0.03] p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] uppercase tracking-widest font-bold text-primary">
                {openingGuidance.phase_label || "Learning"}
              </span>
              {openingGuidance.games_played > 0 && (
                <span className="text-[9px] text-muted-foreground/40">
                  Game {openingGuidance.games_played + 1}
                </span>
              )}
            </div>

            {/* Move idea */}
            {openingGuidance.move_idea && (
              <p className="text-sm text-foreground leading-snug mb-2">
                {openingGuidance.move_idea}
              </p>
            )}

            {/* Coach's move explanation */}
            {openingGuidance.coach_move_idea && (
              <div className="rounded-lg bg-blue-500/5 border border-blue-500/10 px-3 py-2 mb-2">
                <p className="text-[9px] uppercase tracking-widest text-blue-500 font-bold mb-0.5">Opponent played {openingGuidance.coach_move}</p>
                <p className="text-xs text-foreground/80">{openingGuidance.coach_move_idea}</p>
              </div>
            )}

            {/* Deviation warning */}
            {openingGuidance.deviation && (
              <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 p-2.5 mb-2">
                <p className="text-xs text-amber-600 font-medium mb-1">
                  You played {openingGuidance.deviation.played} — that's not the Italian Game plan
                </p>
                <p className="text-[11px] text-foreground/70">
                  {openingGuidance.deviation.idea}
                </p>
              </div>
            )}

            {/* Arrow indicator */}
            {openingGuidance.arrow && !openingGuidance.deviation && (
              <div className="flex items-center gap-2 text-xs text-primary/70">
                <span className="font-mono">{openingGuidance.arrow[0]}</span>
                <span>→</span>
                <span className="font-mono">{openingGuidance.arrow[1]}</span>
              </div>
            )}
          </div>
        )}

        {/* ─── Trap Warning ─── */}
        {trapWarning && (
          <div className="rounded-xl border-2 border-amber-400/30 bg-amber-500/[0.04] p-3">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="w-4 h-4 text-amber-500" strokeWidth={2.5} />
              <span className="text-[10px] uppercase tracking-widest font-bold text-amber-500">
                Trap Alert
              </span>
            </div>
            <p className="text-sm font-semibold text-foreground mb-1">
              {trapWarning.trap_name}
            </p>
            <p className="text-xs text-foreground/70 leading-snug mb-2">
              {trapWarning.warning}
            </p>
            {trapWarning.refutation && (
              <p className="text-[11px] text-amber-600/70 italic">
                {trapWarning.refutation}
              </p>
            )}
          </div>
        )}

        {/* ─── Board Reading ─── */}
        {filteredCommentary && (
          <>
            {/* Material */}
            {filteredCommentary.material && (
              <p className="text-[11px] text-muted-foreground font-medium">{filteredCommentary.material}</p>
            )}

            {/* Summary */}
            {filteredCommentary.summary && (
              <p className="text-sm text-foreground leading-snug">{filteredCommentary.summary}</p>
            )}

            {/* Plan */}
            {filteredCommentary.plan && (
              <div className="rounded-lg bg-primary/5 border border-primary/10 px-3 py-2">
                <p className="text-[9px] uppercase tracking-widest text-primary/60 font-bold mb-1">Plan</p>
                <p className="text-xs text-foreground leading-snug">{filteredCommentary.plan}</p>
              </div>
            )}

            {/* Observations — deduplicated (same title won't repeat next move) */}
            {filteredCommentary.observations && filteredCommentary.observations.length > 0 && (
              <div className="space-y-1.5">
                {filteredCommentary.observations.map((obs, i) => {
                  const config = CATEGORY_CONFIG[obs.category] || CATEGORY_CONFIG.piece_activity;
                  const Icon = config.icon;
                  return (
                    <div key={i} className={`rounded-lg ${config.bg} border ${config.border} px-2.5 py-2`}>
                      <div className="flex items-start gap-2">
                        <Icon className={`w-3 h-3 ${config.color} mt-0.5 flex-shrink-0`} strokeWidth={2} />
                        <div className="flex-1 min-w-0">
                          {obs.title && (
                            <p className={`text-[10px] font-semibold ${config.color} mb-0.5`}>{obs.title}</p>
                          )}
                          <p className="text-xs text-foreground/80 leading-snug">
                            {obs.description || obs.actionable || obs.title}
                          </p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default CommentaryPanel;
