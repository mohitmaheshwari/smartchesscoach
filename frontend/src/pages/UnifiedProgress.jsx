/**
 * PROGRESS PAGE — Matching PAGE_LAYOUTS.md spec
 * 
 * Sections:
 * 1. Header: Progress + games analyzed
 * 2. YOUR ACCURACY JOURNEY — gold line chart with green/red dots
 * 3. WIN RATE + BLUNDERS RISING — side by side
 * 4. DANGER ZONES — clickable patterns with severity badges
 * 5. YOUR CHESS IDENTITY — archetype + biggest leak
 * 6. LAST 10 GAMES — bar chart
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { TrendingUp, TrendingDown, ArrowRight, AlertTriangle, ChevronRight } from "lucide-react";

const WINE = "#722F37";
const GOLD = "#CBA135";
const GOLD_TEXT = "#8B6F1F";

const UnifiedProgress = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [homeData, setHomeData] = useState(null);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [journeyRes, homeRes] = await Promise.all([
          fetch(`${API}/progress/journey`, { credentials: "include" }),
          fetch(`${API}/home/dashboard-v2`, { credentials: "include" }),
        ]);
        if (journeyRes.ok) setData(await journeyRes.json());
        if (homeRes.ok) setHomeData(await homeRes.json());
      } catch (e) {
        console.error("Progress fetch error:", e);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
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
  const recentBlunders = recentGames.reduce((sum, g) => sum + (g.blunders || 0), 0);
  const prevBlunders = prevGames.reduce((sum, g) => sum + (g.blunders || 0), 0);
  const recentBlunderAvg = recentGames.length ? (recentBlunders / recentGames.length) : 0;
  const prevBlunderAvg = prevGames.length ? (prevBlunders / prevGames.length) : 0;
  const blundersRising = recentBlunderAvg > prevBlunderAvg + 0.2;

  // Last 10 games for bar chart
  const last10 = journey.slice(-10);

  return (
    <Layout user={user}>
      <div className="max-w-3xl mx-auto px-4 py-6" data-testid="progress-page">

        {/* ═══════════════════════════════════════════════════
            HEADER
        ═══════════════════════════════════════════════════ */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mb-8">
          <h1 className="text-2xl text-foreground tracking-tight mb-1" style={{ fontFamily: "'Playfair Display', serif" }}>
            Progress
          </h1>
          <p className="text-xs text-muted-foreground font-mono">
            {gamesAnalyzed} games analyzed
          </p>
        </motion.div>

        {/* ═══════════════════════════════════════════════════
            YOUR ACCURACY JOURNEY — gold line, green/red dots
        ═══════════════════════════════════════════════════ */}
        {journey.length > 3 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }} className="mb-8">
            <div className="flex items-center justify-between mb-3">
              <SectionLabel>Your Accuracy Journey</SectionLabel>
              <div className="flex items-center gap-2">
                <span className="text-xl text-foreground font-light" style={{ fontFamily: "'Playfair Display', serif" }}>
                  {currentAccuracy.toFixed(0)}%
                </span>
                {accImproving && <TrendingUp className="w-4 h-4 text-emerald-600" strokeWidth={1.5} />}
                {accDeclining && <TrendingDown className="w-4 h-4" style={{ color: WINE }} strokeWidth={1.5} />}
              </div>
            </div>
            <Card>
              <div className="p-4">
                <JourneyChart journey={journey} onGameClick={(g) => navigate(`/game/${g.game_id}`)} />
              </div>
            </Card>
            {olderAcc.length > 0 && (
              <p className="text-xs text-muted-foreground mt-2 font-light">
                {accImproving
                  ? `Improving: ${olderAvg.toFixed(0)}% → ${recentAvg.toFixed(0)}% in last 10 games`
                  : accDeclining
                    ? `Slipping: ${olderAvg.toFixed(0)}% → ${recentAvg.toFixed(0)}% — slow down`
                    : `Steady at ~${recentAvg.toFixed(0)}% over recent games`
                }
              </p>
            )}
          </motion.div>
        )}

        {/* ═══════════════════════════════════════════════════
            WIN RATE + BLUNDERS — side by side
        ═══════════════════════════════════════════════════ */}
        {journey.length > 5 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="mb-8">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Win Rate */}
              {winTrend && (
                <div>
                  <SectionLabel>Win Rate</SectionLabel>
                  <Card className="h-full">
                    <div className="p-4">
                      <div className="flex items-center gap-3 mb-3">
                        <div>
                          <span className="text-emerald-600 font-mono text-sm">{winTrend.previous.wins}W</span>
                          {" "}
                          <span className="font-mono text-sm" style={{ color: WINE }}>{winTrend.previous.losses}L</span>
                        </div>
                        <ArrowRight className="w-4 h-4 text-muted-foreground/30" strokeWidth={1.5} />
                        <div>
                          <span className="text-emerald-600 font-mono text-sm">{winTrend.recent.wins}W</span>
                          {" "}
                          <span className="font-mono text-sm" style={{ color: WINE }}>{winTrend.recent.losses}L</span>
                        </div>
                      </div>
                      <p className="text-xs text-muted-foreground font-light">
                        {winTrend.improving
                          ? "You're turning the corner."
                          : winTrend.recent.wins === winTrend.previous.wins
                            ? "Holding steady."
                            : "Rough patch. Review losses, don't play more."
                        }
                      </p>
                    </div>
                  </Card>
                </div>
              )}

              {/* Blunders Rising */}
              <div>
                <SectionLabel style={blundersRising ? { color: WINE } : {}}>
                  {blundersRising ? "Blunders Rising" : "Blunder Rate"}
                </SectionLabel>
                <Card className="h-full">
                  <div className="p-4">
                    <div className="flex items-center gap-3 mb-3">
                      <span className="font-mono text-sm text-muted-foreground">{prevBlunderAvg.toFixed(1)}/g</span>
                      <ArrowRight className="w-4 h-4 text-muted-foreground/30" strokeWidth={1.5} />
                      <span className="font-mono text-sm" style={{ color: blundersRising ? WINE : "inherit" }}>
                        {recentBlunderAvg.toFixed(1)}/g
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground font-light">
                      {blundersRising
                        ? "Slow down. Check threats before every move."
                        : recentBlunderAvg < prevBlunderAvg
                          ? "Blunders dropping. Awareness improving."
                          : "Blunder rate steady. Awareness drills could help."
                      }
                    </p>
                  </div>
                </Card>
              </div>
            </div>
          </motion.div>
        )}

        {/* ═══════════════════════════════════════════════════
            DANGER ZONES
        ═══════════════════════════════════════════════════ */}
        {patterns.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="mb-8">
            <SectionLabel>Danger Zones</SectionLabel>
            <Card>
              <div className="divide-y" style={{ borderColor: "hsl(35 10% 87%)" }}>
                {patterns.map((p) => (
                  <div
                    key={p.pattern_type}
                    className="flex items-center justify-between px-4 py-3 cursor-pointer transition-colors hover:bg-black/[0.02]"
                    onClick={() => navigate(`/training?focus=${p.pattern_type}`)}
                    data-testid={`danger-${p.pattern_type}`}
                  >
                    <div className="flex items-center gap-2.5">
                      <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" style={{ color: p.severity === "critical" ? WINE : GOLD_TEXT }} strokeWidth={1.5} />
                      <span className="text-sm text-foreground font-light">{p.label}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground font-mono">{p.recent_count}x</span>
                      <SeverityBadge severity={p.severity} />
                      <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/30" strokeWidth={1.5} />
                    </div>
                  </div>
                ))}
              </div>
            </Card>
            <p className="text-[10px] text-muted-foreground/60 mt-1.5 font-mono">Click a pattern to train it.</p>
          </motion.div>
        )}

        {/* ═══════════════════════════════════════════════════
            YOUR CHESS IDENTITY
        ═══════════════════════════════════════════════════ */}
        {dna && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="mb-8">
            <SectionLabel>Your Chess Identity</SectionLabel>
            <Card>
              <div className="p-4">
                <div className="flex items-start justify-between mb-2">
                  <span className="text-sm text-muted-foreground font-light">
                    {dna.archetype || "Developing"}
                  </span>
                  <div className="text-right">
                    <span className="text-[9px] tracking-[0.15em] uppercase font-mono" style={{ color: WINE }}>
                      Biggest Leak
                    </span>
                    <p className="text-sm text-foreground tracking-tight" style={{ fontFamily: "'Playfair Display', serif" }}>
                      {dna.diagnosis?.replace(/_/g, " ") || "—"}
                    </p>
                  </div>
                </div>
                {dna.before_line && (
                  <p className="text-xs text-muted-foreground font-light mt-2">Before: {dna.before_line}</p>
                )}
                {dna.after_line && (
                  <p className="text-xs text-foreground font-light">After: {dna.after_line}</p>
                )}
              </div>
            </Card>
          </motion.div>
        )}

        {/* ═══════════════════════════════════════════════════
            LAST 10 GAMES — bar chart
        ═══════════════════════════════════════════════════ */}
        {last10.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }} className="mb-8">
            <SectionLabel>Last 10 Games</SectionLabel>
            <Card>
              <div className="p-4">
                <div className="flex items-end justify-between gap-1.5" style={{ height: 100 }}>
                  {last10.map((g, i) => {
                    const h = Math.max((g.accuracy / 100) * 80, 8);
                    const isWin = g.result === "W";
                    const barColor = isWin ? "#16a34a" : WINE;
                    const opacity = Math.max(g.accuracy / 100, 0.3);
                    return (
                      <div
                        key={g.game_id || i}
                        className="flex-1 flex flex-col items-center cursor-pointer transition-opacity hover:opacity-100"
                        style={{ opacity }}
                        onClick={() => navigate(`/game/${g.game_id}`)}
                        data-testid={`bar-game-${i}`}
                      >
                        <div
                          className="w-full rounded-t-sm transition-all"
                          style={{ height: h, background: barColor, minWidth: 12, maxWidth: 36 }}
                        />
                      </div>
                    );
                  })}
                </div>
                {/* Accuracy labels */}
                <div className="flex items-center justify-between gap-1.5 mt-1">
                  {last10.map((g, i) => (
                    <span key={i} className="flex-1 text-center text-[9px] text-muted-foreground font-mono">
                      {g.accuracy.toFixed(0)}
                    </span>
                  ))}
                </div>
                <div className="flex items-center justify-between mt-2">
                  <span className="text-[9px] text-muted-foreground/50 font-mono">older</span>
                  <span className="text-[9px] text-muted-foreground/50 font-mono">recent</span>
                </div>
              </div>
            </Card>
          </motion.div>
        )}

      </div>
    </Layout>
  );
};


// ── REUSABLE COMPONENTS ──

const SectionLabel = ({ children, style }) => (
  <p
    className="text-[10px] tracking-[0.2em] uppercase mb-2 font-mono"
    style={{ color: GOLD_TEXT, fontFamily: "'JetBrains Mono', monospace", ...style }}
  >
    {children}
  </p>
);

const Card = ({ children, className = "" }) => (
  <div className={`bg-white border rounded-sm ${className}`} style={{ borderColor: "hsl(35 10% 87%)" }}>
    {children}
  </div>
);

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
      {isCrit ? "CRIT" : "MED"}
    </span>
  );
};


// ── ACCURACY JOURNEY CHART ──

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
    <div className="overflow-x-auto" style={{ scrollbarWidth: "thin", scrollbarColor: "rgba(0,0,0,0.08) transparent" }}>
      <svg width={W} height={HEIGHT} className="block" data-testid="journey-chart">
        <defs>
          <linearGradient id="areaGradProgress" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={GOLD} stopOpacity={0.3} />
            <stop offset="100%" stopColor={GOLD} stopOpacity={0} />
          </linearGradient>
        </defs>
        <path d={areaD} fill="url(#areaGradProgress)" />
        <path d={pathD} fill="none" stroke={GOLD} strokeWidth={1.5} opacity={0.7} />
        {journey.map((g, i) => {
          const x = getX(i);
          const y = getY(g.accuracy);
          const fill = g.result === "W" ? "#16a34a" : g.result === "L" ? WINE : "#888";
          return (
            <g key={g.game_id || i} className="cursor-pointer" onClick={() => onGameClick(g)}>
              <circle cx={x} cy={y} r={3.5} fill={fill} stroke="white" strokeWidth={1} />
              {i % 5 === 0 && (
                <text x={x} y={y - 9} textAnchor="middle" fill="#999" fontSize={8} fontFamily="'JetBrains Mono', monospace">
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
