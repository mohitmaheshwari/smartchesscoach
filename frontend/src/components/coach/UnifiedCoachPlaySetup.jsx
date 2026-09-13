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
    className={`relative w-full rounded-2xl border p-5 text-left transition ${
      active
        ? "border-emerald-700 bg-emerald-50/80 shadow-sm dark:bg-emerald-950/20"
        : "border-border bg-card hover:border-emerald-700/40"
    } ${blocked ? "opacity-75" : ""}`}
    data-testid={testId}
  >
    <div className="flex items-start gap-4">
      <span className={`mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${
        active ? "bg-emerald-700 text-white" : "bg-muted text-foreground"
      }`}>
        {blocked ? <Lock className="h-4 w-4" /> : <Icon className="h-5 w-5" />}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2 font-serif text-xl text-foreground">
          {label}
          {active && <Check className="h-4 w-4 text-emerald-700" />}
        </span>
        <span className="mt-1 block text-sm leading-relaxed text-muted-foreground">
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
      <main className="cg-page max-w-3xl" data-testid="unified-coach-play-setup">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate("/")}
          className="mb-6 rounded-full"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Home
        </Button>

        <section className="cg-hero mb-7">
          <p className="cg-eyebrow">Today with your coach</p>
          <h1 className="cg-title">
            {practiceMode ? "Let’s replay this moment." : "Let’s play one thoughtful game."}
          </h1>
          <p className="cg-lede">
            {practiceMode && practicePosition
              ? "Try a different plan from the position where your game changed."
              : "You play the game. I’ll decide when one quiet interruption can genuinely help."}
          </p>
        </section>

        <section className="mb-5 rounded-2xl border border-emerald-900/10 bg-emerald-50/70 p-5 dark:bg-emerald-950/20">
          <div className="flex items-start gap-3">
            <Target className="mt-0.5 h-5 w-5 shrink-0 text-emerald-700" />
            <div>
              <p className="cg-eyebrow !mb-1">Today’s work</p>
              <h2 className="font-serif text-xl text-foreground">{focusLabel}</h2>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                {focusInstruction}
              </p>
              {!practiceMode && (
                <button
                  type="button"
                  className="mt-3 text-sm font-medium text-emerald-800 underline-offset-4 hover:underline dark:text-emerald-300"
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
            <div className="mt-4 border-t border-emerald-900/10 pt-4" data-testid="unified-work-choices">
              {choicesLoading ? (
                <p className="text-sm text-muted-foreground">Finding useful choices…</p>
              ) : availableOpenings.length ? (
                <div className="grid gap-2">
                  {availableOpenings.map((opening) => (
                    <button
                      type="button"
                      key={opening.name}
                      className={`rounded-xl border px-4 py-3 text-left text-sm transition ${
                        selectedOpening === opening.name
                          ? "border-emerald-700 bg-white/80 dark:bg-emerald-950/40"
                          : "border-emerald-900/10 hover:border-emerald-700/40"
                      }`}
                      onClick={() => {
                        setSelectedOpening(
                          selectedOpening === opening.name ? null : opening.name
                        );
                        setShowWorkChoices(false);
                      }}
                    >
                      <span className="block font-medium text-foreground">{opening.name}</span>
                      <span className="mt-0.5 block text-xs text-muted-foreground">
                        From your recent {selectedColor} games
                      </span>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-sm leading-relaxed text-muted-foreground">
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

        <section className="mt-5 rounded-2xl border border-border bg-card">
          <button
            type="button"
            className="flex w-full items-center justify-between px-5 py-4 text-left"
            onClick={() => setShowSettings((open) => !open)}
            aria-expanded={showSettings}
            data-testid="unified-settings-toggle"
          >
            <span>
              <span className="block text-sm font-medium text-foreground">
                {selectedColor === "white" ? "White" : "Black"} · {timeControl}
              </span>
              <span className="block text-xs text-muted-foreground">Recommended game settings</span>
            </span>
            <Settings2 className="h-4 w-4 text-muted-foreground" />
          </button>

          {showSettings && (
            <div className="border-t border-border px-5 py-4" data-testid="unified-settings">
              <p className="mb-3 text-sm font-medium text-foreground">Choose your side</p>
              <div className="flex gap-3">
                <Button
                  type="button"
                  variant={selectedColor === "white" ? "default" : "outline"}
                  onClick={() => setSelectedColor("white")}
                  disabled={practiceMode}
                  className="flex-1"
                >
                  White
                </Button>
                <Button
                  type="button"
                  variant={selectedColor === "black" ? "default" : "outline"}
                  onClick={() => setSelectedColor("black")}
                  disabled={practiceMode}
                  className="flex-1"
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
          className="cg-primary-action mt-6 h-12 w-full text-base"
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
      </main>
    </Layout>
  );
};


export default UnifiedCoachPlaySetup;
