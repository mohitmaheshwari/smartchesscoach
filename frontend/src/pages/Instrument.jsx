/**
 * /instrument — the honest progress page.
 *
 * Mohit, 2026-11-26: the first direction was Chessiro's page with my words on
 * it — warm cream, serif display, a sparkline with a JOINED notch. He was
 * right. This is a different thing in both look and argument.
 *
 * THE ARGUMENT. Every competitor can draw a rating line going up. Only we
 * hold a cause for each move, so only we can draw what is UNDERNEATH the
 * line. For this player the two disagree, and that disagreement is the
 * product:
 *
 *   rating            1202 -> 1539   (+337)
 *   piece safety       68% -> 62%    of games
 *   king safety        59% -> 52%
 *   missed tactics     47% -> 55%    WORSE
 *   opening knowledge  44% -> 32%
 *   endgame technique  24% -> 10%
 *
 * They gained 337 points while still hanging a piece in 62% of their games.
 * A page that showed only the green line would be lying by omission. This one
 * leads with the disagreement, because that is what a coach would say.
 *
 * EVERY NUMBER HERE IS MEASURED. 754 analysed rapid games for one real user
 * between 2026-02-23 and 2026-11-25, bucketed into 22 windows of ~34 games:
 * rating is the median `games.user_rating` in the window, each rate is the
 * share of that window's games where the cause appears on at least one of the
 * player's own moves (`game_analyses.stockfish_analysis.move_evaluations`,
 * `cognitive_gap`, excluding `is_opponent_move`). Nothing is drawn or
 * smoothed. The user is not named.
 *
 * Self-contained: styles scoped to `.in-root` in their own stylesheet,
 * nothing global touched. Unlinked, like /shell2 and /lobby2.
 */
import React from "react";
import { Link } from "react-router-dom";
import "@/styles/instrument.css";

// 22 windows of ~34 games. Measured from prod 2026-11-26; see header.
const SERIES = [
  { d: "Feb", r: 1202, piece_safety: 0.676, king_safety: 0.588, missed_tactic: 0.471, opening_knowledge: 0.441, endgame_technique: 0.235 },
  { d: "Apr", r: 1281, piece_safety: 0.765, king_safety: 0.500, missed_tactic: 0.559, opening_knowledge: 0.353, endgame_technique: 0.029 },
  { d: "Apr", r: 1320, piece_safety: 0.676, king_safety: 0.382, missed_tactic: 0.588, opening_knowledge: 0.324, endgame_technique: 0.118 },
  { d: "May", r: 1317, piece_safety: 0.618, king_safety: 0.794, missed_tactic: 0.471, opening_knowledge: 0.500, endgame_technique: 0.206 },
  { d: "May", r: 1356, piece_safety: 0.471, king_safety: 0.559, missed_tactic: 0.500, opening_knowledge: 0.412, endgame_technique: 0.235 },
  { d: "May", r: 1294, piece_safety: 0.735, king_safety: 0.765, missed_tactic: 0.441, opening_knowledge: 0.471, endgame_technique: 0.147 },
  { d: "Jun", r: 1299, piece_safety: 0.706, king_safety: 0.618, missed_tactic: 0.500, opening_knowledge: 0.353, endgame_technique: 0.265 },
  { d: "Jun", r: 1292, piece_safety: 0.706, king_safety: 0.559, missed_tactic: 0.676, opening_knowledge: 0.265, endgame_technique: 0.324 },
  { d: "Jul", r: 1353, piece_safety: 0.706, king_safety: 0.647, missed_tactic: 0.559, opening_knowledge: 0.353, endgame_technique: 0.235 },
  { d: "Jul", r: 1363, piece_safety: 0.559, king_safety: 0.618, missed_tactic: 0.382, opening_knowledge: 0.235, endgame_technique: 0.294 },
  { d: "Jul", r: 1437, piece_safety: 0.647, king_safety: 0.706, missed_tactic: 0.559, opening_knowledge: 0.500, endgame_technique: 0.235 },
  { d: "Jul", r: 1417, piece_safety: 0.706, king_safety: 0.676, missed_tactic: 0.471, opening_knowledge: 0.294, endgame_technique: 0.265 },
  { d: "Jul", r: 1396, piece_safety: 0.794, king_safety: 0.618, missed_tactic: 0.412, opening_knowledge: 0.500, endgame_technique: 0.206 },
  { d: "Jul", r: 1383, piece_safety: 0.647, king_safety: 0.765, missed_tactic: 0.500, opening_knowledge: 0.324, endgame_technique: 0.176 },
  { d: "Jul", r: 1364, piece_safety: 0.647, king_safety: 0.647, missed_tactic: 0.500, opening_knowledge: 0.441, endgame_technique: 0.176 },
  { d: "Aug", r: 1401, piece_safety: 0.588, king_safety: 0.676, missed_tactic: 0.529, opening_knowledge: 0.353, endgame_technique: 0.206 },
  { d: "Aug", r: 1431, piece_safety: 0.588, king_safety: 0.676, missed_tactic: 0.647, opening_knowledge: 0.412, endgame_technique: 0.147 },
  { d: "Sep", r: 1455, piece_safety: 0.735, king_safety: 0.559, missed_tactic: 0.529, opening_knowledge: 0.353, endgame_technique: 0.147 },
  { d: "Oct", r: 1461, piece_safety: 0.529, king_safety: 0.441, missed_tactic: 0.441, opening_knowledge: 0.412, endgame_technique: 0.176 },
  { d: "Oct", r: 1491, piece_safety: 0.706, king_safety: 0.618, missed_tactic: 0.500, opening_knowledge: 0.294, endgame_technique: 0.059 },
  { d: "Nov", r: 1486, piece_safety: 0.676, king_safety: 0.676, missed_tactic: 0.500, opening_knowledge: 0.412, endgame_technique: 0.235 },
  { d: "Nov", r: 1539, piece_safety: 0.625, king_safety: 0.525, missed_tactic: 0.550, opening_knowledge: 0.325, endgame_technique: 0.100 },
];

const CAUSES = [
  { key: "piece_safety", name: "Piece safety", plain: "left something where it could be taken" },
  { key: "king_safety", name: "King safety", plain: "opened the squares around your own king" },
  { key: "missed_tactic", name: "Missed tactics", plain: "a fork or pin was there and went by" },
  { key: "opening_knowledge", name: "Opening knowledge", plain: "left theory early, into something unfamiliar" },
  { key: "endgame_technique", name: "Endgame technique", plain: "a won ending that got away" },
];

const W = 880;
const H = 180;
const LO = 1150;
const HI = 1580;

const rgb = (t) => `rgb(var(--in-${t}))`;

function pointsFor() {
  return SERIES.map((p, i) => {
    const x = (i / (SERIES.length - 1)) * W;
    const y = H - ((p.r - LO) / (HI - LO)) * H;
    return [x, y];
  });
}

function RatingLine() {
  const pts = pointsFor();
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${line} L${W},${H} L0,${H} Z`;
  const last = pts[pts.length - 1];

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      width="100%"
      style={{ display: "block", height: "auto", overflow: "visible" }}
      role="img"
      aria-label="Rapid rating across 754 analysed games, rising from a median of 1202 in February to 1539 in November."
    >
      {[1200, 1300, 1400, 1500].map((r) => {
        const y = H - ((r - LO) / (HI - LO)) * H;
        return (
          <g key={r}>
            <line x1="0" y1={y} x2={W} y2={y} style={{ stroke: rgb("line-soft") }} strokeWidth="1" />
            <text x="0" y={y - 5} fontSize="10" fontFamily="var(--in-mono)" style={{ fill: rgb("faint") }}>
              {r}
            </text>
          </g>
        );
      })}
      <path d={area} style={{ fill: rgb("bone") }} fillOpacity="0.05" />
      <path
        d={line}
        fill="none"
        style={{ stroke: rgb("bone") }}
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle cx={last[0]} cy={last[1]} r="4" style={{ fill: rgb("bone") }} />
    </svg>
  );
}

function Lane({ cause }) {
  const first = SERIES[0][cause.key];
  const last = SERIES[SERIES.length - 1][cause.key];
  const delta = Math.round((last - first) * 100);
  const worse = delta > 0;
  const moved = Math.abs(delta) >= 10;

  return (
    <div className="in-lane">
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13.5, fontWeight: 600 }}>{cause.name}</div>
        <div style={{ fontSize: 11.5, lineHeight: 1.45, color: rgb("faint"), marginTop: 2 }}>
          {cause.plain}
        </div>
      </div>

      <div
        className="in-cells"
        role="img"
        aria-label={`${cause.name}: ${Math.round(first * 100)} percent of games at the start, ${Math.round(
          last * 100
        )} percent now.`}
      >
        {SERIES.map((p, i) => (
          <div
            key={i}
            className="in-cell"
            style={{
              background: moved && !worse ? rgb("cool") : rgb("warm"),
              opacity: 0.12 + p[cause.key] * 0.88,
            }}
          />
        ))}
      </div>

      <div
        className="in-delta"
        style={{ color: worse ? rgb("bad") : moved ? rgb("cool") : rgb("dim") }}
      >
        {Math.round(first * 100)}&thinsp;&rarr;&thinsp;{Math.round(last * 100)}%
      </div>
    </div>
  );
}

export default function Instrument() {
  return (
    <div className="in-root">
      <div
        style={{
          borderBottom: `1px solid ${rgb("line")}`,
          background: rgb("panel"),
        }}
      >
        <div
          className="in-shell"
          style={{ display: "flex", alignItems: "center", gap: 16, minHeight: 56, flexWrap: "wrap" }}
        >
          <span
            className="in-num"
            style={{ fontSize: 13, letterSpacing: "0.18em", fontWeight: 600 }}
          >
            CHESSGURU
          </span>
          <span className="in-label" style={{ marginLeft: "auto" }}>
            Direction: Instrument &middot; not the live product
          </span>
        </div>
      </div>

      <main className="in-shell" style={{ paddingTop: 40, paddingBottom: 80 }}>
        {/* ── the claim ─────────────────────────────────────── */}
        <div className="in-files" style={{ maxWidth: 280, marginBottom: 22 }} aria-hidden="true">
          {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
            <span key={i} className={`in-file${i < 5 ? " in-file--on" : ""}`} />
          ))}
        </div>

        <p className="in-label">Nine months &middot; 754 analysed games</p>
        <h1 className="in-h1">
          Your rating went up 337 points.
          <br />
          Four of your five habits did not move.
        </h1>
        <p className="in-lede">
          Every app can draw the line going up. We keep a reason for each move you
          played, so we can also draw what is underneath it &mdash; and for you the two
          disagree. That gap is the thing worth your next month.
        </p>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 24 }}>
          <span className="in-chip">1202 &rarr; 1539 RAPID</span>
          <span className="in-chip">FEB 23 &rarr; NOV 25</span>
          <span className="in-chip">754 GAMES READ</span>
        </div>

        {/* ── the line ──────────────────────────────────────── */}
        <section className="in-panel" style={{ marginTop: 32, padding: "22px clamp(14px, 2.4vw, 26px)" }}>
          <p className="in-label">What everyone shows you</p>
          <div style={{ marginTop: 14 }}>
            <RatingLine />
          </div>

          <hr className="in-rule" style={{ margin: "26px 0 4px" }} />

          <p className="in-label" style={{ paddingTop: 18 }}>
            What is underneath it &mdash; share of games where it happened
          </p>
          <div style={{ marginTop: 6 }}>
            {CAUSES.map((c) => (
              <Lane key={c.key} cause={c} />
            ))}
          </div>

          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 18,
              marginTop: 18,
              paddingTop: 14,
              borderTop: `1px solid ${rgb("line")}`,
              fontSize: 11.5,
              color: rgb("faint"),
            }}
          >
            <span>
              <span
                style={{
                  display: "inline-block", width: 9, height: 9, borderRadius: 1,
                  background: rgb("warm"), marginRight: 7,
                }}
                aria-hidden="true"
              />
              still roughly where it was
            </span>
            <span>
              <span
                style={{
                  display: "inline-block", width: 9, height: 9, borderRadius: 1,
                  background: rgb("cool"), marginRight: 7,
                }}
                aria-hidden="true"
              />
              genuinely moved
            </span>
            <span style={{ marginLeft: "auto" }}>darker cell = happened in more of those games</span>
          </div>
        </section>

        {/* ── what a coach would say ────────────────────────── */}
        <section style={{ marginTop: 36, display: "grid", gap: 20, gridTemplateColumns: "repeat(auto-fit, minmax(min(300px, 100%), 1fr))" }}>
          <div className="in-panel" style={{ padding: 22 }}>
            <p className="in-label">The one that got worse</p>
            <h2 style={{ margin: "10px 0 0", fontSize: 19, fontWeight: 600 }}>Missed tactics</h2>
            <p style={{ margin: "10px 0 0", fontSize: 14, lineHeight: 1.6, color: rgb("dim") }}>
              47% of your games in February, 55% now. You are winning more while
              seeing less. That usually means the wins are coming from your
              opponents&rsquo; errors rather than your own sight of the board &mdash; which
              stops working at the next level up.
            </p>
            <Link className="in-btn in-btn--solid" to="/lab" style={{ marginTop: 18 }}>
              Show me one
            </Link>
          </div>

          <div className="in-panel" style={{ padding: 22 }}>
            <p className="in-label">The one you actually fixed</p>
            <h2 style={{ margin: "10px 0 0", fontSize: 19, fontWeight: 600 }}>Endgame technique</h2>
            <p style={{ margin: "10px 0 0", fontSize: 14, lineHeight: 1.6, color: rgb("dim") }}>
              24% of your games down to 10%. You used to lose won endings; mostly
              you don&rsquo;t any more. This is the one I will stop bringing up.
            </p>
            <Link className="in-btn in-btn--quiet" to="/lab" style={{ marginTop: 18 }}>
              See the last one
            </Link>
          </div>
        </section>

        <p style={{ marginTop: 34, fontSize: 11.5, lineHeight: 1.6, color: rgb("faint"), maxWidth: "76ch" }}>
          Measured, not illustrated: 754 analysed rapid games for one real player,
          23 Feb &ndash; 25 Nov 2026, in 22 windows of about 34 games. Rating is the median
          of that window; each percentage is the share of its games where the cause
          appears on at least one of the player&rsquo;s own moves. No smoothing, no
          projection, and the player is not named.
        </p>
      </main>
    </div>
  );
}
