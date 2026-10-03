import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Brain, Check, Lock, Play, Settings2, Target } from "lucide-react";

import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { API } from "@/App";


const ModeChoice = ({
  active,
  blocked,
  description,
  icon: Icon,
  label,
  onClick,
  testId,
}) => (
  <button
    type="button"
    role="radio"
    aria-checked={active}
    aria-disabled={blocked}
    onClick={onClick}
    className={`relative w-full rounded-2xl border p-5 text-left transition-all ${
      active
        ? "border-cyan-500/60 bg-cyan-50/50 dark:bg-gradient-to-b dark:from-[#1e2a36] dark:to-[#151f28] shadow-sm dark:shadow-[0_0_25px_rgba(56,189,248,0.2)] ring-1 ring-cyan-400/50"
        : "border-slate-200/90 dark:border-white/10 bg-white dark:bg-[#16202a]/60 hover:border-cyan-400 dark:hover:border-cyan-500/30 hover:bg-slate-50 dark:hover:bg-[#1a2632]/80"
    } ${blocked ? "opacity-75" : ""}`}
    data-testid={testId}
  >
    <div className="flex items-start gap-4">
      <span className={`mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-all ${
        active
          ? "bg-gradient-to-br from-cyan-500 to-blue-600 text-slate-950 font-bold shadow-[0_0_15px_rgba(56,189,248,0.4)]"
          : "bg-slate-100 text-slate-700 dark:bg-white/10 dark:text-slate-200"
      }`}>
        {blocked ? <Lock className="h-4 w-4" /> : <Icon className="h-5 w-5" />}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2 font-serif text-xl text-slate-900 dark:text-white">
          {label}
          {active && <Check className="h-4 w-4 text-cyan-600 dark:text-cyan-400" />}
        </span>
        <span className="mt-1 block text-sm leading-relaxed text-slate-600 dark:text-slate-300/80">
          {description}
        </span>
      </span>
    </div>
  </button>
);


const UnifiedCoachPlaySetup = ({
  user,
  loading,
  experienceLoading,
  experienceConfig,
  upgradeInfo,
  practiceMode,
  practicePosition,
  selectedColor,
  setSelectedColor,
  selectedOpening,
  setSelectedOpening,
  gameMode,
  setGameMode,
  timeControl,
  startGame,
  onModeSelected,
}) => {
  const navigate = useNavigate();
  const [showSettings, setShowSettings] = useState(false);
  const [showWorkChoices, setShowWorkChoices] = useState(false);
  const [openingChoices, setOpeningChoices] = useState(null);
  const [choicesLoading, setChoicesLoading] = useState(false);

  const context = experienceConfig?.coaching_context;
  const primaryFocus = context?.primary_focus;
  const access = experienceConfig?.access?.coach || {};
  const coachAllowed = access.allowed !== false && !upgradeInfo;
  const focusLabel = selectedOpening || primaryFocus?.label || "One useful idea from this game";
  const focusInstruction = selectedOpening
    ? `I’ll connect ${selectedOpening} to the position without choosing your moves for you.`
    : primaryFocus?.instruction_text
      || context?.evidence?.message
      || "I don’t have enough verified games to choose a personal focus yet. I’ll speak only when the board gives us a clear lesson.";

  const chooseCoach = () => {
    setGameMode("coach");
    onModeSelected?.("coach");
  };

  const begin = () => {
    if (gameMode === "coach" && !coachAllowed) {
      navigate(upgradeInfo?.upgrade_url || access.upgrade_url || "/pricing");
      return;
    }
    startGame();
  };

  const toggleWorkChoices = async () => {
    const nextOpen = !showWorkChoices;
    setShowWorkChoices(nextOpen);
    if (!nextOpen || openingChoices || choicesLoading) return;
    setChoicesLoading(true);
    try {
      const response = await fetch(`${API}/coach/play/opening-suggestions`, {
        credentials: "include",
      });
      setOpeningChoices(response.ok ? await response.json() : {});
    } catch (_error) {
      setOpeningChoices({});
    } finally {
      setChoicesLoading(false);
    }
  };

  const availableOpenings = (
    selectedColor === "white" ? openingChoices?.white : openingChoices?.black
  )?.slice(0, 3) || [];

  return (
    <Layout user={user}>
      <main className="min-h-full py-6 px-4 sm:px-6 relative" data-testid="unified-coach-play-setup">
        {/* Soft Ambient Studio Lighting */}
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-[140px] pointer-events-none" />
        <div className="absolute top-1/2 left-10 w-80 h-80 bg-blue-600/5 dark:bg-blue-600/10 rounded-full blur-[140px] pointer-events-none" />

        <div className="max-w-3xl mx-auto relative z-10">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/")}
            className="mb-6 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 dark:bg-white/5 dark:hover:bg-white/10 dark:text-slate-300 dark:border-white/10"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Home
          </Button>

          <section className="bg-white/95 dark:bg-gradient-to-b dark:from-[#25323d]/85 dark:to-[#1a232b]/85 border border-slate-200/90 dark:border-white/15 rounded-3xl p-7 sm:p-9 shadow-[0_20px_50px_rgba(0,0,0,0.06)] dark:shadow-[0_25px_60px_rgba(0,0,0,0.45)] backdrop-blur-xl relative overflow-hidden mb-7">
            <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-cyan-800 dark:text-cyan-300 font-bold bg-cyan-50 dark:bg-cyan-950/60 border border-cyan-200 dark:border-cyan-500/30 px-3 py-1 rounded-full inline-block mb-3 shadow-sm">
              Today with your coach
            </span>
            <h1 className="font-serif text-3xl sm:text-4xl text-slate-900 dark:text-white font-normal tracking-tight">
              {practiceMode ? "Let’s replay this moment." : "Let’s play one thoughtful game."}
            </h1>
            <p className="text-slate-600 dark:text-slate-200/90 text-sm sm:text-base mt-3 max-w-[620px] leading-relaxed">
              {practiceMode && practicePosition
                ? "Try a different plan from the position where your game changed."
                : "You play the game. I’ll decide when one quiet interruption can genuinely help."}
            </p>
          </section>

          <section className="mb-5 rounded-2xl border border-slate-200/90 dark:border-white/15 bg-slate-50/90 dark:bg-gradient-to-b dark:from-[#1e2a36]/80 dark:to-[#162029]/80 p-5 shadow-sm backdrop-blur-md">
            <div className="flex items-start gap-3">
              <Target className="mt-0.5 h-5 w-5 shrink-0 text-cyan-600 dark:text-cyan-400" />
              <div>
                <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-cyan-800 dark:text-cyan-300 font-bold bg-cyan-50 dark:bg-cyan-950/60 border border-cyan-200 dark:border-cyan-500/30 px-2.5 py-0.5 rounded-full inline-block mb-1.5 shadow-sm">
                  Today’s work
                </span>
                <h2 className="font-serif text-xl text-slate-900 dark:text-white">{focusLabel}</h2>
                <p className="mt-1 text-sm leading-relaxed text-slate-600 dark:text-slate-300/90">
                  {focusInstruction}
                </p>
                {!practiceMode && (
                  <button
                    type="button"
                    className="mt-3 text-sm font-medium text-cyan-700 dark:text-cyan-400 underline-offset-4 hover:underline"
                    onClick={toggleWorkChoices}
                    aria-expanded={showWorkChoices}
                    data-testid="unified-work-choice-toggle"
                  >
                    {selectedOpening ? "Choose a different opening" : "Work on something else"}
                  </button>
                )}
              </div>
            </div>
            {showWorkChoices && (
              <div className="mt-4 border-t border-slate-200 dark:border-white/10 pt-4" data-testid="unified-work-choices">
                {choicesLoading ? (
                  <p className="text-sm text-slate-500 dark:text-slate-400">Finding useful choices…</p>
                ) : availableOpenings.length ? (
                  <div className="grid gap-2">
                    {availableOpenings.map((opening) => (
                      <button
                        type="button"
                        key={opening.name}
                        className={`rounded-xl border px-4 py-3 text-left text-sm transition-all ${
                          selectedOpening === opening.name
                            ? "border-cyan-500/60 bg-cyan-50 text-cyan-900 dark:bg-gradient-to-r dark:from-cyan-950/50 dark:to-slate-900/60 dark:text-cyan-300 shadow-[0_0_15px_rgba(56,189,248,0.2)] ring-1 ring-cyan-400/40"
                            : "border-slate-200 bg-white hover:bg-slate-50 text-slate-800 dark:border-white/10 dark:bg-white/5 dark:text-slate-200"
                        }`}
                        onClick={() => {
                          setSelectedOpening(
                            selectedOpening === opening.name ? null : opening.name
                          );
                          setShowWorkChoices(false);
                        }}
                      >
                        <span className="block font-medium text-slate-900 dark:text-white">{opening.name}</span>
                        <span className="mt-0.5 block text-xs text-slate-500 dark:text-slate-400">
                          From your recent {selectedColor} games
                        </span>
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm leading-relaxed text-slate-500 dark:text-slate-400">
                    I need a few games with this color before I can offer a useful opening choice.
                  </p>
                )}
              </div>
            )}
          </section>

          <section role="radiogroup" aria-label="Choose how to play" className="grid gap-3 md:grid-cols-2">
            <ModeChoice
              active={gameMode === "coach"}
              blocked={!coachAllowed}
              label="Play with Coach"
              description={
                coachAllowed
                  ? "I’ll step in only when the moment can teach you something useful."
                  : access.message || upgradeInfo?.message || "Today’s free coached game has been used."
              }
              icon={Brain}
              onClick={chooseCoach}
              testId="unified-mode-coach"
            />
            <ModeChoice
              active={gameMode === "play"}
              blocked={false}
              label="Play a Game"
              description="No help during the game. We’ll review it afterward."
              icon={Play}
              onClick={() => {
                setGameMode("play");
                onModeSelected?.("play");
              }}
              testId="unified-mode-play"
            />
          </section>

          <section className="mt-5 rounded-2xl border border-slate-200/90 dark:border-white/15 bg-white dark:bg-gradient-to-b dark:from-[#1a232c]/80 dark:to-[#141b22]/80 backdrop-blur-md shadow-sm">
            <button
              type="button"
              className="flex w-full items-center justify-between px-5 py-4 text-left"
              onClick={() => setShowSettings((open) => !open)}
              aria-expanded={showSettings}
              data-testid="unified-settings-toggle"
            >
              <span>
                <span className="block text-sm font-medium text-slate-900 dark:text-white">
                  {selectedColor === "white" ? "White" : "Black"} · {timeControl}
                </span>
                <span className="block text-xs text-slate-500 dark:text-slate-400">Recommended game settings</span>
              </span>
              <Settings2 className="h-4 w-4 text-slate-500 dark:text-slate-400" />
            </button>

            {showSettings && (
              <div className="border-t border-slate-200 dark:border-white/10 px-5 py-4" data-testid="unified-settings">
                <p className="mb-3 text-sm font-medium text-slate-900 dark:text-white">Choose your side</p>
                <div className="flex gap-3">
                  <Button
                    type="button"
                    variant={selectedColor === "white" ? "default" : "outline"}
                    onClick={() => setSelectedColor("white")}
                    disabled={practiceMode}
                    className={`flex-1 h-auto py-3 rounded-xl border text-sm font-medium transition-all ${
                      selectedColor === "white"
                        ? "border-cyan-500/60 bg-cyan-50 text-cyan-900 shadow-sm ring-1 ring-cyan-500/40 dark:bg-gradient-to-b dark:from-cyan-950/40 dark:to-slate-900/60 dark:text-white dark:shadow-[0_0_20px_rgba(56,189,248,0.25)]"
                        : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100 dark:border-white/10 dark:bg-white/5 dark:text-slate-300"
                    }`}
                  >
                    White
                  </Button>
                  <Button
                    type="button"
                    variant={selectedColor === "black" ? "default" : "outline"}
                    onClick={() => setSelectedColor("black")}
                    disabled={practiceMode}
                    className={`flex-1 h-auto py-3 rounded-xl border text-sm font-medium transition-all ${
                      selectedColor === "black"
                        ? "border-cyan-500/60 bg-cyan-50 text-cyan-900 shadow-sm ring-1 ring-cyan-500/40 dark:bg-gradient-to-b dark:from-cyan-950/40 dark:to-slate-900/60 dark:text-white dark:shadow-[0_0_20px_rgba(56,189,248,0.25)]"
                        : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100 dark:border-white/10 dark:bg-white/5 dark:text-slate-300"
                    }`}
                  >
                    Black
                  </Button>
                </div>
                <p className="mt-3 text-xs text-muted-foreground">
                  {practiceMode
                    ? "Your side comes from the original position."
                    : "15+10 gives you enough time to think without turning the game into a long session."}
                </p>
              </div>
            )}
          </section>

          <Button
            type="button"
            onClick={begin}
            disabled={loading || experienceLoading}
            className="w-full h-13 py-3.5 mt-6 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-mono text-sm font-bold uppercase tracking-wider shadow-[0_0_25px_rgba(56,189,248,0.45)] flex items-center justify-center transition-all disabled:opacity-60 disabled:cursor-not-allowed"
            data-testid="unified-start-game"
          >
            {loading || experienceLoading
              ? "Preparing your game…"
              : gameMode === "coach" && !coachAllowed
                ? "See coaching access"
                : practiceMode
                  ? "Replay this position"
                  : gameMode === "coach"
                    ? "Start with Coach"
                    : "Start the Game"}
          </Button>
        </div>
      </main>
    </Layout>
  );
};


export default UnifiedCoachPlaySetup;
