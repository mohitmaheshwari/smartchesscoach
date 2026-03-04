/**
 * CoachNotice - Pattern Reminder
 * 
 * Shows when a mistake pattern appears in multiple recent games.
 * Makes the coach feel personal.
 */

import { AlertTriangle } from 'lucide-react';

const CoachNotice = ({ pattern, similarGames = [] }) => {
  if (!pattern || similarGames.length === 0) return null;
  
  return (
    <div className="rounded-lg bg-amber-500/5 border border-amber-500/20 p-3">
      <div className="flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-amber-400 mb-1">
            Coach Notice
          </p>
          <p className="text-sm text-muted-foreground mb-2">
            This mistake appears in several of your recent games.
          </p>
          
          {/* Similar Games List */}
          <div className="flex flex-wrap gap-1.5">
            {similarGames.slice(0, 3).map((game, i) => (
              <span 
                key={i}
                className="text-xs px-2 py-0.5 rounded bg-slate-700/50 text-slate-300"
              >
                vs {game.opponent || 'Unknown'}
              </span>
            ))}
          </div>
          
          <p className="text-xs text-amber-400/80 mt-2 font-medium">
            Let's focus on fixing this habit.
          </p>
        </div>
      </div>
    </div>
  );
};

export default CoachNotice;
