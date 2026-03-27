/**
 * PROGRESS PAGE — Reimagined
 * 
 * Not a report card. A trajectory.
 * Shows: Are you getting better? At what? What's stuck?
 */

import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Loader2, TrendingUp, TrendingDown, ArrowRight } from "lucide-react";

const WINE = "#722F37";
const GOLD = "#CBA135";

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
          <div className="w-5 h-5 border border-gray-700 border-t-white animate-spin" />
        </div>
      </Layout>
    );
  }

  const journey = data?.journey || [];
  const winTrend = data?.win_trend;
  const biggestShift = data?.biggest_shift;
  const stillLeaking = data?.still_leaking;
  const currentAccuracy = data?.current_accuracy || 0;
  const gamesAnalyzed = data?.games_analyzed || 0;

  // Compute accuracy trend
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

        {/* ── HEADER ── */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mb-10">
          <h1 className="text-3xl text-white tracking-tight mb-1" style={{ fontFamily: "'Playfair Display', serif" }}>
            Progress
          </h1>
          <p className="text-sm text-gray-600 font-light" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            {gamesAnalyzed} games analyzed
          </p>
        </motion.div>

        {/* ── ACCURACY JOURNEY LINE ── */}
        {journey.length > 3 && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="mb-10">
            <div className="flex items-center justify-between mb-3">
              <p className="text-[10px] tracking-[0.2em] uppercase" style={{ color: GOLD, fontFamily: "'JetBrains Mono', monospace" }}>
                Your Accuracy Journey
              </p>
              <div className="flex items-center gap-2">
                <span className="text-2xl text-white font-light" style={{ fontFamily: "'Playfair Display', serif" }}>
                  {currentAccuracy.toFixed(0)}%
                </span>
                {accImproving && <TrendingUp className="w-4 h-4 text-emerald-400" strokeWidth={1.5} />}
                {accDeclining && <TrendingDown className="w-4 h-4 text-red-400" strokeWidth={1.5} />}
              </div>
            </div>
            <JourneyChart journey={journey} onGameClick={(g) => navigate(`/game/${g.game_id}`)} />
            {olderAcc.length > 0 && (
              <p className="text-xs text-gray-600 mt-2 font-light">
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

        {/* ── WIN RATE TREND ── */}
        {winTrend && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="mb-8">
            <p className="text-[10px] tracking-[0.2em] uppercase mb-3" style={{ color: GOLD, fontFamily: "'JetBrains Mono', monospace" }}>
              Win Rate
            </p>
            <div style={{ background: "#241A14", border: "1px solid rgba(255,255,255,0.05)" }}>
              <div className="p-5">
                <div className="flex items-center gap-6">
                  {/* Previous */}
                  <div className="text-center flex-1">
                    <p className="text-[10px] tracking-[0.1em] uppercase text-gray-600 mb-1" style={{ fontFamily: "'JetBrains Mono', monospace" }}>Previous 10</p>
                    <p className="text-xl text-gray-400 font-light" style={{ fontFamily: "'Playfair Display', serif" }}>
                      <span className="text-emerald-400">{winTrend.previous.wins}W</span>{" "}
                      <span className="text-red-400">{winTrend.previous.losses}L</span>
                    </p>
                  </div>
                  {/* Arrow */}
                  <ArrowRight className="w-5 h-5 text-gray-700 flex-shrink-0" strokeWidth={1.5} />
                  {/* Recent */}
                  <div className="text-center flex-1">
                    <p className="text-[10px] tracking-[0.1em] uppercase text-gray-600 mb-1" style={{ fontFamily: "'JetBrains Mono', monospace" }}>Last 10</p>
                    <p className="text-xl text-white font-light" style={{ fontFamily: "'Playfair Display', serif" }}>
                      <span className="text-emerald-400">{winTrend.recent.wins}W</span>{" "}
                      <span className="text-red-400">{winTrend.recent.losses}L</span>
                    </p>
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-3 text-center font-light">
                  {winTrend.improving
                    ? "You're turning the corner."
                    : winTrend.recent.wins === winTrend.previous.wins
                      ? "Holding steady."
                      : "Rough patch. Focus on reviewing losses, not playing more."
                  }
                </p>
              </div>
            </div>
          </motion.div>
        )}

        {/* ── BIGGEST SHIFT ── */}
        {biggestShift && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="mb-8">
            <p className="text-[10px] tracking-[0.2em] uppercase mb-3" style={{ color: GOLD, fontFamily: "'JetBrains Mono', monospace" }}>
              Biggest Improvement
            </p>
            <div style={{ background: "#241A14", border: "1px solid rgba(39,111,75,0.2)", borderLeft: "3px solid #276F4B" }}>
              <div className="p-5">
                <p className="text-base text-white font-light" style={{ fontFamily: "'Playfair Display', serif" }}>
                  {biggestShift.dimension}
                </p>
                <div className="flex items-center gap-3 mt-2">
                  <span className="text-sm text-gray-500" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{biggestShift.from_score}</span>
                  <ArrowRight className="w-4 h-4 text-emerald-400" strokeWidth={1.5} />
                  <span className="text-sm text-emerald-400" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{biggestShift.to_score}</span>
                  <span className="text-xs text-emerald-400/60">+{biggestShift.delta_pct}%</span>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* ── STILL LEAKING ── */}
        {stillLeaking && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }} className="mb-8">
            <p className="text-[10px] tracking-[0.2em] uppercase mb-3" style={{ color: GOLD, fontFamily: "'JetBrains Mono', monospace" }}>
              Still Leaking
            </p>
            <div style={{ background: "#241A14", border: "1px solid rgba(114,47,55,0.2)", borderLeft: `3px solid ${WINE}` }}>
              <div className="p-5">
                <p className="text-base text-white font-light" style={{ fontFamily: "'Playfair Display', serif" }}>
                  {stillLeaking.dimension}
                </p>
                <p className="text-sm text-gray-500 mt-1 font-light">
                  Stuck at {stillLeaking.score} for {stillLeaking.games_stuck} games. Needs focused attention.
                </p>
              </div>
            </div>
          </motion.div>
        )}

        {/* ── NO SHIFT/LEAK DATA ── */}
        {!biggestShift && !stillLeaking && journey.length > 5 && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="mb-8">
            <div className="p-5" style={{ background: "#241A14", border: "1px solid rgba(255,255,255,0.05)" }}>
              <p className="text-sm text-gray-500 font-light text-center">
                Keep playing — your dimension trends will appear after more games.
              </p>
            </div>
          </motion.div>
        )}

        {/* ── BLUNDER TREND ── */}
        {journey.length > 5 && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }} className="mb-8">
            <p className="text-[10px] tracking-[0.2em] uppercase mb-3" style={{ color: GOLD, fontFamily: "'JetBrains Mono', monospace" }}>
              Blunder Rate
            </p>
            <BlunderTrend journey={journey} />
          </motion.div>
        )}

      </div>
    </Layout>
  );
};


// ── ACCURACY JOURNEY CHART ──
const JourneyChart = ({ journey, onGameClick }) => {
  if (journey.length < 3) return null;

  const HEIGHT = 160;
  const PAD_Y = 25;
  const PAD_X = 10;
  const usableH = HEIGHT - PAD_Y * 2;

  const accs = journey.map(g => g.accuracy);
  const minA = Math.max(Math.min(...accs) - 10, 0);
  const maxA = Math.min(Math.max(...accs) + 10, 100);
  const range = maxA - minA || 1;

  const W = Math.max(journey.length * 28, 500);
  const getX = (i) => PAD_X + (i / Math.max(journey.length - 1, 1)) * (W - PAD_X * 2);
  const getY = (acc) => PAD_Y + usableH - ((acc - minA) / range) * usableH;

  // Build smooth-ish path
  let pathD = "";
  journey.forEach((g, i) => {
    const x = getX(i);
    const y = getY(g.accuracy);
    if (i === 0) pathD += `M ${x} ${y}`;
    else pathD += ` L ${x} ${y}`;
  });

  // Area fill
  const areaD = pathD + ` L ${getX(journey.length - 1)} ${HEIGHT - PAD_Y} L ${getX(0)} ${HEIGHT - PAD_Y} Z`;

  return (
    <div className="overflow-x-auto" style={{ scrollbarWidth: "thin", scrollbarColor: "rgba(255,255,255,0.1) transparent" }}>
      <svg width={W} height={HEIGHT} className="block" data-testid="journey-chart">
        {/* Area fill */}
        <path d={areaD} fill="url(#areaGrad)" opacity={0.3} />
        <defs>
          <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={GOLD} stopOpacity={0.4} />
            <stop offset="100%" stopColor={GOLD} stopOpacity={0} />
          </linearGradient>
        </defs>

        {/* Line */}
        <path d={pathD} fill="none" stroke={GOLD} strokeWidth={1.5} opacity={0.7} />

        {/* Dots */}
        {journey.map((g, i) => {
          const x = getX(i);
          const y = getY(g.accuracy);
          const fill = g.result === "W" ? "#276F4B" : g.result === "L" ? WINE : "#555";
          return (
            <g key={g.game_id} className="cursor-pointer" onClick={() => onGameClick(g)}>
              <circle cx={x} cy={y} r={4} fill={fill} stroke="rgba(255,255,255,0.1)" strokeWidth={1} />
              {/* Show accuracy on every 5th game */}
              {i % 5 === 0 && (
                <text x={x} y={y - 10} textAnchor="middle" fill="#666" fontSize={9} fontFamily="'JetBrains Mono', monospace">
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


// ── BLUNDER TREND ──
const BlunderTrend = ({ journey }) => {
  const recent = journey.slice(-10);
  const prev = journey.slice(-20, -10);
  const recentBlunders = recent.reduce((sum, g) => sum + (g.blunders || 0), 0);
  const prevBlunders = prev.reduce((sum, g) => sum + (g.blunders || 0), 0);
  const recentAvg = recent.length ? (recentBlunders / recent.length).toFixed(1) : 0;
  const prevAvg = prev.length ? (prevBlunders / prev.length).toFixed(1) : 0;
  const improving = parseFloat(recentAvg) < parseFloat(prevAvg);

  return (
    <div style={{ background: "#241A14", border: "1px solid rgba(255,255,255,0.05)" }}>
      <div className="p-5">
        <div className="flex items-center gap-6">
          <div className="text-center flex-1">
            <p className="text-[10px] tracking-[0.1em] uppercase text-gray-600 mb-1" style={{ fontFamily: "'JetBrains Mono', monospace" }}>Prev 10 avg</p>
            <p className="text-xl text-gray-400 font-light" style={{ fontFamily: "'Playfair Display', serif" }}>
              {prevAvg}<span className="text-sm text-gray-600">/game</span>
            </p>
          </div>
          <ArrowRight className={`w-5 h-5 flex-shrink-0 ${improving ? 'text-emerald-400' : 'text-red-400'}`} strokeWidth={1.5} />
          <div className="text-center flex-1">
            <p className="text-[10px] tracking-[0.1em] uppercase text-gray-600 mb-1" style={{ fontFamily: "'JetBrains Mono', monospace" }}>Last 10 avg</p>
            <p className={`text-xl font-light ${improving ? 'text-emerald-400' : 'text-white'}`} style={{ fontFamily: "'Playfair Display', serif" }}>
              {recentAvg}<span className="text-sm text-gray-600">/game</span>
            </p>
          </div>
        </div>
        <p className="text-xs text-gray-500 mt-3 text-center font-light">
          {improving
            ? "Blunders dropping. Your awareness is improving."
            : parseFloat(recentAvg) === parseFloat(prevAvg)
              ? "Blunder rate unchanged. Awareness drills could help."
              : "Blunders increasing. Slow down — check threats before every move."
          }
        </p>
      </div>
    </div>
  );
};


export default UnifiedProgress;
