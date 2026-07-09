/**
 * DifficultySelector - Filter puzzles by difficulty tier
 *
 * Shows three tabs (Easy/Medium/Hard) with solve rate for each tier.
 * Allows user to select difficulty or auto-recommends based on rating.
 */

import { useState, useEffect } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { TrendingUp, Brain, Zap, AlertCircle } from "lucide-react";

const DIFFICULTY_INFO = {
  easy: {
    icon: Brain,
    color: "text-emerald-600",
    bgColor: "bg-emerald-50 dark:bg-emerald-950/30",
    description: "Start here if you're new or want to build confidence",
    targetSolveRate: "75-85%",
  },
  medium: {
    icon: Zap,
    color: "text-amber-600",
    bgColor: "bg-amber-50 dark:bg-amber-950/30",
    description: "Sweet spot for learning—challenging but achievable",
    targetSolveRate: "60-70%",
  },
  hard: {
    icon: AlertCircle,
    color: "text-red-600",
    bgColor: "bg-red-50 dark:bg-red-950/30",
    description: "Master-level tactics—for advanced players",
    targetSolveRate: "40-55%",
  },
};

export default function DifficultySelector({
  selectedDifficulty,
  recommendedDifficulty,
  userRating,
  solveRates = {},
  onSelectDifficulty,
  showRecommendation = true,
}) {
  const [nextSuggested, setNextSuggested] = useState(null);

  useEffect(() => {
    // Suggest next difficulty if current solve rate ≥ 70%
    if (selectedDifficulty === "easy" && solveRates.easy >= 0.7) {
      setNextSuggested("medium");
    } else if (selectedDifficulty === "medium" && solveRates.medium >= 0.7) {
      setNextSuggested("hard");
    } else {
      setNextSuggested(null);
    }
  }, [selectedDifficulty, solveRates]);

  const renderDifficultyTab = (difficulty) => {
    const info = DIFFICULTY_INFO[difficulty];
    const Icon = info.icon;
    const solveRate = solveRates[difficulty] !== undefined
      ? (solveRates[difficulty] * 100).toFixed(0)
      : null;
    const isRecommended = difficulty === recommendedDifficulty;

    return (
      <div key={difficulty} className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon className={`w-5 h-5 ${info.color}`} />
            <span className="font-semibold capitalize">{difficulty}</span>
            {isRecommended && showRecommendation && (
              <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded-full">
                📊 Recommended for your rating
              </span>
            )}
          </div>
        </div>

        {solveRate !== null && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Solve rate</span>
              <span className="font-semibold">{solveRate}%</span>
            </div>
            <Progress value={Math.min(solveRate, 100)} className="h-2" />
            <p className="text-xs text-muted-foreground">
              Target: {info.targetSolveRate}
            </p>
          </div>
        )}

        <p className="text-sm text-muted-foreground">{info.description}</p>

        {nextSuggested === difficulty && (
          <Button
            size="sm"
            variant="outline"
            className="w-full"
            onClick={() => onSelectDifficulty(nextSuggested)}
          >
            <TrendingUp className="w-4 h-4 mr-2" />
            Ready for {nextSuggested}? Try it!
          </Button>
        )}
      </div>
    );
  };

  return (
    <Card className="mb-6">
      <CardContent className="pt-6">
        <div className="mb-6">
          <h3 className="font-semibold mb-2">Choose Your Difficulty</h3>
          {userRating && (
            <p className="text-sm text-muted-foreground">
              Your rating: <span className="font-semibold">{userRating}</span>
            </p>
          )}
        </div>

        <Tabs value={selectedDifficulty} onValueChange={onSelectDifficulty}>
          <TabsList className="grid w-full grid-cols-3 mb-6">
            <TabsTrigger value="easy">Easy</TabsTrigger>
            <TabsTrigger value="medium">Medium</TabsTrigger>
            <TabsTrigger value="hard">Hard</TabsTrigger>
          </TabsList>

          <TabsContent value="easy">
            {renderDifficultyTab("easy")}
          </TabsContent>

          <TabsContent value="medium">
            {renderDifficultyTab("medium")}
          </TabsContent>

          <TabsContent value="hard">
            {renderDifficultyTab("hard")}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
