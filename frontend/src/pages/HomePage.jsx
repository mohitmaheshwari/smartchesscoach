/**
 * HOME PAGE — Coach-First Dashboard
 * Shows: Coach message, review progress, last game, patterns, actions
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import { ChevronRight, Swords, Target, Import, BookOpen, FlaskConical, Check } from "lucide-react";

const HomePage = ({ user }) => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/home/dashboard-v2`, { credentials: "include" })
      .then(r => r.ok ? r.json() : null)
      .then(d => setData(d))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="w-5 h-5 border border-border border-t-foreground/50 rounded-full animate-spin" />
        </div>
      </Layout>
    );
  }

  const battle = data?.last_battle;
  const dna = data?.chess_dna;
  const fix = data?.one_thing_to_fix;
  const streak = data?.streak;
  const patterns = data?.patterns || [];
  const accuracy = data?.accuracy || 0;
  const gamesAnalyzed = data?.games_analyzed || 0;
  const review = data?.review_progress || {};

  const topPattern = patterns[0];
  const coachMessage = topPattern
    ? `${topPattern.label} is showing up in almost every game.`
    : fix?.fix_line || dna?.root_cause || "Let's review your recent games.";
  const coachSub = topPattern
    ? `${topPattern.recent_count} times recently. This is your biggest leak right now.`
    : fix?.stat_line || "";

  const primaryActionLabel = topPattern
    ? `Train ${topPattern.label}`
    : fix?.pattern ? `Train ${fix.pattern.replace(/_/g, " ")}` : "Train Calculation";
  const primaryActionHref = topPattern
    ? `/training?focus=${topPattern.pattern_type}`
    : `/training?focus=calculation_depth`;

  // Empty state
  if (!battle && gamesAnalyzed === 0) {
    return (
      <Layout user={user}>
        <div className="max-w-xl mx-auto px-4 py-16 text-center" data-testid="home-page">
          <h1 className="text-3xl text-foreground tracking-tight mb-3" style={{ fontFamily: "'Playfair Display', serif" }}>
            Welcome to ChessGuru
          </h1>
          <p className="text-muted-foreground mb-8 text-sm leading-relaxed">
            Import your games to get started. After 5 games, your coach will know your strengths.
            After 15, it'll know your weaknesses by name.
          </p>
          <div className="flex gap-3 justify-center">
            <button onClick={() => navigate("/import")} className="px-6 py-3 text-sm text-background bg-foreground rounded-lg hover:opacity-90 transition-opacity" data-testid="import-cta">
              <Import className="w-4 h-4 inline mr-2" strokeWidth={1.5} />
              Import Games
            </button>
            <button onClick={() => navigate("/play-with-coach")} className="px-6 py-3 text-sm text-foreground border border-border rounded-lg hover:bg-muted/50 transition-colors" data-testid="play-cta">
              <Swords className="w-4 h-4 inline mr-2" strokeWidth={1.5} />
              Play with Coach
            </button>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user}>
      <div className="max-w-3xl mx-auto px-4 py-6" data-testid="home-page">

        {/* ── COACH MESSAGE ── */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mb-6">
          {streak && streak.count >= 2 && (
            <p className="text-xs mb-2" style={{ fontFamily: "'JetBrains Mono', monospace", color: streak.type === "W" ? "#16a34a" : streak.type === "L" ? "#EF4444" : "#888" }}>
              {streak.count} {streak.type === "W" ? "wins" : streak.type === "L" ? "losses" : "draws"} in a row
            </p>
          )}
          <h1 className="text-2xl sm:text-3xl text-foreground tracking-tight leading-snug mb-1.5" style={{ fontFamily: "'Playfair Display', serif" }}>
            {coachMessage}
          </h1>
          {coachSub && <p className="text-sm text-muted-foreground">{coachSub}</p>}
        </motion.div>

        {/* ── REVIEW PROGRESS STRIP ── */}
        {review.pending > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="mb-6"
          >
            <div
              className="flex items-center gap-3 p-3.5 bg-card border border-border rounded-lg cursor-pointer hover:border-primary/30 transition-colors"
              onClick={() => navigate("/lab")}
              data-testid="review-progress-strip"
            >
              <FlaskConical className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0" strokeWidth={1.5} />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-foreground">
                  <strong>{review.pending}</strong> game{review.pending > 1 ? "s" : ""} waiting for review
                </p>
              </div>
              {/* Progress bar */}
              <div className="flex items-center gap-2">
                <div className="w-20 h-1.5 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-emerald-500 rounded-full transition-all"
                    style={{ width: `${review.total ? (review.reviewed / review.total) * 100 : 0}%` }}
                  />
                </div>
                <span className="text-[10px] text-muted-foreground" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  {review.reviewed}/{review.total}
                </span>
              </div>
              <ChevronRight className="w-4 h-4 text-muted-foreground/30 flex-shrink-0" />
            </div>
          </motion.div>
        )}

        {/* ── LAST GAME + ACTIONS ── */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }} className="mb-6">
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            {/* LAST GAME — 3/5 */}
            {battle && (
              <div className="md:col-span-3">
                <Label>Last Game</Label>
                <div
                  className="bg-card border border-border cursor-pointer transition-all duration-200 hover:border-primary/20 hover:shadow-sm rounded-lg overflow-hidden h-full"
                  onClick={() => navigate(`/game/${battle.game_id}`)}
                  data-testid="last-battle-card"
                >
                  <div className="flex h-full">
                    {battle.fen && (
                      <div className="w-[140px] sm:w-[160px] flex-shrink-0">
                        <LichessBoard fen={battle.fen} orientation={battle.user_color} viewOnly={true} />
                      </div>
                    )}
                    <div className="flex-1 p-4 flex flex-col justify-between min-w-0">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm text-muted-foreground">vs {battle.opponent}</span>
                          <ResultBadge result={battle.result} userColor={battle.user_color} />
                          {battle.opening && (
                            <span className="text-xs text-muted-foreground/50 hidden sm:inline">{battle.opening}</span>
                          )}
                        </div>
                        {/* Behavioral insight — the story of this game */}
                        {battle.lesson_label && (
                          <span className="inline-block text-[9px] font-bold uppercase tracking-[0.1em] text-amber-700 dark:text-amber-400 mr-1.5 mb-0.5">
                            {battle.lesson_label}
                          </span>
                        )}
                        <p className="text-sm text-foreground leading-snug">
                          {battle.behavior || dna?.root_cause || "Review this game"}
                        </p>
                      </div>
                      {battle.move_number > 0 && battle.your_move && (
                        <div className="flex items-center gap-2 mt-3 text-[10px]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                          <span className="text-muted-foreground">Move {battle.move_number}</span>
                          <span className="text-red-500 font-medium">{battle.your_move}</span>
                          <span className="text-muted-foreground/40">→</span>
                          <span className="text-emerald-600 font-medium">{battle.best_move}</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ACTIONS — 2/5 */}
            <div className={battle ? "md:col-span-2" : "md:col-span-5"}>
              <Label>Actions</Label>
              <div className="bg-card border border-border rounded-lg overflow-hidden h-full flex flex-col">
                <div
                  className="p-4 cursor-pointer transition-opacity hover:opacity-90 flex items-center gap-3 bg-foreground text-background"
                  onClick={() => navigate(primaryActionHref)}
                  data-testid="primary-action"
                >
                  <Target className="w-4 h-4 flex-shrink-0 opacity-70" strokeWidth={1.5} />
                  <span className="text-sm flex-1">{primaryActionLabel}</span>
                  <ChevronRight className="w-4 h-4 opacity-50" strokeWidth={1.5} />
                </div>
                <ActionRow icon={Swords} label="Play with Coach" onClick={() => navigate("/play-with-coach")} testId="play-action" />
                <ActionRow icon={BookOpen} label="Study Openings" onClick={() => navigate("/openings-overview")} testId="openings-action" />
                <ActionRow icon={FlaskConical} label="Review in Lab" onClick={() => navigate("/lab")} testId="lab-action" />
              </div>
            </div>
          </div>
        </motion.div>

        {/* ── PATTERNS + CHESS DNA ── */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 }} className="mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {patterns.length > 0 && (
              <div>
                <Label>Patterns Across Games</Label>
                <div className="bg-card border border-border rounded-lg overflow-hidden divide-y divide-border">
                  {patterns.map((p) => (
                    <div
                      key={p.pattern_type}
                      className="flex items-center justify-between px-4 py-3 cursor-pointer transition-colors hover:bg-muted/30"
                      onClick={() => navigate(`/training?focus=${p.pattern_type}`)}
                      data-testid={`pattern-${p.pattern_type}`}
                    >
                      <div className="flex items-center gap-2.5">
                        <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${p.severity === "critical" || p.severity === "high" ? "bg-red-500" : "bg-amber-500"}`} />
                        <span className="text-sm text-foreground">{p.label}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{p.recent_count}x</span>
                        <SeverityBadge severity={p.severity} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {dna && (
              <div>
                <Label>Your Chess DNA</Label>
                <div className="bg-card border border-border rounded-lg p-4 h-full">
                  <span className="text-sm text-muted-foreground">{dna.archetype || "Developing"}</span>
                  <div className="mt-3 mb-2">
                    <span className="text-[9px] tracking-[0.15em] uppercase font-bold text-red-600 dark:text-red-400">Biggest Leak</span>
                    <p className="text-base text-foreground tracking-tight mt-0.5" style={{ fontFamily: "'Playfair Display', serif" }}>
                      {dna.diagnosis?.replace(/_/g, " ") || "—"}
                    </p>
                  </div>
                  {dna.after_line && <p className="text-xs text-muted-foreground leading-relaxed">{dna.after_line}</p>}
                </div>
              </div>
            )}
          </div>
        </motion.div>

        {/* ── FOOTER STATS ── */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.15 }}
          className="flex items-center justify-between text-muted-foreground/50 mt-8 pt-3 border-t border-border"
        >
          <span className="text-[10px]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{gamesAnalyzed} games</span>
          {accuracy > 0 && <span className="text-[10px]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{accuracy.toFixed(0)}% avg accuracy</span>}
        </motion.div>
      </div>
    </Layout>
  );
};

// ── Reusable Components ──

const Label = ({ children }) => (
  <p className="text-[10px] tracking-[0.15em] uppercase mb-2 font-bold text-muted-foreground">{children}</p>
);

const ActionRow = ({ icon: Icon, label, onClick, testId }) => (
  <div className="p-3.5 cursor-pointer transition-colors hover:bg-muted/30 flex items-center gap-3 border-t border-border" onClick={onClick} data-testid={testId}>
    <Icon className="w-4 h-4 flex-shrink-0 text-muted-foreground" strokeWidth={1.5} />
    <span className="text-sm text-foreground flex-1">{label}</span>
    <ChevronRight className="w-4 h-4 text-muted-foreground/20" strokeWidth={1.5} />
  </div>
);

const ResultBadge = ({ result, userColor }) => {
  const won = (result === "1-0" && userColor === "white") || (result === "0-1" && userColor === "black");
  const draw = (result || "").includes("1/2");
  const cls = won ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20"
    : draw ? "bg-muted text-muted-foreground border-border"
    : "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20";
  return <span className={`text-[10px] px-1.5 py-0.5 font-semibold rounded border ${cls}`}>{won ? "WON" : draw ? "DRAW" : "LOST"}</span>;
};

const SeverityBadge = ({ severity }) => {
  const high = severity === "critical" || severity === "high";
  return (
    <span className={`text-[9px] px-1.5 py-0.5 uppercase font-semibold rounded ${
      high ? "bg-red-500/10 text-red-600 dark:text-red-400" : "bg-amber-500/10 text-amber-700 dark:text-amber-400"
    }`}>
      {high ? "HIGH" : "MED"}
    </span>
  );
};

export default HomePage;
