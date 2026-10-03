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
      className="space-y-4 p-5 rounded-2xl bg-gradient-to-b from-[#1e2a36]/80 to-[#162029]/80 border border-white/15 shadow-lg backdrop-blur-md"
      data-testid="opening-suggestions"
    >
      <div className="flex items-center justify-between">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-cyan-300 font-bold bg-cyan-950/60 border border-cyan-500/30 px-2.5 py-0.5 rounded-full inline-block mb-1.5">
            Choose today’s first conversation
          </span>
          <p className="font-serif text-xl text-white">Which opening shall we explore?</p>
        </div>
        {selectedOpening && (
          <button
            onClick={() => onSelectOpening(null)}
            className="text-xs text-slate-400 hover:text-cyan-400 transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      <div className="space-y-1.5">
        {colorOpenings.slice(0, 5).map((o, i) => {
          const isSelected = selectedOpening === o.name;
          const isBest = o.name === best.name && best.games >= 3;
          return (
            <button
              key={i}
              onClick={() => onSelectOpening(isSelected ? null : o.name)}
              className={`w-full flex items-center justify-between text-sm p-3.5 rounded-xl border transition-all ${
                isSelected
                  ? "border-cyan-500/60 bg-gradient-to-r from-cyan-950/50 to-slate-900/60 text-cyan-300 shadow-[0_0_15px_rgba(56,189,248,0.2)] ring-1 ring-cyan-400/40"
                  : "border-white/10 bg-white/5 hover:border-cyan-500/30 hover:bg-white/10 text-slate-200"
              }`}
            >
              <div className="flex items-center gap-2">
                {isBest && <span className="text-amber-400 text-xs" aria-label="Coach's pick">★</span>}
                <span className={`font-medium truncate max-w-[180px] ${isSelected ? "text-cyan-300" : "text-slate-200"}`}>
                  {o.name}
                </span>
              </div>
              <span className="text-xs text-slate-400">{statusCopy[o.status] || "Explore this"}</span>
            </button>
          );
        })}
      </div>

      {best.games >= 3 && !selectedOpening && (
        <p className="text-xs text-slate-300/80">
          I’d begin with <span className="font-medium text-cyan-300">{best.name}</span>. It connects naturally to games you already play.
        </p>
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

  return (
    <Layout user={user}>
      <div className="min-h-full py-6 px-4 sm:px-6 relative" data-testid="coach-play-setup">
        {/* Soft Ambient Studio Lighting */}
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-[140px] pointer-events-none" />
        <div className="absolute top-1/2 left-10 w-80 h-80 bg-blue-600/10 rounded-full blur-[140px] pointer-events-none" />

        <div className="max-w-3xl mx-auto relative z-10">
          <div className="mb-6">
            <CurriculumStateStrip user={user} surface="play_with_coach" />
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/")}
            className="mb-6 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 dark:bg-white/5 dark:hover:bg-white/10 dark:text-slate-300 dark:border-white/10"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Home
          </Button>

          {/* Setup hero card */}
          <div className="bg-white/95 dark:bg-gradient-to-b dark:from-[#25323d]/85 dark:to-[#1a232b]/85 border border-slate-200/90 dark:border-white/15 rounded-3xl p-7 sm:p-9 shadow-[0_20px_50px_rgba(0,0,0,0.06)] dark:shadow-[0_25px_60px_rgba(0,0,0,0.45)] backdrop-blur-xl relative overflow-hidden mb-8">
            <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-cyan-800 dark:text-cyan-300 font-bold bg-cyan-50 dark:bg-cyan-950/60 border border-cyan-200 dark:border-cyan-500/30 px-3 py-1 rounded-full inline-block mb-3 shadow-sm">
              At the board with your coach
            </span>
            <h1 className="font-serif text-3xl sm:text-4xl text-slate-900 dark:text-white font-normal tracking-tight">
              {practiceMode ? "Let’s replay the moment." : "Let’s play one thoughtful game."}
            </h1>
            <p className="text-slate-600 dark:text-slate-200/90 text-sm sm:text-base mt-3 max-w-[620px] leading-relaxed">
              {practiceMode
                ? "You know what happened before. This time, slow the position down and find a better story."
                : "Choose how you want me beside you. I’ll watch for the habits we’ve been working on."}
            </p>
          </div>

          <motion.div variants={scaleIn} initial="initial" animate="animate">
            <div className="bg-white/95 dark:bg-gradient-to-b dark:from-[#222e3b]/85 dark:to-[#18212a]/85 border border-slate-200/90 dark:border-white/15 rounded-3xl p-6 sm:p-8 shadow-[0_20px_50px_rgba(0,0,0,0.06)] dark:shadow-[0_25px_60px_rgba(0,0,0,0.45)] backdrop-blur-xl">
              <motion.div
                variants={staggerContainer}
                initial="initial"
                animate="animate"
                className="space-y-6"
              >
              {/* Practice Mode Indicator */}
              {practiceMode && practicePosition && (
                <motion.div
                  variants={staggerItem}
                  className="p-5 rounded-2xl bg-cyan-50 dark:bg-cyan-950/40 border border-cyan-200 dark:border-cyan-500/30 backdrop-blur-md"
                  data-testid="practice-mode-indicator"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Target className="w-4 h-4 text-cyan-600 dark:text-cyan-400" />
                    <span className="font-medium text-cyan-800 dark:text-cyan-300">A position from your game</span>
                  </div>
                  <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                    Start where the game turned. I’ll stay with you while you try a different plan.
                  </p>
                </motion.div>
              )}

              {/* Color Selection */}
              <motion.div variants={staggerItem}>
                <label className="text-sm font-medium mb-3 block text-slate-900 dark:text-slate-200">
                  Which side would you like?
                </label>
                <div className="flex gap-3">
                  <Button
                    variant={selectedColor === "white" ? "default" : "outline"}
                    onClick={() => setSelectedColor("white")}
                    className={`flex-1 h-auto py-3.5 px-4 rounded-xl border text-sm font-medium transition-all ${
                      selectedColor === "white"
                        ? "border-cyan-500/60 bg-cyan-50 text-cyan-900 shadow-sm ring-1 ring-cyan-500/40 dark:bg-gradient-to-b dark:from-cyan-950/40 dark:to-slate-900/60 dark:text-white dark:shadow-[0_0_20px_rgba(56,189,248,0.25)]"
                        : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100 dark:border-white/10 dark:bg-white/5 dark:text-slate-300"
                    }`}
                    data-testid="select-white"
                    disabled={practiceMode}
                  >
                    <div className="w-6 h-6 rounded-full bg-gradient-to-b from-white to-slate-200 border border-slate-300 shadow-sm mr-2.5 flex-shrink-0" />
                    White
                  </Button>
                  <Button
                    variant={selectedColor === "black" ? "default" : "outline"}
                    onClick={() => setSelectedColor("black")}
                    className={`flex-1 h-auto py-3.5 px-4 rounded-xl border text-sm font-medium transition-all ${
                      selectedColor === "black"
                        ? "border-cyan-500/60 bg-cyan-50 text-cyan-900 shadow-sm ring-1 ring-cyan-500/40 dark:bg-gradient-to-b dark:from-cyan-950/40 dark:to-slate-900/60 dark:text-white dark:shadow-[0_0_20px_rgba(56,189,248,0.25)]"
                        : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100 dark:border-white/10 dark:bg-white/5 dark:text-slate-300"
                    }`}
                    data-testid="select-black"
                    disabled={practiceMode}
                  >
                    <div className="w-6 h-6 rounded-full bg-gradient-to-b from-slate-800 to-slate-950 border border-slate-700 shadow-sm mr-2.5 flex-shrink-0" />
                    Black
                  </Button>
                </div>
                {practiceMode && (
                  <p className="text-xs text-muted-foreground mt-2">
                    Color is set based on your original game position.
                  </p>
                )}
              </motion.div>

              {/* Game Mode Selection */}
              {!practiceMode && (
                <motion.div variants={staggerItem}>
                  <label className="text-sm font-medium mb-3 block text-slate-900 dark:text-slate-200">
                    How close should I stay?
                  </label>
                  <div className="grid gap-3 md:grid-cols-3">
                    <Button
                      variant={evidenceMode === "practice_assisted" ? "default" : "outline"}
                      onClick={() => {
                        setGameMode("coach");
                        setEvidenceMode("practice_assisted");
                      }}
                      className={`flex-1 h-auto py-4 px-3 rounded-2xl border text-center transition-all ${
                        evidenceMode === "practice_assisted"
                          ? "border-cyan-500/60 bg-cyan-50 text-cyan-900 shadow-sm ring-1 ring-cyan-500/40 dark:bg-gradient-to-b dark:from-cyan-950/40 dark:to-slate-900/60 dark:text-white dark:shadow-[0_0_20px_rgba(56,189,248,0.25)]"
                          : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100 dark:border-white/10 dark:bg-white/5 dark:text-slate-300"
                      }`}
                      data-testid="evidence-mode-practice"
                    >
                      <div className="flex flex-col items-center gap-1.5">
                        <Brain className={`w-5 h-5 ${evidenceMode === "practice_assisted" ? "text-cyan-600 dark:text-cyan-400" : "text-slate-400"}`} />
                        <span className="text-sm font-medium">Stay with me</span>
                        <span className="text-[10px] text-inherit opacity-75">Gentle questions while you play</span>
                      </div>
                    </Button>
                    <Button
                      variant={evidenceMode === "checkpoint_unassisted" ? "default" : "outline"}
                      onClick={() => {
                        setGameMode("play");
                        setEvidenceMode("checkpoint_unassisted");
                      }}
                      className={`flex-1 h-auto py-4 px-3 rounded-2xl border text-center transition-all ${
                        evidenceMode === "checkpoint_unassisted"
                          ? "border-cyan-500/60 bg-cyan-50 text-cyan-900 shadow-sm ring-1 ring-cyan-500/40 dark:bg-gradient-to-b dark:from-cyan-950/40 dark:to-slate-900/60 dark:text-white dark:shadow-[0_0_20px_rgba(56,189,248,0.25)]"
                          : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100 dark:border-white/10 dark:bg-white/5 dark:text-slate-300"
                      }`}
                      data-testid="evidence-mode-checkpoint"
                    >
                      <div className="flex flex-col items-center gap-1.5">
                        <Target className={`w-5 h-5 ${evidenceMode === "checkpoint_unassisted" ? "text-cyan-600 dark:text-cyan-400" : "text-slate-400"}`} />
                        <span className="text-sm font-medium">Test this lesson</span>
                        <span className="text-[10px] text-inherit opacity-75">No help while you play</span>
                      </div>
                    </Button>
                    <Button
                      variant={evidenceMode === "just_play" ? "default" : "outline"}
                      onClick={() => {
                        setGameMode("play");
                        setEvidenceMode("just_play");
                      }}
                      className={`flex-1 h-auto py-4 px-3 rounded-2xl border text-center transition-all ${
                        evidenceMode === "just_play"
                          ? "border-cyan-500/60 bg-cyan-50 text-cyan-900 shadow-sm ring-1 ring-cyan-500/40 dark:bg-gradient-to-b dark:from-cyan-950/40 dark:to-slate-900/60 dark:text-white dark:shadow-[0_0_20px_rgba(56,189,248,0.25)]"
                          : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100 dark:border-white/10 dark:bg-white/5 dark:text-slate-300"
                      }`}
                      data-testid="evidence-mode-just-play"
                    >
                      <div className="flex flex-col items-center gap-1.5">
                        <Play className={`w-5 h-5 ${evidenceMode === "just_play" ? "text-cyan-600 dark:text-cyan-400" : "text-slate-400"}`} />
                        <span className="text-sm font-medium">Just play</span>
                        <span className="text-[10px] text-inherit opacity-75">We’ll still learn from it later</span>
                      </div>
                    </Button>
                  </div>
                </motion.div>
              )}

              {/* Coach memory: reassuring context, not a scorecard. */}
              {!practiceMode && pastGamesHistory?.sessions?.length > 0 && (
                <motion.div
                  variants={staggerItem}
                  className="p-5 rounded-2xl border border-white/10 bg-gradient-to-b from-[#1b2530]/70 to-[#141c24]/70"
                >
                  <div className="flex items-center gap-2 mb-3">
                    <History className="w-4 h-4 text-cyan-400" />
                    <span className="font-medium text-sm text-slate-200">I remember your games</span>
                  </div>
                  <p className="text-sm leading-relaxed text-slate-300/90">
                    {playerIdentityData?.identity_label
                      ? `You tend to play like ${playerIdentityData.identity_label.toLowerCase()}. I’ll keep that in mind without taking the game away from you.`
                      : "I’ll connect what happens today with the patterns I’ve already seen—without interrupting every move."}
                  </p>
                </motion.div>
              )}

              {/* Opening Suggestions */}
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
                  <label className="text-sm font-medium mb-3 block text-slate-200">
                    How should I help with this opening?
                  </label>
                  <div className="flex gap-3">
                    <Button
                      variant={guidedMode ? "default" : "outline"}
                      onClick={() => setGuidedMode(true)}
                      className={`flex-1 h-auto py-3.5 px-4 rounded-xl border transition-all text-center ${
                        guidedMode
                          ? "border-cyan-500/60 bg-gradient-to-b from-cyan-950/40 to-slate-900/60 text-white shadow-[0_0_20px_rgba(56,189,248,0.25)] ring-1 ring-cyan-400/50 hover:bg-cyan-950/60"
                          : "border-white/10 bg-white/5 hover:border-white/20 hover:bg-white/10 text-slate-300"
                      }`}
                    >
                      <div className="flex flex-col items-center gap-1">
                        <Navigation className={`w-5 h-5 ${guidedMode ? "text-cyan-400" : "text-slate-400"}`} />
                        <span className="text-sm font-medium">Show me the ideas</span>
                        <span className="text-[10px] text-inherit opacity-75">Prompts when the position changes</span>
                      </div>
                    </Button>
                    <Button
                      variant={!guidedMode ? "default" : "outline"}
                      onClick={() => setGuidedMode(false)}
                      className={`flex-1 h-auto py-3.5 px-4 rounded-xl border transition-all text-center ${
                        !guidedMode
                          ? "border-cyan-500/60 bg-gradient-to-b from-cyan-950/40 to-slate-900/60 text-white shadow-[0_0_20px_rgba(56,189,248,0.25)] ring-1 ring-cyan-400/50 hover:bg-cyan-950/60"
                          : "border-white/10 bg-white/5 hover:border-white/20 hover:bg-white/10 text-slate-300"
                      }`}
                    >
                      <div className="flex flex-col items-center gap-1">
                        <GraduationCap className={`w-5 h-5 ${!guidedMode ? "text-cyan-400" : "text-slate-400"}`} />
                        <span className="text-sm font-medium">Let me remember</span>
                        <span className="text-[10px] text-inherit opacity-75">Step in only when I ask</span>
                      </div>
                    </Button>
                  </div>
                </motion.div>
              )}

              {/* Start Button */}
              <motion.div variants={staggerItem}>
              <Button
                onClick={startGame}
                disabled={loading}
                className="w-full h-13 py-3.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-mono text-sm font-bold uppercase tracking-wider shadow-[0_0_25px_rgba(56,189,248,0.45)] flex items-center justify-center gap-2.5 transition-all disabled:opacity-60 disabled:cursor-not-allowed"
                data-testid="start-game-btn"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                    Starting...
                  </>
                ) : practiceMode ? (
                  <>
                    <Target className="w-5 h-5 mr-2" />
                    Replay this position
                  </>
                ) : (
                  <>
                    <Play className="w-5 h-5 mr-2" />
                    Sit with me at the board
                  </>
                )}
              </Button>
              </motion.div>

              {/* Info */}
              <motion.div
                variants={staggerItem}
                className="p-4 rounded-xl bg-white/5 border border-white/10 text-sm text-slate-300/80 backdrop-blur-sm"
              >
                <Brain className="w-4 h-4 inline mr-2 text-cyan-400" />
                I’ll ask only the questions that matter for this game. You still make every decision.
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
