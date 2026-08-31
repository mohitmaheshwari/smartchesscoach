/**
 * Premium frontend experience rollout gate.
 *
 * CRA substitutes this at build time. The inner-product redesign was approved
 * as a replacement, so an unconfigured deployment must render the new shared
 * shell. Setting the flag explicitly to "false" remains an emergency rollback.
 */
export const EXPERIENCE_V1_ENABLED =
  process.env.REACT_APP_FRONTEND_EXPERIENCE_V1_ENABLED !== "false";

