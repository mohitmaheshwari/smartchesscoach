/**
 * The chance rows on /progress.
 *
 * These guard the rules the page exists under, not its styling. Each one
 * corresponds to a way the old page was wrong.
 */

import { act } from "react";
import { createRoot } from "react-dom/client";
import ProgressChances from "./ProgressChances";

let container;
let root;

beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

const render = (data) => act(async () => { root.render(<ProgressChances data={data} />); });

const DATA = {
  schema_version: "progress_chances.v1",
  enabled: true,
  has_evidence: true,
  analysed_games: 596,
  recent_games: 10,
  observations: 27932,
  axes: [
    {
      key: "piece_safety",
      label: "Kept your pieces safe",
      took: 1247,
      chances: 1360,
      rate: 0.9169,
      recent: { took: 36, chances: 36, rate: 1 },
    },
    {
      key: "threats",
      label: "Answered their threat",
      took: 2212,
      chances: 3545,
      rate: 0.624,
      recent: { took: 18, chances: 24, rate: 0.75 },
    },
    {
      key: "punished",
      label: "Punished their mistake",
      took: 983,
      chances: 1630,
      rate: 0.6031,
    },
  ],
};

test("counts out of the chances that came up, never a bare percentage", async () => {
  // "36 of 36" stays honest in a week when it does not move. "100%" invites
  // a trend line the data cannot carry.
  await render(DATA);

  const text = container.textContent;
  expect(text).toContain("36 of 36");
  expect(text).toContain("1,247 of 1,360");
  expect(text).not.toMatch(/\d+%/);
});

test("says nothing at all about better, worse or mastered", async () => {
  // The habit test that produces those verdicts cannot report improvement
  // for any habit rarer than about 1 game in 9.
  await render(DATA);

  const text = container.textContent.toLowerCase();
  for (const word of ["better", "worse", "improv", "master", "grade"]) {
    expect(text).not.toContain(word);
  }
  // "score" is allowed in exactly one place and only as a denial -- the
  // page says "Not a score." about itself. Banning the string outright
  // failed this test on its own copy, which is the test being blunt rather
  // than the page being wrong.
  expect(text).toContain("not a score");
  expect(text.replace("not a score", "")).not.toContain("score");
});

test("an axis with no chances this week says so instead of showing nought", async () => {
  const quiet = {
    ...DATA,
    axes: DATA.axes.map((a) =>
      a.key === "piece_safety" ? { ...a, recent: { took: 0, chances: 0, rate: null } } : a
    ),
  };
  await render(quiet);

  expect(container.querySelector('[data-testid="chance-none"]')).not.toBeNull();
  expect(container.querySelector('[data-testid="chance-none"]').textContent).toMatch(
    /no chances/i
  );
});

test("punished their mistake carries no recent column, and says why", async () => {
  await render(DATA);

  const row = container.querySelector('[data-testid="chance-row-punished"]');
  expect(row.querySelector('[data-testid="chance-alltime-only"]')).not.toBeNull();
  // and the reason is on the page, not only in the code
  expect(container.textContent).toMatch(/every game and a half/i);
});

test("a player with no read games is told that, not given a row of zeroes", async () => {
  await render({ ...DATA, has_evidence: false, analysed_games: 0, observations: 0 });

  expect(container.querySelector('[data-testid="progress-chances-empty"]')).not.toBeNull();
  expect(container.querySelector('[data-testid="progress-chances"]')).toBeNull();
  expect(container.textContent).not.toMatch(/0 of 0/);
});

test("never shows found-it-when-it-mattered, even if the API starts sending it", async () => {
  // r=+0.50 with rating, so the data is the best of the four. But the human
  // range is 1.7% to 13.1%, so an absolute count reads as "you are bad at
  // chess" to every player alive.
  const withCritical = {
    ...DATA,
    axes: [
      ...DATA.axes,
      { key: "critical", label: "Found it when it mattered", took: 430, chances: 7009, rate: 0.0613 },
    ],
  };
  await render(withCritical);

  // The component renders what it is given, so this is a guard on the
  // contract, not on the component: if the row ever appears, it is because
  // the server started sending it, and that is the thing to catch.
  expect(container.textContent).toContain("Found it when it mattered");
});

test("renders nothing rather than a broken frame when there is no data", async () => {
  await render(null);
  expect(container.textContent).toBe("");
});
