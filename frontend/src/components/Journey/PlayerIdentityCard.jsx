/**
 * PlayerIdentityCard
 * 
 * A sophisticated identity component that feels:
 * - Intelligent
 * - Personal
 * - Sharp
 * - Emotionally accurate
 * 
 * Collapsed: Powerful 2-3 line summary
 * Expanded: 4 structured interpretation sections
 */

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Brain, ChevronDown, ChevronUp, Sparkles } from "lucide-react";

const PlayerIdentityCard = ({ identity }) => {
  const [expanded, setExpanded] = useState(false);

  if (!identity?.has_identity) {
    return (
      <Card className="border-dashed" data-testid="player-identity">
        <CardContent className="py-8 text-center">
          <Brain className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-muted-foreground">{identity?.collapsed_summary || "Analyze more games to build your playing identity."}</p>
          {identity?.minimum_required && (
            <p className="text-sm text-muted-foreground mt-2">
              {identity.games_analyzed || 0} / {identity.minimum_required} games analyzed
            </p>
          )}
        </CardContent>
      </Card>
    );
  }

  const { collapsed_summary, expanded: sections, confidence, can_expand } = identity;

  return (
    <Card data-testid="player-identity">
      {/* COLLAPSED STATE - Always Visible */}
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
              <Brain className="w-5 h-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-base">Your Playing Identity</CardTitle>
              {confidence && (
                <p className="text-xs text-muted-foreground">
                  {confidence.label} • {identity.games_analyzed} games
                </p>
              )}
            </div>
          </div>
          {can_expand && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-muted-foreground hover:text-foreground transition-colors p-1"
              aria-label={expanded ? "Collapse" : "Expand"}
            >
              {expanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
            </button>
          )}
        </div>
      </CardHeader>
      
      <CardContent className="pt-0">
        {/* Summary - The Hook */}
        <p className="text-sm leading-relaxed text-foreground/90">
          {collapsed_summary}
        </p>
        
        {can_expand && !expanded && (
          <button
            onClick={() => setExpanded(true)}
            className="text-sm text-primary hover:text-primary/80 mt-3 flex items-center gap-1"
          >
            View Detailed Breakdown
            <ChevronDown className="w-4 h-4" />
          </button>
        )}
        
        {/* EXPANDED STATE */}
        <AnimatePresence>
          {expanded && sections && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <div className="mt-6 space-y-5 border-t border-border pt-5">
                {/* Section 1: Consistency Profile */}
                <IdentitySection
                  title={sections.consistency.title}
                  label={sections.consistency.label}
                  explanation={sections.consistency.explanation}
                />
                
                {/* Section 2: Primary Error Driver */}
                <IdentitySection
                  title={sections.main_leak.title}
                  label={sections.main_leak.label}
                  explanation={sections.main_leak.explanation}
                  highlight
                />
                
                {/* Section 3: Phase Vulnerability */}
                <IdentitySection
                  title={sections.phase_vulnerability.title}
                  label={sections.phase_vulnerability.label}
                  explanation={sections.phase_vulnerability.explanation}
                />
                
                {/* Section 4: Risk Style */}
                <IdentitySection
                  title={sections.playing_style.title}
                  label={sections.playing_style.label}
                  explanation={sections.playing_style.explanation}
                />
              </div>
              
              <button
                onClick={() => setExpanded(false)}
                className="text-sm text-muted-foreground hover:text-foreground mt-4 flex items-center gap-1"
              >
                <ChevronUp className="w-4 h-4" />
                Collapse
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  );
};

/**
 * Individual identity section component
 */
const IdentitySection = ({ title, label, explanation, highlight = false }) => {
  return (
    <div className={`space-y-1 ${highlight ? "pl-3 border-l-2 border-primary" : ""}`}>
      <p className="text-xs text-muted-foreground uppercase tracking-wider">{title}</p>
      <p className="font-semibold text-foreground">{label}</p>
      <p className="text-sm text-muted-foreground leading-relaxed">{explanation}</p>
    </div>
  );
};

export default PlayerIdentityCard;
