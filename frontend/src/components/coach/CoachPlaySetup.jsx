/**
 * CoachPlaySetup — Pre-game setup screen for Play with Coach
 *
 * Shows: color selector, practice mode indicator, past games memory,
 * opening suggestions, and start button.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import Layout from "@/components/Layout";
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

  const statusColors = {
    strong: "text-emerald-600 bg-emerald-500/10 border-emerald-500/20",
    learning: "text-amber-600 bg-amber-500/10 border-amber-500/20",
    weak: "text-red-500 bg-red-500/10 border-red-500/20",
    new: "text-blue-500 bg-blue-500/10 border-blue-500/20",
  };

  // Show openings for the selected color
  const colorOpenings = selectedColor === "white" ? data.white : data.black;
  const colorLabel = selectedColor === "white" ? "As White" : "As Black";

  if (!colorOpenings?.length) return null;

  // Find best opening
  const best = colorOpenings.reduce((a, b) =>
    (b.win_rate > a.win_rate && b.games >= 3) ? b : a, colorOpenings[0]
  );

  return (
    <div
      className="space-y-3 p-3 rounded-lg bg-muted/30 border border-border"
      data-testid="opening-suggestions"
    >
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-foreground">Pick an opening to practice</p>
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
              className={`w-full flex items-center justify-between text-xs p-2 rounded border transition-all ${
                isSelected
                  ? "border-primary bg-primary/10 ring-1 ring-primary/30"
                  : "border-border hover:border-primary/30 hover:bg-muted/50"
              }`}
            >
              <div className="flex items-center gap-1.5">
                {isBest && <span className="text-amber-500 text-[10px]">★</span>}
                <span className={`font-medium truncate max-w-[160px] ${isSelected ? "text-primary" : "text-foreground"}`}>
                  {o.name}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">{o.games}g</span>
                <span className={`font-mono ${o.win_rate >= 50 ? "text-emerald-600" : "text-muted-foreground"}`}>
                  {o.win_rate}%
                </span>
                <span className={`px-1.5 py-0.5 rounded-full text-[10px] border ${statusColors[o.status]}`}>
                  {o.status_label}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {best.games >= 3 && !selectedOpening && (
        <p className="text-[10px] text-muted-foreground">
          Coach recommends: <span className="font-medium text-foreground">{best.name}</span> ({best.win_rate}% win rate)
        </p>
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
      <div className="max-w-2xl mx-auto py-8 px-4" data-testid="coach-play-setup">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate("/")}
          className="mb-6"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Home
        </Button>

        <Card className="border-primary/20">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-full bg-primary/10">
                <Swords className="w-8 h-8 text-primary" />
              </div>
              <div>
                <CardTitle className="text-2xl">
                  {practiceMode ? "Practice Position" : "Play With Coach"}
                </CardTitle>
                <p className="text-muted-foreground">
                  {practiceMode
                    ? "Play from a position in your game and see how it could have gone differently"
                    : "Train against an intelligent opponent"}
                </p>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Practice Mode Indicator */}
            {practiceMode && practicePosition && (
              <div
                className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-200"
                data-testid="practice-mode-indicator"
              >
                <div className="flex items-center gap-2 mb-2">
                  <Target className="w-4 h-4 text-emerald-700" />
                  <span className="font-medium text-emerald-700">Practice Mode</span>
                </div>
                <p className="text-sm text-muted-foreground">
                  You'll start from the position where you made a mistake.
                  Try playing differently and see if you can win!
                </p>
              </div>
            )}

            {/* Color Selection */}
            <div>
              <label className="text-sm font-medium mb-3 block">
                Choose Your Color
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
            </div>

            {/* Past Games Memory */}
            {!practiceMode && pastGamesHistory?.sessions?.length > 0 && (
              <div className="p-4 rounded-lg border border-border bg-muted/30">
                <div className="flex items-center gap-2 mb-3">
                  <History className="w-4 h-4 text-primary" />
                  <span className="font-medium text-sm">Coach Remembers</span>
                </div>

                <div className="grid grid-cols-3 gap-2 text-center mb-3">
                  <div className="p-2 rounded bg-background/50">
                    <div className="text-lg font-bold text-green-500">
                      {pastGamesHistory.stats.wins}
                    </div>
                    <div className="text-xs text-muted-foreground">Wins</div>
                  </div>
                  <div className="p-2 rounded bg-background/50">
                    <div className="text-lg font-bold text-muted-foreground">
                      {pastGamesHistory.stats.draws}
                    </div>
                    <div className="text-xs text-muted-foreground">Draws</div>
                  </div>
                  <div className="p-2 rounded bg-background/50">
                    <div className="text-lg font-bold text-red-500">
                      {pastGamesHistory.stats.losses}
                    </div>
                    <div className="text-xs text-muted-foreground">Losses</div>
                  </div>
                </div>

                <div className="space-y-1">
                  {pastGamesHistory.sessions.slice(0, 3).map((s, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between text-xs p-2 rounded bg-background/50"
                    >
                      <div className="flex items-center gap-2">
                        <div
                          className={`w-2 h-2 rounded-full ${
                            s.result === "win"
                              ? "bg-green-500"
                              : s.result === "loss"
                              ? "bg-red-500"
                              : "bg-gray-400"
                          }`}
                        />
                        <span className="capitalize">{s.result || "In progress"}</span>
                      </div>
                      <span className="text-muted-foreground">
                        {s.created_at
                          ? new Date(s.created_at).toLocaleDateString()
                          : ""}
                      </span>
                    </div>
                  ))}
                </div>

                {playerIdentityData?.identity_label && (
                  <div className="mt-3 pt-3 border-t border-border/50 text-xs">
                    <span className="text-muted-foreground">Your style: </span>
                    <Badge variant="secondary" className="ml-1">
                      {playerIdentityData.identity_label}
                    </Badge>
                  </div>
                )}
              </div>
            )}

            {/* Opening Suggestions */}
            {!practiceMode && (
              <OpeningSuggestions
                selectedColor={selectedColor}
                selectedOpening={selectedOpening}
                onSelectOpening={setSelectedOpening}
              />
            )}

            {/* Start Button */}
            <Button
              onClick={startGame}
              disabled={loading}
              className="w-full h-12 text-lg"
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
                  Start Practice
                </>
              ) : (
                <>
                  <Play className="w-5 h-5 mr-2" />
                  Start Game
                </>
              )}
            </Button>

            {/* Info */}
            <div className="p-4 rounded-lg bg-muted/50 text-sm text-muted-foreground">
              <Brain className="w-4 h-4 inline mr-2" />
              The coach will adapt to your play and help you improve. Future
              updates will add real-time interventions when you're about to make
              mistakes.
            </div>
          </CardContent>
        </Card>
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
