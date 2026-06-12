// ─── Premium UX Motion Foundation ───
// Locked constants per docs/premium_ux_redesign_scope.md (2026-06-12).
// All page-level animation should import from here — no inline magic numbers.

import { useEffect } from "react";
import {
  motion,
  animate,
  useMotionValue,
  useTransform,
  useReducedMotion,
} from "framer-motion";

// Duration and easing constants
export const MOTION_TIMING = {
  micro: { duration: 150, easing: "easeOut" },
  standard: { duration: 300, easing: [0.22, 1, 0.36, 1] },
  page: { duration: 600, easing: "easeOut" },
  chart: { duration: 800, easing: "easeInOut" },
};

export const EASING = {
  snappy: [0.22, 1, 0.36, 1],
  bounce: [0.34, 1.56, 0.64, 1],
};

export const STAGGER_STEP = 60; // ms
export const ROW_STAGGER_STEP = 40; // ms — list rows (Lab archive, Progress tracked patterns)
export const NAV_FADE_MS = 400; // navbar mount fade (Landing)

// PWC board feel — locked in scope §"PWC Board Animations"
export const BOARD_PIECE_MS = 200; // chessground piece slide
export const CAPTURE_FADE_MS = 150; // captured piece fade (chessground built-in + CSS)
export const LAST_MOVE_GLOW_MS = 800; // amber last-move glow fade (index.css keyframes)

// Glow shadows — mirror tailwind.config.js boxShadow entries so Framer
// Motion whileHover targets stay in sync with the utility classes.
export const GLOW = {
  amber: "0 0 20px rgba(251, 191, 36, 0.5)",
  // Hover-lift shadow for nav tiles (2px lift + amber glow) — softer than
  // the full amber glow so a row of tiles doesn't strobe.
  amberLift: "0 4px 20px rgba(251, 191, 36, 0.3)",
  teal: "0 0 20px rgba(20, 184, 166, 0.4)",
  emerald: "0 0 20px rgba(16, 185, 129, 0.4)",
  rose: "0 0 20px rgba(244, 63, 94, 0.3)",
  none: "0 0 0px rgba(0, 0, 0, 0)",
};

// Reusable variants for Framer Motion.
// NOTE: transitions live INSIDE the animate/exit targets (not as sibling
// keys) so they apply when these objects are passed via `variants={...}`.
// Framer Motion ignores top-level `transition` keys on variant objects.
const standardTransition = {
  duration: MOTION_TIMING.standard.duration / 1000,
  ease: MOTION_TIMING.standard.easing,
};

export const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0, transition: standardTransition },
};

export const staggerContainer = {
  initial: { opacity: 0 },
  animate: {
    opacity: 1,
    transition: { staggerChildren: STAGGER_STEP / 1000, delayChildren: 0 },
  },
};

export const staggerItem = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0, transition: standardTransition },
};

export const pageEnter = {
  initial: { opacity: 0, y: 10 },
  animate: {
    opacity: 1,
    y: 0,
    transition: { duration: MOTION_TIMING.page.duration / 1000, ease: MOTION_TIMING.page.easing },
  },
  exit: {
    opacity: 0,
    y: -10,
    transition: { duration: MOTION_TIMING.page.duration / 1000, ease: MOTION_TIMING.page.easing },
  },
};

export const scaleIn = {
  initial: { scale: 0.95, opacity: 0 },
  animate: { scale: 1, opacity: 1, transition: standardTransition },
};

export const slideInRight = {
  initial: { x: 100, opacity: 0 },
  animate: { x: 0, opacity: 1, transition: standardTransition },
  exit: { x: 100, opacity: 0, transition: standardTransition },
};

export const slideInLeft = {
  initial: { x: -100, opacity: 0 },
  animate: { x: 0, opacity: 1, transition: standardTransition },
  exit: { x: -100, opacity: 0, transition: standardTransition },
};

const microTransition = {
  duration: MOTION_TIMING.micro.duration / 1000,
  ease: MOTION_TIMING.micro.easing,
};

const chartTransition = {
  duration: MOTION_TIMING.chart.duration / 1000,
  ease: MOTION_TIMING.chart.easing,
};

export const microHoverTransition = microTransition;
export const chartDrawTransition = chartTransition;

// ─── Phase 2 additions (page implementations) ───

// Navbar mount fade (Landing) — quiet, no movement.
export const navFade = {
  initial: { opacity: 0 },
  animate: {
    opacity: 1,
    transition: { duration: NAV_FADE_MS / 1000, ease: "easeOut" },
  },
};

// Hero headline word-by-word rise. Parent staggers children by
// STAGGER_STEP; each word rises with the standard settle.
export const wordRise = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: standardTransition },
};

export const heroHeadline = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: STAGGER_STEP / 1000,
      delayChildren: 0.2,
    },
  },
};

// Scroll-triggered reveal — spread onto a motion element:
//   <motion.section {...revealOnScroll}>
export const revealOnScroll = {
  initial: { opacity: 0, y: 20 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-60px" },
  transition: standardTransition,
};

// Card entrance with the locked 0.97→1 glow-pulse feel (Lab Coach's Pick).
export const cardGlowEnter = {
  initial: { scale: 0.97, opacity: 0 },
  animate: { scale: 1, opacity: 1, transition: standardTransition },
};

// One-shot amber glow pulse (board preview on Lab Coach's Pick).
export const glowPulseAmber = {
  initial: { boxShadow: GLOW.none },
  animate: {
    boxShadow: [GLOW.none, GLOW.amber, GLOW.none],
    transition: chartTransition,
  },
};

// Stagger container for dense lists — 40ms step instead of the 60ms
// section choreography step.
export const rowStaggerContainer = {
  initial: { opacity: 0 },
  animate: {
    opacity: 1,
    transition: { staggerChildren: ROW_STAGGER_STEP / 1000, delayChildren: 0 },
  },
};

export const rowStaggerItem = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0, transition: standardTransition },
};

// Per-row props for filter-change lists (Lab archive): old rows fade out
// (150ms, handled by the keyed parent's exit), new rows stagger in 40ms/row.
export const gameRowProps = (index) => ({
  initial: { opacity: 0, y: 10 },
  animate: {
    opacity: 1,
    y: 0,
    transition: {
      ...standardTransition,
      delay: (index * ROW_STAGGER_STEP) / 1000,
    },
  },
});

// Exit for a keyed list wrapper inside <AnimatePresence mode="wait">.
export const listFadeSwap = {
  initial: { opacity: 1 },
  animate: { opacity: 1 },
  exit: { opacity: 0, transition: microTransition },
};

// Move-quality chip pop (PWC board) — subtle spring.
export const springPop = {
  initial: { scale: 0.5, opacity: 0 },
  animate: {
    scale: 1,
    opacity: 1,
    transition: { type: "spring", stiffness: 200, damping: 18 },
  },
};

// ─── AnimatedNumber — counts to `value` over the chart timing ───
// <AnimatedNumber value={2.4} decimals={1} /> renders "0.0" → "2.4".
// Respects prefers-reduced-motion (renders final value immediately).
export function AnimatedNumber({
  value,
  decimals = 0,
  duration = MOTION_TIMING.chart.duration / 1000,
  className = "",
}) {
  const shouldReduceMotion = useReducedMotion();
  const count = useMotionValue(0);
  const display = useTransform(count, (latest) =>
    Number(latest).toFixed(decimals)
  );

  useEffect(() => {
    const target = Number(value) || 0;
    if (shouldReduceMotion) {
      count.set(target);
      return undefined;
    }
    const controls = animate(count, target, {
      duration,
      ease: MOTION_TIMING.chart.easing,
    });
    return () => controls.stop();
  }, [value, count, duration, shouldReduceMotion]);

  return <motion.span className={className}>{display}</motion.span>;
}
