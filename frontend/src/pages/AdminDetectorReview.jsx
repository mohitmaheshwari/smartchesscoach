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
import { useCallback, useEffect, useState } from "react";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import LichessBoard from "@/components/LichessBoard";
import { Loader2, RefreshCw, Check, X, HelpCircle } from "lucide-react";

// Ordered by how close each is to the caption bar, so a session that runs
// out of time has spent it on the detectors most likely to promote.
// `simple_hang` already documents 96.9% on 260 fires; fork and discovered
// attack measured 99.2% and 100% on GEOMETRY, which the threshold lock
// explicitly says is not enough on its own -- these rulings are the evidence
// it does accept.
// `claims` is what this detector asserts, in one sentence. It is shown above
// the cards so a reviewer -- including a chess coach who has never seen this
// product -- knows what question every card below is answering.
const DETECTORS = [
  {
    id: "simple_hang",
    label: "Hung a piece",
    grade: "shadow",
    claims:
      "the move left one of their own pieces where the opponent can simply take it",
  },
  {
    id: "fork",
    label: "Missed fork",
    grade: "shadow",
    claims:
      "a move was available that attacks two pieces at once and wins material, and they played something else",
  },
  {
    id: "discovered_attack",
    label: "Missed discovered attack",
    grade: "shadow",
    claims:
      "a move was available that unmasks an attack from a piece behind it and wins material, and they played something else",
  },
  {
    id: "left_book",
    label: "Left the book",
    grade: "shadow",
    claims:
      "they left opening theory here, and the book move was also the engine's best move",
  },
  {
    id: "allowed_mate",
    label: "Allowed mate",
    grade: "shadow",
    claims: "the move they played allows a forced checkmate against them",
  },
];

export default function AdminDetectorReview() {
  const [detector, setDetector] = useState(DETECTORS[0].id);
  const [claims, setClaims] = useState([]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [ruled, setRuled] = useState({});
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

  const load = useCallback(async () => {
    setLoading(true);
    setRuled({});
    try {
      const res = await fetch(
        `${API}/admin/detector-review/batch?detector=${detector}&limit=20`,
        { credentials: "include" }
      );
      setClaims(res.ok ? (await res.json()).claims || [] : []);
    } finally {
      setLoading(false);
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

  const summary = results?.summary?.[detector];
  const active = DETECTORS.find((d) => d.id === detector);

  return (
    <Layout>
      <div className="max-w-5xl mx-auto py-6 px-4 space-y-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="max-w-2xl">
            <h1 className="text-xl font-heading">Detector review</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Every detector we have built is <strong>muted</strong> — it runs,
              it produces claims, and none of them reach a player. A detector
              is only allowed to speak once <strong>you</strong> have read 50
              of its claims and confirmed at least 95% are true. Not 50 I
              checked — 50 a person checked. That rule is why this page is the
              only way any of them get switched on.
            </p>
            <p className="text-sm text-muted-foreground mt-2">
              For each card: look at the board and answer{" "}
              <strong>is this statement true?</strong> Nothing you click puts
              anything in front of a player — it only adds to the count. A
              claim you mark Wrong is a bug report with a position attached.
            </p>
            <p className="text-xs text-muted-foreground mt-2">
              Judge the claim, not the wording. Most of these have never
              spoken, so the sentence is provisional and gets its own pass when
              they are wired into the caption layer.
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

        <div className="flex items-center gap-2 flex-wrap">
          {DETECTORS.map((d) => {
            const isSelected = detector === d.id;
            return (
              <button
                key={d.id}
                onClick={() => setDetector(d.id)}
                aria-pressed={isSelected}
                className={`px-3 py-1.5 text-xs rounded-sm border transition-colors ${
                  isSelected
                    ? "bg-foreground text-background border-foreground font-semibold"
                    : "border-border text-muted-foreground hover:bg-muted/50"
                }`}
              >
                {d.label}
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
            No unjudged <strong>{active?.label?.toLowerCase()}</strong>{" "}
            claims left in the scan window. Either you have ruled on them all,
            or this detector fires very sparsely.
          </p>
        )}

        {claims.map((c) => {
          const verdict = ruled[c.claim_key];
          const e = c.evidence || {};
          return (
            <div
              key={c.claim_key}
              className="border rounded-sm p-4 grid gap-4 md:grid-cols-[280px_1fr]"
            >
              <div className="space-y-1.5">
                {/* view-only: a reading surface, not a play surface. An
                    accidental drag would edit the position under review. */}
                <LichessBoard
                  fen={e.review_fen || e.fen_after || e.fen_before}
                  orientation={e.side_to_move === "black" ? "black" : "white"}
                  arrows={e.arrow ? [[e.arrow[0], e.arrow[1], "green"]] : []}
                  circles={(e.highlight || []).map((sq) => [sq, "red"])}
                  viewOnly={true}
                  interactive={false}
                />
                <p className="text-[11px] text-muted-foreground text-center">
                  {e.side_to_move === "black" ? "Black" : "White"} to move
                  {e.arrow_is ? ` · green arrow = ${e.arrow_is}` : ""}
                  {e.highlight_is ? ` · circle = ${e.highlight_is}` : ""}
                </p>
              </div>

              <div className="space-y-3 min-w-0">
                <p className="text-[15px] leading-snug text-foreground">
                  {c.claim}
                </p>

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
                  {e.pv_after_best?.length > 0 && (
                    <div className="flex gap-2">
                      <dt className="text-muted-foreground w-28 shrink-0">
                        Engine line
                      </dt>
                      <dd className="font-medium">
                        {e.pv_after_best.join(" ")}
                      </dd>
                    </div>
                  )}
                  {e.mating_line?.length > 0 && (
                    <div className="flex gap-2">
                      <dt className="text-muted-foreground w-28 shrink-0">
                        Mating line
                      </dt>
                      <dd className="font-medium">{e.mating_line.join(" ")}</dd>
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
                </dl>

                <div className="flex items-center gap-2 pt-1">
                  <Button
                    size="sm"
                    variant={verdict === "true" ? "default" : "outline"}
                    onClick={() => rule(c, "true")}
                  >
                    <Check className="w-3.5 h-3.5 mr-1" /> True
                  </Button>
                  <Button
                    size="sm"
                    variant={verdict === "false" ? "destructive" : "outline"}
                    onClick={() => rule(c, "false")}
                  >
                    <X className="w-3.5 h-3.5 mr-1" /> Wrong
                  </Button>
                  <Button
                    size="sm"
                    variant={verdict === "unsure" ? "secondary" : "outline"}
                    onClick={() => rule(c, "unsure")}
                  >
                    <HelpCircle className="w-3.5 h-3.5 mr-1" /> Unsure
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
