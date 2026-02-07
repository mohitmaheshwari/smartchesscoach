import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { 
  Loader2, 
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Minus,
  Target,
  Zap,
  Clock,
  CheckCircle2,
  RefreshCw
} from "lucide-react";

// Simple trend indicator
const TrendBadge = ({ trend }) => {
  if (trend === "improving") {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-green-500 bg-green-500/10 px-2 py-0.5 rounded">
        <TrendingUp className="w-3 h-3" /> Improving
      </span>
    );
  }
  if (trend === "worsening") {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-red-500 bg-red-500/10 px-2 py-0.5 rounded">
        <TrendingDown className="w-3 h-3" /> Needs work
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
      <Minus className="w-3 h-3" /> Stable
    </span>
  );
};

const Progress = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    fetchProgress();
  }, []);

  const fetchProgress = async () => {
    try {
      const res = await fetch(`${API}/progress`, { credentials: "include" });
      if (res.ok) setData(await res.json());
    } catch (e) {
      console.error("Failed to fetch progress:", e);
    } finally {
      setLoading(false);
    }
  };

  const syncNow = async () => {
    setSyncing(true);
    try {
      await fetch(`${API}/journey/sync-now`, {
        method: "POST",
        credentials: "include"
      });
      setTimeout(fetchProgress, 3000);
    } catch (e) {
      console.error(e);
    } finally {
      setSyncing(false);
    }
  };

  const [retrying, setRetrying] = useState(false);
  
  const retryFailedAnalyses = async () => {
    setRetrying(true);
    try {
      // Retry each failed game
      const failedIds = data?.failed_analyses || [];
      for (const gameId of failedIds) {
        await fetch(`${API}/analyze-game`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ game_id: gameId, force: true })
        });
      }
      // Refresh data after retrying
      setTimeout(fetchProgress, 2000);
    } catch (e) {
      console.error("Failed to retry analyses:", e);
    } finally {
      setRetrying(false);
    }
  };

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      </Layout>
    );
  }

  const rating = data?.rating || {};
  const accuracy = data?.accuracy || {};
  const habits = data?.habits || [];
  const resolvedHabits = data?.resolved_habits || [];

  return (
    <Layout user={user}>
      <div className="max-w-3xl mx-auto space-y-8" data-testid="progress-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate('/coach')}
              data-testid="back-to-coach"
            >
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div>
              <h1 className="font-heading font-bold text-2xl">Progress</h1>
              <p className="text-sm text-muted-foreground">Your metrics and trends</p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={syncNow}
            disabled={syncing}
          >
            {syncing ? (
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
            ) : (
              <RefreshCw className="w-4 h-4 mr-2" />
            )}
            Sync Games
          </Button>
        </div>

        {/* Failed Analyses Warning */}
        {data?.failed_analysis_count > 0 && (
          <Card className="border-amber-500/30 bg-amber-500/5">
            <CardContent className="pt-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-amber-500/20 flex items-center justify-center">
                    <Zap className="w-5 h-5 text-amber-500" />
                  </div>
                  <div>
                    <p className="font-medium text-sm">
                      {data.failed_analysis_count} game{data.failed_analysis_count > 1 ? 's' : ''} need re-analysis
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Engine analysis failed. Stats may be incomplete.
                    </p>
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={retryFailedAnalyses}
                  disabled={retrying}
                  className="border-amber-500/30 hover:bg-amber-500/10"
                >
                  {retrying ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <RefreshCw className="w-4 h-4 mr-2" />
                  )}
                  Retry Analysis
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Rating Section */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-amber-500" />
              Rating
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <div className="text-3xl font-bold">{rating.current || "—"}</div>
                <div className="text-xs text-muted-foreground">Current</div>
              </div>
              <div>
                <div className={`text-3xl font-bold ${
                  rating.change > 0 ? "text-green-500" : 
                  rating.change < 0 ? "text-red-500" : ""
                }`}>
                  {rating.change > 0 ? "+" : ""}{rating.change || 0}
                </div>
                <div className="text-xs text-muted-foreground">This week</div>
              </div>
              <div>
                <div className="text-3xl font-bold text-muted-foreground">{rating.peak || "—"}</div>
                <div className="text-xs text-muted-foreground">Peak (90d)</div>
              </div>
            </div>
            
            {/* Simple rating context */}
            {rating.change !== 0 && rating.habit_correlation && (
              <p className="text-sm text-muted-foreground mt-4 pt-4 border-t border-border">
                {rating.change > 0 
                  ? `Rating increased by ${rating.change} points. ${rating.habit_correlation}`
                  : "Rating fluctuates. Focus on discipline and long-term habit correction."}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Accuracy & Blunders */}
        <div className="grid md:grid-cols-2 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <Target className="w-4 h-4 text-blue-500" />
                Accuracy
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-end justify-between">
                <div>
                  <div className="text-3xl font-bold">{accuracy.current || "—"}%</div>
                  <div className="text-xs text-muted-foreground">Last 10 games</div>
                </div>
                <TrendBadge trend={accuracy.trend} />
              </div>
              {accuracy.previous && (
                <div className="text-sm text-muted-foreground mt-3">
                  Previous: {accuracy.previous}%
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <Zap className="w-4 h-4 text-red-500" />
                Blunders
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-end justify-between">
                <div>
                  <div className="text-3xl font-bold">{data?.blunders?.avg_per_game ?? "—"}</div>
                  <div className="text-xs text-muted-foreground">Avg per game</div>
                </div>
                <TrendBadge trend={data?.blunders?.trend} />
              </div>
              {data?.blunders?.total !== undefined && (
                <div className="text-sm text-muted-foreground mt-3">
                  Total (last 10): {data.blunders.total}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Active Habits */}
        {habits.length > 0 && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <Clock className="w-4 h-4 text-amber-500" />
                Habit Tracking
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {habits.map((habit, idx) => (
                  <div 
                    key={idx}
                    className={`flex items-center justify-between p-3 rounded-lg ${
                      habit.is_active ? "bg-amber-500/10 border border-amber-500/20" : "bg-muted/50"
                    }`}
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{habit.name}</span>
                        {habit.is_active && (
                          <span className="text-[10px] bg-amber-500 text-black px-1.5 py-0.5 rounded font-semibold">
                            ACTIVE
                          </span>
                        )}
                        {habit.reflection_stats?.status === "improving" && (
                          <span className="text-[10px] bg-emerald-500 text-black px-1.5 py-0.5 rounded font-semibold">
                            IMPROVING
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground mt-0.5">
                        {habit.occurrences_recent} occurrences recently
                        {habit.reflection_stats?.total > 0 && (
                          <span className="ml-2">
                            • Reflections: {habit.reflection_stats.correct}/{habit.reflection_stats.total}
                          </span>
                        )}
                      </div>
                    </div>
                    <TrendBadge trend={habit.trend} />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Resolved Habits */}
        {resolvedHabits.length > 0 && (
          <Card className="border-green-500/20">
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2 text-green-500">
                <CheckCircle2 className="w-4 h-4" />
                Resolved
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {resolvedHabits.map((habit, idx) => (
                  <div key={idx} className="text-sm text-muted-foreground">
                    ✓ {habit.message || habit.name}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* No Data State */}
        {!rating.current && habits.length === 0 && (
          <Card>
            <CardContent className="py-12 text-center">
              <p className="text-muted-foreground">
                Play and analyze some games to see your progress metrics.
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </Layout>
  );
};

export default Progress;
