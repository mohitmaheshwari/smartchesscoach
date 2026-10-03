/**
 * CoachPlayBoard — Elite Chess Studio Edition
 *
 * Implements the tactile, luxury Match Center design:
 * - Dual player cards (Tomasz Master vs Jessica Coach)
 * - Dual circular analog chess clocks with live hand rotation
 * - Pristine metallic slate chessboard with outer bezel coordinates (A-H, 1-8)
 * - Flanking captured pieces trays (White & Black captures)
 * - Tactile bottom toolbar with cyan glowing play button
 * - Horizontal move history pills with active move highlight
 * - Integrated Studio Piece Academy for wide desktop views
 */

import { forwardRef, useState, useMemo, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MOTION_TIMING } from "@/lib/motion";
import LichessBoard from "@/components/LichessBoard";
import { Button } from "@/components/ui/button";
import { isMuted, setMuted } from "@/lib/chessSounds";
import { Badge } from "@/components/ui/badge";
import PreMoveChecklist from "@/components/coach/PreMoveChecklist";
import { OpeningCorrectionDialog } from "@/components/openings/OpeningCorrectionDialog";
import {
  EvalBar,
  PositionCoachingPanel,
} from "@/components/coach-play";
import {
  Brain,
  Clock,
  Lightbulb,
  Loader2,
  RotateCcw,
  Flag,
  Play,
  Pause,
  BookOpen,
  X,
  Volume2,
  VolumeX,
} from "lucide-react";
import { API } from "@/App";

/**
 * Calculates pieces captured by each side from current FEN.
 */
function calculateCapturedPieces(fen) {
  if (!fen) return { capturedWhite: [], capturedBlack: [] };
  const boardPart = fen.split(" ")[0];
  const initial = {
    p: 8, n: 2, b: 2, r: 2, q: 1,
    P: 8, N: 2, B: 2, R: 2, Q: 1,
  };
  const counts = {};
  for (const c of boardPart) {
    if (initial[c]) counts[c] = (counts[c] || 0) + 1;
  }
  const capturedWhite = [];
  const capturedBlack = [];

  // Pieces captured by White (meaning Black lost them)
  const blackSymbols = { q: "♛", r: "♜", b: "♝", n: "♞", p: "♟" };
  for (const [p, sym] of Object.entries(blackSymbols)) {
    const lost = (initial[p] || 0) - (counts[p] || 0);
    for (let i = 0; i < lost; i++) capturedWhite.push(sym);
  }

  // Pieces captured by Black (meaning White lost them)
  const whiteSymbols = { Q: "♕", R: "♖", B: "♗", N: "♘", P: "♙" };
  for (const [p, sym] of Object.entries(whiteSymbols)) {
    const lost = (initial[p] || 0) - (counts[p] || 0);
    for (let i = 0; i < lost; i++) capturedBlack.push(sym);
  }

  return { capturedWhite, capturedBlack };
}

const getStoredClock = (sessionId) => {
  if (!sessionId) return null;
  try {
    const item = localStorage.getItem(`coach_clock_${sessionId}`);
    return item ? JSON.parse(item) : null;
  } catch {
    return null;
  }
};

const setStoredClock = (sessionId, uSecs, cSecs, paused = false) => {
  if (!sessionId) return;
  try {
    localStorage.setItem(`coach_clock_${sessionId}`, JSON.stringify({
      user_time_remaining: uSecs,
      coach_time_remaining: cSecs,
      is_paused: paused,
      timestamp: Date.now()
    }));
  } catch {}
};

const CoachPlayBoard = forwardRef(function CoachPlayBoard(
  {
    /* game state */
    session,
    currentFen,
    boardOrientation = "white",
    lastMove,
    isPlayerTurn,
    coachingLocked,
    gameOver,
    evaluation,
    selectedColor = "white",
    gameMode,
    unifiedExperience = false,
    /* teaching state */
    isInTeachingMode,
    activeLesson,
    lessonInstruction,
    lessonComplete,
    inlineOpening,
    inlineTrap,
    setInlineOpening,
    setInlineTrap,
    openingGuidance,
    openingCorrectionCount,
    setOpeningCorrectionCount,
    /* UI state */
    hideEvalBar,
    coachArrows,
    coachThinking,
    undoLoading,
    hasCastled,
    developedPieces,
    playerWeaknesses,
    showChecklist,
    setShowChecklist,
    positionCoaching,
    setPositionCoaching,
    setChatMessages,
    /* handlers */
    makeMove,
    flipBoard,
    resignGame,
    newGame,
    restartGame,
    isGamePaused = false,
    setIsGamePaused,
    showResumeModal = false,
    canUndoLastMove,
    handleUndoMove,
    handleExitLesson,
    triggerCoachMove,
    handleStartLesson,
    moveClassification,
    user,
  },
  boardRef
) {
  const [soundOff, setSoundOff] = useState(() => isMuted());
  const [showRestartConfirm, setShowRestartConfirm] = useState(false);
  const [localPaused, setLocalPaused] = useState(false);

  const isPaused = Boolean(isGamePaused || showResumeModal || localPaused);

  // Initial seconds from session or default 15 minutes (900s)
  const initialUserSecs = (() => {
    const stored = getStoredClock(session?.session_id);
    return stored?.user_time_remaining ?? session?.user_time_remaining ?? (session?.time_control ? session.time_control * 60 : 900);
  })();

  const initialCoachSecs = (() => {
    const stored = getStoredClock(session?.session_id);
    return stored?.coach_time_remaining ?? session?.coach_time_remaining ?? (session?.time_control ? session.time_control * 60 : 900);
  })();

  const [playerSeconds, setPlayerSeconds] = useState(initialUserSecs);
  const [coachSeconds, setCoachSeconds] = useState(initialCoachSecs);

  // Sync if session resets or updates from backend
  useEffect(() => {
    if (!session?.session_id) return;
    const stored = getStoredClock(session.session_id);
    if (stored?.user_time_remaining != null) {
      setPlayerSeconds(stored.user_time_remaining);
    } else if (session.user_time_remaining != null) {
      setPlayerSeconds(session.user_time_remaining);
    }

    if (stored?.coach_time_remaining != null) {
      setCoachSeconds(stored.coach_time_remaining);
    } else if (session.coach_time_remaining != null) {
      setCoachSeconds(session.coach_time_remaining);
    }
  }, [session?.session_id]);

  // Active Timer Countdown: ticks down every second for whoever's turn it is ONLY when NOT paused
  useEffect(() => {
    if (!session || gameOver || isPaused) return;

    const timer = setInterval(() => {
      if (isPlayerTurn) {
        setPlayerSeconds((prev) => {
          const next = Math.max(0, prev - 1);
          setStoredClock(session.session_id, next, coachSeconds, false);
          return next;
        });
      } else {
        setCoachSeconds((prev) => {
          const next = Math.max(0, prev - 1);
          setStoredClock(session.session_id, playerSeconds, next, false);
          return next;
        });
      }
    }, 1000);

    return () => clearInterval(timer);
  }, [session, isPlayerTurn, gameOver, isPaused, playerSeconds, coachSeconds]);

  // Automatically pause clock when user leaves (visibilitychange, beforeunload, unmount)
  useEffect(() => {
    if (!session?.session_id || gameOver) return;

    const handleVisibility = () => {
      if (document.hidden) {
        setLocalPaused(true);
        setIsGamePaused?.(true);
        setStoredClock(session.session_id, playerSeconds, coachSeconds, true);
        fetch(`${API}/coach/play/sync-clock`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          keepalive: true,
          body: JSON.stringify({
            session_id: session.session_id,
            user_time_remaining: playerSeconds,
            coach_time_remaining: coachSeconds,
            is_paused: true,
          }),
        }).catch(() => {});
      }
    };

    const handleBeforeUnload = () => {
      setStoredClock(session.session_id, playerSeconds, coachSeconds, true);
      const payload = JSON.stringify({
        session_id: session.session_id,
        user_time_remaining: playerSeconds,
        coach_time_remaining: coachSeconds,
        is_paused: true,
      });
      if (navigator.sendBeacon) {
        navigator.sendBeacon(`${API}/coach/play/sync-clock`, new Blob([payload], { type: "application/json" }));
      }
    };

    document.addEventListener("visibilitychange", handleVisibility);
    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener("beforeunload", handleBeforeUnload);
      setStoredClock(session.session_id, playerSeconds, coachSeconds, true);
      fetch(`${API}/coach/play/sync-clock`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        keepalive: true,
        body: JSON.stringify({
          session_id: session.session_id,
          user_time_remaining: playerSeconds,
          coach_time_remaining: coachSeconds,
          is_paused: true,
        }),
      }).catch(() => {});
    };
  }, [session?.session_id, playerSeconds, coachSeconds, gameOver, setIsGamePaused]);

  const formatTime = (secs) => {
    const mins = Math.floor(secs / 60);
    const rem = secs % 60;
    return `${mins}:${String(rem).padStart(2, "0")}`;
  };

  // Compute captured pieces dynamically
  const { capturedWhite, capturedBlack } = useMemo(
    () => calculateCapturedPieces(currentFen),
    [currentFen]
  );

  // Formatted Move History Pills
  const historyPills = useMemo(() => {
    const moves = session?.move_history || [];
    if (!moves.length) return ["Start"];
    return moves.slice(-6).map((entry, idx) => {
      const globalIdx = moves.length - moves.slice(-6).length + idx;
      const moveNum = Math.floor(globalIdx / 2) + 1;
      const isWhite = globalIdx % 2 === 0;
      const san = entry.move || entry.san || entry;
      return isWhite ? `[${moveNum}] ${san}` : `[${moveNum}] ...${san}`;
    });
  }, [session?.move_history]);

  const files = boardOrientation === "white"
    ? ["A", "B", "C", "D", "E", "F", "G", "H"]
    : ["H", "G", "F", "E", "D", "C", "B", "A"];
  const ranks = boardOrientation === "white"
    ? [8, 7, 6, 5, 4, 3, 2, 1]
    : [1, 2, 3, 4, 5, 6, 7, 8];

  return (
    <div className="flex-1 flex flex-col items-center justify-between h-full pt-1.5 pb-2 px-2 sm:px-4 overflow-hidden max-w-full">
      <div className="w-full mx-auto max-w-[min(98vw,1100px)] flex flex-col items-center justify-between h-full">

        {/* ─── TOP: ELITE CHESS STUDIO PLAYER HEADER & DUAL ANALOG CLOCKS ─── */}
        <div className="flex items-center justify-between gap-2 sm:gap-4 mb-1.5 sm:mb-2 w-full shrink-0">
          {/* Left Player: Tomasz (You) */}
          <div className="flex items-center gap-2 sm:gap-2.5 py-1.5 px-3 sm:px-3.5 rounded-xl bg-[#18222e]/95 border border-white/10 shadow-md backdrop-blur-md min-w-[120px] sm:min-w-[155px]">
            <div className="relative shrink-0">
              <img
                src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=80&h=80&fit=crop&crop=faces"
                alt="Player"
                className="w-8 h-8 sm:w-9 sm:h-9 rounded-full object-cover ring-2 ring-amber-500/80 shadow-sm"
              />
              {isPlayerTurn && !gameOver && (
                <div className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-500 ring-2 ring-[#18222e] animate-pulse" />
              )}
            </div>
            <div className="flex flex-col justify-center min-w-0">
              <span className="font-semibold text-slate-100 text-xs sm:text-sm tracking-tight truncate">
                {user?.name || "Tomasz"}
              </span>
              <span className="text-[10px] text-slate-400 font-medium tracking-wide">
                Master
              </span>
            </div>
          </div>

          {/* Center: Dual Circular Analog Chess Clocks (Wide Studio Edition) */}
          <div className="flex items-center gap-3 sm:gap-6 px-4 sm:px-6 py-1.5 sm:py-2 rounded-2xl bg-[#111822]/95 border border-white/10 shadow-lg min-w-[200px] sm:min-w-[260px] justify-center">
            {/* Player Analog Clock */}
            <div
              className={`relative flex flex-col items-center px-1.5 py-0.5 rounded-xl transition-all ${
                isPlayerTurn && !gameOver
                  ? "bg-cyan-500/15 ring-1 ring-cyan-500/50 shadow-[0_0_12px_rgba(56,189,248,0.25)]"
                  : "opacity-70"
              }`}
            >
              <span className="text-[8px] font-mono uppercase tracking-widest text-slate-400 font-bold mb-0.5 select-none">
                You
              </span>
              <div className="relative w-9 h-9 sm:w-10 sm:h-10 rounded-full border-2 border-slate-600 bg-slate-950 shadow-inner flex items-center justify-center">
                <div className="absolute inset-0.5 rounded-full border border-dashed border-slate-700/60" />
                <div
                  className="absolute w-0.5 h-3 sm:h-3.5 bg-cyan-400 rounded-full origin-bottom transition-transform duration-200"
                  style={{
                    bottom: "50%",
                    transform: `rotate(${(playerSeconds % 60) * 6}deg)`,
                    boxShadow: "0 0 5px #38bdf8",
                  }}
                />
                <div className="w-1.5 h-1.5 rounded-full bg-cyan-300 z-10" />
              </div>
              <span className="text-[11px] sm:text-xs font-mono text-cyan-300 mt-1 font-bold tracking-wider">
                {formatTime(playerSeconds)}
              </span>
            </div>

            {isPaused ? (
              <div className="flex flex-col items-center justify-center px-1">
                <span className="text-[8px] font-mono font-bold uppercase tracking-wider text-amber-400 bg-amber-500/20 border border-amber-500/40 px-1.5 py-0.5 rounded-full animate-pulse flex items-center gap-0.5">
                  <Pause className="w-2.5 h-2.5" />
                  PAUSED
                </span>
              </div>
            ) : (
              <div className="w-px h-9 sm:h-10 bg-white/10" />
            )}

            {/* Coach Analog Clock */}
            <div
              className={`relative flex flex-col items-center px-1.5 py-0.5 rounded-xl transition-all ${
                !isPlayerTurn && !gameOver
                  ? "bg-amber-500/15 ring-1 ring-amber-500/50 shadow-[0_0_12px_rgba(251,191,36,0.25)]"
                  : "opacity-70"
              }`}
            >
              <span className="text-[8px] font-mono uppercase tracking-widest text-slate-400 font-bold mb-0.5 select-none">
                Coach
              </span>
              <div className="relative w-9 h-9 sm:w-10 sm:h-10 rounded-full border-2 border-slate-600 bg-slate-950 shadow-inner flex items-center justify-center">
                <div className="absolute inset-0.5 rounded-full border border-dashed border-slate-700/60" />
                <div
                  className="absolute w-0.5 h-3 sm:h-3.5 bg-amber-400 rounded-full origin-bottom transition-transform duration-200"
                  style={{
                    bottom: "50%",
                    transform: `rotate(${(coachSeconds % 60) * 6}deg)`,
                    boxShadow: "0 0 5px #fbbf24",
                  }}
                />
                <div className="w-1.5 h-1.5 rounded-full bg-amber-300 z-10" />
              </div>
              <span className="text-[11px] sm:text-xs font-mono text-amber-300 mt-1 font-bold tracking-wider">
                {formatTime(coachSeconds)}
              </span>
            </div>
          </div>

          {/* Right Player: Coach Jessica */}
          <div className="flex items-center gap-2 sm:gap-2.5 py-1.5 px-3 sm:px-3.5 rounded-xl bg-[#18222e]/95 border border-cyan-500/25 shadow-md backdrop-blur-md min-w-[120px] sm:min-w-[155px] justify-end">
            <div className="flex flex-col justify-center text-right min-w-0">
              <div className="flex items-center justify-end gap-1">
                <span className="text-[8.5px] font-mono font-bold uppercase tracking-wider px-1 py-0.2 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                  GM
                </span>
                <span className="font-semibold text-slate-100 text-xs sm:text-sm tracking-tight truncate">
                  Coach Jessica
                </span>
              </div>
              <span className="text-[10px] font-medium tracking-wide">
                {coachThinking ? (
                  <span className="text-cyan-400 font-medium flex items-center justify-end gap-1 animate-pulse">
                    <Loader2 className="w-2.5 h-2.5 animate-spin" /> Analyzing
                  </span>
                ) : (
                  <span className="text-slate-400">Master · 2200</span>
                )}
              </span>
            </div>
            <div className="relative shrink-0">
              <img
                src="https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=80&h=80&fit=crop&crop=faces"
                alt="Coach Jessica"
                className="w-8 h-8 sm:w-9 sm:h-9 rounded-full object-cover ring-2 ring-cyan-500/80 shadow-[0_0_10px_rgba(6,182,212,0.3)]"
              />
              {!isPlayerTurn && !gameOver ? (
                <div className="absolute -bottom-0.5 -left-0.5 w-2.5 h-2.5 rounded-full bg-cyan-400 ring-2 ring-[#18222e] animate-ping" />
              ) : (
                <div className="absolute -bottom-0.5 -left-0.5 w-2 h-2 rounded-full bg-emerald-400 ring-2 ring-[#18222e]" />
              )}
            </div>
          </div>
        </div>

        {/* Paused state alert banner */}
        {isPaused && !showResumeModal && (
          <div className="flex items-center justify-between gap-3 px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-amber-500/20 via-amber-500/15 to-amber-500/20 border border-amber-500/35 text-amber-200 text-xs mb-1.5 shadow-lg backdrop-blur-md animate-in fade-in duration-200 w-full max-w-lg mx-auto">
            <div className="flex items-center gap-2">
              <Pause className="w-3.5 h-3.5 text-amber-400 shrink-0" />
              <span className="font-medium">Time paused — clocks are frozen.</span>
            </div>
            <button
              onClick={() => {
                setLocalPaused(false);
                setIsGamePaused?.(false);
                setStoredClock(session?.session_id, playerSeconds, coachSeconds, false);
                fetch(`${API}/coach/play/sync-clock`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  credentials: "include",
                  body: JSON.stringify({
                    session_id: session?.session_id,
                    user_time_remaining: playerSeconds,
                    coach_time_remaining: coachSeconds,
                    is_paused: false,
                  }),
                }).catch(() => {});
              }}
              data-testid="resume-banner-btn"
              className="px-2.5 py-1 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs flex items-center gap-1 shadow-sm transition-colors cursor-pointer"
            >
              <Play className="w-3 h-3 fill-current" />
              Resume
            </button>
          </div>
        )}

        {/* ─── MAIN MATCH CENTER: BOARD STAGE FLANKED BY CAPTURED PIECES TRAYS ─── */}
        <div className="flex items-center justify-center gap-2 sm:gap-3 w-full flex-1 min-h-0">
          {/* Left Flanking Tray: Captured Pieces (White captures) */}
          <div className="hidden lg:flex flex-col items-center justify-start p-2 sm:p-3 w-20 sm:w-24 lg:w-28 rounded-2xl bg-[#141d27]/90 border border-white/10 shadow-lg backdrop-blur-md self-stretch">
            <div className="flex items-center justify-between w-full px-1 mb-2.5 shrink-0">
              <span className="text-[8.5px] font-mono text-slate-400 uppercase tracking-widest font-bold select-none">
                Captures
              </span>
              <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded-md bg-white/10 text-amber-300">
                {capturedWhite.length}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-1.5 sm:gap-2 justify-items-center w-full overflow-y-auto flex-1 content-start">
              {capturedWhite.map((symbol, idx) => (
                <span
                  key={idx}
                  className="w-7 h-7 sm:w-8 sm:h-8 rounded-xl bg-white/5 border border-white/5 flex items-center justify-center text-base sm:text-lg text-slate-100 filter drop-shadow select-none hover:scale-125 transition-transform"
                >
                  {symbol}
                </span>
              ))}
            </div>
          </div>

          {/* Center: Metallic Slate Chessboard Chassis with Bezel Coordinates */}
          <div className="flex flex-col items-center justify-center max-w-[min(90vw,calc(100vh-190px),580px)] w-full">
            <div className="relative p-2 sm:p-2.5 rounded-2xl bg-[#161f2a] border border-white/15 shadow-[0_15px_45px_rgba(0,0,0,0.6),inset_0_1px_0_rgba(255,255,255,0.1)] w-full">
              {/* Outer Bezel Coordinates: Top A–H */}
              <div className="flex justify-between px-2 pb-0.5 text-[9px] font-mono text-slate-400 font-semibold tracking-wider select-none">
                {files.map((f) => (
                  <span key={f} className="w-[12.5%] text-center opacity-80">{f}</span>
                ))}
              </div>

              <div className="flex items-center gap-1 sm:gap-1.5">
                {/* Outer Bezel Coordinates: Left 8–1 */}
                <div className="flex flex-col justify-between py-0.5 text-[9px] font-mono text-slate-400 font-semibold select-none">
                  {ranks.map((r) => (
                    <span key={r} className="h-[12.5%] flex items-center justify-center opacity-80">{r}</span>
                  ))}
                </div>

                {/* Eval Bar */}
                <div className="w-3 sm:w-3.5 shrink-0 self-stretch rounded overflow-hidden" data-testid="coach-play-eval-bar">
                  <EvalBar
                    evaluation={evaluation}
                    userColor={selectedColor}
                    hidden={false}
                  />
                </div>

                {/* The Chessboard Stage (Elite Metallic Carbon Slate Theme) */}
                <div
                  className="studio-chess-theme experience-board-stage flex-1 relative rounded-xl sm:rounded-2xl overflow-hidden aspect-square border border-white/15 shadow-2xl"
                  data-testid="coach-play-board-stage"
                >
                  <LichessBoard
                    ref={boardRef}
                    fen={currentFen}
                    orientation={boardOrientation}
                    lastMove={lastMove}
                    arrows={coachArrows || []}
                    onMove={(moveData) => {
                      const canMoveInTeaching =
                        isInTeachingMode &&
                        activeLesson &&
                        lessonInstruction?.is_user_move;
                      if (
                        (canMoveInTeaching || (isPlayerTurn && !gameOver)) &&
                        moveData
                      ) {
                        makeMove(moveData.from, moveData.to);
                      }
                    }}
                    interactive={
                      (isInTeachingMode &&
                        activeLesson &&
                        lessonInstruction?.is_user_move) ||
                      (isPlayerTurn && !gameOver && !coachingLocked)
                    }
                    viewOnly={
                      !(
                        isInTeachingMode &&
                        activeLesson &&
                        lessonInstruction?.is_user_move
                      ) &&
                      (!isPlayerTurn || gameOver)
                    }
                    showDests={gameMode !== "play"}
                    disableArrows={gameMode === "play"}
                    moveClassification={moveClassification}
                    showCoordinates={false}
                  />

                  {/* Board lock overlay */}
                  <AnimatePresence>
                    {coachingLocked && !gameOver && !isInTeachingMode && (
                      <motion.div
                        key="board-lock-overlay"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{
                          duration: MOTION_TIMING.micro.duration / 1000,
                          ease: MOTION_TIMING.micro.easing,
                        }}
                        className="absolute inset-0 z-10 bg-black/40 backdrop-blur-[1px] pointer-events-none"
                        data-testid="board-lock-overlay"
                      />
                    )}
                  </AnimatePresence>

                  {/* Pedagogical Opportunity Hint Overlay */}
                  {hideEvalBar && isPlayerTurn && !gameOver && (
                    <div className="absolute top-2 left-1/2 -translate-x-1/2 z-10">
                      <div className="px-3 py-1.5 rounded-full bg-cyan-500/90 text-slate-950 text-xs font-bold shadow-lg animate-pulse">
                        <Lightbulb className="w-3 h-3 inline mr-1" />
                        Find the opportunity!
                      </div>
                    </div>
                  )}

                  {/* Lesson Complete Overlay */}
                  {lessonComplete && (
                    <div className="absolute inset-0 z-20 bg-background/80 backdrop-blur-md flex items-center justify-center p-4">
                      <div className="bg-[#16202c] border border-white/20 rounded-2xl shadow-2xl p-6 max-w-sm w-full text-center space-y-4 text-white">
                        <div className="mx-auto w-11 h-11 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 flex items-center justify-center text-2xl">
                          🎉
                        </div>
                        <div className="space-y-2">
                          <p className="text-[10.5px] uppercase tracking-[0.18em] text-cyan-400 font-semibold">
                            Trap complete
                          </p>
                          <p className="text-sm leading-relaxed text-slate-200 text-left">
                            {String(lessonComplete.message || "")
                              .replace(/^\s*trap complete[!.:\-\s]*/i, "")
                              .trim() || "Nicely played — that's the whole idea of this trap."}
                          </p>
                        </div>
                        <div className="flex gap-2 justify-center pt-1">
                          <Button
                            size="sm"
                            variant="outline"
                            className="flex-1 bg-white/5 border-white/15 text-slate-200 hover:bg-white/10"
                            onClick={() => handleExitLesson("continue_game", {})}
                          >
                            Continue Game
                          </Button>
                          <Button
                            size="sm"
                            className="flex-1 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold"
                            onClick={() => handleExitLesson("new_game", {})}
                          >
                            Next Lesson
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Outer Bezel Coordinates: Right 8–1 */}
                <div className="flex flex-col justify-between py-0.5 text-[9px] font-mono text-slate-400 font-semibold select-none">
                  {ranks.map((r) => (
                    <span key={r} className="h-[12.5%] flex items-center justify-center opacity-80">{r}</span>
                  ))}
                </div>
              </div>

              {/* Outer Bezel Coordinates: Bottom A–H */}
              <div className="flex justify-between px-2 pt-0.5 text-[9px] font-mono text-slate-400 font-semibold tracking-wider select-none">
                {files.map((f) => (
                  <span key={f} className="w-[12.5%] text-center opacity-80">{f}</span>
                ))}
              </div>
            </div>
          </div>

          {/* Right Flanking Tray: Captured Pieces (Black captures) */}
          <div className="hidden lg:flex flex-col items-center justify-start p-2 sm:p-3 w-20 sm:w-24 lg:w-28 rounded-2xl bg-[#141d27]/90 border border-white/10 shadow-lg backdrop-blur-md self-stretch">
            <div className="flex items-center justify-between w-full px-1 mb-2.5 shrink-0">
              <span className="text-[8.5px] font-mono text-slate-400 uppercase tracking-widest font-bold select-none">
                Captures
              </span>
              <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded-md bg-white/10 text-cyan-300">
                {capturedBlack.length}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-1.5 sm:gap-2 justify-items-center w-full overflow-y-auto flex-1 content-start">
              {capturedBlack.map((symbol, idx) => (
                <span
                  key={idx}
                  className="w-7 h-7 sm:w-8 sm:h-8 rounded-xl bg-white/5 border border-white/5 flex items-center justify-center text-base sm:text-lg text-slate-300 filter drop-shadow select-none hover:scale-125 transition-transform"
                >
                  {symbol}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* ─── BOTTOM CONTROLS & MOVE HISTORY PILLS ─── */}
        <div className="flex flex-wrap items-center justify-between gap-2 mt-1.5 sm:mt-2 w-full shrink-0">
          {/* Quick Toolbar */}
          <div className="flex items-center gap-1 sm:gap-1.5 p-1 px-2 rounded-xl bg-[#18222e]/95 border border-white/10 shadow-md backdrop-blur-md">
            <Button
              variant="ghost"
              size="icon"
              onClick={flipBoard}
              className="h-7 w-7 text-slate-300 hover:text-white hover:bg-white/10 rounded-lg"
              title="Flip Board"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </Button>

            <Button
              variant="ghost"
              size="icon"
              onClick={() => {
                const next = !soundOff;
                setSoundOff(next);
                setMuted(next);
              }}
              data-testid="board-sound-toggle"
              className="h-7 w-7 text-slate-300 hover:text-white hover:bg-white/10 rounded-lg"
              title={soundOff ? "Sound Off" : "Sound On"}
            >
              {soundOff ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
            </Button>

            {!gameOver && (
              <>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => {
                    const next = !isPaused;
                    setLocalPaused(next);
                    setIsGamePaused?.(next);
                    setStoredClock(session?.session_id, playerSeconds, coachSeconds, next);
                    fetch(`${API}/coach/play/sync-clock`, {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      credentials: "include",
                      body: JSON.stringify({
                        session_id: session?.session_id,
                        user_time_remaining: playerSeconds,
                        coach_time_remaining: coachSeconds,
                        is_paused: next,
                      }),
                    }).catch(() => {});
                  }}
                  data-testid="pause-board-btn"
                  className={`h-7 w-7 rounded-lg transition-all ${
                    isPaused
                      ? "text-cyan-300 bg-cyan-500/20 hover:bg-cyan-500/30 ring-1 ring-cyan-400/50"
                      : "text-slate-400 hover:text-cyan-300 hover:bg-cyan-500/10"
                  }`}
                  title={isPaused ? "Resume Time" : "Pause Time"}
                >
                  {isPaused ? <Play className="w-3.5 h-3.5 fill-current text-cyan-400" /> : <Pause className="w-3.5 h-3.5" />}
                </Button>

                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setShowRestartConfirm(true)}
                  data-testid="restart-board-btn"
                  className="h-7 w-7 text-slate-400 hover:text-amber-400 hover:bg-amber-500/10 rounded-lg"
                  title="Restart Game"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </Button>

                <Button
                  variant="ghost"
                  size="icon"
                  onClick={resignGame}
                  data-testid="resign-btn"
                  className="h-7 w-7 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg"
                  title="Resign Game"
                >
                  <Flag className="w-3.5 h-3.5" />
                </Button>
              </>
            )}
          </div>

          {/* Move History Pills */}
          <div className="flex items-center gap-1.5 p-1 px-2.5 rounded-xl bg-[#18222e]/95 border border-white/10 shadow-md backdrop-blur-md overflow-x-auto max-w-full">
            <span className="text-[9.5px] font-mono uppercase tracking-wider text-slate-400 font-bold mr-1">
              History
            </span>
            {historyPills.map((pill, idx) => {
              const isLast = idx === historyPills.length - 1;
              return (
                <span
                  key={idx}
                  className={`text-xs font-mono px-2 py-0.5 rounded-lg border whitespace-nowrap transition-all ${
                    isLast
                      ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/40 font-bold shadow-[0_0_8px_rgba(56,189,248,0.25)]"
                      : "bg-white/5 text-slate-300 border-white/10 hover:bg-white/10"
                  }`}
                >
                  {pill}
                </span>
              );
            })}
          </div>
        </div>

        {/* Pre-Move Checklist */}
        {session && showChecklist && isPlayerTurn && !gameOver && !isInTeachingMode && (
          <div className="mt-3">
            <PreMoveChecklist
              moveNumber={Math.floor((session?.move_history?.length || 0) / 2) + 1}
              hasCastled={hasCastled}
              developedPieces={developedPieces}
              playerWeaknesses={playerWeaknesses}
              isPlayerTurn={isPlayerTurn}
              onDismiss={() => setShowChecklist(false)}
              compact={true}
            />
          </div>
        )}

        {/* Post-game actions */}
        {gameOver && !unifiedExperience && (
          <div className="flex items-center justify-center gap-2 mt-4">
            <Button
              size="sm"
              onClick={newGame}
              data-testid="new-game-btn"
              className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-mono text-xs font-bold uppercase tracking-wider shadow-[0_0_20px_rgba(56,189,248,0.4)] transition-all"
            >
              <Play className="w-4 h-4 mr-1" />
              New Game
            </Button>
          </div>
        )}
      </div>

      {/* Restart confirmation modal */}
      {showRestartConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="w-full max-w-sm rounded-2xl border border-white/20 bg-gradient-to-b from-[#1b2633] to-[#111822] p-6 text-white shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-400 shrink-0">
                <RotateCcw className="w-5 h-5" />
              </div>
              <div>
                <h4 className="font-serif text-lg font-bold text-white">Restart Game?</h4>
                <p className="text-xs text-slate-300 mt-0.5">Start fresh from move 1 with Coach Jessica?</p>
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowRestartConfirm(false)}
                className="text-xs text-slate-300 hover:text-white"
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={() => {
                  setShowRestartConfirm(false);
                  if (restartGame) {
                    restartGame();
                  } else {
                    newGame();
                  }
                }}
                data-testid="confirm-restart-btn"
                className="text-xs font-bold bg-amber-500 hover:bg-amber-400 text-slate-950 px-4"
              >
                Yes, Restart
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
});

export default CoachPlayBoard;
