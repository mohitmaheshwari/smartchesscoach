import { act } from "react";
import { createRoot } from "react-dom/client";
import BoardCoordinates, { SQUARE_TAG } from "./BoardCoordinates";

global.IS_REACT_ACT_ENVIRONMENT = true;

let container;
let root;
beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

const draw = (props) => act(() => root.render(<BoardCoordinates {...props} />));
const tag = (square) => container.querySelector(`[data-testid="square-tag-${square}"]`);
const tags = () => container.querySelectorAll('[data-testid^="square-tag-"]');

const luminance = (hex) => {
  const channel = (i) => {
    const v = parseInt(hex.slice(i, i + 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5);
};
const contrast = (a, b) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};
// jsdom reports colours as rgb(); the browser does the same for hex styles.
const rgb = (hex) => `rgb(${[1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(", ")})`;

test("a tagged board names all 64 squares at any width", () => {
  draw({ tagged: true });
  expect(tags()).toHaveLength(64);
  expect(tag("a1").textContent).toBe("a1");
  expect(tag("h8").textContent).toBe("h8");
});

test("each tag takes the colour of its own square", () => {
  draw({ tagged: true });
  // a1 is a dark square, a2 a light one.
  expect(tag("a1").style.backgroundColor).toBe(rgb(SQUARE_TAG.dark.background));
  expect(tag("a2").style.backgroundColor).toBe(rgb(SQUARE_TAG.light.background));
});

test("flipping the board moves a1 to the top right", () => {
  draw({ tagged: true, orientation: "black" });
  const box = tag("a1").parentElement;
  expect(box.style.left).toBe("87.5%");
  expect(box.style.top).toBe("0%");
});

test("tag text is readable on both squares", () => {
  expect(contrast(SQUARE_TAG.light.color, SQUARE_TAG.light.background)).toBeGreaterThanOrEqual(4.5);
  expect(contrast(SQUARE_TAG.dark.color, SQUARE_TAG.dark.background)).toBeGreaterThanOrEqual(4.5);
});

test("an untagged board keeps the size rule and the plain labels", () => {
  draw({});
  expect(tags()).toHaveLength(0);
  expect(container.textContent).toBe("");
});
