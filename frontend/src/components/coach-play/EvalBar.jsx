/**
 * EvalBar - Visual evaluation bar showing position advantage
 * 
 * A vertical bar that fills its container height:
 * - Score displayed in the CENTER of the bar for readability
 */

const EvalBar = ({ evaluation, userColor }) => {
  const { score, mate_in } = evaluation || { score: 0, mate_in: null };
  
  // Calculate percentage for the bar (50% = equal, >50% = white advantage)
  const getBarPercentage = () => {
    if (mate_in !== null) {
      return mate_in > 0 ? 95 : 5;
    }
    const clamped = Math.max(-10, Math.min(10, score));
    return 50 + (clamped * 4.5);
  };
  
  const whitePercent = getBarPercentage();
  
  // Determine display text with sign
  const getEvalText = () => {
    if (mate_in !== null) {
      const sign = mate_in > 0 ? "+" : "-";
      return `${sign}M${Math.abs(mate_in)}`;
    }
    if (Math.abs(score) < 0.1) return "0.0";
    const sign = score > 0 ? "+" : "-";
    return `${sign}${Math.abs(score).toFixed(1)}`;
  };
  
  // Determine who is winning
  const isWhiteWinning = score > 0.3 || (mate_in !== null && mate_in > 0);
  const isBlackWinning = score < -0.3 || (mate_in !== null && mate_in < 0);
  
  // Color coding based on user's perspective
  const userIsWhite = userColor === "white";
  const userWinning = (userIsWhite && isWhiteWinning) || (!userIsWhite && isBlackWinning);
  const userLosing = (userIsWhite && isBlackWinning) || (!userIsWhite && isWhiteWinning);
  
  return (
    <div 
      className="w-full h-full flex flex-col rounded overflow-hidden border border-zinc-700 relative select-none"
      data-testid="eval-bar"
      title={`Evaluation: ${getEvalText()}`}
    >
      {/* Black portion (top) */}
      <div 
        className="bg-zinc-800 transition-all duration-500 ease-out"
        style={{ height: `${100 - whitePercent}%` }}
      />
      
      {/* White portion (bottom) */}
      <div 
        className="bg-zinc-200 transition-all duration-500 ease-out"
        style={{ height: `${whitePercent}%` }}
      />
      
      {/* Score displayed in the CENTER of the bar for readability */}
      <div 
        className="absolute inset-0 flex items-center justify-center pointer-events-none"
      >
        <div 
          className={`px-1.5 py-1 rounded text-xs font-bold leading-none whitespace-nowrap shadow-md ${
            userWinning 
              ? "bg-green-500 text-white" 
              : userLosing 
                ? "bg-red-500 text-white"
                : "bg-zinc-600 text-white"
          }`}
          data-testid="eval-text"
        >
          {getEvalText()}
        </div>
      </div>
    </div>
  );
};

export default EvalBar;
