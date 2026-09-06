export function buildTrainingFeedbackView({
  puzzleState,
  userMove,
  sourceMove,
  verifiedSolution,
  patternType,
  coaching,
  fallback,
}) {
  const solved = puzzleState === "correct" || puzzleState === "acceptable";
  const revealed = puzzleState === "revealed";
  const safeRetry = puzzleState === "concept_pass";
  const retry = puzzleState === "incorrect" || safeRetry;

  let outcome = "retry";
  if (solved) outcome = "correct";
  if (safeRetry) outcome = "safe";
  if (revealed) outcome = "revealed";

  let san = userMove ? `${userMove} (you played)` : "";
  if (solved) {
    san = userMove || verifiedSolution || "";
  } else if (revealed) {
    const answerLabel = patternType === "piece_safety"
      ? "safer move"
      : "coach's move";
    san = sourceMove && verifiedSolution
      ? `${sourceMove} (from the game) · ${verifiedSolution} (${answerLabel})`
      : verifiedSolution || "";
  }

  return {
    outcome,
    san,
    headline: coaching?.why || coaching?.lesson || fallback,
    takeaway: coaching?.remember || coaching?.takeaway || "",
    nextStep: coaching?.behavior || "",
    showSolution: revealed,
    canReveal: retry,
  };
}
