/**
 * The fork gets drawn, on the board it is true of.
 *
 * Mohit 2026-10-28: "ik clearly asked you to build arrow, but you didn't do
 * that, i dn't want a what if". The card described a fork and drew nothing.
 * These frames are what the board plays instead, and the one assertion that
 * matters is that the fork arrows appear on the ply the pawn reaches d5 and
 * on no earlier one -- on the card's own position the pawn is still on d7.
 */
import { buildLineFrames } from "./bestLineFrames";
import { namesMoveInText } from "./moveSeverity";

// His card, as the backend ships it: game 68cd307b, move 4, Bc5.
const HIS_CARD = {
  fen_before:
    "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R b KQkq - 5 4",
  fen_after:
    "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 6 5",
  caption:
    "You develop the bishop, bringing a new piece into the game. Though " +
    "Nxe4 was a bit stronger, it gives up material, then d5 hits the bishop " +
    "and the knight at once, and dxe4 wins the knight on e4.",
  line_steps: {
    played: [
      { san: "Bc5", from: "f8", to: "c5", side: "mover",
        captured_square: null, fork_targets: [] },
    ],
    best: [
      { san: "Nxe4", from: "f6", to: "e4", side: "mover",
        captured_square: "e4", fork_targets: [] },
      { san: "Nxe4", from: "c3", to: "e4", side: "opponent",
        captured_square: "e4", fork_targets: [] },
      { san: "d5", from: "d7", to: "d5", side: "mover",
        captured_square: null, fork_targets: ["c4", "e4"] },
      { san: "Bd3", from: "c4", to: "d3", side: "opponent",
        captured_square: null, fork_targets: [] },
      { san: "dxe4", from: "d5", to: "e4", side: "mover",
        captured_square: "e4", fork_targets: ["d3", "f3"] },
    ],
  },
};

describe("buildLineFrames on Mohit's Nxe4 card", () => {
  const frames = buildLineFrames(HIS_CARD, namesMoveInText);

  // Mohit, watching the first version: "it does't even show the move bishop
  // move, it removes the bishop and palys the alternative move, that
  // confuses user, like what just happened".
  test("it shows your move first, then steps back off it", () => {
    expect(frames[0].intro).toBe(true);
    expect(frames[0].san).toBe("Bc5");
    expect(frames[0].fen).toBe(HIS_CARD.fen_after);
    expect(frames[0].arrows).toEqual([["f8", "c5", "palegrey"]]);

    // The same arrow stays up while the board rewinds one ply, so the
    // bishop going home reads as undoing that move, not as a glitch.
    expect(frames[1].intro).toBe(true);
    expect(frames[1].fen).toBe(HIS_CARD.fen_before);
    expect(frames[1].arrows).toEqual([["f8", "c5", "palegrey"]]);
  });

  test("then it plays the line, and stops at the fork", () => {
    expect(frames.filter((f) => !f.intro).map((f) => f.san))
      .toEqual(["Nxe4", "Nxe4", "d5"]);
  });

  test("the two intro frames hold longer than a ply of the line", () => {
    expect(frames[0].hold).toBeGreaterThan(1200);
    expect(frames[1].hold).toBeGreaterThan(1200);
    expect(frames[2].hold).toBe(1500);
  });

  test("the fork is drawn on the ply the pawn reaches d5", () => {
    const last = frames[frames.length - 1];
    expect(last.arrows).toEqual(
      expect.arrayContaining([
        ["d5", "c4", "red"],
        ["d5", "e4", "red"],
      ])
    );
  });

  test("and on no earlier ply, because the pawn is not there yet", () => {
    for (const frame of frames.slice(0, -1)) {
      expect(frame.arrows.filter((a) => a[2] === "red")).toHaveLength(0);
      expect(frame.arrows.every((a) => a[0] !== "d5")).toBe(true);
    }
  });

  test("the move arrows accumulate, ours amber then blue, theirs grey", () => {
    const line = frames.filter((f) => !f.intro);
    expect(line[0].arrows).toEqual([["f6", "e4", "amber"]]);
    expect(line[1].arrows).toEqual([
      ["f6", "e4", "blue"],
      ["c3", "e4", "palegrey"],
    ]);
    expect(line[2].arrows.slice(0, 3)).toEqual([
      ["f6", "e4", "blue"],
      ["c3", "e4", "palegrey"],
      ["d7", "d5", "amber"],
    ]);
  });

  test("each frame is the real position after that ply", () => {
    const line = frames.filter((f) => !f.intro);
    // After Nxe4 Nxe4 d5 it is White to move and the pawn stands on d5.
    expect(line[2].fen.split(" ")[1]).toBe("w");
    expect(line[2].fen.split(" ")[0]).toContain("3p");
  });

  test("a capture paints the square the piece died on", () => {
    const line = frames.filter((f) => !f.intro);
    expect(line[0].highlights).toEqual(["e4"]);
    expect(line[2].highlights).toEqual([]);
    // The intro frames claim nothing died.
    expect(frames[0].highlights).toEqual([]);
  });
});

describe("buildLineFrames refuses what it cannot show", () => {
  test("no line, no frames", () => {
    expect(buildLineFrames({ fen_before: HIS_CARD.fen_before }, namesMoveInText))
      .toEqual([]);
    expect(buildLineFrames({ line_steps: HIS_CARD.line_steps }, namesMoveInText))
      .toEqual([]);
    expect(buildLineFrames(null, namesMoveInText)).toEqual([]);
  });

  test("a line that will not replay shows nothing, never something wrong", () => {
    const bogus = {
      ...HIS_CARD,
      line_steps: { best: [{ san: "Qh8", from: "d8", to: "h8",
                             side: "mover", fork_targets: [] }] },
    };
    expect(buildLineFrames(bogus, namesMoveInText)).toEqual([]);
  });

  test("with no fork it stops at the deepest move the caption names", () => {
    const quiet = {
      ...HIS_CARD,
      caption: "You played Bc5; Nxe4 was stronger.",
      line_steps: {
        best: HIS_CARD.line_steps.best.map((s) => ({ ...s, fork_targets: [] })),
      },
    };
    expect(buildLineFrames(quiet, namesMoveInText)
      .filter((f) => !f.intro).map((f) => f.san)).toEqual(["Nxe4"]);
  });

  // "Nxe4" is his move AND their recapture. Searching every ply matched
  // theirs and played a ply further than the card talks about.
  test("the opponent's identically-named reply is not what it stops on", () => {
    const collide = {
      ...HIS_CARD,
      caption: "You played Bc5; Nxe4 was stronger.",
      line_steps: {
        best: HIS_CARD.line_steps.best.map((s) => ({ ...s, fork_targets: [] })),
      },
    };
    const line = buildLineFrames(collide, namesMoveInText)
      .filter((f) => !f.intro);
    expect(line).toHaveLength(1);
    expect(line[0].arrows).toEqual([["f6", "e4", "amber"]]);
  });

  test("a fork the opponent gets in our line is not drawn as our lesson", () => {
    const theirs = {
      ...HIS_CARD,
      caption: "You played Bc5; Nxe4 was stronger.",
      line_steps: {
        best: HIS_CARD.line_steps.best.map((s, i) => ({
          ...s,
          fork_targets: i === 1 ? ["c4", "e4"] : [],
        })),
      },
    };
    const line = buildLineFrames(theirs, namesMoveInText)
      .filter((f) => !f.intro);
    expect(line.map((f) => f.san)).toEqual(["Nxe4"]);
    expect(line[0].arrows.filter((a) => a[2] === "red")).toHaveLength(0);
  });

  test("a caption naming nothing still shows the recommended move", () => {
    const silent = {
      ...HIS_CARD,
      caption: "That move does not change much here.",
      line_steps: {
        best: HIS_CARD.line_steps.best.map((s) => ({ ...s, fork_targets: [] })),
      },
    };
    expect(buildLineFrames(silent, namesMoveInText)
      .filter((f) => !f.intro).map((f) => f.san)).toEqual(["Nxe4"]);
  });
});
