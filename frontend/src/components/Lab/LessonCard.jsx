/**
 * LessonCard - Enhanced Coaching Structure
 * 
 * Full lesson structure:
 * 1. Concept (from chess principles library)
 * 2. What happened (specific to this game)
 * 3. Why it matters (explains the principle)
 * 4. Better idea (what should have been played)
 * 5. Memorable rule (one-liner to remember)
 * 6. Coach Insight (optional wisdom quote)
 * 
 * Two variants:
 * - Main (⭐) - full structure, highlighted
 * - Supporting (📘) - compact version
 */

import { Star, BookOpen, ChevronRight, Lightbulb, ArrowRight, MessageSquare } from 'lucide-react';

// Memorable coach insights mapped to common patterns
const COACH_INSIGHTS = {
  'CASTLE_BEFORE_ATTACKING': "An uncastled king is like a house without a roof.",
  'FORCING_MOVES_FIRST': "The best move is often the one your opponent fears most.",
  'SIMPLIFY_WHEN_AHEAD': "When winning, remove chaos. When losing, create it.",
  'IMPROVE_WORST_PIECE': "Your army is only as strong as your weakest soldier.",
  'OPEN_FILE_CONTROL': "Rooks dream of open files.",
  'LPDO': "Loose pieces drop off. Count your undefended pieces every move.",
  'ACTIVATE_KING_ENDGAME': "In the endgame, the king becomes a warrior.",
  'DONT_MOVE_SAME_PIECE_TWICE': "Each move should bring a new piece to the battle.",
  'BACK_RANK_WEAKNESS': "A king needs breathing room. Give it air.",
  'QUEEN_OUT_TOO_EARLY': "The queen is too valuable to be chased around.",
  'default': "A move without a purpose is usually a bad move."
};

const LessonCard = ({ 
  lesson, 
  variant = 'supporting', // 'main' | 'supporting'
  onMoveClick,
  onAskCoach, // New: callback to ask coach for deeper explanation
  onSeeStrategy // New: callback to switch to strategy tab
}) => {
  if (!lesson) return null;
  
  const isMain = variant === 'main';
  
  // Get coach insight based on lesson pattern/module
  const getCoachInsight = () => {
    if (lesson.module_key && COACH_INSIGHTS[lesson.module_key]) {
      return COACH_INSIGHTS[lesson.module_key];
    }
    // Try to match from concept
    const concept = (lesson.concept || '').toUpperCase();
    if (concept.includes('CASTLE') || concept.includes('KING')) {
      return COACH_INSIGHTS['CASTLE_BEFORE_ATTACKING'];
    }
    if (concept.includes('AHEAD') || concept.includes('WINNING') || concept.includes('ADVANTAGE')) {
      return COACH_INSIGHTS['SIMPLIFY_WHEN_AHEAD'];
    }
    if (concept.includes('ROOK') || concept.includes('FILE')) {
      return COACH_INSIGHTS['OPEN_FILE_CONTROL'];
    }
    if (concept.includes('PIECE') || concept.includes('WORST')) {
      return COACH_INSIGHTS['IMPROVE_WORST_PIECE'];
    }
    return COACH_INSIGHTS['default'];
  };
  
  return (
    <div className={`rounded-lg border ${
      isMain 
        ? 'bg-gradient-to-br from-amber-500/10 to-orange-500/10 border-amber-500/30 p-4' 
        : 'bg-slate-800/50 border-slate-700/50 p-3'
    }`}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        {isMain ? (
          <Star className="w-4 h-4 text-amber-400 fill-amber-400" />
        ) : (
          <BookOpen className="w-3.5 h-3.5 text-blue-400" />
        )}
        <span className={`text-xs font-bold uppercase tracking-wider ${
          isMain ? 'text-amber-400' : 'text-blue-400'
        }`}>
          {isMain ? 'Main Lesson' : `Lesson ${lesson.index || ''}`}
        </span>
      </div>
      
      {/* 1. Concept Name */}
      <h3 className={`font-semibold mb-2 ${isMain ? 'text-base' : 'text-sm'}`}>
        {lesson.concept}
      </h3>
      
      {/* 2. What Happened (specific to this game) */}
      {lesson.move_number && (
        <div className="mb-3">
          <button
            onClick={() => onMoveClick && onMoveClick(lesson.move_number)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <span className="font-mono font-medium">Move {lesson.move_number}</span>
            {lesson.move_san && (
              <span className="text-slate-500">({lesson.move_san})</span>
            )}
            <ChevronRight className="w-3 h-3" />
          </button>
          
          {/* What you played vs what was better */}
          {lesson.your_move && lesson.better_move && (
            <div className="mt-2 flex items-center gap-2 text-xs">
              <span className="text-red-400/80">Played: <span className="font-mono">{lesson.your_move}</span></span>
              <ArrowRight className="w-3 h-3 text-muted-foreground" />
              <span className="text-green-400/80">Better: <span className="font-mono">{lesson.better_move}</span></span>
            </div>
          )}
        </div>
      )}
      
      {/* 3. Why it matters / Description */}
      {lesson.description && (
        <p className={`text-muted-foreground mb-3 ${isMain ? 'text-sm' : 'text-xs'}`}>
          {lesson.description}
        </p>
      )}
      
      {/* 4. Better Idea (what should have happened) */}
      {lesson.better_idea && (
        <div className={`mb-3 p-2 rounded bg-green-500/10 border border-green-500/20 ${isMain ? 'text-sm' : 'text-xs'}`}>
          <span className="text-green-400 font-medium">Better idea: </span>
          <span className="text-muted-foreground">{lesson.better_idea}</span>
        </div>
      )}
      
      {/* 5. Memorable Rule */}
      {lesson.rule && (
        <div className={`rounded px-2.5 py-2 mb-3 ${
          isMain ? 'bg-black/20 border border-amber-500/20' : 'bg-black/30'
        }`}>
          <span className={`font-bold ${isMain ? 'text-amber-400 text-xs' : 'text-blue-400 text-[10px]'}`}>
            Rule:
          </span>
          <p className={`mt-0.5 ${isMain ? 'text-sm' : 'text-xs'}`}>
            {lesson.rule}
          </p>
        </div>
      )}
      
      {/* 6. Coach Insight (memorable wisdom) - Main lessons only */}
      {isMain && (
        <div className="flex items-start gap-2 p-2 rounded bg-violet-500/10 border border-violet-500/20 mb-3">
          <Lightbulb className="w-3.5 h-3.5 text-violet-400 mt-0.5 shrink-0" />
          <p className="text-xs text-violet-300 italic">
            "{getCoachInsight()}"
          </p>
        </div>
      )}
      
      {/* Action buttons - Connect to other tabs */}
      <div className="flex items-center gap-2 mt-2">
        {onAskCoach && (
          <button
            onClick={() => onAskCoach(lesson)}
            className="flex items-center gap-1 text-[10px] text-violet-400 hover:text-violet-300 transition-colors"
            data-testid="ask-coach-why"
          >
            <MessageSquare className="w-3 h-3" />
            Ask Coach Why?
          </button>
        )}
        {onSeeStrategy && isMain && (
          <button
            onClick={onSeeStrategy}
            className="flex items-center gap-1 text-[10px] text-blue-400 hover:text-blue-300 transition-colors"
            data-testid="see-strategy"
          >
            <ArrowRight className="w-3 h-3" />
            See Strategy
          </button>
        )}
      </div>
    </div>
  );
};

export default LessonCard;
