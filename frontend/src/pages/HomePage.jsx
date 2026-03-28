/**
 * HOME PAGE — V4
 * 
 * The coach talks to you. One clear message. One clear action.
 * Less data, more direction.
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
  const streak = data?.streak;
  const patterns = data?.patterns || [];
  const accuracy = data?.accuracy || 0;
  const gamesAnalyzed = data?.games_analyzed || 0;

  // Build the coach message — personal, direct, actionable
  const coachMessage = buildCoachMessage(streak, battle, dna, fix, patterns);

  // No games state
  if (!battle && gamesAnalyzed === 0) {
    return (
      <Layout user={user}>
        <div className="max-w-4xl mx-auto px-6 py-16" data-testid="home-page">
          <div className="max-w-lg">
            <h1 className="text-4xl text-foreground tracking-tight font-heading mb-4">
              Welcome to ChessGuru
            </h1>
            <p className="text-muted-foreground mb-8">
              Import your games to get started. After 5 games, your coach will know your strengths. After 15, it'll know your weaknesses by name.
            </p>
            <div className="flex gap-3">
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
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user}>
      <div className="max-w-4xl mx-auto px-6 py-8" data-testid="home-page">

        {/* ── COACH MESSAGE ── */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mb-10">
          <p className="text-2xl text-foreground font-heading leading-relaxed max-w-2xl">
            {coachMessage.headline}
          </p>
          {coachMessage.subtext && (
            <p className="text-sm text-muted-foreground mt-2 max-w-xl">{coachMessage.subtext}</p>
          )}
        </motion.div>

        {/* ── TWO COLUMNS: Board + Actions ── */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 mb-10">

          {/* LEFT: Last Game Board (3 cols) */}
          {battle && (
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="lg:col-span-3"
            >
              <SectionLabel>Last Game</SectionLabel>
              <div
                className="bg-card border border-border rounded-sm overflow-hidden cursor-pointer hover:shadow-sm transition-all mt-2"
                onClick={() => navigate(`/game/${battle.game_id}`)}
                data-testid="last-battle-card"
              >
                <div className="grid grid-cols-2">
                  <div className="aspect-square">
                    <LichessBoard fen={battle.fen} orientation={battle.user_color} viewOnly={true} />
                  </div>
                  <div className="p-5 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-sm text-muted-foreground">vs {battle.opponent}</span>
                        <ResultBadge result={battle.result} userColor={battle.user_color} />
                      </div>
                      <p className="text-sm text-foreground leading-relaxed">
                        {dna?.root_cause || "Review this game"}
                      </p>
                    </div>
                    <div>
                      <div className="flex items-center gap-1.5 mb-3">
                        <span className="text-[10px] text-muted-foreground font-mono">Move {battle.move_number}</span>
                        <span className="text-[10px] font-mono" style={{ color: WINE }}>{battle.your_move}</span>
                        <ArrowRight className="w-2.5 h-2.5 text-muted-foreground/30" />
                        <span className="text-[10px] font-mono text-emerald-600">{battle.best_move}</span>
                      </div>
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        Review game <ChevronRight className="w-3 h-3" />
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* RIGHT: Actions (2 cols) */}
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="lg:col-span-2 space-y-3"
          >
            {/* Primary action — contextual */}
            <ActionCard
              label={coachMessage.action_label}
              description={coachMessage.action_desc}
              onClick={() => navigate(coachMessage.action_href)}
              primary
              testId="primary-action"
            />

            {/* Secondary actions */}
            <ActionCard
              label="Play with Coach"
              description="Real-time feedback on every move"
              icon={<Swords className="w-4 h-4" strokeWidth={1.5} />}
              onClick={() => navigate("/play-with-coach")}
              testId="play-action"
            />

            <ActionCard
              label="Study Openings"
              description="Your repertoire + endgame lessons"
              icon={<BookOpen className="w-4 h-4" strokeWidth={1.5} />}
              onClick={() => navigate("/openings-overview")}
              testId="study-action"
            />
          </motion.div>
        </div>

        {/* ── PATTERNS + DNA row ── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">
          {/* Patterns */}
          {patterns.length > 0 && (
            <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
              <SectionLabel>Patterns Across Games</SectionLabel>
              <div className="bg-card border border-border rounded-sm divide-y divide-border mt-2">
                {patterns.map((p) => (
                  <div
                    key={p.pattern_type}
                    className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-muted/30 transition-colors"
                    onClick={() => navigate(`/training?focus=${p.pattern_type}`)}
                    data-testid={`pattern-${p.pattern_type}`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-1.5 h-1.5 rounded-full" style={{ background: p.severity === "critical" ? WINE : "#CBA135" }} />
                      <span className="text-sm text-foreground">{p.label}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono" style={{ color: p.severity === "critical" ? WINE : GOLD_TEXT }}>{p.recent_count}x</span>
                      <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/30" strokeWidth={1.5} />
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          {/* Chess DNA */}
          {dna && (
            <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}>
              <SectionLabel>Your Chess DNA</SectionLabel>
              <div className="bg-card border border-border rounded-sm p-4 mt-2 h-[calc(100%-24px)] flex flex-col justify-between">
                <div>
                  <h2 className="text-xl text-foreground font-heading">{dna.archetype}</h2>
                  <p className="text-xs text-muted-foreground mt-2">{dna.before_line}</p>
                  <p className="text-xs text-foreground mt-0.5">{dna.after_line}</p>
                </div>
                {fix && (
                  <div className="mt-4 pt-3 border-t border-border cursor-pointer hover:bg-muted/20 -mx-4 px-4 -mb-4 pb-4 transition-colors rounded-b-sm"
                    onClick={() => navigate("/training")}
                  >
                    <p className="text-xs text-muted-foreground">{fix.stat_line}</p>
                    {fix.diff_line && (
                      <p className="text-sm text-emerald-600 mt-0.5 font-heading">{fix.diff_line}</p>
                    )}
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </div>

        {/* ── FOOTER ── */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}
          className="flex items-center justify-between text-muted-foreground/50 pt-3 border-t border-border">
          <span className="text-[10px] font-mono">{gamesAnalyzed} games</span>
          <span className="text-[10px] font-mono">{accuracy.toFixed(0)}% accuracy</span>
        </motion.div>
      </div>
    </Layout>
  );
};

// Build the coach's personal greeting
function buildCoachMessage(streak, battle, dna, fix, patterns) {
  const hour = new Date().getHours();
  const timeGreet = hour < 12 ? "Morning" : hour < 17 ? "Afternoon" : "Evening";

  let headline = `${timeGreet}. Let's get better today.`;
  let subtext = null;
  let action_label = "Train Your Weakness";
  let action_desc = "Positions from your games";
  let action_href = "/training";

  // Streak-based messaging
  if (streak?.count >= 3 && streak?.type === "L") {
    headline = `${streak.count} losses in a row. Stop playing. Start reviewing.`;
    subtext = "Playing more when you're losing makes it worse. Let's look at what's going wrong.";
    action_label = "Review Your Losses";
    action_desc = "The coach picked one for you";
    action_href = "/lab";
  } else if (streak?.count >= 3 && streak?.type === "W") {
    headline = `${streak.count} wins in a row. Momentum is real.`;
    if (battle && dna?.diagnosis === "WON_OPPONENT_BLUNDER") {
      subtext = "But those wins had blunders. Clean up now while you're confident.";
      action_label = "Train Calculation";
      action_desc = `${patterns[0]?.recent_count || ""}x recently — fix it while you're sharp`;
      action_href = `/training?focus=${patterns[0]?.pattern_type || "calculation_depth"}`;
    } else {
      subtext = "Keep the focus. Don't get sloppy.";
    }
  }
  // Pattern-based
  else if (patterns.length > 0 && patterns[0]?.severity === "critical") {
    const p = patterns[0];
    headline = `${p.label} is showing up in almost every game.`;
    subtext = `${p.recent_count} times recently. This is your biggest leak right now.`;
    action_label = `Train ${p.label}`;
    action_desc = "Positions where this pattern appeared";
    action_href = `/training?focus=${p.pattern_type}`;
  }
  // Last game based
  else if (battle) {
    const won = (battle.result === "1-0" && battle.user_color === "white") || (battle.result === "0-1" && battle.user_color === "black");
    if (!won) {
      headline = `Last game didn't go well. Let's see why.`;
      action_label = "Review This Loss";
      action_desc = dna?.root_cause?.slice(0, 50) || "Understand what went wrong";
      action_href = `/game/${battle.game_id}`;
    }
  }

  // Fix action for when there's a specific fix
  if (fix && fix.diff_line && action_href === "/training") {
    action_desc = fix.diff_line;
  }

  return { headline, subtext, action_label, action_desc, action_href };
}

const SectionLabel = ({ children }) => (
  <p className="text-[10px] tracking-[0.2em] uppercase font-mono" style={{ color: GOLD_TEXT }}>{children}</p>
);

const ResultBadge = ({ result, userColor }) => {
  const won = (result === "1-0" && userColor === "white") || (result === "0-1" && userColor === "black");
  const draw = (result || "").includes("1/2");
  return (
    <span className="text-[10px] px-1.5 py-0.5 font-mono rounded-sm" style={{
      background: won ? "rgba(22,163,74,0.1)" : draw ? "rgba(0,0,0,0.05)" : `${WINE}15`,
      color: won ? "#16a34a" : draw ? "#888" : WINE,
    }}>
      {won ? "WON" : draw ? "DRAW" : "LOST"}
    </span>
  );
};

const ActionCard = ({ label, description, icon, onClick, primary, testId }) => (
  <div
    className={`p-4 rounded-sm cursor-pointer transition-all hover:shadow-sm flex items-center gap-3 ${
      primary
        ? "text-white"
        : "bg-card border border-border text-foreground hover:bg-muted/30"
    }`}
    style={primary ? { background: WINE } : undefined}
    onClick={onClick}
    data-testid={testId}
  >
    {icon && <div className="flex-shrink-0 opacity-60">{icon}</div>}
    {!icon && primary && <Target className="w-4 h-4 flex-shrink-0 opacity-70" strokeWidth={1.5} />}
    <div className="flex-1 min-w-0">
      <p className="text-sm font-medium">{label}</p>
      {description && <p className={`text-xs mt-0.5 ${primary ? "text-white/60" : "text-muted-foreground"}`}>{description}</p>}
    </div>
    <ChevronRight className="w-4 h-4 flex-shrink-0 opacity-40" strokeWidth={1.5} />
  </div>
);

export default HomePage;
