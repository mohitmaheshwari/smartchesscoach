import { createRoot } from "react-dom/client";
import { act } from "react";
import ReflectFlow from "./ReflectFlow";
import qf3Moment from "./__fixtures__/qf3Moment";
import { ne2Moment, nxe5Moment } from "./__fixtures__/reviewMoments";
import developmentMoment from "./__fixtures__/developmentMoment";
import { qf3StoryMoment } from "./__fixtures__/reviewQf3Story";

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

// docs/review_tap_reflection_scope.md, amendment 2: walk through Qf3 the way a
// coach would — his problem first, credit, the check, the story, the cause
// read from the game, then another way to solve his problem.
describe("ReflectFlow — review mode, Qf3 as a coach would take it", () => {
  const flush = () => act(async () => { await Promise.resolve(); });

  test("starts from his problem, credits the idea, tells the story, and asks for another way", async () => {
    const onSubmit = jest.fn(() => Promise.resolve({}));
    const checkBetter = jest.fn(() => Promise.resolve({
      ok: true, san: "Bd2",
      words: "Yes. Bd2 breaks the pin, so your knight on c3 guards e4 again. It also brings a piece into play.",
      best: { uci: "c1d2", san: "Bd2", words: "Bd2 breaks the pin, so your knight on c3 guards e4 again." },
    }));
    render(<ReflectFlow mode="review" moment={qf3StoryMoment} onSubmit={onSubmit} checkBetter={checkBetter} onClose={() => {}} />);
    expect(text()).toContain("Before Qf3, what were you worried about?");
    expect(text()).not.toContain("What was Qf3 for?");
    click(square("e4 white pawn"));
    expect(text()).toContain("Right. His knight on f6 was attacking it, and your knight on c3 couldn't help: his bishop on b4 pins it to your king.");
    expect(text()).toContain("Qf3 guards it, and it also attacks his knight on f6. Good idea.");
    expect(text()).toContain("which of his pieces could take it?");
    click(square("e5 black knight"));
    click(button("Done"));
    expect(text()).toContain("He didn't take it. He played O-O.");
    expect(text()).toContain("Then you played Ne2, he played d5, and you played exd5. Your queen was still on f3.");
    expect(text()).toContain("Then he took it with Nxf3+.");
    // the game already answered "did you see it?" — no question
    expect(text()).not.toContain("One honest question");
    expect(text()).toContain("In the game you left your queen there for two more moves, so you didn't see it.");
    expect(text()).toContain("How else could you look after your pawn on e4?");
    click(square("c1 white bishop"));
    click(square("d2"));
    await flush();
    expect(checkBetter).toHaveBeenCalledWith("c1d2");
    expect(text()).toContain("Yes. Bd2 breaks the pin");
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      picks: [{ kind: "worried", sq: "e4" }], tapped: ["e5"], seen_in_game: "no", better: ["c1d2"],
    }));
  });

  test("a wrong first worry still gets the real problem explained, and Show me reveals a better way", async () => {
    const checkBetter = jest.fn(() => Promise.resolve({ best: { uci: "c1d2", san: "Bd2", words: "Bd2 breaks the pin, so your knight on c3 guards e4 again." } }));
    render(<ReflectFlow mode="review" moment={qf3StoryMoment} onSubmit={() => Promise.resolve({})} checkBetter={checkBetter} />);
    click(button("Nothing, I had a plan"));
    expect(text()).toContain("Look at your pawn on e4. His knight on f6 was attacking it");
    click(button("Done"));
    expect(text()).toContain("The piece that can take it is his knight on e5.");
    expect(text()).toContain("It's a knight jump, and that's what we'll practise.");
    click(button("Show me"));
    await flush();
    expect(checkBetter).toHaveBeenCalledWith(null);
    expect(text()).toContain("Here's one: Bd2 breaks the pin");
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

describe("ReflectFlow — development moment (scope amendment A)", () => {
  const devSign = { title: "Pieces still at home", text: "In the opening, look at your back row." };
  const devRule = { id: "new_piece_each_move", text: "Before move 10, every move brings a new piece out, unless something is attacked." };
  const flush = () => act(async () => { await Promise.resolve(); });

  test("names the pieces still at home and asks which should come out", () => {
    render(<ReflectFlow moment={developmentMoment} warningSign={devSign} rule={devRule} />);
    click(button("Not sure"));
    expect(text()).toContain("your knight on b1, bishop on c1, bishop on f1 and knight on g1 were still at home");
    expect(text()).toContain("Which piece should come out, and where?");
  });

  test("a developing answer is accepted and explained; a non-developing one is never sent to the server", async () => {
    const checkMove = jest.fn(() => Promise.resolve(true));
    const onSubmit = jest.fn();
    render(<ReflectFlow moment={developmentMoment} warningSign={devSign} rule={devRule} checkMove={checkMove} onSubmit={onSubmit} />);
    click(button("Not sure"));
    click(square("g1 white knight"));
    click(square("f3"));
    await flush();
    expect(checkMove).not.toHaveBeenCalled();
    expect(text()).toContain("Not that one. Have another look.");
    click(square("b1 white knight"));
    click(square("c3"));
    expect(text()).toContain("Yes, Nc3. It brings your knight into the game.");
    expect(text()).toContain("did you see that your knight on b1");
    click(button("No, I didn't see it"));
    expect(text()).toContain("Still at home: knight on b1");
  });
});
