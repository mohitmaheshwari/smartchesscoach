/**
 * Pricing page — Free vs Pro tiers + Razorpay checkout.
 *
 * Flow:
 *   1. User clicks "Subscribe to Pro"
 *   2. We POST /api/billing/create-order to mint a Razorpay order
 *   3. Open Razorpay's Checkout.js modal with the returned key + order
 *   4. On success, post back to /api/billing/verify-payment which
 *      validates the HMAC signature and flips the user's plan to Pro
 *
 * Razorpay's Checkout.js script is loaded dynamically the first time
 * the page mounts so unauthenticated visitors don't pay the load cost.
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, ChevronRight, Loader2 } from "lucide-react";
import { API } from "@/App";

const RZP_SCRIPT_URL = "https://checkout.razorpay.com/v1/checkout.js";

function loadRazorpay() {
  return new Promise((resolve) => {
    if (typeof window !== "undefined" && window.Razorpay) {
      resolve(true);
      return;
    }
    const script = document.createElement("script");
    script.src = RZP_SCRIPT_URL;
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}

const FREE_FEATURES = [
  "5 game analyses per month",
  "Basic coaching feedback",
  "Pattern training",
  "Game import from Chess.com & Lichess",
];

const PRO_FEATURES = [
  "25 game analyses per month",
  "Real-time coaching during games",
  "LLM commentary & deep narratives",
  "Priority Stockfish analysis queue",
  "Auto-sync new games",
  "Everything in Free",
];

export default function Pricing() {
  const navigate = useNavigate();
  const [config, setConfig] = useState(null);
  const [user, setUser] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [cfgRes, meRes] = await Promise.all([
          fetch(`${API}/billing/config`, { credentials: "include" }),
          fetch(`${API}/auth/me`, { credentials: "include" }),
        ]);
        const cfg = await cfgRes.json().catch(() => null);
        const me = meRes.ok ? await meRes.json().catch(() => null) : null;
        if (!cancelled) {
          setConfig(cfg);
          setUser(me);
        }
      } catch {
        // Non-fatal — page still renders, the Subscribe button will
        // just bounce the user to /login.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const formatINR = (paise) => {
    if (!paise) return "—";
    return `₹${(paise / 100).toFixed(0)}`;
  };

  const handleSubscribe = async () => {
    setError("");

    if (!user) {
      window.sessionStorage.setItem("post_auth_redirect", "/pricing");
      navigate("/login");
      return;
    }
    if (!config?.enabled) {
      setError("Payments aren't configured yet. Please try again shortly.");
      return;
    }

    setSubmitting(true);
    try {
      const ok = await loadRazorpay();
      if (!ok) {
        setError("Could not load the payment dialog. Check your network.");
        return;
      }

      // 1. Create order
      const orderRes = await fetch(`${API}/billing/create-order`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan: "pro_monthly" }),
      });
      const order = await orderRes.json();
      if (!orderRes.ok) {
        setError(order.detail || "Could not start checkout.");
        return;
      }

      // 2. Open Razorpay Checkout
      const rzp = new window.Razorpay({
        key: order.key_id,
        order_id: order.order_id,
        amount: order.amount,
        currency: order.currency,
        name: "ChessGuru",
        description: order.plan_name,
        prefill: {
          name: user.name || "",
          email: user.email || "",
        },
        theme: { color: "#F59E0B" },
        handler: async (rzpResponse) => {
          // 3. Verify on the server
          try {
            const verifyRes = await fetch(`${API}/billing/verify-payment`, {
              method: "POST",
              credentials: "include",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                razorpay_order_id: rzpResponse.razorpay_order_id,
                razorpay_payment_id: rzpResponse.razorpay_payment_id,
                razorpay_signature: rzpResponse.razorpay_signature,
              }),
            });
            const data = await verifyRes.json();
            if (!verifyRes.ok) {
              setError(data.detail || "Payment verification failed.");
              return;
            }
            setSuccess(true);
            setTimeout(() => navigate("/home"), 2500);
          } catch {
            setError("Payment verification failed. Please contact support.");
          }
        },
        modal: {
          ondismiss: () => {
            setSubmitting(false);
          },
        },
      });
      rzp.open();
    } catch (e) {
      setError("Something went wrong starting checkout.");
    } finally {
      // submitting stays true while Razorpay modal is open;
      // ondismiss + handler reset it.
    }
  };

  const isPro = user?.plan === "pro";

  return (
    <div className="min-h-screen bg-[#06060B] text-gray-100">
      {/* Ambient glow */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] rounded-full blur-[180px] bg-amber-500/[0.06]" />
        <div className="absolute bottom-1/4 right-1/4 w-[400px] h-[400px] rounded-full blur-[160px] bg-amber-600/[0.04]" />
      </div>

      <div className="relative max-w-5xl mx-auto px-6 py-16 md:py-24">
        <div className="text-center mb-14">
          <p className="text-[10.5px] uppercase tracking-[0.22em] text-amber-400/70 font-semibold mb-4">
            Pricing
          </p>
          <h1 className="text-4xl md:text-5xl font-heading font-bold tracking-tight text-white mb-4">
            Train smarter, not just harder.
          </h1>
          <p className="text-base text-gray-400 max-w-xl mx-auto">
            Free is enough to feel the coach. Pro is for players who want
            the full closed loop — every game watched, every pattern
            tracked.
          </p>
          {config?.test_mode && (
            <div className="inline-block mt-6 px-3 py-1.5 rounded-md bg-amber-500/[0.08] border border-amber-500/20 text-amber-300 text-[12px]">
              Test mode — use card 4111 1111 1111 1111 with any future
              expiry and any CVV. No real money moves.
            </div>
          )}
        </div>

        <div className="grid md:grid-cols-2 gap-5 max-w-3xl mx-auto">
          {/* Free */}
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-7">
            <div className="text-xs uppercase tracking-wider text-gray-500 mb-2">Free</div>
            <div className="flex items-baseline gap-1 mb-1">
              <span className="text-4xl font-heading font-bold text-white">₹0</span>
              <span className="text-sm text-gray-500">/month</span>
            </div>
            <p className="text-sm text-gray-400 mb-6">
              Get a feel for the coach. No credit card.
            </p>
            <ul className="space-y-2.5 mb-8">
              {FREE_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-2.5 text-[13.5px] text-gray-300">
                  <Check className="h-4 w-4 text-emerald-500/80 mt-0.5 flex-shrink-0" strokeWidth={2.4} />
                  <span>{f}</span>
                </li>
              ))}
            </ul>
            <button
              onClick={() => navigate(user ? "/home" : "/login")}
              className="w-full px-5 py-2.5 text-sm text-gray-300 border border-white/10 rounded-lg hover:border-white/20 hover:text-white transition-all"
            >
              {user ? "Go to your dashboard" : "Get started"}
            </button>
          </div>

          {/* Pro */}
          <div className="rounded-2xl border border-amber-500/30 bg-gradient-to-b from-amber-500/[0.04] to-transparent p-7 relative">
            <div className="absolute top-4 right-4 px-2 py-0.5 rounded-md bg-amber-500/15 border border-amber-500/30 text-amber-300 text-[10px] uppercase tracking-wider font-semibold">
              Recommended
            </div>
            <div className="text-xs uppercase tracking-wider text-amber-400/70 mb-2">Pro</div>
            <div className="flex items-baseline gap-1 mb-1">
              <span className="text-4xl font-heading font-bold text-white">
                {formatINR(config?.amount)}
              </span>
              <span className="text-sm text-gray-500">/month</span>
            </div>
            <p className="text-sm text-gray-400 mb-6">
              The full closed loop. Cancel any time.
            </p>
            <ul className="space-y-2.5 mb-8">
              {PRO_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-2.5 text-[13.5px] text-gray-200">
                  <Check className="h-4 w-4 text-amber-400 mt-0.5 flex-shrink-0" strokeWidth={2.4} />
                  <span>{f}</span>
                </li>
              ))}
            </ul>

            {success ? (
              <div className="text-center text-emerald-400 text-sm py-3">
                ✓ Payment received. Redirecting…
              </div>
            ) : isPro ? (
              <button
                disabled
                className="w-full px-5 py-3 text-sm font-semibold text-emerald-400 bg-emerald-500/[0.08] border border-emerald-500/30 rounded-lg cursor-default"
              >
                You're already Pro
              </button>
            ) : (
              <button
                onClick={handleSubscribe}
                disabled={submitting || !config}
                data-testid="subscribe-button"
                className="w-full px-5 py-3 text-sm font-semibold text-black rounded-lg bg-gradient-to-r from-amber-400 to-amber-500 hover:from-amber-300 hover:to-amber-400 transition-all shadow-lg shadow-amber-500/20 disabled:opacity-60 flex items-center justify-center gap-2"
              >
                {submitting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    Subscribe to Pro
                    <ChevronRight className="w-4 h-4" />
                  </>
                )}
              </button>
            )}

            {error && (
              <div className="mt-3 text-[12.5px] text-red-400 bg-red-500/[0.08] border border-red-500/20 rounded-lg px-3 py-2">
                {error}
              </div>
            )}
          </div>
        </div>

        <p className="text-center text-xs text-gray-600 mt-10">
          Payments processed securely by Razorpay. We never see or store
          your card details.
        </p>
      </div>
    </div>
  );
}
