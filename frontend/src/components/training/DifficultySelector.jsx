/**
 * DifficultySelector
 *
 * The engine still uses rating and solve history to recommend a level, but
 * the player should not have to read a report to choose how practice feels.
 */

import { Brain, Zap, Sparkles } from "lucide-react";

const DIFFICULTY_INFO = {
  easy: {
    icon: Brain,
    label: "Gentle start",
    description: "Give me clear positions while I learn what to look for.",
  },
  medium: {
    icon: Zap,
    label: "Learning pace",
    description: "Make me think, but keep the lesson within reach.",
  },
  hard: {
    icon: Sparkles,
    label: "Stretch me",
    description: "Give me positions where the idea is harder to recognise.",
  },
};

export default function DifficultySelector({
  selectedDifficulty,
  recommendedDifficulty,
  onSelectDifficulty,
  showRecommendation = true,
}) {
  return (
    <section className="cg-panel mb-7 p-5" aria-label="Choose how practice should feel">
      <p className="cg-eyebrow mb-2">How should today’s practice feel?</p>
      <p className="mb-5 max-w-xl text-sm leading-relaxed text-muted-foreground">
        Your coach has chosen a starting point. You can change it without changing the lesson.
      </p>

      <div className="grid gap-3 md:grid-cols-3">
        {Object.entries(DIFFICULTY_INFO).map(([difficulty, info]) => {
          const Icon = info.icon;
          const selected = selectedDifficulty === difficulty;
          const recommended = recommendedDifficulty === difficulty;
          return (
            <button
              key={difficulty}
              type="button"
              onClick={() => onSelectDifficulty(difficulty)}
              aria-pressed={selected}
              className={`rounded-2xl border p-4 text-left transition-all hover:-translate-y-0.5 ${
                selected
                  ? "border-[#B7F34A] bg-[#B7F34A]/15 shadow-[0_14px_34px_rgba(183,243,74,0.12)]"
                  : "border-border bg-card/60 hover:border-emerald-700/25"
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <Icon className="h-4 w-4 text-emerald-700 dark:text-emerald-300" aria-hidden="true" />
                {recommended && showRecommendation && (
                  <span className="text-[9px] font-bold uppercase tracking-[0.14em] text-emerald-700 dark:text-emerald-300">
                    Your coach’s pick
                  </span>
                )}
              </div>
              <p className="mt-3 text-sm font-semibold text-foreground">{info.label}</p>
              <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{info.description}</p>
            </button>
          );
        })}
      </div>
    </section>
  );
}
