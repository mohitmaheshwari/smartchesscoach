/**
 * PROGRESS PAGE — V2
 * 
 * Not a report card. A trajectory + danger zones + action items.
 */

import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { ArrowRight, TrendingUp, TrendingDown, AlertTriangle, ChevronRight } from "lucide-react";

const WINE = "#722F37";
const GOLD_TEXT = "#8B6F1F";

const UnifiedProgress = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch(`${API}/progress/journey`, { credentials: "include" });
        if (res.ok) setData(await res.json());
      } catch (e) {
        console.error("Progress fetch error:", e);
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

  const journey = data?.journey || [];
  const winTrend = data?.win_trend;
  const chess_dna = data?.chess_dna;
  const dangerZones = data?.danger_zones || [];
  const blunderTrend = data?.blunder_trend;
  const currentAccuracy = data?.current_accuracy || 0;
  const gamesAnalyzed = data?.games_analyzed || 0;

  const recentAcc = journey.slice(-10).map(g => g.accuracy);
  const olderAcc = journey.slice(-20, -10).map(g => g.accuracy);
  const recentAvg = recentAcc.length ? recentAcc.reduce((a, b) => a + b, 0) / recentAcc.length : 0;
  const olderAvg = olderAcc.length ? olderAcc.reduce((a, b) => a + b, 0) / olderAcc.length : 0;
  const accDelta = recentAvg - olderAvg;
  const accImproving = accDelta > 2;
  const accDeclining = accDelta < -2;

  return (
    <Layout user={user}>
      <div className="max-w-3xl mx-auto px-4 py-8" data-testid="progress-page">

        {/* Header */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mb-10">
          <h1 className="text-3xl text-foreground tracking-tight font-heading">Progress</h1>
          <p className="text-xs text-muted-foreground mt-1 font-mono">{gamesAnalyzed} games analyzed</p>
        </motion.div>

        {/* ── ACCURACY JOURNEY ── */}
        {journey.length > 3 && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }} className="mb-8">
            <div className="flex items-center justify-between mb-3">
              <SectionLabel>Your Accuracy Journey</SectionLabel>
              <div className="flex items-center gap-2">
                <span className="text-2xl text-foreground font-heading">{currentAccuracy.toFixed(0)}%</span>
                {accImproving && <TrendingUp className="w-4 h-4 text-emerald-600" strokeWidth={1.5} />}
                {accDeclining && <TrendingDown className="w-4 h-4 text-red-600" strokeWidth={1.5} />}
              </div>
            </div>
            <JourneyChart journey={journey} onGameClick={(g) => navigate(`/game/${g.game_id}`)} />
            {olderAcc.length > 0 && (
              <p className="text-xs text-muted-foreground mt-2">
                {accImproving
                  ? `Improving: ${olderAvg.toFixed(0)}% → ${recentAvg.toFixed(0)}% in last 10 games`
                  : accDeclining
                    ? `Slipping: ${olderAvg.toFixed(0)}% → ${recentAvg.toFixed(0)}% — time to slow down and review`
                    : `Steady at ~${recentAvg.toFixed(0)}% over recent games`
                }
              </p>
            )}
          </motion.div>
        )}

        {/* ── TWO COLUMNS: Win Rate + Blunders ── */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="grid grid-cols-2 gap-4 mb-8">
          {/* Win Rate */}
          {winTrend && (
            <div className="bg-card border border-border rounded-sm p-4">
              <SectionLabel>Win Rate</SectionLabel>
              <div className="flex items-center gap-3 mt-3">
                <div className="text-center flex-1">
                  <p className="text-lg text-muted-foreground font-heading">
                    <span className="text-emerald-600">{winTrend.previous.wins}W</span> <span style={{ color: WINE }}>{winTrend.previous.losses}L</span>
                  </p>
                  <p className="text-[9px] text-muted-foreground/60 font-mono mt-1">PREV 10</p>
                </div>
                <ArrowRight className="w-4 h-4 text-muted-foreground/30 flex-shrink-0" strokeWidth={1.5} />
                <div className="text-center flex-1">
                  <p className="text-lg text-foreground font-heading">
                    <span className="text-emerald-600">{winTrend.recent.wins}W</span> <span style={{ color: WINE }}>{winTrend.recent.losses}L</span>
                  </p>
                  <p className="text-[9px] text-muted-foreground/60 font-mono mt-1">LAST 10</p>
                </div>
              </div>
              <p className="text-xs text-muted-foreground mt-3">
                {winTrend.improving ? "Turning the corner." : winTrend.recent.wins === winTrend.previous.wins ? "Holding steady." : "Rough stretch."}
              </p>
            </div>
          )}

          {/* Blunder Rate */}
          {blunderTrend && (
            <div className={`bg-card border rounded-sm p-4 ${blunderTrend.getting_worse ? 'border-red-200' : 'border-border'}`}>
              <SectionLabel>{blunderTrend.getting_worse ? <span style={{ color: WINE }}>Blunders Rising</span> : "Blunder Rate"}</SectionLabel>
              <div className="flex items-center gap-3 mt-3">
                <div className="text-center flex-1">
                  <p className="text-lg text-muted-foreground font-heading">{blunderTrend.prev_avg}<span className="text-xs">/g</span></p>
                  <p className="text-[9px] text-muted-foreground/60 font-mono mt-1">PREV 10</p>
                </div>
                <ArrowRight className={`w-4 h-4 flex-shrink-0 ${blunderTrend.getting_worse ? 'text-red-500' : 'text-emerald-500'}`} strokeWidth={1.5} />
                <div className="text-center flex-1">
                  <p className={`text-lg font-heading ${blunderTrend.getting_worse ? 'text-red-600' : 'text-foreground'}`}>
                    {blunderTrend.recent_avg}<span className="text-xs">/g</span>
                  </p>
                  <p className="text-[9px] text-muted-foreground/60 font-mono mt-1">LAST 10</p>
                </div>
              </div>
              <p className="text-xs text-muted-foreground mt-3">
                {blunderTrend.getting_worse
                  ? "Slow down. Check threats before every move."
                  : blunderTrend.recent_avg < blunderTrend.prev_avg
                    ? "Blunders dropping. Awareness improving."
                    : "Blunder rate stable."
                }
              </p>
            </div>
          )}
        </motion.div>

        {/* ── DANGER ZONES (patterns that need attention) ── */}
        {dangerZones.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="mb-8">
            <SectionLabel>Danger Zones</SectionLabel>
            <div className="bg-card border border-border rounded-sm divide-y divide-border mt-2">
              {dangerZones.map((dz) => (
                <div
                  key={dz.pattern_type}
                  className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-muted/30 transition-colors"
                  onClick={() => navigate(`/training?focus=${dz.pattern_type}`)}
                >
                  <div className="flex items-center gap-3">
                    <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" style={{ color: dz.severity === "critical" ? WINE : GOLD_TEXT }} strokeWidth={1.5} />
                    <span className="text-sm text-foreground">{dz.label}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono" style={{ color: dz.severity === "critical" ? WINE : GOLD_TEXT }}>
                      {dz.recent_count}x
                    </span>
                    <span className="text-[9px] px-1.5 py-0.5 font-mono rounded-sm uppercase"
                      style={{
                        background: dz.severity === "critical" ? `${WINE}10` : `${GOLD_TEXT}15`,
                        color: dz.severity === "critical" ? WINE : GOLD_TEXT,
                      }}>
                      {dz.severity}
                    </span>
                    <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/40" strokeWidth={1.5} />
                  </div>
                </div>
              ))}
            </div>
            <p className="text-xs text-muted-foreground mt-2">Click a pattern to train it directly.</p>
          </motion.div>
        )}

        {/* ── CHESS DNA ── */}
        {chess_dna && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="mb-8">
            <SectionLabel>Your Chess Identity</SectionLabel>
            <div className="bg-card border border-border rounded-sm p-4 mt-2">
              <div className="flex items-center justify-between">
                <h3 className="text-lg text-foreground font-heading capitalize">{chess_dna.archetype?.replace(/_/g, " ") || "Developing"}</h3>
                {chess_dna.worst_pattern && (
                  <span className="text-[9px] px-1.5 py-0.5 font-mono rounded-sm uppercase" style={{ border: `1px solid ${WINE}40`, color: WINE }}>
                    Biggest leak: {chess_dna.worst_pattern}
                  </span>
                )}
              </div>
              {chess_dna.worst_count > 0 && (
                <p className="text-xs text-muted-foreground mt-2">
                  {chess_dna.worst_pattern} has appeared {chess_dna.worst_count} times across your games.
                </p>
              )}
            </div>
          </motion.div>
        )}

        {/* ── LAST 10 GAMES STRIP ── */}
        {journey.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }} className="mb-8">
            <SectionLabel>Last 10 Games</SectionLabel>
            <div className="flex gap-1.5 mt-2">
              {journey.slice(-10).map((g, i) => (
                <div
                  key={g.game_id}
                  className="flex-1 cursor-pointer group relative"
                  onClick={() => navigate(`/game/${g.game_id}`)}
                  title={`vs ${g.opponent} — ${g.accuracy}% accuracy, ${g.blunders} blunders`}
                >
                  <div
                    className="h-10 rounded-sm transition-all group-hover:opacity-80"
                    style={{
                      background: g.result === "W" ? "#16a34a" : g.result === "L" ? WINE : "#d4d4d4",
                      opacity: 0.15 + (g.accuracy / 100) * 0.85,
                    }}
                  />
                  <p className="text-[8px] text-center text-muted-foreground/60 mt-0.5 font-mono">
                    {g.accuracy.toFixed(0)}%
                  </p>
                </div>
              ))}
            </div>
            <div className="flex justify-between mt-1">
              <span className="text-[9px] text-muted-foreground/40 font-mono">older</span>
              <span className="text-[9px] text-muted-foreground/40 font-mono">recent</span>
            </div>
          </motion.div>
        )}

      </div>
    </Layout>
  );
};

const SectionLabel = ({ children }) => (
  <p className="text-[10px] tracking-[0.2em] uppercase font-mono" style={{ color: GOLD_TEXT }}>{children}</p>
);

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

  const W = Math.max(journey.length * 24, 500);
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
          <linearGradient id="accGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#CBA135" stopOpacity={0.3} />
            <stop offset="100%" stopColor="#CBA135" stopOpacity={0} />
          </linearGradient>
        </defs>
        <path d={areaD} fill="url(#accGrad)" />
        <path d={pathD} fill="none" stroke="#CBA135" strokeWidth={1.5} opacity={0.6} />
        {journey.map((g, i) => {
          const x = getX(i);
          const y = getY(g.accuracy);
          return (
            <g key={g.game_id} className="cursor-pointer" onClick={() => onGameClick(g)}>
              <circle cx={x} cy={y} r={3.5} fill={g.result === "W" ? "#16a34a" : g.result === "L" ? WINE : "#aaa"} stroke="white" strokeWidth={1} />
              {i % 6 === 0 && (
                <text x={x} y={y - 8} textAnchor="middle" fill="#999" fontSize={8} fontFamily="'JetBrains Mono', monospace">{g.accuracy.toFixed(0)}%</text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
};

export default UnifiedProgress;
