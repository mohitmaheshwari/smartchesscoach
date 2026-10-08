import { shouldTranscribeLine } from "./coachLine";

describe("a line is only transcribed when it explains itself", () => {
  test("an engine punishment line is not transcribed", () => {
    // How the component builds it: pv moves with no explanation.
    const steps = ["h4", "h5", "g5", "Nc6", "a5"].map((m) => ({ move: m, explanation: null }));
    expect(shouldTranscribeLine(steps)).toBe(false);
  });

  test("an authored trap line is transcribed", () => {
    const steps = [
      { move: "Nxf7", explanation: "White gives up the knight to pull the king out." },
      { move: "Kxf7", explanation: "Black must capture." },
      { move: "Qf3+", explanation: "Check! Double attack on king and knight." },
    ];
    expect(shouldTranscribeLine(steps)).toBe(true);
  });

  test("a partly explained line still earns its transcript", () => {
    expect(shouldTranscribeLine([
      { move: "Re1", explanation: null },
      { move: "Bd2", explanation: "The bishop has to run." },
    ])).toBe(true);
  });

  test("nothing at all is not transcribed", () => {
    expect(shouldTranscribeLine([])).toBe(false);
    expect(shouldTranscribeLine(null)).toBe(false);
    expect(shouldTranscribeLine(undefined)).toBe(false);
  });
});
