import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import BadgeDetailModal from "@/components/BadgeDetailModal";
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
  Shield,
  Crown,
  Brain,
  Focus,
  Trophy,
  Crosshair,
  ChevronRight,
  Lightbulb,
  AlertTriangle,
  ArrowRight,
  Swords,
  Eye
} from "lucide-react";

// Badge icon mapping
const BADGE_ICONS = {
  opening: Target,
  tactical: Swords,
  positional: Brain,
  endgame: Crown,
  defense: Shield,
  converting: Trophy,
  focus: Eye,
  time: Clock
};

// Star rating component
const StarRating = ({ score, size = "md" }) => {
  const fullStars = Math.floor(score);
  const hasHalf = score - fullStars >= 0.3 && score - fullStars < 0.8;
  const sizeClass = size === "lg" ? "w-5 h-5" : "w-4 h-4";
  
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <span 
          key={star} 
          className={`${sizeClass} ${
            star <= fullStars 
              ? "text-yellow-500" 
              : star === fullStars + 1 && hasHalf 
                ? "text-yellow-500/50" 
                : "text-gray-300 dark:text-gray-600"
          }`}
        >
          ★
        </span>
      ))}
      <span className="ml-1 text-sm font-medium text-muted-foreground">
        {score.toFixed(1)}
      </span>
    </div>
  );
};

// Trend badge component
const TrendBadge = ({ trend }) => {
  if (trend === "improving") {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-green-500 bg-green-500/10 px-2 py-0.5 rounded-full">
        <TrendingUp className="w-3 h-3" /> ↑
      </span>
    );
  }
  if (trend === "declining") {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-red-500 bg-red-500/10 px-2 py-0.5 rounded-full">
        <TrendingDown className="w-3 h-3" /> ↓
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
      <Minus className="w-3 h-3" /> →
    </span>
  );
};

// Badge card component - NOW CLICKABLE
const BadgeCard = ({ badge, isStrength, isWeakness, onClick }) => {
  const Icon = BADGE_ICONS[badge.key] || Target;
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={() => onClick(badge)}
      className={`p-3 rounded-lg border cursor-pointer transition-all hover:shadow-md ${
        isStrength 
          ? "border-green-500/30 bg-green-500/5 hover:border-green-500/50" 
          : isWeakness 
            ? "border-red-500/30 bg-red-500/5 hover:border-red-500/50" 
            : "border-border bg-card hover:border-amber-500/30"
      }`}
      data-testid={`badge-card-${badge.key}`}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className={`p-1.5 rounded ${
            isStrength ? "bg-green-500/20" : isWeakness ? "bg-red-500/20" : "bg-muted"
          }`}>
            <Icon className={`w-4 h-4 ${
              isStrength ? "text-green-500" : isWeakness ? "text-red-500" : "text-muted-foreground"
            }`} />
          </div>
          <span className="text-sm font-medium">{badge.name}</span>
        </div>
        <TrendBadge trend={badge.trend} />
      </div>
      <StarRating score={badge.score} />
      <p className="text-xs text-muted-foreground mt-2 line-clamp-2">
        {badge.insight}
      </p>
      <div className="flex items-center justify-end mt-2 text-xs text-amber-500 opacity-0 group-hover:opacity-100 transition-opacity">
        <span>See why</span>
        <ChevronRight className="w-3 h-3 ml-1" />
      </div>
    </motion.div>
  );
};

// Coach message component
const CoachMessage = ({ message }) => {
  if (!message) return null;
  
  // Split message by ** for bold sections
  const parts = message.split(/(\*\*.*?\*\*)/g);
  
  return (
    <div className="whitespace-pre-line text-sm leading-relaxed">
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return <strong key={i} className="text-foreground">{part.slice(2, -2)}</strong>;
        }
        return <span key={i}>{part}</span>;
      })}
    </div>
  );
};

// Rule card component
const RuleCard = ({ rule, index }) => (
  <motion.div
    initial={{ opacity: 0, x: -10 }}
    animate={{ opacity: 1, x: 0 }}
    transition={{ delay: index * 0.1 }}
    className={`p-4 rounded-lg border ${
      rule.is_primary ? "border-amber-500/30 bg-amber-500/5" : "border-border bg-card"
    }`}
  >
    <div className="flex items-start gap-3">
      <div className={`p-2 rounded-full ${
        rule.is_primary ? "bg-amber-500/20" : "bg-muted"
      }`}>
        <Lightbulb className={`w-4 h-4 ${
          rule.is_primary ? "text-amber-500" : "text-muted-foreground"
        }`} />
      </div>
      <div className="flex-1">
        <p className="font-medium text-sm">{rule.rule}</p>
        <p className="text-xs text-muted-foreground mt-1">{rule.reason}</p>
      </div>
    </div>
  </motion.div>
);

// Before Coach vs After Coach Comparison Component
const CoachingComparisonSection = ({ comparison }) => {
  const [activeTab, setActiveTab] = useState('progress'); // 'before', 'after', 'progress'
  
  if (!comparison.has_baseline) {
    // Still building baseline
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <Card className="border-2 border-dashed border-primary/30">
          <CardContent className="py-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                <Target className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h3 className="font-semibold">Getting to Know Your Game</h3>
                <p className="text-sm text-muted-foreground">
                  {comparison.games_until_baseline > 0 
                    ? `${comparison.games_until_baseline} more games to analyze`
                    : 'Almost ready...'}
                </p>
              </div>
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden">
              <div 
                className="h-full bg-primary transition-all"
                style={{ width: `${((10 - comparison.games_until_baseline) / 10) * 100}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground mt-3">
              We're learning your playing style to track your improvement.
            </p>
          </CardContent>
        </Card>
      </motion.div>
    );
  }

  const { baseline, current, progress } = comparison;
  if (!progress) return null;

  // Determine improvements and focus areas
  const getInsights = () => {
    const improving = [];
    const needsWork = [];

    if (progress.accuracy.delta >= 3) {
      improving.push({ label: "Move Quality", detail: "Your moves are getting sharper" });
    } else if (progress.accuracy.delta <= -3) {
      needsWork.push({ label: "Move Quality", detail: "Focus on calculating before moving" });
    }

    if (progress.blunders_per_game.delta <= -0.5) {
      improving.push({ label: "Blunder Control", detail: "Making fewer game-losing mistakes" });
    } else if (progress.blunders_per_game.delta >= 0.3) {
      needsWork.push({ label: "Blunder Control", detail: "Double-check before big moves" });
    }

    if (progress.win_rate.delta >= 5) {
      improving.push({ label: "Winning More", detail: "Your results are improving" });
    } else if (progress.win_rate.delta <= -5) {
      needsWork.push({ label: "Game Results", detail: "Focus on converting advantages" });
    }

    return { improving, needsWork };
  };

  const { improving, needsWork } = getInsights();
  const overallImproving = improving.length >= needsWork.length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <Card className="overflow-hidden">
        {/* Tabs */}
        <div className="flex border-b">
          <button
            onClick={() => setActiveTab('before')}
            className={`flex-1 py-3 px-4 text-sm font-medium transition-colors ${
              activeTab === 'before' 
                ? 'bg-muted/50 border-b-2 border-amber-500 text-amber-500' 
                : 'text-muted-foreground hover:bg-muted/30'
            }`}
          >
            Before Coach
          </button>
          <button
            onClick={() => setActiveTab('after')}
            className={`flex-1 py-3 px-4 text-sm font-medium transition-colors ${
              activeTab === 'after' 
                ? 'bg-muted/50 border-b-2 border-emerald-500 text-emerald-500' 
                : 'text-muted-foreground hover:bg-muted/30'
            }`}
          >
            After Coach
          </button>
          <button
            onClick={() => setActiveTab('progress')}
            className={`flex-1 py-3 px-4 text-sm font-medium transition-colors ${
              activeTab === 'progress' 
                ? 'bg-muted/50 border-b-2 border-primary text-primary' 
                : 'text-muted-foreground hover:bg-muted/30'
            }`}
          >
            Your Growth
          </button>
        </div>

        <CardContent className="py-5">
          {/* Before Coach Tab */}
          {activeTab === 'before' && baseline && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 mb-4">
                <Clock className="w-4 h-4 text-amber-500" />
                <span className="text-sm text-muted-foreground">
                  Based on your first {baseline.games_analyzed} games
                </span>
              </div>
              
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-4 rounded-lg bg-amber-500/5 border border-amber-500/20">
                  <p className="text-xs text-muted-foreground mb-1">Accuracy</p>
                  <p className="text-2xl font-bold text-amber-500">{baseline.avg_accuracy}%</p>
                </div>
                <div className="text-center p-4 rounded-lg bg-amber-500/5 border border-amber-500/20">
                  <p className="text-xs text-muted-foreground mb-1">Blunders/Game</p>
                  <p className="text-2xl font-bold text-amber-500">{baseline.blunders_per_game}</p>
                </div>
                <div className="text-center p-4 rounded-lg bg-amber-500/5 border border-amber-500/20">
                  <p className="text-xs text-muted-foreground mb-1">Win Rate</p>
                  <p className="text-2xl font-bold text-amber-500">{baseline.win_rate}%</p>
                </div>
                <div className="text-center p-4 rounded-lg bg-amber-500/5 border border-amber-500/20">
                  <p className="text-xs text-muted-foreground mb-1">Mistakes/Game</p>
                  <p className="text-2xl font-bold text-amber-500">{baseline.mistakes_per_game}</p>
                </div>
              </div>

              {baseline.top_openings && baseline.top_openings.length > 0 && (
                <div className="mt-4 pt-4 border-t">
                  <p className="text-xs text-muted-foreground mb-3">Opening Win Rates</p>
                  {baseline.top_openings.slice(0, 3).map((o, i) => (
                    <div key={i} className="flex justify-between py-1.5 text-sm">
                      <span>{o.name}</span>
                      <span className="text-amber-500 font-medium">{o.win_rate}%</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* After Coach Tab */}
          {activeTab === 'after' && current && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 mb-4">
                <TrendingUp className="w-4 h-4 text-emerald-500" />
                <span className="text-sm text-muted-foreground">
                  Based on your last {current.games_analyzed} games
                </span>
              </div>
              
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-4 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
                  <p className="text-xs text-muted-foreground mb-1">Accuracy</p>
                  <p className="text-2xl font-bold text-emerald-500">{current.avg_accuracy}%</p>
                  {progress.accuracy.delta !== 0 && (
                    <p className={`text-xs ${progress.accuracy.delta > 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                      {progress.accuracy.delta > 0 ? '+' : ''}{progress.accuracy.delta}%
                    </p>
                  )}
                </div>
                <div className="text-center p-4 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
                  <p className="text-xs text-muted-foreground mb-1">Blunders/Game</p>
                  <p className="text-2xl font-bold text-emerald-500">{current.blunders_per_game}</p>
                  {progress.blunders_per_game.delta !== 0 && (
                    <p className={`text-xs ${progress.blunders_per_game.delta < 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                      {progress.blunders_per_game.delta > 0 ? '+' : ''}{progress.blunders_per_game.delta}
                    </p>
                  )}
                </div>
                <div className="text-center p-4 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
                  <p className="text-xs text-muted-foreground mb-1">Win Rate</p>
                  <p className="text-2xl font-bold text-emerald-500">{current.win_rate}%</p>
                  {progress.win_rate.delta !== 0 && (
                    <p className={`text-xs ${progress.win_rate.delta > 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                      {progress.win_rate.delta > 0 ? '+' : ''}{progress.win_rate.delta}%
                    </p>
                  )}
                </div>
                <div className="text-center p-4 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
                  <p className="text-xs text-muted-foreground mb-1">Mistakes/Game</p>
                  <p className="text-2xl font-bold text-emerald-500">{current.mistakes_per_game}</p>
                  {progress.mistakes_per_game.delta !== 0 && (
                    <p className={`text-xs ${progress.mistakes_per_game.delta < 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                      {progress.mistakes_per_game.delta > 0 ? '+' : ''}{progress.mistakes_per_game.delta}
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Your Growth Tab */}
          {activeTab === 'progress' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  {overallImproving 
                    ? <TrendingUp className="w-5 h-5 text-emerald-500" />
                    : <Target className="w-5 h-5 text-amber-500" />
                  }
                  <span className="text-sm text-muted-foreground">
                    {progress.games_since_baseline} games with your coach
                  </span>
                </div>
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                  overallImproving 
                    ? 'bg-emerald-500/10 text-emerald-500'
                    : 'bg-amber-500/10 text-amber-500'
                }`}>
                  {overallImproving ? 'Growing!' : 'Keep Going!'}
                </span>
              </div>

              <div className="grid md:grid-cols-2 gap-6">
                {/* What's Improving */}
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                    <span className="text-sm font-medium text-emerald-500">What's Improving</span>
                  </div>
                  {improving.length > 0 ? (
                    <div className="space-y-2">
                      {improving.map((item, idx) => (
                        <div key={idx} className="p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/10">
                          <p className="font-medium text-sm">{item.label}</p>
                          <p className="text-xs text-muted-foreground">{item.detail}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground p-3 bg-muted/30 rounded-lg">
                      Keep playing! We're tracking your progress.
                    </p>
                  )}
                </div>

                {/* Focus Areas */}
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <Target className="w-4 h-4 text-amber-500" />
                    <span className="text-sm font-medium text-amber-500">Focus Areas</span>
                  </div>
                  {needsWork.length > 0 ? (
                    <div className="space-y-2">
                      {needsWork.map((item, idx) => (
                        <div key={idx} className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/10">
                          <p className="font-medium text-sm">{item.label}</p>
                          <p className="text-xs text-muted-foreground">{item.detail}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground p-3 bg-muted/30 rounded-lg">
                      Great job! No major concerns right now.
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
};

const ProgressV2 = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  
  // Badge detail modal state
  const [selectedBadge, setSelectedBadge] = useState(null);
  const [badgeModalOpen, setBadgeModalOpen] = useState(false);

  useEffect(() => {
    fetchProgress();
  }, []);

  const fetchProgress = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${API}/progress/v2`, {
        credentials: "include"
      });
      
      if (!response.ok) throw new Error("Failed to fetch progress data");
      
      const result = await response.json();
      setData(result);
    } catch (err) {
      console.error("Progress fetch error:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Handle badge click - open modal
  const handleBadgeClick = (badge) => {
    setSelectedBadge(badge);
    setBadgeModalOpen(true);
  };

  // Close modal
  const handleCloseBadgeModal = () => {
    setBadgeModalOpen(false);
    setSelectedBadge(null);
  };

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
        </div>
      </Layout>
    );
  }

  if (error || !data) {
    return (
      <Layout user={user}>
        <div className="max-w-4xl mx-auto px-4 py-8">
          <Card className="p-8 text-center">
            <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
            <h2 className="text-xl font-semibold mb-2">Unable to load progress</h2>
            <p className="text-muted-foreground mb-4">
              {error || "Import and analyze some games first to see your progress."}
            </p>
            <Button onClick={() => navigate("/import")}>Import Games</Button>
          </Card>
        </div>
      </Layout>
    );
  }

  const { 
    coach_assessment, 
    rating_reality, 
    badges, 
    proof_from_games, 
    memorable_rules, 
    next_games_plan 
  } = data;

  const badgesList = Object.values(badges?.badges || {});
  const strengths = badges?.strengths || [];
  const weaknesses = badges?.weaknesses || [];

  return (
    <Layout user={user}>
      <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button 
              variant="ghost" 
              size="icon"
              onClick={() => navigate("/dashboard")}
            >
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div>
              <h1 className="text-2xl font-bold">Your Chess Journey</h1>
              <p className="text-sm text-muted-foreground">
                Honest assessment • Clear direction
              </p>
            </div>
          </div>
        </div>

        {/* NEW: Before Coach vs After Coach Comparison */}
        {data.coaching_comparison && (
          <CoachingComparisonSection comparison={data.coaching_comparison} />
        )}

        {/* Section 1: Coach's Assessment */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <Card className="overflow-hidden">
            <CardHeader className="bg-gradient-to-r from-amber-500/10 to-orange-500/10 border-b">
              <CardTitle className="flex items-center gap-2 text-lg">
                <Brain className="w-5 h-5 text-amber-500" />
                Coach's Assessment
              </CardTitle>
            </CardHeader>
            <CardContent className="p-5">
              {coach_assessment?.has_enough_data ? (
                <div className="space-y-4">
                  <CoachMessage message={coach_assessment.message} />
                  
                  {coach_assessment.capability_gap?.gap_type === "execution" && (
                    <div className="mt-4 p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
                      <div className="flex items-start gap-2">
                        <Eye className="w-4 h-4 text-blue-500 mt-0.5" />
                        <p className="text-sm text-blue-700 dark:text-blue-300">
                          {coach_assessment.capability_gap.evidence?.message}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-muted-foreground">
                  {coach_assessment?.message || "Analyze more games for a detailed assessment."}
                </p>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Section 2: Rating Reality */}
        {rating_reality && rating_reality.blunders_in_losses > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <TrendingUp className="w-5 h-5 text-green-500" />
                  Rating Reality
                </CardTitle>
              </CardHeader>
              <CardContent>
                <CoachMessage message={rating_reality.message} />
                
                {rating_reality.points_recoverable > 0 && (
                  <div className="mt-4 flex items-center gap-2 p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                    <Trophy className="w-5 h-5 text-green-500" />
                    <p className="text-sm">
                      <strong className="text-green-600 dark:text-green-400">
                        ~{rating_reality.points_recoverable} points
                      </strong>
                      <span className="text-muted-foreground"> recoverable by avoiding simple blunders</span>
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Section 2.5: Tactical Ratio - NEW Motivating Metric */}
        {badges?.tactical_ratio && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
          >
            <Card className="overflow-hidden border-amber-500/20">
              <CardHeader className="bg-gradient-to-r from-amber-500/5 to-orange-500/5 pb-2">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Zap className="w-5 h-5 text-amber-500" />
                  Tactical Ratio
                  <span className="ml-auto text-3xl font-bold text-amber-500">
                    {badges.tactical_ratio.percentage}%
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-4">
                {/* Progress bar */}
                <div className="relative h-4 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden mb-4">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${badges.tactical_ratio.percentage}%` }}
                    transition={{ duration: 1, ease: "easeOut" }}
                    className={`absolute left-0 top-0 h-full rounded-full ${
                      badges.tactical_ratio.percentage >= 75 
                        ? "bg-gradient-to-r from-green-500 to-emerald-500" 
                        : badges.tactical_ratio.percentage >= 50 
                          ? "bg-gradient-to-r from-amber-500 to-orange-500"
                          : "bg-gradient-to-r from-red-500 to-orange-500"
                    }`}
                  />
                </div>
                
                {/* Stats breakdown */}
                <div className="grid grid-cols-3 gap-3 mb-4">
                  <div className="text-center p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                    <div className="text-2xl font-bold text-green-500">
                      {badges.tactical_ratio.executed?.total || 0}
                    </div>
                    <div className="text-xs text-muted-foreground">Tactics Executed</div>
                    <div className="text-[10px] text-green-600 mt-1">
                      {badges.tactical_ratio.executed?.forks || 0} forks • {badges.tactical_ratio.executed?.pins || 0} pins • {badges.tactical_ratio.executed?.skewers || 0} skewers
                    </div>
                  </div>
                  
                  <div className="text-center p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
                    <div className="text-2xl font-bold text-blue-500">
                      {badges.tactical_ratio.avoided?.total || 0}
                    </div>
                    <div className="text-xs text-muted-foreground">Threats Avoided</div>
                    <div className="text-[10px] text-blue-600 mt-1">
                      Good defensive awareness!
                    </div>
                  </div>
                  
                  <div className="text-center p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                    <div className="text-2xl font-bold text-red-500">
                      {badges.tactical_ratio.fallen_into?.total || 0}
                    </div>
                    <div className="text-xs text-muted-foreground">Fell Into</div>
                    <div className="text-[10px] text-red-600 mt-1">
                      {badges.tactical_ratio.fallen_into?.forks || 0} forks • {badges.tactical_ratio.fallen_into?.pins || 0} pins • {badges.tactical_ratio.fallen_into?.skewers || 0} skewers
                    </div>
                  </div>
                </div>
                
                {/* Trend message */}
                <div className="flex items-center gap-2 p-3 rounded-lg bg-muted/50">
                  <Lightbulb className="w-4 h-4 text-amber-500 flex-shrink-0" />
                  <p className="text-sm">
                    {badges.tactical_ratio.trend_message}
                  </p>
                </div>
                
                {/* Weakness tip if present */}
                {badges.tactical_ratio.weakness && (
                  <div className="mt-3 flex items-center gap-2 p-2 rounded bg-amber-500/10 border border-amber-500/20">
                    <Target className="w-4 h-4 text-amber-500" />
                    <p className="text-xs text-amber-700 dark:text-amber-300">
                      Focus area: Practice recognizing <strong>{badges.tactical_ratio.weakness}</strong> - you're falling for these most often.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Section 3: Chess DNA Badges */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Crosshair className="w-5 h-5 text-purple-500" />
                  Your Chess DNA
                </CardTitle>
                <div className="text-sm text-muted-foreground">
                  Overall: <span className="font-bold text-foreground">{badges?.overall_score?.toFixed(1)}/5.0</span>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {badgesList.map((badge) => (
                  <BadgeCard 
                    key={badge.key} 
                    badge={badge}
                    isStrength={strengths.includes(badge.key)}
                    isWeakness={weaknesses.includes(badge.key)}
                    onClick={handleBadgeClick}
                  />
                ))}
              </div>
              
              {/* Hint text */}
              <p className="text-center text-xs text-muted-foreground mt-4">
                Click any badge to see which games affected your score
              </p>
              
              {/* Legend */}
              <div className="flex items-center justify-center gap-4 mt-3 pt-3 border-t text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-green-500"></span> Strength
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-red-500"></span> Focus Area
                </span>
                <span className="flex items-center gap-1">
                  <TrendingUp className="w-3 h-3 text-green-500" /> Improving
                </span>
                <span className="flex items-center gap-1">
                  <TrendingDown className="w-3 h-3 text-red-500" /> Declining
                </span>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Section 4: Proof From Games */}
        {proof_from_games?.has_proof && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Swords className="w-5 h-5 text-blue-500" />
                  Proof From Your Games
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">
                  {proof_from_games.message}
                </p>
                <div className="grid grid-cols-2 gap-4">
                  <div 
                    className="p-4 rounded-lg border border-red-500/30 bg-red-500/5 cursor-pointer hover:bg-red-500/10 transition-colors"
                    onClick={() => navigate(`/game/${proof_from_games.bad_example?.game_id}`)}
                  >
                    <div className="flex items-center gap-2 text-red-500 font-medium text-sm mb-2">
                      <AlertTriangle className="w-4 h-4" />
                      Mistake Example
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {proof_from_games.bad_example?.summary}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      vs {proof_from_games.bad_example?.opponent}
                    </p>
                  </div>
                  <div 
                    className="p-4 rounded-lg border border-green-500/30 bg-green-500/5 cursor-pointer hover:bg-green-500/10 transition-colors"
                    onClick={() => navigate(`/game/${proof_from_games.good_example?.game_id}`)}
                  >
                    <div className="flex items-center gap-2 text-green-500 font-medium text-sm mb-2">
                      <CheckCircle2 className="w-4 h-4" />
                      Clean Game
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {proof_from_games.good_example?.summary}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      vs {proof_from_games.good_example?.opponent}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Section 5: 2 Ideas to Remember */}
        {memorable_rules && memorable_rules.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Lightbulb className="w-5 h-5 text-amber-500" />
                  2 Ideas to Remember
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {memorable_rules.map((rule, i) => (
                  <RuleCard key={i} rule={rule} index={i} />
                ))}
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Section 6: Next 10 Games Plan */}
        {next_games_plan && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
          >
            <Card className="overflow-hidden">
              <CardHeader className="bg-gradient-to-r from-green-500/10 to-emerald-500/10 border-b">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Target className="w-5 h-5 text-green-500" />
                  Next {next_games_plan.games_count} Games Plan
                </CardTitle>
              </CardHeader>
              <CardContent className="p-5">
                <CoachMessage message={next_games_plan.message} />
                
                {next_games_plan.opening_advice && (
                  <div className="mt-4 p-3 rounded-lg bg-muted">
                    <p className="text-sm text-muted-foreground">
                      <strong className="text-foreground">Opening tip:</strong> {next_games_plan.opening_advice}
                    </p>
                  </div>
                )}
                
                <div className="mt-4 pt-4 border-t">
                  <Button 
                    className="w-full"
                    onClick={() => navigate("/training")}
                  >
                    Start Focused Training
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Footer note */}
        <div className="text-center text-xs text-muted-foreground py-4">
          Based on {badges?.games_analyzed || 0} analyzed games • Updated {new Date(data.generated_at).toLocaleDateString()}
        </div>

      </div>
      
      {/* Badge Detail Modal */}
      <BadgeDetailModal
        isOpen={badgeModalOpen}
        onClose={handleCloseBadgeModal}
        badgeKey={selectedBadge?.key}
        badgeName={selectedBadge?.name}
      />
    </Layout>
  );
};

export default ProgressV2;
