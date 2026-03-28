/**
 * CoachInsightPanel — The 3-tab Coach Mode for The Lab
 * 
 * Tab 1: Summary — ONE brutal truth about why you lost/won
 * Tab 2: Habits  — Pass/fail checklist of behavioral patterns  
 * Tab 3: Memory  — Identity snapshot + impact projection
 *
 * No LLM, no storytelling. Pure diagnosis.
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { 
  AlertTriangle, Target, CheckCircle2, XCircle, 
  Brain, TrendingUp, Loader2, Crosshair, 
  Shield, Zap, ArrowRight
} from "lucide-react";

// ─── DIAGNOSIS COLORS & ICONS ────────────────────────────────────

const DIAGNOSIS_CONFIG = {
  THROW:              { color: "text-red-600",    bg: "bg-red-500/10",    border: "border-red-500/20",    label: "Thrown Game" },
  MATE_BLIND:         { color: "text-red-500",    bg: "bg-red-500/15",    border: "border-red-500/30",    label: "Missed Mate" },
  SLOW_BLEED:         { color: "text-amber-600",  bg: "bg-amber-500/10",  border: "border-amber-500/20",  label: "Outplayed" },
  OPENING_COLLAPSE:   { color: "text-orange-400", bg: "bg-orange-500/10", border: "border-orange-500/20", label: "Opening Failure" },
  PIECE_GIVEAWAY:     { color: "text-orange-400", bg: "bg-orange-500/10", border: "border-orange-500/20", label: "Hung Piece" },
  TACTICAL_MISS:      { color: "text-amber-600",  bg: "bg-amber-500/10",  border: "border-amber-500/20",  label: "Tactical Miss" },
  TIME_COLLAPSE:      { color: "text-orange-400", bg: "bg-orange-500/10", border: "border-orange-500/20", label: "Time Trouble" },
  WON_CLEAN:          { color: "text-emerald-600",bg: "bg-emerald-500/10",border: "border-emerald-500/20",label: "Clean Win" },
  WON_OPPONENT_BLUNDER:{ color: "text-emerald-600",bg: "bg-yellow-500/10",border: "border-yellow-500/20",label: "Lucky Win" },
  DRAW:               { color: "text-gray-500",   bg: "bg-zinc-500/10",   border: "border-zinc-500/20",   label: "Draw" },
  UNKNOWN:            { color: "text-gray-500",   bg: "bg-zinc-500/10",   border: "border-zinc-500/20",   label: "Unknown" },
};

const SEVERITY_COLORS = {
  CRITICAL: "text-red-600 bg-red-500/15 border-red-500/30",
  HIGH:     "text-orange-400 bg-orange-500/15 border-orange-500/30",
  MEDIUM:   "text-amber-600 bg-amber-500/15 border-amber-500/30",
  LOW:      "text-gray-500 bg-zinc-500/15 border-zinc-500/30",
};

// ─── MAIN COMPONENT ──────────────────────────────────────────────

const CoachInsightPanel = ({ gameId, onMoveClick }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("summary");

  useEffect(() => {
    if (!gameId) return;
    const fetchInsight = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${API}/lab/${gameId}/coach-insight`, { credentials: "include" });
        if (!res.ok) throw new Error("Failed to load coach insight");
        const json = await res.json();
        setData(json);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetchInsight();
  }, [gameId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20" data-testid="coach-insight-loading">
        <Loader2 className="w-6 h-6 animate-spin text-primary mr-3" />
        <span className="text-sm text-muted-foreground">Analyzing game...</span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-center py-16 text-muted-foreground" data-testid="coach-insight-error">
        <AlertTriangle className="w-8 h-8 mx-auto mb-3 opacity-50" />
        <p className="text-sm">{error || "No data available"}</p>
      </div>
    );
  }

  return (
    <div data-testid="coach-insight-panel">
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="w-full bg-gray-50 mb-4">
          <TabsTrigger value="summary" className="flex-1 text-xs" data-testid="tab-summary">
            <Crosshair className="w-3 h-3 mr-1.5" />
            Summary
          </TabsTrigger>
          <TabsTrigger value="habits" className="flex-1 text-xs" data-testid="tab-habits">
            <Shield className="w-3 h-3 mr-1.5" />
            Habits
            {data.habits && (
              <span className="ml-1.5 text-[10px] opacity-60">
                {data.habits.passed_count}/{data.habits.total_count}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="memory" className="flex-1 text-xs" data-testid="tab-memory">
            <Brain className="w-3 h-3 mr-1.5" />
            Memory
          </TabsTrigger>
        </TabsList>

        <TabsContent value="summary" className="mt-0">
          <SummaryTab summary={data.summary} onMoveClick={onMoveClick} />
        </TabsContent>

        <TabsContent value="habits" className="mt-0">
          <HabitsTab habits={data.habits} />
        </TabsContent>

        <TabsContent value="memory" className="mt-0">
          <MemoryTab memory={data.memory} />
        </TabsContent>
      </Tabs>
    </div>
  );
};


// ─── SUMMARY TAB ─────────────────────────────────────────────────

const SummaryTab = ({ summary, onMoveClick }) => {
  if (!summary) return null;
  const config = DIAGNOSIS_CONFIG[summary.diagnosis] || DIAGNOSIS_CONFIG.UNKNOWN;
  const critical = summary.critical_move;

  return (
    <div className="space-y-4" data-testid="summary-tab">
      {/* Diagnosis badge */}
      <div className={`rounded-lg p-4 ${config.bg} border ${config.border}`}>
        <div className="flex items-center gap-2 mb-3">
          <Badge variant="outline" className={`text-xs ${config.color} border-current`}>
            {config.label}
          </Badge>
        </div>

        {/* Root cause — THE truth */}
        <p className={`text-base font-semibold leading-relaxed ${config.color}`} data-testid="root-cause">
          {summary.root_cause}
        </p>
      </div>

      {/* Critical moment */}
      {critical && (
        <div 
          className="bg-gray-50 rounded-lg p-3 border border-gray-200 cursor-pointer hover:border-gray-300 transition-colors"
          onClick={() => onMoveClick?.(critical.move_number)}
          data-testid="critical-moment"
        >
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Critical Moment</div>
          <div className="flex items-center gap-3">
            <span className="font-mono font-bold text-lg text-gray-900">{critical.san}</span>
            <div className="text-xs text-gray-500">
              Move {critical.move_number} &middot; Lost {(critical.cp_loss / 100).toFixed(1)} pawns
            </div>
            {critical.best_move && (
              <div className="text-xs">
                <span className="text-gray-500">Best: </span>
                <span className="text-emerald-600 font-mono">{critical.best_move}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Context bullets */}
      {summary.context?.length > 0 && (
        <div className="space-y-1.5 pl-1">
          {summary.context.map((line, i) => (
            <div key={i} className="flex items-start gap-2 text-sm text-gray-500">
              <ArrowRight className="w-3 h-3 mt-1 flex-shrink-0 text-gray-400" />
              <span>{line}</span>
            </div>
          ))}
        </div>
      )}

      {/* Coach note */}
      {summary.coach_note && (
        <div className="bg-blue-500/8 rounded-lg p-3 border border-blue-500/15" data-testid="coach-note">
          <p className="text-sm text-blue-700 leading-relaxed">{summary.coach_note}</p>
        </div>
      )}
    </div>
  );
};


// ─── HABITS TAB ──────────────────────────────────────────────────

const HabitsTab = ({ habits }) => {
  if (!habits) return null;

  return (
    <div className="space-y-4" data-testid="habits-tab">
      {/* Score */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-500">Habits Score</span>
        <span className={`font-bold ${
          habits.passed_count === habits.total_count ? 'text-emerald-600' :
          habits.passed_count >= habits.total_count / 2 ? 'text-amber-600' :
          'text-red-600'
        }`}>
          {habits.passed_count}/{habits.total_count} passed
        </span>
      </div>

      {/* Checklist */}
      <div className="space-y-2">
        {habits.habits.map((habit, i) => (
          <div 
            key={i}
            className={`rounded-lg p-3 border transition-colors ${
              habit.passed 
                ? 'bg-emerald-500/5 border-emerald-500/15' 
                : 'bg-red-500/5 border-red-500/15'
            }`}
            data-testid={`habit-${i}`}
          >
            <div className="flex items-start gap-2.5">
              {habit.passed ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 flex-shrink-0" />
              ) : (
                <XCircle className="w-4 h-4 text-red-600 mt-0.5 flex-shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-medium ${habit.passed ? 'text-emerald-600' : 'text-red-600'}`}>
                  {habit.name}
                </p>
                <p className="text-xs text-gray-500 mt-0.5">{habit.evidence}</p>
                {habit.impact && !habit.passed && (
                  <p className="text-xs text-red-600/70 mt-0.5">{habit.impact}</p>
                )}
              </div>
              <Badge 
                variant="outline" 
                className={`text-[10px] flex-shrink-0 ${habit.passed ? 'text-emerald-600 border-emerald-500/30' : 'text-red-600 border-red-500/30'}`}
              >
                {habit.passed ? "PASSED" : "FAILED"}
              </Badge>
            </div>
          </div>
        ))}
      </div>

      {/* Focus habit highlight */}
      {habits.focus_habit && (
        <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/20" data-testid="focus-habit">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="w-4 h-4 text-red-600" />
            <span className="text-xs text-red-600 uppercase tracking-wider font-semibold">Focus Habit</span>
          </div>
          <p className="text-sm font-medium text-gray-900">{habits.focus_habit.name}</p>
          <p className="text-xs text-red-600/70 mt-1">{habits.focus_habit.evidence}</p>
          {habits.focus_habit.impact && (
            <p className="text-xs text-red-600 mt-1 font-medium">{habits.focus_habit.impact}</p>
          )}
        </div>
      )}
    </div>
  );
};


// ─── MEMORY TAB ──────────────────────────────────────────────────

const MemoryTab = ({ memory }) => {
  if (!memory) return null;
  const { identity, impact } = memory;

  return (
    <div className="space-y-4" data-testid="memory-tab">
      {/* YOUR CHESS DNA — Identity Snapshot */}
      <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Brain className="w-4 h-4 text-blue-600" />
            <span className="text-xs text-blue-600 uppercase tracking-wider font-semibold">Your Chess DNA</span>
          </div>
          {identity.archetype && (
            <Badge variant="outline" className="text-[10px] text-blue-700 border-blue-500/30">
              {identity.archetype}
            </Badge>
          )}
        </div>

        {/* Before / After this game */}
        <div className="space-y-3">
          {identity.before_line && (
            <div className="flex items-start gap-2.5">
              <span className="text-[10px] text-gray-400 uppercase tracking-wider w-14 flex-shrink-0 pt-0.5">Before</span>
              <p className="text-sm text-gray-500 leading-relaxed">{identity.before_line}</p>
            </div>
          )}
          {identity.after_line && (
            <div className="flex items-start gap-2.5">
              <span className="text-[10px] text-gray-400 uppercase tracking-wider w-14 flex-shrink-0 pt-0.5">After</span>
              <p className="text-sm text-gray-900 font-medium leading-relaxed">{identity.after_line}</p>
            </div>
          )}
        </div>

        {identity.this_game_confirms && (
          <p className="text-xs text-gray-500 mt-3 border-l-2 border-blue-500/30 pl-3 italic">
            {identity.this_game_confirms}
          </p>
        )}
      </div>

      {/* IF YOU FIXED THIS ONE THING — Impact Projection */}
      {impact && impact.estimated_rating_gain > 0 && (
        <div className={`rounded-lg p-4 border ${SEVERITY_COLORS[impact.severity] || SEVERITY_COLORS.LOW}`} data-testid="impact-projection">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4" />
              <span className="text-xs uppercase tracking-wider font-semibold">If You Fixed This One Thing</span>
            </div>
            <Badge variant="outline" className="text-[10px] border-current">
              {impact.severity}
            </Badge>
          </div>

          {/* The 3-line punch */}
          <div className="space-y-2.5">
            {impact.stat_line && (
              <p className="text-sm text-gray-700">{impact.stat_line}</p>
            )}
            {impact.fix_line && (
              <p className="text-sm text-gray-900 font-semibold">{impact.fix_line}</p>
            )}
            {impact.diff_line && (
              <p className="text-base font-bold text-emerald-600">{impact.diff_line}</p>
            )}
          </div>

          {/* Rating projection bar */}
          {impact.projected_rating && impact.current_rating > 0 && (
            <div className="bg-gray-50 rounded p-2.5 flex items-center justify-center gap-3 mt-4">
              <span className="text-sm text-gray-500">{impact.current_rating}</span>
              <ArrowRight className="w-4 h-4 text-emerald-600" />
              <span className="text-sm font-bold text-emerald-600">~{impact.projected_rating}</span>
            </div>
          )}
        </div>
      )}

      {/* No significant pattern */}
      {impact && impact.estimated_rating_gain === 0 && (
        <div className="bg-gray-50 rounded-lg p-4 border border-gray-200 text-center">
          <p className="text-sm text-gray-500">No dominant pattern yet. Keep playing — your identity is forming.</p>
        </div>
      )}
    </div>
  );
};


export default CoachInsightPanel;
