/**
 * Admin → Waitlist.
 *
 * Everyone who asked for an invite, newest first, with one button per row.
 * Inviting sets the waitlist row to "invited", and that row IS the allowlist
 * signup_gate checks — so the person simply signs in with Google and their
 * account is created on first login. No password is ever issued.
 *
 * See docs/invite_only_signup_scope.md.
 */

import { useCallback, useEffect, useState } from "react";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Loader2, RefreshCw, Check, Undo2 } from "lucide-react";

export default function AdminWaitlist() {
  const [rows, setRows] = useState([]);
  const [counts, setCounts] = useState({ pending: 0, invited: 0 });
  const [signupsOpen, setSignupsOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const r = await fetch(`${API}/admin/waitlist`, { credentials: "include" });
      if (!r.ok) throw new Error(`Could not load the waitlist (${r.status})`);
      const d = await r.json();
      setRows(d.rows || []);
      setCounts(d.counts || { pending: 0, invited: 0 });
      setSignupsOpen(d.signups_open === true);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const decide = async (email, action) => {
    setBusy(email);
    setError("");
    try {
      const r = await fetch(`${API}/admin/waitlist/${action}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `Could not ${action} ${email}`);
      }
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  };

  return (
    <Layout>
      <div className="mx-auto max-w-4xl px-5 py-10">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">Waitlist</h1>
            <p className="mt-1.5 text-sm text-gray-500">
              {counts.pending} waiting · {counts.invited} invited
              {signupsOpen && " · signups are OPEN to everyone right now"}
            </p>
          </div>
          <button
            type="button"
            onClick={load}
            className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm"
            data-testid="waitlist-refresh"
          >
            <RefreshCw className="h-4 w-4" /> Refresh
          </button>
        </div>

        {signupsOpen && (
          <p className="mt-4 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-900">
            SIGNUPS_OPEN is true, so anyone can create an account and inviting is
            not required. Unset it to go back to invite-only.
          </p>
        )}
        {error && (
          <p className="mt-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700" data-testid="waitlist-error">
            {error}
          </p>
        )}

        {loading ? (
          <div className="mt-10 flex items-center gap-2 text-gray-500">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading…
          </div>
        ) : rows.length === 0 ? (
          <p className="mt-10 text-gray-500" data-testid="waitlist-empty">
            Nobody has asked for an invite yet.
          </p>
        ) : (
          <div className="mt-6 divide-y rounded-xl border" data-testid="waitlist-rows">
            {rows.map((row) => (
              <div key={row.email} className="flex items-start justify-between gap-4 p-4">
                <div className="min-w-0">
                  <p className="font-medium">
                    {row.name || "—"}{" "}
                    <span className="font-normal text-gray-500">{row.email}</span>
                  </p>
                  {row.note && <p className="mt-1 text-sm text-gray-600">{row.note}</p>}
                  <p className="mt-1 text-xs text-gray-400">
                    {String(row.created_at || "").slice(0, 16).replace("T", " ")}
                    {row.source ? ` · ${row.source}` : ""}
                    {row.status === "invited" && row.invited_at
                      ? ` · invited ${String(row.invited_at).slice(0, 10)}`
                      : ""}
                  </p>
                </div>
                {row.status === "invited" ? (
                  <button
                    type="button"
                    disabled={busy === row.email}
                    onClick={() => decide(row.email, "uninvite")}
                    className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border px-3 py-2 text-sm text-gray-600 disabled:opacity-50"
                    data-testid={`uninvite-${row.email}`}
                  >
                    <Undo2 className="h-4 w-4" /> Invited
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={busy === row.email}
                    onClick={() => decide(row.email, "invite")}
                    className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
                    data-testid={`invite-${row.email}`}
                  >
                    {busy === row.email ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                    Invite
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
}
