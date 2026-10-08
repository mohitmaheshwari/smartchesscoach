/**
 * BoardCoordinates — Clean, professional rank (1-8) and file (a-h) edge coordinates
 * styled with modern typography, crisp contrast, and orientation awareness.
 */
import { useLayoutEffect, useRef, useState } from "react";

const FILES = ["a", "b", "c", "d", "e", "f", "g", "h"];
const RANKS = [1, 2, 3, 4, 5, 6, 7, 8];

const BoardCoordinates = ({ orientation = "white", minWidth = 240 }) => {
  const ref = useRef(null);
  const [bigEnough, setBigEnough] = useState(true);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setBigEnough(el.offsetWidth >= minWidth);
    measure();
    let ro;
    if (typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(measure);
      ro.observe(el);
    }
    return () => ro && ro.disconnect();
  }, [minWidth]);

  if (!bigEnough) return null;

  const displayFiles = orientation === "white" ? FILES : [...FILES].reverse();
  const displayRanks = orientation === "white" ? [...RANKS].reverse() : RANKS;

  return (
    <div
      ref={ref}
      className="pointer-events-none absolute inset-0 z-30 select-none overflow-hidden font-mono text-[11px] sm:text-xs font-bold"
      data-testid="board-coordinates"
    >
      {/* File letters along bottom edge */}
      {displayFiles.map((file, i) => {
        // Determine whether this bottom square is dark or light
        // For white orientation, bottom rank is 1. i even => dark square (a1, c1, e1, g1)
        const isDarkSquare = orientation === "white" ? i % 2 === 0 : i % 2 === 1;
        return (
          <span
            key={`file-${file}`}
            className="absolute bottom-1 sm:bottom-1.5 font-mono font-bold tracking-tight"
            style={{
              left: `${i * 12.5 + 9.8}%`,
              color: isDarkSquare ? "#f0d9b5" : "#785338",
              textShadow: isDarkSquare ? "0 1px 3px rgba(0,0,0,0.7)" : "none",
              opacity: 0.85,
            }}
          >
            {file}
          </span>
        );
      })}

      {/* Rank numbers along left edge */}
      {displayRanks.map((rank, i) => {
        // Determine whether this left square is dark or light
        // For white orientation, top rank is 8 (a8 is light => i=0 is light, i=1 is dark)
        const isDarkSquare = orientation === "white" ? i % 2 === 1 : i % 2 === 0;
        return (
          <span
            key={`rank-${rank}`}
            className="absolute top-1 sm:top-1.5 font-mono font-bold tracking-tight"
            style={{
              top: `${i * 12.5 + 1.2}%`,
              left: "1.2%",
              color: isDarkSquare ? "#f0d9b5" : "#785338",
              textShadow: isDarkSquare ? "0 1px 3px rgba(0,0,0,0.7)" : "none",
              opacity: 0.85,
            }}
          >
            {rank}
          </span>
        );
      })}
    </div>
  );
};

export default BoardCoordinates;

