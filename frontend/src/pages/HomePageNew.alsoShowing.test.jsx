/**
 * Home named one thing out of six the system holds.
 *
 * The picker already ranks the other board areas and writes them onto the
 * focus document; every one was thrown away. components/FocusCard.jsx had this
 * block built and nothing ever mounted that component.
 *
 * These tests cover the block only, not the whole page, because the page pulls
 * four endpoints and the point here is what gets rendered from runners_up.
 */
import { createRoot } from "react-dom/client";
import { act } from "react";

// The block, extracted exactly as the page renders it.
function AlsoShowing({ activeFocus }) {
  if (!Array.isArray(activeFocus?.runners_up) || activeFocus.runners_up.length === 0) {
    return null;
  }
  return (
    <div>
      <p>Also showing in your games</p>
      <div>
        {activeFocus.runners_up.slice(0, 3).map((r) => (
          <span key={r.topic || r.topic_key} data-testid="also-showing">
            {String(r.topic || r.topic_key || "").replace(/_/g, " ")}
          </span>
        ))}
      </div>
      <p>Not this week&rsquo;s job. Just so you know I can see them.</p>
    </div>
  );
}

let container, root;
beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(() => { act(() => root.unmount()); container.remove(); });

const render = (focus) => act(() => root.render(<AlsoShowing activeFocus={focus} />));
const chips = () => Array.from(container.querySelectorAll('[data-testid="also-showing"]'))
  .map((n) => n.textContent);

const REAL = {
  runners_up: [
    { topic: "piece_safety", score: 3.681, evidence_count: 132 },
    { topic: "king_safety", score: 3.492, evidence_count: 151 },
    { topic: "missed_tactic", score: 1.852, evidence_count: 54 },
  ],
};

test("the other areas the games prove are shown", () => {
  render(REAL);
  expect(chips()).toEqual(["piece safety", "king safety", "missed tactic"]);
});

test("no count and no score reaches the screen", () => {
  render(REAL);
  expect(container.textContent).not.toMatch(/\d/);
});

test("it stays a mention, never a second instruction", () => {
  render(REAL);
  expect(container.textContent).toContain("Not this week");
  expect(container.textContent).not.toMatch(/practise|practice|drill|work on/i);
});

test("at most three, however many the picker ranked", () => {
  render({ runners_up: [
    { topic: "a_one" }, { topic: "b_two" }, { topic: "c_three" },
    { topic: "d_four" }, { topic: "e_five" },
  ] });
  expect(chips()).toHaveLength(3);
});

test("a player with no runners-up gets no empty heading", () => {
  render({ runners_up: [] });
  expect(container.textContent).toBe("");
  render({});
  expect(container.textContent).toBe("");
});

test("the newer topic_key spelling is accepted too", () => {
  render({ runners_up: [{ topic_key: "time_management" }] });
  expect(chips()).toEqual(["time management"]);
});
