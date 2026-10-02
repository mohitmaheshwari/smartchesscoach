// Whether a played-out line is worth transcribing under the board.
//
// Mohit 2026-10-02, on the "Why it was bad" and "What happens next" panels:
// "really bad stuff, i dont really like them, they just run stockfish".
//
// He is right about what they were showing. Trap lines carry an explanation
// per move (authored in data/traps.json). Engine punishment lines do not --
// the component builds them with `explanation: null` -- so the list collapsed
// to "1. h4  2. h5  3. g5  4. Nc6  5. a5": ply indices printed as if they were
// move numbers, both sides mixed together, and nothing taught. The board
// animation is the thing of value there; the transcript was engine output
// wearing a coaching label.
export function shouldTranscribeLine(lineSteps) {
  if (!Array.isArray(lineSteps) || lineSteps.length === 0) return false;
  return lineSteps.some((step) => step && step.explanation);
}
