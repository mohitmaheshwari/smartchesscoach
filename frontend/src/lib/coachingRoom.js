/**
 * Coaching-room presentation gate (client side).
 *
 * The decision is made on the server and arrives as `coaching_room_v2` on the
 * /auth/me payload, which ProtectedRoute already fetches. Nothing here decides
 * who is enrolled -- see backend/services/coaching_room_gate.py.
 *
 * Deliberately NOT a REACT_APP_* flag: CRA bakes those into one bundle at build
 * time, so a build-time flag cannot serve two accounts differently on a single
 * deployment. See docs/coaching_room_all_pages_spec.md section 5.
 *
 * Public pages are a deliberate exception. They have no account, so a
 * per-account gate cannot reach them: Landing and friends render outside
 * ProtectedRoute, so nothing there ever sees an /auth/me payload. Mohit ruled
 * on 2026-09-22 that public surfaces adopt the design unconditionally rather
 * than carry a second flag, so the front door stops contradicting the app.
 *
 * Exactly one component owns the <html> class at a time -- CoachingRoomProvider
 * on protected routes, CoachingRoomPublic on public ones. A given URL is one or
 * the other, never both, so they cannot fight over it.
 *
 * Two consumers:
 *   - a class on <html>, so stylesheets can scope every new rule under it and
 *     a disabled account renders byte-identical presentation to today;
 *   - useCoachingRoom(), for components that compose differently rather than
 *     just restyle.
 */

import { createContext, createElement, useContext, useEffect } from "react";

export const COACHING_ROOM_CLASS = "coaching-room";

/** Read the server's decision off an /auth/me payload. Absent means off. */
export function isCoachingRoomEnabled(user) {
  return Boolean(user && user.coaching_room_v2 === true);
}

const CoachingRoomContext = createContext(false);

/**
 * Public routes, taken from the routes in App.js that are NOT wrapped in
 * ProtectedRoute. Redirect-only routes are excluded: they render no page.
 */
const PUBLIC_EXACT = new Set([
  "/",
  "/login",
  "/invite",
  "/pricing",
  "/terms",
  "/privacy",
  "/refund",
  "/contact",
  "/learn/openings",
]);

const PUBLIC_PREFIXES = ["/learn/openings/", "/prototype/"];

/** True for a page that has no account and therefore cannot be gated. */
export function isPublicCoachingRoomPath(pathname) {
  const path = String(pathname || "");
  if (PUBLIC_EXACT.has(path)) return true;
  return PUBLIC_PREFIXES.some((prefix) => path.startsWith(prefix));
}

/** True when the current account is enrolled in the redesign. */
export function useCoachingRoom() {
  return useContext(CoachingRoomContext);
}

/**
 * Toggle the <html> class for the lifetime of the enrolled session.
 *
 * Removes the class on unmount so signing out, or an account that is not
 * enrolled, never leaves the redesign applied to a page that did not opt in.
 */
export function useCoachingRoomClass(enabled) {
  useEffect(() => {
    const root = document.documentElement;
    if (!root) return undefined;
    if (!enabled) {
      root.classList.remove(COACHING_ROOM_CLASS);
      return undefined;
    }
    root.classList.add(COACHING_ROOM_CLASS);
    return () => root.classList.remove(COACHING_ROOM_CLASS);
  }, [enabled]);
}

/** Provide the flag to the tree and keep the <html> class in step with it. */
export function CoachingRoomProvider({ user, children }) {
  const enabled = isCoachingRoomEnabled(user);
  useCoachingRoomClass(enabled);
  return createElement(CoachingRoomContext.Provider, { value: enabled }, children);
}

/**
 * Apply the coaching room to a public page.
 *
 * Unconditional by design: there is no account to consult. Renders nothing.
 */
export function CoachingRoomPublic({ children = null }) {
  useCoachingRoomClass(true);
  return createElement(CoachingRoomContext.Provider, { value: true }, children);
}

export default CoachingRoomContext;
