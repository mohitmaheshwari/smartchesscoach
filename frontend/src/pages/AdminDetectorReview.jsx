/**
 * AdminDetectorReview - read what a shadow detector would say, and rule on it.
 *
 * Mohit, 2026-09-18: "we are not yet live and you do things like we are live
 * and that's why you keep lot of things silent so user don't see any bad
 * thing, and that's why I assume things are fine."
 *
 * He is right. Every detector lands in shadow by default, which is correct for
 * a launched product and wrong for this one - 47 of 48 registered detectors
 * have been mute long enough that nobody remembers what they would say, and
 * the silence is what made the backlog invisible.
 *
 * So this shows the claims, several at a time, rendered exactly as a player
 * would read them, with the position and the detector's own evidence beside
 * them. Reading fifty in ten minutes is the point; a claim you can read is a
 * claim you can fix.
 *
 * The verdict is Mohit's. Recording one does not promote anything - it
 * accumulates the precision figure a promotion packet needs, and
 * detector_quality stays the only authority over what reaches a player.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import LichessBoard from "@/components/LichessBoard";
import { Chess } from "chess.js";
import { Loader2, RefreshCw, Check, X, HelpCircle, RotateCcw } from "lucide-react";

// Ordered MUTED FIRST. The first version of this list led with
// `simple_hang` and `fork`, both of which were promoted to caption grade
// weeks ago -- 96.9% over 260 reviewed fires for simple_hang on 2026-08-31.
// Reviewing them buys nothing at this bar, and they would have eaten most of
// a session. The live grade comes from detector_quality via /results, so this
// order is a default and the page marks what is actually already done.
// Why a caption is bad, as distinct from whether the CLAIM is true. Each of
// these is a fault Mohit named on a real card on 2026-09-19, which is why
// they are these five and not a generic "was it helpful" scale:
//   "don't tell something the board is already showing"
//   "it's not dxc5, it's about ignorance of opponent plan"
//   "captions should tell principles that you don't forget"
//   "are you sure that position was this? never write something bad or wrong"
const CAPTION_FAULTS = [
  { id: "describes_board", label: "Says what the board already shows" },
  { id: "wrong_lesson", label: "Right facts, wrong lesson" },
  { id: "no_principle", label: "No rule you would remember" },
  { id: "false_claim", label: "A claim in it is untrue" },
  { id: "jargon_or_long", label: "Jargon, or too long to read" },
];

const DETECTORS = [
  // The missed-concept branch, 2026-09-19. These four detectors previously
  // gated on "the move played WAS the engine's move", so across 400 games
  // they produced 1,639 "applied" and 0 "missed" -- they could only ever
  // congratulate. They can now say the concept was missed, and these 215
  // claims have never been judged by anyone. Listed first for that reason.
  {
    id: "missed_development",
    label: "Missed development",
    claims:
      "a piece was still on its starting square, the engine's move was to develop one, and they played something else that lost ground",
  },
  {
    id: "missed_center",
    label: "Missed the centre",
    claims:
      "the engine's move was a central pawn push and they played something else that lost ground",
  },
  {
    id: "missed_castling",
    label: "Missed castling",
    claims:
      "the engine's move was to castle and they played something else that lost ground",
  },
  {
    id: "missed_king_activity",
    label: "Missed king activity",
    claims:
      "an endgame where the engine's move walked the king towards the centre, and they played something else that lost ground",
  },
  {
    id: "discovered_attack",
    label: "Missed discovered attack",
    claims:
      "a move was available that unmasks an attack from a piece behind it and wins material, and they played something else",
  },
  {
    id: "allowed_mate",
    label: "Allowed mate",
    claims: "the move they played allows a forced checkmate against them",
  },
  {
    id: "left_book",
    label: "Left the book",
    claims:
      "they left opening theory here, and the book move was also the engine's best move",
  },
  {
    id: "simple_hang",
    label: "Hung a piece",
    claims:
      "the move left one of their own pieces where the opponent can simply take it",
  },
  {
    id: "fork",
    label: "Missed fork",
    claims:
      "a move was available that attacks two pieces at once and wins material, and they played something else",
  },
];

// Same helpers as /admin/geometry-gaps, deliberately -- Mohit asked for
// "exactly all those things", and two admin review surfaces that step a line
// differently is how a reviewer loses their place.
const sanToArrow = (fen, san, color) => {
  if (!fen || !san) return null;
  try {
    const game = new Chess(fen);
    const move = game.move(san, { sloppy: true });
    return move ? [move.from, move.to, color] : null;
  } catch {
    return null;
  }
};

// Replay from the original FEN every time rather than mutating a board we keep
// around: one illegal SAN then truncates the line instead of corrupting every
// later position.
const replay = (fen, moves, ply) => {
  const base = { fen, arrow: null };
  if (!fen || !moves?.length || ply < 1) return base;
  try {
    const game = new Chess(fen);
    let last = null;
    for (const san of moves.slice(0, ply)) {
      const made = game.move(san, { sloppy: true });
      if (!made) break;
      last = made;
    }
    return { fen: game.fen(), last };
  } catch {
    return base;
  }
};

export default function AdminDetectorReview() {
  const [detector, setDetector] = useState(DETECTORS[0].id);
  const [claims, setClaims] = useState([]);
  // Caption feedback is deliberately NOT part of the verdict. A detector can
  // be dead right and still say it badly, and collapsing the two means the
  // only way to record a bad caption is to rule the DETECTION wrong -- which
  // corrupts the precision figure a promotion rests on.
  const [captionOpen, setCaptionOpen] = useState(false);
  const [captionFaults, setCaptionFaults] = useState([]);
  const [captionRewrite, setCaptionRewrite] = useState("");
  const [captionSent, setCaptionSent] = useState({});
  const [scanInfo, setScanInfo] = useState({});
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [ruled, setRuled] = useState({});
  // Which card of the loaded batch is in front of the reviewer, and -- when
  // they are walking a line -- which line and how far in.
  const [cursor, setCursor] = useState(0);
  const [line, setLine] = useState(null);
  const [ply, setPly] = useState(0);
  // The admin login is shared with a reviewing coach, so the account email
  // cannot tell two reviewers apart. This is not access control -- it labels
  // the evidence so the promotion packet can say who judged what.
  const [reviewer, setReviewer] = useState(() => {
    try {
      return localStorage.getItem("detectorReviewer") || "";
    } catch {
      return "";
    }
  });
  const setReviewerPersisted = (v) => {
    setReviewer(v);
    try {
      localStorage.setItem("detectorReviewer", v);
    } catch {
      /* private window / blocked storage: the field still works this session */
    }
  };

  // Guards against an out-of-order batch. Switching detector fires a second
  // fetch while the first is still in flight, and the SLOWER one used to win:
  // Mohit ruled a discovered_attack card while the page header said
  // allowed_mate (2026-09-19). The verdict was still recorded against the
  // card's own detector, so the data was right and only the label lied -- but
  // a reviewer cannot judge a claim they think belongs to something else.
  const requestSeq = useRef(0);

  const load = useCallback(async () => {
    const seq = ++requestSeq.current;
    setLoading(true);
    setRuled({});
    // Never show the previous detector's cards under the new one's heading.
    setClaims([]);
    // Back to the first card of the new batch. Without this the cursor stays
    // at 20 while a fresh 20-card batch arrives, the "ran off the end" effect
    // fires again immediately, and the page reloads forever.
    setCursor(0);
    setLine(null);
    setPly(0);
    try {
      const res = await fetch(
        `${API}/admin/detector-review/batch?detector=${detector}&limit=20`,
        { credentials: "include" }
      );
      const body = res.ok ? await res.json() : {};
      // A batch that arrives after a newer request was made is stale: drop it.
      if (seq !== requestSeq.current) return;
      // And never trust the response to be for the detector we are showing.
      if (body.detector && body.detector !== detector) return;
      setClaims(body.claims || []);
      setScanInfo({
        scanned: body.scanned_analyses,
        ruled: body.already_ruled,
        split: body.confidence_split,
      });
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }, [detector]);

  const loadResults = useCallback(async () => {
    const res = await fetch(`${API}/admin/detector-review/results`, {
      credentials: "include",
    });
    if (res.ok) setResults(await res.json());
  }, []);

  useEffect(() => {
    load();
    loadResults();
  }, [load, loadResults]);

  const rule = async (claim, verdict) => {
    // Optimistic: the verdict is cheap and re-rulable, and waiting on the
    // round trip is what makes a review queue tedious enough to abandon.
    setRuled((prev) => ({ ...prev, [claim.claim_key]: verdict }));
    await fetch(`${API}/admin/detector-review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        claim_key: claim.claim_key,
        detector: claim.detector,
        verdict,
        claim: claim.claim,
        reviewer_name: reviewer,
      }),
    });
    loadResults();
  };

  // One card at a time. Fifty rulings by mouse is what makes a review queue
  // get abandoned; this is the difference between a 30-minute job and an hour.

  // Writes to /feedback/flag -> move_feedback -> /admin/authoring-queue, the
  // caption pipeline that already exists. A second feedback store for the
  // same thing is how the openings sprawl started.
  const sendCaptionFeedback = async (claim) => {
    const e = claim.evidence || {};
    const faults = CAPTION_FAULTS.filter((f) => captionFaults.includes(f.id))
      .map((f) => f.label)
      .join("; ");
    const note =
      [faults, captionRewrite.trim() ? `wants: ${captionRewrite.trim()}` : ""]
        .filter(Boolean)
        .join(" -- ") || "caption flagged, no detail given";
    await fetch(`${API}/feedback/flag`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        source: "detector_review",
        game_id: claim.game_id,
        move_number: e.move_number,
        fen: e.fen_before || e.review_fen,
        move_san: e.played_san,
        coaching_text: claim.claim,
        user_note: note,
        suggested_caption: captionRewrite.trim() || null,
        // So the authoring queue can filter to one detector's captions.
        component: `detector_review:${claim.detector}`,
        concept_id: claim.detector,
        cp_loss: e.cp_loss,
        best_move: e.best_move,
      }),
    });
    setCaptionSent((prev) => ({ ...prev, [claim.claim_key]: true }));
    setCaptionOpen(false);
    setCaptionFaults([]);
    setCaptionRewrite("");
  };

  const ruleAndAdvance = useCallback(
    (verdict) => {
      const claim = claims[cursor];
      if (!claim) return;
      // Already ruled (a double-click, or a key pressed twice): do not record
      // it again, but DO move on. Leaving the reviewer on a card they have
      // already judged is what makes the page feel broken.
      if (!ruled[claim.claim_key]) rule(claim, verdict);
      setCursor((i) => i + 1);
      setLine(null);
      setPly(0);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [claims, cursor, ruled]
  );

  useEffect(() => {
    const onKey = (ev) => {
      if (ev.target?.tagName === "INPUT" || ev.metaKey || ev.ctrlKey) return;
      const key = ev.key.toLowerCase();
      if (key === "c") {
        ev.preventDefault();
        setCaptionOpen((open) => !open);
        return;
      }
      const verdict =
        key === "t" ? "true" : key === "w" ? "false" : key === "u" ? "unsure" : null;
      if (!verdict) return;
      ev.preventDefault();
      ruleAndAdvance(verdict);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [ruleAndAdvance]);

  // A new card starts with a closed, empty panel -- carrying the previous
  // card's faults over would attach them to the wrong caption.
  useEffect(() => {
    setCaptionOpen(false);
    setCaptionFaults([]);
    setCaptionRewrite("");
  }, [cursor, detector]);

  // Running off the end of a batch should fetch the next one, not present an
  // empty screen that looks like the queue is finished.
  useEffect(() => {
    if (claims.length && cursor >= claims.length && !loading) {
      load();
    }
  }, [cursor, claims.length, loading, load]);

  useEffect(() => {
    setCursor(0);
    setLine(null);
    setPly(0);
  }, [detector]);

  const summary = results?.summary?.[detector];
  const active = DETECTORS.find((d) => d.id === detector);

  return (
    <Layout>
      <div className="max-w-5xl mx-auto py-6 px-4 space-y-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="max-w-2xl">
            <h1 className="text-xl font-heading">Detector review</h1>
            <p className="text-sm mt-1">
              <strong>Your job:</strong> look at each position and say whether
              the sentence under it is <strong>true</strong>. That is the whole
              task.
            </p>
            <p className="text-sm text-muted-foreground mt-2">
              Fifty rulings switches a detector on. It is muted until then — it
              cannot say a word to a player, and nothing you click here changes
              that. Roughly 30 minutes per detector.
            </p>
            <p className="text-xs text-muted-foreground mt-2">
              Keys: <kbd className="px-1 border rounded">T</kbd> true ·{" "}
              <kbd className="px-1 border rounded">W</kbd> wrong ·{" "}
              <kbd className="px-1 border rounded">U</kbd> unsure. Use Unsure
              freely — it is thrown out of the maths, so it costs nothing and
              beats a guess.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <input
              value={reviewer}
              onChange={(ev) => setReviewerPersisted(ev.target.value)}
              placeholder="Reviewing as…"
              className="px-2 py-1.5 text-xs rounded-sm border bg-transparent w-36"
              aria-label="Your name, recorded with each ruling"
            />
            <Button variant="outline" size="sm" onClick={load} disabled={loading}>
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Reload
            </Button>
          </div>
        </div>

        <div className="grid gap-1.5">
          {DETECTORS.map((d) => {
            const isSelected = detector === d.id;
            const st = results?.summary?.[d.id];
            const judged = st?.judged ?? 0;
            const need = st?.caption_bar?.fires ?? 50;
            const pct = Math.min(100, (judged / need) * 100);
            const done = judged >= need;
            return (
              <button
                key={d.id}
                onClick={() => setDetector(d.id)}
                aria-pressed={isSelected}
                className={`text-left px-3 py-2 rounded-sm border transition-colors ${
                  isSelected
                    ? "border-foreground bg-muted/40"
                    : "border-border hover:bg-muted/20"
                }`}
              >
                <div className="flex items-center gap-3 text-xs">
                  <span
                    className={`flex-1 ${isSelected ? "font-semibold" : ""}`}
                  >
                    {d.label}
                  </span>
                  <span className="font-mono text-muted-foreground">
                    {judged} / {need}
                  </span>
                  {st?.precision !== null && st?.precision !== undefined && (
                    <span
                      className={`font-mono w-24 text-right ${
                        st.on_track === false
                          ? "text-amber-600 dark:text-amber-500"
                          : "text-muted-foreground"
                      }`}
                    >
                      {st.precision}%{" "}
                      {st.on_track === false ? "below bar" : ""}
                    </span>
                  )}
                  {(st?.precision === null || st?.precision === undefined) && (
                    <span className="w-24 text-right text-muted-foreground">
                      not started
                    </span>
                  )}
                  <span className="w-28 text-right">
                    {st?.already_promoted
                      ? `already ${st.grade}`
                      : done
                      ? "ready"
                      : `${need - judged} left`}
                  </span>
                </div>
                <div className="h-1 bg-muted rounded-full overflow-hidden mt-1.5">
                  <div
                    className={`h-full transition-all ${
                      st?.already_promoted
                        ? "bg-green-600"
                        : done
                        ? "bg-green-600"
                        : "bg-foreground/60"
                    }`}
                    style={{
                      width: st?.already_promoted ? "100%" : `${pct}%`,
                    }}
                  />
                </div>
              </button>
            );
          })}
        </div>

        {/* Which detector these cards belong to, said once, in words. The
            selected tab alone was too quiet to answer "are the positions
            below related to the detector I picked?" */}
        {active && (
          <div className="border-l-2 border-foreground/40 pl-3 py-1">
            <p className="text-sm">
              Showing what <strong>{active.label}</strong> would say. It claims{" "}
              {active.claims}.
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Every card below is one real move from a real game where this
              detector fired. Switch detector above to review a different one.
            </p>
            {scanInfo.split && (
              <p className="text-xs text-muted-foreground mt-1">
                Least certain first.{" "}
                <strong>{scanInfo.split.uncertain || 0}</strong> of these the
                board cannot settle — those are the ones worth your time. The
                other{" "}
                {(scanInfo.split.certain || 0) + (scanInfo.split.likely || 0)}{" "}
                are board-verified already and are here only so nothing is
                hidden from you.
              </p>
            )}
            {summary?.already_promoted && (
              <p className="text-xs mt-1 text-green-700 dark:text-green-500">
                This one is already <strong>{summary.grade}</strong> grade and
                can speak to players. More rulings here buy nothing at this
                bar — the muted detectors at the top of the list are where the
                time pays.
              </p>
            )}
            {summary?.evidence_note && (
              <p className="text-xs mt-1 text-amber-700 dark:text-amber-500">
                <strong>Grade under review.</strong> {summary.evidence_note}
              </p>
            )}
          </div>
        )}

        {summary && (
          <div className="border rounded-sm p-3 bg-muted/20 space-y-2">
            <div className="flex items-baseline gap-3 flex-wrap text-sm">
              <span>
                <strong>{summary.judged}</strong> of{" "}
                {summary.caption_bar.fires} rulings needed
              </span>
              <span className="text-muted-foreground">
                {summary.true} true · {summary.false} wrong
                {summary.unsure ? ` · ${summary.unsure} unsure` : ""}
              </span>
              {summary.precision !== null && (
                <span
                  className={
                    summary.precision >= summary.caption_bar.precision
                      ? "text-green-600 dark:text-green-500"
                      : "text-amber-600 dark:text-amber-500"
                  }
                >
                  running precision <strong>{summary.precision}%</strong> (needs{" "}
                  {summary.caption_bar.precision}%)
                </span>
              )}
            </div>
            <div className="h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-foreground/70 transition-all"
                style={{
                  width: `${Math.min(
                    100,
                    (summary.judged / summary.caption_bar.fires) * 100
                  )}%`,
                }}
              />
            </div>
          </div>
        )}

        {loading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="w-4 h-4 animate-spin" /> Scanning real games for{" "}
            {active?.label?.toLowerCase()}…
          </div>
        )}

        {!loading && claims.length === 0 && (
          <p className="text-sm text-muted-foreground">
            {summary?.remaining === 0 ? (
              <>
                <strong>{active?.label}</strong> has its 50 rulings at{" "}
                {summary.precision}%. {summary.on_track === false
                  ? "That is below the 95% bar, so the misses are bug reports rather than a promotion."
                  : "That clears the 95% bar — it is ready to be promoted."}{" "}
                Pick another detector above.
              </>
            ) : summary?.judged > 0 ? (
              <>
                {/* The queue ran out of window, not out of work. Saying
                    "no claims left" here read as "you are finished" and
                    stopped Mohit at 36 of 50. */}
                I have searched{" "}
                <strong>{scanInfo.scanned?.toLocaleString() ?? "all"}</strong>{" "}
                analysed games and found no <em>unjudged</em>{" "}
                {active?.label?.toLowerCase()} claims beyond the{" "}
                {summary.judged} you have ruled. This detector fires sparsely —
                it needs {summary.remaining} more rulings and the corpus does
                not currently hold them. Tell me and I will widen the search or
                analyse more games.
              </>
            ) : (
              <>
                No unjudged <strong>{active?.label?.toLowerCase()}</strong>{" "}
                claims left in the scan window. Either you have ruled on them
                all, or this detector fires very sparsely.
              </>
            )}
          </p>
        )}

        {claims.length > 0 && cursor < claims.length && (
          <div className="flex items-baseline justify-between text-xs text-muted-foreground">
            <span>
              {summary
                ? `${summary.judged} ruled · ${summary.remaining} to go before ${active?.label ?? "this detector"} can speak`
                : `${active?.label ?? "This detector"} — nothing ruled yet`}
            </span>
            <span className="font-mono">
              claim {cursor + 1} of {claims.length} loaded
            </span>
          </div>
        )}

        {claims.slice(cursor, cursor + 1).map((c) => {
          const verdict = ruled[c.claim_key];
          const e = c.evidence || {};
          const lineFen = e.line_fen || e.fen_before || e.review_fen;
          const movesFor = (which) =>
            which === "played"
              ? [e.played_san, ...(e.pv_after_played || [])].filter(Boolean)
              : [e.best_move || e.book_move, ...(e.pv_after_best || [])].filter(
                  Boolean
                );
          const stepped = replay(lineFen, movesFor(line), ply);
          // No line selected: show the position the claim is ABOUT. Stepping a
          // line takes over and shows that instead.
          const view = line
            ? stepped
            : { fen: e.review_fen || e.fen_after || e.fen_before };
          const arrows = line
            ? stepped.last
              ? [[stepped.last.from, stepped.last.to,
                  line === "played" ? "red" : "green"]]
              : []
            : [
                sanToArrow(lineFen, e.played_san, "red"),
                sanToArrow(lineFen, e.best_move || e.book_move, "green"),
                // The line the move OPENS — the thing the caption is actually
                // about. Without it the board showed two moves and never the
                // geometry they create.
                ...(e.extra_arrows || []),
              ].filter(Boolean);

          const renderLine = (which, label, colorClass) => {
            const moves = movesFor(which);
            if (!moves.length) return null;
            const startNumber = e.move_number || 1;
            const blackToMove = e.side_to_move === "black";
            return (
              <div className="rounded-sm border p-2">
                <p className={`text-[10px] font-semibold uppercase tracking-wide ${colorClass}`}>
                  {label}
                </p>
                <div className="mt-1 flex flex-wrap items-center gap-0.5">
                  {moves.map((san, i) => {
                    const whiteMove = blackToMove ? i % 2 === 1 : i % 2 === 0;
                    const number =
                      startNumber + Math.floor((blackToMove ? i + 1 : i) / 2);
                    const isActive = line === which && ply === i + 1;
                    return (
                      <span key={`${which}-${i}-${san}`} className="flex items-center">
                        {whiteMove ? (
                          <span className="mr-0.5 text-[10px] text-muted-foreground">
                            {number}.
                          </span>
                        ) : i === 0 ? (
                          <span className="mr-0.5 text-[10px] text-muted-foreground">
                            {number}...
                          </span>
                        ) : null}
                        <button
                          type="button"
                          onClick={() => {
                            setLine(which);
                            setPly(i + 1);
                          }}
                          className={`rounded px-1 py-0.5 font-mono text-xs hover:bg-muted ${
                            isActive ? "bg-foreground text-background" : ""
                          }`}
                        >
                          {san}
                        </button>
                      </span>
                    );
                  })}
                </div>
              </div>
            );
          };
          return (
            <div
              key={c.claim_key}
              className="border rounded-sm p-4 grid gap-4 md:grid-cols-[280px_1fr]"
            >
              <div className="space-y-1.5">
                {/* view-only: a reading surface, not a play surface. An
                    accidental drag would edit the position under review. */}
                <LichessBoard
                  fen={view.fen}
                  orientation={e.side_to_move === "black" ? "black" : "white"}
                  arrows={arrows}
                  circles={
                    line ? [] : (e.highlight || []).map((sq) => [sq, "red"])
                  }
                  viewOnly={true}
                  interactive={false}
                />
                {line ? (
                  <button
                    type="button"
                    onClick={() => {
                      setLine(null);
                      setPly(0);
                    }}
                    className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:underline"
                  >
                    <RotateCcw className="h-3 w-3" /> Back to the position
                  </button>
                ) : (
                  <p className="text-[11px] text-muted-foreground text-center">
                    {e.side_to_move === "black" ? "Black" : "White"} to move ·{" "}
                    <span className="text-red-600">red</span> = played ·{" "}
                    <span className="text-green-600">green</span> = claimed
                    better
                    {e.extra_arrows_is ? (
                      <>
                        {" · "}
                        <span className="text-amber-600">yellow</span> ={" "}
                        {e.extra_arrows_is}
                      </>
                    ) : null}
                    {e.highlight_is ? ` · circle = ${e.highlight_is}` : ""}
                  </p>
                )}
              </div>

              <div className="space-y-3 min-w-0">
                <div className="flex items-start gap-2">
                  <p className="text-[15px] leading-snug text-foreground flex-1">
                    {c.claim}
                  </p>
                  {e.confidence && e.confidence !== "uncertain" && (
                    <span className="shrink-0 text-[10px] px-1.5 py-0.5 rounded-sm border text-muted-foreground">
                      board says {e.confidence}
                    </span>
                  )}
                  {e.confidence === "uncertain" && (
                    <span className="shrink-0 text-[10px] px-1.5 py-0.5 rounded-sm border border-amber-500 text-amber-700 dark:text-amber-500">
                      needs your call
                    </span>
                  )}
                </div>

                {/* Plain language, not the raw keys. The first build printed
                    `quality_id tactic:discovered_attack_with_stored_payoff ·
                    detector_facts [object Object]` and the FEN twice, which is
                    the schema showing through the card. */}
                <dl className="text-[13px] space-y-0.5">
                  {e.played_san && (
                    <div className="flex gap-2">
                      <dt className="text-muted-foreground w-28 shrink-0">
                        They played
                      </dt>
                      <dd className="font-medium">{e.played_san}</dd>
                    </div>
                  )}
                  {e.best_move && (
                    <div className="flex gap-2">
                      <dt className="text-muted-foreground w-28 shrink-0">
                        Claimed better
                      </dt>
                      <dd className="font-medium">{e.best_move}</dd>
                    </div>
                  )}
                  {e.book_move && (
                    <div className="flex gap-2">
                      <dt className="text-muted-foreground w-28 shrink-0">
                        Book move
                      </dt>
                      <dd className="font-medium">{e.book_move}</dd>
                    </div>
                  )}
                  {e.hung_piece && (
                    <div className="flex gap-2">
                      <dt className="text-muted-foreground w-28 shrink-0">
                        Said to hang
                      </dt>
                      <dd className="font-medium">
                        {e.hung_piece} on {e.hung_square}
                        {e.defender_moved_away ? " (defender left)" : ""}
                      </dd>
                    </div>
                  )}
                  {typeof e.cp_loss === "number" && (
                    <div className="flex gap-2">
                      {/* Deliberately NOT rendered as pawns — centipawn loss
                          is not material. See the pre-commit caption guard. */}
                      <dt className="text-muted-foreground w-28 shrink-0">
                        Engine cost
                      </dt>
                      <dd className="font-medium">{e.cp_loss} cp</dd>
                    </div>
                  )}
                  <div className="flex gap-2">
                    <dt className="text-muted-foreground w-28 shrink-0">
                      Game
                    </dt>
                    <dd className="text-muted-foreground">
                      {c.game?.white && c.game?.black ? (
                        <>
                          <span
                            className={
                              c.game.user_color === "white"
                                ? "font-medium text-foreground"
                                : ""
                            }
                          >
                            {c.game.white}
                          </span>{" "}
                          vs{" "}
                          <span
                            className={
                              c.game.user_color === "black"
                                ? "font-medium text-foreground"
                                : ""
                            }
                          >
                            {c.game.black}
                          </span>
                          {c.game.result ? ` · ${c.game.result}` : ""}
                          {c.game.platform ? ` · ${c.game.platform}` : ""}
                          {" · move "}
                          {e.move_number}
                        </>
                      ) : (
                        <>move {e.move_number} of {c.game_id}</>
                      )}
                    </dd>
                  </div>
                  {/* The card says which detector it belongs to, not just the
                      page heading. Mohit ruled a discovered_attack claim
                      believing it was allowed_mate (2026-09-19); the stale
                      batch that caused it is fixed, but a reviewer should
                      never have to trust the header to know what they are
                      judging. */}
                  <div>
                    <dt className="text-muted-foreground">detector</dt>
                    <dd className="font-mono text-xs">{c.detector}</dd>
                  </div>
                </dl>

                {/* Click any move to walk the board to it -- the same
                    interaction as /admin/geometry-gaps. */}
                <div className="space-y-1.5">
                  {renderLine(
                    "played",
                    "What happened after the move",
                    "text-red-600"
                  )}
                  {renderLine(
                    "best",
                    "What the engine wanted",
                    "text-green-600"
                  )}
                </div>

                <div className="flex items-center gap-2 pt-1">
                  <Button
                    size="sm"
                    variant={verdict === "true" ? "default" : "outline"}
                    onClick={() => ruleAndAdvance("true")}
                  >
                    <Check className="w-3.5 h-3.5 mr-1" /> True <span className="opacity-50 ml-1">T</span>
                  </Button>
                  <Button
                    size="sm"
                    variant={verdict === "false" ? "destructive" : "outline"}
                    onClick={() => ruleAndAdvance("false")}
                  >
                    <X className="w-3.5 h-3.5 mr-1" /> Wrong <span className="opacity-50 ml-1">W</span>
                  </Button>
                  <Button
                    size="sm"
                    variant={verdict === "unsure" ? "secondary" : "outline"}
                    onClick={() => ruleAndAdvance("unsure")}
                  >
                    <HelpCircle className="w-3.5 h-3.5 mr-1" /> Unsure <span className="opacity-50 ml-1">U</span>
                  </Button>
                  <Button
                    size="sm"
                    variant={captionSent[c.claim_key] ? "secondary" : "ghost"}
                    onClick={() => setCaptionOpen((open) => !open)}
                    title="The claim can be true and the caption still bad"
                  >
                    {captionSent[c.claim_key] ? "Caption noted" : "Caption…"}
                    <span className="opacity-50 ml-1">C</span>
                  </Button>
                  <details className="ml-auto">
                    <summary className="text-[11px] text-muted-foreground cursor-pointer">
                      raw
                    </summary>
                    <pre className="text-[10px] font-mono whitespace-pre-wrap break-all mt-1 max-w-full">
                      {JSON.stringify(e, null, 1)}
                    </pre>
                  </details>
                </div>

                {/* Separate from the verdict on purpose -- see captionOpen. */}
                {captionOpen && (
                  <div className="mt-2 rounded-sm border p-3 space-y-2">
                    <div className="text-[11px] text-muted-foreground">
                      What is wrong with the words? Your verdict above is
                      untouched — a true claim can still read badly.
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {CAPTION_FAULTS.map((f) => {
                        const on = captionFaults.includes(f.id);
                        return (
                          <Button
                            key={f.id}
                            size="sm"
                            variant={on ? "default" : "outline"}
                            className="h-7 text-[11px]"
                            onClick={() =>
                              setCaptionFaults((prev) =>
                                on
                                  ? prev.filter((x) => x !== f.id)
                                  : [...prev, f.id]
                              )
                            }
                          >
                            {f.label}
                          </Button>
                        );
                      })}
                    </div>
                    <input
                      className="w-full rounded-sm border px-2 py-1.5 text-xs bg-transparent"
                      placeholder="What should it have said? (optional — becomes a candidate template)"
                      value={captionRewrite}
                      onChange={(ev) => setCaptionRewrite(ev.target.value)}
                    />
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        disabled={!captionFaults.length && !captionRewrite.trim()}
                        onClick={() => sendCaptionFeedback(c)}
                      >
                        Send to the authoring queue
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setCaptionOpen(false)}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {results?.wrong_claims?.length > 0 && (
          <div className="border rounded-sm p-4">
            <h2 className="text-sm font-medium mb-2">
              Ruled wrong — these are the bug reports
            </h2>
            {results.wrong_claims.slice(0, 20).map((w) => (
              <p key={w.claim_key} className="text-xs text-muted-foreground mb-1">
                <span className="font-mono opacity-60">{w.detector}</span>{" "}
                {w.claim}
              </p>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
}
