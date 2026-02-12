/**
 * Converts chess engine evaluation (centipawns/pawns) to human-readable descriptions.
 * 
 * Evaluation scale:
 * - 0.0 to 0.3: Equal position
 * - 0.3 to 1.0: Slight advantage
 * - 1.0 to 2.0: Clear advantage  
 * - 2.0 to 4.0: Winning position
 * - 4.0+: Decisive / Game over
 */

/**
 * Format an evaluation value (in pawns) to a friendly description
 * @param {number} evalValue - Evaluation in pawns (e.g., 2.5 means +2.5 pawn advantage)
 * @param {boolean} forUser - If true, positive = good for user. If false, use absolute perspective.
 * @returns {string} Human-readable evaluation
 */
export const formatEvalToWords = (evalValue, forUser = true) => {
  if (evalValue === undefined || evalValue === null) return "Unknown";
  
  const absVal = Math.abs(evalValue);
  const isPositive = evalValue >= 0;
  
  // Determine the description based on magnitude
  let description;
  if (absVal < 0.3) {
    description = "Equal position";
  } else if (absVal < 1.0) {
    description = isPositive ? "Slight edge" : "Slightly worse";
  } else if (absVal < 2.0) {
    description = isPositive ? "Clear advantage" : "Clearly worse";
  } else if (absVal < 4.0) {
    description = isPositive ? "Winning" : "Lost position";
  } else {
    description = isPositive ? "Completely winning" : "Hopeless";
  }
  
  return description;
};

/**
 * Format evaluation with both description and numeric value
 * @param {number} evalValue - Evaluation in pawns
 * @returns {object} { text: string, className: string }
 */
export const formatEvalWithContext = (evalValue) => {
  if (evalValue === undefined || evalValue === null) {
    return { text: "Unknown", className: "text-muted-foreground" };
  }
  
  const absVal = Math.abs(evalValue);
  const isPositive = evalValue >= 0;
  
  let text;
  let className;
  
  if (absVal < 0.3) {
    text = "Equal";
    className = "text-yellow-500";
  } else if (absVal < 1.0) {
    text = isPositive ? "Slight edge" : "Slightly worse";
    className = isPositive ? "text-green-400" : "text-orange-400";
  } else if (absVal < 2.0) {
    text = isPositive ? "Clear advantage" : "Clearly worse";
    className = isPositive ? "text-green-500" : "text-orange-500";
  } else if (absVal < 4.0) {
    text = isPositive ? "Winning" : "Losing";
    className = isPositive ? "text-green-500" : "text-red-500";
  } else {
    text = isPositive ? "Completely winning" : "Hopeless";
    className = isPositive ? "text-emerald-400" : "text-red-600";
  }
  
  return { text, className };
};

/**
 * Format centipawn loss to describe the severity of a mistake
 * @param {number} cpLoss - Centipawn loss (always positive, represents how bad the move was)
 * @returns {object} { text: string, severity: string, className: string }
 */
export const formatCpLoss = (cpLoss) => {
  if (cpLoss === undefined || cpLoss === null) {
    return { text: "Unknown", severity: "unknown", className: "text-muted-foreground" };
  }
  
  // cpLoss is typically in centipawns (100cp = 1 pawn)
  // But check if it's already in pawn units (small number)
  const cp = cpLoss > 10 ? cpLoss : cpLoss * 100;
  
  if (cp < 50) {
    return { 
      text: "Minor inaccuracy", 
      severity: "minor",
      className: "text-yellow-500" 
    };
  } else if (cp < 100) {
    return { 
      text: "Inaccuracy", 
      severity: "inaccuracy",
      className: "text-orange-400" 
    };
  } else if (cp < 200) {
    return { 
      text: "Mistake", 
      severity: "mistake",
      className: "text-orange-500" 
    };
  } else if (cp < 400) {
    return { 
      text: "Serious mistake", 
      severity: "serious",
      className: "text-red-500" 
    };
  } else {
    return { 
      text: "Blunder", 
      severity: "blunder",
      className: "text-red-600" 
    };
  }
};

/**
 * Format total centipawn loss for weakness summaries
 * @param {number} totalCpLoss - Total centipawns lost across all occurrences
 * @returns {string} Human-readable total loss description
 */
export const formatTotalCpLoss = (totalCpLoss) => {
  if (totalCpLoss === undefined || totalCpLoss === null) return "Unknown impact";
  
  // Convert to pawns for easier understanding
  const pawns = totalCpLoss / 100;
  
  if (pawns < 1) {
    return "Minor impact";
  } else if (pawns < 3) {
    return `~${pawns.toFixed(1)} pawns lost`;
  } else if (pawns < 6) {
    return `${Math.round(pawns)} pawns lost (significant)`;
  } else {
    return `${Math.round(pawns)} pawns lost (major weakness)`;
  }
};

/**
 * Get a simple emoji-free icon indicator for eval change
 * @param {number} evalBefore - Eval before the move
 * @param {number} evalAfter - Eval after the move (or calculated from cpLoss)
 * @returns {string} Simple indicator
 */
export const getEvalChangeIndicator = (evalBefore, cpLoss) => {
  if (evalBefore === undefined || cpLoss === undefined) return "";
  
  const cp = cpLoss > 10 ? cpLoss : cpLoss * 100;
  
  if (cp < 50) return "Small slip";
  if (cp < 100) return "Lost some advantage";
  if (cp < 200) return "Gave away the edge";
  if (cp < 400) return "Big drop in position";
  return "Position collapsed";
};
