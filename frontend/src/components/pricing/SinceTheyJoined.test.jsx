/**
 * The "Since they joined" strip.
 *
 * Each test is a rule this panel ships under, not a styling check.
 */

import { act } from "react";
import { createRoot } from "react-dom/client";
import SinceTheyJoined from "./SinceTheyJoined";

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

const render = (data) => act(async () => { root.render(<SinceTheyJoined data={data} />); });

const curve = (from, to) =>
  Array.from({ length: 24 }, (_, i) => Math.round(from + ((to - from) * i) / 23));

// The real production numbers, 2026-11-27.
const DATA = {
  schema_version: "rating_journeys.v1",
  counts: { measurable: 55, up: 32, flat: 2, down: 21, no_games_since_joining: 76, too_few_games: 7 },
  journeys: [
    { delta: 1115, start: 800, end: 1915, games: 718, curve: curve(800, 1915) },
    { delta: 899, start: 1079, end: 1978, games: 686, curve: curve(1079, 1978) },
  ],
};

test("shows the curves it was given", async () => {
  await render(DATA);

  expect(container.querySelectorAll('[data-testid="journey-card"]')).toHaveLength(2);
  expect(container.textContent).toContain("+1115");
  expect(container.textContent).toContain("800");
  expect(container.textContent).toContain("1915");
  expect(container.querySelectorAll("polyline")).toHaveLength(2);
});

test("prints its own denominator beside the winners", async () => {
  // A proof panel you cannot check against its base rate is an advert. Of
  // the 55 measurable players, 21 LOST rating over the same period, and
  // that number is on the page.
  await render(DATA);

  const denom = container.querySelector('[data-testid="journey-denominator"]');
  expect(denom).not.toBeNull();
  expect(denom.textContent).toContain("55");
  expect(denom.textContent).toContain("32 went up");
  expect(denom.textContent).toContain("21 went down");
});

test("never claims we caused it", async () => {
  // One player's rating rose 337 points while their mistake rates barely
  // moved, and most of these accounts predate the coaching features.
  await render(DATA);

  const text = container.textContent.toLowerCase();
  expect(text).toContain("not claiming we caused");
  for (const phrase of ["because of chessguru", "thanks to", "we improved", "our coaching made"]) {
    expect(text).not.toContain(phrase);
  }
});

test("shows no handle, no avatar and no user id", async () => {
  // A chess.com handle is public, but printing it beside our product name
  // asserts this person uses ChessGuru. Nobody consented to that.
  await render(DATA);

  expect(container.querySelectorAll("img")).toHaveLength(0);
  const json = JSON.stringify(DATA);
  expect(json).not.toMatch(/user_id|username|handle|avatar/i);
});

test("draws nothing at all rather than an empty frame while the cache warms", async () => {
  // The first request after the cache is empty returns no journeys instead
  // of holding a public page open for a 15-second computation.
  await render({ schema_version: "rating_journeys.v1", journeys: [], counts: null, warming: true });
  expect(container.textContent).toBe("");

  await render(null);
  expect(container.textContent).toBe("");
});

test("survives a journey with a flat curve", async () => {
  await render({
    ...DATA,
    journeys: [{ delta: 0, start: 1200, end: 1200, games: 40, curve: curve(1200, 1200) }],
  });
  expect(container.querySelector("polyline")).not.toBeNull();
  expect(container.textContent).toContain("1200");
});
