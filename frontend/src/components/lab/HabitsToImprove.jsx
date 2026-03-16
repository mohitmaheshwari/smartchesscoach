/**
 * HabitsToImprove - The Coach Assigns Homework
 * 
 * This is the Identity Engine output.
 * Shows patterns detected across games and training focus.
 * 
 * The most powerful section - connects games to improvement.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { API } from "@/App";
import {
  Brain,
  Target,
  TrendingUp,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Sparkles,
  BookOpen
} from "lucide-react";

const HabitsToImprove = ({ 
  patternContext,
  focusModule,
  labData,
  deepStrategy,
  onStartTraining,
  onNavigateToMove
}) => {
  const navigate = useNavigate();
  
  // Current game's opening stats from progress API
  const [openingStats, setOpeningStats] = useState(null);
  const [loadingProgress, setLoadingProgress] = useState(false);
  const [openingLibraryKey, setOpeningLibraryKey] = useState(null);
  
  // Get the opening from the current game
  const currentOpening = deepStrategy?.game?.opening || deepStrategy?.game?.opening_name;
  const currentEco = deepStrategy?.game?.eco;
  
  // Get opening performance from THIS game's analysis
  const openingPerformance = deepStrategy?.opening_performance;
  
  // Fetch opening progress to get overall stats for this opening
  useEffect(() => {
    const fetchProgress = async () => {
      if (!currentOpening) return;
      
      setLoadingProgress(true);
      try {
        const res = await fetch(`${API}/training/opening-progress`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          // Find this game's opening in the progress (case-insensitive match)
          const normalizedOpening = currentOpening.toLowerCase().replace(/[-_]/g, ' ');
          const thisOpening = data.progress?.find(p => {
            const progressName = (p.opening_name || '').toLowerCase().replace(/[-_]/g, ' ');
            return progressName.includes(normalizedOpening) || normalizedOpening.includes(progressName);
          });
          if (thisOpening) {
            setOpeningStats(thisOpening);
            // Check if it has a library key
            if (thisOpening.library_key) {
              setOpeningLibraryKey(thisOpening.library_key);
            }
          }
        }
        
        // Use the backend's intelligent matching endpoint instead of naive substring matching
        // This handles variations like "Giuoco Piano Game" -> "italian-game"
        const matchRes = await fetch(
          `${API}/openings/match?opening_name=${encodeURIComponent(currentOpening)}${currentEco ? `&eco=${encodeURIComponent(currentEco)}` : ''}`,
          { credentials: "include" }
        );
        if (matchRes.ok) {
          const matchData = await matchRes.json();
          if (matchData.found && matchData.library_key) {
            setOpeningLibraryKey(matchData.library_key);
          }
        }
      } catch (err) {
        console.error("Error fetching opening progress:", err);
      } finally {
        setLoadingProgress(false);
      }
    };
    fetchProgress();
  }, [currentOpening, currentEco]);

  // Extract pattern detected from this game - STRICT RULE: Must have cross-game evidence
  const getPatternDetected = () => {
    // Get cross-game occurrence data
    const history = patternContext?.history || {};
    const mostRecurring = history.most_recurring;
    const occurrenceCount = history.count || patternContext?.occurrence_count || 0;
    const gamesWithPattern = patternContext?.games_with_pattern || [];
    
    // STRICT RULE: Only show as "pattern" if we have cross-game evidence (2+ games)
    if (mostRecurring && occurrenceCount >= 2) {
      const patternLabel = mostRecurring.replace(/_/g, ' ');
      return {
        label: patternLabel,
        message: `This pattern appeared in ${occurrenceCount} of your recent games.`,
        hasEvidence: true,
        severity: occurrenceCount >= 5 ? "high" : occurrenceCount >= 3 ? "medium" : "low",
        gamesCount: occurrenceCount
      };
    }
    
    // Check summary for cross-game info (if it's a string mentioning multiple games)
    const summary = patternContext?.summary;
    if (typeof summary === 'string' && summary.includes("games")) {
      return {
        label: null,
        message: summary,
        hasEvidence: true,
        severity: "medium",
        gamesCount: null
      };
    }
    
    // From this game's critical moments - BUT mark as "potential" since it's one game only
    const moments = deepStrategy?.critical_moments || [];
    if (moments.length > 0) {
      const firstInsight = moments[0]?.insight;
      if (firstInsight?.pattern_to_remember) {
        return {
          label: null,
          message: firstInsight.pattern_to_remember,
          hasEvidence: false, // Only this game, not cross-game
          severity: "potential",
          gamesCount: 1
        };
      }
    }
    
    return null;
  };
  
  // Build training rule from pattern
  const getTrainingRule = () => {
    const pattern = patternContext?.history?.most_recurring;
    const insight = deepStrategy?.critical_moments?.[0]?.insight;
    
    // Specific rules based on pattern type
    if (pattern) {
      const patternLower = pattern.toLowerCase();
      
      if (patternLower.includes("tactical") || patternLower.includes("capture")) {
        return {
          title: "Before every move ask:",
          steps: [
            "What is my opponent threatening?",
            "Do I have a capture?",
            "Is anything hanging?"
          ]
        };
      }
      
      if (patternLower.includes("piece_safety") || patternLower.includes("hanging")) {
        return {
          title: "Before committing to a move:",
          steps: [
            "Is my move safe?",
            "What can opponent do next?",
            "Are all my pieces protected?"
          ]
        };
      }
      
      if (patternLower.includes("time") || patternLower.includes("blunder_when")) {
        return {
          title: "When ahead or under pressure:",
          steps: [
            "Slow down, don't rush",
            "Check for opponent threats",
            "Simplify if winning"
          ]
        };
      }
    }
    
    // From insight's ask_yourself
    if (insight?.ask_yourself) {
      return {
        title: "Before moving, ask yourself:",
        steps: [insight.ask_yourself]
      };
    }
    
    // Default rule
    return {
      title: "Before every move:",
      steps: [
        "Checks - Can I give check?",
        "Captures - Can I win material?",
        "Threats - What is opponent planning?"
      ]
    };
  };
  
  // Get training focus areas
  const getTrainingFocus = () => {
    const focus = [];
    
    // From focus module
    if (focusModule?.habit_name) {
      focus.push(focusModule.habit_name);
    }
    
    // From pattern context
    if (patternContext?.history?.most_recurring) {
      const pattern = patternContext.history.most_recurring.replace(/_/g, ' ');
      if (!focus.includes(pattern)) {
        focus.push(pattern);
      }
    }
    
    // From deep strategy themes
    const moments = deepStrategy?.critical_moments || [];
    moments.forEach(m => {
      const tags = m.tags || {};
      if (tags.tactical_theme && !focus.includes(tags.tactical_theme)) {
        focus.push(tags.tactical_theme.replace(/_/g, ' '));
      }
    });
    
    // Defaults based on blunder count
    if (focus.length === 0) {
      const blunders = labData?.blunders || 0;
      if (blunders > 0) {
        focus.push("Tactical awareness");
        focus.push("Threat detection");
      } else {
        focus.push("Position understanding");
      }
    }
    
    return focus.slice(0, 4);
  };
  
  const patternDetected = getPatternDetected();
  const trainingRule = getTrainingRule();
  const trainingFocus = getTrainingFocus();
  
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Brain className="w-5 h-5 text-violet-500" />
        <h3 className="font-semibold">Habits to Improve</h3>
      </div>
      
      {/* Pattern Detected - With cross-game evidence requirement */}
      {patternDetected && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <Card className={`${
            patternDetected.hasEvidence 
              ? patternDetected.severity === "high"
                ? "border-red-500/30 bg-red-500/5"
                : "border-violet-500/30 bg-violet-500/5"
              : "border-slate-500/30 bg-slate-500/5"
          }`}>
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <AlertTriangle className={`w-5 h-5 mt-0.5 flex-shrink-0 ${
                  patternDetected.hasEvidence 
                    ? patternDetected.severity === "high" 
                      ? "text-red-400" 
                      : "text-violet-400"
                    : "text-slate-400"
                }`} />
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <h4 className={`text-xs font-medium uppercase tracking-wide ${
                      patternDetected.hasEvidence 
                        ? patternDetected.severity === "high"
                          ? "text-red-400"
                          : "text-violet-400"
                        : "text-slate-400"
                    }`}>
                      {patternDetected.hasEvidence ? "Pattern Detected" : "Potential Pattern"}
                    </h4>
                    {patternDetected.hasEvidence && patternDetected.gamesCount && (
                      <Badge variant="outline" className={`text-xs ${
                        patternDetected.severity === "high" 
                          ? "border-red-500/50 text-red-300" 
                          : "border-violet-500/50 text-violet-300"
                      }`}>
                        {patternDetected.severity === "high" ? "High" : patternDetected.severity === "medium" ? "Medium" : "Low"} priority
                      </Badge>
                    )}
                  </div>
                  <p className={`text-sm ${
                    patternDetected.hasEvidence 
                      ? patternDetected.severity === "high"
                        ? "text-red-200"
                        : "text-violet-200"
                      : "text-slate-300"
                  }`}>
                    {patternDetected.message}
                  </p>
                  {!patternDetected.hasEvidence && (
                    <p className="text-xs text-slate-400 mt-2">
                      We'll track this across future games to confirm.
                    </p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
      
      {/* Training Rule */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <Card className="border-emerald-500/30 bg-emerald-500/5">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <Target className="w-5 h-5 text-emerald-400 mt-0.5 flex-shrink-0" />
              <div>
                <h4 className="text-xs font-medium text-emerald-400 uppercase tracking-wide mb-2">
                  Training Rule
                </h4>
                <p className="text-sm font-medium mb-2">
                  {trainingRule.title}
                </p>
                <ul className="space-y-1.5">
                  {trainingRule.steps.map((step, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                      <CheckCircle2 className="w-4 h-4 text-emerald-500 mt-0.5 flex-shrink-0" />
                      <span>{step}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>
      
      {/* Current Game's Opening Performance */}
      {currentOpening && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
        >
          <Card className={`${
            openingPerformance?.verdict === "poor" || openingPerformance?.verdict === "needs_work"
              ? "border-amber-500/30 bg-amber-500/5" 
              : openingPerformance?.verdict === "excellent"
              ? "border-green-500/30 bg-green-500/5"
              : "border-primary/30 bg-primary/5"
          }`}>
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-3">
                {openingPerformance?.verdict === "poor" || openingPerformance?.verdict === "needs_work" ? (
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                ) : openingPerformance?.verdict === "excellent" ? (
                  <CheckCircle2 className="w-4 h-4 text-green-400" />
                ) : (
                  <Target className="w-4 h-4 text-primary" />
                )}
                <h4 className={`text-xs font-medium uppercase tracking-wide ${
                  openingPerformance?.verdict === "poor" || openingPerformance?.verdict === "needs_work"
                    ? "text-amber-400" 
                    : openingPerformance?.verdict === "excellent"
                    ? "text-green-400"
                    : "text-primary"
                }`}>
                  Opening Phase
                </h4>
                {currentEco && (
                  <Badge variant="outline" className="text-xs ml-auto">
                    {currentEco}
                  </Badge>
                )}
              </div>
              
              {/* Opening name */}
              <div className={`p-3 rounded-lg mb-3 ${
                openingPerformance?.verdict === "poor" || openingPerformance?.verdict === "needs_work"
                  ? "bg-slate-800/50 border border-amber-500/20" 
                  : openingPerformance?.verdict === "excellent"
                  ? "bg-slate-800/50 border border-green-500/20"
                  : "bg-slate-800/50 border border-primary/20"
              }`}>
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full ${
                    openingPerformance?.verdict === "poor" || openingPerformance?.verdict === "needs_work"
                      ? "bg-amber-500" 
                      : openingPerformance?.verdict === "excellent"
                      ? "bg-green-500"
                      : "bg-primary"
                  }`} />
                  <span className="text-sm font-medium">{currentOpening}</span>
                </div>
              </div>
              
              {/* This game's opening performance */}
              {openingPerformance && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">This game:</span>
                    <span className={`font-medium capitalize ${
                      openingPerformance.verdict === "excellent" ? "text-green-400" :
                      openingPerformance.verdict === "good" ? "text-blue-400" :
                      openingPerformance.verdict === "needs_work" ? "text-amber-400" :
                      "text-red-400"
                    }`}>
                      {openingPerformance.verdict === "excellent" ? "Played Well" :
                       openingPerformance.verdict === "good" ? "Solid" :
                       openingPerformance.verdict === "needs_work" ? "Needs Work" :
                       "Struggled"}
                    </span>
                  </div>
                  
                  {openingPerformance.mistakes_in_opening > 0 && (
                    <p className="text-xs text-amber-400">
                      {openingPerformance.mistakes_in_opening} mistake{openingPerformance.mistakes_in_opening > 1 ? 's' : ''} in first {openingPerformance.opening_moves_analyzed} moves
                    </p>
                  )}
                  
                  {openingPerformance.first_mistake_details && (
                    <div 
                      className="p-2 rounded bg-red-500/10 border border-red-500/20 text-xs cursor-pointer hover:bg-red-500/20 transition-colors"
                      onClick={() => {
                        if (onNavigateToMove) {
                          onNavigateToMove(
                            openingPerformance.first_mistake_details.move_number,
                            openingPerformance.first_mistake_details.your_move,
                            openingPerformance.first_mistake_details.best_move
                          );
                        }
                      }}
                      data-testid="opening-mistake-link"
                    >
                      <span className="text-red-400 underline hover:no-underline">
                        Move {openingPerformance.first_mistake_details.move_number}:
                      </span>
                      <span className="text-muted-foreground ml-1">
                        You played <span className="text-foreground">{openingPerformance.first_mistake_details.your_move}</span>
                        {openingPerformance.first_mistake_details.best_move && (
                          <>, better was <span className="text-green-400">{openingPerformance.first_mistake_details.best_move}</span></>
                        )}
                      </span>
                      <ArrowRight className="w-3 h-3 inline ml-2 text-muted-foreground" />
                    </div>
                  )}
                  
                  {openingPerformance.verdict === "excellent" && (
                    <p className="text-xs text-green-400">
                      No mistakes in the opening - well played!
                    </p>
                  )}
                </div>
              )}
              
              {/* Overall stats for this opening */}
              {openingStats && (
                <div className="mt-3 pt-3 border-t border-border/30">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>Overall with this opening:</span>
                    <span className={
                      openingStats.real_win_rate < 40 ? "text-red-400" :
                      openingStats.real_win_rate >= 60 ? "text-green-400" : 
                      "text-foreground"
                    }>
                      {openingStats.real_win_rate?.toFixed(0)}% win rate ({openingStats.real_games} games)
                    </span>
                  </div>
                </div>
              )}
              
              {!openingStats && !loadingProgress && (
                <p className="text-xs text-muted-foreground mt-2">
                  First game with this opening
                </p>
              )}
              
              {/* Learn this opening button */}
              {openingLibraryKey && (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full mt-3"
                  onClick={() => {
                    // Pass the current game's opening mistake if available
                    const mistakeData = openingPerformance?.first_mistake_details ? {
                      gameId: deepStrategy?.game_id,
                      mistake: openingPerformance.first_mistake_details
                    } : null;
                    
                    navigate(`/openings/${openingLibraryKey}`, {
                      state: { currentGameMistake: mistakeData }
                    });
                  }}
                >
                  <BookOpen className="w-4 h-4 mr-2" />
                  Learn This Opening
                  <ArrowRight className="w-4 h-4 ml-auto" />
                </Button>
              )}
            </CardContent>
          </Card>
        </motion.div>
      )}
      
      {/* Training Focus */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <Card className="border-0 bg-slate-800/30">
          <CardContent className="p-4">
            <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">
              Training Focus For Your Next Games
            </h4>
            <div className="flex flex-wrap gap-2">
              {trainingFocus.map((focus, i) => (
                <Badge 
                  key={i} 
                  variant="secondary"
                  className="text-xs capitalize"
                >
                  {focus}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      </motion.div>
      
      {/* Start Training CTA */}
      {onStartTraining && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <Button 
            onClick={onStartTraining}
            className="w-full gap-2"
          >
            <Sparkles className="w-4 h-4" />
            Practice These Patterns
            <ArrowRight className="w-4 h-4" />
          </Button>
        </motion.div>
      )}
    </div>
  );
};

export default HabitsToImprove;
