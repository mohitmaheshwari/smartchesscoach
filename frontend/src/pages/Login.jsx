/**
 * Login / Register page.
 *
 * Email + password sign-in (and sign-up) sharing the session-cookie
 * pattern that Google OAuth already uses. Google sign-in is also
 * available below as a secondary path.
 */

import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { ChevronRight, Loader2 } from "lucide-react";
import { API } from "@/App";

export default function Login() {
  const navigate = useNavigate();
  const [mode, setMode] = useState("signin"); // "signin" | "signup"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const postAuthRedirect = () =>
    window.sessionStorage.getItem("post_auth_redirect") || "/dashboard";

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const url = mode === "signin" ? "/auth/login" : "/auth/register";
      const body = mode === "signin"
        ? { email, password }
        : { email, password, name: name || undefined };

      const res = await fetch(`${API}${url}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data.detail || "Something went wrong. Please try again.");
        return;
      }
      window.location.href = postAuthRedirect();
    } catch (err) {
      setError("Network error. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleGoogle = async () => {
    try {
      const res = await fetch(`${API}/auth/google/login`);
      const data = await res.json();
      if (data.auth_url) window.location.href = data.auth_url;
    } catch {
      setError("Google sign-in failed. Please try again.");
    }
  };

  return (
    <div className="min-h-screen bg-[#06060B] text-gray-100 flex items-center justify-center px-6">
      {/* Ambient glow */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/3 left-1/4 w-[400px] h-[400px] rounded-full blur-[160px] bg-amber-500/[0.06]" />
        <div className="absolute bottom-1/4 right-1/4 w-[400px] h-[400px] rounded-full blur-[160px] bg-amber-600/[0.04]" />
      </div>

      <div className="relative w-full max-w-sm">
        <Link to="/" className="flex items-center gap-2.5 mb-10">
          <img src="/chessguru-logo.svg" alt="ChessGuru" className="w-7 h-7" />
          <span className="text-[15px] font-heading font-bold tracking-tight text-white">
            ChessGuru
          </span>
        </Link>

        <h1 className="text-3xl font-heading font-bold tracking-tight text-white mb-2">
          {mode === "signin" ? "Welcome back" : "Create your account"}
        </h1>
        <p className="text-sm text-gray-400 mb-8">
          {mode === "signin"
            ? "Sign in to continue your training."
            : "Start building your coaching profile."}
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === "signup" && (
            <div>
              <label className="text-xs text-gray-500 mb-1.5 block">Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-white/[0.03] border border-white/10 rounded-lg px-4 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-amber-500/50 transition-colors"
                placeholder="Optional"
                autoComplete="name"
              />
            </div>
          )}

          <div>
            <label className="text-xs text-gray-500 mb-1.5 block">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full bg-white/[0.03] border border-white/10 rounded-lg px-4 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-amber-500/50 transition-colors"
              placeholder="you@example.com"
              autoComplete="email"
              data-testid="login-email"
            />
          </div>

          <div>
            <label className="text-xs text-gray-500 mb-1.5 block">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={mode === "signup" ? 8 : undefined}
              className="w-full bg-white/[0.03] border border-white/10 rounded-lg px-4 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-amber-500/50 transition-colors"
              placeholder={mode === "signup" ? "At least 8 characters" : ""}
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
              data-testid="login-password"
            />
          </div>

          {error && (
            <div className="text-[13px] text-red-400 bg-red-500/[0.08] border border-red-500/20 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            data-testid="login-submit"
            className="w-full px-5 py-3 text-sm font-semibold text-black rounded-lg bg-gradient-to-r from-amber-400 to-amber-500 hover:from-amber-300 hover:to-amber-400 transition-all shadow-lg shadow-amber-500/20 disabled:opacity-60 flex items-center justify-center gap-2"
          >
            {submitting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <>
                {mode === "signin" ? "Sign in" : "Create account"}
                <ChevronRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        <div className="my-6 flex items-center gap-3 text-[11px] text-gray-600">
          <div className="flex-1 h-px bg-white/10" />
          OR
          <div className="flex-1 h-px bg-white/10" />
        </div>

        <button
          onClick={handleGoogle}
          className="w-full px-5 py-2.5 text-sm text-gray-300 border border-white/10 rounded-lg hover:border-white/20 hover:text-white transition-all"
        >
          Continue with Google
        </button>

        <div className="mt-8 text-center text-[13px] text-gray-500">
          {mode === "signin" ? (
            <>
              No account yet?{" "}
              <button
                onClick={() => { setMode("signup"); setError(""); }}
                className="text-amber-400 hover:text-amber-300"
              >
                Create one
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button
                onClick={() => { setMode("signin"); setError(""); }}
                className="text-amber-400 hover:text-amber-300"
              >
                Sign in
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
