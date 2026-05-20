/**
 * AdminCaptionDrafts — review queue for caption proposals.
 *
 * Authors submit proposed templates via /admin/captions (the audit UI).
 * Those land here as pending drafts. Claude reviews them (chess
 * accuracy, placeholder validity, voice) and writes a review comment.
 * Mohit/Parth read the review and click Approve (writes to JSON) or
 * Reject (drops the draft).
 *
 * Auth: admin-only.
 */
import { useState, useEffect, useMemo } from "react";
import { Link } from "react-router-dom";
import { Chess } from "chess.js";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import LichessBoard from "@/components/LichessBoard";
import { Loader2, CheckCircle2, XCircle, RefreshCw } from "lucide-react";


const sanToArrow = (fen, san, color) => {
  if (!fen || !san) return null;
  try {
    const game = new Chess(fen);
    const move = game.move(san, { sloppy: true });
    if (!move) return null;
    return [move.from, move.to, color];
  } catch {
    return null;
  }
};

const buildArrowsFromContext = (pos) => {
  if (!pos) return [];
  const arrows = [];
  const played = sanToArrow(pos.fen_before, pos.move_san, "red");
  if (played) arrows.push(played);
  const best = sanToArrow(pos.fen_before, pos.best_move_san, "green");
  if (best) arrows.push(best);
  return arrows;
};

const AdminCaptionDrafts = ({ user }) => {
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("pending");

  const fetchDrafts = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/admin/captions/drafts?status=${filter}`, {
        credentials: "include",
      });
      if (!res.ok) {
        if (res.status === 403) setError("Admin access required.");
        else setError(`Failed to load drafts (HTTP ${res.status}).`);
        return;
      }
      const data = await res.json();
      setDrafts(data.drafts || []);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDrafts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  const handleApprove = async (id) => {
    if (!window.confirm("Approve this draft? It will be written to the JSON file.")) return;
    const res = await fetch(`${API}/admin/captions/drafts/${id}/approve`, {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) {
      alert(`Approve failed: ${await res.text()}`);
      return;
    }
    fetchDrafts();
  };

  const handleReject = async (id) => {
    if (!window.confirm("Reject this draft? It will be marked rejected (no JSON change).")) return;
    const res = await fetch(`${API}/admin/captions/drafts/${id}/reject`, {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) {
      alert(`Reject failed: ${await res.text()}`);
      return;
    }
    fetchDrafts();
  };

  return (
    <Layout user={user}>
      <div className="max-w-[1100px] mx-auto px-6 py-8 space-y-6">
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-semibold text-zinc-100">
              Caption Drafts — Review Queue
            </h1>
            <p className="text-sm text-zinc-400 mt-1">
              Proposed templates wait here for review before being written
              to JSON.{" "}
              <Link
                to="/admin/captions"
                className="underline text-blue-400"
              >
                Back to audit
              </Link>
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="px-2 py-1 bg-zinc-800 border border-zinc-700 rounded text-sm text-zinc-200"
            >
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
            </select>
            <Button onClick={fetchDrafts} variant="outline" size="sm">
              <RefreshCw className="w-4 h-4 mr-1" />
              Refresh
            </Button>
          </div>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-12 text-zinc-400">
            <Loader2 className="w-6 h-6 animate-spin" />
          </div>
        )}

        {error && (
          <div className="text-sm text-red-400">{error}</div>
        )}

        {!loading && drafts.length === 0 && (
          <div className="border border-zinc-800 rounded-lg p-8 text-center text-zinc-500">
            No {filter} drafts.
          </div>
        )}

        {drafts.map((d) => (
          <DraftCard
            key={d.draft_id}
            draft={d}
            onApprove={handleApprove}
            onReject={handleReject}
          />
        ))}
      </div>
    </Layout>
  );
};

const DraftCard = ({ draft, onApprove, onReject }) => {
  const pos = draft.position_context || {};
  const pending = draft.status === "pending";
  return (
    <div className="border border-zinc-800 rounded-lg p-5 space-y-4 bg-zinc-900/30">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="text-xs text-zinc-500 font-mono">
            {draft.file} → variants.{draft.variant}
          </div>
          <div className="text-xs text-zinc-400 mt-1">
            Author: {draft.author_email || "unknown"}{" "}
            <span className="text-zinc-600">·</span>{" "}
            Submitted:{" "}
            {draft.created_at?.slice(0, 19).replace("T", " ")}
          </div>
        </div>
        <span
          className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
            draft.status === "pending"
              ? "bg-amber-500/20 text-amber-200 border border-amber-500/40"
              : draft.status === "approved"
              ? "bg-emerald-500/20 text-emerald-200 border border-emerald-500/40"
              : "bg-zinc-500/20 text-zinc-300 border border-zinc-600"
          }`}
        >
          {draft.status.toUpperCase()}
        </span>
      </div>

      {pos.fen_before && (
        <div className="flex gap-4">
          <div className="w-64 h-64 flex-shrink-0">
            <LichessBoard
              fen={pos.fen_before}
              orientation={pos.is_white ? "white" : "black"}
              interactive={false}
              viewOnly={true}
              arrows={buildArrowsFromContext(pos)}
            />
          </div>
          <div className="flex-1 text-xs text-zinc-400 space-y-1">
            <div>
              game {pos.game_id?.slice(0, 8)} · move {pos.move_number}{" "}
              · {pos.move_san}
            </div>
            <div>cp_loss: {pos.cp_loss}</div>
            <div className="flex items-center gap-3 text-[10px] mt-2">
              <span className="flex items-center gap-1 text-red-300">
                <span className="inline-block w-3 h-1 bg-red-500" />
                played: {pos.move_san}
              </span>
              {pos.best_move_san && (
                <span className="flex items-center gap-1 text-emerald-300">
                  <span className="inline-block w-3 h-1 bg-emerald-500" />
                  best: {pos.best_move_san}
                </span>
              )}
            </div>
            <div className="text-zinc-500 mt-2">
              Caption observed: {pos.caption_observed || "(none)"}
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
        <div>
          <div className="text-xs text-zinc-500 mb-1">Current template</div>
          <pre className="font-mono whitespace-pre-wrap p-2 rounded bg-zinc-800/50 border border-zinc-700 text-zinc-300">
            {draft.current_template}
          </pre>
        </div>
        <div>
          <div className="text-xs text-zinc-500 mb-1">Proposed template</div>
          <pre className="font-mono whitespace-pre-wrap p-2 rounded bg-blue-950/30 border border-blue-700 text-blue-200">
            {draft.proposed_template}
          </pre>
        </div>
      </div>

      {draft.claude_review ? (
        <div className="p-3 rounded bg-purple-950/30 border border-purple-700">
          <div className="text-xs text-purple-400 mb-1 font-semibold">
            Claude review
          </div>
          <div className="text-sm text-purple-100 whitespace-pre-wrap">
            {draft.claude_review}
          </div>
        </div>
      ) : pending ? (
        <div className="p-3 rounded bg-zinc-800/50 border border-zinc-700 text-xs text-zinc-400 italic">
          Awaiting Claude review. Ask Claude in chat to review pending drafts.
        </div>
      ) : null}

      {pending && (
        <div className="flex gap-2">
          <Button
            onClick={() => onApprove(draft.draft_id)}
            size="sm"
            className="bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            <CheckCircle2 className="w-4 h-4 mr-1" />
            Approve (writes to JSON)
          </Button>
          <Button
            onClick={() => onReject(draft.draft_id)}
            variant="outline"
            size="sm"
            className="text-red-300 border-red-700 hover:bg-red-950/30"
          >
            <XCircle className="w-4 h-4 mr-1" />
            Reject
          </Button>
        </div>
      )}
    </div>
  );
};

export default AdminCaptionDrafts;
