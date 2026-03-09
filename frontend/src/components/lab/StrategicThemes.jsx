/**
 * StrategicThemes - Positional Understanding
 * 
 * The coach zooms out and explains big-picture concepts.
 * Shows themes from this game in card format.
 * 
 * NO engine evaluation. Just strategic concepts.
 */

import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import {
  Crown,
  Shield,
  Swords,
  Target,
  Zap,
  Clock,
  Grid3X3,
  ArrowUpRight
} from "lucide-react";

// Map theme types to icons and colors
const THEME_CONFIG = {
  piece_activity: {
    icon: Zap,
    color: "text-amber-400",
    bgColor: "bg-amber-500/10",
    borderColor: "border-amber-500/30"
  },
  pawn_structure: {
    icon: Grid3X3,
    color: "text-blue-400",
    bgColor: "bg-blue-500/10",
    borderColor: "border-blue-500/30"
  },
  king_safety: {
    icon: Crown,
    color: "text-red-400",
    bgColor: "bg-red-500/10",
    borderColor: "border-red-500/30"
  },
  central_control: {
    icon: Target,
    color: "text-emerald-400",
    bgColor: "bg-emerald-500/10",
    borderColor: "border-emerald-500/30"
  },
  piece_coordination: {
    icon: Swords,
    color: "text-violet-400",
    bgColor: "bg-violet-500/10",
    borderColor: "border-violet-500/30"
  },
  development: {
    icon: ArrowUpRight,
    color: "text-cyan-400",
    bgColor: "bg-cyan-500/10",
    borderColor: "border-cyan-500/30"
  },
  time_management: {
    icon: Clock,
    color: "text-orange-400",
    bgColor: "bg-orange-500/10",
    borderColor: "border-orange-500/30"
  },
  defense: {
    icon: Shield,
    color: "text-slate-400",
    bgColor: "bg-slate-500/10",
    borderColor: "border-slate-500/30"
  }
};

const StrategicThemes = ({ 
  deepStrategy,
  labData,
  game
}) => {
  // Extract strategic themes from the analysis
  const extractThemes = () => {
    const themes = [];
    
    // From deep strategy lesson
    const lesson = deepStrategy?.lesson;
    if (lesson) {
      if (lesson.main_strategic_theme) {
        themes.push({
          type: "central_control",
          title: lesson.main_strategic_theme,
          description: lesson.strategic_explanation || "A key theme in this game.",
          source: "lesson"
        });
      }
    }
    
    // From critical moments - extract unique strategic themes
    const criticalMoments = deepStrategy?.critical_moments || [];
    const seenThemes = new Set();
    
    criticalMoments.forEach(moment => {
      const insight = moment.insight || {};
      const tags = moment.tags || {};
      
      // Check for piece activity issues
      if (insight.what_you_missed?.toLowerCase().includes("inactive") ||
          insight.what_you_missed?.toLowerCase().includes("rook") ||
          tags.positional_concepts?.includes("piece_activity")) {
        if (!seenThemes.has("piece_activity")) {
          seenThemes.add("piece_activity");
          themes.push({
            type: "piece_activity",
            title: "Piece Activity",
            description: insight.what_you_missed || "Improving your least active piece can strengthen your position.",
            source: "moment"
          });
        }
      }
      
      // Check for pawn structure issues
      if (insight.what_you_missed?.toLowerCase().includes("pawn") ||
          insight.what_you_missed?.toLowerCase().includes("weakness") ||
          tags.positional_concepts?.includes("pawn_structure")) {
        if (!seenThemes.has("pawn_structure")) {
          seenThemes.add("pawn_structure");
          themes.push({
            type: "pawn_structure",
            title: "Pawn Structure",
            description: insight.what_you_missed || "Pawn moves create permanent weaknesses. Think twice before pushing.",
            source: "moment"
          });
        }
      }
      
      // Check for king safety issues
      if (insight.what_you_missed?.toLowerCase().includes("king") ||
          insight.pattern_to_remember?.toLowerCase().includes("king") ||
          tags.tactical_theme === "king_attack") {
        if (!seenThemes.has("king_safety")) {
          seenThemes.add("king_safety");
          themes.push({
            type: "king_safety",
            title: "King Safety",
            description: insight.what_you_missed || "A safe king is a happy king. Don't neglect your monarch.",
            source: "moment"
          });
        }
      }
      
      // Check for central control
      if (insight.what_best_move_achieves?.toLowerCase().includes("center") ||
          insight.what_best_move_achieves?.toLowerCase().includes("central") ||
          tags.positional_concepts?.includes("central_control")) {
        if (!seenThemes.has("central_control")) {
          seenThemes.add("central_control");
          themes.push({
            type: "central_control",
            title: "Central Control",
            description: insight.what_best_move_achieves || "Control the center to control the game.",
            source: "moment"
          });
        }
      }
    });
    
    // If we found few themes, add generic strategic observation
    if (themes.length < 2) {
      const blunders = labData?.blunders || 0;
      const mistakes = labData?.mistakes || 0;
      
      if (blunders + mistakes > 0) {
        // Add a defensive theme
        if (!seenThemes.has("defense")) {
          themes.push({
            type: "defense",
            title: "Defensive Awareness",
            description: "Before attacking, always check what your opponent is threatening.",
            source: "general"
          });
        }
      }
    }
    
    return themes.slice(0, 4); // Max 4 themes
  };
  
  const themes = extractThemes();
  
  if (themes.length === 0) {
    return null;
  }
  
  return (
    <div className="space-y-4">
      <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
        Strategic Themes From This Game
      </h3>
      
      <div className="grid gap-3">
        {themes.map((theme, idx) => {
          const config = THEME_CONFIG[theme.type] || THEME_CONFIG.defense;
          const Icon = config.icon;
          
          return (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.1 }}
            >
              <Card className={`border ${config.borderColor} ${config.bgColor}`}>
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <div className={`w-10 h-10 rounded-lg ${config.bgColor} flex items-center justify-center flex-shrink-0`}>
                      <Icon className={`w-5 h-5 ${config.color}`} />
                    </div>
                    <div>
                      <h4 className={`font-medium ${config.color} mb-1`}>
                        {theme.title}
                      </h4>
                      <p className="text-sm text-muted-foreground leading-relaxed">
                        {theme.description}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
};

export default StrategicThemes;
