/**
 * CoachBoard — The chess board + move controls for Play with Coach
 */

import { Button } from "@/components/ui/button";
import LichessBoard from "@/components/LichessBoard";
import {
  SkipBack, SkipForward, ChevronLeft, ChevronRight,
  Play, Pause, RotateCcw,
} from "lucide-react";

const CoachBoard = ({
  fen,
  orientation,
  isPlayerTurn,
  userColor,
  interactive,
  arrows,
  lastMove,
  onMove,
  onFlipBoard,
  // Guardian overlay props
  guardianOverlay,
  // Teaching overlay props
  teachingOverlay,
}) => {
  return (
    <div className="w-[55%] flex flex-col border-r border-border" data-testid="coach-board">
      {/* Board */}
      <div className="flex-1 flex items-center justify-center p-4">
        <div className="w-full max-w-[560px] aspect-square relative">
          <LichessBoard
            fen={fen}
            orientation={orientation}
            viewOnly={!isPlayerTurn || !interactive}
            interactive={isPlayerTurn && interactive}
            movableColor={isPlayerTurn ? userColor : undefined}
            arrows={arrows}
            lastMove={lastMove}
            onMove={isPlayerTurn ? onMove : undefined}
          />
          {guardianOverlay}
          {teachingOverlay}
        </div>
      </div>

      {/* Controls */}
      <div className="p-3 border-t border-border flex items-center justify-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={onFlipBoard}
          data-testid="flip-board-btn"
        >
          <RotateCcw className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
};

export default CoachBoard;
