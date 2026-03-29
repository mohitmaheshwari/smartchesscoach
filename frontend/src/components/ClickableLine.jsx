/**
 * ClickableLine Component
 * 
 * Renders a chess line with clickable moves.
 * When a move is clicked, it plays all moves up to that point on the board.
 */

import React from "react";

/**
 * Parse explanation text and extract moves to make them clickable
 * 
 * Input: "After d5, the line goes: exd5 (White takes pawn), Na5, Bb5++, c6."
 * Output: Array of {type: "text" | "move", content: string, moveIndex: number}
 */
export function parseLineText(text) {
  if (!text) return [{ type: "text", content: text || "" }];
  
  // Pattern to match chess moves (SAN notation)
  // Matches: e4, Nf3, Bxc6, O-O, O-O-O, exd5, Qh5+, Bb5++, etc.
  const movePattern = /\b([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]*|O-O-O|O-O)\b/g;
  
  const parts = [];
  let lastIndex = 0;
  let moveIndex = 0;
  let match;
  
  // Find "the line goes:" to start tracking moves
  const lineStartMatch = text.match(/the line goes:\s*/i);
  const lineStartIndex = lineStartMatch ? lineStartMatch.index + lineStartMatch[0].length : 0;
  
  while ((match = movePattern.exec(text)) !== null) {
    // Add text before this match
    if (match.index > lastIndex) {
      parts.push({
        type: "text",
        content: text.slice(lastIndex, match.index)
      });
    }
    
    // Only make moves clickable if they're after "the line goes:"
    const isInLine = match.index >= lineStartIndex;
    
    parts.push({
      type: isInLine ? "move" : "text",
      content: match[0],
      moveIndex: isInLine ? moveIndex++ : -1
    });
    
    lastIndex = match.index + match[0].length;
  }
  
  // Add remaining text
  if (lastIndex < text.length) {
    parts.push({
      type: "text",
      content: text.slice(lastIndex)
    });
  }
  
  return parts;
}

/**
 * Extract the actual moves from the explanation (just the SAN moves in order)
 */
export function extractMovesFromText(text) {
  if (!text) return [];
  
  // Find the part after "the line goes:"
  const lineMatch = text.match(/the line goes:\s*(.+?)(?:\.|$)/i);
  if (!lineMatch) return [];
  
  const lineText = lineMatch[1];
  
  // Extract all moves
  const movePattern = /\b([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]*|O-O-O|O-O)\b/g;
  const moves = [];
  let match;
  
  while ((match = movePattern.exec(lineText)) !== null) {
    moves.push(match[0]);
  }
  
  return moves;
}

/**
 * ClickableLine Component
 */
export default function ClickableLine({ 
  text, 
  onMoveClick,
  className = ""
}) {
  const parts = parseLineText(text);
  const moves = extractMovesFromText(text);
  
  const handleMoveClick = (moveIndex) => {
    if (onMoveClick && moveIndex >= 0) {
      // Get all moves up to and including this one
      const movesToPlay = moves.slice(0, moveIndex + 1);
      onMoveClick(movesToPlay, moveIndex);
    }
  };
  
  return (
    <span className={className}>
      {parts.map((part, i) => {
        if (part.type === "move" && part.moveIndex >= 0) {
          return (
            <button
              key={i}
              onClick={() => handleMoveClick(part.moveIndex)}
              className="font-mono font-bold text-amber-400 hover:text-amber-300 hover:underline cursor-pointer transition-colors"
              title={`Click to play moves up to ${part.content}`}
            >
              {part.content}
            </button>
          );
        }
        return <span key={i}>{part.content}</span>;
      })}
    </span>
  );
}
