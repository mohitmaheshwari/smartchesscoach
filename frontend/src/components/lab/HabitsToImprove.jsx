/**
 * HabitsToImprove - The Coach Assigns Homework
 * 
 * This is the Identity Engine output.
 * Shows patterns detected across games and training focus.
 * 
 * The most powerful section - connects games to improvement.
 */

import { useState, useEffect } from "react";
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
  BookOpen,
  ChevronDown,
  ChevronUp
} from "lucide-react";

const HabitsToImprove = ({ 
  patternContext,
  focusModule,
  labData,
  deepStrategy,
  onStartTraining
}) => {
  // Opening progress state
  const [openingProgress, setOpeningProgress] = useState(null);
  const [loadingProgress, setLoadingProgress] = useState(false);
  const [showAllOpenings, setShowAllOpenings] = useState(false);
  
  // Fetch opening progress on mount
  useEffect(() => {
    const fetchProgress = async () => {
      setLoadingProgress(true);
      try {
        const res = await fetch(`${API}/training/opening-progress`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          setOpeningProgress(data);
        }
      } catch (err) {
        console.error("Error fetching opening progress:", err);
      } finally {
        setLoadingProgress(false);
      }
    };
    fetchProgress();
  }, []);

  // Extract pattern detected from this game
  const getPatternDetected = () => {
    // From pattern context - check if summary is a string or object
    if (patternContext?.summary) {
      const summary = patternContext.summary;
      // If it's an object with coach_summary, use that
      if (typeof summary === 'object' && summary.coach_summary) {
        return summary.coach_summary;
      }
      // If it's a string, use it directly
      if (typeof summary === 'string') {
        return summary;
      }
      // If it has dominant_pattern
      if (typeof summary === 'object' && summary.dominant_pattern) {
        return `Your main pattern this game: ${summary.dominant_label || summary.dominant_pattern.replace(/_/g, ' ')}`;
      }
    }
    
    // From recurring patterns
    const mostRecurring = patternContext?.history?.most_recurring;
    if (mostRecurring) {
      const count = patternContext?.history?.count || 3;
      return `You've made ${mostRecurring.replace(/_/g, ' ')} mistakes in ${count} recent games.`;
    }
    
    // From this game's critical moments
    const moments = deepStrategy?.critical_moments || [];
    if (moments.length > 0) {
      const firstInsight = moments[0]?.insight;
      if (firstInsight?.pattern_to_remember) {
        return `This game revealed a pattern: ${firstInsight.pattern_to_remember}`;
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
      
      {/* Pattern Detected */}
      {patternDetected && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <Card className="border-violet-500/30 bg-violet-500/5">
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-violet-400 mt-0.5 flex-shrink-0" />
                <div>
                  <h4 className="text-xs font-medium text-violet-400 uppercase tracking-wide mb-1">
                    Pattern Detected
                  </h4>
                  <p className="text-sm text-violet-200">
                    {patternDetected}
                  </p>
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
      
      {/* Opening Progress Section */}
      {openingProgress && openingProgress.progress?.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
        >
          <Card className="border-primary/30 bg-primary/5">
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <BookOpen className="w-5 h-5 text-primary" />
                  <h4 className="text-xs font-medium text-primary uppercase tracking-wide">
                    Opening Progress
                  </h4>
                </div>
                <div className="flex gap-2 text-xs text-muted-foreground">
                  <span>{openingProgress.total_taught} learned</span>
                  {openingProgress.needs_attention > 0 && (
                    <Badge variant="destructive" className="text-xs h-5">
                      {openingProgress.needs_attention} needs work
                    </Badge>
                  )}
                </div>
              </div>
              
              <div className="space-y-2">
                {openingProgress.progress
                  .slice(0, showAllOpenings ? undefined : 3)
                  .map((opening, i) => (
                    <div 
                      key={i}
                      className={`flex items-center justify-between p-2 rounded-lg ${
                        opening.needs_work ? 'bg-red-500/10 border border-red-500/20' : 'bg-slate-800/30'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${
                          opening.mastery_level === 'mastered' ? 'bg-green-500' :
                          opening.mastery_level === 'practiced' ? 'bg-blue-500' :
                          opening.mastery_level === 'learning' ? 'bg-amber-500' :
                          opening.mastery_level === 'introduced' ? 'bg-purple-500' :
                          'bg-gray-500'
                        }`} />
                        <div className="flex flex-col">
                          <span className="text-sm font-medium">{opening.opening_name}</span>
                          {opening.dominant_loss_phase && (
                            <span className="text-xs text-red-400">
                              Loses in {opening.dominant_loss_phase}
                            </span>
                          )}
                        </div>
                        {!opening.coach_taught && (
                          <Badge variant="outline" className="text-xs h-4 px-1">
                            Not learned
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-xs text-muted-foreground">
                        {opening.real_games > 0 && (
                          <span className={opening.real_win_rate < 50 ? 'text-red-400' : 'text-green-400'}>
                            {opening.real_win_rate.toFixed(0)}% win
                          </span>
                        )}
                        <span>{opening.real_games} games</span>
                        <Badge variant="secondary" className="text-xs h-5 capitalize">
                          {opening.mastery_level}
                        </Badge>
                      </div>
                    </div>
                  ))}
              </div>
              
              {openingProgress.progress.length > 3 && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full mt-2 text-xs"
                  onClick={() => setShowAllOpenings(!showAllOpenings)}
                >
                  {showAllOpenings ? (
                    <>Show Less <ChevronUp className="w-3 h-3 ml-1" /></>
                  ) : (
                    <>Show All ({openingProgress.progress.length}) <ChevronDown className="w-3 h-3 ml-1" /></>
                  )}
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
