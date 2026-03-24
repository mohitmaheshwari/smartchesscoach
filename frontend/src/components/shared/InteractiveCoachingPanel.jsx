/**
 * Interactive Coaching Panel - The REAL coaching experience
 * 
 * This replaces the simple feedback card with a TRUE coaching conversation:
 * 
 * 1. AFTER USER MOVES:
 *    - Feedback on user's move (good/bad)
 *    - If mistake: What went wrong, what was better
 * 
 * 2. AFTER COACH MOVES:
 *    - Coach EXPLAINS their move and plan
 *    - What threats does this create?
 *    - What should user watch out for?
 * 
 * 3. BEFORE USER'S NEXT MOVE:
 *    - Guiding question: "What's your plan here?"
 *    - Hint if user is stuck
 * 
 * This creates a DIALOGUE, not just move evaluation.
 */

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  AlertTriangle,
  CheckCircle2,
  Lightbulb,
  GraduationCap,
  Trophy,
  MessageCircle,
  Eye,
  Target,
  Swords,
  HelpCircle,
  ChevronRight,
  Sparkles
} from "lucide-react";

// ═══════════════════════════════════════════════════════════════════
// MAIN INTERACTIVE COACHING PANEL
// ═══════════════════════════════════════════════════════════════════

const InteractiveCoachingPanel = ({
  userMoveCoaching,      // Coaching for user's last move
  coachMoveCoaching,     // Coaching for coach's last move  
  isUserTurn,            // Is it currently user's turn?
  onShowMove,            // Show a move on the board
  onAcknowledge,         // "I understand" click
  acknowledgedConcepts,  // Set of acknowledged concept IDs
  onAskCoach,            // User asks coach a question
  isCoachThinking        // Coach is processing
}) => {
  const [expandedSection, setExpandedSection] = useState(null);
  
  return (
    <div className="space-y-3" data-testid="interactive-coaching-panel">
      {/* Coach is thinking indicator */}
      {isCoachThinking && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-zinc-800/50 border border-zinc-700/50">
          <div className="animate-pulse">
            <Sparkles className="w-4 h-4 text-amber-400" />
          </div>
          <span className="text-sm text-zinc-400">Coach is analyzing...</span>
        </div>
      )}
      
      {/* SECTION 1: Feedback on YOUR move */}
      {userMoveCoaching && !isCoachThinking && (
        <UserMoveSection 
          coaching={userMoveCoaching}
          onShowMove={onShowMove}
          onAcknowledge={onAcknowledge}
          isAcknowledged={acknowledgedConcepts?.has(userMoveCoaching.concept_id)}
          expanded={expandedSection === 'user'}
          onToggle={() => setExpandedSection(expandedSection === 'user' ? null : 'user')}
        />
      )}
      
      {/* SECTION 2: Coach's move explanation */}
      {coachMoveCoaching && !isCoachThinking && (
        <CoachMoveSection 
          coaching={coachMoveCoaching}
          onShowMove={onShowMove}
          expanded={expandedSection === 'coach'}
          onToggle={() => setExpandedSection(expandedSection === 'coach' ? null : 'coach')}
        />
      )}
      
      {/* SECTION 3: Your turn - What's your plan? */}
      {isUserTurn && !isCoachThinking && (
        <YourTurnSection 
          threats={coachMoveCoaching?.threats}
          hint={coachMoveCoaching?.hint_for_user}
          onAskCoach={onAskCoach}
        />
      )}
    </div>
  );
};


// ═══════════════════════════════════════════════════════════════════
// USER MOVE SECTION - Feedback on user's move
// ═══════════════════════════════════════════════════════════════════

const UserMoveSection = ({ 
  coaching, 
  onShowMove, 
  onAcknowledge,
  isAcknowledged,
  expanded,
  onToggle 
}) => {
  if (!coaching) return null;
  
  const severity = coaching.severity || "good";
  const isGood = ["good", "great", "brilliant", "best"].includes(severity);
  const isBad = ["inaccuracy", "mistake", "blunder"].includes(severity);
  
  return (
    <div className={`rounded-xl border overflow-hidden ${
      isGood ? 'bg-emerald-500/5 border-emerald-500/20' :
      isBad ? 'bg-red-500/5 border-red-500/20' :
      'bg-zinc-800/50 border-zinc-700/50'
    }`}>
      {/* Header - Always visible */}
      <div 
        className={`px-4 py-3 cursor-pointer flex items-center justify-between ${
          isGood ? 'hover:bg-emerald-500/10' :
          isBad ? 'hover:bg-red-500/10' :
          'hover:bg-zinc-700/50'
        }`}
        onClick={onToggle}
      >
        <div className="flex items-center gap-3">
          <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
            isGood ? 'bg-emerald-500/20' : isBad ? 'bg-red-500/20' : 'bg-zinc-700'
          }`}>
            {isGood ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> :
             isBad ? <AlertTriangle className="w-4 h-4 text-red-400" /> :
             <Target className="w-4 h-4 text-zinc-400" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-zinc-500 uppercase tracking-wide">You played</span>
              <span className="font-mono font-bold text-white">{coaching.move_san}</span>
              <Badge variant="outline" className={`text-xs ${
                isGood ? 'text-emerald-400 border-emerald-500/30' :
                isBad ? 'text-red-400 border-red-500/30' :
                'text-zinc-400 border-zinc-500/30'
              }`}>
                {severity}
              </Badge>
            </div>
            <p className="text-sm text-zinc-400 mt-0.5">{coaching.narrative}</p>
          </div>
        </div>
        <ChevronRight className={`w-4 h-4 text-zinc-500 transition-transform ${expanded ? 'rotate-90' : ''}`} />
      </div>
      
      {/* Expanded content */}
      {expanded && isBad && (
        <div className="px-4 pb-4 space-y-3 border-t border-zinc-700/50 pt-3">
          {/* What went wrong */}
          {coaching.consequence && (
            <div className="bg-red-500/10 rounded-lg p-3">
              <p className="text-xs text-red-400 mb-1 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" /> What happens
              </p>
              <p className="text-sm text-white">{coaching.consequence}</p>
            </div>
          )}
          
          {/* Better move */}
          {coaching.better_approach && (
            <div className="bg-emerald-500/10 rounded-lg p-3">
              <p className="text-xs text-emerald-400 mb-1 flex items-center gap-1">
                <Lightbulb className="w-3 h-3" /> Better idea
              </p>
              <p className="text-sm text-white">{coaching.better_approach}</p>
            </div>
          )}
          
          {/* Candidate moves */}
          {coaching.candidate_moves?.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs text-blue-400 flex items-center gap-1">
                <Target className="w-3 h-3" /> Alternative moves
              </p>
              {coaching.candidate_moves.map((c, i) => (
                <button
                  key={i}
                  className="w-full text-left p-2 rounded bg-zinc-800/50 hover:bg-zinc-700/50 flex items-center gap-2"
                  onClick={() => onShowMove?.(c.move)}
                >
                  <span className={`font-mono font-bold px-2 py-0.5 rounded ${
                    c.is_best ? 'bg-emerald-500/20 text-emerald-400' : 'bg-blue-500/20 text-blue-400'
                  }`}>
                    {c.move}
                  </span>
                  <span className="text-sm text-zinc-300">{c.idea}</span>
                  {c.is_best && <Trophy className="w-3 h-3 text-emerald-400 ml-auto" />}
                </button>
              ))}
            </div>
          )}
          
          {/* Golden rule */}
          {coaching.transferable_learning && (
            <div className="bg-amber-500/10 rounded-lg p-3 border border-amber-500/30">
              <div className="flex items-center gap-2 mb-1">
                <GraduationCap className="w-4 h-4 text-amber-400" />
                <p className="text-xs font-semibold text-amber-400">Remember this!</p>
              </div>
              <p className="text-sm text-white">{coaching.transferable_learning}</p>
              
              {!isAcknowledged && coaching.concept_id && onAcknowledge && (
                <Button
                  size="sm"
                  variant="outline"
                  className="w-full mt-2 border-amber-500/30 text-amber-400 hover:bg-amber-500/10"
                  onClick={() => onAcknowledge(coaching.concept_id)}
                >
                  <CheckCircle2 className="w-3 h-3 mr-2" />
                  I understand
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};


// ═══════════════════════════════════════════════════════════════════
// COACH MOVE SECTION - Explains what coach is doing
// ═══════════════════════════════════════════════════════════════════

const CoachMoveSection = ({ coaching, onShowMove, expanded, onToggle }) => {
  if (!coaching) return null;
  
  return (
    <div className="rounded-xl border bg-blue-500/5 border-blue-500/20 overflow-hidden">
      {/* Header */}
      <div 
        className="px-4 py-3 cursor-pointer flex items-center justify-between hover:bg-blue-500/10"
        onClick={onToggle}
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center">
            <MessageCircle className="w-4 h-4 text-blue-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-zinc-500 uppercase tracking-wide">Coach plays</span>
              <span className="font-mono font-bold text-white">{coaching.move_san}</span>
            </div>
            <p className="text-sm text-blue-300 mt-0.5">{coaching.explanation || "Let me show you something..."}</p>
          </div>
        </div>
        <ChevronRight className={`w-4 h-4 text-zinc-500 transition-transform ${expanded ? 'rotate-90' : ''}`} />
      </div>
      
      {/* Expanded content */}
      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-blue-500/20 pt-3">
          {/* Coach's plan */}
          {coaching.plan && (
            <div className="bg-blue-500/10 rounded-lg p-3">
              <p className="text-xs text-blue-400 mb-1 flex items-center gap-1">
                <Target className="w-3 h-3" /> My plan
              </p>
              <p className="text-sm text-white">{coaching.plan}</p>
            </div>
          )}
          
          {/* Threats created */}
          {coaching.threats?.length > 0 && (
            <div className="bg-orange-500/10 rounded-lg p-3">
              <p className="text-xs text-orange-400 mb-1 flex items-center gap-1">
                <Swords className="w-3 h-3" /> Watch out!
              </p>
              <ul className="text-sm text-white space-y-1">
                {coaching.threats.map((threat, i) => (
                  <li key={i} className="flex items-center gap-2">
                    <span className="w-1 h-1 rounded-full bg-orange-400" />
                    {threat}
                  </li>
                ))}
              </ul>
            </div>
          )}
          
          {/* Teaching moment */}
          {coaching.teaching_point && (
            <div className="bg-purple-500/10 rounded-lg p-3 border border-purple-500/30">
              <p className="text-xs text-purple-400 mb-1 flex items-center gap-1">
                <GraduationCap className="w-3 h-3" /> Why I played this
              </p>
              <p className="text-sm text-white">{coaching.teaching_point}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};


// ═══════════════════════════════════════════════════════════════════
// YOUR TURN SECTION - Prompt for user's next move
// ═══════════════════════════════════════════════════════════════════

const YourTurnSection = ({ threats, hint, onAskCoach }) => {
  return (
    <div className="rounded-xl border bg-gradient-to-r from-amber-500/10 to-orange-500/10 border-amber-500/30 p-4">
      <div className="flex items-center gap-2 mb-2">
        <div className="w-8 h-8 rounded-full bg-amber-500/20 flex items-center justify-center">
          <HelpCircle className="w-4 h-4 text-amber-400" />
        </div>
        <span className="font-semibold text-amber-400">Your turn!</span>
      </div>
      
      {/* Main prompt */}
      <p className="text-sm text-white mb-3">
        {threats?.length > 0 
          ? "I've created some threats. How will you respond?"
          : "What's your plan here? Think about what you want to achieve."}
      </p>
      
      {/* Quick threats reminder */}
      {threats?.length > 0 && (
        <div className="text-xs text-orange-400 mb-3 flex items-center gap-1">
          <Eye className="w-3 h-3" />
          Don't forget: {threats[0]}
        </div>
      )}
      
      {/* Hint if available */}
      {hint && (
        <div className="text-xs text-zinc-400 italic mb-3">
          💡 Hint: {hint}
        </div>
      )}
      
      {/* Ask coach button */}
      {onAskCoach && (
        <Button
          size="sm"
          variant="outline"
          className="w-full border-amber-500/30 text-amber-400 hover:bg-amber-500/10"
          onClick={() => onAskCoach("What should I focus on here?")}
        >
          <MessageCircle className="w-3 h-3 mr-2" />
          Ask coach for help
        </Button>
      )}
    </div>
  );
};


export default InteractiveCoachingPanel;
export { UserMoveSection, CoachMoveSection, YourTurnSection };
