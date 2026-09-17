import { createRoot } from "react-dom/client";
import { act } from "react";
import HomeLoadingSkeleton from "@/components/HomeLoadingSkeleton";

let container, root;
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

test("it announces itself as busy rather than sitting silently", async () => {
  await act(async () => root.render(<HomeLoadingSkeleton />));
  const panel = container.querySelector('[data-testid="home-loading-skeleton"]');
  expect(panel).not.toBeNull();
  expect(panel.getAttribute("aria-busy")).toBe("true");
  expect(panel.getAttribute("role")).toBe("status");
  // A spinner alone told a screen reader nothing at all.
  expect(container.textContent).toContain("Loading your coaching home");
});

test("it matches the real page's width so nothing jumps on load", async () => {
  await act(async () => root.render(<HomeLoadingSkeleton />));
  const panel = container.querySelector('[data-testid="home-loading-skeleton"]');
  // CurriculumHome renders cg-page max-w-[960px]; the skeleton must agree.
  expect(panel.className).toContain("cg-page");
  expect(panel.className).toContain("max-w-[960px]");
});

test("the rows are staggered, which is what makes it read as a wave", async () => {
  await act(async () => root.render(<HomeLoadingSkeleton />));
  const delays = Array.from(container.querySelectorAll("[style]"))
    .map((el) => el.style.animationDelay)
    .filter(Boolean);
  expect(delays.length).toBeGreaterThan(8);
  // Not all the same value — a uniform pulse is the thing being replaced.
  expect(new Set(delays).size).toBeGreaterThan(5);
});

test("every shimmering row opts out under prefers-reduced-motion", async () => {
  await act(async () => root.render(<HomeLoadingSkeleton />));
  const pulsing = Array.from(container.querySelectorAll(".animate-pulse"));
  expect(pulsing.length).toBeGreaterThan(8);
  for (const el of pulsing) {
    expect(el.className).toContain("motion-reduce:animate-none");
  }
});
