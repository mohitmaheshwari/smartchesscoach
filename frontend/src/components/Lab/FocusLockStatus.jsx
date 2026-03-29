/**
 * FocusLockStatus - Compact Focus Lock display
 * 
 * Shows progress and compliance when lock is active.
 */

import { Lock } from 'lucide-react';

const FocusLockStatus = ({ lock }) => {
  if (!lock || !lock.active) return null;
  
  const compliance = lock.compliance?.average || 0;
  const complianceColor = compliance >= 75 ? 'text-emerald-400' : 
                          compliance >= 60 ? 'text-amber-400' : 'text-red-400';
  
  return (
    <div className="rounded-lg bg-blue-500/5 border border-blue-500/20 p-3">
      <div className="flex items-center gap-2 mb-2">
        <Lock className="w-4 h-4 text-blue-400" />
        <span className="text-xs font-bold uppercase tracking-wider text-blue-400">
          Focus Lock
        </span>
      </div>
      
      <p className="text-sm font-medium mb-2">
        Lesson: {lock.rule_description || lock.lesson_key?.replace(/_/g, ' ').toLowerCase()}
      </p>
      
      <div className="flex items-center justify-between text-xs">
        <div>
          <span className="text-muted-foreground">Progress:</span>
          <span className="ml-1 font-mono">
            {lock.progress?.completed || 0} / {lock.progress?.required || 5} games
          </span>
        </div>
        <div>
          <span className="text-muted-foreground">Compliance:</span>
          <span className={`ml-1 font-bold ${complianceColor}`}>
            {compliance}%
          </span>
        </div>
      </div>
    </div>
  );
};

export default FocusLockStatus;
