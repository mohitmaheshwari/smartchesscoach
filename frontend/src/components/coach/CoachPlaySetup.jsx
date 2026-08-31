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
      className="space-y-4 cg-panel !p-5"
      data-testid="opening-suggestions"
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="cg-eyebrow !mb-1">Choose today’s first conversation</p>
          <p className="font-serif text-xl text-foreground">Which opening shall we explore?</p>
        </div>
        {selectedOpening && (
          <button
            onClick={() => onSelectOpening(null)}
            className="text-[10px] text-muted-foreground hover:text-foreground"
          >
            Clear
          </button>
        )}
      </div>

      <div className="space-y-1">
        {colorOpenings.slice(0, 5).map((o, i) => {
          const isSelected = selectedOpening === o.name;
          const isBest = o.name === best.name && best.games >= 3;
          return (
            <button
              key={i}
              onClick={() => onSelectOpening(isSelected ? null : o.name)}
              className={`w-full flex items-center justify-between text-sm p-3 rounded-xl border transition-all ${
                isSelected
                  ? "border-primary bg-primary/10 ring-1 ring-primary/30"
                  : "border-border hover:border-primary/30 hover:bg-muted/50"
              }`}
            >
              <div className="flex items-center gap-1.5">
                {isBest && <span className="text-amber-500 text-xs" aria-label="Coach's pick">★</span>}
                <span className={`font-medium truncate max-w-[160px] ${isSelected ? "text-primary" : "text-foreground"}`}>
                  {o.name}
                </span>
              </div>
              <span className="text-xs text-muted-foreground">{statusCopy[o.status] || "Explore this"}</span>
            </button>
          );
        })}
      </div>

      {best.games >= 3 && !selectedOpening && (
        <p className="text-xs text-muted-foreground">
          I’d begin with <span className="font-medium text-foreground">{best.name}</span>. It connects naturally to games you already play.
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
  pastGamesHistory,
  playerIdentityData,
  startGame,
  showPreGameStreakPopup,
  setShowPreGameStreakPopup,
  actuallyStartGame,
}) => {
  const navigate = useNavigate();

  return (
    <Layout user={user}>
      <div className="cg-page max-w-3xl" data-testid="coach-play-setup">
        <div className="mb-6">
          <CurriculumStateStrip user={user} surface="play_with_coach" />
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate("/")}
          className="mb-6 rounded-full"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Home
        </Button>

        {/* Setup card scales in (0.95 → 1); the sections inside stagger
            via the shared container — fade + scale per the locked spec. */}
        <div className="cg-hero mb-8">
          <p className="cg-eyebrow">At the board with your coach</p>
          <h1 className="cg-title">
            {practiceMode ? "Let’s replay the moment." : "Let’s play one thoughtful game."}
          </h1>
          <p className="cg-lede">
            {practiceMode
              ? "You know what happened before. This time, slow the position down and find a better story."
              : "Choose how you want me beside you. I’ll watch for the habits we’ve been working on."}
          </p>
        </div>

        <motion.div variants={scaleIn} initial="initial" animate="animate">
        <Card className="cg-panel !p-0 overflow-hidden">
          <CardContent className="space-y-6">
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
                className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-200"
                data-testid="practice-mode-indicator"
              >
                <div className="flex items-center gap-2 mb-2">
                  <Target className="w-4 h-4 text-emerald-700" />
                  <span className="font-medium text-emerald-700">A position from your game</span>
                </div>
                <p className="text-sm text-muted-foreground">
                  Start where the game turned. I’ll stay with you while you try a different plan.
                </p>
              </motion.div>
            )}

            {/* Color Selection */}
            <motion.div variants={staggerItem}>
              <label className="text-sm font-medium mb-3 block">
                Which side would you like?
              </label>
              <div className="flex gap-3">
                <Button
                  variant={selectedColor === "white" ? "default" : "outline"}
                  onClick={() => setSelectedColor("white")}
                  className="flex-1"
                  data-testid="select-white"
                  disabled={practiceMode}
                >
                  <div className="w-6 h-6 rounded-full bg-white border mr-2" />
                  White
                </Button>
                <Button
                  variant={selectedColor === "black" ? "default" : "outline"}
                  onClick={() => setSelectedColor("black")}
                  className="flex-1"
                  data-testid="select-black"
                  disabled={practiceMode}
                >
                  <div className="w-6 h-6 rounded-full bg-gray-900 border mr-2" />
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
                <label className="text-sm font-medium mb-3 block">
                  How close should I stay?
                </label>
                <div className="flex gap-3">
                  <Button
                    variant={gameMode === "coach" ? "default" : "outline"}
                    onClick={() => setGameMode("coach")}
                    className="flex-1 h-auto py-3"
                  >
                    <div className="flex flex-col items-center gap-1">
                      <Brain className="w-5 h-5" />
                      <span className="text-sm font-medium">Stay with me</span>
                      <span className="text-[10px] text-inherit opacity-70">Gentle questions while you play</span>
                    </div>
                  </Button>
                  <Button
                    variant={gameMode === "play" ? "default" : "outline"}
                    onClick={() => setGameMode("play")}
                    className="flex-1 h-auto py-3"
                  >
                    <div className="flex flex-col items-center gap-1">
                      <Play className="w-5 h-5" />
                      <span className="text-sm font-medium">Let me think</span>
                      <span className="text-[10px] text-inherit opacity-70">We’ll talk after the game</span>
                    </div>
                  </Button>
                </div>
              </motion.div>
            )}

            {/* Coach memory: reassuring context, not a scorecard. */}
            {!practiceMode && pastGamesHistory?.sessions?.length > 0 && (
              <motion.div
                variants={staggerItem}
                className="p-5 rounded-2xl border border-emerald-900/10 bg-emerald-50/70 dark:bg-emerald-950/20"
              >
                <div className="flex items-center gap-2 mb-3">
                  <History className="w-4 h-4 text-primary" />
                  <span className="font-medium text-sm">I remember your games</span>
                </div>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {playerIdentityData?.identity_label
                    ? `You tend to play like ${playerIdentityData.identity_label.toLowerCase()}. I’ll keep that in mind without taking the game away from you.`
                    : "I’ll connect what happens today with the patterns I’ve already seen—without interrupting every move."}
                </p>
              </motion.div>
            )}

            {/* Opening Suggestions — animates its own root (it mounts
                later, after its fetch resolves, so it can't join the
                initial stagger; an outer wrapper would leave an empty
                spaced div while it returns null). */}
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
                <label className="text-sm font-medium mb-3 block">
                  How should I help with this opening?
                </label>
                <div className="flex gap-3">
                  <Button
                    variant={guidedMode ? "default" : "outline"}
                    onClick={() => setGuidedMode(true)}
                    className="flex-1 h-auto py-3"
                  >
                    <div className="flex flex-col items-center gap-1">
                      <Navigation className="w-5 h-5" />
                      <span className="text-sm font-medium">Show me the ideas</span>
                      <span className="text-[10px] text-inherit opacity-70">Prompts when the position changes</span>
                    </div>
                  </Button>
                  <Button
                    variant={!guidedMode ? "default" : "outline"}
                    onClick={() => setGuidedMode(false)}
                    className="flex-1 h-auto py-3"
                  >
                    <div className="flex flex-col items-center gap-1">
                      <GraduationCap className="w-5 h-5" />
                      <span className="text-sm font-medium">Let me remember</span>
                      <span className="text-[10px] text-inherit opacity-70">Step in only when I ask</span>
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
              className="cg-primary-action w-full h-12 text-base"
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
              className="p-4 rounded-xl bg-muted/40 text-sm text-muted-foreground"
            >
              <Brain className="w-4 h-4 inline mr-2" />
              I’ll ask only the questions that matter for this game. You still make every decision.
            </motion.div>
            </motion.div>
          </CardContent>
        </Card>
        </motion.div>
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
