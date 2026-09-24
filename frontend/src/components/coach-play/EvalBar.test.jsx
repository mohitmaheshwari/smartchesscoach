/**
 * The eval bar on Play with Coach.
 *
 * This component was written, imported by CoachPlayBoard, handed an
 * `evaluation` prop on every move — and rendered by nothing, for five months.
 * The first block exists to make that specific failure loud: a component that
 * is imported but never placed looks completely healthy to the compiler, to
 * lint, and to every other test in the repo.
 */
import fs from "fs";
import path from "path";
import { act } from "react";
import { createRoot } from "react-dom/client";
import EvalBar from "./EvalBar";

function draw(props) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  act(() => {
    root.render(<EvalBar {...props} />);
  });
  return {
    host,
    text: () => host.textContent || "",
    bar: () => host.querySelector('[data-testid="eval-bar"]'),
    score: () => host.querySelector('[data-testid="eval-text"]'),
    cleanup: () => act(() => root.unmount()),
  };
}

describe("the board actually renders the bar", () => {
  const boardSource = fs.readFileSync(
    path.join(__dirname, "..", "coach", "CoachPlayBoard.jsx"),
    "utf8"
  );

  it("places an <EvalBar> element, not just an import", () => {
    expect(boardSource).toMatch(/<EvalBar\b/);
  });

  it("feeds it the evaluation and the hide flag the page already tracks", () => {
    const element = boardSource.slice(boardSource.indexOf("<EvalBar"));
    expect(element).toMatch(/evaluation=\{evaluation\}/);
    expect(element).toMatch(/hidden=\{hideEvalBar\}/);
  });
});

describe("what the bar says", () => {
  it("shows a signed score the player can read at a glance", () => {
    const v = draw({ evaluation: { score: 1.7, mate_in: null }, userColor: "white" });
    expect(v.score().textContent).toBe("+1.7");
    v.cleanup();
  });

  it("shows the other side ahead as a negative score", () => {
    const v = draw({ evaluation: { score: -2.4, mate_in: null }, userColor: "white" });
    expect(v.score().textContent).toBe("-2.4");
    v.cleanup();
  });

  it("calls a dead-level position 0.0, not a tiny signed number", () => {
    const v = draw({ evaluation: { score: 0.04, mate_in: null }, userColor: "white" });
    expect(v.score().textContent).toBe("0.0");
    v.cleanup();
  });

  it("says mate in N instead of a centipawn score", () => {
    const v = draw({ evaluation: { score: 99, mate_in: 3 }, userColor: "white" });
    expect(v.score().textContent).toBe("+M3");
    v.cleanup();
  });

  it("survives a missing evaluation instead of taking the board down", () => {
    const v = draw({ evaluation: null, userColor: "white" });
    expect(v.score().textContent).toBe("0.0");
    v.cleanup();
  });
});

describe("withholding the position when the coach means to", () => {
  it("masks the score to a question mark", () => {
    const v = draw({
      evaluation: { score: 4.2, mate_in: null },
      userColor: "white",
      hidden: true,
    });
    expect(v.bar()).not.toBeNull();
    expect(v.score()).toBeNull();
    expect(v.text()).toContain("?");
    v.cleanup();
  });

  it("does not leak the number it is hiding, in text or in bar height", () => {
    const v = draw({
      evaluation: { score: 4.2, mate_in: null },
      userColor: "white",
      hidden: true,
    });
    expect(v.text()).not.toMatch(/4\.2/);
    // The shape would give away what the text refused to say, so the hidden
    // bar must not be drawn at the real position's height either.
    v.host.querySelectorAll("[style]").forEach((el) => {
      expect(el.getAttribute("style") || "").not.toMatch(/height:/);
    });
    v.cleanup();
  });
});
