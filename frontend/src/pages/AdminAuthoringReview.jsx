/**
 * Authoring Review — per-item triage of Parth's authoring submissions.
 *
 * Mohit 2026-06-03. Spec: docs/authoring_review_ui_spec.md.
 *
 * One submission per screen. Two columns: original caption | Parth's
 * suggestion. Mini-board oriented by user_color. Auto-gate verdict
 * shown prominently. Hotkeys: a / r / s / e.
 *
 * Approving writes to authored_caption_overrides (the V5 service
 * checks this collection at render time and replaces the templated
 * caption). Rejecting marks the feedback dismissed. Skipping marks
 * it acknowledged (out of the default 'pending' queue but resurfaceable).
 */
import { useEffect, useState, useCallback, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import LichessBoard from "@/components/LichessBoard";
import { API } from "@/App";
import { Check, X, ChevronRight, Edit3, AlertTriangle, Loader2 } from "lucide-react";


const STATUS_FILTERS = [
  { value: "pending", label: "Pending" },
  { value: "acknowledged", label: "Skipped" },
  { value: "valid", label: "Approved" },
  { value: "dismissed", label: "Rejected" },
];


const AdminAuthoringReview = () => {
  const [statusFilter, setStatusFilter] = useState("pending");
  const [queue, setQueue] = useState([]);
  const [total, setTotal] = useState(0);
  const [cursor, setCursor] = useState(0);
  const [loading, setLoading] = useState(true);
  const [actionPending, setActionPending] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState("");
  const navigate = useNavigate();

  const current = queue[cursor];

  const loadQueue = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(
        `${API}/admin/authoring/queue?status=${statusFilter}&skip=0&limit=200`,
        { credentials: "include" },
      );
      if (!res.ok) throw new Error("queue fetch failed");
      const data = await res.json();
      setQueue(data.items || []);
      setTotal(data.total || 0);
      setCursor(0);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { loadQueue(); }, [loadQueue]);

  const advance = () => {
    setEditing(false);
    setEditText("");
    setCursor((c) => Math.min(c + 1, queue.length));
  };

  const doApprove = useCallback(async (caption_override) => {
    if (!current || actionPending) return;
    setActionPending(true);
    try {
      const res = await fetch(
        `${API}/admin/authoring/${current.feedback_id}/approve`,
        {
          method: "POST", credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ caption_override: caption_override || null }),
        },
      );
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        alert(`Approve failed: ${e.detail || res.statusText}`);
        return;
      }
      advance();
    } finally {
      setActionPending(false);
    }
  }, [current, actionPending, queue]);

  const doReject = useCallback(async () => {
    if (!current || actionPending) return;
    // If auto-gate said PASS and reviewer rejects, ask why (one click).
    if (current.auto_gate_verdict === "PASS") {
      const ok = window.confirm(
        "Auto-gate said PASS but you're rejecting. Sure?",
      );
      if (!ok) return;
    }
    setActionPending(true);
    try {
      await fetch(
        `${API}/admin/authoring/${current.feedback_id}/reject`,
        {
          method: "POST", credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ admin_note: null }),
        },
      );
      advance();
    } finally {
      setActionPending(false);
    }
  }, [current, actionPending]);

  const doSkip = useCallback(async () => {
    if (!current || actionPending) return;
    setActionPending(true);
    try {
      await fetch(
        `${API}/admin/authoring/${current.feedback_id}/skip`,
        { method: "POST", credentials: "include" },
      );
      advance();
    } finally {
      setActionPending(false);
    }
  }, [current, actionPending]);

  const startEdit = useCallback(() => {
    if (!current) return;
    setEditText(current.suggested_caption || "");
    setEditing(true);
  }, [current]);

  // Hotkeys: a r s e (matches spec §10 decision #4)
  useEffect(() => {
    if (editing) return; // textarea has focus, let it take keys
    const onKey = (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
      switch (e.key) {
        case "a": e.preventDefault(); doApprove(null); break;
        case "r": e.preventDefault(); doReject(); break;
        case "s": e.preventDefault(); doSkip(); break;
        case "e": e.preventDefault(); startEdit(); break;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [editing, doApprove, doReject, doSkip, startEdit]);

  const orientation = useMemo(() => {
    // Spec §10 #3 — orient by user_color if present, white fallback.
    const c = (current && (current.user_color || (current.diagnostics || {}).user_color)) || "white";
    return c.toLowerCase() === "black" ? "black" : "white";
  }, [current]);

  if (loading) {
    return <div className="p-10 text-center text-muted-foreground">
      <Loader2 className="h-4 w-4 inline animate-spin mr-2" /> Loading queue…
    </div>;
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="mb-6 flex items-baseline justify-between gap-4">
        <div>
          <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold">
            Admin
          </div>
          <h1 className="font-serif text-[26px] text-foreground mt-1">
            Authoring Review
          </h1>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border border-border rounded-md px-2 py-1 text-sm bg-background"
          >
            {STATUS_FILTERS.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
          <span className="text-muted-foreground tabular-nums">
            {Math.min(cursor + 1, queue.length)} / {queue.length} loaded · {total} total
          </span>
        </div>
      </div>

      {/* Empty / done */}
      {queue.length === 0 && (
        <div className="rounded-xl border border-border p-10 text-center text-muted-foreground">
          No submissions in <span className="font-medium">{statusFilter}</span>.
        </div>
      )}
      {queue.length > 0 && cursor >= queue.length && (
        <div className="rounded-xl border border-border p-10 text-center">
          <h2 className="font-serif text-xl mb-2">Queue cleared.</h2>
          <p className="text-muted-foreground mb-4">
            You reviewed {queue.length} items.
          </p>
          <button
            onClick={loadQueue}
            className="px-4 h-9 rounded-md bg-foreground text-background text-sm font-medium"
          >
            Reload queue
          </button>
        </div>
      )}

      {/* Current card */}
      {current && cursor < queue.length && (
        <div className="rounded-xl border border-border p-5 space-y-4">
          {/* Identification + verdict */}
          <div className="flex items-baseline justify-between gap-3 flex-wrap">
            <div className="text-sm">
              <span className="font-mono text-muted-foreground">{current.feedback_id}</span>
              <span className="mx-2 text-muted-foreground/40">·</span>
              <span className="font-mono">{(current.game_id || "?").slice(0, 18)}</span>
              <span className="mx-2 text-muted-foreground/40">·</span>
              <span className="font-mono">m{current.move_number} {current.move_san}</span>
              <span className="ml-2 text-[11px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground tabular-nums">
                [{(current.diagnostics || {}).severity || "?"}] cp={(current.diagnostics || {}).cp_loss ?? "?"}
              </span>
            </div>
            <div>
              {current.auto_gate_verdict === "PASS" ? (
                <span className="text-[11px] px-2 py-1 rounded-md font-semibold uppercase tracking-wider"
                      style={{ background: "#dcfce7", color: "#15803d" }}>
                  Auto-gate: PASS
                </span>
              ) : (
                <span className="text-[11px] px-2 py-1 rounded-md font-semibold uppercase tracking-wider"
                      style={{ background: "#fef3c7", color: "#b45309" }}>
                  Auto-gate: REJECT ({(current.auto_gate_reasons || []).join(", ")})
                </span>
              )}
            </div>
          </div>

          {/* Mini-board + engine truth */}
          <div className="grid grid-cols-[280px_1fr] gap-5">
            <div>
              {current.fen ? (
                <LichessBoard fen={current.fen} orientation={orientation} viewOnly={true} interactive={false} />
              ) : (
                <div className="aspect-square bg-muted/40 rounded-md flex items-center justify-center text-xs text-muted-foreground">
                  <AlertTriangle className="h-4 w-4 mr-1.5" /> No FEN
                </div>
              )}
            </div>

            <div className="space-y-2 text-[13px]">
              <div className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold">
                Engine truth
              </div>
              <div className="font-mono text-[12.5px]">
                <span className="text-muted-foreground">best: </span>{(current.diagnostics || {}).best_move || "—"}
                {(current.diagnostics || {}).concept_id && (
                  <span className="ml-3 text-muted-foreground">gap: <span className="text-foreground">{current.diagnostics.concept_id}</span></span>
                )}
              </div>
              <div className="text-[12.5px] text-muted-foreground">
                eval before: <span className="font-mono">{(current.diagnostics || {}).eval_before ?? "—"}</span>
                <span className="mx-2">·</span>
                eval after: <span className="font-mono">{(current.diagnostics || {}).eval_after ?? "—"}</span>
              </div>
              {current.inaccuracy_reason && current.inaccuracy_reason !== "." && (
                <div className="pt-2 border-t border-border/60 mt-2">
                  <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold">
                    What went wrong (Parth's note)
                  </span>
                  <p className="text-foreground/85 mt-1">{current.inaccuracy_reason}</p>
                </div>
              )}
            </div>
          </div>

          {/* Side-by-side compare */}
          <div className="grid grid-cols-2 gap-5">
            <div>
              <div className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold mb-1.5">
                Original caption
              </div>
              <div className="text-[13px] text-foreground/85 p-3 rounded-md bg-muted/30 leading-snug">
                {current.coaching_text || <span className="text-muted-foreground italic">(none)</span>}
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold mb-1.5">
                Parth's suggestion
              </div>
              {!editing ? (
                <div className="text-[13px] text-foreground/85 p-3 rounded-md bg-amber-50 border border-amber-200 leading-snug">
                  {current.suggested_caption}
                </div>
              ) : (
                <textarea
                  autoFocus
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                  className="w-full h-32 text-[13px] p-3 rounded-md border border-amber-300 bg-amber-50/60 leading-snug resize-none focus:outline-none focus:border-amber-500"
                />
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-2 pt-2">
            {editing ? (
              <>
                <button
                  onClick={() => doApprove(editText)}
                  disabled={actionPending}
                  className="px-4 h-9 rounded-md bg-emerald-600 text-white text-sm font-medium inline-flex items-center gap-1.5 hover:bg-emerald-500"
                >
                  <Check className="h-4 w-4" /> Save edits & approve
                </button>
                <button
                  onClick={() => { setEditing(false); setEditText(""); }}
                  className="px-4 h-9 rounded-md border border-border text-sm hover:bg-muted"
                >
                  Cancel
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => doApprove(null)}
                  disabled={actionPending}
                  className="px-4 h-9 rounded-md bg-emerald-600 text-white text-sm font-medium inline-flex items-center gap-1.5 hover:bg-emerald-500"
                >
                  <Check className="h-4 w-4" /> Approve <kbd className="ml-1 text-[9px] opacity-70">a</kbd>
                </button>
                <button
                  onClick={startEdit}
                  disabled={actionPending}
                  className="px-4 h-9 rounded-md border border-border text-sm inline-flex items-center gap-1.5 hover:bg-muted"
                >
                  <Edit3 className="h-4 w-4" /> Edit <kbd className="ml-1 text-[9px] opacity-70">e</kbd>
                </button>
                <button
                  onClick={doReject}
                  disabled={actionPending}
                  className="px-4 h-9 rounded-md bg-rose-600 text-white text-sm font-medium inline-flex items-center gap-1.5 hover:bg-rose-500"
                >
                  <X className="h-4 w-4" /> Reject <kbd className="ml-1 text-[9px] opacity-70">r</kbd>
                </button>
                <button
                  onClick={doSkip}
                  disabled={actionPending}
                  className="ml-auto px-4 h-9 rounded-md border border-border text-sm inline-flex items-center gap-1.5 hover:bg-muted"
                >
                  Skip <ChevronRight className="h-4 w-4" /> <kbd className="ml-1 text-[9px] opacity-70">s</kbd>
                </button>
              </>
            )}
          </div>
        </div>
      )}

      <p className="text-[11px] text-muted-foreground mt-4 text-center">
        Hotkeys: <kbd>a</kbd> approve · <kbd>e</kbd> edit · <kbd>r</kbd> reject · <kbd>s</kbd> skip
      </p>
    </div>
  );
};

export default AdminAuthoringReview;
