/**
 * AlternateTimeline - Shows what would have happened with the better move
 * 
 * This is the "human coach" feature - showing the alternate reality:
 * "If you had played Nxd4, here's how it could have continued..."
 * 
 * Uses PV (Principal Variation) data from Stockfish analysis.
 */

import { useState } from 'react';
import { ChevronDown, ChevronUp, GitBranch, Play, ArrowRight, Swords } from 'lucide-react';
import { Chess } from 'chess.js';
import { Chessboard } from 'react-chessboard';

const AlternateTimeline = ({ 
  fen,              // Position before the mistake
  yourMove,         // What user played (e.g., "Rec8")
  betterMove,       // What was better (e.g., "Nxd4")
  pvAfterBest,      // Array of moves after best move (e.g., ["Rd5", "Rad8", ...])
  cpLoss,           // How much was lost
  userColor = 'white',
  onPlayMove,       // Callback when user wants to see a position
  onPractice        // Callback to start practice mode from this position
}) => {
  const [expanded, setExpanded] = useState(false);
  const [previewIndex, setPreviewIndex] = useState(-1); // -1 = show initial position
  
  // If no PV data, don't show the component
  if (!pvAfterBest || pvAfterBest.length === 0 || !betterMove) {
    return null;
  }
  
  // Build the alternate timeline: betterMove + opponent responses
  const timeline = [betterMove, ...pvAfterBest].slice(0, 6); // Show up to 6 moves
  
  // Calculate positions for each move in the timeline
  const getPositionAtIndex = (index) => {
    if (!fen || index < 0) return fen;
    
    try {
      const chess = new Chess(fen);
      for (let i = 0; i <= index && i < timeline.length; i++) {
        const move = timeline[i];
        const result = chess.move(move);
        if (!result) break;
      }
      return chess.fen();
    } catch (e) {
      return fen;
    }
  };
  
  const previewFen = previewIndex >= 0 ? getPositionAtIndex(previewIndex) : fen;
  
  // Format move with number
  const formatMoveWithNumber = (move, idx, startingColor) => {
    const isWhiteMove = (startingColor === 'white' && idx % 2 === 0) || 
                        (startingColor === 'black' && idx % 2 === 1);
    if (isWhiteMove) {
      const moveNum = Math.floor(idx / 2) + 1;
      return `${moveNum}. ${move}`;
    }
    return `${move}`;
  };
  
  // Determine starting color (opposite of who just moved in the mistake position)
  const fenParts = fen?.split(' ') || [];
  const toMove = fenParts[1] || 'w';
  const startingColor = toMove === 'w' ? 'white' : 'black';
  
  return (
    <div 
      className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 overflow-hidden"
      data-testid="alternate-timeline"
    >
      {/* Header - always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-3 flex items-center justify-between hover:bg-emerald-500/10 transition-colors"
      >
        <div className="flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-emerald-400" />
          <span className="text-sm font-medium text-emerald-400">
            What if you played {betterMove}?
          </span>
        </div>
        <div className="flex items-center gap-2">
          {cpLoss && (
            <span className="text-xs text-muted-foreground">
              Saved {Math.abs(cpLoss / 100).toFixed(1)} pawns
            </span>
          )}
          {expanded ? (
            <ChevronUp className="w-4 h-4 text-emerald-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-emerald-400" />
          )}
        </div>
      </button>
      
      {/* Expanded content */}
      {expanded && (
        <div className="p-3 pt-0 space-y-3">
          {/* Timeline moves */}
          <div className="flex flex-wrap items-center gap-1 text-sm">
            <span className="text-emerald-400 font-medium">{betterMove}</span>
            {pvAfterBest.slice(0, 5).map((move, idx) => (
              <span key={idx} className="flex items-center gap-1">
                <ArrowRight className="w-3 h-3 text-muted-foreground" />
                <button
                  onClick={() => setPreviewIndex(idx + 1)}
                  className={`px-1.5 py-0.5 rounded transition-colors ${
                    previewIndex === idx + 1 
                      ? 'bg-emerald-500/20 text-emerald-300' 
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                  }`}
                >
                  {move}
                </button>
              </span>
            ))}
          </div>
          
          {/* Mini board preview */}
          <div className="flex gap-3">
            <div className="w-[140px] h-[140px] rounded overflow-hidden border border-emerald-500/20">
              <Chessboard
                position={previewFen}
                boardOrientation={userColor}
                arePiecesDraggable={false}
                customBoardStyle={{
                  borderRadius: '0',
                }}
                customDarkSquareStyle={{ backgroundColor: '#1a4d3e' }}
                customLightSquareStyle={{ backgroundColor: '#2d7d64' }}
              />
            </div>
            
            <div className="flex-1 flex flex-col justify-center">
              <p className="text-xs text-muted-foreground mb-2">
                {previewIndex < 0 ? (
                  "This was the position. Click a move to see how it continues."
                ) : previewIndex === 0 ? (
                  <>After your <span className="text-emerald-400 font-medium">{betterMove}</span>, you'd have a solid advantage.</>
                ) : (
                  <>The game could continue naturally with both sides playing accurately.</>
                )}
              </p>
              
              {/* Play through button */}
              <div className="flex items-center gap-3">
                <button
                  onClick={() => {
                    // Cycle through the timeline
                    setPreviewIndex(prev => prev >= timeline.length - 1 ? -1 : prev + 1);
                  }}
                  className="flex items-center gap-1 text-xs text-emerald-400 hover:text-emerald-300 transition-colors"
                >
                  <Play className="w-3 h-3" />
                  {previewIndex < 0 ? 'Play through' : 'Next move'}
                </button>
                
                {/* Practice this variation button */}
                {onPractice && (
                  <button
                    onClick={() => onPractice(fen, betterMove)}
                    className="flex items-center gap-1 text-xs text-amber-400 hover:text-amber-300 transition-colors"
                    data-testid="practice-variation-btn"
                  >
                    <Swords className="w-3 h-3" />
                    Practice this
                  </button>
                )}
              </div>
            </div>
          </div>
          
          {/* Coaching insight */}
          <p className="text-xs text-emerald-300/80 italic border-t border-emerald-500/20 pt-2">
            This is the line the engine expected. Your opponent might play differently, but you'd have the advantage.
          </p>
        </div>
      )}
    </div>
  );
};

export default AlternateTimeline;
