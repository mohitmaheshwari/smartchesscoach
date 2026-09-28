/**
 * The behavioural traits are described, never graded.
 *
 * Its sibling AreaGradesCard scores board areas Excellent to Needs work. That
 * is right for a skill and wrong for a disposition: measured per player,
 * thinking longer goes with FEWER errors, not more, so "thinks too long - Needs
 * work" would be a judgement the data refuses.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("@/App", () => ({ API: "https://api.test/api" }), { virtual: true });
jest.mock("@/components/ui/card", () => ({
  Card: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  CardContent: ({ children }) => <div>{children}</div>,
  CardHeader: ({ children }) => <div>{children}</div>,
  CardTitle: ({ children }) => <div>{children}</div>,
}), { virtual: true });
jest.mock("lucide-react", () => ({ Loader2: () => null }), { virtual: true });

const HowYouPlayCard = require("./HowYouPlayCard").default;

let container;
let root;

const respond = (body) => {
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve(body) })
  );
};

const render = async () => {
  act(() => root.render(<HowYouPlayCard />));
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
};

beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  delete global.fetch;
});

test("it shows every line the server sends", async () => {
  respond({
    measured: true,
    lines: [
      { trait: "thinks_long", sentence: "You take long thinks." },
      { trait: "clock_front_loaded", sentence: "You keep time back for later." },
    ],
  });
  await render();
  expect(container.textContent).toContain("You take long thinks.");
  expect(container.textContent).toContain("You keep time back for later.");
});

test("it never renders a grade or a number", async () => {
  respond({
    measured: true,
    lines: [{ trait: "thinks_long", sentence: "You take long thinks." }],
    _traits: { thinks_long: 0.187, error_rate: 0.152 },
  });
  await render();
  const text = container.textContent;
  expect(text).not.toMatch(/\d/);
  for (const grade of ["Excellent", "Good", "Fair", "Needs work"]) {
    expect(text).not.toContain(grade);
  }
});

test("a player with too little history gets no card at all", async () => {
  respond({ measured: false, reason: "not enough games watched yet", lines: [] });
  await render();
  expect(container.querySelector('[data-testid="how-you-play-card"]')).toBeNull();
});

test("a failed request costs the page nothing", async () => {
  global.fetch = jest.fn(() => Promise.reject(new Error("offline")));
  await render();
  expect(container.querySelector('[data-testid="how-you-play-card"]')).toBeNull();
});

test("the balanced answer still renders, because a blank page is worse", async () => {
  /** Three of 48 players sit in the middle half on all seven traits, and one of
   *  them has 21,126 observed moves. "Nothing stands out" is a real answer. */
  respond({
    measured: true,
    lines: [{
      trait: "balanced",
      sentence: "Nothing about how you play stands out at either end.",
    }],
  });
  await render();
  expect(container.textContent).toContain("stands out at either end");
});
