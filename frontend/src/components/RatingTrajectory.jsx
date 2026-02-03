import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { API } from "@/App";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { 
  TrendingUp, 
  TrendingDown, 
  Target, 
  Zap, 
  Clock,
  Brain,
  ChevronRight,
  Loader2,
  Trophy,
  AlertTriangle,
  CheckCircle2
} from "lucide-react";

// Rating milestone colors
const getMilestoneColor = (rating) => {
  if (rating >= 2000) return "text-purple-400";
  if (rating >= 1800) return "text-blue-400";
  if (rating >= 1600) return "text-green-400";
  if (rating >= 1400) return "text-yellow-400";
  if (rating >= 1200) return "text-orange-400";
  return "text-zinc-400";
};

const getTrendIcon = (trend) => {
  if (trend === "rapid_improvement" || trend === "steady_improvement") {
    return <TrendingUp className="w-4 h-4 text-green-500" />;
  }
  if (trend === "slight_decline" || trend === "needs_attention") {
    return <TrendingDown className="w-4 h-4 text-red-500" />;
  }
  return <div className="w-4 h-4 rounded-full bg-zinc-500" />;
};

const getTrendLabel = (trend) => {
  const labels = {
    "rapid_improvement": "Rapid Improvement 🔥",
    "steady_improvement": "Steady Progress 📈",
    "stable": "Holding Steady",
    "slight_decline": "Slight Dip",
    "needs_attention": "Needs Focus",
    "insufficient_data": "Analyzing..."
  };
  return labels[trend] || trend;
};

export const RatingTrajectory = () => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchTrajectory();
  }, []);

  const fetchTrajectory = async () => {
    try {
      const res = await fetch(API + "/rating/trajectory", { credentials: "include" });
      if (!res.ok) throw new Error("Failed to fetch rating data");
      setData(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Card className="surface">
        <CardContent className="py-12 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card className="surface">
        <CardContent className="py-8 text-center text-muted-foreground">
          <p>Connect a chess account to see your rating trajectory</p>
        </CardContent>
      </Card>
    );
  }

  const { trajectory, platform_ratings, current_rating, improvement_velocity } = data;
  const nextMilestone = trajectory?.next_milestone;
  const projectedRating = trajectory?.projected_rating;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-4"
    >
      {/* Main Rating Card */}
      <Card className="surface overflow-hidden">
        <div className="bg-gradient-to-r from-amber-500/10 to-transparent p-6 border-b border-border">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">Current Rating</p>
              <div className="flex items-baseline gap-3">
                <span className={`text-4xl font-bold ${getMilestoneColor(current_rating)}`}>
                  {current_rating}
                </span>
                <span className="text-sm text-muted-foreground">
                  {data.rating_source?.replace(/_/g, ' ').replace('chess com', 'Chess.com')}
                </span>
              </div>
            </div>
            <div className="text-right">
              <div className="flex items-center gap-2 text-sm">
                {getTrendIcon(improvement_velocity?.trend)}
                <span className={improvement_velocity?.trend?.includes("improvement") ? "text-green-500" : "text-muted-foreground"}>
                  {getTrendLabel(improvement_velocity?.trend)}
                </span>
              </div>
              {improvement_velocity?.velocity !== 0 && (
                <p className="text-xs text-muted-foreground mt-1">
                  {improvement_velocity?.velocity > 0 ? "+" : ""}{improvement_velocity?.velocity} pts/month
                </p>
              )}
            </div>
          </div>
        </div>

        <CardContent className="py-6">
          {/* Projection Section */}
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="text-center p-3 rounded-lg bg-muted/30">
              <p className="text-xs text-muted-foreground mb-1">1 Month</p>
              <p className="text-xl font-semibold">{projectedRating?.["1_month"]}</p>
            </div>
            <div className="text-center p-3 rounded-lg bg-muted/50 border border-amber-500/30">
              <p className="text-xs text-muted-foreground mb-1">3 Months</p>
              <p className="text-2xl font-bold text-amber-500">{projectedRating?.["3_months"]}</p>
              <p className="text-xs text-muted-foreground">
                {projectedRating?.range_3m?.[0]}-{projectedRating?.range_3m?.[1]}
              </p>
            </div>
            <div className="text-center p-3 rounded-lg bg-muted/30">
              <p className="text-xs text-muted-foreground mb-1">6 Months</p>
              <p className="text-xl font-semibold">{projectedRating?.["6_months"]}</p>
            </div>
          </div>

          {/* Next Milestone */}
          {nextMilestone && (
            <div className="flex items-center justify-between p-4 rounded-lg bg-gradient-to-r from-green-500/10 to-transparent border border-green-500/20">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-green-500/20 flex items-center justify-center">
                  <Trophy className="w-5 h-5 text-green-500" />
                </div>
                <div>
                  <p className="font-medium">Next: {nextMilestone.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {nextMilestone.points_needed} points to {nextMilestone.rating}
                  </p>
                </div>
              </div>
              <div className="text-right">
                {nextMilestone.estimated_months ? (
                  <>
                    <p className="text-2xl font-bold text-green-500">{nextMilestone.estimated_months}</p>
                    <p className="text-xs text-muted-foreground">months</p>
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">Keep practicing!</p>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Weakness Impact Card */}
      {trajectory?.weakness_impact?.length > 0 && (
        <Card className="surface">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Target className="w-4 h-4 text-amber-500" />
              Rating Potential from Fixing Weaknesses
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {trajectory.weakness_impact.slice(0, 3).map((w, i) => (
              <div key={i} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-amber-500" />
                  <span className="text-sm capitalize">{w.weakness?.replace(/_/g, ' ')}</span>
                </div>
                <span className="text-sm font-medium text-green-500">+{w.potential_rating_gain} pts</span>
              </div>
            ))}
            <div className="pt-2 border-t border-border flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Total potential gain</span>
              <span className="font-bold text-green-500">+{trajectory.total_potential_gain} pts</span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tips */}
      {trajectory?.improvement_tips?.length > 0 && (
        <Card className="surface">
          <CardContent className="py-4">
            <div className="space-y-2">
              {trajectory.improvement_tips.map((tip, i) => (
                <p key={i} className="text-sm text-muted-foreground">{tip}</p>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Platform Ratings */}
      {(platform_ratings?.chess_com || platform_ratings?.lichess) && (
        <Card className="surface">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">All Ratings</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              {platform_ratings?.chess_com && (
                <div>
                  <p className="text-xs text-muted-foreground mb-2">Chess.com</p>
                  <div className="space-y-1">
                    {platform_ratings.chess_com.rapid && <RatingRow label="Rapid" value={platform_ratings.chess_com.rapid} />}
                    {platform_ratings.chess_com.blitz && <RatingRow label="Blitz" value={platform_ratings.chess_com.blitz} />}
                    {platform_ratings.chess_com.bullet && <RatingRow label="Bullet" value={platform_ratings.chess_com.bullet} />}
                  </div>
                </div>
              )}
              {platform_ratings?.lichess && (
                <div>
                  <p className="text-xs text-muted-foreground mb-2">Lichess</p>
                  <div className="space-y-1">
                    {platform_ratings.lichess.rapid && <RatingRow label="Rapid" value={platform_ratings.lichess.rapid} />}
                    {platform_ratings.lichess.blitz && <RatingRow label="Blitz" value={platform_ratings.lichess.blitz} />}
                    {platform_ratings.lichess.classical && <RatingRow label="Classical" value={platform_ratings.lichess.classical} />}
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </motion.div>
  );
};

const RatingRow = ({ label, value }) => (
  <div className="flex items-center justify-between text-sm">
    <span className="text-muted-foreground">{label}</span>
    <span className={`font-medium ${getMilestoneColor(value)}`}>{value}</span>
  </div>
);

// Time Management Component
export const TimeManagement = () => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);

  useEffect(() => {
    fetchTimeData();
  }, []);

  const fetchTimeData = async () => {
    try {
      const res = await fetch(API + "/training/time-management", { credentials: "include" });
      if (res.ok) setData(await res.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Card className="surface">
        <CardContent className="py-8 flex items-center justify-center">
          <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (!data?.has_data) {
    return (
      <Card className="surface">
        <CardContent className="py-6 text-center">
          <Clock className="w-8 h-8 mx-auto mb-3 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{data?.message || "Play more timed games to see analysis"}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="surface">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Clock className="w-4 h-4 text-blue-500" />
          Time Management
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Phase breakdown */}
        <div className="grid grid-cols-3 gap-2">
          {data.phase_breakdown?.opening && (
            <div className="text-center p-2 rounded bg-muted/30">
              <p className="text-xs text-muted-foreground">Opening</p>
              <p className="font-medium">{data.phase_breakdown.opening.avg_time}s</p>
            </div>
          )}
          {data.phase_breakdown?.middlegame && (
            <div className="text-center p-2 rounded bg-muted/30">
              <p className="text-xs text-muted-foreground">Middle</p>
              <p className="font-medium">{data.phase_breakdown.middlegame.avg_time}s</p>
            </div>
          )}
          {data.phase_breakdown?.endgame && (
            <div className="text-center p-2 rounded bg-muted/30">
              <p className="text-xs text-muted-foreground">Endgame</p>
              <p className="font-medium">{data.phase_breakdown.endgame.avg_time}s</p>
            </div>
          )}
        </div>

        {/* Insights */}
        {data.insights?.length > 0 && (
          <div className="space-y-2">
            {data.insights.map((insight, i) => (
              <div 
                key={i} 
                className={`text-sm p-2 rounded ${
                  insight.type === 'critical' ? 'bg-red-500/10 text-red-400' :
                  insight.type === 'warning' ? 'bg-amber-500/10 text-amber-400' :
                  'bg-blue-500/10 text-blue-400'
                }`}
              >
                {insight.message}
              </div>
            ))}
          </div>
        )}

        {/* Recommendations */}
        {data.recommendations?.length > 0 && (
          <div className="space-y-1 pt-2 border-t border-border">
            {data.recommendations.map((rec, i) => (
              <p key={i} className="text-xs text-muted-foreground">{rec}</p>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// Fast Thinking Component
export const FastThinking = () => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const res = await fetch(API + "/training/fast-thinking", { credentials: "include" });
      if (res.ok) setData(await res.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Card className="surface">
        <CardContent className="py-8 flex items-center justify-center">
          <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (!data?.has_data) {
    return (
      <Card className="surface">
        <CardContent className="py-6 text-center">
          <Brain className="w-8 h-8 mx-auto mb-3 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Analyze more games to see thinking patterns</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="surface">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Brain className="w-4 h-4 text-purple-500" />
          Calculation Speed
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Speed issues */}
        {data.speed_issues?.length > 0 && (
          <div className="space-y-2">
            {data.speed_issues.map((issue, i) => (
              <div key={i} className="flex items-start gap-3 p-2 rounded bg-muted/30">
                <AlertTriangle className="w-4 h-4 text-amber-500 mt-0.5" />
                <div>
                  <p className="text-sm font-medium">{issue.pattern}</p>
                  <p className="text-xs text-muted-foreground">{issue.tip}</p>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Overall tip */}
        {data.overall_tip && (
          <p className="text-sm text-muted-foreground">{data.overall_tip}</p>
        )}

        {data.recommended_drill_time && (
          <div className="flex items-center gap-2 text-sm">
            <Zap className="w-4 h-4 text-amber-500" />
            <span>Recommended: {data.recommended_drill_time}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// Puzzle Trainer Component
export const PuzzleTrainer = () => {
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState(null);
  const [currentPuzzle, setCurrentPuzzle] = useState(0);

  useEffect(() => {
    fetchPuzzles();
  }, []);

  const fetchPuzzles = async () => {
    try {
      const res = await fetch(API + "/training/puzzles?count=5", { credentials: "include" });
      if (res.ok) setSession(await res.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Card className="surface">
        <CardContent className="py-8 flex items-center justify-center">
          <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  const puzzle = session?.puzzles?.[currentPuzzle];

  return (
    <Card className="surface">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Zap className="w-4 h-4 text-amber-500" />
          {session?.session_type === 'targeted' ? `Training: ${session.target_weakness}` : 'Tactical Training'}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {session?.tips?.length > 0 && (
          <div className="p-3 rounded bg-amber-500/10 border border-amber-500/20">
            <p className="text-sm font-medium text-amber-500 mb-1">💡 Tips</p>
            {session.tips.slice(0, 2).map((tip, i) => (
              <p key={i} className="text-xs text-muted-foreground">{tip}</p>
            ))}
          </div>
        )}

        {puzzle && (
          <div className="text-center py-4">
            <p className="text-xs text-muted-foreground mb-2">
              Puzzle {currentPuzzle + 1} of {session.puzzles.length}
            </p>
            <p className="font-mono text-sm mb-2">{puzzle.theme}</p>
            <p className="text-muted-foreground text-sm">
              Find the best move! (Difficulty: {puzzle.difficulty})
            </p>
          </div>
        )}

        {session?.estimated_time_minutes && (
          <p className="text-xs text-muted-foreground text-center">
            Estimated time: {session.estimated_time_minutes} minutes
          </p>
        )}

        <div className="flex gap-2">
          <Button 
            variant="outline" 
            size="sm" 
            className="flex-1"
            onClick={() => setCurrentPuzzle(Math.max(0, currentPuzzle - 1))}
            disabled={currentPuzzle === 0}
          >
            Previous
          </Button>
          <Button 
            variant="outline" 
            size="sm" 
            className="flex-1"
            onClick={() => setCurrentPuzzle(Math.min(session?.puzzles?.length - 1, currentPuzzle + 1))}
            disabled={currentPuzzle >= (session?.puzzles?.length - 1)}
          >
            Next
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default RatingTrajectory;
