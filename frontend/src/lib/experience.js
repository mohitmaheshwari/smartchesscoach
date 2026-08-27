/**
 * Premium frontend experience rollout gate.
 *
 * CRA substitutes this at build time. Keep the fallback false so an
 * unconfigured deployment always renders the established experience.
 */
export const EXPERIENCE_V1_ENABLED =
  process.env.REACT_APP_FRONTEND_EXPERIENCE_V1_ENABLED === "true";

