/**
 * OneThingFix - Step 10 Lab Page Core Component
 * 
 * The single most important element on the Lab page.
 * Large. Bold. Non-negotiable.
 * 
 * Shows:
 * - "If you fix only one thing" message
 * - Evidence (move number + cp loss)
 * - Rule to follow
 */

import { Brain, Target, ChevronRight } from 'lucide-react';

const OneThingFix = ({ 
  coreLesson, 
  moduleTrigger, 
  biggestSwing,
  onMoveClick 
}) => {
  // Determine what to show
  const hasModule = moduleTrigger?.triggered;
  const hasLesson = coreLesson?.lesson && coreLesson?.pattern !== "clean_game";
  
  // If no lesson and no module, show nothing
  if (!hasLesson && !hasModule) {
    return null;
  }
  
  // Determine the main message
  let mainMessage = "";
  let rule = "";
  let evidenceMove = null;
  let evidenceCp = 0;
  
  if (hasModule) {
    // Use module trigger data
    mainMessage = coreLesson?.lesson || moduleTrigger.explanation;
    rule = moduleTrigger.rule;
    evidenceMove = moduleTrigger.evidence_move;
    evidenceCp = moduleTrigger.evidence_cp_loss || 0;
  } else if (hasLesson) {
    // Use core lesson data
    mainMessage = coreLesson.lesson;
    rule = coreLesson.behavioral_fix || "";
    
    // Get evidence from biggest swing
    if (biggestSwing) {
      evidenceMove = biggestSwing.move_number;
      evidenceCp = biggestSwing.cp_loss || 0;
    }
  }
  
  return (
    <div className="p-5 rounded-xl bg-gradient-to-br from-amber-500/10 to-orange-500/10 border-2 border-amber-500/30">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <div className="p-2 rounded-lg bg-amber-500/20">
          <Brain className="w-5 h-5 text-amber-400" />
        </div>
        <span className="text-sm font-bold uppercase tracking-wider text-amber-400">
          If You Fix Only One Thing
        </span>
      </div>
      
      {/* Main Message */}
      <h2 className="text-lg font-bold mb-3 leading-snug">
        {mainMessage}
      </h2>
      
      {/* Evidence */}
      {evidenceMove && (
        <button
          onClick={() => onMoveClick && onMoveClick(evidenceMove)}
          className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors mb-3"
        >
          <Target className="w-4 h-4 text-red-400" />
          <span>
            Evidence: Move {evidenceMove}
            {evidenceCp > 0 && (
              <span className="text-red-400 ml-1">
                (lost {(evidenceCp / 100).toFixed(1)} pawns)
              </span>
            )}
          </span>
          <ChevronRight className="w-3 h-3" />
        </button>
      )}
      
      {/* Rule */}
      {rule && (
        <div className="flex items-start gap-2 p-3 rounded-lg bg-black/20 border border-amber-500/20">
          <span className="text-amber-400 font-bold text-sm">Rule:</span>
          <span className="text-sm">{rule}</span>
        </div>
      )}
    </div>
  );
};

export default OneThingFix;
