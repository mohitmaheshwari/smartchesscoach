import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { API } from "@/App";
import {
  Brain,
  TrendingUp,
  TrendingDown,
  Minus,
  Target,
  AlertTriangle,
  Sparkles,
  ChevronRight,
  Dumbbell,
  LineChart,
  Loader2,
} from "lucide-react";

const GapProgressDashboard = ({ onTrainGap }) => {
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState(null);
  const [progress, setProgress] = useState(null);
  const [planQuality, setPlanQuality] = useState(null);
  const [recurringPatterns, setRecurringPatterns] = useState([]);
  const [recommendations, setRecommendations] = useState(null);
  const [activeTab, setActiveTab] = useState("overview");

  useEffect(() => {
    fetchAllData();
  }, []);

  const fetchAllData = async () => {
    setLoading(true);
    try {
      const [summaryRes, progressRes, planRes, recurringRes, recsRes] = await Promise.all([
        fetch(`${API}/cognitive-gaps/summary`, { credentials: "include" }),
        fetch(`${API}/cognitive-gaps/progress?weeks=8`, { credentials: "include" }),
        fetch(`${API}/cognitive-gaps/plan-quality`, { credentials: "include" }),
        fetch(`${API}/cognitive-gaps/recurring`, { credentials: "include" }),
        fetch(`${API}/drills/recommended`, { credentials: "include" }),
      ]);

      if (summaryRes.ok) setSummary(await summaryRes.json());
      if (progressRes.ok) setProgress(await progressRes.json());
      if (planRes.ok) setPlanQuality(await planRes.json());
      if (recurringRes.ok) {
        const data = await recurringRes.json();
        setRecurringPatterns(data.patterns || []);
      }
      if (recsRes.ok) setRecommendations(await recsRes.json());
    } catch (err) {
      console.error("Error fetching gap data:", err);
    } finally {
      setLoading(false);
    }
  };

  const getTrendIcon = (trend) => {
    if (trend === "improving") return <TrendingDown className="w-4 h-4 text-green-500" />;
    if (trend === "worsening") return <TrendingUp className="w-4 h-4 text-red-500" />;
    return <Minus className="w-4 h-4 text-muted-foreground" />;
  };

  const getTrendColor = (trend) => {
    if (trend === "improving") return "text-green-500";
    if (trend === "worsening") return "text-red-500";
    return "text-muted-foreground";
  };

  const getSeverityColor = (severity) => {
    if (severity === "critical") return "border-red-500/50 bg-red-500/10";
    if (severity === "high") return "border-orange-500/50 bg-orange-500/10";
    if (severity === "medium") return "border-amber-500/50 bg-amber-500/10";
    return "border-muted";
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="py-8 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (!summary?.has_data) {
    return (
      <Card className="border-dashed">
        <CardContent className="py-8 text-center">
          <Brain className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-muted-foreground mb-2">No cognitive gap data yet</p>
          <p className="text-sm text-muted-foreground">
            Complete reflections to see your mistake patterns and progress.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Tab Navigation */}
      <div className="flex gap-2 border-b border-border pb-2">
        {[
          { id: "overview", label: "Overview", icon: Brain },
          { id: "progress", label: "Progress", icon: LineChart },
          { id: "plans", label: "Plan Quality", icon: Target },
        ].map((tab) => (
          <Button
            key={tab.id}
            variant={activeTab === tab.id ? "default" : "ghost"}
            size="sm"
            onClick={() => setActiveTab(tab.id)}
            className="gap-2"
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </Button>
        ))}
      </div>

      {/* Overview Tab */}
      {activeTab === "overview" && (
        <div className="space-y-4">
          {/* Summary Card */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <Brain className="w-5 h-5 text-primary" />
                Cognitive Gap Summary
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center p-3 bg-muted/30 rounded-lg">
                  <div className="text-2xl font-bold">{summary.total_gaps_tracked}</div>
                  <div className="text-xs text-muted-foreground">Gaps Analyzed</div>
                </div>
                <div className="text-center p-3 bg-muted/30 rounded-lg">
                  <div className={`text-2xl font-bold ${getTrendColor(summary.overall_trend)}`}>
                    {summary.overall_trend === "improving" ? "↓" : summary.overall_trend === "worsening" ? "↑" : "→"}
                  </div>
                  <div className="text-xs text-muted-foreground">Overall Trend</div>
                </div>
                <div className="text-center p-3 bg-muted/30 rounded-lg">
                  <div className="text-2xl font-bold text-green-500">{summary.improving_count}</div>
                  <div className="text-xs text-muted-foreground">Improving</div>
                </div>
              </div>

              {summary.dominant_gap && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30">
                  <div className="text-xs text-red-400 mb-1">Your biggest weakness</div>
                  <div className="font-medium">{summary.dominant_gap.name}</div>
                  <div className="text-sm text-muted-foreground">
                    {summary.dominant_gap.count} occurrences
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Recurring Patterns Alert */}
          {recurringPatterns.length > 0 && (
            <Card className="border-amber-500/50 bg-amber-500/5">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2 text-amber-400">
                  <AlertTriangle className="w-5 h-5" />
                  Recurring Patterns This Week
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {recurringPatterns.slice(0, 3).map((pattern, idx) => (
                  <div
                    key={idx}
                    className={`p-3 rounded-lg border ${getSeverityColor(pattern.severity)}`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium">{pattern.gap_name}</div>
                        <div className="text-sm text-muted-foreground">
                          {pattern.occurrences} times this week
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onTrainGap?.(pattern.gap_type)}
                        className="gap-1"
                        data-testid={`train-gap-${pattern.gap_type}`}
                      >
                        <Dumbbell className="w-3 h-3" />
                        Train
                      </Button>
                    </div>
                    <div className="text-xs text-muted-foreground mt-2">
                      {pattern.training_focus}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Recommended Drills */}
          {recommendations?.has_data && recommendations.recommendations?.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <Target className="w-5 h-5 text-primary" />
                  Recommended Training
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {recommendations.recommendations.map((rec, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-2 hover:bg-muted/30 rounded-lg cursor-pointer"
                    onClick={() => onTrainGap?.(rec.gap_type)}
                  >
                    <div className="flex items-center gap-3">
                      <Badge variant="outline" className="text-xs">
                        #{idx + 1}
                      </Badge>
                      <div>
                        <div className="font-medium text-sm">{rec.gap_name}</div>
                        <div className="text-xs text-muted-foreground">
                          {rec.occurrences} mistakes • {rec.drill_category}
                        </div>
                      </div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-muted-foreground" />
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Progress Tab */}
      {activeTab === "progress" && progress && (
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <LineChart className="w-5 h-5 text-primary" />
                Gap Trends ({progress.weeks_analyzed} weeks)
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Overall trend */}
              <div className={`p-4 rounded-lg ${
                progress.overall_trend === "improving" ? "bg-green-500/10 border border-green-500/30" :
                progress.overall_trend === "worsening" ? "bg-red-500/10 border border-red-500/30" :
                "bg-muted/30"
              }`}>
                <div className="flex items-center gap-2 mb-1">
                  {getTrendIcon(progress.overall_trend)}
                  <span className={`font-medium ${getTrendColor(progress.overall_trend)}`}>
                    {progress.overall_trend === "improving" ? "Improving!" :
                     progress.overall_trend === "worsening" ? "Needs attention" :
                     "Stable"}
                  </span>
                </div>
                <p className="text-sm text-muted-foreground">
                  {progress.overall_change_percent > 0 ? "+" : ""}{progress.overall_change_percent}% change
                </p>
              </div>

              {/* Individual gap progress */}
              <div className="space-y-3">
                {progress.gaps?.slice(0, 5).map((gap, idx) => (
                  <div key={idx} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {getTrendIcon(gap.trend)}
                        <span className="text-sm font-medium">{gap.gap_name}</span>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {gap.total_occurrences} total
                      </span>
                    </div>
                    <div className="flex gap-1">
                      {progress.week_labels?.map((week, wIdx) => {
                        const count = gap.weekly_counts?.[week] || 0;
                        const maxCount = Math.max(...Object.values(gap.weekly_counts || {}), 1);
                        const height = Math.max(4, (count / maxCount) * 24);
                        return (
                          <div
                            key={wIdx}
                            className="flex-1 flex items-end"
                            title={`${week}: ${count}`}
                          >
                            <div
                              className={`w-full rounded-sm ${
                                count > 0 ? "bg-primary/60" : "bg-muted/30"
                              }`}
                              style={{ height: `${height}px` }}
                            />
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Improving vs Worsening */}
          <div className="grid grid-cols-2 gap-4">
            <Card className="border-green-500/30">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-green-400 flex items-center gap-2">
                  <TrendingDown className="w-4 h-4" />
                  Improving ({progress.improving_gaps?.length || 0})
                </CardTitle>
              </CardHeader>
              <CardContent>
                {progress.improving_gaps?.length > 0 ? (
                  <div className="space-y-1">
                    {progress.improving_gaps.slice(0, 3).map((g, i) => (
                      <div key={i} className="text-sm">{g.gap_name}</div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">None yet</p>
                )}
              </CardContent>
            </Card>
            <Card className="border-red-500/30">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-red-400 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4" />
                  Needs Work ({progress.worsening_gaps?.length || 0})
                </CardTitle>
              </CardHeader>
              <CardContent>
                {progress.worsening_gaps?.length > 0 ? (
                  <div className="space-y-1">
                    {progress.worsening_gaps.slice(0, 3).map((g, i) => (
                      <div key={i} className="text-sm">{g.gap_name}</div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">None - great!</p>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* Plan Quality Tab */}
      {activeTab === "plans" && planQuality && (
        <div className="space-y-4">
          {planQuality.has_data ? (
            <>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Target className="w-5 h-5 text-primary" />
                    Plan Quality Analysis
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Insight */}
                  <div className="p-3 rounded-lg bg-primary/10 border border-primary/30">
                    <div className="flex items-start gap-2">
                      <Sparkles className="w-4 h-4 text-primary mt-0.5" />
                      <p className="text-sm">{planQuality.insight}</p>
                    </div>
                  </div>

                  {/* Stats */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-3 bg-muted/30 rounded-lg">
                      <div className="text-2xl font-bold">{planQuality.accuracy?.rate}%</div>
                      <div className="text-xs text-muted-foreground">Plan Accuracy</div>
                      <Progress value={planQuality.accuracy?.rate || 0} className="mt-2 h-1" />
                    </div>
                    <div className="p-3 bg-muted/30 rounded-lg">
                      <div className="text-2xl font-bold capitalize">{planQuality.plan_quality?.specificity}</div>
                      <div className="text-xs text-muted-foreground">Plan Detail Level</div>
                      <div className="text-xs text-muted-foreground mt-1">
                        ~{planQuality.plan_quality?.avg_length} chars avg
                      </div>
                    </div>
                  </div>

                  {/* Trend */}
                  <div className={`p-3 rounded-lg ${
                    planQuality.trend?.direction === "improving" ? "bg-green-500/10" :
                    planQuality.trend?.direction === "worsening" ? "bg-red-500/10" :
                    "bg-muted/30"
                  }`}>
                    <div className="flex items-center gap-2">
                      {getTrendIcon(planQuality.trend?.direction)}
                      <span className="font-medium">
                        {planQuality.trend?.direction === "improving" ? "Plans are improving!" :
                         planQuality.trend?.direction === "worsening" ? "Plans need work" :
                         "Plans are consistent"}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground mt-1">
                      Recent: {planQuality.trend?.recent_accuracy}% vs Earlier: {planQuality.trend?.older_accuracy}%
                    </p>
                  </div>

                  {/* Confidence Calibration */}
                  {planQuality.confidence_calibration && Object.keys(planQuality.confidence_calibration).length > 0 && (
                    <div>
                      <div className="text-sm font-medium mb-2">Confidence Calibration</div>
                      <div className="space-y-2">
                        {Object.entries(planQuality.confidence_calibration).map(([conf, data]) => (
                          <div key={conf} className="flex items-center justify-between text-sm">
                            <span className="capitalize">{conf.replace(/_/g, " ")}</span>
                            <span className={data.accuracy > 60 ? "text-green-500" : data.accuracy < 40 ? "text-red-500" : ""}>
                              {data.accuracy}% accurate ({data.sample_size} samples)
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          ) : (
            <Card className="border-dashed">
              <CardContent className="py-8 text-center">
                <Target className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
                <p className="text-muted-foreground">{planQuality.message}</p>
                <p className="text-sm text-muted-foreground mt-1">
                  {planQuality.plans_recorded || 0} plans recorded so far
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
};

export default GapProgressDashboard;
