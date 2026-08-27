/**
 * PERSONAL MOMENTS — landing page for re-engagement email CTAs.
 *
 * URL: /coach/moments/:topic   (topic ∈ moments_topic_registry.TOPICS keys)
 *
 * Why this exists:
 *   Re-engagement emails promise "3 specific moments from your games." If the
 *   link goes anywhere generic (like /lab) the trust the email built dies on
 *   first click. This page DELIVERS the 3 moments — pulled live from THIS
 *   user's recent games via /api/coach/personal-moments/:topic.
 *
 * The page is intentionally minimal — board + what you played + what was
 * better + 1-sentence why. No menu, no upsell. The whole job is making good
 * on the email's promise.
 *
 * See: backend/services/moments_topic_registry.py + docs/email_page_contract.md
 */

import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Chessboard } from "react-chessboard";
import { API } from "@/App";
import { ArrowRight, ChevronLeft } from "lucide-react";

const WINE = "#722F37";

const PersonalMoments = ({ user }) => {
  const { topic } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    fetch(`${API}/coach/personal-moments/${topic}`, { credentials: "include" })
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.text()) || `HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setErr(String(e.message || e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [topic]);

  if (loading) {
    return (
      <div className="experience-page experience-moments-page min-h-screen flex items-center justify-center text-muted-foreground">
        Pulling your moments…
      </div>
    );
  }

  if (err || !data) {
    return (
      <div className="experience-page experience-moments-page min-h-screen flex items-center justify-center">
        <div className="max-w-md text-center space-y-3">
          <h2 className="text-xl font-semibold">We couldn't load this</h2>
          <p className="text-sm text-muted-foreground">{err || "Unknown error"}</p>
          <button
            onClick={() => navigate("/home")}
            className="px-4 py-2 rounded bg-gray-900 text-white text-sm"
          >Back to dashboard</button>
        </div>
      </div>
    );
  }

  const moments = data.moments || [];

  return (
    <div className="experience-page experience-moments-page min-h-screen bg-[#FAF7F2] py-8">
      <div className="max-w-3xl mx-auto px-6">
        {/* Header */}
        <button
          onClick={() => navigate("/home")}
          className="flex items-center text-sm text-muted-foreground hover:text-foreground mb-4"
        >
          <ChevronLeft className="w-4 h-4 mr-1" />
          Dashboard
        </button>
        <h1 className="text-3xl font-semibold" style={{ color: WINE }}>
          {data.label}
        </h1>
        <p className="text-base text-muted-foreground mt-2">{data.subtitle}</p>

        {/* Teaching paragraph */}
        <div className="mt-6 p-5 rounded-lg bg-white border border-amber-100 leading-relaxed">
          <p className="text-[15px] text-gray-800">{data.explainer}</p>
        </div>

        {/* Moments */}
        {moments.length === 0 ? (
          <div className="mt-8 p-6 rounded-lg bg-white border text-center">
            <p className="text-base text-gray-800">
              Good news — there aren't any matching moments from your recent games.
            </p>
            <p className="text-sm text-muted-foreground mt-2">
              That probably means you've avoided this pattern lately. Keep playing.
            </p>
          </div>
        ) : (
          <div className="mt-8 space-y-6">
            {moments.map((m, i) => (
              <MomentCard key={`${m.game_id}-${m.move_number}`} moment={m} index={i} />
            ))}
          </div>
        )}

        {/* CTA */}
        <div className="mt-10 p-6 rounded-lg bg-white border border-amber-100 text-center">
          <p className="text-base text-gray-900 font-medium">
            Want to keep working on this pattern?
          </p>
          <p className="text-sm text-muted-foreground mt-1 mb-4">
            We have puzzles drawn from positions just like these.
          </p>
          <button
            onClick={() => navigate(`/training/pattern/${topic}`)}
            className="px-5 py-2.5 rounded text-white text-sm font-medium inline-flex items-center"
            style={{ background: WINE }}
          >
            Take the {data.label.toLowerCase()} drill
            <ArrowRight className="w-4 h-4 ml-2" />
          </button>
        </div>
      </div>
    </div>
  );
};


const MomentCard = ({ moment, index }) => {
  const fen = moment.fen_before || "";
  // Orientation: derive from the FEN side-to-move (the user is the side about to move)
  const sideToMove = fen.split(" ")[1] === "b" ? "black" : "white";
  return (
    <div className="rounded-lg bg-white border overflow-hidden">
      <div className="p-4 border-b flex items-center justify-between">
        <span className="text-xs uppercase tracking-wide text-amber-700 font-semibold">
          Moment {index + 1}
        </span>
        <span className="text-xs text-muted-foreground">
          Game move {moment.move_number}
        </span>
      </div>
      <div className="grid md:grid-cols-2 gap-5 p-5">
        <div style={{ maxWidth: 360 }}>
          <Chessboard
            position={fen}
            arePiecesDraggable={false}
            boardOrientation={sideToMove}
          />
        </div>
        <div className="space-y-3 text-sm">
          <div>
            <div className="text-xs text-muted-foreground">You played</div>
            <div className="text-lg font-mono font-semibold text-red-700">
              {moment.user_played || "—"}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Engine's best</div>
            <div className="text-lg font-mono font-semibold text-green-700">
              {moment.best_move || "—"}
            </div>
          </div>
          {moment.cp_loss !== undefined && (
            <div>
              <div className="text-xs text-muted-foreground">Cost</div>
              <div className="text-sm">{moment.cp_loss} centipawns dropped</div>
            </div>
          )}
          <div className="pt-2 border-t">
            <p className="text-[14px] leading-snug text-gray-800">{moment.why}</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PersonalMoments;
