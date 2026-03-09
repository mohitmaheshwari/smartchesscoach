/**
 * HabitsToImprove - The Coach Assigns Homework
 * 
 * This is the Identity Engine output.
 * Shows patterns detected across games and training focus.
 * 
 * The most powerful section - connects games to improvement.
 */

import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Brain,
  Target,
  TrendingUp,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Sparkles
} from "lucide-react";

const HabitsToImprove = ({ 
  patternContext,
  focusModule,
  labData,
  deepStrategy,
  onStartTraining
}) => {
  // Extract pattern detected from this game
  const getPatternDetected = () => {
    // From pattern context
    if (patternContext?.summary) {
      return patternContext.summary;
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
