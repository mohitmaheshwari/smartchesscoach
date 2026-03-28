/**
 * HOME PAGE — Coach-First Dashboard
 * 
 * Layout spec:
 * 1. COACH MESSAGE (top, bold Playfair)
 * 2. LAST GAME (3/5) + ACTIONS (2/5) side-by-side
 * 3. PATTERNS (1/2) + CHESS DNA (1/2) side-by-side
 * 4. Footer stats
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import { ChevronRight, Swords, Target, ArrowRight, Import, BookOpen } from "lucide-react";

const WINE = "#722F37";
const GOLD_TEXT = "#8B6F1F";

const HomePage = ({ user }) => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch(`${API}/home/dashboard-v2`, { credentials: "include" });
        if (res.ok) setData(await res.json());
      } catch (e) {
        console.error("Home fetch error:", e);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
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
  const action = data?.context_action;
  const streak = data?.streak;
  const patterns = data?.patterns || [];
  const accuracy = data?.accuracy || 0;
  const gamesAnalyzed = data?.games_analyzed || 0;

  // No games state
  if (!battle && gamesAnalyzed === 0) {
    return (
      <Layout user={user}>
        <div className="max-w-xl mx-auto px-4 py-16 text-center" data-testid="home-page">
          <h1 className="text-3xl text-foreground tracking-tight mb-3" style={{ fontFamily: "'Playfair Display', serif" }}>
            Welcome to ChessGuru
          </h1>
          <p className="text-muted-foreground mb-8 font-light">
            Import your games to get started. After 5 games, your coach will know your strengths. After 15, it'll know your weaknesses by name.
          </p>
          <div className="flex gap-3 justify-center">
            <button onClick={() => navigate("/import")} className="px-6 py-3 text-sm text-white rounded-sm" style={{ background: WINE }} data-testid="import-cta">
              <Import className="w-4 h-4 inline mr-2" strokeWidth={1.5} />
              Import Games
            </button>
            <button onClick={() => navigate("/play-with-coach")} className="px-6 py-3 text-sm text-foreground border border-border rounded-sm" data-testid="play-cta">
              <Swords className="w-4 h-4 inline mr-2" strokeWidth={1.5} />
              Play with Coach
            </button>
          </div>
        </div>
      </Layout>
    );
  }

  // Build coach message from patterns or fix data
  const topPattern = patterns.length > 0 ? patterns[0] : null;
  const coachMessageMain = topPattern
    ? `${topPattern.label} is showing up in almost every game.`
    : fix?.fix_line || "Let's review your recent games.";
  const coachMessageSub = topPattern
    ? `${topPattern.recent_count} times recently. This is your biggest leak right now.`
    : fix?.stat_line || "";

  // Dynamic primary action label
  const primaryActionLabel = topPattern
    ? `Train ${topPattern.label}`
    : fix?.pattern
      ? `Train ${fix.pattern.replace(/_/g, " ")}`
      : "Train Calculation";
  const primaryActionHref = topPattern
    ? `/training?focus=${topPattern.pattern_type}`
    : `/training?focus=calculation_depth`;

  return (
    <Layout user={user}>
      <div className="max-w-3xl mx-auto px-4 py-6" data-testid="home-page">

        {/* ═══════════════════════════════════════════════════
            COACH MESSAGE
        ═══════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          {/* Streak indicator */}
          {streak && streak.count >= 2 && (
            <p className="text-xs font-mono mb-3" style={{
              color: streak.type === "W" ? "#16a34a" : streak.type === "L" ? WINE : "#888"
            }}>
              {streak.count} {streak.type === "W" ? "wins" : streak.type === "L" ? "losses" : "draws"} in a row
            </p>
          )}

          <h1
            className="text-2xl sm:text-3xl text-foreground tracking-tight leading-snug mb-2"
            style={{ fontFamily: "'Playfair Display', serif" }}
          >
            {coachMessageMain}
          </h1>
          {coachMessageSub && (
            <p className="text-sm text-muted-foreground font-light">{coachMessageSub}</p>
          )}
        </motion.div>

        {/* ═══════════════════════════════════════════════════
            LAST GAME (3/5) + ACTIONS (2/5)
        ═══════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="mb-6"
        >
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            {/* LAST GAME — 3/5 */}
            {battle && (
              <div className="md:col-span-3">
                <SectionLabel>Last Game</SectionLabel>
                <div
                  className="bg-white border border-border cursor-pointer transition-all duration-200 hover:shadow-sm rounded-sm overflow-hidden h-full"
                  onClick={() => navigate(`/game/${battle.game_id}`)}
                  data-testid="last-battle-card"
                  style={{ borderColor: "hsl(35 10% 87%)" }}
                >
                  <div className="flex h-full">
                    <div className="w-[140px] sm:w-[160px] flex-shrink-0">
                      <LichessBoard fen={battle.fen} orientation={battle.user_color} viewOnly={true} />
                    </div>
                    <div className="flex-1 p-4 flex flex-col justify-between min-w-0">
                      <div>
                        <div className="flex items-center gap-2 mb-1.5">
                          <span className="text-sm text-muted-foreground font-light">vs {battle.opponent}</span>
                          <ResultBadge result={battle.result} userColor={battle.user_color} />
                        </div>
                        <p className="text-sm text-foreground leading-snug font-light">
                          {dna?.root_cause || "Review this game"}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 mt-3">
                        <span className="text-[10px] text-muted-foreground font-mono">Move {battle.move_number}</span>
                        <span className="text-[10px] font-mono" style={{ color: WINE }}>{battle.your_move}</span>
                        <ArrowRight className="w-2.5 h-2.5 text-border" />
                        <span className="text-[10px] font-mono text-emerald-600">{battle.best_move}</span>
                        <span className="text-[10px] text-muted-foreground/60 ml-auto font-mono">Review ›</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ACTIONS — 2/5 */}
            <div className={battle ? "md:col-span-2" : "md:col-span-5"}>
              <SectionLabel>Actions</SectionLabel>
              <div className="bg-white border border-border rounded-sm h-full flex flex-col justify-between" style={{ borderColor: "hsl(35 10% 87%)" }}>
                {/* Primary CTA */}
                <div
                  className="p-4 cursor-pointer transition-all duration-200 hover:opacity-90 flex items-center gap-3 text-white rounded-t-sm"
                  style={{ background: WINE }}
                  onClick={() => navigate(primaryActionHref)}
                  data-testid="primary-action"
                >
                  <Target className="w-4 h-4 flex-shrink-0 opacity-80" strokeWidth={1.5} />
                  <span className="text-sm font-light flex-1">{primaryActionLabel}</span>
                  <ChevronRight className="w-4 h-4 opacity-60" strokeWidth={1.5} />
                </div>

                <div className="border-t border-border" style={{ borderColor: "hsl(35 10% 87%)" }} />

                {/* Play with Coach */}
                <div
                  className="p-4 cursor-pointer transition-colors hover:bg-black/[0.02] flex items-center gap-3"
                  onClick={() => navigate("/play-with-coach")}
                  data-testid="play-action"
                >
                  <Swords className="w-4 h-4 flex-shrink-0 text-muted-foreground" strokeWidth={1.5} />
                  <span className="text-sm text-foreground font-light flex-1">Play with Coach</span>
                  <ChevronRight className="w-4 h-4 text-muted-foreground/30" strokeWidth={1.5} />
                </div>

                <div className="border-t border-border" style={{ borderColor: "hsl(35 10% 87%)" }} />

                {/* Study Openings */}
                <div
                  className="p-4 cursor-pointer transition-colors hover:bg-black/[0.02] flex items-center gap-3"
                  onClick={() => navigate("/openings-overview")}
                  data-testid="openings-action"
                >
                  <BookOpen className="w-4 h-4 flex-shrink-0 text-muted-foreground" strokeWidth={1.5} />
                  <span className="text-sm text-foreground font-light flex-1">Study Openings</span>
                  <ChevronRight className="w-4 h-4 text-muted-foreground/30" strokeWidth={1.5} />
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        {/* ═══════════════════════════════════════════════════
            PATTERNS (1/2) + CHESS DNA (1/2) — side by side
        ═══════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="mb-6"
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* PATTERNS ACROSS GAMES */}
            {patterns.length > 0 && (
              <div>
                <SectionLabel>Patterns Across Games</SectionLabel>
                <div className="bg-white border border-border rounded-sm h-full" style={{ borderColor: "hsl(35 10% 87%)" }}>
                  <div className="divide-y divide-border" style={{ "--tw-divide-opacity": 1, borderColor: "hsl(35 10% 87%)" }}>
                    {patterns.map((p) => (
                      <div
                        key={p.pattern_type}
                        className="flex items-center justify-between px-4 py-3 cursor-pointer transition-colors hover:bg-black/[0.02]"
                        onClick={() => navigate(`/training?focus=${p.pattern_type}`)}
                        data-testid={`pattern-${p.pattern_type}`}
                      >
                        <div className="flex items-center gap-2.5">
                          <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{
                            background: p.severity === "critical" ? WINE : "#CBA135"
                          }} />
                          <span className="text-sm text-foreground font-light">{p.label}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-muted-foreground font-mono">{p.recent_count}x</span>
                          <SeverityBadge severity={p.severity} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* YOUR CHESS DNA */}
            {dna && (
              <div>
                <SectionLabel>Your Chess DNA</SectionLabel>
                <div className="bg-white border border-border rounded-sm h-full" style={{ borderColor: "hsl(35 10% 87%)" }}>
                  <div className="p-4">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-sm text-muted-foreground font-light">
                        {dna.archetype || "Developing"}
                      </span>
                    </div>

                    <div className="mb-3">
                      <span className="text-[9px] tracking-[0.15em] uppercase font-mono" style={{ color: WINE }}>
                        Biggest Leak
                      </span>
                      <p className="text-base text-foreground tracking-tight mt-0.5" style={{ fontFamily: "'Playfair Display', serif" }}>
                        {dna.diagnosis?.replace(/_/g, " ") || "—"}
                      </p>
                    </div>

                    {dna.before_line && (
                      <p className="text-xs text-muted-foreground font-light mb-0.5">
                        Before: {dna.before_line}
                      </p>
                    )}
                    {dna.after_line && (
                      <p className="text-xs text-foreground font-light">
                        After: {dna.after_line}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* If no DNA but patterns exist, fill the second column */}
            {!dna && patterns.length > 0 && fix && (
              <div>
                <SectionLabel>If You Fixed One Thing</SectionLabel>
                <div
                  className="bg-white border border-border rounded-sm h-full cursor-pointer transition-all duration-200 hover:shadow-sm"
                  style={{ borderColor: "hsl(35 10% 87%)" }}
                  onClick={() => navigate(primaryActionHref)}
                >
                  <div className="p-4">
                    <p className="text-xs text-muted-foreground font-light mb-1">{fix.stat_line}</p>
                    <p className="text-sm text-foreground font-light" style={{ fontFamily: "'Playfair Display', serif" }}>
                      {fix.fix_line}
                    </p>
                    {fix.diff_line && (
                      <p className="text-base mt-2 text-emerald-600" style={{ fontFamily: "'Playfair Display', serif" }}>
                        {fix.diff_line}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </motion.div>

        {/* ═══════════════════════════════════════════════════
            FOOTER STATS
        ═══════════════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.15 }}
          className="flex items-center justify-between text-muted-foreground/60 mt-8 pt-3 border-t"
          style={{ borderColor: "hsl(35 10% 87%)" }}
        >
          <span className="text-[10px] font-mono">{gamesAnalyzed} games</span>
          <span className="text-[10px] font-mono">{accuracy.toFixed(0)}% accuracy</span>
        </motion.div>
      </div>
    </Layout>
  );
};

// ── Reusable Components ──

const SectionLabel = ({ children }) => (
  <p
    className="text-[10px] tracking-[0.2em] uppercase mb-2 font-mono"
    style={{ color: GOLD_TEXT }}
  >
    {children}
  </p>
);

const ResultBadge = ({ result, userColor }) => {
  const won = (result === "1-0" && userColor === "white") || (result === "0-1" && userColor === "black");
  const draw = (result || "").includes("1/2");
  return (
    <span
      className="text-[10px] px-1.5 py-0.5 font-mono rounded-sm"
      style={{
        background: won ? "rgba(22,163,74,0.1)" : draw ? "rgba(0,0,0,0.05)" : `rgba(114,47,55,0.08)`,
        color: won ? "#16a34a" : draw ? "#888" : WINE,
      }}
    >
      {won ? "WON" : draw ? "DRAW" : "LOST"}
    </span>
  );
};

const SeverityBadge = ({ severity }) => {
  const isCrit = severity === "critical";
  return (
    <span
      className="text-[9px] px-1.5 py-0.5 uppercase font-mono rounded-sm"
      style={{
        background: isCrit ? "rgba(114,47,55,0.06)" : "rgba(203,161,53,0.1)",
        color: isCrit ? WINE : GOLD_TEXT,
      }}
    >
      {isCrit ? "CRIT" : severity?.toUpperCase() || "MED"}
    </span>
  );
};

export default HomePage;
