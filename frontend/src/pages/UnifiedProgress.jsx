/**
 * PROGRESS — Your chess journey dashboard
 *
 * Professional, clean design showing:
 * - Focus area with before/after proof
 * - Opening repertoire with win rates
 * - Recent game results
 * - Clear next actions
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import {
  ChevronRight, Target, Swords, Check, X as XIcon, ArrowRight,
  Crown, BookOpen, TrendingUp, TrendingDown, Minus,
  Activity, Flame, Shield, Loader2
} from "lucide-react";

const UnifiedProgress = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState(null);
  const [openings, setOpenings] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const [progressRes, openingsRes] = await Promise.all([
          fetch(`${API}/progress/real`, { credentials: "include" }),
          fetch(`${API}/coach/play/opening-suggestions`, { credentials: "include" }),
        ]);
        if (progressRes.ok) setProgress(await progressRes.json());
        if (openingsRes.ok) setOpenings(await openingsRes.json());
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    })();
  }, []);

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center h-[60vh]">
          <Loader2 className="w-6 h-6 text-primary animate-spin" />
        </div>
      </Layout>
    );
  }

  const state = progress?.state || "not_started";

  return (
    <Layout user={user}>
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8" data-testid="progress-page">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          {/* Page Header */}
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-foreground tracking-tight">Your Progress</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Track your improvement and see what's working.
            </p>
          </div>

          {/* Focus Area Card */}
          <FocusCard state={state} progress={progress} navigate={navigate} />

          {/* Opening Repertoire */}
          {openings && openings.total_games > 0 && (
            <OpeningRepertoire openings={openings} navigate={navigate} />
          )}

          {/* Quick Actions */}
          <QuickActions state={state} progress={progress} navigate={navigate} />

        </motion.div>
      </div>
    </Layout>
  );
};


// ─── Focus Card ─────────────────────────────────────────────────

const FocusCard = ({ state, progress, navigate }) => {

  // NOT STARTED
  if (state === "not_started") {
    return (
      <div className="rounded-2xl border border-border bg-card p-6 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-muted flex items-center justify-center">
            <Target className="w-5 h-5 text-muted-foreground" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-foreground">No focus area yet</h2>
            <p className="text-xs text-muted-foreground">Analyze your games to find what to improve</p>
          </div>
        </div>
        <p className="text-sm text-muted-foreground leading-relaxed mb-5">
          Go to Lab to review your games. The coach will identify your biggest weakness and build a training plan around it.
        </p>
        <button
          onClick={() => navigate("/lab")}
          className="w-full py-3 text-sm font-semibold rounded-xl bg-foreground text-background hover:opacity-90 transition-all flex items-center justify-center gap-2"
        >
          Go to Lab
          <ChevronRight className="w-4 h-4 opacity-60" />
        </button>
      </div>
    );
  }

  // WAITING FOR GAMES
  if (state === "waiting_for_games") {
    const played = progress.post_games_played || 0;
    const needed = progress.post_games_needed || 3;
    const pct = Math.round((played / needed) * 100);

    return (
      <div className="rounded-2xl border border-border bg-card p-6 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center">
            <Activity className="w-5 h-5 text-amber-500" />
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Working on</p>
            <h2 className="text-base font-semibold text-foreground">{progress.focus_label}</h2>
          </div>
          <div className="ml-auto flex items-center gap-1.5">
            <Check className="w-3.5 h-3.5 text-emerald-500" strokeWidth={2.5} />
            <span className="text-xs text-emerald-600 font-medium">Trained</span>
          </div>
        </div>

        {/* Progress bar */}
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1.5">
            <p className="text-xs text-muted-foreground">Apply in real games</p>
            <p className="text-xs font-mono text-muted-foreground">{played}/{needed}</p>
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-amber-500 rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${pct}%` }}
              transition={{ duration: 0.6, ease: "easeOut" }}
            />
          </div>
        </div>

        {/* Game dots */}
        <div className="flex items-center gap-1.5 mb-5">
          {Array.from({ length: needed }).map((_, i) => (
            <div key={i} className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs ${
              i < played
                ? "bg-emerald-500/10 border border-emerald-500/20"
                : "bg-muted/50 border border-border/50"
            }`}>
              {i < played
                ? <Check className="w-3 h-3 text-emerald-500" strokeWidth={2.5} />
                : <span className="text-muted-foreground/30">{i + 1}</span>
              }
            </div>
          ))}
        </div>

        <button
          onClick={() => navigate("/play-with-coach")}
          className="w-full py-3 text-sm font-semibold rounded-xl bg-foreground text-background hover:opacity-90 transition-all flex items-center justify-center gap-2"
        >
          <Swords className="w-4 h-4" strokeWidth={2} />
          Play Game {played + 1}
        </button>
      </div>
    );
  }

  // TRACKING — the proof
  const pre = progress.pre_training || {};
  const post = progress.post_training || {};
  const verdict = progress.verdict || "no_change";
  const postGames = progress.post_training_games || [];

  const verdictConfig = {
    improving: {
      icon: TrendingUp,
      text: "You're improving",
      color: "text-emerald-500",
      bg: "bg-emerald-500/10",
      border: "border-emerald-500/20",
      iconColor: "text-emerald-500",
    },
    slipping: {
      icon: TrendingDown,
      text: "Needs more work",
      color: "text-red-400",
      bg: "bg-red-500/10",
      border: "border-red-500/20",
      iconColor: "text-red-400",
    },
    no_change: {
      icon: Minus,
      text: "No change yet",
      color: "text-muted-foreground",
      bg: "bg-muted",
      border: "border-border",
      iconColor: "text-muted-foreground",
    },
  };

  const v = verdictConfig[verdict] || verdictConfig.no_change;
  const VerdictIcon = v.icon;
  const delta = (pre.mistakes || 0) - (post.mistakes || 0);

  return (
    <div className="rounded-2xl border border-border bg-card mb-6 overflow-hidden">
      {/* Header */}
      <div className="px-6 pt-6 pb-4">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl ${v.bg} flex items-center justify-center`}>
            <VerdictIcon className={`w-5 h-5 ${v.iconColor}`} />
          </div>
          <div className="flex-1">
            <p className="text-xs text-muted-foreground">Working on</p>
            <h2 className="text-base font-semibold text-foreground">{progress.focus_label}</h2>
          </div>
          <div className={`px-3 py-1.5 rounded-full text-xs font-semibold ${v.bg} ${v.color} ${v.border} border`}>
            {v.text}
          </div>
        </div>
      </div>

      {/* Before / After comparison */}
      <div className="px-6 pb-5">
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl bg-muted/50 p-4">
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground/50 font-semibold mb-2">Before</p>
            <div className="flex items-baseline gap-1">
              <span className="text-3xl font-bold font-mono text-foreground">{pre.mistakes ?? "—"}</span>
              <span className="text-xs text-muted-foreground">mistakes</span>
            </div>
            <p className="text-[11px] text-muted-foreground mt-1">in {pre.games ?? 0} games</p>
          </div>
          <div className={`rounded-xl p-4 ${
            verdict === "improving" ? "bg-emerald-500/[0.05]" :
            verdict === "slipping" ? "bg-red-500/[0.05]" :
            "bg-muted/50"
          }`}>
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground/50 font-semibold mb-2">After</p>
            <div className="flex items-baseline gap-1">
              <span className={`text-3xl font-bold font-mono ${v.color}`}>{post.mistakes ?? "—"}</span>
              <span className="text-xs text-muted-foreground">mistakes</span>
            </div>
            <p className="text-[11px] text-muted-foreground mt-1">in {post.games ?? 0} games</p>
          </div>
        </div>

        {/* Delta indicator */}
        {delta !== 0 && (
          <div className="flex items-center justify-center mt-3">
            <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${
              delta > 0 ? "bg-emerald-500/10 text-emerald-600" : "bg-red-500/10 text-red-500"
            }`}>
              {delta > 0 ? <TrendingDown className="w-3 h-3" /> : <TrendingUp className="w-3 h-3" />}
              {delta > 0 ? `${delta} fewer mistakes` : `${Math.abs(delta)} more mistakes`}
            </div>
          </div>
        )}
      </div>

      {/* Recent games strip */}
      {postGames.length > 0 && (
        <div className="px-6 pb-5">
          <p className="text-[10px] uppercase tracking-widest font-semibold text-muted-foreground/40 mb-2">Recent games</p>
          <div className="flex items-center gap-1.5">
            {postGames.map((g, i) => (
              <div
                key={i}
                className={`h-8 flex-1 rounded-md flex items-center justify-center transition-all ${
                  g.had_mistake
                    ? "bg-red-500/8 border border-red-500/12"
                    : "bg-emerald-500/8 border border-emerald-500/12"
                }`}
                title={`vs ${g.opponent} — ${g.had_mistake ? "had mistake" : "clean"}`}
              >
                {g.had_mistake
                  ? <XIcon className="w-3 h-3 text-red-400" strokeWidth={2.5} />
                  : <Check className="w-3 h-3 text-emerald-500" strokeWidth={2.5} />
                }
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between mt-1.5">
            <p className="text-[10px] text-muted-foreground/40">
              {postGames.filter(g => !g.had_mistake).length} clean
            </p>
            <p className="text-[10px] text-muted-foreground/40">
              {postGames.filter(g => g.had_mistake).length} with mistakes
            </p>
          </div>
        </div>
      )}
    </div>
  );
};


// ─── Opening Repertoire ─────────────────────────────────────────

const OpeningRepertoire = ({ openings, navigate }) => {
  if (!openings || openings.total_games === 0) return null;

  const bestWhite = openings.white?.length > 0
    ? openings.white.reduce((a, b) => (b.win_rate > a.win_rate && b.games >= 3) ? b : a, openings.white[0])
    : null;
  const bestBlack = openings.black?.length > 0
    ? openings.black.reduce((a, b) => (b.win_rate > a.win_rate && b.games >= 3) ? b : a, openings.black[0])
    : null;

  return (
    <div className="rounded-2xl border border-border bg-card mb-6 overflow-hidden">
      <div className="px-6 pt-5 pb-2">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
            <BookOpen className="w-4 h-4 text-primary" />
          </div>
          <h3 className="text-sm font-semibold text-foreground">Your Openings</h3>
        </div>
      </div>

      <div className="px-6 pb-5 space-y-4">
        <OpeningColorSection label="As White" list={openings.white} best={bestWhite} />
        <OpeningColorSection label="As Black" list={openings.black} best={bestBlack} />
      </div>

      {/* Coach recommendation */}
      {(bestWhite || bestBlack) && (
        <div className="px-6 pb-5">
          <div className="rounded-xl bg-primary/[0.04] border border-primary/10 p-4">
            <div className="flex items-start gap-3">
              <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Flame className="w-3.5 h-3.5 text-primary" />
              </div>
              <div className="flex-1">
                <p className="text-xs font-semibold text-primary mb-0.5">Coach recommends</p>
                <p className="text-sm text-foreground leading-relaxed">
                  Focus on{" "}
                  {bestWhite && <span className="font-semibold">{bestWhite.name}</span>}
                  {bestWhite && bestBlack && " and "}
                  {bestBlack && <span className="font-semibold">{bestBlack.name}</span>}
                  . Mastering 1-2 openings deeply is how you climb.
                </p>
              </div>
            </div>
            <button
              onClick={() => {
                const opening = bestWhite?.name || bestBlack?.name || "";
                navigate(`/play-with-coach${opening ? `?opening=${encodeURIComponent(opening)}` : ""}`);
              }}
              className="mt-3 ml-10 text-xs font-medium text-primary hover:text-primary/80 flex items-center gap-1 transition-colors"
            >
              Practice with Coach
              <ChevronRight className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

const OpeningColorSection = ({ label, list, best }) => {
  if (!list?.length) return null;

  return (
    <div>
      <p className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground/40 mb-2">{label}</p>
      <div className="space-y-1">
        {list.slice(0, 4).map((o) => {
          const isBest = best && o.name === best.name && best.games >= 3;
          return (
            <div
              key={o.name}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all ${
                isBest
                  ? "bg-emerald-500/[0.04] border border-emerald-500/15"
                  : "hover:bg-muted/50"
              }`}
            >
              {isBest && <Crown className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />}
              <span className={`text-sm text-foreground flex-1 truncate ${isBest ? "font-medium" : ""}`}>
                {o.name}
              </span>

              {/* Win rate bar */}
              <div className="flex items-center gap-2 flex-shrink-0">
                <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      o.win_rate >= 55 ? "bg-emerald-500" :
                      o.win_rate >= 45 ? "bg-amber-400" :
                      "bg-red-400"
                    }`}
                    style={{ width: `${Math.min(100, o.win_rate)}%` }}
                  />
                </div>
                <span className={`text-xs font-mono w-8 text-right ${
                  o.win_rate >= 55 ? "text-emerald-600" :
                  o.win_rate >= 45 ? "text-foreground" :
                  "text-red-400"
                }`}>
                  {o.win_rate}%
                </span>
                <span className="text-[10px] text-muted-foreground/50 w-5 text-right">{o.games}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};


// ─── Quick Actions ──────────────────────────────────────────────

const QuickActions = ({ state, progress, navigate }) => {
  const verdict = progress?.verdict;

  return (
    <div className="grid grid-cols-2 gap-3">
      <button
        onClick={() => navigate("/play-with-coach")}
        className="flex items-center gap-3 p-4 rounded-2xl border border-border bg-card hover:bg-muted/50 transition-all group"
      >
        <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center group-hover:bg-primary/15 transition-colors">
          <Swords className="w-4 h-4 text-primary" strokeWidth={2} />
        </div>
        <div className="text-left">
          <p className="text-sm font-medium text-foreground">Play with Coach</p>
          <p className="text-[11px] text-muted-foreground">Practice your openings</p>
        </div>
      </button>

      <button
        onClick={() => navigate("/lab")}
        className="flex items-center gap-3 p-4 rounded-2xl border border-border bg-card hover:bg-muted/50 transition-all group"
      >
        <div className="w-9 h-9 rounded-xl bg-amber-500/10 flex items-center justify-center group-hover:bg-amber-500/15 transition-colors">
          <Target className="w-4 h-4 text-amber-500" strokeWidth={2} />
        </div>
        <div className="text-left">
          <p className="text-sm font-medium text-foreground">Review Games</p>
          <p className="text-[11px] text-muted-foreground">Find your weaknesses</p>
        </div>
      </button>
    </div>
  );
};

export default UnifiedProgress;
