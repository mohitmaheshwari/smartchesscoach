/**
 * Should the sidebar show its "before the first move" line?
 *
 * Every coaching panel in CoachPlaySidebar is gated on something that only
 * exists AFTER a move: guardianIntervention needs a pendingMove, v5Coaching
 * needs a played move, feedback needs a request in flight. So at move 0 the
 * panel rendered a goal card and then two-thirds of empty space -- at the one
 * moment a player is deciding whether this thing is going to help them.
 *
 * The line states when the coach actually speaks. That is a true claim, not
 * filler: the guardian interrupts BEFORE a risky move. Silence then reads as
 * the coach waiting rather than the coach being broken.
 *
 * Strictly move 0. Mid-game silence is a different question and this must
 * never start explaining itself over a live position.
 */
export const shouldShowWaitingLine = ({
  gameOver,
  guardianIntervention,
  geometryMoment,
  v5Coaching,
  loadingFeedback,
  moveCount,
} = {}) => {
  if (gameOver) return false;
  if (guardianIntervention || geometryMoment || v5Coaching || loadingFeedback) return false;
  return (moveCount || 0) === 0;
};

export default shouldShowWaitingLine;
