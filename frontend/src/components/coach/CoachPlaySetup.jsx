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
const OpeningSuggestions = ({ selectedColor, selectedOpening, onSelectOpening }) => {
  const [data, setData] = useState(null);
  useEffect(() => {
    fetch(`${API}/coach/play/opening-suggestions`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setData(d))
      .catch(() => {});
  }, []);

  if (!data || data.total_games === 0) return null;

  const statusCopy = {
    strong: "Feels familiar",
    learning: "Worth another look",
    weak: "Let’s make this clearer",
    new: "Try something new",
  };

  // Show openings for the selected color
  const colorOpenings = selectedColor === "white" ? data.white : data.black;
  if (!colorOpenings?.length) return null;

  // Find best opening
  const best = colorOpenings.reduce((a, b) =>
    (b.win_rate > a.win_rate && b.games >= 3) ? b : a, colorOpenings[0]
  );

  return (
    <motion.div
      variants={scaleIn}
      initial="initial"
      animate="animate"
      className="space-y-4 p-5 sm:p-6 rounded-2xl bg-gradient-to-b from-[#18232e]/95 via-[#131d27]/95 to-[#0b1118]/95 border border-white/15 shadow-xl backdrop-blur-xl relative overflow-hidden"
      data-testid="opening-suggestions"
    >
      <div className="absolute top-0 right-0 w-48 h-48 bg-cyan-500/5 rounded-full blur-3xl pointer-events-none" />

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3.5 border-b border-white/10">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-cyan-300 font-bold bg-cyan-950/80 border border-cyan-500/40 px-3 py-1 rounded-full shadow-sm flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
              Choose today’s first conversation
            </span>
          </div>
          <p className="font-heading font-extrabold text-base sm:text-lg text-white tracking-tight">
            Which opening shall we explore?
          </p>
        </div>
        {selectedOpening && (
          <button
            type="button"
            onClick={() => onSelectOpening(null)}
            className="self-start sm:self-auto text-xs font-mono font-bold text-cyan-400 hover:text-cyan-300 transition-colors px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 cursor-pointer"
          >
            Clear choice
          </button>
        )}
      </div>

      <div className="space-y-2.5">
        {colorOpenings.slice(0, 5).map((o, i) => {
          const isSelected = selectedOpening === o.name;
          const isBest = o.name === best.name && best.games >= 3;
          return (
            <button
              key={i}
              type="button"
              onClick={() => onSelectOpening(isSelected ? null : o.name)}
              className={`w-full flex items-center justify-between text-left p-3.5 sm:p-4 rounded-xl border transition-all duration-200 cursor-pointer ${
                isSelected
                  ? "border-cyan-400 bg-gradient-to-r from-cyan-950/80 via-[#112435] to-[#0a1622] text-white shadow-[0_0_25px_rgba(56,189,248,0.3)] ring-2 ring-cyan-400/50"
                  : "border-white/10 bg-[#121b25]/80 hover:border-cyan-400/40 hover:bg-[#162330] text-slate-200"
              }`}
            >
              <div className="flex items-center gap-3 min-w-0">
                <span className={`w-3 h-3 rounded-full shrink-0 transition-all ${
                  isSelected ? "bg-cyan-400 shadow-[0_0_10px_#38bdf8] ring-2 ring-cyan-400/50" : "bg-slate-600 border border-slate-500"
                }`} />
                <span className={`font-heading font-bold text-sm sm:text-base truncate ${isSelected ? "text-cyan-200" : "text-white"}`}>
                  {o.name}
                </span>
                {isBest && (
                  <span className="text-[10px] font-mono font-extrabold uppercase tracking-wider text-slate-950 bg-gradient-to-r from-amber-400 to-amber-500 px-2 py-0.5 rounded-full shrink-0 shadow-[0_0_10px_rgba(245,158,11,0.4)]" aria-label="Coach's pick">
                    ★ Coach's Pick
                  </span>
                )}
              </div>
              <span className={`text-xs font-mono font-semibold ml-2 shrink-0 px-2.5 py-1 rounded-md ${
                isSelected
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
                  : "bg-white/5 text-slate-400"
              }`}>
                {statusCopy[o.status] || "Explore this"}
              </span>
            </button>
          );
        })}
      </div>

      {best.games >= 3 && !selectedOpening && (
        <div className="p-3 rounded-xl bg-cyan-950/40 border border-cyan-500/20 flex items-center gap-2.5 text-xs text-slate-300">
          <Sparkles className="w-4 h-4 text-cyan-400 shrink-0" />
          <span>
            I’d begin with <span className="font-bold text-cyan-300">{best.name}</span>. It connects naturally to games you already play.
          </span>
        </div>
      )}
    </motion.div>
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
    <Layout user={user}>
      <div className="min-h-full py-6 px-4 sm:px-6 relative" data-testid="coach-play-setup">
        {/* Subtle Luxury Chessboard Grid Background */}
        <div className="absolute inset-0 bg-[radial-gradient(#38bdf8_0.75px,transparent_0.75px)] [background-size:24px_24px] opacity-15 pointer-events-none" />
        <div className="absolute top-0 right-1/4 w-[450px] h-[450px] bg-cyan-500/10 rounded-full blur-[150px] pointer-events-none" />
        <div className="absolute top-1/2 left-10 w-[400px] h-[400px] bg-indigo-600/10 rounded-full blur-[150px] pointer-events-none" />

        <div className="max-w-3xl mx-auto relative z-10">
          <div className="mb-6">
            <CurriculumStateStrip user={user} surface="play_with_coach" />
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/")}
            className="mb-6 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 dark:bg-white/5 dark:hover:bg-white/10 dark:text-slate-300 dark:border-white/10 cursor-pointer"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Home
          </Button>

          {/* Setup Hero Card */}
          <div className="bg-gradient-to-r from-[#172330]/95 via-[#131d27]/98 to-[#0e1620]/95 border border-white/15 rounded-3xl p-6 sm:p-8 shadow-[0_25px_60px_rgba(0,0,0,0.6)] backdrop-blur-2xl relative overflow-hidden mb-6">
            <div className="flex items-center gap-2 mb-2.5">
              <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-cyan-300 font-bold bg-cyan-950/80 border border-cyan-500/40 px-3 py-1 rounded-full shadow-[0_0_12px_rgba(56,189,248,0.25)] flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                Grandmaster Match Setup
              </span>
            </div>
            <h1 className="font-heading font-extrabold text-2xl sm:text-3xl text-white tracking-tight leading-snug">
              {practiceMode ? "Let’s replay the critical moment." : "Let’s play one thoughtful game."}
            </h1>
            <p className="text-slate-300 text-xs sm:text-sm mt-2 max-w-[620px] leading-relaxed font-normal">
              {practiceMode
                ? "You know what happened before. This time, slow the position down and find a better plan."
                : "Choose your side and how you want me beside you. I’ll watch for the habits we’ve been working on."}
            </p>
          </div>

          <motion.div variants={scaleIn} initial="initial" animate="animate">
            <div className="bg-gradient-to-b from-[#18232e]/95 via-[#121a24]/95 to-[#0b1118]/95 border border-white/15 rounded-3xl p-6 sm:p-8 shadow-[0_25px_60px_rgba(0,0,0,0.7)] backdrop-blur-2xl">
              <motion.div
                variants={staggerContainer}
                initial="initial"
                animate="animate"
                className="space-y-7"
              >
              {/* Practice Mode Indicator */}
              {practiceMode && practicePosition && (
                <motion.div
                  variants={staggerItem}
                  className="p-5 rounded-2xl bg-cyan-950/40 border border-cyan-500/40 shadow-lg backdrop-blur-md"
                  data-testid="practice-mode-indicator"
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <Target className="w-4 h-4 text-cyan-400" />
                    <span className="font-heading font-bold text-sm text-cyan-300">A position from your game</span>
                  </div>
                  <p className="text-xs sm:text-sm text-slate-300 leading-relaxed font-normal">
                    Start where the game turned. I’ll stay with you while you try a different plan.
                  </p>
                </motion.div>
              )}

              {/* 1. Color Selection (White vs Black) */}
              <motion.div variants={staggerItem}>
                <div className="flex items-center justify-between mb-3.5">
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-cyan-400 font-bold block mb-1">
                      Which side would you like?
                    </span>
                    <h3 className="font-heading font-extrabold text-base sm:text-lg text-white tracking-tight">
                      Choose Your Army
                    </h3>
                  </div>
                  <span className="text-xs font-mono text-slate-400 font-semibold px-2.5 py-1 rounded-md bg-white/5 border border-white/10">
                    {selectedColor === "white" ? "White (Initiative)" : "Black (Counter-Attack)"}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {/* White Side Card */}
                  <button
                    type="button"
                    onClick={() => setSelectedColor("white")}
                    disabled={practiceMode}
                    data-testid="select-white"
                    className={`group relative rounded-2xl p-5 border text-left transition-all duration-300 cursor-pointer overflow-hidden ${
                      selectedColor === "white"
                        ? "border-amber-400/90 dark:border-cyan-400 bg-gradient-to-br from-[#1d2d3d] via-[#142331] to-[#0b141d] shadow-[0_0_30px_rgba(56,189,248,0.35),inset_0_1px_1px_rgba(255,255,255,0.2)] ring-2 ring-cyan-400/60"
                        : "border-white/15 bg-gradient-to-b from-[#15202a]/85 to-[#0d151c]/85 hover:border-cyan-400/40 hover:bg-[#182430]/90"
                    } ${practiceMode ? "opacity-60 cursor-not-allowed" : ""}`}
                  >
                    {selectedColor === "white" && (
                      <div className="absolute top-0 right-0 w-36 h-36 bg-cyan-400/15 rounded-full blur-2xl pointer-events-none" />
                    )}
                    <div className="flex items-center gap-4 relative z-10">
                      {/* Realistic Piece Display */}
                      <div className="relative w-16 h-16 sm:w-18 sm:h-18 rounded-2xl overflow-hidden ring-2 ring-white/30 shadow-xl bg-gradient-to-br from-slate-100 via-slate-200 to-slate-300 flex items-center justify-center shrink-0">
                        <img
                          src="/assets/studio/white_piece_king.jpg"
                          alt="White King"
                          className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
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
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="font-heading font-black text-xl text-white tracking-tight">
                            White
                          </span>
                          <span className={`text-[10px] font-mono font-black uppercase tracking-wider px-2.5 py-0.5 rounded-full transition-all ${
                            selectedColor === "white"
                              ? "bg-cyan-400 text-slate-950 shadow-[0_0_12px_#38bdf8]"
                              : "bg-white/10 text-slate-300"
                          }`}>
                            Play 1st
                          </span>
                        </div>
                        <p className="text-xs sm:text-sm text-slate-200 font-semibold leading-snug">
                          First Initiative · 1. e4 / 1. d4
                        </p>
                        <p className="text-[11px] text-cyan-300 font-mono mt-1 flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                          Set the tempo & command the center
                        </p>
                      </div>
                    </div>
                  </button>

                  {/* Black Side Card */}
                  <button
                    type="button"
                    onClick={() => setSelectedColor("black")}
                    disabled={practiceMode}
                    data-testid="select-black"
                    className={`group relative rounded-2xl p-5 border text-left transition-all duration-300 cursor-pointer overflow-hidden ${
                      selectedColor === "black"
                        ? "border-cyan-400 bg-gradient-to-br from-[#1d2d3d] via-[#142331] to-[#0b141d] shadow-[0_0_30px_rgba(56,189,248,0.35),inset_0_1px_1px_rgba(255,255,255,0.2)] ring-2 ring-cyan-400/60"
                        : "border-white/15 bg-gradient-to-b from-[#15202a]/85 to-[#0d151c]/85 hover:border-cyan-400/40 hover:bg-[#182430]/90"
                    } ${practiceMode ? "opacity-60 cursor-not-allowed" : ""}`}
                  >
                    {selectedColor === "black" && (
                      <div className="absolute top-0 right-0 w-36 h-36 bg-cyan-400/15 rounded-full blur-2xl pointer-events-none" />
                    )}
                    <div className="flex items-center gap-4 relative z-10">
                      {/* Realistic Piece Display */}
                      <div className="relative w-16 h-16 sm:w-18 sm:h-18 rounded-2xl overflow-hidden ring-2 ring-slate-700 shadow-xl bg-gradient-to-br from-slate-900 via-slate-800 to-black flex items-center justify-center shrink-0">
                        <img
                          src="/assets/studio/black_piece_king.jpg"
                          alt="Black King"
                          className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
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
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="font-heading font-black text-xl text-white tracking-tight">
                            Black
                          </span>
                          <span className={`text-[10px] font-mono font-black uppercase tracking-wider px-2.5 py-0.5 rounded-full transition-all ${
                            selectedColor === "black"
                              ? "bg-cyan-400 text-slate-950 shadow-[0_0_12px_#38bdf8]"
                              : "bg-white/10 text-slate-300"
                          }`}>
                            Play 2nd
                          </span>
                        </div>
                        <p className="text-xs sm:text-sm text-slate-200 font-semibold leading-snug">
                          Counter-Strike · 1... e5 / 1... c5
                        </p>
                        <p className="text-[11px] text-cyan-300 font-mono mt-1 flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                          Absorb pressure & strike back
                        </p>
                      </div>
                    </div>
                  </button>
                </div>
                {practiceMode && (
                  <p className="text-xs text-slate-400 mt-2 font-mono">
                    Color is locked to your original game position.
                  </p>
                )}
              </motion.div>

              {/* 2. How close should I stay? (Coaching Proximity) */}
              {!practiceMode && (
                <motion.div variants={staggerItem}>
                  <div className="flex items-center justify-between mb-3.5">
                    <div>
                      <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-cyan-400 font-bold block mb-1">
                        How close should I stay?
                      </span>
                      <h3 className="font-heading font-extrabold text-base sm:text-lg text-white tracking-tight">
                        Coaching & Guidance Level
                      </h3>
                    </div>
                    <span className="text-xs font-mono text-slate-400 font-semibold px-2.5 py-1 rounded-md bg-white/5 border border-white/10">
                      Select your style
                    </span>
                  </div>

                  <div className="grid gap-4 md:grid-cols-3">
                    {/* Stay with me */}
                    <button
                      type="button"
                      onClick={() => {
                        setGameMode("coach");
                        setEvidenceMode("practice_assisted");
                      }}
                      data-testid="evidence-mode-practice"
                      className={`relative rounded-2xl p-5 border text-left transition-all duration-300 cursor-pointer overflow-hidden flex flex-col justify-between ${
                        evidenceMode === "practice_assisted"
                          ? "border-cyan-400 bg-gradient-to-b from-[#162d3e] via-[#10212e] to-[#0a1620] shadow-[0_0_30px_rgba(56,189,248,0.35)] ring-2 ring-cyan-400/60"
                          : "border-white/15 bg-gradient-to-b from-[#15202a]/85 to-[#0d151c]/85 hover:border-cyan-400/40 hover:bg-[#182430]/90"
                      }`}
                    >
                      <div>
                        <div className="flex items-center justify-between mb-3.5">
                          <div className={`w-11 h-11 rounded-xl flex items-center justify-center transition-all ${
                            evidenceMode === "practice_assisted"
                              ? "bg-cyan-400 text-slate-950 font-black shadow-[0_0_15px_rgba(56,189,248,0.5)]"
                              : "bg-white/10 text-cyan-400"
                          }`}>
                            <Brain className="w-5 h-5" strokeWidth={2.4} />
                          </div>
                          <span className={`text-[10px] font-mono font-black uppercase tracking-wider px-2.5 py-0.5 rounded-full transition-all ${
                            evidenceMode === "practice_assisted"
                              ? "bg-cyan-400 text-slate-950 shadow-[0_0_10px_#38bdf8]"
                              : "bg-cyan-950/80 border border-cyan-500/40 text-cyan-300"
                          }`}>
                            Recommended
                          </span>
                        </div>
                        <div className="font-heading font-extrabold text-base sm:text-lg text-white mb-1 tracking-tight">
                          Stay with me
                        </div>
                        <p className="text-xs sm:text-sm text-cyan-200 font-semibold mb-2 leading-snug">
                          Gentle questions while you play
                        </p>
                        <p className="text-xs text-slate-300/80 font-normal leading-relaxed">
                          Live guardian alerts before major blunders & helpful prompts.
                        </p>
                      </div>

                      {evidenceMode === "practice_assisted" && (
                        <div className="mt-4 pt-3 border-t border-cyan-500/20 flex items-center gap-1.5 text-[11px] font-mono font-bold text-cyan-300">
                          <Check className="w-3.5 h-3.5 text-cyan-400" />
                          <span>Active Mentor Enabled</span>
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
                      className={`relative rounded-2xl p-5 border text-left transition-all duration-300 cursor-pointer overflow-hidden flex flex-col justify-between ${
                        evidenceMode === "checkpoint_unassisted"
                          ? "border-amber-400 bg-gradient-to-b from-[#302413] via-[#22180b] to-[#140e06] shadow-[0_0_30px_rgba(245,158,11,0.35)] ring-2 ring-amber-400/60"
                          : "border-white/15 bg-gradient-to-b from-[#15202a]/85 to-[#0d151c]/85 hover:border-amber-400/40 hover:bg-[#182430]/90"
                      }`}
                    >
                      <div>
                        <div className="flex items-center justify-between mb-3.5">
                          <div className={`w-11 h-11 rounded-xl flex items-center justify-center transition-all ${
                            evidenceMode === "checkpoint_unassisted"
                              ? "bg-amber-400 text-slate-950 font-black shadow-[0_0_15px_rgba(245,158,11,0.5)]"
                              : "bg-white/10 text-amber-400"
                          }`}>
                            <Target className="w-5 h-5" strokeWidth={2.4} />
                          </div>
                          <span className={`text-[10px] font-mono font-black uppercase tracking-wider px-2.5 py-0.5 rounded-full transition-all ${
                            evidenceMode === "checkpoint_unassisted"
                              ? "bg-amber-400 text-slate-950 shadow-[0_0_10px_#f59e0b]"
                              : "bg-amber-950/80 border border-amber-500/40 text-amber-300"
                          }`}>
                            Test Mode
                          </span>
                        </div>
                        <div className="font-heading font-extrabold text-base sm:text-lg text-white mb-1 tracking-tight">
                          Test this lesson
                        </div>
                        <p className="text-xs sm:text-sm text-amber-200 font-semibold mb-2 leading-snug">
                          No help while you play
                        </p>
                        <p className="text-xs text-slate-300/80 font-normal leading-relaxed">
                          Independent exam. Diagnostic post-game breakdown afterwards.
                        </p>
                      </div>

                      {evidenceMode === "checkpoint_unassisted" && (
                        <div className="mt-4 pt-3 border-t border-amber-500/20 flex items-center gap-1.5 text-[11px] font-mono font-bold text-amber-300">
                          <Check className="w-3.5 h-3.5 text-amber-400" />
                          <span>Diagnostic Exam Selected</span>
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
                      className={`relative rounded-2xl p-5 border text-left transition-all duration-300 cursor-pointer overflow-hidden flex flex-col justify-between ${
                        evidenceMode === "just_play"
                          ? "border-violet-400 bg-gradient-to-b from-[#2a1c40] via-[#1d132e] to-[#100a1c] shadow-[0_0_30px_rgba(168,85,247,0.35)] ring-2 ring-violet-400/60"
                          : "border-white/15 bg-gradient-to-b from-[#15202a]/85 to-[#0d151c]/85 hover:border-violet-400/40 hover:bg-[#182430]/90"
                      }`}
                    >
                      <div>
                        <div className="flex items-center justify-between mb-3.5">
                          <div className={`w-11 h-11 rounded-xl flex items-center justify-center transition-all ${
                            evidenceMode === "just_play"
                              ? "bg-violet-400 text-slate-950 font-black shadow-[0_0_15px_rgba(168,85,247,0.5)]"
                              : "bg-white/10 text-violet-400"
                          }`}>
                            <Play className="w-5 h-5" strokeWidth={2.4} />
                          </div>
                          <span className={`text-[10px] font-mono font-black uppercase tracking-wider px-2.5 py-0.5 rounded-full transition-all ${
                            evidenceMode === "just_play"
                              ? "bg-violet-400 text-slate-950 shadow-[0_0_10px_#a855f7]"
                              : "bg-violet-950/80 border border-violet-500/40 text-violet-300"
                          }`}>
                            Classic
                          </span>
                        </div>
                        <div className="font-heading font-extrabold text-base sm:text-lg text-white mb-1 tracking-tight">
                          Just play
                        </div>
                        <p className="text-xs sm:text-sm text-violet-200 font-semibold mb-2 leading-snug">
                          We’ll still learn from it later
                        </p>
                        <p className="text-xs text-slate-300/80 font-normal leading-relaxed">
                          Uninterrupted chess at your tempo. Review habits whenever you wish.
                        </p>
                      </div>

                      {evidenceMode === "just_play" && (
                        <div className="mt-4 pt-3 border-t border-violet-500/20 flex items-center gap-1.5 text-[11px] font-mono font-bold text-violet-300">
                          <Check className="w-3.5 h-3.5 text-violet-400" />
                          <span>Uninterrupted Match Selected</span>
                        </div>
                      )}
                    </button>
                  </div>
                </motion.div>
              )}

              {/* 3. Coach Memory Dossier */}
              {!practiceMode && (
                <motion.div
                  variants={staggerItem}
                  className="p-5 sm:p-6 rounded-2xl border border-cyan-500/30 bg-gradient-to-r from-[#172330]/95 via-[#131d27]/95 to-[#0e1620]/95 shadow-xl relative overflow-hidden"
                >
                  <div className="absolute top-0 right-0 w-64 h-64 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

                  <div className="flex items-start gap-4 relative z-10">
                    <div className="relative shrink-0">
                      <div className="w-14 h-14 rounded-2xl overflow-hidden ring-2 ring-cyan-400/50 bg-slate-800 shadow-lg">
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
                      <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-emerald-500 rounded-full ring-2 ring-[#131d27] flex items-center justify-center">
                        <div className="w-2 h-2 bg-white rounded-full animate-ping" />
                      </div>
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                        <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-cyan-300 font-bold bg-cyan-950/80 border border-cyan-500/40 px-2.5 py-0.5 rounded-full shadow-sm flex items-center gap-1.5">
                          <Brain className="w-3 h-3 text-cyan-400" />
                          Coach Intelligence
                        </span>
                        <span className="text-xs font-mono text-emerald-400 font-semibold flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                          Profile Synced
                        </span>
                      </div>
                      <h4 className="font-heading font-extrabold text-base sm:text-lg text-white tracking-tight mb-1.5">
                        I remember your games
                      </h4>
                      <p className="text-xs sm:text-sm leading-relaxed text-slate-200 font-normal">
                        You tend to play like{" "}
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md font-heading font-extrabold text-amber-300 bg-amber-950/80 border border-amber-500/40 shadow-sm mx-1">
                          ♞ {identityLabel}
                        </span>
                        . I’ll keep that in mind without taking the game away from you.
                      </p>
                    </div>
                  </div>
                </motion.div>
              )}

              {/* 4. Opening Suggestions */}
              {!practiceMode && (
                <OpeningSuggestions
                  selectedColor={selectedColor}
                  selectedOpening={selectedOpening}
                  onSelectOpening={setSelectedOpening}
                />
              )}

              {/* Guide Mode Toggle — only when an opening is selected */}
              {!practiceMode && selectedOpening && (
                <motion.div variants={staggerItem}>
                  <label className="text-xs font-mono font-bold uppercase tracking-wider mb-2.5 block text-slate-300">
                    How should I help with this opening?
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                    <button
                      type="button"
                      onClick={() => setGuidedMode(true)}
                      className={`p-4 rounded-2xl border text-left transition-all duration-200 cursor-pointer ${
                        guidedMode
                          ? "border-cyan-400 bg-gradient-to-b from-[#182836] via-[#121f2b] to-[#0c1620] shadow-[0_0_20px_rgba(56,189,248,0.3)] ring-2 ring-cyan-400/50"
                          : "border-white/15 bg-white/5 hover:border-cyan-400/40 hover:bg-white/10 text-slate-300"
                      }`}
                    >
                      <div className="flex items-center gap-3 mb-1.5">
                        <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${guidedMode ? "bg-cyan-400 text-slate-950 font-bold shadow-[0_0_10px_#38bdf8]" : "bg-white/10 text-slate-400"}`}>
                          <Navigation className="w-4 h-4" strokeWidth={2.4} />
                        </div>
                        <span className="font-heading font-extrabold text-sm sm:text-base text-white">Show me the ideas</span>
                      </div>
                      <p className="text-xs text-slate-300 font-normal leading-relaxed pl-12">
                        Prompts & alerts when theoretical opportunities appear.
                      </p>
                    </button>
                    <button
                      type="button"
                      onClick={() => setGuidedMode(false)}
                      className={`p-4 rounded-2xl border text-left transition-all duration-200 cursor-pointer ${
                        !guidedMode
                          ? "border-cyan-400 bg-gradient-to-b from-[#182836] via-[#121f2b] to-[#0c1620] shadow-[0_0_20px_rgba(56,189,248,0.3)] ring-2 ring-cyan-400/50"
                          : "border-white/15 bg-white/5 hover:border-cyan-400/40 hover:bg-white/10 text-slate-300"
                      }`}
                    >
                      <div className="flex items-center gap-3 mb-1.5">
                        <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${!guidedMode ? "bg-cyan-400 text-slate-950 font-bold shadow-[0_0_10px_#38bdf8]" : "bg-white/10 text-slate-400"}`}>
                          <GraduationCap className="w-4 h-4" strokeWidth={2.4} />
                        </div>
                        <span className="font-heading font-extrabold text-sm sm:text-base text-white">Let me remember</span>
                      </div>
                      <p className="text-xs text-slate-300 font-normal leading-relaxed pl-12">
                        Silent testing mode. Step in only if I ask for advice.
                      </p>
                    </button>
                  </div>
                </motion.div>
              )}

              {/* Start Button */}
              <motion.div variants={staggerItem} className="pt-2">
                <Button
                  onClick={startGame}
                  disabled={loading}
                  className="w-full h-14 sm:h-16 py-4 rounded-2xl bg-gradient-to-r from-cyan-400 via-cyan-500 to-blue-600 hover:from-cyan-300 hover:to-blue-500 text-slate-950 font-heading font-black text-sm sm:text-base uppercase tracking-wider shadow-[0_0_35px_rgba(56,189,248,0.45)] hover:shadow-[0_0_45px_rgba(56,189,248,0.7)] hover:scale-[1.01] active:scale-[0.99] flex items-center justify-center gap-3 transition-all cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
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
              </motion.div>

              {/* Footer Reassurance */}
              <motion.div
                variants={staggerItem}
                className="p-4 rounded-xl bg-white/[0.04] border border-white/10 text-xs sm:text-sm text-slate-300 backdrop-blur-sm flex items-center gap-3"
              >
                <Brain className="w-4 h-4 text-cyan-400 shrink-0" />
                <span>I’ll ask only the questions that matter for this game. You still make every decision.</span>
              </motion.div>
              </motion.div>
            </div>
          </motion.div>
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
