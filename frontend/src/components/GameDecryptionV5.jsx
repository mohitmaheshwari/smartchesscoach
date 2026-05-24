/**
 * GameDecryptionV5.jsx - "Thinking Simulator"
 * 
 * Vision:
 * - Coach on EVERY move (user + opponent)
 * - Show PLANS (transferable knowledge, not just moves)
 * - "I understand" button for concept acknowledgment
 * - Clickable moves to show the future on the board
 * - Simple, 1200-friendly language
 */

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { Chess } from "chess.js";
import LichessBoard from "@/components/LichessBoard";
import ClickableLine, { extractMovesFromText } from "@/components/ClickableLine";
import ClickableCaption from "@/components/ClickableCaption";
import TruthHeadline from "@/components/TruthHeadline";
import PlayerDecryption from "@/components/PlayerDecryption";
import PatternEvidence from "@/components/PatternEvidence";
import GameMoments from "@/components/GameMoments";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { toast } from "sonner";
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  AlertTriangle,
  CheckCircle2,
  Lightbulb,
  Target,
  ThumbsDown,
  Send,
  X,
  Loader2,
  BookOpen,
  Brain,
  Eye,
  Swords,
  GraduationCap,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Zap,
  Trophy,
  ArrowRight,
  Check
} from "lucide-react";
import { InlineFlag } from "@/components/shared/FlagMoveDialog";
import { API } from "@/App";

/**
 * Generate POSITION-SPECIFIC reflection options.
 * Uses the actual pieces, squares, and threats from this position.
 */
function _generateThoughtOptions(move, posCommentary) {
  const options = [];
  const san = move.move_san || "";
  const phase = move.phase || "";

  // 1. What the move ACTUALLY does — from the move itself
  if (move.plan?.goal) {
    options.push({ text: move.plan.goal, category: "intention" });
  }

  // 2. If it's a capture — name the piece and square
  if (san.includes("x") && move.narrative) {
    const captureMatch = move.narrative.match(/(?:takes?|captures?|took)\s+(?:the\s+)?(\w+\s+on\s+[a-h][1-8])/i);
    if (captureMatch) {
      options.push({ text: `I wanted to take the ${captureMatch[1]}`, category: "piece_safety" });
    }
  }

  // 3. From position commentary — specific observations
  if (posCommentary?.observations) {
    for (const obs of posCommentary.observations.slice(0, 2)) {
      const title = (obs.title || "").toLowerCase();
      const desc = obs.description || "";
      const shortDesc = desc.split(".")[0].toLowerCase();
      if (title.includes("undefended") || title.includes("hanging")) {
        options.push({ text: `I didn't see that ${shortDesc}`, category: "piece_safety" });
      } else if (title.includes("pin")) {
        options.push({ text: `I missed the pin — ${shortDesc}`, category: "tactical_vision" });
      } else if (title.includes("fork")) {
        options.push({ text: `I didn't see the fork — ${shortDesc}`, category: "tactical_vision" });
      } else if (title.includes("overloaded")) {
        options.push({ text: `I didn't notice ${shortDesc}`, category: "calculation" });
      } else if (title.includes("threat") || title.includes("attack")) {
        options.push({ text: `I didn't notice ${shortDesc}`, category: "threat_awareness" });
      }
    }
  }

  // 4. From the threat field — what opponent was threatening
  if (move.threat) {
    options.push({ text: `I didn't see their ${move.threat} was threatening`, category: "threat_awareness" });
  }

  // 5. From the best move — what the user SHOULD have done
  if ((move.best_move_san || move.best_move) && move.plan?.better_approach) {
    const best = move.best_move_san || move.best_move;
    options.push({ text: `I didn't consider ${best} — ${move.plan.better_approach.split(".")[0].toLowerCase()}`, category: "calculation" });
  }

  // 6. Position-specific plan from commentary
  if (posCommentary?.plan) {
    const planShort = posCommentary.plan.split(".")[0].toLowerCase();
    if (planShort.length > 15 && !options.some(o => o.text.includes(planShort.slice(0, 20)))) {
      options.push({ text: `I didn't see that the position needed: ${planShort}`, category: "planning" });
    }
  }

  // 7. Opening theory — only if actually in opening
  if (phase === "opening" && move.opening_name) {
    options.push({ text: `I didn't know the theory for the ${move.opening_name}`, category: "opening_knowledge" });
  }

  // Only genuine options — no padding, no forced minimums
  // Deduplicate and clean
  const seen = new Set();
  return options.filter(o => {
    const t = o.text?.trim();
    if (!t || t.length < 10 || seen.has(t)) return false;
    seen.add(t);
    return true;
  });
}


const GameDecryptionV5 = ({ gameId, analysis, pgn, userColor, onBack, coachSummary, coreLesson, gameResult, opponentName, coachReview, onPlayBestLine }) => {
  // ?show_facts=1 enables a per-move JSON-fact panel for caption authoring
  // (Parth's templating round). Off by default — invisible to normal users.
  const showFacts = typeof window !== "undefined" && new URLSearchParams(window.location.search).get("show_facts") === "1";
  const [factsByMove, setFactsByMove] = useState({});
  const [decryptionData, setDecryptionData] = useState(null);
  const [cctNarrative, setCctNarrative] = useState(null);
  const [truthLine, setTruthLine] = useState(null);
  const [playerDecryption, setPlayerDecryption] = useState(null);
  const [decryptionBlock, setDecryptionBlock] = useState(null);
  const [patternEvidence, setPatternEvidence] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentMoveIndex, setCurrentMoveIndex] = useState(-1);
  const [boardFen, setBoardFen] = useState("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackText, setFeedbackText] = useState("");
  const [feedbackRuleName, setFeedbackRuleName] = useState(null);
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [acknowledgedConcepts, setAcknowledgedConcepts] = useState(new Set());
  const [habitsReport, setHabitsReport] = useState(null);
  const [posCommentary, setPosCommentary] = useState({}); // {moveIndex: commentary}
  const [showingFutureMoves, setShowingFutureMoves] = useState(false);
  const [futureMoveIndex, setFutureMoveIndex] = useState(0);
  const [highlights, setHighlights] = useState([]);
  const [arrows, setArrows] = useState([]);
  
  // "What were you thinking?" state
  const [userThoughts, setUserThoughts] = useState({});
  const [thoughtInputOpen, setThoughtInputOpen] = useState({});
  const [savingThought, setSavingThought] = useState(null);
  
  // "Show my plan" interactive mode state
  const [planMode, setPlanMode] = useState(false);
  const [planMoves, setPlanMoves] = useState([]);
  const [planBoard, setPlanBoard] = useState(null);
  const [planReasoning, setPlanReasoning] = useState("");
  const [analyzingPlan, setAnalyzingPlan] = useState(false);
  const [planAnalysis, setPlanAnalysis] = useState(null);
  
  const boardRef = useRef(null);
  const containerRef = useRef(null);

  // v78.3 (2026-05-24) — "Play this line" state. Mohit caught the
  // button was missing on the Lab page. Track which move's playback
  // is active + the current step so the step panel highlights the
  // correct cell.
  const [coachLinePlaybackIdx, setCoachLinePlaybackIdx] = useState(-1);
  const [coachLineStepIndex, setCoachLineStepIndex] = useState(-1);

  useEffect(() => { fetchDecryptionData(); }, [gameId]);

  // v78.3 — cancel in-flight playback when the user navigates moves.
  useEffect(() => {
    if (coachLinePlaybackIdx !== -1 && coachLinePlaybackIdx !== currentMoveIndex) {
      if (boardRef.current?.cancelVariation) {
        boardRef.current.cancelVariation();
      }
      setCoachLinePlaybackIdx(-1);
      setCoachLineStepIndex(-1);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentMoveIndex]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
      switch (e.key) {
        case 'ArrowRight': e.preventDefault(); goForward(); break;
        case 'ArrowLeft': e.preventDefault(); goBackward(); break;
        case 'ArrowUp': e.preventDefault(); goToStart(); break;
        case 'ArrowDown': e.preventDefault(); goToEnd(); break;
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [decryptionData, currentMoveIndex]);

  const fetchDecryptionData = async (isRetry = false) => {
    try {
      if (!isRetry) setLoading(true);
      setError(null);
      
      // Use V5 endpoint
      const res = await fetch(`${API}/coach/decryption/v5/${gameId}`, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to fetch decryption data");
      const data = await res.json();
      
      if (data.status === "generating") {
        setLoading(true);
        setTimeout(() => fetchDecryptionData(true), 5000);
        return;
      }
      
      if (data.error || !data.decryption_data) {
        setError(data.error || "Decryption data not available");
        return;
      }

      // Path B: fetch per-move deterministic captions from the new
      // pipeline. We merge them into decryption_data, replacing the V5
      // `narrative` field so the rest of the UI (which reads
      // move.narrative) gets the deterministic caption automatically.
      // Same principle as Option B (decryption_block override) but
      // applied to EVERY move, not just critical moments.
      let perMoveData = data.decryption_data;
      try {
        const pmRes = await fetch(`${API}/coach/decryption/per-move/${gameId}`, { credentials: "include" });
        if (pmRes.ok) {
          const pmJson = await pmRes.json();
          const captionByKey = new Map();
          for (const c of (pmJson.captions || [])) {
            captionByKey.set(`${c.move_number}|${c.move_san}`, c);
          }
          perMoveData = data.decryption_data.map((m) => {
            const cap = captionByKey.get(`${m.move_number}|${m.move_san}`);
            // Teaching cue + principle id flow through regardless of
            // whether the base caption text is present. The cue is
            // the new named-principle habit reminder (≤20 words).
            const principle_cue = (cap && cap.principle_cue) || "";
            const principle_id = (cap && cap.principle_id) || null;
            // TIER 3 shape pattern (visual danger language). Highest-
            // priority engine-verified pattern in this position; at
            // most one per move, suppressed once-per-game in V5 wiring.
            const shape_pattern_id = (cap && cap.shape_pattern_id) || null;
            const shape_pattern_name = (cap && cap.shape_pattern_name) || "";
            const shape_pattern_desc = (cap && cap.shape_pattern_desc) || "";
            const shape_pattern_targets = (cap && cap.shape_pattern_targets) || [];
            // v78.2 (2026-05-23) — Mohit: "captions are loaded but UI
            // doesn't show anything." The V5 service writes the fresh
            // caption to m.caption (with caption_llm sibling). The
            // legacy per-move endpoint /coach/decryption/per-move/X
            // serves a different (older) caption surface — when its
            // text is empty (cap && !cap.text path), this branch was
            // setting narrative="" and silently dropping the v78
            // caption. Fix: prefer m.caption / m.caption_llm whenever
            // they're populated, regardless of what the per-move
            // endpoint returns. Per-move endpoint becomes the
            // FALLBACK, not the override.
            const fresh_caption = m.caption || "";
            if (fresh_caption) {
              return {
                ...m,
                narrative: fresh_caption,
                _caption_source: "v5_caption_field",
                principle_cue,
                principle_id,
                shape_pattern_id,
                shape_pattern_name,
                shape_pattern_desc,
                shape_pattern_targets,
              };
            }
            if (cap && cap.text) {
              return {
                ...m,
                narrative: cap.text,
                _caption_source: cap.source,
                principle_cue,
                principle_id,
                shape_pattern_id,
                shape_pattern_name,
                shape_pattern_desc,
                shape_pattern_targets,
              };
            }
            // Both V5 caption and per-move endpoint empty = honest 'no comment'.
            if (cap && !cap.text) {
              return {
                ...m,
                narrative: "",
                _caption_source: "silent",
                principle_cue,
                principle_id,
                shape_pattern_id,
                shape_pattern_name,
                shape_pattern_desc,
                shape_pattern_targets,
              };
            }
            return m;
          });
        }
      } catch (e) {
        console.warn("Per-move caption fetch failed; falling back to V5 narrative:", e);
      }
      setDecryptionData(perMoveData);

      // Authoring mode: pull raw per-move facts when ?show_facts=1 is set.
      // Backend endpoint added 2026-05-13 for Parth's template-authoring round.
      if (showFacts) {
        try {
          const fRes = await fetch(`${API}/coach/decryption/facts/${gameId}`, { credentials: "include" });
          if (fRes.ok) {
            const fJson = await fRes.json();
            const byKey = {};
            for (const m of (fJson.moves || [])) {
              byKey[`${m.move_number}|${m.move_san}`] = m;
            }
            setFactsByMove(byKey);
          }
        } catch (e) {
          console.warn("Facts fetch failed (show_facts mode):", e);
        }
      }

      // Store habits report if available
      if (data.habits_report) {
        setHabitsReport(data.habits_report);
      }

      // CCT discipline narrative — null/missing means "no signal worth
      // narrating", show nothing. When present, it's a coach-voice line
      // celebrating either a held-initiative-after-miss segment or a
      // strong CCT streak.
      if (data.cct_narrative) {
        setCctNarrative(data.cct_narrative);
      }

      // Voice layer (3 surfaces). All null when the user won.
      // truth_line       — 3-line Coach Voice headline
      // player_decryption — Story / Pattern / Carry-forward (identity)
      // decryption_block  — Plan Decryption (board-grounded prose)
      if (data.truth_line) {
        setTruthLine(data.truth_line);
      }
      if (data.player_decryption) {
        setPlayerDecryption(data.player_decryption);
      }
      if (data.decryption_block) {
        setDecryptionBlock(data.decryption_block);
      }
      if (data.pattern_evidence) {
        setPatternEvidence(data.pattern_evidence);
      }
      
      // Pre-load acknowledged concepts
      if (data.decryption_data) {
        const acked = new Set();
        data.decryption_data.forEach(m => {
          if (m.already_acknowledged && m.concept_id) {
            acked.add(m.concept_id);
          }
        });
        setAcknowledgedConcepts(acked);
      }
      
      // Fetch existing user thoughts for this game
      fetchUserThoughts();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  
  // Fetch existing thoughts
  const fetchUserThoughts = async () => {
    try {
      const res = await fetch(`${API}/games/${gameId}/thoughts`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        if (data.thoughts?.length > 0) {
          const thoughts = {};
          data.thoughts.forEach(t => {
            thoughts[t.move_number] = { text: t.thought_text, saved: true };
          });
          setUserThoughts(thoughts);
        }
      }
    } catch (e) {
      console.log("Could not fetch existing thoughts");
    }
  };
  
  // Save user thought for a move
  const saveThought = async (moveNumber, fen, category) => {
    const thoughtText = userThoughts[moveNumber]?.text?.trim();
    const thoughtCategory = category || userThoughts[moveNumber]?.category || null;
    if (!thoughtText) {
      toast.error("Please enter your thought");
      return;
    }

    setSavingThought(moveNumber);
    try {
      const res = await fetch(`${API}/games/${gameId}/thought`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          move_number: moveNumber,
          fen: fen || "",
          thought_text: thoughtText,
          weakness_category: thoughtCategory,
        })
      });
      
      if (!res.ok) throw new Error("Failed to save");
      
      setUserThoughts(prev => ({
        ...prev,
        [moveNumber]: { text: thoughtText, saved: true }
      }));
      setThoughtInputOpen(prev => ({ ...prev, [moveNumber]: false }));
      toast.success("Thanks! This helps improve coaching.");
    } catch (e) {
      toast.error("Could not save thought");
    } finally {
      setSavingThought(null);
    }
  };

  // ─── PLAN MODE FUNCTIONS ───────────────────────────────────────────────
  
  // Start plan mode - user will play their intended moves
  const startPlanMode = (moveData) => {
    if (!moveData?.fen_after) return;
    
    // Initialize chess.js with position after user's move
    const chess = new Chess(moveData.fen_after);
    setPlanBoard(chess);
    setPlanMoves([]);
    setPlanReasoning("");
    setPlanAnalysis(null);
    setPlanMode(true);
  };
  
  // Handle move made in plan mode
  const handlePlanMove = (from, to, promotion) => {
    if (!planBoard) return false;
    
    try {
      const move = planBoard.move({ from, to, promotion: promotion || 'q' });
      if (move) {
        setPlanMoves(prev => [...prev, move.san]);
        // Update board state (force re-render)
        setPlanBoard(new Chess(planBoard.fen()));
        return true;
      }
    } catch (e) {
      console.log("Invalid move in plan mode");
    }
    return false;
  };
  
  // Undo last plan move
  const undoPlanMove = () => {
    if (!planBoard || planMoves.length === 0) return;
    
    planBoard.undo();
    setPlanMoves(prev => prev.slice(0, -1));
    setPlanBoard(new Chess(planBoard.fen()));
  };
  
  // Cancel plan mode
  const cancelPlanMode = () => {
    setPlanMode(false);
    setPlanMoves([]);
    setPlanBoard(null);
    setPlanReasoning("");
    setPlanAnalysis(null);
  };
  
  // Submit plan for analysis
  const submitPlan = async (moveData) => {
    if (planMoves.length === 0) {
      toast.error("Play at least one move to show your plan");
      return;
    }
    
    setAnalyzingPlan(true);
    
    try {
      const res = await fetch(`${API}/analyze-plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          fen: moveData.fen_before,
          user_move: moveData.move_san,
          plan_moves: planMoves,
          plan_reasoning: planReasoning
        })
      });
      
      if (!res.ok) throw new Error("Analysis failed");
      
      const data = await res.json();
      
      if (data.success && data.analysis) {
        setPlanAnalysis(data.analysis);
        setPlanMode(false);
        
        // Show the critical move on the board if available
        if (data.analysis.arrows?.length > 0) {
          setArrows(data.analysis.arrows.map(a => ({
            orig: a.from,
            dest: a.to,
            brush: a.color || 'red'
          })));
        }
      } else {
        toast.error(data.error || "Could not analyze plan");
      }
    } catch (e) {
      toast.error("Failed to analyze plan");
    } finally {
      setAnalyzingPlan(false);
    }
  };

  const goForward = useCallback(() => {
    if (!decryptionData || currentMoveIndex >= decryptionData.length - 1) return;
    resetFutureView();
    const i = currentMoveIndex + 1;
    setCurrentMoveIndex(i);
    setBoardFen(decryptionData[i].fen_after);

    const m = decryptionData[i];
    if (m.highlight_squares?.length) {
      setHighlights(m.highlight_squares);
    } else {
      setHighlights([]);
    }
  }, [decryptionData, currentMoveIndex]);

  const goBackward = useCallback(() => {
    if (!decryptionData || currentMoveIndex < 0) return;
    resetFutureView();
    const i = currentMoveIndex - 1;
    setCurrentMoveIndex(i);
    setBoardFen(i === -1 ? "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" : decryptionData[i].fen_after);
    setHighlights([]);
  }, [decryptionData, currentMoveIndex]);

  const goToStart = useCallback(() => {
    resetFutureView();
    setCurrentMoveIndex(-1);
    setBoardFen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
    setHighlights([]);
  }, []);

  const goToEnd = useCallback(() => {
    if (!decryptionData?.length) return;
    resetFutureView();
    const i = decryptionData.length - 1;
    setCurrentMoveIndex(i);
    setBoardFen(decryptionData[i].fen_after);
    setHighlights([]);
  }, [decryptionData]);

  const goToMove = useCallback((i) => {
    if (!decryptionData || i < -1 || i >= decryptionData.length) return;
    resetFutureView();
    setCurrentMoveIndex(i);
    setBoardFen(i === -1 ? "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" : decryptionData[i].fen_after);
    
    if (i >= 0 && decryptionData[i].highlight_squares?.length) {
      setHighlights(decryptionData[i].highlight_squares);
    } else {
      setHighlights([]);
    }
  }, [decryptionData]);

  const resetFutureView = () => {
    setShowingFutureMoves(false);
    setFutureMoveIndex(0);
    setArrows([]);
  };

  // Play future moves on the board (clickable line feature) - from position AFTER user's move
  const showFutureMoves = useCallback((moves, upToIndex) => {
    if (!decryptionData || currentMoveIndex < 0) return;
    
    const currentMove = decryptionData[currentMoveIndex];
    const startFen = currentMove.fen_after;
    
    try {
      const chess = new Chess(startFen);
      
      // Play moves up to the clicked one
      for (let i = 0; i <= upToIndex && i < moves.length; i++) {
        const move = chess.move(moves[i]);
        if (!move) break;
      }
      
      setBoardFen(chess.fen());
      setShowingFutureMoves(true);
      setFutureMoveIndex(upToIndex);
      
      // Draw arrow for last move
      const history = chess.history({ verbose: true });
      if (history.length > 0) {
        const lastMove = history[history.length - 1];
        setArrows([[lastMove.from, lastMove.to, "green"]]);
      }
    } catch (err) {
      console.error("Error showing future moves:", err);
    }
  }, [decryptionData, currentMoveIndex]);

  // Show ALTERNATIVE moves from position BEFORE the current move (for candidate moves)
  const showAlternativeMove = useCallback((move) => {
    if (!decryptionData || currentMoveIndex < 0) return;
    
    const currentMove = decryptionData[currentMoveIndex];
    const startFen = currentMove.fen_before; // Use position BEFORE the move!
    
    if (!startFen) {
      console.error("No fen_before available");
      return;
    }
    
    try {
      const chess = new Chess(startFen);
      const result = chess.move(move);
      
      if (!result) {
        console.error("Invalid move:", move, "from FEN:", startFen);
        return;
      }
      
      setBoardFen(chess.fen());
      setShowingFutureMoves(true);
      setFutureMoveIndex(0);
      
      // Draw arrow showing the alternative move
      setArrows([[result.from, result.to, "blue"]]);
    } catch (err) {
      console.error("Error showing alternative move:", err, move);
    }
  }, [decryptionData, currentMoveIndex]);

  const resetToCurrentMove = useCallback(() => {
    if (!decryptionData || currentMoveIndex < 0) return;
    setBoardFen(decryptionData[currentMoveIndex].fen_after);
    setShowingFutureMoves(false);
    setFutureMoveIndex(0);
    setArrows([]);
  }, [decryptionData, currentMoveIndex]);

  // Acknowledge a concept
  const acknowledgeConceptHandler = async (conceptId) => {
    try {
      const res = await fetch(`${API}/coach/decryption/acknowledge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ concept_id: conceptId })
      });
      
      if (res.ok) {
        setAcknowledgedConcepts(prev => new Set([...prev, conceptId]));
        toast.success("Got it! I'll remember you understand this.");
      }
    } catch (err) {
      toast.error("Failed to save acknowledgment");
    }
  };

  const handleSubmitFeedback = async () => {
    if (!feedbackText.trim() || currentMoveIndex < 0) return;
    const m = decryptionData[currentMoveIndex];
    try {
      setSubmittingFeedback(true);
      // Post to /feedback/flag (writes to move_feedback) so the admin queue
      // has full diagnostics + rule_name. The old /coach/decryption/feedback
      // wrote to coaching_feedback with no rule context — insufficient for
      // the authoring queue to act on shape-pattern misfires.
      const res = await fetch(`${API}/feedback/flag`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          source: "lab",
          game_id: gameId,
          move_number: m.move_number,
          fen: m.fen_before || "",
          move_san: m.move_san || null,
          // coaching_text: the narrative the user saw (primary caption).
          // When the user flags a secondary (shape pattern) we also send
          // rule_name so the queue knows which layer misfired.
          coaching_text: m.narrative || "",
          user_note: feedbackText.trim(),
          severity: m.severity || null,
          cp_loss: m.cp_loss != null ? m.cp_loss : null,
          best_move: m.best_move || null,
          eval_before: m.eval_before != null ? m.eval_before : null,
          eval_after: m.eval_after != null ? m.eval_after : null,
          phase: m.phase || null,
          component: "GameDecryptionV5",
          concept_id: "not_helpful_flag",
          // rule_name: tracks which caption layer the user found inaccurate.
          // When a shape pattern (secondary narrative) is visible, default to
          // flagging that; otherwise flag the primary rule_name.
          rule_name: feedbackRuleName || m.rule_name || null,
          inaccuracy_reason: feedbackText.trim(),
        })
      });
      if (res.ok) {
        toast.success("Flagged — thanks for the report.");
        setFeedbackOpen(false);
        setFeedbackText("");
        setFeedbackRuleName(null);
      }
    } catch (err) {
      toast.error("Failed to send feedback");
    } finally {
      setSubmittingFeedback(false);
    }
  };

  const rawCurrentMove = currentMoveIndex >= 0 ? decryptionData?.[currentMoveIndex] : null;

  // Hybrid narrative source: prefer decryption_block.moments[].text over
  // the V5 per-move narrative when available. The decryption pipeline
  // produces deterministic, correctly-attributed captions (templates +
  // coach overrides) while the V5 narrative sometimes mis-attributes
  // the SAN — e.g., showing 'wins the bishop' on the played move when
  // it actually describes the engine's best move. See feedback
  // fb_2b99199d5617 (Parth Gilda, Rf8 vs Rxd8). decryption_block only
  // covers ~4 critical moments per game; for non-matched moves we fall
  // back to V5 narrative so analysis pages still have prose for every
  // move.
  // Defensive filter for V5 text fields. Returns true when the string
  // matches a known-bad pattern surfaced in Parth Gilda's May 2026
  // review (77 issues across narrative / consequence / better_approach
  // / your_plan_now / candidate_moves). Most of these patterns come
  // from older V5 code that's been replaced — but the strings live on
  // in cached game_analyses records. Frontend filter is the cheapest
  // defensive layer.
  const _isV5TextStale = (text, cpLoss) => {
    const n = (text || "").trim();
    if (!n) return false;
    const lower = n.toLowerCase();
    return (
      // Cutesy piece names from older code.
      /\b(horsey|slicey|naughty knight|little soldier|boss knight)\b/i.test(n)
      // 'Sneaky! X creates a threat' overuse — fires on neutral moves.
      || /^sneaky!\s/i.test(n)
      // 'BOSS KNIGHT! ... monster ... hard to kick out' — childish framing.
      || (/\b(monster|boss)\b/i.test(n) && /hard to kick/i.test(n))
      // 'damn bad shit' — committed once.
      || /\bdamn bad\b/i.test(n)
      // 'X allows checkmate' when there's no actual forced mate.
      || (lower.includes("allows checkmate") && cpLoss != null && cpLoss < 1000)
      // Negative cp_loss + 'passive' — the move was actually good.
      || (cpLoss != null && cpLoss < 0 && lower.includes("passive"))
      // Generic context-blind platitudes.
      || /^make sure your pieces aren't on that diagonal/i.test(n)
      || /^recapture\? check if it's worth it first/i.test(n)
      || /^keep developing! castle if you haven't/i.test(n)
    );
  };

  const currentMove = useMemo(() => {
    if (!rawCurrentMove) return null;
    // decryption_block.moments[] override DISABLED — per-move endpoint
    // (which now sources from V5 caption pipeline, see backend commit
    // 13c1073b) is the single source of move-by-move text. LLM voice
    // moments live on their own surface (TruthHeadline / GameMoments),
    // also currently hidden for "tester sees only upgraded output."
    // Legacy plan-prose fields (consequence / better_approach /
    // your_plan_now) are nulled regardless of `_isV5TextStale` — they
    // are never rendered now (retire commit 13c1073b deleted the JSX),
    // so passing them through the filter is dead work. Candidate-move
    // SANs are preserved for the click-to-see-line buttons.
    const cleanedPlan = rawCurrentMove.plan
      ? {
          ...rawCurrentMove.plan,
          consequence: null,
          better_approach: null,
          transferable_learning: null,
          candidate_moves: (rawCurrentMove.plan.candidate_moves || []).map(c => ({
            ...c,
            idea: null,
          })),
        }
      : rawCurrentMove.plan;
    return {
      ...rawCurrentMove,
      narrative: rawCurrentMove.narrative || "",
      plan: cleanedPlan,
      your_plan_now: null,
      _narrative_source: "v5_caption",
    };
  }, [rawCurrentMove, decryptionBlock]);

  const orientation = userColor === "black" ? "black" : "white";

  // Fetch position commentary for mistake moves (lazy, one at a time)
  useEffect(() => {
    if (!currentMove || posCommentary[currentMoveIndex]) return;
    const sev = currentMove.severity;
    if (sev !== "blunder" && sev !== "mistake" && sev !== "inaccuracy") return;
    const fen = currentMove.fen_before || currentMove.fen;
    if (!fen) return;

    (async () => {
      try {
        const res = await fetch(`${API}/coach/play/position/read`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ fen, user_color: userColor }),
        });
        if (res.ok) {
          const data = await res.json();
          setPosCommentary(prev => ({ ...prev, [currentMoveIndex]: data }));
        } else {
          console.warn("[Decrypt] Position read failed:", res.status);
        }
      } catch (e) {
        console.warn("[Decrypt] Position read error:", e.message);
      }
    })();
  }, [currentMoveIndex, currentMove?.fen_before]);

  if (loading) return (
    <div className="flex flex-col items-center justify-center h-96" data-testid="decryption-loading">
      <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
      <span className="mt-3 text-gray-500">Your coach is analyzing every move...</span>
      <span className="mt-1 text-gray-400 text-sm">This takes about 45 seconds for V5 analysis</span>
    </div>
  );

  if (error) return (
    <div className="flex flex-col items-center justify-center h-96 text-center" data-testid="decryption-error">
      <AlertTriangle className="w-12 h-12 text-amber-400 mb-4" />
      <p className="text-gray-600 mb-2">{error}</p>
      <Button variant="outline" onClick={() => fetchDecryptionData()} className="mt-4">Try Again</Button>
    </div>
  );

  return (
    <>
      {/* Voice layer, post-game. Hidden when user won.

          Locked 2026-05-04 — collapsed from three sections to ONE:
          Truth IS the post-game read, no Player Decryption block on
          default surface. Plan Decryption stays gated under "Show me why".
          Pattern Evidence (visual proof on a mini board) shipped
          2026-05-05 — rendered when the game has tracked-pattern
          evidence (king-safety / piece-safety so far). */}
      {/* TruthHeadline stays retired (LLM voice, separate workstream).
          GameMoments restored 2026-05-20 (Mohit): the 3-candidate
          turning-point puzzles is the load-bearing "highlights with
          options" UX. PatternEvidence stays — factual mini-board. */}
      {false && <TruthHeadline truthLine={truthLine} decryptionBlock={decryptionBlock} userColor={userColor} />}
      <PatternEvidence patternEvidence={patternEvidence} userColor={userColor} />
      <GameMoments moments={decryptionBlock?.moments || []} userColor={userColor} gameId={gameId} />

    <div ref={containerRef} className="flex flex-col lg:flex-row gap-4 p-4" data-testid="game-decryption-v5">
      {/* LEFT: Board + Controls */}
      <div className="lg:w-1/2 space-y-4">
        <div className="aspect-square max-w-[500px] mx-auto relative">
          <LichessBoard
            ref={boardRef}
            fen={planMode && planBoard ? planBoard.fen() : boardFen}
            orientation={orientation}
            viewOnly={!planMode}
            onMove={planMode ? handlePlanMove : undefined}
            lastMove={!planMode && currentMove && !showingFutureMoves ? getLastMoveSquares(currentMove) : null}
            arrows={arrows}
            highlights={highlights}
            moveClassification={(() => {
              if (!currentMove || planMode || showingFutureMoves) return null;
              const squares = getLastMoveSquares(currentMove);
              if (!squares) return null;

              let severity = currentMove.severity;

              // For opponent moves without severity, derive from cp_loss
              if ((!severity || severity === "context" || severity === "good") && !currentMove.is_user_move) {
                const cpLoss = Math.abs(currentMove.cp_loss || 0);
                if (cpLoss >= 200) severity = "blunder";
                else if (cpLoss >= 100) severity = "mistake";
                else if (cpLoss >= 50) severity = "inaccuracy";
                else if (cpLoss <= 5) severity = "best";
                else severity = "good";
              }

              if (!severity || severity === "context") return null;
              return { square: squares[1], type: severity };
            })()}
          />
          
          {/* Plan mode indicator */}
          {planMode && (
            <div className="absolute top-2 left-2 bg-cyan-500/90 text-gray-900 text-xs px-2 py-1 rounded flex items-center gap-1 animate-pulse">
              <Swords className="w-3 h-3" />
              Play your intended moves
            </div>
          )}
          
          {/* Future moves indicator */}
          {showingFutureMoves && !planMode && (
            <div className="absolute top-2 left-2 bg-emerald-500/90 text-gray-900 text-xs px-2 py-1 rounded flex items-center gap-1">
              <Eye className="w-3 h-3" />
              Showing future line
              <button 
                onClick={resetToCurrentMove}
                className="ml-2 bg-white/20 hover:bg-white/30 px-1.5 py-0.5 rounded text-xs"
              >
                Reset
              </button>
            </div>
          )}
        </div>

        <div className="flex items-center justify-center gap-2">
          <Button variant="outline" size="icon" onClick={goToStart} disabled={currentMoveIndex === -1} data-testid="btn-go-start">
            <ChevronsLeft className="w-4 h-4" />
          </Button>
          <Button variant="outline" size="icon" onClick={goBackward} disabled={currentMoveIndex === -1} data-testid="btn-go-back">
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <span className="px-4 text-sm text-gray-500 min-w-[100px] text-center">
            {currentMoveIndex === -1 ? "Start" : `Move ${currentMove?.move_number || ""}`}
            {currentMove && !currentMove.is_user_move && " (opp)"}
          </span>
          <Button variant="outline" size="icon" onClick={goForward} disabled={!decryptionData || currentMoveIndex >= decryptionData.length - 1} data-testid="btn-go-forward">
            <ChevronRight className="w-4 h-4" />
          </Button>
          <Button variant="outline" size="icon" onClick={goToEnd} disabled={!decryptionData || currentMoveIndex >= decryptionData.length - 1} data-testid="btn-go-end">
            <ChevronsRight className="w-4 h-4" />
          </Button>
        </div>

        <MoveListV5 
          decryptionData={decryptionData} 
          currentMoveIndex={currentMoveIndex} 
          onMoveClick={goToMove} 
        />
      </div>

      {/* RIGHT: Coaching */}
      <div className="lg:w-1/2 space-y-4">
        {currentMoveIndex === -1 ? (
          <GameStartCard
            decryptionData={decryptionData}
            habitsReport={habitsReport}
            cctNarrative={cctNarrative}
            coachSummary={coachSummary}
            coreLesson={coreLesson}
            gameResult={gameResult}
            opponentName={opponentName}
            onBegin={goForward}
          />
        ) : (
          <MoveCoachingCardV5
            move={currentMove}
            gameId={gameId}
            acknowledgedConcepts={acknowledgedConcepts}
            onAcknowledge={acknowledgeConceptHandler}
            onShowFutureMoves={showFutureMoves}
            onShowAlternativeMove={showAlternativeMove}
            onFeedbackClick={(ruleName) => {
              setFeedbackRuleName(ruleName || null);
              setFeedbackOpen(true);
            }}
            // Caption move click: draw arrow on the main board for any
            // SAN clicked in the narrative or principle_cue. Arrow
            // colour amber so it visually differs from green (last move).
            onCaptionMoveClick={(san, from, to) => setArrows([[from, to, "amber"]])}
            // Thought reflection props
            userThought={userThoughts[currentMove?.move_number]}
            thoughtInputOpen={thoughtInputOpen[currentMove?.move_number]}
            onToggleThoughtInput={(moveNum) => setThoughtInputOpen(prev => ({ ...prev, [moveNum]: !prev[moveNum] }))}
            onThoughtChange={(moveNum, text, category) => setUserThoughts(prev => ({ ...prev, [moveNum]: { text, category, saved: false } }))}
            onSaveThought={saveThought}
            savingThought={savingThought}
            // Plan mode props
            planMode={planMode}
            planMoves={planMoves}
            planBoard={planBoard}
            planReasoning={planReasoning}
            planAnalysis={planAnalysis}
            analyzingPlan={analyzingPlan}
            onStartPlanMode={() => startPlanMode(currentMove)}
            onPlanMove={handlePlanMove}
            onUndoPlanMove={undoPlanMove}
            onCancelPlan={cancelPlanMode}
            onSubmitPlan={() => submitPlan(currentMove)}
            onPlanReasoningChange={setPlanReasoning}
            // Enrichment props
            positionCommentary={posCommentary[currentMoveIndex]}
            openingAnalysis={coachReview?.opening_analysis}
            patternContext={coachReview?.pattern_context}
            onPlayBestLine={onPlayBestLine}
          />
        )}

        {/* Authoring fact-dump panel — only when ?show_facts=1 is on URL.
            Shows the raw per-move record from decryption_v5_data so the
            caption author can see exactly which facts the extractor
            produced for this move. The header carries an Export-session
            button that downloads the full debug bundle (game + analysis
            + V5 records + voice layer + coach review) as a single JSON
            file. Built for offline debugging / sharing a session. */}
        {showFacts && currentMove && (() => {
          const rec = factsByMove[`${currentMove.move_number}|${currentMove.move_san}`];

          // Bundle exporter — fetches /api/lab/export/{gameId} and saves
          // the response as chessguru-session-{gameId}-{date}.json.
          const handleExport = async () => {
            try {
              const res = await fetch(`${API}/lab/export/${gameId}`, {
                credentials: "include",
              });
              if (!res.ok) {
                console.warn(`Export failed: ${res.status}`);
                return;
              }
              const data = await res.json();
              const blob = new Blob([JSON.stringify(data, null, 2)], {
                type: "application/json",
              });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              const date = new Date().toISOString().slice(0, 10);
              a.href = url;
              a.download = `chessguru-session-${gameId}-${date}.json`;
              document.body.appendChild(a);
              a.click();
              document.body.removeChild(a);
              URL.revokeObjectURL(url);
            } catch (e) {
              console.warn("Export error:", e);
            }
          };

          const Header = (
            <div className="flex items-center justify-between mb-2">
              <p className="text-[11px] uppercase tracking-wider text-zinc-400">
                {rec
                  ? `authoring · facts (move ${rec.move_number} ${rec.move_san})`
                  : "authoring · facts"}
              </p>
              <button
                onClick={handleExport}
                className="text-[10px] uppercase tracking-[0.18em] font-semibold text-zinc-300 hover:text-white border border-zinc-700 hover:border-zinc-500 rounded px-2 py-1 transition-colors"
                data-testid="export-session-bundle"
                title="Download full session debug bundle as JSON"
              >
                Export session JSON
              </button>
            </div>
          );

          if (!rec) {
            return (
              <div className="mt-3 p-3 rounded border border-zinc-700 bg-zinc-900/50">
                {Header}
                <p className="text-xs text-zinc-500">No raw record found for this move.</p>
              </div>
            );
          }
          return (
            <div className="mt-3 p-3 rounded border border-zinc-700 bg-zinc-900/50">
              {Header}
              <pre className="text-[11px] text-zinc-300 whitespace-pre-wrap break-all max-h-[420px] overflow-y-auto font-mono">
                {JSON.stringify(rec, null, 2)}
              </pre>
            </div>
          );
        })()}

        {feedbackOpen && currentMove && (
          <FeedbackPanel
            move={currentMove}
            ruleName={feedbackRuleName}
            feedbackText={feedbackText}
            setFeedbackText={setFeedbackText}
            onSubmit={handleSubmitFeedback}
            onCancel={() => { setFeedbackOpen(false); setFeedbackText(""); setFeedbackRuleName(null); }}
            submitting={submittingFeedback}
          />
        )}
        
        <div className="text-xs text-gray-400 text-center">
          Arrow keys: left/right navigate • Click moves in explanation to see on board
        </div>
      </div>
    </div>
    </>
  );
};


// ─── GAME START CARD ────────────────────────────────────────────────

const GameStartCard = ({ decryptionData, habitsReport, cctNarrative, coachSummary, coreLesson, gameResult, opponentName, onBegin }) => {
  if (!decryptionData?.length) return null;

  // Calculate stats
  const userMoves = decryptionData.filter(m => m.is_user_move);
  const mistakes = userMoves.filter(m => m.severity === 'mistake' || m.severity === 'blunder').length;
  const bestMoves = userMoves.filter(m => m.is_best_move).length;
  const openingName = decryptionData[0]?.opening_name;
  
  // Build story hook from available data
  const storyHook = coachSummary?.opening_line || coachSummary?.key_observation || null;
  const lessonLabel = coreLesson?.short_label || null;
  const lessonText = coreLesson?.lesson || null;
  const takeaway = coachSummary?.actionable_takeaway || null;
  
  return (
    <div className="space-y-4" data-testid="game-start-card">
      {/* Story hook — the narrative intro */}
      {(storyHook || lessonLabel) && (
        <div className="rounded-lg border border-border bg-muted/30 p-5">
          {lessonLabel && (
            <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-amber-600 dark:text-amber-400 mb-2 block">
              {lessonLabel}
            </span>
          )}
          {lessonText && (
            <p className="text-base font-semibold text-foreground leading-relaxed mb-2 font-heading">
              {lessonText}
            </p>
          )}
          {storyHook && !lessonText && (
            <p className="text-sm text-foreground leading-relaxed">
              {storyHook}
            </p>
          )}
          {takeaway && lessonText && (
            <p className="text-xs text-muted-foreground leading-relaxed mt-1">
              {takeaway}
            </p>
          )}
        </div>
      )}

      {/* Opening + Stats row */}
      <div className="flex items-stretch gap-3">
        {openingName && (
          <div className="flex-1 rounded-lg bg-emerald-500/8 border border-emerald-500/15 p-3.5">
            <p className="text-[10px] uppercase tracking-wider text-emerald-600 dark:text-emerald-400 font-semibold mb-0.5">Opening</p>
            <p className="text-sm font-medium text-foreground">{openingName}</p>
          </div>
        )}
        <div className="flex gap-2">
          <div className="w-16 rounded-lg bg-muted/50 border border-border p-3 text-center">
            <p className="text-lg font-bold text-foreground font-mono">{userMoves.length}</p>
            <p className="text-[10px] text-muted-foreground">Moves</p>
          </div>
          <div className="w-16 rounded-lg bg-emerald-500/8 border border-emerald-500/15 p-3 text-center">
            <p className="text-lg font-bold text-emerald-600 dark:text-emerald-400 font-mono">{bestMoves}</p>
            <p className="text-[10px] text-muted-foreground">Best</p>
          </div>
          <div className="w-16 rounded-lg bg-red-500/8 border border-red-500/15 p-3 text-center">
            <p className="text-lg font-bold text-red-500 font-mono">{mistakes}</p>
            <p className="text-[10px] text-muted-foreground">Errors</p>
          </div>
        </div>
      </div>
      
      {/* CCT discipline celebration — fires only when the analyzer
          detected a held-initiative-after-miss segment OR a strong
          forcing-move streak. Backend returns null when there's no
          signal worth narrating; in that case the block stays hidden. */}
      {/* CCT narrative block retired for "show only upgraded output"
          testing — LLM voice surface, separate pipeline from V5 captions. */}
      {false && cctNarrative && (<div />)}

      {/* What this analysis does */}
      <div className="rounded-lg border border-border p-4 bg-background">
        <p className="text-sm text-muted-foreground leading-relaxed">
          Your coach will walk you through <strong className="text-foreground">every move</strong> — yours and your opponent's.
          Tap <span className="text-amber-600 dark:text-amber-400 font-medium">"I understand"</span> on each concept to track what you've learned.
        </p>
      </div>

      {/* CTA */}
      <button 
        onClick={onBegin}
        className="w-full py-3.5 rounded-lg bg-foreground text-background font-medium text-sm hover:opacity-90 transition-opacity flex items-center justify-center gap-2"
        data-testid="begin-decrypt-btn"
      >
        <ChevronRight className="w-4 h-4" />
        Begin walkthrough
      </button>
      
      {/* Keyboard hint */}
      <p className="text-[10px] text-muted-foreground/60 text-center">
        or press the right arrow key
      </p>
    </div>
  );
};


// ─── MOVE COACHING CARD V5 ──────────────────────────────────────────

const MoveCoachingCardV5 = ({
  move,
  gameId,
  acknowledgedConcepts,
  onAcknowledge,
  onShowFutureMoves,
  onShowAlternativeMove,
  onFeedbackClick,
  // Thought reflection props
  userThought,
  thoughtInputOpen,
  onToggleThoughtInput,
  onThoughtChange,
  onSaveThought,
  savingThought,
  // Plan mode props
  planMode,
  planMoves,
  planBoard,
  planReasoning,
  planAnalysis,
  analyzingPlan,
  onStartPlanMode,
  onPlanMove,
  onUndoPlanMove,
  onCancelPlan,
  onSubmitPlan,
  onPlanReasoningChange,
  // Enrichment props
  positionCommentary,
  openingAnalysis,
  patternContext,
  onPlayBestLine,
  // Caption move-click: parent draws an arrow on the main board when
  // any chess move SAN in narrative or principle_cue is clicked.
  onCaptionMoveClick,
}) => {
  const [expanded, setExpanded] = useState(false);
  if (!move) return null;

  const isUser = move.is_user_move;
  const severity = move.severity || 'good';
  const priority = move.priority || (severity === 'good' ? 'silent' : 'essential');
  const weaknessMatch = move.weakness_match;
  const hasPlan = !!move.plan;
  const needsAck = move.needs_acknowledgment && move.concept_id && !acknowledgedConcepts.has(move.concept_id);
  const wasAcked = move.concept_id && acknowledgedConcepts.has(move.concept_id);
  
  // Show thought prompt for user mistakes
  const isMistake = isUser && (severity === 'blunder' || severity === 'mistake' || severity === 'inaccuracy');
  const hasThought = userThought?.saved;

  // Determine card style based on move type
  let borderClass = 'border-gray-200 bg-white';
  let headerIcon = <Brain className="w-5 h-5 text-blue-400" />;
  
  if (!isUser) {
    borderClass = 'border-indigo-500/30 bg-indigo-50';
    headerIcon = <Target className="w-5 h-5 text-indigo-400" />;
  } else if (severity === 'blunder' || severity === 'mistake') {
    borderClass = 'border-red-500/30 bg-red-50';
    headerIcon = <AlertTriangle className="w-5 h-5 text-red-400" />;
  } else if (severity === 'inaccuracy') {
    borderClass = weaknessMatch 
      ? 'border-amber-500/40 bg-amber-950/15 ring-1 ring-amber-500/20'
      : 'border-orange-500/30 bg-orange-50';
    headerIcon = <Lightbulb className="w-5 h-5 text-orange-400" />;
  } else if (move.is_best_move) {
    borderClass = 'border-emerald-500/30 bg-emerald-50';
    headerIcon = <Trophy className="w-5 h-5 text-emerald-400" />;
  } else if (severity === 'good') {
    borderClass = 'border-emerald-500/20 bg-emerald-50/50';
    headerIcon = <CheckCircle2 className="w-5 h-5 text-emerald-400" />;
  }

  // Shared flag context for all inline flags on this move
  const flagCtx = {
    source: "lab",
    gameId,
    moveNumber: move.move_number,
    fen: move.fen_before || move.fen || "",
    moveSan: move.move_san,
    side: isUser ? "user" : "opponent",
    severity,
    cpLoss: move.cp_loss,
    bestMove: move.best_move,
    evalBefore: move.eval_before,
    evalAfter: move.eval_after,
    phase: move.phase,
    component: "GameDecryptionV5",
    opening: move.opening_name,
    goal: move.plan?.goal,
    consequence: move.plan?.consequence,
    betterApproach: move.plan?.better_approach,
    yourPlanNow: move.your_plan_now,
  };

  return (
    <Card className={`border ${borderClass}`} data-testid="move-coaching-card-v5">
      <CardContent className="p-5 space-y-3">
        {/* ─── HEADER ──────────────────────────────────────── */}
        {/* Severity and phase tags removed — they were System-layer labels
            leaking into the Surface. The border color (red/amber) and the
            narrative below already convey how the move went. */}
        <div className="flex items-center gap-2">
          {headerIcon}
          <span className="font-bold text-gray-900 text-lg">{move.move_san}</span>
          <Badge variant={isUser ? "default" : "secondary"} className="text-xs">
            {isUser ? "Your move" : "Opponent"}
          </Badge>
          {move.is_best_move && (
            <Badge className="text-xs bg-emerald-500/20 text-emerald-400 border-emerald-500/30">
              Best move!
            </Badge>
          )}
          {weaknessMatch && (
            <Badge className="text-xs bg-amber-500/20 text-amber-300 border-amber-500/30">
              Known pattern{move.weakness_count ? ` (${move.weakness_count}x)` : ''}
            </Badge>
          )}
        </div>

        {/* ─── NARRATIVE ────────────────────────────────────── */}
        {move.narrative && (
          <div className="leading-relaxed group" data-testid="move-narrative">
            <ClickableCaption
              text={move.narrative}
              fen={move.fen_before}
              onMoveSelect={onCaptionMoveClick}
              className="text-sm text-gray-700"
            />
            <InlineFlag section="narrative" flaggedText={move.narrative} context={flagCtx} />
          </div>
        )}

        {/* v78.3 — "Play this line" button. Visible on user-mistake
            moves where V5 surfaced a coach_line_length_hint (or a
            trap_line_full). Animates engine's PV / trap_line on the
            board with 2-second pacing. Mirrors the GameAnalysis-side
            implementation but uses LichessBoard's new playVariation. */}
        {(() => {
          // Build coachLine in-line so we don't pollute the outer scope
          if (!isUser) return null;
          const trap = move.trap_line_full;
          let lineMoves = null;
          let lineSteps = null;
          let lineKind = null;
          if (Array.isArray(trap) && trap.length > 0) {
            lineMoves = trap.map((s) => s.move).filter(Boolean);
            lineSteps = trap;
            lineKind = "trap";
          } else if ((move.pv_after_best || []).length > 0 && (move.coach_line_length_hint || 0) >= 1) {
            const sliced = (move.pv_after_best || []).slice(0, move.coach_line_length_hint);
            lineMoves = sliced;
            lineSteps = sliced.map((m) => ({ move: m, explanation: null }));
            lineKind = "pv";
          }
          if (!lineMoves || !lineMoves.length) return null;
          const isPlaying = coachLinePlaybackIdx === currentMoveIndex;
          return (
            <div className="mt-2">
              {!isPlaying && (
                <button
                  onClick={() => {
                    if (!boardRef.current?.playVariation) return;
                    setCoachLinePlaybackIdx(currentMoveIndex);
                    setCoachLineStepIndex(-1);
                    boardRef.current.playVariation(
                      move.fen_before,
                      lineMoves,
                      { stepDelayMs: 2000, onStep: (idx) => setCoachLineStepIndex(idx) },
                    );
                  }}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 border border-amber-500/30"
                  data-testid="play-this-line-btn"
                >
                  ▶ Play this line
                </button>
              )}
              {isPlaying && (
                <div className="rounded border border-amber-500/30 bg-amber-500/5 p-2.5 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs uppercase tracking-wide text-amber-500 font-medium">
                      {lineKind === "trap" ? "Trap line" : "Engine line"}
                    </span>
                    <button
                      onClick={() => {
                        boardRef.current?.cancelVariation?.();
                        // Snap board back to current move's post-position
                        if (move.fen_after && boardRef.current?.setPosition) {
                          boardRef.current.setPosition(move.fen_after);
                        }
                        setCoachLinePlaybackIdx(-1);
                        setCoachLineStepIndex(-1);
                      }}
                      className="text-[10px] text-gray-500 hover:text-gray-300"
                    >
                      Back to game
                    </button>
                  </div>
                  <ol className="space-y-0.5">
                    {lineSteps.map((s, i) => {
                      const isCurrent = i === coachLineStepIndex;
                      const isPlayed = i <= coachLineStepIndex;
                      return (
                        <li
                          key={`${i}-${s.move}`}
                          className={`text-xs leading-relaxed ${
                            isCurrent ? "text-amber-300" : isPlayed ? "text-gray-300" : "text-gray-500"
                          }`}
                        >
                          <span className="font-mono mr-2">{i + 1}. {s.move}</span>
                          {s.explanation && <span>{s.explanation}</span>}
                        </li>
                      );
                    })}
                  </ol>
                </div>
              )}
            </div>
          );
        })()}

        {/* Teaching cue — named-principle habit reminder. Rendered
            as a smaller italic line under the diagnosis so the
            diagnostic caption and the habit cue stay visually
            distinct. Cue lives on move.principle_cue (set in
            currentMove useMemo, sourced from per-move endpoint). */}
        {move.principle_cue && (
          <div
            className="leading-relaxed group mt-1.5 pl-3 border-l-2 border-amber-500/30"
            data-testid="move-principle-cue"
          >
            <ClickableCaption
              text={move.principle_cue}
              fen={move.fen_before}
              onMoveSelect={onCaptionMoveClick}
              className="text-xs italic text-amber-700 dark:text-amber-300/80"
            />
            <InlineFlag
              section="principle_cue"
              flaggedText={move.principle_cue}
              context={{ ...flagCtx, principle_id: move.principle_id || null }}
            />
          </div>
        )}

        {/* TIER 3 shape pattern — visual danger language. The pattern
            NAME is what the player remembers (Class 6-8 English).
            Description sits on the same line in lighter weight so
            kids see both the label and the picture at once. */}
        {move.shape_pattern_id && move.shape_pattern_name && (
          <div
            className="leading-relaxed group mt-1.5 pl-3 border-l-2 border-teal-500/40"
            data-testid="move-shape-pattern"
          >
            <p className="text-xs">
              <span className="font-semibold text-teal-700 dark:text-teal-300">
                {move.shape_pattern_name}
              </span>
              {move.shape_pattern_desc && (
                <span className="text-teal-700/80 dark:text-teal-300/70">
                  {" — "}{move.shape_pattern_desc}
                </span>
              )}
            </p>
            <InlineFlag
              section="shape_pattern"
              flaggedText={`${move.shape_pattern_name}${move.shape_pattern_desc ? ` — ${move.shape_pattern_desc}` : ""}`}
              context={{ ...flagCtx, rule_name: move.shape_pattern_id }}
            />
          </div>
        )}

        {/* ─── POSITION COMMENTARY (what the board says) ──────── */}
        {/* Header is "What this position tells us" — NOT "A better plan here".
            The plan/observations come from PLAN_RULES + position_reader,
            which describe position features (pins, back-rank pieces, etc.)
            independent of the move actually played. Labeling them as
            move-specific advice lies to the user. */}
        {/* POSITION COMMENTARY block retired (800-tester feedback:
            "too much theory, longer sentences"). The new V5 caption
            above is the single move-grounded signal we show now. */}
        {false && positionCommentary && (isMistake || move.is_best_move) && (
          <div />
        )}

        {/* ─── OPENING THEORY (if in opening phase) ──────────────
            Tester reported the "Deviated: played dxc4 instead of e6"
            phrasing was confusing — dxc4 is the Queen's Gambit
            Accepted main line, not a deviation. The wording now says
            "Played X — book continues with Y" which is honest whether
            X is a true deviation or a valid alternative line.
            Also bumped contrast from text-gray-500/400 (faded in dark
            mode) to text-foreground/80 + foreground/60 for readability. */}
        {false && openingAnalysis && move.phase === "opening" && move.move_number <= 12 && (
          <div className="bg-primary/5 rounded-lg p-3 border border-primary/30">
            <p className="text-xs text-primary font-semibold mb-1">
              Opening: {openingAnalysis.name}
              <span className="text-primary/60 ml-2">{openingAnalysis.moves_in_theory}/{openingAnalysis.total_theory_moves} theory</span>
            </p>
            {openingAnalysis.deviation && openingAnalysis.deviation.ply <= (move.move_number * 2) && (
              <p className="group text-xs text-foreground/80">
                Played <span className="font-mono text-amber-500">{openingAnalysis.deviation.played}</span>
                {" "}— book continues with <span className="font-mono text-emerald-500">{openingAnalysis.deviation.expected}</span>
                {openingAnalysis.deviation.idea && <span className="text-foreground/60"> — {openingAnalysis.deviation.idea}</span>}
                <InlineFlag
                  section="opening_deviation"
                  flaggedText={`Played ${openingAnalysis.deviation.played} — book continues with ${openingAnalysis.deviation.expected}${openingAnalysis.deviation.idea ? ` — ${openingAnalysis.deviation.idea}` : ""}`}
                  context={flagCtx}
                />
              </p>
            )}
            {openingAnalysis.traps?.map((t, i) => (
              <p key={i} className="group text-xs text-amber-500 mt-1">
                <span className="font-semibold">{t.name}:</span> {t.story || t.explanation}
                <InlineFlag
                  section={`opening_trap_${i}`}
                  flaggedText={`${t.name}: ${t.story || t.explanation}`}
                  context={flagCtx}
                />
              </p>
            ))}
          </div>
        )}

        {/* PATTERN CONNECTION (cross-game) — RETIRED 2026-05-13.
            Per feedback_sub1500_memory_anchors: <1500 players remember
            NAMED principles, geometric shapes, and process habits —
            never games/opponents/move-sequences. "12 of your last 20
            games" reads as empty. The cross-game repetition surfaces
            naturally now through the V5 principle cue + shape pattern
            NAME appearing under the same kind of move across games —
            the player sees "Free Piece" or "Hanging Piece" repeatedly,
            which is the actual memory anchor. */}
        {false && patternContext?.is_recurring && isMistake && (<div />)}

        {/* ─── STOCKFISH BRANCHING (what if best move?) ────────── */}
        {isMistake && (move.best_move_san || move.best_move) && (
          <button
            onClick={() => {
              // Play the best move from fen_before, then PV continuation
              const bestMove = move.best_move_san || move.best_move;
              // First show the best move as an alternative
              onShowAlternativeMove(bestMove);
            }}
            className="w-full text-xs text-blue-400 hover:text-blue-300 bg-blue-500/5 hover:bg-blue-500/10 rounded-lg p-2.5 border border-blue-500/15 transition-all flex items-center justify-center gap-1.5"
          >
            <Eye className="w-3 h-3" />
            What if I played {move.best_move_san || move.best_move}? See on board
          </button>
        )}

        {/* "What's your plan now?" block retired (800-tester feedback). */}
        {false && !isUser && move.your_plan_now && (<div />)}

        {/* ─── PLAN (THE TRANSFERABLE LEARNING) ─────────────── */}
        {hasPlan && (
          <div className="space-y-2">
            {/* "What happens" / "Better approach" prose blocks retired
                (800-tester feedback: too much theory, longer sentences).
                The V5 caption above already says what went wrong and
                names the engine's best move when there is one. */}
            
            {/* Candidate Moves with Ideas - CLICKABLE */}
            {move.plan.candidate_moves?.length > 0 && (
              <div className="bg-blue-500/10 rounded-lg p-3 border border-blue-500/20" data-testid="candidate-moves">
                <p className="text-xs text-blue-400 mb-2 flex items-center gap-1">
                  <Lightbulb className="w-3 h-3" /> Alternative ideas in this position
                </p>
                <div className="space-y-2">
                  {move.plan.candidate_moves.map((candidate, idx) => (
                    <div 
                      key={idx}
                      className={`flex items-start gap-2 p-2 rounded cursor-pointer transition-all hover:scale-[1.01] ${
                        candidate.is_best 
                          ? 'bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-100' 
                          : 'bg-gray-50 hover:bg-gray-100'
                      }`}
                      onClick={() => onShowAlternativeMove(candidate.move)}
                      title={`Click to see ${candidate.move} on the board`}
                    >
                      <button
                        className={`font-mono font-bold text-sm min-w-[50px] px-2 py-1 rounded hover:ring-2 ring-offset-1 ring-offset-zinc-900 ${
                          candidate.is_best 
                            ? 'text-emerald-400 bg-emerald-500/20 hover:ring-emerald-500/50' 
                            : 'text-blue-400 bg-blue-500/20 hover:ring-blue-500/50'
                        }`}
                        onClick={(e) => {
                          e.stopPropagation();
                          onShowAlternativeMove(candidate.move);
                        }}
                      >
                        {candidate.move}
                      </button>
                      <div className="flex-1 text-xs text-gray-500">
                        click to see line
                      </div>
                      {candidate.is_best && (
                        <Trophy className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* "Learning" / transferable-learning block retired
                (800-tester feedback: too much theory, longer sentences).
                Acknowledgment loop also retired with it — re-introduce
                once the voice gets a 800-friendly pass. */}
          </div>
        )}

        {/* CONCEPT APPLIED — RETIRED 2026-05-13.
            concept_applied is an internal TAG ("found_best_move",
            "king_safety_castling", etc.) emitted by recognize_good_move
            in game_decryption_v5_service.py. It was never meant to be
            display text; this block was rendering the raw tag with
            underscores stripped, producing user-visible junk like
            "You demonstrated found best move" (fb_c8310544af99).
            V5 captions are the proper teaching surface for good moves.
            Future authored "You demonstrated X" needs user-written text. */}
        {false && move.concept_applied && !hasPlan && (<div />)}

        {/* ─── FUTURE MOVES (clickable) ───────────────────────── */}
        {move.future_moves?.length > 0 && !hasPlan && (
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-xs text-gray-500 mb-2">The line continues:</p>
            <div className="flex flex-wrap gap-1">
              {move.future_moves.slice(0, 4).map((m, i) => (
                <button
                  key={i}
                  onClick={() => onShowFutureMoves(move.future_moves, i)}
                  className="font-mono text-sm bg-gray-100 hover:bg-emerald-100 px-2 py-1 rounded text-gray-900 transition-colors"
                  title={`Click to see position after ${m}`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ─── WHAT WERE YOU THINKING? (smart dropdown + board play) ── */}
        {isMistake && !planMode && !planAnalysis && (
          <div className="bg-violet-500/5 rounded-lg p-3 border border-violet-500/20" data-testid="thought-prompt">
            {hasThought ? (
              // Already saved thought
              <div className="space-y-3">
                <div className="flex items-start gap-2">
                  <Eye className="w-4 h-4 text-violet-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-xs text-violet-400 mb-1">Your thinking</p>
                    <p className="text-sm text-gray-600 italic">"{userThought.text}"</p>
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={onStartPlanMode}
                  className="w-full text-xs border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10"
                >
                  <Swords className="w-3 h-3 mr-2" />
                  Show my plan on the board
                </Button>
              </div>
            ) : thoughtInputOpen ? (
              // Smart dropdown with context-aware options
              <div className="space-y-2">
                <p className="text-xs text-violet-400 flex items-center gap-1">
                  <Eye className="w-3 h-3" /> Why did you play {move.move_san}?
                </p>
                {/* Smart options generated from position context */}
                <div className="space-y-1">
                  {_generateThoughtOptions(move, positionCommentary).map((opt, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        onThoughtChange(move.move_number, opt.text, opt.category);
                        // Auto-save after selection
                        setTimeout(() => onSaveThought(move.move_number, move.fen_before, opt.category), 100);
                      }}
                      className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all ${
                        userThought?.text === opt.text
                          ? "bg-violet-500/20 border border-violet-500/30 text-violet-300"
                          : "bg-gray-50 hover:bg-violet-500/10 text-gray-700 border border-transparent"
                      }`}
                    >
                      {opt.text}
                    </button>
                  ))}
                  {/* Other — show text input */}
                  <button
                    onClick={() => onThoughtChange(move.move_number, "")}
                    className="w-full text-left px-3 py-2 rounded-lg text-sm bg-gray-50 hover:bg-violet-500/10 text-gray-500 border border-transparent"
                  >
                    Other...
                  </button>
                </div>
                {/* Text input shows when "Other" is selected or text is custom */}
                {userThought?.text !== undefined && !_generateThoughtOptions(move, positionCommentary).some(o => o.text === userThought?.text) && (
                  <div className="space-y-2 pt-1">
                    <Textarea
                      value={userThought?.text || ""}
                      onChange={(e) => onThoughtChange(move.move_number, e.target.value)}
                      placeholder="What were you thinking..."
                      className="min-h-[50px] text-sm bg-gray-50 border-gray-200 resize-none"
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() => onSaveThought(move.move_number, move.fen_before)}
                        disabled={savingThought === move.move_number || !userThought?.text?.trim()}
                        className="text-xs bg-violet-600 hover:bg-violet-700"
                      >
                        {savingThought === move.move_number ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Check className="w-3 h-3 mr-1" />}
                        Save
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => onToggleThoughtInput(move.move_number)} className="text-xs text-gray-500">
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
                {/* Play my intended move on the board */}
                <Button
                  size="sm"
                  variant="outline"
                  onClick={onStartPlanMode}
                  className="w-full text-xs border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10 mt-1"
                >
                  <Swords className="w-3 h-3 mr-2" />
                  Or show what I wanted to play on the board
                </Button>
              </div>
            ) : (
              // Collapsed - show button to expand
              <div className="space-y-2">
                <button
                  onClick={() => onToggleThoughtInput(move.move_number)}
                  className="flex items-center gap-2 text-xs text-violet-400 hover:text-violet-300 transition-colors w-full"
                >
                  <Eye className="w-3 h-3" />
                  <span>Why did you play {move.move_san}?</span>
                  <ChevronDown className="w-3 h-3 ml-auto" />
                </button>
              </div>
            )}
          </div>
        )}

        {/* ─── PLAN MODE: Interactive Board ────────────────────── */}
        {planMode && isMistake && (
          <div className="bg-cyan-500/5 rounded-lg p-4 border border-cyan-500/30 space-y-4" data-testid="plan-mode">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Swords className="w-4 h-4 text-cyan-400" />
                <span className="text-sm font-medium text-cyan-400">Show Your Plan</span>
              </div>
              <Button
                size="sm"
                variant="ghost"
                onClick={onCancelPlan}
                className="h-6 w-6 p-0 text-gray-500 hover:text-gray-700"
              >
                <X className="w-3 h-3" />
              </Button>
            </div>
            
            <p className="text-xs text-gray-500">
              Play the moves you intended. What did you think would happen?
            </p>
            
            {/* Current plan moves */}
            {planMoves.length > 0 && (
              <div className="bg-gray-50 rounded p-2">
                <p className="text-xs text-gray-500 mb-1">Your line:</p>
                <div className="flex flex-wrap items-center gap-1">
                  <span className="font-mono text-sm text-gray-900">{move.move_san}</span>
                  {planMoves.map((m, i) => (
                    <span key={i} className="font-mono text-sm text-cyan-300">{m}</span>
                  ))}
                </div>
              </div>
            )}
            
            {/* Undo button */}
            {planMoves.length > 0 && (
              <Button
                size="sm"
                variant="ghost"
                onClick={onUndoPlanMove}
                className="text-xs text-gray-500"
              >
                ← Undo last move
              </Button>
            )}
            
            {/* Submit plan */}
            <div className="space-y-2">
              <Textarea
                value={planReasoning}
                onChange={(e) => onPlanReasoningChange(e.target.value)}
                placeholder="Why did you think this would work? (optional)"
                className="min-h-[50px] text-sm bg-gray-50 border-gray-200 resize-none"
              />
              <Button
                size="sm"
                onClick={onSubmitPlan}
                disabled={planMoves.length === 0 || analyzingPlan}
                className="w-full bg-cyan-600 hover:bg-cyan-700"
              >
                {analyzingPlan ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin mr-2" />
                    Analyzing your calculation...
                  </>
                ) : (
                  <>
                    <Brain className="w-3 h-3 mr-2" />
                    Analyze my plan
                  </>
                )}
              </Button>
            </div>
            
            <p className="text-xs text-gray-400 text-center">
              Make moves on the board to show your intended line
            </p>
          </div>
        )}

        {/* ─── PLAN ANALYSIS RESULTS ───────────────────────────── */}
        {planAnalysis && isMistake && (
          <div className="bg-gradient-to-b from-cyan-500/10 to-transparent rounded-lg p-4 border border-cyan-500/30 space-y-4" data-testid="plan-analysis">
            <div className="flex items-center gap-2">
              <Brain className="w-5 h-5 text-cyan-400" />
              <span className="text-sm font-medium text-gray-900">Calculation Analysis</span>
              {planAnalysis.gap_severity === "critical" && (
                <Badge className="bg-red-500/20 text-red-400 text-xs">Critical Gap</Badge>
              )}
              {planAnalysis.gap_severity === "significant" && (
                <Badge className="bg-amber-500/20 text-amber-400 text-xs">Significant Gap</Badge>
              )}
            </div>
            
            {/* Gap type */}
            <div className="p-3 rounded bg-gray-50">
              <p className="text-xs text-gray-500 mb-1">What went wrong</p>
              <p className="text-sm text-gray-900 font-medium">
                {planAnalysis.gap_type === "missed_tactic" && "Missed Tactic"}
                {planAnalysis.gap_type === "calculation_depth" && "Calculation Too Shallow"}
                {planAnalysis.gap_type === "correct_plan" && "Your plan was actually reasonable!"}
              </p>
            </div>
            
            {/* Explanation */}
            <p className="text-sm text-gray-600">{planAnalysis.explanation}</p>
            
            {/* Divergence point */}
            {planAnalysis.divergence_move_number > 0 && (
              <div className="p-3 rounded bg-red-500/10 border border-red-500/20">
                <p className="text-xs text-red-400 mb-1">The critical moment (move {planAnalysis.divergence_move_number})</p>
                <p className="text-sm">
                  You expected <span className="font-mono text-gray-500">{planAnalysis.user_expected_move}</span>
                  {" "}but <span className="font-mono text-emerald-400">{planAnalysis.actual_best_move}</span> changes everything
                </p>
                {planAnalysis.missed_tactic_type && (
                  <p className="text-xs text-amber-400 mt-1">
                    Tactic: {planAnalysis.missed_tactic_type.replace(/_/g, ' ')}
                  </p>
                )}
              </div>
            )}
            
            {/* Eval swing */}
            {planAnalysis.eval_swing > 0 && (
              <p className="text-xs text-gray-500">
                Evaluation swing: <span className="text-red-400">{planAnalysis.eval_swing.toFixed(1)} pawns</span>
              </p>
            )}
            
            {/* Lesson */}
            {planAnalysis.lesson && (
              <div className="p-3 rounded bg-amber-500/10 border border-amber-500/20">
                <div className="flex items-start gap-2">
                  <Lightbulb className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
                  <p className="text-sm text-amber-200">{planAnalysis.lesson}</p>
                </div>
              </div>
            )}
            
            {/* Try again button */}
            <Button
              size="sm"
              variant="ghost"
              onClick={onStartPlanMode}
              className="text-xs text-cyan-400"
            >
              Show a different line
            </Button>
          </div>
        )}

        {/* ─── FEEDBACK ──────────────────────────────────────── */}
        <div className="flex items-center justify-end pt-2 border-t border-gray-200/50">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onFeedbackClick(move.shape_pattern_id || move.rule_name || null)}
            className="text-xs text-gray-500 hover:text-red-400"
            data-testid="btn-not-helpful"
            title="Report an inaccurate narrative"
          >
            <ThumbsDown className="w-3 h-3 mr-1" /> Report
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};


// ─── CLICKABLE MOVES COMPONENT ──────────────────────────────────────

const ClickableMoves = ({ text, moves, onMoveClick }) => {
  if (!moves?.length || !text) {
    return <p className="text-gray-900 text-sm">{text}</p>;
  }
  
  // Parse text and make moves clickable
  const movePattern = /\b([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]*|O-O-O|O-O)\b/g;
  const parts = [];
  let lastIndex = 0;
  let moveIndex = 0;
  let match;
  
  while ((match = movePattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', content: text.slice(lastIndex, match.index) });
    }
    
    const moveSan = match[0];
    const foundIndex = moves.findIndex((m, i) => 
      i >= moveIndex && m.replace(/[+#]/g, '') === moveSan.replace(/[+#]/g, '')
    );
    
    if (foundIndex !== -1) {
      parts.push({ type: 'move', content: moveSan, moveIndex: foundIndex });
      moveIndex = foundIndex + 1;
    } else {
      parts.push({ type: 'move-inactive', content: moveSan });
    }
    
    lastIndex = match.index + match[0].length;
  }
  
  if (lastIndex < text.length) {
    parts.push({ type: 'text', content: text.slice(lastIndex) });
  }
  
  return (
    <p className="text-gray-900 text-sm">
      {parts.map((part, i) => {
        if (part.type === 'move') {
          return (
            <button
              key={i}
              onClick={() => onMoveClick(moves, part.moveIndex)}
              className="font-mono font-bold text-amber-400 hover:text-amber-300 hover:underline cursor-pointer transition-colors"
              title={`Click to see this on the board`}
            >
              {part.content}
            </button>
          );
        }
        if (part.type === 'move-inactive') {
          return <span key={i} className="font-mono font-semibold text-gray-600">{part.content}</span>;
        }
        return <span key={i}>{part.content}</span>;
      })}
    </p>
  );
};


// ─── FEEDBACK PANEL ─────────────────────────────────────────────────
// Inline expand-on-click form. Shows which rule is being flagged so the
// admin queue knows whether the complaint is about the primary caption or
// the secondary shape-pattern narrative. No modal — sits inline below
// the coaching card. Per [[no-parallel-surfaces]]: posts to the same
// /feedback/flag endpoint used by InlineFlag; writes to move_feedback.

const FeedbackPanel = ({ move, ruleName, feedbackText, setFeedbackText, onSubmit, onCancel, submitting }) => (
  <Card className="bg-red-50 border-red-200" data-testid="feedback-panel">
    <CardContent className="p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-900">What is wrong with this explanation?</p>
          {ruleName && (
            <p className="text-[11px] text-gray-500 mt-0.5">
              Flagging: <span className="font-mono text-red-500">{ruleName}</span>
            </p>
          )}
        </div>
        <Button variant="ghost" size="icon" onClick={onCancel} className="h-6 w-6">
          <X className="w-4 h-4" />
        </Button>
      </div>
      {move?.narrative && (
        <div className="bg-white rounded border border-red-100 px-3 py-2">
          <p className="text-[11px] text-gray-400 mb-0.5">Narrative shown</p>
          <p className="text-xs text-gray-700 leading-relaxed">{move.narrative}</p>
        </div>
      )}
      <Textarea
        value={feedbackText}
        onChange={(e) => setFeedbackText(e.target.value)}
        placeholder="What's wrong? e.g., 'Queen moved to a2, not to the diagonal — Open Long Line doesn't apply here.'"
        className="min-h-[80px] bg-white border-red-200 text-gray-900"
        data-testid="feedback-textarea"
        autoFocus
      />
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onCancel}>Cancel</Button>
        <Button size="sm" onClick={onSubmit} disabled={!feedbackText.trim() || submitting} data-testid="submit-feedback-btn">
          {submitting ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Send className="w-4 h-4 mr-1" />} Submit report
        </Button>
      </div>
    </CardContent>
  </Card>
);


// ─── MOVE LIST V5 ───────────────────────────────────────────────────

const MoveListV5 = ({ decryptionData, currentMoveIndex, onMoveClick }) => {
  if (!decryptionData?.length) return null;
  
  const pairs = [];
  for (let i = 0; i < decryptionData.length; i += 2) {
    pairs.push({
      num: decryptionData[i].move_number,
      w: decryptionData[i],
      b: decryptionData[i + 1] || null,
      wi: i,
      bi: i + 1
    });
  }
  
  const moveClass = (m, idx) => {
    if (currentMoveIndex === idx) return 'bg-emerald-500/30 text-gray-900 ring-1 ring-emerald-500/50';
    
    const severity = m.severity || 'good';
    if (severity === 'blunder') return 'text-red-400 bg-red-500/10 hover:bg-red-500/20';
    if (severity === 'mistake') return 'text-red-400 hover:bg-red-500/10';
    if (severity === 'inaccuracy') return 'text-orange-400 hover:bg-orange-500/10';
    if (m.is_best_move) return 'text-emerald-400 hover:bg-emerald-500/10';
    if (!m.is_user_move) return 'text-gray-500 hover:bg-gray-100';
    return 'text-gray-600 hover:bg-gray-100';
  };
  
  const indicator = (m) => {
    const severity = m.severity || 'good';
    if (severity === 'blunder') return <span className="text-red-400 ml-0.5">??</span>;
    if (severity === 'mistake') return <span className="text-red-400 ml-0.5">?</span>;
    if (severity === 'inaccuracy') return <span className="text-orange-400 ml-0.5">?!</span>;
    if (m.is_best_move) return <span className="text-emerald-400 ml-0.5">!</span>;
    return null;
  };

  return (
    <ScrollArea className="h-[180px] rounded-lg border border-gray-200 bg-gray-50">
      <div className="p-2 space-y-1">
        {pairs.map(p => (
          <div key={p.num} className="flex items-center gap-1 text-sm">
            <span className="w-8 text-gray-500 text-right shrink-0">{p.num}.</span>
            <button 
              onClick={() => onMoveClick(p.wi)} 
              className={`px-2 py-0.5 rounded font-mono transition-colors ${moveClass(p.w, p.wi)}`}
            >
              {p.w.move_san}{indicator(p.w)}
            </button>
            {p.b && (
              <button 
                onClick={() => onMoveClick(p.bi)} 
                className={`px-2 py-0.5 rounded font-mono transition-colors ${moveClass(p.b, p.bi)}`}
              >
                {p.b.move_san}{indicator(p.b)}
              </button>
            )}
          </div>
        ))}
      </div>
    </ScrollArea>
  );
};


// ─── HELPER ─────────────────────────────────────────────────────────

const getLastMoveSquares = (move) => {
  if (!move?.fen_before || !move?.move_san) return null;
  try {
    const c = new Chess(move.fen_before);
    const p = c.move(move.move_san);
    return p ? [p.from, p.to] : null;
  } catch { 
    return null; 
  }
};


export default GameDecryptionV5;
