/**
 * Reading the guard's refusal.
 *
 * While a player is mid-game on Lichess, `live_play_guard.py` refuses every
 * API call outside the ten paths playing needs. That is deliberate, and it is
 * what keeps a real account off Lichess's engine-cheating list. What it left
 * behind is that the rest of the app then looks broken: Layout's coach-pulse
 * poll asks three endpoints every minute, each comes back 403, every one is
 * swallowed by `if (res.ok)`, and the player is told nothing.
 *
 * This turns one of those refusals into something sayable. It is a plain
 * function, not an interceptor: an earlier version wrapped the global `fetch`
 * so that any call anywhere would be caught, and that broke identity for
 * everything else holding a reference to fetch (LayoutNotificationEffects
 * caught it immediately). The poll that was already being refused is a better
 * place to notice than every call in the app.
 *
 * Nothing here may ever carry coaching. The whole reason the guard exists is
 * that no evaluation reaches a player mid-game, so this passes on the server's
 * own sentence and a link, and nothing else.
 */

const DEFAULT_OPEN = "/play-with-coach";

/**
 * Is this response the guard refusing us? Returns the notice, or null.
 *
 * Takes a Response and only clones and parses it on a 403, so the normal path
 * costs one integer comparison.
 */
export async function readRefusal(response) {
  if (!response || response.status !== 403) return null;
  let body = null;
  try {
    body = await response.clone().json();
  } catch (_) {
    return null; // a 403 that is not JSON is not ours
  }
  if (!body || body.live_lichess_game !== true) return null;
  return {
    message:
      typeof body.detail === "string"
        ? body.detail
        : "Your game is live, so the coach is quiet.",
    open: typeof body.open === "string" ? body.open : DEFAULT_OPEN,
    label:
      typeof body.open_label === "string" ? body.open_label : "Back to your game",
  };
}
