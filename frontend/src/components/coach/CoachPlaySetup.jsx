/**
 * CoachPlaySetup — Pre-game setup screen for Play with Coach
 *
 * Shows: color selector, practice mode indicator, past games memory,
 * opening suggestions, and start button.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { scaleIn, staggerContainer, staggerItem } from "@/lib/motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import Layout from "@/components/Layout";
import CurriculumStateStrip from "@/components/curriculum/CurriculumStateStrip";
import { PreGameStreakPopup } from "@/components/streak";
import { API } from "@/App";
import UnifiedCoachPlaySetup from "@/components/coach/UnifiedCoachPlaySetup";
import {
  ArrowLeft,
  Swords,
  Brain,
  Loader2,
  History,
  Target,
  Play,
  Navigation,
  GraduationCap,
  Check,
  Sparkles,
  ArrowRight,
  Shield,
} from "lucide-react";

/* ── Opening Suggestions sub-component ── */
const DEFAULT_OPENINGS = {
  white: [
    { name: "London System", games: 0, wins: 0, losses: 0, win_rate: 0, status: "new" },
    { name: "Italian Game", games: 0, wins: 0, losses: 0, win_rate: 0, status: "new" },
    { name: "Queen's Gambit", games: 0, wins: 0, losses: 0, win_rate: 0, status: "new" },
    { name: "Ruy Lopez", games: 0, wins: 0, losses: 0, win_rate: 0, status: "new" },
    { name: "Scotch Game", games: 0, wins: 0, losses: 0, win_rate: 0, status: "new" },
  ],
  black: [
    { name: "Sicilian Defense", games: 0, wins: 0, losses: 0, win_rate: 0, status: "new" },
    { name: "French Defense", games: 0, wins: 0, losses: 0, win_rate: 0, status: "new" },
    { name: "Caro-Kann Defense", games: 0, wins: 0, losses: 0, win_rate: 0, status: "new" },
    { name: "King's Indian Defense", games: 0, wins: 0, losses: 0, win_rate: 0, status: "new" },
    { name: "Queen's Gambit Declined", games: 0, wins: 0, losses: 0, win_rate: 0, status: "new" },
  ],
};

const OpeningSuggestions = ({ selectedColor, selectedOpening, onSelectOpening }) => {
  const [data, setData] = useState(null);
  useEffect(() => {
    fetch(`${API}/coach/play/opening-suggestions`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setData(d))
      .catch(() => {});
  }, []);

  const statusCopy = {
    strong: "Feels familiar",
    learning: "Worth another look",
    weak: "Let’s make this clearer",
    new: "Try something new",
  };

  // Build robust list of openings for selected color with guaranteed repertoire fallback
  const rawList = selectedColor === "white" ? data?.white : data?.black;
  const defaults = DEFAULT_OPENINGS[selectedColor] || DEFAULT_OPENINGS.white;

  let colorOpenings = Array.isArray(rawList) ? [...rawList] : [];
  const existingNames = new Set(colorOpenings.map((o) => o.name?.toLowerCase()));

  for (const def of defaults) {
    if (colorOpenings.length >= 5) break;
    const defLower = def.name.toLowerCase();
    const alreadyExists = [...existingNames].some(
      (ex) => ex && (ex.includes(defLower) || defLower.includes(ex))
    );
    if (!alreadyExists) {
      colorOpenings.push(def);
      existingNames.add(defLower);
    }
  }

  if (!colorOpenings.length) return null;

  // Find best opening
  const best = colorOpenings.reduce((a, b) =>
    (b.win_rate > a.win_rate && b.games >= 3) ? b : a, colorOpenings[0]
  );

  return (
    <div
      className="space-y-3"
      data-testid="opening-suggestions"
    >
      <div className="flex items-center justify-between gap-2 pb-2.5 border-b border-slate-200 dark:border-white/10">
        <div>
          <span className="text-xs sm:text-[13px] font-mono uppercase tracking-[0.2em] text-cyan-700 dark:text-cyan-300 font-bold flex items-center gap-1.5 mb-1">
            <span className="w-2 h-2 rounded-full bg-cyan-500 dark:bg-cyan-400 animate-pulse" />
            Step 3 · Opening Preparation
          </span>
          <p className="font-heading font-black text-base sm:text-lg text-slate-900 dark:text-white tracking-tight">
            Which opening shall we explore?
          </p>
        </div>
        {selectedOpening && (
          <button
            type="button"
            onClick={() => onSelectOpening(null)}
            className="text-xs font-mono font-bold text-cyan-700 dark:text-cyan-300 hover:text-cyan-800 dark:hover:text-cyan-200 transition-colors px-3 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-white/5 dark:hover:bg-white/10 border border-slate-200 dark:border-white/10 cursor-pointer"
          >
            Clear choice
          </button>
        )}
      </div>

      <div className="space-y-2 max-h-[220px] xl:max-h-[260px] 2xl:max-h-[300px] overflow-y-auto pr-1">
        {colorOpenings.slice(0, 5).map((o, i) => {
          const isSelected = selectedOpening === o.name;
          const isBest = o.name === best.name && best.games >= 3;
          return (
            <button
              key={i}
              type="button"
              onClick={() => onSelectOpening(isSelected ? null : o.name)}
              className={`w-full flex items-center justify-between text-left p-3 sm:p-3.5 rounded-xl transition-all duration-200 cursor-pointer relative overflow-hidden ${
                isSelected
                  ? "border-2 border-cyan-400 bg-gradient-to-r from-cyan-100 via-cyan-50 to-white dark:from-cyan-950/90 dark:via-[#112a3d] dark:to-[#0c1e2c] text-slate-900 dark:text-white shadow-md dark:shadow-[0_0_15px_rgba(56,189,248,0.25)] ring-1 ring-cyan-400/50"
                  : "border border-slate-200/90 dark:border-white/10 bg-white dark:bg-[#121b25]/80 hover:border-cyan-400/40 hover:bg-slate-50 dark:hover:bg-[#162330] text-slate-800 dark:text-slate-200"
              }`}
            >
              {isSelected && (
                <div className="absolute left-0 inset-y-0 w-1 bg-cyan-400 shadow-[0_0_8px_#38bdf8]" />
              )}
              <div className="flex items-center gap-3 min-w-0 pl-1">
                <span className={`w-3 h-3 rounded-full shrink-0 transition-all ${
                  isSelected ? "bg-cyan-400 shadow-[0_0_8px_#38bdf8] ring-2 ring-cyan-400/40" : "bg-slate-300 dark:bg-slate-600 border border-slate-400/50 dark:border-slate-500"
                }`} />
                <span className={`font-heading font-extrabold text-sm sm:text-base truncate ${isSelected ? "text-cyan-950 dark:text-white" : "text-slate-900 dark:text-white"}`}>
                  {o.name}
                </span>
                {isBest && (
                  <span className={`text-[11px] font-mono font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full shrink-0 shadow-xs ${
                    isSelected ? "bg-amber-400 text-slate-950 font-black" : "bg-gradient-to-r from-amber-400 to-amber-500 text-slate-950 font-bold"
                  }`} aria-label="Coach's pick">
                    ★ Pick
                  </span>
                )}
              </div>
              <span className={`text-xs font-mono font-bold ml-2 shrink-0 px-2.5 py-1 rounded-md ${
                isSelected
                  ? "bg-cyan-200/90 text-cyan-950 dark:bg-cyan-950/90 dark:text-cyan-300 border border-cyan-400/50"
                  : "bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-slate-400 border border-slate-200/60 dark:border-transparent"
              }`}>
                {statusCopy[o.status] || "Explore this"}
              </span>
            </button>
          );
        })}
      </div>

      {best.games >= 3 && !selectedOpening && (
        <div className="p-3 rounded-xl bg-cyan-50 dark:bg-cyan-950/40 border border-cyan-200 dark:border-cyan-500/20 flex items-center gap-2.5 text-xs sm:text-sm text-slate-700 dark:text-slate-300">
          <Sparkles className="w-4 h-4 text-cyan-600 dark:text-cyan-400 shrink-0" />
          <span className="text-xs sm:text-[13px] leading-snug">
            I’d begin with <span className="font-bold text-cyan-800 dark:text-cyan-300">{best.name}</span>. It connects naturally to games you play.
          </span>
        </div>
      )}
    </div>
  );
};

/* ── Main Pre-Game Setup ── */
const CoachPlaySetup = ({
  user,
  loading,
  practiceMode,
  practicePosition,
  selectedColor,
  setSelectedColor,
  selectedOpening,
  setSelectedOpening,
  guidedMode,
  setGuidedMode,
  gameMode,
  setGameMode,
  evidenceMode,
  setEvidenceMode,
  pastGamesHistory,
  playerIdentityData,
  startGame,
  showPreGameStreakPopup,
  setShowPreGameStreakPopup,
  actuallyStartGame,
  unifiedExperience = false,
  experienceLoading = false,
  experienceConfig = null,
  upgradeInfo = null,
  timeControl = "15+10",
  onUnifiedModeSelected,
}) => {
  const navigate = useNavigate();

  if (experienceLoading && !experienceConfig) {
    return (
      <Layout user={user}>
        <div
          className="flex min-h-[55vh] items-center justify-center gap-3 text-sm text-muted-foreground"
          data-testid="coach-play-experience-loading"
        >
          <Loader2 className="h-4 w-4 animate-spin" />
          Preparing your game…
        </div>
      </Layout>
    );
  }

  if (unifiedExperience) {
    return (
      <UnifiedCoachPlaySetup
        user={user}
        loading={loading}
        experienceLoading={experienceLoading}
        experienceConfig={experienceConfig}
        upgradeInfo={upgradeInfo}
        practiceMode={practiceMode}
        practicePosition={practicePosition}
        selectedColor={selectedColor}
        setSelectedColor={setSelectedColor}
        selectedOpening={selectedOpening}
        setSelectedOpening={setSelectedOpening}
        gameMode={gameMode}
        setGameMode={setGameMode}
        timeControl={timeControl}
        startGame={startGame}
        onModeSelected={onUnifiedModeSelected}
      />
    );
  }

  const identityLabel = playerIdentityData?.identity_label || "The Improviser";

  return (
    <Layout user={user} fullBleed={true}>
      <div className="w-full min-h-[calc(100vh-4rem)] p-3 sm:p-5 lg:p-7 flex flex-col justify-center items-center relative overflow-x-hidden" data-testid="coach-play-setup">
        {/* Ambient radial lighting */}
        <div className="absolute inset-0 bg-[radial-gradient(#0ea5e9_0.6px,transparent_0.6px)] [background-size:24px_24px] opacity-10 pointer-events-none" />
        <div className="absolute top-1/4 right-1/4 w-[550px] h-[550px] bg-cyan-500/10 rounded-full blur-[160px] pointer-events-none" />
        <div className="absolute bottom-1/4 left-1/4 w-[500px] h-[500px] bg-blue-600/5 dark:bg-indigo-600/10 rounded-full blur-[160px] pointer-events-none" />

        {/* Master Cockpit Deck (Enlarged & High-Impact) */}
        <div className="w-full max-w-[1400px] mx-auto flex flex-col gap-3 sm:gap-4 relative z-10">
          
          {/* Top Bar: Navigation + State Strip */}
          <div className="flex items-center justify-between gap-3 shrink-0">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/")}
              className="rounded-full bg-white/90 hover:bg-slate-100 text-slate-700 border border-slate-200 dark:bg-white/5 dark:hover:bg-white/10 dark:text-slate-300 dark:border-white/10 shadow-xs cursor-pointer h-8.5 px-3.5 text-xs font-semibold"
            >
              <ArrowLeft className="w-3.5 h-3.5 mr-1.5" />
              Back to Home
            </Button>
            <CurriculumStateStrip user={user} surface="play_with_coach" />
          </div>

          {/* ── UNIFIED MASTER COCKPIT CARD (Expanded & Theme-Adaptive) ── */}
          <div className="w-full rounded-2xl sm:rounded-3xl border border-slate-200/90 dark:border-white/15 bg-white dark:bg-gradient-to-b dark:from-[#1b2734] dark:via-[#131d27] dark:to-[#0b1118] shadow-xl dark:shadow-[0_25px_60px_rgba(0,0,0,0.7)] backdrop-blur-2xl p-5 sm:p-7 lg:p-9 relative overflow-hidden flex flex-col gap-5 sm:gap-6">
            
            {/* Header: Title + Coach Intelligence Pill */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-white/10">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs sm:text-[13px] font-mono uppercase tracking-[0.2em] text-cyan-800 dark:text-cyan-300 font-bold bg-cyan-100/80 dark:bg-cyan-950/80 border border-cyan-300/80 dark:border-cyan-500/40 px-3 py-1 rounded-full shadow-xs flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-cyan-500 dark:bg-cyan-400 animate-pulse" />
                    Grandmaster Match Setup
                  </span>
                </div>
                <h1 className="font-heading font-black text-2xl sm:text-3xl lg:text-[32px] text-slate-900 dark:text-white tracking-tight">
                  {practiceMode ? "Let’s replay the critical moment." : "Let’s play one thoughtful game."}
                </h1>
                <p className="text-slate-600 dark:text-slate-300 text-sm sm:text-base mt-1 font-normal leading-relaxed">
                  {practiceMode
                    ? "You know what happened before. This time, slow the position down and find a better plan."
                    : "Choose your side and how you want me beside you. I’ll watch for the habits we’ve been working on."}
                </p>
              </div>

              {/* Coach Intelligence Dossier Header Pill */}
              {!practiceMode && (
                <div className="sm:self-center shrink-0 flex items-center gap-3.5 py-3 px-4.5 rounded-2xl bg-slate-50 dark:bg-white/[0.04] border border-slate-200 dark:border-cyan-500/30 shadow-xs">
                  <div className="relative shrink-0">
                    <div className="w-11 h-11 rounded-xl overflow-hidden ring-2 ring-cyan-500/40 dark:ring-cyan-400/60 bg-slate-200 dark:bg-slate-800">
                      <img
                        src="/coach-jessica.png"
                        alt="Coach Jessica"
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          e.target.onerror = null;
                          e.target.src = "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150&auto=format&fit=crop&q=80";
                        }}
                      />
                    </div>
                    <div className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 bg-emerald-500 rounded-full ring-2 ring-white dark:ring-[#121a24]" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs sm:text-[13px] font-mono uppercase tracking-wider text-cyan-800 dark:text-cyan-300 font-bold">Coach Jessica</span>
                      <span className="text-xs font-mono text-emerald-600 dark:text-emerald-400 font-bold">• Synced</span>
                    </div>
                    <div className="text-xs sm:text-sm text-slate-700 dark:text-slate-200 font-medium truncate mt-0.5">
                      Style match: <span className="font-extrabold text-amber-600 dark:text-amber-300">♞ {identityLabel}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Practice Mode Indicator (if active) */}
            {practiceMode && practicePosition && (
              <div
                className="p-3.5 rounded-xl bg-cyan-50 dark:bg-cyan-950/50 border border-cyan-200 dark:border-cyan-500/40 shadow-xs"
                data-testid="practice-mode-indicator"
              >
                <div className="flex items-center gap-2 mb-0.5">
                  <Target className="w-4 h-4 text-cyan-600 dark:text-cyan-400" />
                  <span className="font-heading font-bold text-sm text-cyan-800 dark:text-cyan-300">A position from your game</span>
                </div>
                <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                  Start where the game turned. I’ll stay with you while you try a different plan.
                </p>
              </div>
            )}

            {/* 2-Column Balanced Cockpit Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 lg:gap-7 items-stretch">
              
              {/* ── LEFT COLUMN (7 cols): Army & Coaching Proximity ── */}
              <div className="lg:col-span-7 flex flex-col gap-5">
                
                {/* Step 1: Army Selection */}
                <div className="flex flex-col gap-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs sm:text-[13px] font-mono uppercase tracking-[0.2em] text-cyan-700 dark:text-cyan-400 font-bold flex items-center gap-1.5">
                      Step 1 · Choose Your Army
                    </span>
                    <span className="text-xs sm:text-[13px] font-mono text-slate-700 dark:text-slate-300 font-semibold px-3 py-1 rounded-md bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10">
                      {selectedColor === "white" ? "White (Initiative)" : "Black (Counter-Strike)"}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3.5">
                    {/* White Side Card */}
                    <button
                      type="button"
                      onClick={() => setSelectedColor("white")}
                      disabled={practiceMode}
                      data-testid="select-white"
                      className={`group relative rounded-2xl p-4 sm:p-5 border text-left transition-all duration-300 cursor-pointer overflow-hidden ${
                        selectedColor === "white"
                          ? "border-2 border-cyan-400 bg-gradient-to-br from-cyan-100/90 via-cyan-50 to-white dark:from-cyan-950/90 dark:via-[#102538] dark:to-[#0a1824] text-slate-900 dark:text-white shadow-lg dark:shadow-[0_0_25px_rgba(56,189,248,0.3)] ring-2 ring-cyan-400/60"
                          : "border border-slate-200/90 dark:border-white/10 bg-slate-50/70 dark:bg-white/[0.03] hover:border-cyan-400/50 hover:bg-slate-100/70 dark:hover:bg-white/[0.06] text-slate-800 dark:text-slate-200"
                      } ${practiceMode ? "opacity-60 cursor-not-allowed" : ""}`}
                    >
                      {selectedColor === "white" && (
                        <div className="absolute top-0 inset-x-0 h-[2.5px] bg-gradient-to-r from-transparent via-cyan-400 to-transparent shadow-[0_0_10px_#38bdf8]" />
                      )}
                      <div className="flex items-center gap-4 relative z-10">
                        <div className={`relative w-14 h-14 sm:w-16 sm:h-16 rounded-xl overflow-hidden ring-1 ring-slate-300 dark:ring-white/30 bg-gradient-to-br from-slate-100 via-slate-200 to-slate-300 flex items-center justify-center shrink-0 shadow-sm ${selectedColor === "white" ? "ring-2 ring-cyan-400" : ""}`}>
                          <img
                            src="/assets/studio/white_piece_king.jpg"
                            alt="White King"
                            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
                            onError={(e) => {
                              e.currentTarget.style.display = "none";
                              const fallback = e.currentTarget.nextElementSibling;
                              if (fallback) fallback.style.display = "flex";
                            }}
                          />
                          <div style={{ display: "none" }} className="w-full h-full items-center justify-center text-4xl select-none text-slate-800">
                            ♔
                          </div>
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center justify-between gap-1 mb-1">
                            <span className="font-heading font-black text-lg sm:text-xl text-slate-900 dark:text-white">White</span>
                            <span className={`text-xs font-mono font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full ${
                              selectedColor === "white" ? "bg-cyan-500 text-white dark:bg-cyan-400 dark:text-slate-950 font-black shadow-xs ring-1 ring-cyan-400/50" : "bg-slate-200 text-slate-700 dark:bg-white/10 dark:text-slate-300"
                            }`}>
                              Play 1st
                            </span>
                          </div>
                          <p className="text-sm sm:text-base text-slate-800 dark:text-slate-100 font-bold truncate">1. e4 / 1. d4</p>
                          <p className={`text-xs sm:text-[13.5px] font-mono truncate font-semibold mt-0.5 ${selectedColor === "white" ? "text-cyan-800 dark:text-cyan-300" : "text-slate-500 dark:text-slate-400"}`}>Command center</p>
                        </div>
                      </div>
                    </button>

                    {/* Black Side Card */}
                    <button
                      type="button"
                      onClick={() => setSelectedColor("black")}
                      disabled={practiceMode}
                      data-testid="select-black"
                      className={`group relative rounded-2xl p-4 sm:p-5 border text-left transition-all duration-300 cursor-pointer overflow-hidden ${
                        selectedColor === "black"
                          ? "border-2 border-cyan-400 bg-gradient-to-br from-cyan-100/90 via-cyan-50 to-white dark:from-cyan-950/90 dark:via-[#102538] dark:to-[#0a1824] text-slate-900 dark:text-white shadow-lg dark:shadow-[0_0_25px_rgba(56,189,248,0.3)] ring-2 ring-cyan-400/60"
                          : "border border-slate-200/90 dark:border-white/10 bg-slate-50/70 dark:bg-white/[0.03] hover:border-cyan-400/50 hover:bg-slate-100/70 dark:hover:bg-white/[0.06] text-slate-800 dark:text-slate-200"
                      } ${practiceMode ? "opacity-60 cursor-not-allowed" : ""}`}
                    >
                      {selectedColor === "black" && (
                        <div className="absolute top-0 inset-x-0 h-[2.5px] bg-gradient-to-r from-transparent via-cyan-400 to-transparent shadow-[0_0_10px_#38bdf8]" />
                      )}
                      <div className="flex items-center gap-4 relative z-10">
                        <div className={`relative w-14 h-14 sm:w-16 sm:h-16 rounded-xl overflow-hidden ring-1 ring-slate-400 dark:ring-slate-700 bg-gradient-to-br from-slate-900 via-slate-800 to-black flex items-center justify-center shrink-0 shadow-sm ${selectedColor === "black" ? "ring-2 ring-cyan-400" : ""}`}>
                          <img
                            src="/assets/studio/black_piece_king.jpg"
                            alt="Black King"
                            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
                            onError={(e) => {
                              e.currentTarget.style.display = "none";
                              const fallback = e.currentTarget.nextElementSibling;
                              if (fallback) fallback.style.display = "flex";
                            }}
                          />
                          <div style={{ display: "none" }} className="w-full h-full items-center justify-center text-4xl select-none text-slate-200">
                            ♚
                          </div>
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center justify-between gap-1 mb-1">
                            <span className="font-heading font-black text-lg sm:text-xl text-slate-900 dark:text-white">Black</span>
                            <span className={`text-xs font-mono font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full ${
                              selectedColor === "black" ? "bg-cyan-500 text-white dark:bg-cyan-400 dark:text-slate-950 font-black shadow-xs ring-1 ring-cyan-400/50" : "bg-slate-200 text-slate-700 dark:bg-white/10 dark:text-slate-300"
                            }`}>
                              Play 2nd
                            </span>
                          </div>
                          <p className="text-sm sm:text-base text-slate-800 dark:text-slate-100 font-bold truncate">1... e5 / c5</p>
                          <p className={`text-xs sm:text-[13.5px] font-mono truncate font-semibold mt-0.5 ${selectedColor === "black" ? "text-cyan-800 dark:text-cyan-300" : "text-slate-500 dark:text-slate-400"}`}>Absorb & strike</p>
                        </div>
                      </div>
                    </button>
                  </div>
                </div>

                {/* Step 2: Guidance Level */}
                {!practiceMode && (
                  <div className="flex flex-col gap-2.5">
                    <div className="flex items-center justify-between">
                      <span className="text-xs sm:text-[13px] font-mono uppercase tracking-[0.2em] text-cyan-700 dark:text-cyan-400 font-bold flex items-center gap-1.5">
                        Step 2 · Coaching Proximity
                      </span>
                      <span className="text-xs sm:text-[13px] font-mono text-slate-700 dark:text-slate-300 font-semibold px-3 py-1 rounded-md bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10">
                        Select style
                      </span>
                    </div>

                    <div className="grid grid-cols-3 gap-3">
                      {/* Stay with me */}
                      <button
                        type="button"
                        onClick={() => {
                          setGameMode("coach");
                          setEvidenceMode("practice_assisted");
                        }}
                        data-testid="evidence-mode-practice"
                        className={`relative rounded-2xl p-3.5 sm:p-4 border text-left transition-all duration-300 cursor-pointer overflow-hidden flex flex-col justify-between ${
                          evidenceMode === "practice_assisted"
                            ? "border-2 border-cyan-400 bg-gradient-to-b from-cyan-100/90 via-cyan-50/90 to-white dark:from-cyan-500/25 dark:via-[#0e2738] dark:to-[#081824] shadow-lg dark:shadow-[0_0_22px_rgba(56,189,248,0.3)] ring-2 ring-cyan-400/60"
                            : "border border-slate-200/90 dark:border-white/10 bg-slate-50/70 dark:bg-white/[0.03] hover:border-cyan-400/50 hover:bg-slate-100/70 dark:hover:bg-white/[0.06]"
                        }`}
                      >
                        {evidenceMode === "practice_assisted" && (
                          <div className="absolute top-0 inset-x-0 h-[2.5px] bg-gradient-to-r from-transparent via-cyan-400 to-transparent shadow-[0_0_8px_#38bdf8]" />
                        )}
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <div className={`w-9 h-9 sm:w-10 sm:h-10 rounded-xl flex items-center justify-center ${
                              evidenceMode === "practice_assisted" ? "bg-cyan-500 text-white dark:bg-cyan-400 dark:text-slate-950 shadow-xs font-black ring-1 ring-cyan-400/50" : "bg-slate-200 dark:bg-white/10 text-cyan-600 dark:text-cyan-400"
                            }`}>
                              <Brain className="w-5 h-5" strokeWidth={2.4} />
                            </div>
                            <span className={`text-[11px] sm:text-xs font-mono font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full ${
                              evidenceMode === "practice_assisted" ? "bg-cyan-500 text-white dark:bg-cyan-400 dark:text-slate-950 font-black shadow-xs ring-1 ring-cyan-400/40" : "bg-cyan-100 text-cyan-800 dark:bg-cyan-950/80 dark:border dark:border-cyan-500/40 dark:text-cyan-300"
                            }`}>
                              Rec
                            </span>
                          </div>
                          <div className="font-heading font-black text-base sm:text-lg text-slate-900 dark:text-white mb-1">Stay with me</div>
                          <p className={`text-xs sm:text-sm font-medium leading-snug ${evidenceMode === "practice_assisted" ? "text-cyan-950 dark:text-cyan-200 font-semibold" : "text-slate-600 dark:text-slate-400"}`}>Live prompts & warnings</p>
                        </div>
                        {evidenceMode === "practice_assisted" && (
                          <div className="mt-3 pt-2.5 border-t border-cyan-300/80 dark:border-cyan-500/30 flex items-center gap-1.5 text-xs font-mono font-bold text-cyan-800 dark:text-cyan-300">
                            <Check className="w-4 h-4 text-cyan-600 dark:text-cyan-400" />
                            <span>Active Mentor</span>
                          </div>
                        )}
                      </button>

                      {/* Test this lesson */}
                      <button
                        type="button"
                        onClick={() => {
                          setGameMode("play");
                          setEvidenceMode("checkpoint_unassisted");
                        }}
                        data-testid="evidence-mode-checkpoint"
                        className={`relative rounded-2xl p-3.5 sm:p-4 border text-left transition-all duration-300 cursor-pointer overflow-hidden flex flex-col justify-between ${
                          evidenceMode === "checkpoint_unassisted"
                            ? "border-2 border-amber-400 bg-gradient-to-b from-amber-100/90 via-amber-50/90 to-white dark:from-amber-500/25 dark:via-[#2b1f10] dark:to-[#171008] shadow-lg dark:shadow-[0_0_22px_rgba(245,158,11,0.3)] ring-2 ring-amber-400/60"
                            : "border border-slate-200/90 dark:border-white/10 bg-slate-50/70 dark:bg-white/[0.03] hover:border-amber-400/50 hover:bg-slate-100/70 dark:hover:bg-white/[0.06]"
                        }`}
                      >
                        {evidenceMode === "checkpoint_unassisted" && (
                          <div className="absolute top-0 inset-x-0 h-[2.5px] bg-gradient-to-r from-transparent via-amber-400 to-transparent shadow-[0_0_8px_#f59e0b]" />
                        )}
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <div className={`w-9 h-9 sm:w-10 sm:h-10 rounded-xl flex items-center justify-center ${
                              evidenceMode === "checkpoint_unassisted" ? "bg-amber-500 text-white dark:bg-amber-400 dark:text-slate-950 shadow-xs font-black ring-1 ring-amber-400/50" : "bg-slate-200 dark:bg-white/10 text-amber-600 dark:text-amber-400"
                            }`}>
                              <Target className="w-5 h-5" strokeWidth={2.4} />
                            </div>
                            <span className={`text-[11px] sm:text-xs font-mono font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full ${
                              evidenceMode === "checkpoint_unassisted" ? "bg-amber-500 text-white dark:bg-amber-400 dark:text-slate-950 font-black shadow-xs ring-1 ring-amber-400/40" : "bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:border dark:border-amber-500/40 dark:text-amber-300"
                            }`}>
                              Test
                            </span>
                          </div>
                          <div className="font-heading font-black text-base sm:text-lg text-slate-900 dark:text-white mb-1">Test mode</div>
                          <p className={`text-xs sm:text-sm font-medium leading-snug ${evidenceMode === "checkpoint_unassisted" ? "text-amber-950 dark:text-amber-200 font-semibold" : "text-slate-600 dark:text-slate-400"}`}>No help during play</p>
                        </div>
                        {evidenceMode === "checkpoint_unassisted" && (
                          <div className="mt-3 pt-2.5 border-t border-amber-300/80 dark:border-amber-500/30 flex items-center gap-1.5 text-xs font-mono font-bold text-amber-800 dark:text-amber-300">
                            <Check className="w-4 h-4 text-amber-600 dark:text-amber-400" />
                            <span>Diagnostic Exam</span>
                          </div>
                        )}
                      </button>

                      {/* Just play */}
                      <button
                        type="button"
                        onClick={() => {
                          setGameMode("play");
                          setEvidenceMode("just_play");
                        }}
                        data-testid="evidence-mode-just-play"
                        className={`relative rounded-2xl p-3.5 sm:p-4 border text-left transition-all duration-300 cursor-pointer overflow-hidden flex flex-col justify-between ${
                          evidenceMode === "just_play"
                            ? "border-2 border-violet-400 bg-gradient-to-b from-violet-100/90 via-violet-50/90 to-white dark:from-violet-500/25 dark:via-[#28183d] dark:to-[#140b20] shadow-lg dark:shadow-[0_0_22px_rgba(139,92,246,0.3)] ring-2 ring-violet-400/60"
                            : "border border-slate-200/90 dark:border-white/10 bg-slate-50/70 dark:bg-white/[0.03] hover:border-violet-400/50 hover:bg-slate-100/70 dark:hover:bg-white/[0.06]"
                        }`}
                      >
                        {evidenceMode === "just_play" && (
                          <div className="absolute top-0 inset-x-0 h-[2.5px] bg-gradient-to-r from-transparent via-violet-400 to-transparent shadow-[0_0_8px_#8b5cf6]" />
                        )}
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <div className={`w-9 h-9 sm:w-10 sm:h-10 rounded-xl flex items-center justify-center ${
                              evidenceMode === "just_play" ? "bg-violet-500 text-white dark:bg-violet-400 dark:text-slate-950 shadow-xs font-black ring-1 ring-violet-400/50" : "bg-slate-200 dark:bg-white/10 text-violet-600 dark:text-violet-400"
                            }`}>
                              <Play className="w-5 h-5" strokeWidth={2.4} />
                            </div>
                            <span className={`text-[11px] sm:text-xs font-mono font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full ${
                              evidenceMode === "just_play" ? "bg-violet-500 text-white dark:bg-violet-400 dark:text-slate-950 font-black shadow-xs ring-1 ring-violet-400/40" : "bg-violet-100 text-violet-800 dark:bg-violet-950/80 dark:border dark:border-violet-500/40 dark:text-violet-300"
                            }`}>
                              Classic
                            </span>
                          </div>
                          <div className="font-heading font-black text-base sm:text-lg text-slate-900 dark:text-white mb-1">Just play</div>
                          <p className={`text-xs sm:text-sm font-medium leading-snug ${evidenceMode === "just_play" ? "text-violet-950 dark:text-violet-200 font-semibold" : "text-slate-600 dark:text-slate-400"}`}>Review habits later</p>
                        </div>
                        {evidenceMode === "just_play" && (
                          <div className="mt-3 pt-2.5 border-t border-violet-300/80 dark:border-violet-500/30 flex items-center gap-1.5 text-xs font-mono font-bold text-violet-800 dark:text-violet-300">
                            <Check className="w-4 h-4 text-violet-600 dark:text-violet-400" />
                            <span>Uninterrupted</span>
                          </div>
                        )}
                      </button>
                    </div>
                  </div>
                )}

                {/* Left side reassurance badge */}
                <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-white/[0.03] border border-slate-200 dark:border-white/5 text-xs sm:text-sm text-slate-700 dark:text-slate-300 flex items-center gap-2.5">
                  <Brain className="w-5 h-5 text-cyan-600 dark:text-cyan-400 shrink-0" />
                  <span className="leading-snug font-medium">Coach Jessica monitors move-by-move quality adapted to your rating tier.</span>
                </div>
              </div>

              {/* ── RIGHT COLUMN (5 cols): Opening Preparation & Launch Command Station ── */}
              <div className="lg:col-span-5 flex flex-col justify-between rounded-2xl sm:rounded-3xl bg-slate-50/70 dark:bg-white/[0.03] border border-slate-200/90 dark:border-white/10 p-5 sm:p-6">
                
                {/* Top part: Openings & Guided Mode */}
                <div className="flex flex-col gap-3.5">
                  {!practiceMode && (
                    <OpeningSuggestions
                      selectedColor={selectedColor}
                      selectedOpening={selectedOpening}
                      onSelectOpening={setSelectedOpening}
                    />
                  )}

                  {/* Guided Mode Toggle (if opening picked) */}
                  {!practiceMode && selectedOpening && (
                    <div className="pt-3.5 border-t border-slate-200 dark:border-white/10">
                      <label className="text-xs sm:text-[13px] font-mono font-bold uppercase tracking-wider mb-2 block text-slate-800 dark:text-slate-200">
                        How should I help with this opening?
                      </label>
                      <div className="grid grid-cols-2 gap-2.5">
                        <button
                          type="button"
                          onClick={() => setGuidedMode(true)}
                          className={`p-3 rounded-xl border text-left transition-all duration-200 cursor-pointer ${
                            guidedMode
                              ? "border-2 border-cyan-400 bg-cyan-100/90 dark:bg-cyan-950/90 text-slate-900 dark:text-white shadow-sm ring-1 ring-cyan-400/50 font-bold"
                              : "border border-slate-200/90 dark:border-white/10 bg-white dark:bg-white/5 hover:border-cyan-400/40 text-slate-700 dark:text-slate-300"
                          }`}
                        >
                          <div className="flex items-center gap-2.5">
                            <Navigation className={`w-4.5 h-4.5 shrink-0 ${guidedMode ? "text-cyan-600 dark:text-cyan-400" : "text-slate-400"}`} strokeWidth={2.4} />
                            <span className="font-heading font-bold text-sm sm:text-base truncate">Show ideas</span>
                          </div>
                        </button>
                        <button
                          type="button"
                          onClick={() => setGuidedMode(false)}
                          className={`p-3 rounded-xl border text-left transition-all duration-200 cursor-pointer ${
                            !guidedMode
                              ? "border-2 border-cyan-400 bg-cyan-100/90 dark:bg-cyan-950/90 text-slate-900 dark:text-white shadow-sm ring-1 ring-cyan-400/50 font-bold"
                              : "border border-slate-200/90 dark:border-white/10 bg-white dark:bg-white/5 hover:border-cyan-400/40 text-slate-700 dark:text-slate-300"
                          }`}
                        >
                          <div className="flex items-center gap-2.5">
                            <GraduationCap className={`w-4.5 h-4.5 shrink-0 ${!guidedMode ? "text-cyan-600 dark:text-cyan-400" : "text-slate-400"}`} strokeWidth={2.4} />
                            <span className="font-heading font-bold text-sm sm:text-base truncate">Let me remember</span>
                          </div>
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                {/* Bottom part: Launch Button & Reassurance */}
                <div className="pt-4 mt-3 border-t border-slate-200 dark:border-white/10 space-y-2.5">
                  <Button
                    onClick={startGame}
                    disabled={loading}
                    className="w-full h-14 sm:h-16 py-3.5 rounded-2xl bg-gradient-to-r from-cyan-500 via-sky-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-heading font-black text-base sm:text-lg uppercase tracking-wider shadow-lg shadow-cyan-500/25 hover:shadow-cyan-500/40 flex items-center justify-center gap-3 transition-all cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
                    data-testid="start-game-btn"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="w-5 h-5 animate-spin" />
                        <span>Setting Up Board with Stockfish...</span>
                      </>
                    ) : practiceMode ? (
                      <>
                        <Target className="w-5 h-5" strokeWidth={2.5} />
                        <span>Replay this position</span>
                      </>
                    ) : (
                      <>
                        <Swords className="w-5 h-5" strokeWidth={2.5} />
                        <span>Sit with me at the board</span>
                        <ArrowRight className="w-5 h-5" strokeWidth={2.5} />
                      </>
                    )}
                  </Button>
                  <p className="text-center text-xs sm:text-sm text-slate-600 dark:text-slate-300 font-medium">
                    You make every move. Jessica alerts you on critical turning points.
                  </p>
                </div>

              </div>
            </div>

          </div>

        </div>
      </div>

      {/* Pre-Game Streak Popup */}
      <PreGameStreakPopup
        userId={user?.user_id}
        isOpen={showPreGameStreakPopup}
        onClose={() => setShowPreGameStreakPopup(false)}
        onStartGame={actuallyStartGame}
      />
    </Layout>
  );
};

export default CoachPlaySetup;
