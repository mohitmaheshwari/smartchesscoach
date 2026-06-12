// ─── Reduced-motion-aware motion value hook ───
// Part of the premium UX foundation (docs/premium_ux_redesign_scope.md).
// Components should check `shouldSkipAnimation` and render final state
// immediately when the user prefers reduced motion.

import { useMotionValue, useReducedMotion } from "framer-motion";

export function useMotionSafe(initialValue = 0) {
  const shouldReduceMotion = useReducedMotion();
  const value = useMotionValue(initialValue);
  return { value, shouldSkipAnimation: shouldReduceMotion };
}
