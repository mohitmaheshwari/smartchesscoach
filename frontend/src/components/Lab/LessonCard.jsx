/**
 * LessonCard - Step 10 Redesign
 * 
 * Displays a single lesson with:
 * - Concept name
 * - Move reference (clickable)
 * - Rule (max 2 lines)
 * 
 * Two variants:
 * - Main (⭐) - larger, highlighted
 * - Supporting (📘) - compact
 */

import { Star, BookOpen, ChevronRight } from 'lucide-react';

const LessonCard = ({ 
  lesson, 
  variant = 'supporting', // 'main' | 'supporting'
  onMoveClick 
}) => {
  if (!lesson) return null;
  
  const isMain = variant === 'main';
  
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
      
      {/* Concept */}
      <h3 className={`font-semibold mb-2 ${isMain ? 'text-base' : 'text-sm'}`}>
        {lesson.concept}
      </h3>
      
      {/* Move Reference */}
      {lesson.move_number && (
        <button
          onClick={() => onMoveClick && onMoveClick(lesson.move_number)}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors mb-2"
        >
          <span className="font-mono">Move {lesson.move_number}</span>
          {lesson.move_san && (
            <span className="text-slate-500">({lesson.move_san})</span>
          )}
          <ChevronRight className="w-3 h-3" />
        </button>
      )}
      
      {/* Description (short) */}
      {lesson.description && (
        <p className={`text-muted-foreground mb-2 ${isMain ? 'text-sm' : 'text-xs'}`}>
          {lesson.description}
        </p>
      )}
      
      {/* Rule */}
      {lesson.rule && (
        <div className={`rounded px-2.5 py-2 ${
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
    </div>
  );
};

export default LessonCard;
