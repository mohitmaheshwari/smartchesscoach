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
const DETECTORS = [
  { id: "simple_hang", label: "Hung a piece", grade: "shadow" },
  { id: "fork", label: "Missed fork", grade: "shadow" },
  { id: "discovered_attack", label: "Missed discovered attack", grade: "shadow" },
  { id: "left_book", label: "Left the book", grade: "shadow" },
  { id: "allowed_mate", label: "Allowed mate", grade: "shadow" },
];

export default function AdminDetectorReview() {
  const [detector, setDetector] = useState(DETECTORS[0].id);
  const [claims, setClaims] = useState([]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [ruled, setRuled] = useState({});

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
      }),
    });
    loadResults();
  };

  const summary = results?.summary?.[detector];

  return (
    <Layout>
      <div className="max-w-5xl mx-auto py-6 px-4 space-y-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-xl font-heading">Detector review</h1>
            <p className="text-sm text-muted-foreground max-w-2xl">
              What a shadow detector would say, if it were allowed to speak.
              Ruling here records evidence — it does not put anything in front
              of a player.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={load} disabled={loading}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Reload
          </Button>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {DETECTORS.map((d) => (
            <button
              key={d.id}
              onClick={() => setDetector(d.id)}
              className={`px-3 py-1.5 text-xs rounded-sm border transition-colors ${
                detector === d.id ? "bg-muted font-medium" : "hover:bg-muted/50"
              }`}
            >
              {d.label} <span className="opacity-60">· {d.grade}</span>
            </button>
          ))}
        </div>

        {summary && (
          <div className="text-xs font-mono border rounded-sm p-3 bg-muted/20">
            ruled {summary.judged} · true {summary.true} · false {summary.false}
            {summary.unsure ? ` · unsure ${summary.unsure}` : ""}
            {summary.precision !== null && (
              <> · <strong>precision {summary.precision}%</strong></>
            )}
            <span className="opacity-60">
              {"  "}— caption needs {summary.caption_bar.fires} fires at{" "}
              {summary.caption_bar.precision}%, plan needs{" "}
              {summary.plan_bar.fires} at {summary.plan_bar.precision}% plus{" "}
              {summary.plan_bar.recall}% recall
            </span>
          </div>
        )}

        {loading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="w-4 h-4 animate-spin" /> Scanning real games…
          </div>
        )}

        {!loading && claims.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No unjudged claims in the scan window. Either everything here is
            ruled, or this detector fires very sparsely.
          </p>
        )}

        {claims.map((c) => {
          const verdict = ruled[c.claim_key];
          return (
            <div
              key={c.claim_key}
              className="border rounded-sm p-4 grid gap-4 md:grid-cols-[260px_1fr]"
            >
              {/* view-only: this is a reading surface, not a play surface,
                  and an accidental drag would edit the position under review */}
              <LichessBoard
                // The backend says which position the claim is ABOUT: "after X your
                  // piece hangs" wants the position after, a missed fork
                  // wants the position the fork was available in.
                  fen={
                    c.evidence?.review_fen ||
                    c.evidence?.fen_after ||
                    c.evidence?.fen_before
                  }
                viewOnly={true}
                interactive={false}
                disableArrows={true}
              />
              <div className="space-y-2 min-w-0">
                <p className="text-[15px] text-foreground">{c.claim}</p>
                {/* Every detector carries different evidence, so this renders
                    whatever it actually supplied rather than assuming the
                    allowed-mate shape. A field the detector did not set is
                    simply absent, not an empty label the reviewer has to
                    decode. */}
                <p className="text-[11px] font-mono text-muted-foreground break-all">
                  {Object.entries(c.evidence || {})
                    .filter(
                      ([k, v]) =>
                        !["fen_before", "fen_after"].includes(k) &&
                        v !== null &&
                        v !== undefined &&
                        v !== "" &&
                        !(Array.isArray(v) && v.length === 0)
                    )
                    .map(
                      ([k, v]) =>
                        `${k} ${Array.isArray(v) ? v.join(" ") : typeof v === "object" ? JSON.stringify(v) : v}`
                    )
                    .join(" · ")}
                </p>
                <p className="text-[11px] font-mono text-muted-foreground break-all">
                  {c.evidence?.fen_before}
                </p>
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
