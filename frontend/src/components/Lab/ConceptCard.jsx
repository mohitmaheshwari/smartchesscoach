/**
 * ConceptCard - Step 10 Theory Module Display
 * 
 * Shows the theory concept the user is missing.
 * Collapsed by default unless high-intensity failure.
 * 
 * One short paragraph. One rule. No essays.
 */

import { useState } from 'react';
import { BookOpen, ChevronDown, ChevronUp } from 'lucide-react';

const CATEGORY_COLORS = {
  tactical: { bg: 'bg-red-500/10', border: 'border-red-500/30', text: 'text-red-400' },
  conversion: { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-400' },
  endgame: { bg: 'bg-purple-500/10', border: 'border-purple-500/30', text: 'text-purple-400' },
  positional: { bg: 'bg-green-500/10', border: 'border-green-500/30', text: 'text-green-400' },
  opening: { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400' },
};

const ConceptCard = ({ moduleTrigger, defaultExpanded = false }) => {
  const [expanded, setExpanded] = useState(defaultExpanded);
  
  if (!moduleTrigger?.triggered) {
    return null;
  }
  
  const colors = CATEGORY_COLORS[moduleTrigger.category] || CATEGORY_COLORS.tactical;
  const isHighConfidence = moduleTrigger.confidence === 'high';
  
  return (
    <div className={`rounded-lg ${colors.bg} ${colors.border} border overflow-hidden`}>
      {/* Header - Always Visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-3 hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-2">
          <BookOpen className={`w-4 h-4 ${colors.text}`} />
          <span className={`text-sm font-medium ${colors.text}`}>
            {moduleTrigger.module_name}
          </span>
          {isHighConfidence && (
            <span className="px-1.5 py-0.5 text-[10px] font-bold bg-red-500/20 text-red-400 rounded">
              HIGH IMPACT
            </span>
          )}
        </div>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        )}
      </button>
      
      {/* Content - Collapsible */}
      {expanded && (
        <div className="px-3 pb-3 space-y-2">
          {/* Explanation */}
          <p className="text-sm text-muted-foreground">
            {moduleTrigger.explanation}
          </p>
          
          {/* Rule */}
          <div className="flex items-start gap-2 p-2 rounded bg-black/20">
            <span className={`text-xs font-bold ${colors.text}`}>Rule:</span>
            <span className="text-xs">{moduleTrigger.rule}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default ConceptCard;
