/**
 * PROGRESS — "Am I getting better?"
 *
 * 3 states:
 *   NOT STARTED  → "Go to Lab"
 *   WAITING      → "Play 3 games first"
 *   TRACKING     → Pre vs Post comparison + verdict
 *
 * Based on REAL game behavior, not training data.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import {
  ChevronRight, Target, Swords, Check, X as XIcon, ArrowRight,
  Crown, BookOpen, TrendingUp, TrendingDown
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
    return <Layout user={user}><div className="flex items-center justify-center h-[60vh]"><div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" /></div></Layout>;
  }

  const state = progress?.state || "not_started";

  // ═══════════════════════════════════════════
  // STATE 1: NOT STARTED
  // ═══════════════════════════════════════════
  if (state === "not_started") {
    return (
      <Layout user={user}>
        <div className="max-w-md mx-auto px-6 py-24" data-testid="progress-page">
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
            <p className="text-base text-foreground mb-2">
              You haven't started working on anything yet.
            </p>
            <p className="text-sm text-muted-foreground mb-8">
              Go to Lab to find out what to fix. Then train it. Then play. Then come back here to see if it worked.
            </p>
            {/* Opening Repertoire */}
            {openings && openings.total_games > 0 && (
              <div className="mb-8">
                <OpeningRepertoire openings={openings} navigate={navigate} />
              </div>
            )}

            <button onClick={() => navigate("/lab")}
              className="w-full py-3.5 text-[15px] font-semibold rounded-xl gradient-gold text-black hover:opacity-90 transition-all shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2">
              Go to Lab
              <ChevronRight className="w-4 h-4 opacity-60" />
            </button>
          </motion.div>
        </div>
      </Layout>
    );
  }

  // ═══════════════════════════════════════════
  // STATE 2: WAITING FOR GAMES
  // ═══════════════════════════════════════════
  if (state === "waiting_for_games") {
    const played = progress.post_games_played || 0;
    const needed = progress.post_games_needed || 3;

    return (
      <Layout user={user}>
        <div className="max-w-md mx-auto px-6 py-16" data-testid="progress-page">
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>

            {/* What they're working on */}
            <p className="text-sm text-muted-foreground/60 mb-1">You are working on:</p>
            <h1 className="text-xl font-heading text-foreground tracking-tight mb-8">
              {progress.focus_label}
            </h1>

            {/* Training complete acknowledgment */}
            <div className="flex items-center gap-2.5 mb-6">
              <div className="w-6 h-6 rounded-full bg-emerald-500/15 flex items-center justify-center">
                <Check className="w-3.5 h-3.5 text-emerald-500" strokeWidth={2.5} />
              </div>
              <p className="text-sm text-emerald-500 font-medium">Training complete</p>
            </div>

            {/* Now apply it */}
            <p className="text-[15px] text-foreground leading-relaxed mb-3">
              Now apply it in real games.
            </p>
            <p className="text-sm text-muted-foreground mb-8">
              Play {needed - played} more game{needed - played !== 1 ? "s" : ""} to see if it's working.
            </p>

            {/* Game dots */}
            <div className="flex items-center gap-2 mb-8">
              {Array.from({ length: needed }).map((_, i) => (
                <div key={i} className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                  i < played
                    ? "bg-emerald-500/15 border border-emerald-500/20"
                    : "bg-muted border border-border"
                }`}>
                  {i < played
                    ? <Check className="w-3.5 h-3.5 text-emerald-500" strokeWidth={2.5} />
                    : <span className="text-xs text-muted-foreground/30">{i + 1}</span>
                  }
                </div>
              ))}
              <p className="text-xs text-muted-foreground ml-2">{played} of {needed}</p>
            </div>

            {/* CTA */}
            <button onClick={() => navigate("/play-with-coach")}
              className="w-full py-4 text-[15px] font-semibold rounded-xl gradient-gold text-black hover:opacity-90 transition-all shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2">
              <Swords className="w-4 h-4" strokeWidth={2} />
              Play with Coach
              <ChevronRight className="w-4 h-4 opacity-60" />
            </button>

          </motion.div>
        </div>
      </Layout>
    );
  }

  // ═══════════════════════════════════════════
  // STATE 3: TRACKING — the proof
  // ═══════════════════════════════════════════
  const pre = progress.pre_training || {};
  const post = progress.post_training || {};
  const verdict = progress.verdict || "no_change";
  const postGames = progress.post_training_games || [];

  const verdictText = {
    improving: "You are improving.",
    slipping: "You are slipping.",
    no_change: "No change yet.",
  };
  const verdictColor = {
    improving: "text-emerald-500",
    slipping: "text-red-400",
    no_change: "text-foreground/60",
  };

  return (
    <Layout user={user}>
      <div className="max-w-md mx-auto px-6 py-12" data-testid="progress-page">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>

          {/* Identity */}
          <p className="text-sm text-muted-foreground/60 mb-1">You are working on:</p>
          <h1 className="text-xl font-heading text-foreground tracking-tight mb-10">
            {progress.focus_label}
          </h1>

          {/* Comparison — THE proof */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            {/* Before */}
            <div className="rounded-xl border border-border bg-card p-5">
              <p className="text-xs text-muted-foreground/50 uppercase tracking-wider mb-3">Before training</p>
              <p className="text-4xl font-mono font-bold text-foreground mb-1">{pre.mistakes}</p>
              <p className="text-xs text-muted-foreground">in {pre.games} games</p>
            </div>
            {/* After */}
            <div className={`rounded-xl border p-5 ${
              verdict === "improving" ? "border-emerald-500/20 bg-emerald-500/[0.03]" :
              verdict === "slipping" ? "border-red-500/15 bg-red-500/[0.02]" :
              "border-border bg-card"
            }`}>
              <p className="text-xs text-muted-foreground/50 uppercase tracking-wider mb-3">After training</p>
              <p className={`text-4xl font-mono font-bold mb-1 ${
                verdict === "improving" ? "text-emerald-500" :
                verdict === "slipping" ? "text-red-400" :
                "text-foreground"
              }`}>{post.mistakes}</p>
              <p className="text-xs text-muted-foreground">in {post.games} games</p>
            </div>
          </div>

          {/* Arrow between */}
          <div className="flex items-center justify-center mb-6">
            <div className="flex items-center gap-2">
              <span className="text-sm font-mono text-muted-foreground">{pre.mistakes}</span>
              <ArrowRight className="w-4 h-4 text-muted-foreground/40" />
              <span className={`text-sm font-mono font-bold ${verdictColor[verdict]}`}>{post.mistakes}</span>
            </div>
          </div>

          {/* Verdict — big, clear */}
          <p className={`text-xl font-heading font-semibold ${verdictColor[verdict]} text-center mb-8`}>
            {verdictText[verdict]}
          </p>

          {/* Recent games — proof dots */}
          {postGames.length > 0 && (
            <div className="mb-8">
              <p className="text-[10px] tracking-[0.15em] uppercase font-bold text-muted-foreground/40 mb-3">Recent games</p>
              <div className="flex items-center gap-2">
                {postGames.map((g, i) => (
                  <div key={i} className={`w-9 h-9 rounded-lg flex items-center justify-center ${
                    g.had_mistake
                      ? "bg-red-500/10 border border-red-500/15"
                      : "bg-emerald-500/10 border border-emerald-500/15"
                  }`} title={`vs ${g.opponent} — ${g.had_mistake ? "mistake" : "clean"}`}>
                    {g.had_mistake
                      ? <XIcon className="w-3.5 h-3.5 text-red-400" strokeWidth={2.5} />
                      : <Check className="w-3.5 h-3.5 text-emerald-500" strokeWidth={2.5} />
                    }
                  </div>
                ))}
              </div>
              <p className="text-[10px] text-muted-foreground/40 mt-2">
                {postGames.filter(g => !g.had_mistake).length} clean · {postGames.filter(g => g.had_mistake).length} with mistakes
              </p>
            </div>
          )}

          {/* Opening Repertoire */}
          {openings && openings.total_games > 0 && (
            <OpeningRepertoire openings={openings} navigate={navigate} />
          )}

          {/* Action */}
          <div className="space-y-3">
            {verdict === "improving" ? (
              <button onClick={() => navigate("/play-with-coach")}
                className="w-full py-4 text-[15px] font-semibold rounded-xl gradient-gold text-black hover:opacity-90 transition-all shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2">
                <Swords className="w-4 h-4" strokeWidth={2} />
                Keep going
                <ChevronRight className="w-4 h-4 opacity-60" />
              </button>
            ) : (
              <button onClick={() => navigate(progress.focus_pattern ? `/training?focus=${progress.focus_pattern}` : "/lab")}
                className="w-full py-4 text-[15px] font-semibold rounded-xl gradient-gold text-black hover:opacity-90 transition-all shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2">
                <Target className="w-4 h-4" strokeWidth={2} />
                Train more
                <ChevronRight className="w-4 h-4 opacity-60" />
              </button>
            )}

            <button onClick={() => navigate("/play-with-coach")}
              className="w-full py-3 text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center justify-center gap-1.5">
              <Swords className="w-3.5 h-3.5" strokeWidth={1.5} />
              Play with Coach
            </button>
          </div>

        </motion.div>
      </div>
    </Layout>
  );
};

// ─── Opening Repertoire Section ─────────────────────────────────

const STATUS_STYLES = {
  strong: "text-emerald-600 bg-emerald-50 border-emerald-200",
  learning: "text-amber-600 bg-amber-50 border-amber-200",
  weak: "text-red-500 bg-red-50 border-red-200",
  new: "text-blue-500 bg-blue-50 border-blue-200",
};

const OpeningRepertoire = ({ openings, navigate }) => {
  if (!openings || openings.total_games === 0) return null;

  // Find best opening per color
  const bestWhite = openings.white?.length > 0
    ? openings.white.reduce((a, b) => (b.win_rate > a.win_rate && b.games >= 3) ? b : a, openings.white[0])
    : null;
  const bestBlack = openings.black?.length > 0
    ? openings.black.reduce((a, b) => (b.win_rate > a.win_rate && b.games >= 3) ? b : a, openings.black[0])
    : null;

  const renderOpeningRow = (o, isBest) => (
    <div
      key={o.name}
      className={`flex items-center justify-between p-2.5 rounded-lg border ${
        isBest ? "border-emerald-200 bg-emerald-50/50" : "border-border bg-card"
      }`}
    >
      <div className="flex items-center gap-2 min-w-0 flex-1">
        {isBest && <Crown className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />}
        <span className="text-sm font-medium text-foreground truncate">{o.name}</span>
      </div>
      <div className="flex items-center gap-3 flex-shrink-0 ml-2">
        <span className="text-xs text-muted-foreground">{o.games}g</span>
        <span className={`text-xs font-mono font-bold ${
          o.win_rate >= 60 ? "text-emerald-600" :
          o.win_rate >= 45 ? "text-foreground" :
          "text-red-400"
        }`}>{o.win_rate}%</span>
        <span className={`px-1.5 py-0.5 rounded text-[10px] border ${STATUS_STYLES[o.status] || ""}`}>
          {o.status_label}
        </span>
      </div>
    </div>
  );

  const renderColorSection = (label, list, best) => {
    if (!list?.length) return null;
    return (
      <div>
        <p className="text-[10px] tracking-[0.15em] uppercase font-bold text-muted-foreground/40 mb-2">{label}</p>
        <div className="space-y-1.5">
          {list.slice(0, 5).map((o) => renderOpeningRow(o, best && o.name === best.name))}
        </div>
      </div>
    );
  };

  return (
    <div className="mb-8">
      <div className="flex items-center gap-2 mb-4">
        <BookOpen className="w-4 h-4 text-primary" />
        <p className="text-sm font-medium text-foreground">Your Openings</p>
      </div>

      <div className="space-y-4">
        {renderColorSection("As White", openings.white, bestWhite)}
        {renderColorSection("As Black", openings.black, bestBlack)}
      </div>

      {/* Coach recommendation */}
      {(bestWhite || bestBlack) && (
        <div className="mt-4 p-3 rounded-lg bg-primary/5 border border-primary/10">
          <p className="text-xs text-primary font-medium mb-1">Coach recommends</p>
          <p className="text-sm text-foreground">
            Stick with{" "}
            {bestWhite && <span className="font-semibold">{bestWhite.name}</span>}
            {bestWhite && bestBlack && " and "}
            {bestBlack && <span className="font-semibold">{bestBlack.name}</span>}
            . Master these and your rating will climb.
          </p>
          <button
            onClick={() => navigate("/play-with-coach")}
            className="mt-2 text-xs text-primary hover:text-primary/80 flex items-center gap-1 transition-colors"
          >
            <Swords className="w-3 h-3" />
            Practice with Coach
            <ChevronRight className="w-3 h-3" />
          </button>
        </div>
      )}
    </div>
  );
};

export default UnifiedProgress;
