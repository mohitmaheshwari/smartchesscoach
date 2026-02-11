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
    </Layout>
  );
};

export default ProgressV2;
