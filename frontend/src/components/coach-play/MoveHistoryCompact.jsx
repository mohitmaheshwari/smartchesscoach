/**
 * MoveHistory - Compact, utility-focused move list
 * 
 * Rules:
 * - Minimal and readable
 * - Compact notation
 * - Click move to revisit position
 * - Current move highlighted
 * - Does NOT compete with coach card
 */

import { useRef, useEffect } from "react";
import { History } from "lucide-react";

const MoveHistory = ({ 
  moves = [],
  currentMoveIndex,
  onMoveClick,
  maxHeight = "120px"
}) => {
  const containerRef = useRef(null);
  const currentMoveRef = useRef(null);
  
  // Auto-scroll to current move
  useEffect(() => {
    if (currentMoveRef.current) {
      currentMoveRef.current.scrollIntoView({ 
        behavior: "smooth", 
        block: "nearest" 
      });
    }
  }, [currentMoveIndex, moves.length]);
  
  if (!moves || moves.length === 0) {
    return (
      <div className="text-xs text-muted-foreground text-center py-2">
        No moves yet
      </div>
    );
  }
  
  // Group moves into pairs (white + black)
  const movePairs = [];
  for (let i = 0; i < moves.length; i += 2) {
    movePairs.push({
      number: Math.floor(i / 2) + 1,
      white: moves[i],
      black: moves[i + 1]
    });
  }
  
  return (
    <div 
      ref={containerRef}
      className="overflow-y-auto text-xs font-mono"
      style={{ maxHeight }}
    >
      <div className="flex flex-wrap gap-x-3 gap-y-0.5">
        {movePairs.map((pair, pairIndex) => (
          <div key={pairIndex} className="flex items-center gap-1">
            <span className="text-muted-foreground w-4 text-right">
              {pair.number}.
            </span>
            
            {/* White's move */}
            <button
              ref={pairIndex * 2 === currentMoveIndex ? currentMoveRef : null}
              onClick={() => onMoveClick?.(pairIndex * 2)}
              className={`px-1 rounded hover:bg-muted/50 ${
                pairIndex * 2 === currentMoveIndex 
                  ? "bg-primary/20 text-primary" 
                  : ""
              }`}
            >
              {pair.white?.move || pair.white}
            </button>
            
            {/* Black's move */}
            {pair.black && (
              <button
                ref={pairIndex * 2 + 1 === currentMoveIndex ? currentMoveRef : null}
                onClick={() => onMoveClick?.(pairIndex * 2 + 1)}
                className={`px-1 rounded hover:bg-muted/50 ${
                  pairIndex * 2 + 1 === currentMoveIndex 
                    ? "bg-primary/20 text-primary" 
                    : ""
                }`}
              >
                {pair.black?.move || pair.black}
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

// Collapsible wrapper
const MoveHistorySection = ({ 
  moves, 
  currentMoveIndex, 
  onMoveClick,
  defaultExpanded = true 
}) => {
  return (
    <details open={defaultExpanded} className="group">
      <summary className="flex items-center gap-2 cursor-pointer text-xs text-muted-foreground hover:text-foreground py-2 select-none">
        <History className="w-3 h-3" />
        <span>Moves ({moves?.length || 0})</span>
      </summary>
      <div className="pt-1 pb-2">
        <MoveHistory 
          moves={moves} 
          currentMoveIndex={currentMoveIndex}
          onMoveClick={onMoveClick}
        />
      </div>
    </details>
  );
};

export { MoveHistory, MoveHistorySection };
export default MoveHistory;
