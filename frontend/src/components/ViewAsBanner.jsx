/**
 * The bar that says whose eyes you are looking through.
 *
 * It is deliberately loud and deliberately fixed. The failure mode this
 * guards against is not a security one -- the backend already refuses every
 * write -- it is an admin forgetting, reading a page as somebody else, and
 * drawing a conclusion about their own account. So it sits above everything,
 * it names the person, and the way out is one click that is always visible.
 *
 * It renders nothing at all for everyone else, which is almost everyone.
 */
import { useCallback, useEffect, useState } from "react";

const API = process.env.REACT_APP_BACKEND_URL
  ? `${process.env.REACT_APP_BACKEND_URL}/api`
  : "/api";

export default function ViewAsBanner() {
  const [session, setSession] = useState(null);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API}/auth/me`, { credentials: "include" });
        if (!res.ok) return;
        const me = await res.json();
        if (!cancelled) setSession(me?.viewing_as || null);
      } catch (e) {
        // Never let this bar break the page it sits on.
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const exit = useCallback(async () => {
    setLeaving(true);
    try {
      await fetch(`${API}/admin/view-as`, {
        method: "DELETE",
        credentials: "include",
      });
    } catch (e) {
      // Fall through to the reload; the cookie is short-lived regardless.
    }
    // Full reload rather than a state change: every page below this has
    // already fetched the other user's data, and there is no honest way to
    // repaint it piecemeal.
    window.location.reload();
  }, []);

  if (!session) return null;

  const who = session.target_email || session.target_user_id;

  return (
    <div
      role="status"
      style={{
        position: "sticky",
        top: 0,
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        gap: "12px",
        flexWrap: "wrap",
        padding: "10px 16px",
        background: "#7c2d12",
        color: "#fff",
        fontSize: "14px",
        lineHeight: 1.4,
        boxShadow: "0 1px 0 rgba(0,0,0,0.25)",
      }}
    >
      <span aria-hidden="true">👁</span>
      <strong>Viewing as {session.target_name || who}</strong>
      <span style={{ opacity: 0.85 }}>{who} · read-only</span>
      <button
        type="button"
        onClick={exit}
        disabled={leaving}
        style={{
          marginLeft: "auto",
          padding: "5px 14px",
          borderRadius: "6px",
          border: "1px solid rgba(255,255,255,0.55)",
          background: "transparent",
          color: "#fff",
          cursor: leaving ? "default" : "pointer",
          fontSize: "13px",
        }}
      >
        {leaving ? "Exiting…" : "Exit"}
      </button>
    </div>
  );
}
