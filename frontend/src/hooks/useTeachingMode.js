/**
 * useTeachingMode — Manages all opening/trap teaching state and handlers
 *
 * This hook is the pluggable teaching system for Play with Coach.
 * New lesson types (tactics, short wins, positional) can be added
 * by extending the handlers here.
 *
 * External callers can update teaching state via exposed setters
 * (e.g., pollCoachMessages sets inlineOpening, resumeSession sets openingGuidance).
 */

import { useState, useCallback } from "react";
import { Chess } from "chess.js";
import { API } from "@/App";
import { toast } from "sonner";

const useTeachingMode = ({
  session,
  currentFen,
  setChatMessages,
  setCurrentFen,
  setCurrentInsight,
  newGameFn,
  startGameFn,
}) => {
  // ── Teaching State ──
  const [teachingOffer, setTeachingOffer] = useState(null);
  const [activeLesson, setActiveLesson] = useState(null);
  const [lessonInstruction, setLessonInstruction] = useState(null);
  const [lessonComplete, setLessonComplete] = useState(null);
  const [isInTeachingMode, setIsInTeachingMode] = useState(false);

  // ── Opening Guidance ──
  const [openingGuidance, setOpeningGuidance] = useState(null);
  const [inlineOpening, setInlineOpening] = useState(null);
  const [inlineTrap, setInlineTrap] = useState(null);
  const [coachIntroMessage, setCoachIntroMessage] = useState(null);
  const [curriculumFeedback, setCurriculumFeedback] = useState(null);
  const [lastCoachMoveSan, setLastCoachMoveSan] = useState(null);
  const [positionCoaching, setPositionCoaching] = useState(null);
  const [openingCorrectionCount, setOpeningCorrectionCount] = useState(0);

  // ── Reset all teaching state (called on new game) ──
  const resetTeachingState = useCallback(() => {
    setTeachingOffer(null);
    setActiveLesson(null);
    setLessonInstruction(null);
    setLessonComplete(null);
    setIsInTeachingMode(false);
    setOpeningGuidance(null);
    setInlineOpening(null);
    setInlineTrap(null);
    setCoachIntroMessage(null);
    setCurriculumFeedback(null);
    setLastCoachMoveSan(null);
    setPositionCoaching(null);
  }, []);

  // ── Handlers ──

  const handleStartLesson = useCallback(
    (lessonData) => {
      setTeachingOffer(null);
      setActiveLesson(lessonData);
      setLessonInstruction(lessonData.instruction);
      setIsInTeachingMode(true);

      if (lessonData.teaching_fen) {
        setCurrentFen(lessonData.teaching_fen);
      }

      setCurrentInsight({
        quality: "teaching",
        main_insight: `Let's learn the ${lessonData.lesson_name}! ${
          lessonData.instruction?.message || "Follow along and play the moves."
        }`,
        why: lessonData.opening_name
          ? `Part of the ${lessonData.opening_name}`
          : null,
        next_idea: lessonData.instruction?.is_user_move
          ? `Your turn: play ${lessonData.instruction.move}`
          : `Watch: I'll play ${lessonData.instruction?.move}`,
        has_better_move: false,
        can_explain: true,
        teaching_mode: true,
        lesson_name: lessonData.lesson_name,
        remaining_moves: lessonData.instruction?.remaining,
      });

      setChatMessages((prev) => [
        ...prev,
        {
          type: "coach",
          trigger: "teaching",
          message: `Let's learn the ${lessonData.lesson_name}! Follow along and play the moves.`,
          timestamp: Date.now(),
        },
      ]);

      if (lessonData.auto_played_move) {
        setChatMessages((prev) => [
          ...prev,
          {
            type: "coach",
            trigger: "teaching",
            message: `I played ${lessonData.auto_played_move}. Now your turn!`,
            timestamp: Date.now(),
          },
        ]);
      }

      // Handle multiple auto-played moves (trap lessons)
      if (lessonData.auto_played_moves?.length > 0 && !lessonData.auto_played_move) {
        setChatMessages((prev) => [
          ...prev,
          {
            type: "coach",
            trigger: "teaching",
            message: `Opponent played ${lessonData.auto_played_moves.join(", ")}. Your turn!`,
            timestamp: Date.now(),
          },
        ]);
      }

      // Show endgame/trap-specific info
      if (lessonData.endgame_info?.rule) {
        setChatMessages((prev) => [
          ...prev,
          {
            type: "coach",
            trigger: "teaching",
            message: `Key rule: ${lessonData.endgame_info.rule}`,
            timestamp: Date.now(),
          },
        ]);
      }
      if (lessonData.trap_info?.why_it_works) {
        setChatMessages((prev) => [
          ...prev,
          {
            type: "coach",
            trigger: "teaching",
            message: `Goal: ${lessonData.trap_info.why_it_works}`,
            timestamp: Date.now(),
          },
        ]);
      }

      toast.success(`Starting lesson: ${lessonData.lesson_name}`);
    },
    [setChatMessages, setCurrentFen, setCurrentInsight]
  );

  const handleSkipTeachingOffer = useCallback(() => {
    setTeachingOffer(null);
    setChatMessages((prev) => [
      ...prev,
      {
        type: "coach",
        trigger: "encouragement",
        message:
          "No problem! Let's continue playing. I'll guide you as we go.",
        timestamp: Date.now(),
      },
    ]);
  }, [setChatMessages]);

  const handleTeachingMoveValidated = useCallback(
    (result) => {
      if (result.next_instruction) {
        setLessonInstruction(result.next_instruction);
        setCurrentInsight({
          quality: result.correct ? "good" : "teaching",
          main_insight:
            result.message ||
            (result.correct ? "Good! Keep going." : "That's not quite right. Try again."),
          why: result.explanation,
          next_idea: result.next_instruction?.is_user_move
            ? `Your turn: play ${result.next_instruction.move}`
            : `Watch: I'll play ${result.next_instruction?.move}`,
          has_better_move: !result.correct,
          can_explain: true,
          teaching_mode: true,
          remaining_moves: result.next_instruction?.remaining,
        });
      }

      if (result.teaching_fen) {
        setCurrentFen(result.teaching_fen);
      }

      if (result.auto_played) {
        setChatMessages((prev) => [
          ...prev,
          {
            type: "coach",
            trigger: "teaching",
            message: result.message,
            timestamp: Date.now(),
          },
        ]);
      }
    },
    [setChatMessages, setCurrentFen, setCurrentInsight]
  );

  const handleLessonComplete = useCallback(
    (completion) => {
      setLessonInstruction(null);
      setLessonComplete(completion);

      setChatMessages((prev) => [
        ...prev,
        {
          type: "coach",
          trigger: "encouragement",
          message: completion.message,
          timestamp: Date.now(),
        },
      ]);

      // Show additional info for trap completions
      if (completion.why_it_works) {
        setChatMessages((prev) => [
          ...prev,
          {
            type: "coach",
            trigger: "teaching",
            message: `Why it works: ${completion.why_it_works}`,
            timestamp: Date.now(),
          },
        ]);
      }

      toast.success("Lesson complete!");
    },
    [setChatMessages]
  );

  const handleExitLesson = useCallback(
    async (choice, result) => {
      setActiveLesson(null);
      setLessonComplete(null);
      setIsInTeachingMode(false);

      if (choice === "continue_game" && result?.restored_fen) {
        setCurrentFen(result.restored_fen);
        setChatMessages((prev) => [
          ...prev,
          {
            type: "coach",
            trigger: "teaching",
            message: "Game restored! Your turn to continue.",
            timestamp: Date.now(),
          },
        ]);
      } else if (choice === "new_game") {
        newGameFn();
        setTimeout(() => startGameFn(), 500);
      }
    },
    [setChatMessages, setCurrentFen, newGameFn, startGameFn]
  );

  const handleTeachingMove = useCallback(
    async (from, to) => {
      if (!activeLesson || !session) return false;

      const chess = new Chess(currentFen);
      let moveObj;
      try {
        moveObj = chess.move({ from, to, promotion: "q" });
      } catch {
        return false;
      }
      if (!moveObj) return false;

      try {
        const response = await fetch(`${API}/coach/play/teaching/move`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            session_id: session.session_id,
            move: moveObj.san,
          }),
        });

        if (response.ok) {
          const result = await response.json();

          if (result.complete) {
            handleLessonComplete(result);
          } else if (result.correct) {
            setCurrentFen(result.teaching_fen);
            handleTeachingMoveValidated(result);
            return true;
          } else {
            toast.error(result.message);
            setChatMessages((prev) => [
              ...prev,
              {
                type: "coach",
                trigger: "teaching",
                message: `${result.message} ${result.hint || ""}`,
                timestamp: Date.now(),
              },
            ]);
          }
        }
      } catch (error) {
        console.error("Teaching move error:", error);
      }

      return false;
    },
    [
      activeLesson,
      session,
      currentFen,
      handleLessonComplete,
      handleTeachingMoveValidated,
      setChatMessages,
      setCurrentFen,
    ]
  );

  return {
    // State (read by render + other hooks)
    teachingOffer,
    activeLesson,
    lessonInstruction,
    lessonComplete,
    isInTeachingMode,
    openingGuidance,
    inlineOpening,
    inlineTrap,
    coachIntroMessage,
    curriculumFeedback,
    lastCoachMoveSan,
    positionCoaching,
    openingCorrectionCount,
    // Setters (for external callers like pollCoachMessages, resumeSession)
    setTeachingOffer,
    setActiveLesson,
    setLessonInstruction,
    setLessonComplete,
    setIsInTeachingMode,
    setOpeningGuidance,
    setInlineOpening,
    setInlineTrap,
    setCoachIntroMessage,
    setCurriculumFeedback,
    setLastCoachMoveSan,
    setPositionCoaching,
    setOpeningCorrectionCount,
    // Handlers
    handleStartLesson,
    handleSkipTeachingOffer,
    handleExitLesson,
    handleTeachingMove,
    // Utilities
    resetTeachingState,
  };
};

export default useTeachingMode;
