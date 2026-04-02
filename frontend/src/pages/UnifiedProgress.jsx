/**
 * PROGRESS PAGE — Coaching Progress Report
 * 
 * Not a dashboard. A coach telling you: "Here's how you're doing."
 * 
 * Sections:
 * 1. Header with coaching headline
 * 2. Accuracy Journey chart (clickable dots)
 * 3. Win Rate + Blunder Trend (with correct insights)
 * 4. Danger Zones (clickable patterns)
 * 5. Review Progress (games reviewed, concepts learned)
 * 6. Chess Identity
 * 7. Last 10 Games bar chart
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { TrendingUp, TrendingDown, Minus, AlertTriangle, ChevronRight, FlaskConical, Check } from "lucide-react";

const UnifiedProgress = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [homeData, setHomeData] = useState(null);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/progress/journey`, { credentials: "include" }).then(r => r.ok ? r.json() : null),
      fetch(`${API}/home/dashboard-v2`, { credentials: "include" }).then(r => r.ok ? r.json() : null),
    ]).then(([j, h]) => { setData(j); setHomeData(h); })
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

  const journey = data?.journey || [];
  const winTrend = data?.win_trend;
  const currentAccuracy = data?.current_accuracy || 0;
  const gamesAnalyzed = data?.games_analyzed || 0;
  const patterns = homeData?.patterns || [];
  const dna = homeData?.chess_dna;
  const review = homeData?.review_progress || {};

  // Accuracy trend
  const recentAcc = journey.slice(-10).map(g => g.accuracy);
  const olderAcc = journey.slice(-20, -10).map(g => g.accuracy);
  const recentAvg = recentAcc.length ? recentAcc.reduce((a, b) => a + b, 0) / recentAcc.length : 0;
  const olderAvg = olderAcc.length ? olderAcc.reduce((a, b) => a + b, 0) / olderAcc.length : 0;
  const accDelta = recentAvg - olderAvg;
  const accImproving = accDelta > 2;
  const accDeclining = accDelta < -2;

  // Blunder trend
  const recentGames = journey.slice(-10);
  const prevGames = journey.slice(-20, -10);
  const recentBlunderAvg = recentGames.length ? recentGames.reduce((s, g) => s + (g.blunders || 0), 0) / recentGames.length : 0;
  const prevBlunderAvg = prevGames.length ? prevGames.reduce((s, g) => s + (g.blunders || 0), 0) / prevGames.length : 0;
  const blundersRising = recentBlunderAvg > prevBlunderAvg + 0.2;
  const blundersDropping = recentBlunderAvg < prevBlunderAvg - 0.2;

  // Win rate — compare RATES not absolutes
  const recentWinRate = winTrend?.recent?.total ? (winTrend.recent.wins / winTrend.recent.total * 100) : 0;
  const prevWinRate = winTrend?.previous?.total ? (winTrend.previous.wins / winTrend.previous.total * 100) : 0;
  const winRateImproving = recentWinRate > prevWinRate + 5;
  const winRateDeclining = recentWinRate < prevWinRate - 5;

  // Headline — the coaching insight
  const headline = accImproving
    ? "Your accuracy is climbing. Keep this up."
    : accDeclining
      ? "Your accuracy has dipped. Slow down, review more."
      : blundersRising
        ? "Blunders are creeping up. Check threats before every move."
        : winRateDeclining
          ? "Win rate is dropping. Focus on the Lab before playing more."
          : "Steady progress. Keep reviewing your games.";

  const last10 = journey.slice(-10);

  return (
    <Layout user={user}>
      <div className="max-w-3xl mx-auto px-4 py-6" data-testid="progress-page">

        {/* ── HEADER ── */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mb-8">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl text-foreground tracking-tight mb-1.5" style={{ fontFamily: "'Playfair Display', serif" }}>
                Progress
              </h1>
              <p className="text-sm text-muted-foreground leading-relaxed" data-testid="progress-headline">{headline}</p>
            </div>
            {currentAccuracy > 0 && (
              <div className="text-right flex-shrink-0 ml-4">
                <p className="text-2xl text-foreground font-light" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  {currentAccuracy.toFixed(0)}%
                </p>
                <div className="flex items-center gap-1 justify-end">
                  {accImproving && <TrendingUp className="w-3 h-3 text-emerald-500" />}
                  {accDeclining && <TrendingDown className="w-3 h-3 text-red-500" />}
                  {!accImproving && !accDeclining && <Minus className="w-3 h-3 text-muted-foreground/40" />}
                  <span className="text-[10px] text-muted-foreground" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                    avg accuracy
                  </span>
                </div>
              </div>
            )}
          </div>
        </motion.div>

        {/* ── ACCURACY JOURNEY ── */}
        {journey.length > 3 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }} className="mb-8">
            <Label>Your Accuracy Journey</Label>
            <div className="bg-card border border-border rounded-lg p-4">
              <JourneyChart journey={journey} onGameClick={(g) => navigate(`/game/${g.game_id}`)} />
            </div>
            {olderAcc.length > 0 && (
              <p className="text-[10px] text-muted-foreground mt-2" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                {accImproving
                  ? `${olderAvg.toFixed(0)}% → ${recentAvg.toFixed(0)}% last 10 games`
                  : accDeclining
                    ? `${olderAvg.toFixed(0)}% → ${recentAvg.toFixed(0)}% — slipping`
                    : `~${recentAvg.toFixed(0)}% steady`
                }
              </p>
            )}
          </motion.div>
        )}

        {/* ── WIN RATE + BLUNDERS ── */}
        {journey.length > 3 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="mb-8">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Win Rate */}
              {winTrend && (
                <div>
                  <Label>Win Rate</Label>
                  <div className="bg-card border border-border rounded-lg p-4 h-full">
                    <div className="flex items-center gap-3 mb-2.5">
                      <span className="text-foreground font-medium" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                        <span className="text-emerald-600">{winTrend.recent.wins}W</span>{" "}
                        <span className="text-red-500">{winTrend.recent.losses}L</span>
                      </span>
                      <span className="text-xs text-muted-foreground/40">last {winTrend.recent.total}</span>
                      {winRateImproving && <TrendingUp className="w-3.5 h-3.5 text-emerald-500 ml-auto" />}
                      {winRateDeclining && <TrendingDown className="w-3.5 h-3.5 text-red-500 ml-auto" />}
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {winRateImproving
                        ? "You're winning more. Lessons are translating to results."
                        : winRateDeclining
                          ? `Win rate dropped from ${prevWinRate.toFixed(0)}% to ${recentWinRate.toFixed(0)}%. Review losses before playing more.`
                          : "Win rate is holding. Consistency matters."
                      }
                    </p>
                  </div>
                </div>
              )}

              {/* Blunder Trend */}
              <div>
                <Label style={blundersRising ? { color: "rgb(239 68 68)" } : {}}>
                  {blundersRising ? "Blunders Rising" : "Blunder Rate"}
                </Label>
                <div className={`bg-card border rounded-lg p-4 h-full ${blundersRising ? "border-red-500/30" : "border-border"}`}>
                  <div className="flex items-center gap-3 mb-2.5">
                    <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      <span className="text-muted-foreground">{prevBlunderAvg.toFixed(1)}/g</span>
                      <span className="text-muted-foreground/30 mx-1.5">→</span>
                      <span className={blundersRising ? "text-red-500 font-medium" : "text-foreground"}>
                        {recentBlunderAvg.toFixed(1)}/g
                      </span>
                    </span>
                    {blundersRising && <AlertTriangle className="w-3.5 h-3.5 text-red-500 ml-auto" />}
                    {blundersDropping && <TrendingDown className="w-3.5 h-3.5 text-emerald-500 ml-auto" />}
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {blundersRising
                      ? "Blunders are climbing. Slow down. Check threats before every move."
                      : blundersDropping
                        ? "Blunders dropping. Your awareness is improving."
                        : "Blunder rate steady. Awareness drills could help."
                    }
                  </p>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* ── DANGER ZONES ── */}
        {patterns.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="mb-8">
            <Label>Danger Zones</Label>
            <div className="bg-card border border-border rounded-lg divide-y divide-border overflow-hidden">
              {patterns.map((p) => (
                <div
                  key={p.pattern_type}
                  className="flex items-center justify-between px-4 py-3 cursor-pointer transition-colors hover:bg-muted/30"
                  onClick={() => navigate(`/training?focus=${p.pattern_type}`)}
                  data-testid={`danger-${p.pattern_type}`}
                >
                  <div className="flex items-center gap-2.5">
                    <AlertTriangle className={`w-3.5 h-3.5 flex-shrink-0 ${p.severity === "critical" || p.severity === "high" ? "text-red-500" : "text-amber-500"}`} strokeWidth={1.5} />
                    <span className="text-sm text-foreground">{p.label}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{p.recent_count}x</span>
                    <SeverityBadge severity={p.severity} />
                    <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/20" strokeWidth={1.5} />
                  </div>
                </div>
              ))}
            </div>
            <p className="text-[10px] text-muted-foreground/50 mt-1.5">Click a pattern to train it.</p>
          </motion.div>
        )}

        {/* ── REVIEW PROGRESS ── */}
        {review.total > 0 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.18 }} className="mb-8">
            <Label>Review Progress</Label>
            <div className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <FlaskConical className="w-4 h-4 text-muted-foreground" strokeWidth={1.5} />
                  <span className="text-sm text-foreground">
                    <strong>{review.reviewed}</strong> of {review.total} games reviewed
                  </span>
                </div>
                {review.pending > 0 && (
                  <button
                    onClick={() => navigate("/lab")}
                    className="text-xs text-primary hover:underline flex items-center gap-1"
                    data-testid="go-to-lab-btn"
                  >
                    {review.pending} pending <ChevronRight className="w-3 h-3" />
                  </button>
                )}
              </div>
              {/* Progress bar */}
              <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500 rounded-full transition-all"
                  style={{ width: `${(review.reviewed / review.total) * 100}%` }}
                />
              </div>
              {review.reviewed === review.total && review.total > 0 && (
                <div className="flex items-center gap-1.5 mt-2.5">
                  <Check className="w-3.5 h-3.5 text-emerald-500" />
                  <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">All caught up!</span>
                </div>
              )}
            </div>
          </motion.div>
        )}

        {/* ── CHESS IDENTITY ── */}
        {dna && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="mb-8">
            <Label>Your Chess Identity</Label>
            <div className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-start justify-between mb-2">
                <span className="text-sm text-muted-foreground">{dna.archetype || "Developing"}</span>
                <div className="text-right">
                  <span className="text-[9px] tracking-[0.15em] uppercase font-bold text-red-600 dark:text-red-400">Biggest Leak</span>
                  <p className="text-sm text-foreground tracking-tight" style={{ fontFamily: "'Playfair Display', serif" }}>
                    {dna.diagnosis?.replace(/_/g, " ") || "—"}
                  </p>
                </div>
              </div>
              {dna.after_line && <p className="text-xs text-muted-foreground leading-relaxed mt-1">{dna.after_line}</p>}
            </div>
          </motion.div>
        )}

        {/* ── LAST 10 GAMES ── */}
        {last10.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }} className="mb-8">
            <Label>Last {last10.length} Games</Label>
            <div className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-end justify-between gap-1.5" style={{ height: 100 }}>
                {last10.map((g, i) => {
                  const h = Math.max((g.accuracy / 100) * 80, 8);
                  const isWin = g.result === "W";
                  const barColor = isWin ? "#16a34a" : g.result === "D" ? "#888" : "#EF4444";
                  return (
                    <div
                      key={g.game_id || i}
                      className="flex-1 flex flex-col items-center cursor-pointer group"
                      onClick={() => navigate(`/game/${g.game_id}`)}
                      data-testid={`bar-game-${i}`}
                    >
                      <div
                        className="w-full rounded-t transition-all group-hover:opacity-100"
                        style={{ height: h, background: barColor, minWidth: 12, maxWidth: 36, opacity: 0.7 }}
                      />
                    </div>
                  );
                })}
              </div>
              <div className="flex items-center justify-between gap-1.5 mt-1">
                {last10.map((g, i) => (
                  <span key={i} className="flex-1 text-center text-[9px] text-muted-foreground" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                    {g.accuracy.toFixed(0)}
                  </span>
                ))}
              </div>
              <div className="flex items-center justify-between mt-2">
                <span className="text-[9px] text-muted-foreground/40" style={{ fontFamily: "'JetBrains Mono', monospace" }}>older</span>
                <span className="text-[9px] text-muted-foreground/40" style={{ fontFamily: "'JetBrains Mono', monospace" }}>recent</span>
              </div>
            </div>
          </motion.div>
        )}

        {/* ── FOOTER ── */}
        <div className="text-center text-[10px] text-muted-foreground/40 pb-4" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
          {gamesAnalyzed} games analyzed
        </div>
      </div>
    </Layout>
  );
};


// ── Components ──

const Label = ({ children, style }) => (
  <p className="text-[10px] tracking-[0.15em] uppercase mb-2 font-bold text-muted-foreground" style={style}>{children}</p>
);

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

// ── Accuracy Journey Chart ──

const GOLD = "#CBA135";

const JourneyChart = ({ journey, onGameClick }) => {
  if (journey.length < 3) return null;

  const HEIGHT = 140;
  const PAD_Y = 20;
  const PAD_X = 10;
  const usableH = HEIGHT - PAD_Y * 2;

  const accs = journey.map(g => g.accuracy);
  const minA = Math.max(Math.min(...accs) - 10, 0);
  const maxA = Math.min(Math.max(...accs) + 10, 100);
  const range = maxA - minA || 1;

  const W = Math.max(journey.length * 26, 400);
  const getX = (i) => PAD_X + (i / Math.max(journey.length - 1, 1)) * (W - PAD_X * 2);
  const getY = (acc) => PAD_Y + usableH - ((acc - minA) / range) * usableH;

  let pathD = "";
  journey.forEach((g, i) => {
    const x = getX(i);
    const y = getY(g.accuracy);
    if (i === 0) pathD += `M ${x} ${y}`;
    else pathD += ` L ${x} ${y}`;
  });

  const areaD = pathD + ` L ${getX(journey.length - 1)} ${HEIGHT - PAD_Y} L ${getX(0)} ${HEIGHT - PAD_Y} Z`;

  return (
    <div className="overflow-x-auto" style={{ scrollbarWidth: "thin" }}>
      <svg width={W} height={HEIGHT} className="block" data-testid="journey-chart">
        <defs>
          <linearGradient id="areaGradProgress" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={GOLD} stopOpacity={0.25} />
            <stop offset="100%" stopColor={GOLD} stopOpacity={0} />
          </linearGradient>
        </defs>
        <path d={areaD} fill="url(#areaGradProgress)" />
        <path d={pathD} fill="none" stroke={GOLD} strokeWidth={1.5} opacity={0.6} />
        {journey.map((g, i) => {
          const x = getX(i);
          const y = getY(g.accuracy);
          const fill = g.result === "W" ? "#16a34a" : g.result === "L" ? "#EF4444" : "#888";
          return (
            <g key={g.game_id || i} className="cursor-pointer" onClick={() => onGameClick(g)}>
              <circle cx={x} cy={y} r={4} fill={fill} stroke="white" strokeWidth={1.5} opacity={0.9} />
              {i % 5 === 0 && (
                <text x={x} y={y - 10} textAnchor="middle" fill="#999" fontSize={8} fontFamily="'JetBrains Mono', monospace">
                  {g.accuracy.toFixed(0)}%
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
};

export default UnifiedProgress;
