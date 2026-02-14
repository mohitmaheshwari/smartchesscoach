import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import { 
  Loader2, 
  Flame,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  TrendingUp,
  TrendingDown,
  Target,
  Zap,
  ChevronRight,
  BarChart3,
  Shield,
  Brain,
  Eye,
  Dumbbell,
  BookOpen,
  Clock,
  Crown,
  Minus
} from "lucide-react";
import EvidenceModal from "@/components/EvidenceModal";
import DrillMode from "@/components/DrillMode";
import { formatTotalCpLoss } from "@/utils/evalFormatter";

/**
 * JOURNEY PAGE - "How you're evolving"
 * 
 * KEPT:
 * - Weakness ranking (Your Weaknesses Prioritized) with evidence/training
 * - Win state analysis (Pattern Analysis / When You Blunder)
 * 
 * NEW:
 * - Chess Fundamentals Assessment
 * - Rating Ceiling Assessment
 * - Opening Progress
 * 
 * REMOVED:
 * - Mistake Heatmap
 * - Recent Achievements / Milestones
 * - Stable Strength
 * - Chess Identity
 */

// Trend indicator component
const TrendIndicator = ({ trend }) => {
  if (!trend) return null;
  
  const { recent, previous, change, direction } = trend;
  
  if (direction === "improving") {
    return (
      <span className="text-xs bg-green-500/20 text-green-400 px-2 py-0.5 rounded-full flex items-center gap-1">
        <TrendingDown className="w-3 h-3" />
        {previous} → {recent} ({change}%)
      </span>
    );
  } else if (direction === "worsening") {
    return (
      <span className="text-xs bg-red-500/20 text-red-400 px-2 py-0.5 rounded-full flex items-center gap-1">
        <TrendingUp className="w-3 h-3" />
        {previous} → {recent} (+{Math.abs(change)}%)
      </span>
    );
  }
  
  return (
    <span className="text-xs bg-gray-500/20 text-gray-400 px-2 py-0.5 rounded-full">
      Stable ({recent})
    </span>
  );
};

// Win state analysis component - Pattern Analysis / When You Blunder
const WinStateAnalysis = ({ data, onShowEvidence }) => {
  if (!data || data.total_blunders === 0) {
    return null;
  }

  const getStateEvidence = (state) => {
    if (state === 'winning') return data.when_winning?.evidence || [];
    if (state === 'equal') return data.when_equal?.evidence || [];
    if (state === 'losing') return data.when_losing?.evidence || [];
    return [];
  };

  const StateRow = ({ state, label, icon: Icon, iconColor, percentage, isDanger }) => {
    const evidence = getStateEvidence(state);
    const hasEvidence = evidence.length > 0;
    
    return (
      <div 
        className={`${hasEvidence ? 'cursor-pointer hover:bg-muted/30 rounded-lg p-2 -mx-2 transition-colors' : ''}`}
        onClick={() => hasEvidence && onShowEvidence(state, evidence)}
        data-testid={`win-state-${state}`}
      >
        <div className="flex justify-between text-sm mb-1">
          <span className="flex items-center gap-1">
            <Icon className={`w-3 h-3 ${iconColor}`} />
            {label}
            {hasEvidence && (
              <span className="text-xs text-muted-foreground ml-1">
                ({evidence.length} examples)
              </span>
            )}
          </span>
          <span className={isDanger ? 'text-red-500 font-bold' : ''}>
            {percentage}%
          </span>
        </div>
        <Progress 
          value={percentage} 
          className={`h-2 ${isDanger ? '[&>div]:bg-red-500' : `[&>div]:${iconColor.replace('text-', 'bg-')}`}`}
        />
      </div>
    );
  };

  return (
    <Card className="border-blue-500/20">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-blue-500" />
          When You Blunder
          <span className="text-xs text-muted-foreground font-normal ml-auto">Click to see examples</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-3">
          <StateRow 
            state="winning"
            label="When Winning"
            icon={TrendingUp}
            iconColor="text-green-500"
            percentage={data.when_winning.percentage}
            isDanger={data.danger_zone === 'winning'}
          />
          
          <StateRow 
            state="equal"
            label="When Equal"
            icon={Target}
            iconColor="text-yellow-500"
            percentage={data.when_equal.percentage}
            isDanger={data.danger_zone === 'equal'}
          />
          
          <StateRow 
            state="losing"
            label="When Losing"
            icon={TrendingDown}
            iconColor="text-orange-500"
            percentage={data.when_losing.percentage}
            isDanger={data.danger_zone === 'losing'}
          />
        </div>
        
        <div className="p-3 rounded-lg bg-muted/50 text-sm">
          {data.insight}
        </div>
      </CardContent>
    </Card>
  );
};

// Weakness ranking component - Your Weaknesses (Prioritized)
const WeaknessRanking = ({ data, onShowEvidence, onStartDrill }) => {
  if (!data || !data.ranking || data.ranking.length === 0) {
    return null;
  }

  const WeaknessCard = ({ weakness, rank, color, colorClass }) => {
    const evidence = weakness.evidence || [];
    const hasEvidence = evidence.length > 0;
    const trend = weakness.trend;
    
    const labels = {
      1: "#1 Rating Killer",
      2: "Secondary Weakness"
    };
    
    const icons = {
      1: Flame,
      2: AlertTriangle
    };
    
    const Icon = icons[rank] || AlertTriangle;
    
    return (
      <motion.div
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: (rank - 1) * 0.1 }}
      >
        <Card 
          className={`border-2 ${colorClass} cursor-pointer hover:border-opacity-50 transition-colors`}
          onClick={() => hasEvidence && onShowEvidence(weakness, evidence)}
          data-testid={`weakness-rank-${rank}`}
        >
          <CardContent className="py-5">
            <div className="flex items-start gap-4">
              <div className={`p-3 rounded-full ${color}/20`}>
                <Icon className={`w-6 h-6 ${color}`} />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <span className={`text-xs font-bold uppercase tracking-wider ${color}`}>
                    {labels[rank]}
                  </span>
                  <span className={`text-xs ${color}/80 bg-${color.replace('text-', '')}/20 px-2 py-0.5 rounded-full`}>
                    {weakness.frequency_pct}% of games
                  </span>
                  {hasEvidence && (
                    <span className="text-xs text-muted-foreground flex items-center gap-1">
                      <Eye className="w-3 h-3" />
                      {evidence.length} examples
                    </span>
                  )}
                </div>
                
                {trend && (
                  <div className="mb-2">
                    <TrendIndicator trend={trend} />
                  </div>
                )}
                
                <h3 className="text-lg font-bold mb-1">{weakness.label}</h3>
                <p className="text-sm text-muted-foreground mb-2">
                  {weakness.message}
                </p>
                <div className="flex items-center gap-4 text-xs text-muted-foreground mb-3">
                  <span>{formatTotalCpLoss(weakness.total_cp_loss)}</span>
                  <span>{weakness.occurrences} occurrences</span>
                </div>
                
                <div className="flex gap-2" onClick={e => e.stopPropagation()}>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="gap-1 text-xs"
                    onClick={() => onShowEvidence(weakness, evidence)}
                    disabled={!hasEvidence}
                  >
                    <Eye className="w-3 h-3" />
                    See Examples
                  </Button>
                  <Button 
                    size="sm" 
                    className={`gap-1 text-xs ${rank === 1 ? 'bg-red-500 hover:bg-red-600' : 'bg-amber-500 hover:bg-amber-600'}`}
                    onClick={() => onStartDrill(weakness.pattern, weakness.label)}
                  >
                    <Dumbbell className="w-3 h-3" />
                    Train This
                  </Button>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    );
  };

  return (
    <div className="space-y-4">
      {data.rating_killer && (
        <WeaknessCard 
          weakness={data.rating_killer} 
          rank={1} 
          color="text-red-500"
          colorClass="border-red-500/30 bg-gradient-to-r from-red-500/10 to-transparent"
        />
      )}

      {data.secondary_weakness && (
        <WeaknessCard 
          weakness={data.secondary_weakness} 
          rank={2} 
          color="text-amber-500"
          colorClass="border-amber-500/20"
        />
      )}
    </div>
  );
};

// ============================================
// NEW SECTION: Chess Fundamentals Assessment
// ============================================
const FundamentalsSection = ({ data, onViewGame }) => {
  if (!data?.has_data) {
    return null;
  }

  const fundamentalIcons = {
    positional_play: <Shield className="w-5 h-5" />,
    tactics: <Zap className="w-5 h-5" />,
    opening: <BookOpen className="w-5 h-5" />,
    endgame: <Crown className="w-5 h-5" />,
    time_management: <Clock className="w-5 h-5" />
  };

  const levelColors = {
    strong: "text-emerald-500",
    developing: "text-blue-500",
    needs_work: "text-amber-500",
    focus_area: "text-red-500"
  };

  const levelBgColors = {
    strong: "bg-emerald-500/10",
    developing: "bg-blue-500/10",
    needs_work: "bg-amber-500/10",
    focus_area: "bg-red-500/10"
  };

  return (
    <Card className="border-indigo-500/20" data-testid="fundamentals-section">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <Brain className="w-5 h-5 text-indigo-500" />
          Chess Fundamentals
          <span className="text-xs text-muted-foreground font-normal ml-auto">
            How you compare across key areas
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {data.fundamentals.map((fund) => (
          <div key={fund.key} className="group">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${levelBgColors[fund.level]}`}>
                  {fundamentalIcons[fund.key] || <Target className="w-5 h-5" />}
                </div>
                <div>
                  <p className="font-medium">{fund.name}</p>
                  <p className="text-xs text-muted-foreground">{fund.description}</p>
                </div>
              </div>
              <span className={`text-sm font-semibold ${levelColors[fund.level]}`}>
                {fund.score}%
              </span>
            </div>
            
            <Progress value={fund.score} className="h-2" />
            
            {(fund.level === "focus_area" || fund.level === "needs_work") && (
              <div className="mt-2 p-3 rounded-lg bg-muted/50">
                <p className="text-sm text-muted-foreground">
                  <AlertTriangle className="w-4 h-4 inline mr-1 text-amber-500" />
                  {fund.suggestions?.[0]}
                </p>
                {fund.tagged_games?.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    <span className="text-xs text-muted-foreground">Practice games:</span>
                    {fund.tagged_games.map((game, i) => (
                      <button
                        key={i}
                        onClick={() => onViewGame(game.game_id)}
                        className="text-xs px-2 py-1 rounded bg-muted hover:bg-accent transition-colors"
                      >
                        vs {game.opponent}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {data.strongest && data.weakest && (
          <div className="mt-4 pt-4 border-t border-border grid grid-cols-2 gap-4">
            <div className="p-3 rounded-lg bg-emerald-500/10">
              <p className="text-xs text-emerald-500 font-medium mb-1">Strongest Area</p>
              <p className="font-medium">{data.strongest.name}</p>
            </div>
            <div className="p-3 rounded-lg bg-red-500/10">
              <p className="text-xs text-red-500 font-medium mb-1">Focus Area</p>
              <p className="font-medium">{data.weakest.name}</p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// ============================================
// NEW SECTION: Rating Ceiling Assessment
// ============================================
const RatingCeilingSection = ({ data }) => {
  if (!data?.has_data) {
    return null;
  }

  const urgencyColors = {
    high: "border-l-red-500",
    medium: "border-l-amber-500",
    low: "border-l-emerald-500"
  };

  return (
    <Card className={`border-l-4 ${urgencyColors[data.urgency]}`} data-testid="rating-ceiling-section">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-blue-500" />
          Rating Ceiling Assessment
          <span className="text-xs text-muted-foreground font-normal ml-auto">
            You're not bad, you're unstable
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div className="text-center p-4 rounded-lg bg-muted/50">
            <p className="text-xs text-muted-foreground mb-1">Stable Level</p>
            <p className="text-2xl font-bold text-foreground">{data.stable_level}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {data.stable_games_count} clean games
            </p>
          </div>
          <div className="text-center p-4 rounded-lg bg-primary/10">
            <p className="text-xs text-muted-foreground mb-1">Demonstrated Peak</p>
            <p className="text-2xl font-bold text-primary">{data.peak_level}</p>
            <p className="text-xs text-muted-foreground mt-1">
              Top 30% ({data.peak_accuracy}% acc)
            </p>
          </div>
        </div>

        <div className="p-3 rounded-lg bg-muted/30 mb-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-muted-foreground">Performance Gap</span>
            <span className="font-bold">
              {data.gap > 0 ? (
                <span className="text-amber-500">+{data.gap} points</span>
              ) : (
                <span className="text-emerald-500">Consistent!</span>
              )}
            </span>
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-emerald-500 to-primary transition-all"
              style={{ width: `${Math.min(100, (data.stable_level / data.peak_level) * 100)}%` }}
            />
          </div>
        </div>

        {data.gap > 50 && (
          <div className="p-3 rounded-lg border border-amber-500/30 bg-amber-500/5">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-500 mt-0.5" />
              <div>
                <p className="font-medium text-amber-500">Gap Driver: {data.gap_driver}</p>
                <p className="text-sm text-muted-foreground mt-1">{data.gap_description}</p>
                <p className="text-sm mt-2 font-medium">{data.fix_suggestion}</p>
              </div>
            </div>
          </div>
        )}

        <p className="text-sm text-muted-foreground mt-4 text-center italic">
          {data.message}
        </p>
      </CardContent>
    </Card>
  );
};

// ============================================
// NEW SECTION: Opening Progress
// ============================================
const OpeningProgressSection = ({ data, onViewGame }) => {
  const [showColor, setShowColor] = useState("white");

  if (!data?.has_data) {
    return null;
  }

  const statusIcons = {
    working: <CheckCircle2 className="w-4 h-4 text-emerald-500" />,
    struggling: <XCircle className="w-4 h-4 text-red-500" />,
    error_prone: <AlertTriangle className="w-4 h-4 text-amber-500" />,
    needs_study: <BookOpen className="w-4 h-4 text-blue-500" />,
    neutral: <Minus className="w-4 h-4 text-muted-foreground" />
  };

  const currentData = showColor === "white" ? data.as_white : data.as_black;

  return (
    <Card className="border-purple-500/20" data-testid="opening-progress-section">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-purple-500" />
          Opening Progress
          <div className="flex gap-2 ml-auto">
            <button
              onClick={() => setShowColor("white")}
              className={`px-3 py-1 text-xs rounded-full transition-colors ${
                showColor === "white" 
                  ? "bg-primary text-primary-foreground" 
                  : "bg-muted hover:bg-accent"
              }`}
            >
              White ({data.as_white.total_games})
            </button>
            <button
              onClick={() => setShowColor("black")}
              className={`px-3 py-1 text-xs rounded-full transition-colors ${
                showColor === "black" 
                  ? "bg-primary text-primary-foreground" 
                  : "bg-muted hover:bg-accent"
              }`}
            >
              Black ({data.as_black.total_games})
            </button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {currentData.openings.map((opening, idx) => (
          <div 
            key={idx}
            className="p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                {statusIcons[opening.status]}
                <span className="font-medium">{opening.name}</span>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <span className="text-muted-foreground">{opening.games} games</span>
                <span className={
                  opening.win_rate >= 60 ? "text-emerald-500 font-semibold" :
                  opening.win_rate < 40 ? "text-red-500 font-semibold" :
                  "text-foreground"
                }>
                  {opening.win_rate}% WR
                </span>
              </div>
            </div>
            
            <div className="flex h-2 rounded-full overflow-hidden bg-muted">
              <div 
                className="bg-emerald-500 transition-all"
                style={{ width: `${(opening.wins / opening.games) * 100}%` }}
              />
              <div 
                className="bg-slate-400 transition-all"
                style={{ width: `${(opening.draws / opening.games) * 100}%` }}
              />
              <div 
                className="bg-red-500 transition-all"
                style={{ width: `${(opening.losses / opening.games) * 100}%` }}
              />
            </div>
            
            <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                {opening.wins}W
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-slate-400" />
                {opening.draws}D
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-red-500" />
                {opening.losses}L
              </span>
              {opening.avg_accuracy > 0 && (
                <span className="ml-auto">{opening.avg_accuracy}% avg acc</span>
              )}
            </div>
            
            {opening.suggestion && (
              <p className="text-xs text-muted-foreground mt-2 pl-4 border-l-2 border-primary/30">
                {opening.suggestion}
              </p>
            )}
          </div>
        ))}

        {(data.working_well?.length > 0 || data.needs_work?.length > 0) && (
          <div className="mt-4 pt-4 border-t border-border grid grid-cols-2 gap-4">
            {data.working_well?.length > 0 && (
              <div className="p-3 rounded-lg bg-emerald-500/10">
                <p className="text-xs text-emerald-500 font-medium mb-2">Working Well</p>
                <div className="space-y-1">
                  {data.working_well.slice(0, 2).map((o, i) => (
                    <p key={i} className="text-sm truncate">{o.name}</p>
                  ))}
                </div>
              </div>
            )}
            {data.needs_work?.length > 0 && (
              <div className="p-3 rounded-lg bg-red-500/10">
                <p className="text-xs text-red-500 font-medium mb-2">Needs Work</p>
                <div className="space-y-1">
                  {data.needs_work.slice(0, 2).map((o, i) => (
                    <p key={i} className="text-sm truncate">{o.name}</p>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// ============================================
// MAIN PAGE COMPONENT
// ============================================
// Before/After Coach Comparison Component
const CoachingComparison = ({ data, activeTab, onTabChange }) => {
  const { baseline, current_stats, progress, has_baseline, games_until_baseline, pattern_comparison } = data;
  
  // If no baseline yet
  if (!has_baseline) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-6"
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
                  {games_until_baseline > 0 
                    ? `${games_until_baseline} more games to analyze`
                    : 'Almost ready...'}
                </p>
              </div>
            </div>
            <Progress value={((10 - (games_until_baseline || 0)) / 10) * 100} className="h-2" />
            <p className="text-xs text-muted-foreground mt-3">
              We're learning your playing style to track your improvement.
            </p>
          </CardContent>
        </Card>
      </motion.div>
    );
  }

  if (!progress) return null;

  // Determine improvements and focus areas
  const getInsights = () => {
    const improving = [];
    const needsWork = [];

    if (progress.accuracy?.delta >= 3) {
      improving.push({ label: "Move Quality", detail: "Your moves are getting sharper" });
    } else if (progress.accuracy?.delta <= -3) {
      needsWork.push({ label: "Move Quality", detail: "Focus on calculating before moving" });
    }

    if (progress.blunders_per_game?.delta <= -0.5) {
      improving.push({ label: "Blunder Control", detail: "Making fewer game-losing mistakes" });
    } else if (progress.blunders_per_game?.delta >= 0.3) {
      needsWork.push({ label: "Blunder Control", detail: "Double-check before big moves" });
    }

    if (progress.win_rate?.delta >= 5) {
      improving.push({ label: "Winning More", detail: "Your results are improving" });
    } else if (progress.win_rate?.delta <= -5) {
      needsWork.push({ label: "Game Results", detail: "Focus on converting advantages" });
    }
    
    // Add pattern-based insights
    if (pattern_comparison?.weaknesses) {
      const fixed = pattern_comparison.weaknesses.filter(w => w.trend === 'fixed' || w.trend === 'improved');
      const regressed = pattern_comparison.weaknesses.filter(w => w.trend === 'regressed' || w.trend === 'new');
      
      fixed.forEach(w => {
        improving.push({ label: w.label, detail: `${w.trend === 'fixed' ? 'No longer an issue!' : `Improved by ${Math.abs(w.delta)}%`}` });
      });
      
      regressed.forEach(w => {
        needsWork.push({ label: w.label, detail: `${w.trend === 'new' ? 'New weakness detected' : `Increased by ${w.delta}%`}` });
      });
    }

    return { improving, needsWork };
  };

  const { improving, needsWork } = getInsights();
  const overallImproving = improving.length >= needsWork.length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-6"
    >
      <Card className="overflow-hidden">
        {/* Tabs */}
        <div className="flex border-b">
          <button
            onClick={() => onTabChange('before')}
            className={`flex-1 py-3 px-4 text-sm font-medium transition-colors ${
              activeTab === 'before' 
                ? 'bg-muted/50 border-b-2 border-amber-500 text-amber-500' 
                : 'text-muted-foreground hover:bg-muted/30'
            }`}
          >
            Before Coach
          </button>
          <button
            onClick={() => onTabChange('after')}
            className={`flex-1 py-3 px-4 text-sm font-medium transition-colors ${
              activeTab === 'after' 
                ? 'bg-muted/50 border-b-2 border-emerald-500 text-emerald-500' 
                : 'text-muted-foreground hover:bg-muted/30'
            }`}
          >
            After Coach
          </button>
          <button
            onClick={() => onTabChange('growth')}
            className={`flex-1 py-3 px-4 text-sm font-medium transition-colors ${
              activeTab === 'growth' 
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
                  Your first {baseline.games_analyzed} games
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
            </div>
          )}

          {/* After Coach Tab */}
          {activeTab === 'after' && current_stats && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 mb-4">
                <TrendingUp className="w-4 h-4 text-emerald-500" />
                <span className="text-sm text-muted-foreground">
                  Your last {current_stats.games_analyzed} games
                </span>
              </div>
              
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-4 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
                  <p className="text-xs text-muted-foreground mb-1">Accuracy</p>
                  <p className="text-2xl font-bold text-emerald-500">{current_stats.avg_accuracy}%</p>
                  {progress.accuracy?.delta !== 0 && (
                    <p className={`text-xs ${progress.accuracy.delta > 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                      {progress.accuracy.delta > 0 ? '+' : ''}{progress.accuracy.delta}%
                    </p>
                  )}
                </div>
                <div className="text-center p-4 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
                  <p className="text-xs text-muted-foreground mb-1">Blunders/Game</p>
                  <p className="text-2xl font-bold text-emerald-500">{current_stats.blunders_per_game}</p>
                  {progress.blunders_per_game?.delta !== 0 && (
                    <p className={`text-xs ${progress.blunders_per_game.delta < 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                      {progress.blunders_per_game.delta > 0 ? '+' : ''}{progress.blunders_per_game.delta}
                    </p>
                  )}
                </div>
                <div className="text-center p-4 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
                  <p className="text-xs text-muted-foreground mb-1">Win Rate</p>
                  <p className="text-2xl font-bold text-emerald-500">{current_stats.win_rate}%</p>
                  {progress.win_rate?.delta !== 0 && (
                    <p className={`text-xs ${progress.win_rate.delta > 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                      {progress.win_rate.delta > 0 ? '+' : ''}{progress.win_rate.delta}%
                    </p>
                  )}
                </div>
                <div className="text-center p-4 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
                  <p className="text-xs text-muted-foreground mb-1">Mistakes/Game</p>
                  <p className="text-2xl font-bold text-emerald-500">{current_stats.mistakes_per_game}</p>
                  {progress.mistakes_per_game?.delta !== 0 && (
                    <p className={`text-xs ${progress.mistakes_per_game.delta < 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                      {progress.mistakes_per_game.delta > 0 ? '+' : ''}{progress.mistakes_per_game.delta}
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Your Growth Tab */}
          {activeTab === 'growth' && (
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
                      {improving.slice(0, 4).map((item, idx) => (
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
                      {needsWork.slice(0, 4).map((item, idx) => (
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

const JourneyPage = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [journeyData, setJourneyData] = useState(null);
  
  // Lifted tab state for coordinating weakness/pattern display
  const [activeComparisonTab, setActiveComparisonTab] = useState('growth'); // 'before', 'after', 'growth'
  
  const [evidenceModal, setEvidenceModal] = useState({
    isOpen: false,
    title: "",
    subtitle: "",
    evidence: [],
    type: "pattern",
    state: null
  });
  
  const [drillMode, setDrillMode] = useState({
    active: false,
    pattern: null,
    patternLabel: ""
  });

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch(`${API}/journey/v2`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          setJourneyData(data);
        }
      } catch (err) {
        console.error("Failed to load journey data:", err);
        toast.error("Failed to load journey data");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);
  
  const handleShowWeaknessEvidence = (weakness, evidence) => {
    setEvidenceModal({
      isOpen: true,
      title: weakness.label,
      subtitle: weakness.message,
      evidence: evidence,
      type: "pattern",
      state: null
    });
  };
  
  const handleShowStateEvidence = (state, evidence) => {
    const stateLabels = {
      winning: "Blunders When Winning",
      equal: "Blunders When Equal",
      losing: "Blunders When Losing"
    };
    
    setEvidenceModal({
      isOpen: true,
      title: stateLabels[state],
      subtitle: `${evidence.length} positions where you blundered while ${state}`,
      evidence: evidence,
      type: "state",
      state: state
    });
  };
  
  const handleStartDrill = (pattern, patternLabel) => {
    setDrillMode({
      active: true,
      pattern: pattern,
      patternLabel: patternLabel
    });
  };

  const handleViewGame = (gameId) => {
    navigate(`/lab/${gameId}`);
  };
  
  // Get the appropriate patterns based on active tab
  const getActivePatterns = () => {
    if (activeComparisonTab === 'before') {
      return journeyData?.baseline_patterns;
    }
    return journeyData?.current_patterns;
  };
  
  // Transform pattern data for WeaknessRanking component
  const getWeaknessRankingData = () => {
    const patterns = getActivePatterns();
    if (!patterns?.weaknesses) return journeyData?.weakness_ranking;
    
    // Transform the patterns data to match expected weakness_ranking format
    const weaknesses = patterns.weaknesses.map((w, index) => ({
      rank: index + 1,
      pattern: w.id,
      label: w.label,
      message: w.description,
      severity: w.severity,
      occurrence_rate: w.occurrence_pct,
      total_games: w.total_games,
      occurrence_count: w.occurrence_count,
      pawns_lost: w.pawns_lost || 0,
      evidence: w.examples || [],
      trend: journeyData?.pattern_comparison?.weaknesses?.find(c => c.id === w.id)?.trend || null
    }));
    
    return {
      weaknesses,
      primary: weaknesses[0] || null,
      secondary: weaknesses[1] || null
    };
  };
  
  // Transform pattern data for WinStateAnalysis component
  const getWinStateData = () => {
    const patterns = getActivePatterns();
    if (!patterns?.blunder_context) return journeyData?.win_state;
    
    const bc = patterns.blunder_context;
    return {
      when_winning: {
        count: bc.when_winning?.count || 0,
        percentage: bc.when_winning?.percentage || 0,
        evidence: bc.when_winning?.examples || []
      },
      when_equal: {
        count: bc.when_equal?.count || 0,
        percentage: bc.when_equal?.percentage || 0,
        evidence: bc.when_equal?.examples || []
      },
      when_losing: {
        count: bc.when_losing?.count || 0,
        percentage: bc.when_losing?.percentage || 0,
        evidence: bc.when_losing?.examples || []
      },
      total_blunders: bc.total_blunders || 0,
      insight: bc.insight || ""
    };
  };

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </Layout>
    );
  }

  const gamesAnalyzed = journeyData?.games_analyzed || 0;
  
  if (drillMode.active) {
    return (
      <Layout user={user}>
        <div className="max-w-4xl mx-auto px-4 py-8">
          <DrillMode
            pattern={drillMode.pattern}
            patternLabel={drillMode.patternLabel}
            onComplete={() => setDrillMode({ active: false, pattern: null, patternLabel: "" })}
            onClose={() => setDrillMode({ active: false, pattern: null, patternLabel: "" })}
          />
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user}>
      <div className="max-w-5xl mx-auto px-4 py-8">
        
        {/* Header */}
        <motion.div 
          initial={{ opacity: 0, y: -10 }} 
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <h1 className="text-3xl font-bold mb-2">Your Chess Journey</h1>
          <p className="text-muted-foreground">
            Based on your last {gamesAnalyzed} analyzed games
          </p>
        </motion.div>

        {gamesAnalyzed < 5 ? (
          <Card className="border-2 border-dashed border-muted-foreground/20">
            <CardContent className="py-12 text-center">
              <Brain className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
              <h3 className="text-lg font-medium mb-2">Building Your Story</h3>
              <p className="text-muted-foreground mb-6">
                Analyze at least 5 games to see your chess journey
              </p>
              <Button onClick={() => navigate("/import")}>
                Import Games
              </Button>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Before/After Coach Comparison */}
            {journeyData?.progress && (
              <CoachingComparison data={journeyData} />
            )}
            
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            
            {/* LEFT COLUMN */}
            <div className="space-y-6">
              <h2 className="text-xl font-bold flex items-center gap-2">
                <Target className="w-5 h-5" />
                Your Weaknesses (Prioritized)
              </h2>
              
              <WeaknessRanking 
                data={journeyData?.weakness_ranking} 
                onShowEvidence={handleShowWeaknessEvidence}
                onStartDrill={handleStartDrill}
              />

              {/* Rating Ceiling Assessment */}
              <RatingCeilingSection data={journeyData?.rating_ceiling} />
            </div>

            {/* RIGHT COLUMN */}
            <div className="space-y-6">
              <h2 className="text-xl font-bold flex items-center gap-2">
                <BarChart3 className="w-5 h-5" />
                Pattern Analysis
              </h2>
              
              <WinStateAnalysis 
                data={journeyData?.win_state} 
                onShowEvidence={handleShowStateEvidence}
              />
              
              {/* Chess Fundamentals */}
              <FundamentalsSection 
                data={journeyData?.fundamentals} 
                onViewGame={handleViewGame}
              />
              
              {/* Opening Progress */}
              <OpeningProgressSection 
                data={journeyData?.opening_progress}
                onViewGame={handleViewGame}
              />
            </div>
          </div>
          </>
        )}

        {/* Navigation */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="flex justify-center gap-4 mt-8"
        >
          <Button 
            variant="outline" 
            onClick={() => navigate("/coach")}
          >
            ← Today's Focus
          </Button>
          <Button 
            onClick={() => navigate("/dashboard")}
            className="group"
          >
            Analyze Games
            <ChevronRight className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform" />
          </Button>
        </motion.div>
      </div>
      
      {/* Evidence Modal */}
      <EvidenceModal
        isOpen={evidenceModal.isOpen}
        onClose={() => setEvidenceModal({ ...evidenceModal, isOpen: false })}
        title={evidenceModal.title}
        subtitle={evidenceModal.subtitle}
        evidence={evidenceModal.evidence}
        type={evidenceModal.type}
        state={evidenceModal.state}
      />
    </Layout>
  );
};

export default JourneyPage;
