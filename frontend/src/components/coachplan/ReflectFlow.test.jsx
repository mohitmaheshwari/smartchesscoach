import { createRoot } from "react-dom/client";
import { act } from "react";
import ReflectFlow from "./ReflectFlow";
import qf3Moment from "./__fixtures__/qf3Moment";
import { ne2Moment, nxe5Moment } from "./__fixtures__/reviewMoments";

const sign = { title: "The three looks", text: "Before any piece lands: pieces close by, knight jumps, long lines to the edge." };
const rule = { id: "three_looks", text: "Do the three looks before every move that puts a piece on a new square." };

let container; let root;
beforeEach(() => { container = document.createElement("div"); document.body.appendChild(container); root = createRoot(container); });
afterEach(() => { act(() => root.unmount()); container.remove(); });

const render = (el) => act(() => { root.render(el); });
const text = () => container.textContent;
const square = (label) => container.querySelector(`button[aria-label="${label}"]`);
const button = (name) => [...container.querySelectorAll("button")].find((b) => b.textContent === name);
const click = (el) => {
  if (!el) throw new Error("element not found");
  act(() => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
};

describe("ReflectFlow — piece safety moment (Qf3)", () => {
  test("asks what the move was for, with the board's options and no text box", () => {
    render(<ReflectFlow moment={qf3Moment} warningSign={sign} rule={rule} />);
    expect(text()).toContain("What was Qf3 for?");
    expect(button("Bring it into play")).toBeTruthy();
    expect(container.querySelector("textarea, input")).toBeNull();
    // the board's own options are tappable: two guards and one attack
    ["c3 white knight", "e4 white pawn", "f6 black knight"].forEach((l) => expect(square(l).className).toContain("live"));
  });

  test("two taps on ringed pieces, then Done, keeps both picks", () => {
    render(<ReflectFlow moment={qf3Moment} warningSign={sign} rule={rule} />);
    click(square("e4 white pawn"));
    click(square("f6 black knight"));
    click(button("Done"));
    expect(text()).toContain("To guard your pawn on e4 and attack his knight on f6.");
    // The e4 guard was really needed: its only guard was stuck in front of the king.
    expect(text()).toContain("stuck in front of your king, on the line of his bishop on b4");
    expect(text()).toContain("which of his pieces could take it?");
  });

  test("a tap taken back is not kept", () => {
    render(<ReflectFlow moment={qf3Moment} warningSign={sign} rule={rule} />);
    click(square("c3 white knight"));
    click(square("c3 white knight"));
    click(button("Bring it into play"));
    click(button("Done"));
    expect(text()).toContain("To bring my queen into play.");
    expect(text()).not.toContain("guard your knight on c3");
  });

  test("the whole moment ends in a reflection card and submits the answers", () => {
    const onSubmit = jest.fn();
    render(<ReflectFlow moment={qf3Moment} warningSign={sign} rule={rule} onSubmit={onSubmit} />);
    click(button("Bring it into play"));
    click(button("Done"));
    click(square("e5 black knight"));
    click(button("Done"));
    expect(text()).toContain("Yes, his knight on e5. You saw it.");
    click(button("No, I didn't see it"));
    expect(text()).toContain("What happened next: Nxf3+.");
    click(button("Your turn"));
    click(square("e2")); // Qe2: safe, and the engine rates it
    expect(text()).toContain("Safe. Nothing of his can reach e2.");
    expect(text()).toContain("The strongest move here was Bd2.");
    expect(text()).toContain("Your reflection");
    expect(text()).toContain("Your rule this week");
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      picks: [{ kind: "develop" }],
      found_when_asked: true,
      tapped: ["e5"],
      seen_in_game: "no",
      practice: ["d1e2"],
    }));
  });

  test("a missed knight is explained as a knight jump", () => {
    render(<ReflectFlow moment={qf3Moment} warningSign={sign} rule={rule} />);
    click(button("Not sure"));
    click(button("Done"));
    expect(text()).toContain("The piece that can take it is his knight on e5.");
    expect(text()).toContain("Knights jump.");
  });
});

// docs/review_tap_reflection_scope.md — the same flow inside a Game Review chapter.
describe("ReflectFlow — review mode", () => {
  const flush = () => act(async () => { await Promise.resolve(); });

  test("asks about the piece that can be taken, even when another piece moved", async () => {
    const onSubmit = jest.fn(() => Promise.resolve({}));
    const onClose = jest.fn();
    render(<ReflectFlow mode="review" moment={ne2Moment} onSubmit={onSubmit} onClose={onClose} closeLabel="See the explanation" />);
    expect(text()).toContain("You played Ne2.");
    expect(text()).not.toContain("Invalid Date");
    expect(container.querySelector("textarea, input")).toBeNull();
    click(button("Not sure"));
    expect(text()).toContain("After Ne2, which of his pieces could take your queen on f3?");
    click(square("e5 black knight"));
    click(button("Done"));
    expect(text()).toContain("Yes, his knight on e5. You saw it.");
    click(button("No, I didn't see it"));
    expect(text()).toContain("You found it just now when you looked for it.");
    // no practice step and no weekly card in review
    expect(button("Your turn")).toBeUndefined();
    expect(text()).not.toContain("Your reflection");
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ tapped: ["e5"], seen_in_game: "no" }));
    await flush();
    click(button("See the explanation"));
    expect(onClose).toHaveBeenCalled();
  });

  test("a failed save offers one button to try again", async () => {
    const onSubmit = jest.fn().mockRejectedValueOnce(new Error("x")).mockResolvedValueOnce({});
    render(<ReflectFlow mode="review" moment={ne2Moment} onSubmit={onSubmit} onClose={() => {}} />);
    click(button("Not sure"));
    click(button("Done"));
    click(button("Not sure"));
    await flush();
    expect(text()).toContain("I couldn't save that.");
    click(button("Try again"));
    await flush();
    expect(onSubmit).toHaveBeenCalledTimes(2);
    expect(button("Continue")).toBeTruthy();
  });

  test("find the move: one tap on Show me reveals it", () => {
    render(<ReflectFlow mode="review" moment={nxe5Moment} onSubmit={() => Promise.resolve({})} />);
    click(button("Not sure"));
    expect(text()).toContain("There was a move here that wins something. Find it.");
    click(button("Show me"));
    expect(text()).toContain("Here it is: Nxe5. It takes his knight on e5.");
    expect(text()).toContain("did you see Nxe5?");
  });

  test("find the move: another good move is checked by the server and accepted", async () => {
    const checkMove = jest.fn(() => Promise.resolve(true));
    render(<ReflectFlow mode="review" moment={nxe5Moment} checkMove={checkMove} onSubmit={() => Promise.resolve({})} />);
    click(button("Not sure"));
    click(square("d2 white pawn"));
    click(square("d4"));
    await flush();
    expect(checkMove).toHaveBeenCalledWith("d2d4");
    expect(text()).toContain("Yes, d4 works too. The engine's first choice was Nxe5.");
  });
});
