/**
 * Choose a new password, from the link in the reset email.
 * The token is checked on the server and works once, for one hour.
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import { ChevronRight, Loader2 } from "lucide-react";
import { API } from "@/App";

export default function ResetPassword() {
  // "code", not "token": App.js strips any ?token= from every URL, so a reset
  // link named that way lost its token on the first render. Read once on open.
  const [token] = useState(() => new URLSearchParams(window.location.search).get("code") || "");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(token ? "" : "This link has expired. Ask for a new one.");
  const [done, setDone] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data.detail || "Something went wrong. Please try again.");
        return;
      }
      setDone(true);
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="experience-page experience-login-page min-h-screen bg-[#06060B] text-gray-100 flex items-center justify-center px-6">
      <div className="experience-auth-panel relative w-full max-w-sm">
        <Link to="/" className="flex items-center gap-2.5 mb-10">
          <img src="/chessguru-logo.svg" alt="ChessGuru" className="w-7 h-7" />
          <span className="text-[15px] font-heading font-bold tracking-tight text-white">ChessGuru</span>
        </Link>
        <h1 className="text-3xl font-heading font-bold tracking-tight text-white mb-2">
          {done ? "Password changed" : "Choose a new password"}
        </h1>
        {done ? (
          <>
            <p className="text-sm text-gray-400 mb-8">You can sign in with it now.</p>
            <Link to="/login" data-testid="reset-signin" className="text-sm text-amber-400 hover:text-amber-300">
              Go to sign in
            </Link>
          </>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4 mt-8">
            <div>
              <label htmlFor="new-password" className="text-xs text-gray-500 mb-1.5 block">New password</label>
              <input
                id="new-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
                placeholder="At least 8 characters"
                data-testid="reset-password"
                className="w-full bg-white/[0.03] border border-white/10 rounded-lg px-4 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-amber-500/50 transition-colors"
              />
            </div>
            {error && (
              <div className="text-[13px] text-red-400 bg-red-500/[0.08] border border-red-500/20 rounded-lg px-3 py-2">
                {error}{" "}
                <Link to="/login" className="underline">Back to sign in</Link>
              </div>
            )}
            <button
              type="submit"
              disabled={submitting || !token}
              data-testid="reset-submit"
              className="w-full px-5 py-3 text-sm font-semibold text-black rounded-lg bg-gradient-to-r from-amber-400 to-amber-500 hover:from-amber-300 hover:to-amber-400 transition-all shadow-lg shadow-amber-500/20 disabled:opacity-60 flex items-center justify-center gap-2"
            >
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Save new password<ChevronRight className="w-4 h-4" /></>}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
