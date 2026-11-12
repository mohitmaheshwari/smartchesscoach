/**
 * The design system, asserted rather than eyeballed.
 *
 * Context (2026-11-12): tailwind.config.js had no `fontSize` scale at all,
 * which is why src carries 40 distinct arbitrary pixel sizes including
 * text-[10.5px] (72 uses) and text-[12.5px] (53). Nothing named the right
 * answer, so text-[Npx] was the path of least resistance.
 *
 * The collision test below is the load-bearing one. The first version of the
 * scale used the names `sm` and `base`, which are Tailwind defaults — and src
 * uses text-sm 1,468 times and text-base 112 times. Shipping that would have
 * silently changed the line-height of the whole app with no visual regression
 * cover. The scale is additive on purpose; this test keeps it that way.
 */
const config = require("../tailwind.config.js");

const scale = config.theme.extend.fontSize;
const radii = config.theme.extend.borderRadius;
const shadows = config.theme.extend.boxShadow;

// Every size Tailwind already ships. Naming any of these would silently
// restyle existing markup instead of adding a new option.
const TAILWIND_DEFAULT_TEXT = [
  "xs", "sm", "base", "lg", "xl",
  "2xl", "3xl", "4xl", "5xl", "6xl", "7xl", "8xl", "9xl",
];

describe("type scale", () => {
  it("names exactly the six steps, smallest to largest", () => {
    expect(Object.keys(scale)).toEqual([
      "meta", "note", "body", "lead", "title", "display",
    ]);
  });

  it("collides with no Tailwind default, so existing markup is untouched", () => {
    const clashes = Object.keys(scale).filter((k) =>
      TAILWIND_DEFAULT_TEXT.includes(k));
    expect(clashes).toEqual([]);
  });

  it("floors at 12px — 10 and 11px body text is what read as cheap", () => {
    const px = (v) => parseFloat(Array.isArray(v) ? v[0] : v) * 16;
    expect(px(scale.meta)).toBe(12);
    expect(Math.min(...Object.values(scale).map(px))).toBe(12);
  });

  it("rises monotonically, so a step is always a real step", () => {
    const px = (v) => parseFloat(Array.isArray(v) ? v[0] : v) * 16;
    const sizes = Object.values(scale).map(px);
    expect(sizes).toEqual([...sizes].sort((a, b) => a - b));
    expect(new Set(sizes).size).toBe(sizes.length);
  });

  it("carries a line height on every step", () => {
    for (const [name, value] of Object.entries(scale)) {
      expect(Array.isArray(value)).toBe(true);
      expect(value[1]).toHaveProperty("lineHeight");
      expect(String(value[1].lineHeight)).not.toBe("");
      expect(name).toBeTruthy();
    }
  });
});

describe("radii and elevation", () => {
  it("adds three named radii without dropping the shadcn ones", () => {
    expect(radii).toEqual(expect.objectContaining({
      control: "0.5rem", card: "0.875rem", panel: "1.5rem",
    }));
    // lg/md/sm feed shadcn's components off --radius; removing them would
    // restyle every ui/ primitive at once.
    for (const k of ["lg", "md", "sm"]) expect(radii[k]).toMatch(/var\(--radius\)/);
  });

  it("defines three NEUTRAL elevations, not only coloured glows", () => {
    for (const k of ["e1", "e2", "e3"]) {
      expect(shadows[k]).toBeTruthy();
      expect(shadows[k]).toMatch(/rgb\(0 0 0/);
    }
  });

  it("keeps the glows, which are a separate, intentional set", () => {
    expect(Object.keys(shadows)).toEqual(
      expect.arrayContaining(["glow-amber", "glow-emerald"]));
  });
});
