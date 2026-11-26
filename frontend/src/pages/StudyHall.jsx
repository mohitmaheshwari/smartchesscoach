/**
 * /study-hall — a candidate visual direction, rendered on the real site.
 *
 * Why it exists: the theme repair shipped on 2026-11-26 fixed a broken
 * palette (surface separation, hairlines, elevation) but that is plumbing,
 * not design. Mohit's note: it still read as rough work. This is the
 * direction proposed in response — "Study Hall": warm paper, editorial
 * serif over Inter, ink text, one ember accent, hairline rules.
 *
 * What is real and what is not:
 *   - The rating figures (1251 -> 1181 -> 1429, +248, 590 games, joined
 *     6 April) are one real user's, measured from prod on 2026-11-26.
 *   - The six pattern names, weighted scores, counts and clean streaks are
 *     a real `user_pattern_decay` document, same date.
 *   - The path BETWEEN the chart's endpoints is drawn, not measured. The
 *     per-game series exists in `games.user_rating` and should replace it
 *     before any of this ships to a user.
 *   - "What you've dropped" is empty because for that user it genuinely is:
 *     all six patterns are state=active and none has a clean streak of 3.
 *
 * It is self-contained: styles live in styles/study-hall.css scoped to
 * `.sh-root`, nothing touches the app's own tokens, and the board is the
 * real LichessBoard component, unmodified. Deleting this file, the stylesheet
 * and the route removes it with no trace.
 *
 * Unauthenticated and unlinked, like /shell2 and /theme2.
 */
import React, { useState } from "react";
import { Link } from "react-router-dom";
import LichessBoard from "@/components/LichessBoard";
import "@/styles/study-hall.css";

const LAST_GAME_FEN =
  "r1b1k2r/pp2qppp/2n5/3pp3/1b1P4/2NBPN2/PP3PPP/R1BQ1RK1 w kq - 0 10";

// Real `user_pattern_decay` scores, read from prod 2026-11-26.
const PATTERNS = [
  {
    name: "Piece safety",
    display: 5,
    score: 4.65,
    raw: 15,
    recent: 11,
    streak: 0,
    line: "Pieces left where something can take them. Your most frequent, and it has not gone quiet yet.",
  },
  {
    name: "King safety",
    display: 4,
    score: 3.8,
    raw: 12,
    recent: 8,
    streak: 0,
    line: "Castling late, or opening the squares in front of your own king.",
  },
  {
    name: "Endgame technique",
    display: 3,
    score: 3.19,
    raw: 6,
    recent: 6,
    streak: 0,
    line: "Won positions that got away once the queens came off.",
  },
  {
    name: "Missed tactics",
    display: 3,
    score: 2.89,
    raw: 10,
    recent: 6,
    streak: 0,
    line: "Forks and pins that were there for you and went by.",
  },
  {
    name: "Seeing one move on",
    display: 1,
    score: 1.27,
    raw: 2,
    recent: 2,
    streak: 0,
    line: "You saw their move. You did not see what came after it.",
  },
  {
    name: "Opening knowledge",
    display: 1,
    score: 1.15,
    raw: 8,
    recent: 5,
    streak: 2,
    line: "Leaving theory early and ending up somewhere you did not know.",
  },
];

const SLIPS = [
  { no: "08", hot: false, text: "The Vienna Game gave a level position." },
  {
    no: "10",
    hot: true,
    move: "Rf1",
    text: " nearly cost you a rook. After Nxb3 it would have had no safe square. They played f5 instead.",
  },
  {
    no: "23",
    hot: true,
    move: "dxe5",
    text: " gave them a big chance. Qb6 was strong, but they played fxe5.",
  },
];

const PRE_PATH =
  "M0,112 L30,124 L58,116 L86,132 L112,127 L145,142 L175,136 L205,151 L230,158";
const POST_PATH =
  "M230,158 L270,150 L305,161 L340,143 L375,132 L412,138 L450,120 L488,110 " +
  "L525,118 L562,98 L600,88 L638,95 L675,76 L712,70 L750,78 L788,58 L825,50 " +
  "L862,57 L900,40 L938,34 L975,42 L1010,28 L1040,27";

const ink = (t) => `rgb(var(--sh-${t}))`;

function Mark({ children }) {
  return (
    <strong style={{ fontWeight: 600, color: ink("ink") }}>{children}</strong>
  );
}

function Thread() {
  return (
    <figure style={{ margin: "36px 0 0" }}>
      <svg
        viewBox="0 0 1040 206"
        width="100%"
        style={{ display: "block", height: "auto", overflow: "visible" }}
        role="img"
        aria-label="Rapid rating over time. It drifts down from 1251 across the 28 games before joining, then climbs from 1181 to 1429 over the 590 games after."
      >
        <line x1="0" y1="190" x2="1040" y2="190" style={{ stroke: ink("line-firm") }} strokeWidth="1" />
        <line x1="0" y1="125" x2="1040" y2="125" style={{ stroke: ink("line-soft") }} strokeWidth="1" strokeDasharray="2 5" />
        <line x1="0" y1="60" x2="1040" y2="60" style={{ stroke: ink("line-soft") }} strokeWidth="1" strokeDasharray="2 5" />

        <path
          d={`${POST_PATH} L1040,190 L230,190 Z`}
          style={{ fill: ink("ember-lit") }}
          fillOpacity="0.08"
        />
        <path
          d={PRE_PATH}
          fill="none"
          style={{ stroke: ink("ghost") }}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
          strokeDasharray="5 4"
        />
        <path
          d={POST_PATH}
          fill="none"
          style={{ stroke: ink("ember-lit") }}
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        <line x1="230" y1="10" x2="230" y2="190" style={{ stroke: ink("ink") }} strokeWidth="1" />
        <circle cx="230" cy="158" r="4.5" style={{ fill: ink("paper"), stroke: ink("ink") }} strokeWidth="2" />
        <circle cx="1040" cy="27" r="4.5" style={{ fill: ink("ember-lit") }} />

        <text x="238" y="24" fontSize="11" fontWeight="700" letterSpacing="1.4" style={{ fill: ink("ink") }}>JOINED</text>
        <text x="238" y="40" fontSize="11" style={{ fill: ink("muted") }}>6 April</text>
        <text x="0" y="178" fontSize="12" fontWeight="600" style={{ fill: ink("muted") }}>1251</text>
        <text x="186" y="178" fontSize="12" fontWeight="600" style={{ fill: ink("muted") }}>1181</text>
        <text x="1000" y="18" fontSize="12" fontWeight="700" style={{ fill: ink("ember") }}>1429</text>
      </svg>
    </figure>
  );
}

function TrackRow({ p, max }) {
  const pct = Math.max(0, Math.min(100, (p.score / max) * 100));
  const cold = p.score < 2;
  const colour = cold ? ink("faint") : ink("ember-lit");
  const gate =
    p.streak >= 3 && cold
      ? "both gates met"
      : cold
      ? `needs ${3 - p.streak} clean`
      : "still loud";

  return (
    <div className="sh-track-row">
      <div className="sh-track-name">
        <div
          style={{
            fontFamily: "var(--sh-display)",
            fontSize: 16.5,
            fontWeight: 600,
            letterSpacing: "-0.01em",
          }}
        >
          {p.name}
        </div>
        <div className="sh-num" style={{ fontSize: 11.5, color: ink("faint"), marginTop: 3 }}>
          {p.recent} of {p.raw} lately
        </div>
      </div>

      <div className="sh-track-rail">
        <div
          style={{
            position: "absolute", left: 0, right: 0, top: 12, height: 2,
            background: ink("line-soft"), borderRadius: 1,
          }}
        />
        <div
          style={{
            position: "absolute", left: 0, top: 12, height: 2, borderRadius: 1,
            background: colour, width: `${pct}%`,
          }}
        />
        <div
          style={{
            position: "absolute", top: 6, width: 14, height: 14, borderRadius: "50%",
            background: colour,
            border: `2.5px solid ${ink("raised")}`,
            boxShadow: `0 0 0 1px ${colour}`,
            left: `${pct}%`, marginLeft: -7,
          }}
        />
        <div
          style={{
            position: "absolute", top: -2, display: "flex", gap: 3,
            left: `${pct}%`, marginLeft: 12,
          }}
          aria-hidden="true"
        >
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              style={{
                display: "block", width: 5, height: 5, borderRadius: "50%",
                background: i < p.streak ? ink("moss") : "transparent",
                border: i < p.streak ? "none" : `1px solid ${ink("dash")}`,
              }}
            />
          ))}
        </div>
      </div>

      <div className="sh-track-score">
        <span
          className="sh-num"
          style={{ fontFamily: "var(--sh-display)", fontSize: 17, fontWeight: 600 }}
        >
          {p.score.toFixed(2)}
        </span>
        <div style={{ fontSize: 11, color: ink("faint"), marginTop: 2 }}>{gate}</div>
      </div>
    </div>
  );
}

export default function StudyHall() {
  const [theme, setTheme] = useState("light");
  const max = 5;

  return (
    <div className="sh-root" data-sh-theme={theme}>
      {/* honest marker: this is a proposal on a live domain */}
      <div
        style={{
          background: ink("ink"), color: ink("raised"),
          fontSize: 12, letterSpacing: "0.04em",
          padding: "7px 16px", textAlign: "center",
        }}
      >
        Design proposal &mdash; &ldquo;Study Hall&rdquo;. Not the live product. Figures are real; the
        line between the chart&rsquo;s endpoints is drawn.
      </div>

      <header className="sh-masthead">
        <div
          className="sh-shell"
          style={{ height: 68, display: "flex", alignItems: "center", gap: 40 }}
        >
          <Link
            to="/study-hall"
            style={{
              display: "flex", alignItems: "center", gap: 11,
              textDecoration: "none", color: ink("ink"),
            }}
          >
            <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
              <rect width="20" height="20" rx="3" style={{ fill: ink("ink") }} />
              {[[0, 0], [10, 0], [5, 5], [15, 5], [0, 10], [10, 10], [5, 15], [15, 15]].map(
                ([x, y]) => (
                  <rect key={`${x}-${y}`} x={x} y={y} width="5" height="5" style={{ fill: ink("raised") }} />
                )
              )}
            </svg>
            <span
              style={{
                fontFamily: "var(--sh-display)", fontSize: 17,
                fontWeight: 600, letterSpacing: "0.1em",
              }}
            >
              CHESSGURU
            </span>
          </Link>

          <nav style={{ display: "flex", gap: 28, marginLeft: 8, overflowX: "auto" }}>
            <Link className="sh-navlink" to="/study-hall" aria-current="page">Coach</Link>
            <a className="sh-navlink" href="#ledger">Ledger</a>
            <Link className="sh-navlink" to="/play-with-coach">Play</Link>
            <Link className="sh-navlink" to="/lab">Games</Link>
          </nav>

          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 16 }}>
            <span className="sh-num" style={{ fontSize: 13, color: ink("muted"), whiteSpace: "nowrap" }}>
              Rapid <Mark>1429</Mark>
            </span>
            <button
              type="button"
              onClick={() => setTheme(theme === "light" ? "dark" : "light")}
              style={{
                minHeight: 34, padding: "0 14px", borderRadius: 3,
                border: `1px solid ${ink("line")}`, background: ink("sunken"),
                color: ink("muted"), fontSize: 12, fontWeight: 600, cursor: "pointer",
                whiteSpace: "nowrap",
              }}
            >
              {theme === "light" ? "Dark" : "Light"}
            </button>
          </div>
        </div>
      </header>

      <main className="sh-shell" style={{ paddingBottom: 96 }}>
        {/* ── the thread ─────────────────────────────────── */}
        <section style={{ padding: "56px 0 48px" }}>
          <div
            style={{
              display: "flex", flexWrap: "wrap", alignItems: "flex-end",
              justifyContent: "space-between", gap: 24,
            }}
          >
            <div style={{ maxWidth: 560 }}>
              <p className="sh-eyebrow">Since you joined</p>
              <h1 className="sh-display">You were sliding. Then you stopped.</h1>
            </div>
            <div style={{ textAlign: "right" }}>
              <div
                className="sh-num"
                style={{
                  fontFamily: "var(--sh-display)",
                  fontSize: "clamp(44px, 5vw, 68px)",
                  lineHeight: 0.9, fontWeight: 600,
                  color: ink("ember"), letterSpacing: "-0.03em",
                }}
              >
                +248
              </div>
              <p className="sh-num" style={{ margin: "10px 0 0", fontSize: 13, color: ink("muted") }}>
                1181 &rarr; 1429 rapid &middot; 590 games
              </p>
            </div>
          </div>

          <Thread />

          <div
            style={{
              display: "flex", flexWrap: "wrap", gap: 32, marginTop: 22,
              paddingTop: 18, borderTop: `1px solid ${ink("line")}`,
            }}
          >
            <p className="sh-prose" style={{ margin: 0, maxWidth: 620 }}>
              The dashed stretch is the 28 games you played before we met &mdash; you were
              drifting down about 70 points. The solid line is everything since. We are not
              claiming we did that; you played 590 games. But the turn happened here.
            </p>
            <a className="sh-link" href="#ledger" style={{ marginLeft: "auto", alignSelf: "center" }}>
              See what changed &rarr;
            </a>
          </div>
        </section>

        <hr className="sh-rule" />

        {/* ── last game ──────────────────────────────────── */}
        <section style={{ padding: "48px 0" }}>
          <p className="sh-eyebrow" style={{ marginBottom: 24 }}>Your last game &middot; Thursday</p>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 48 }}>
            <div style={{ flex: "0 1 300px", minWidth: 240 }}>
              <div className="sh-board-mount">
                <div style={{ aspectRatio: "1 / 1", width: "100%", overflow: "hidden" }}>
                  <LichessBoard
                    fen={LAST_GAME_FEN}
                    orientation="white"
                    viewOnly
                    interactive={false}
                    showCoordinates={false}
                  />
                </div>
              </div>
              <p className="sh-num" style={{ margin: "14px 0 0", fontSize: 13, color: ink("muted") }}>
                Move 10. You played{" "}
                <strong style={{ fontFamily: "var(--sh-display)", color: ink("ink"), fontWeight: 600 }}>
                  Rf1
                </strong>
                .
              </p>
            </div>

            <div style={{ flex: "1 1 420px", minWidth: 300 }}>
              <h2 className="sh-h2" style={{ marginTop: -6 }}>A winning position slipped away</h2>
              <p className="sh-prose" style={{ margin: "14px 0 0", maxWidth: "52ch" }}>
                You had the chances. You missed them, and your opponent took some of what you
                gave. Look for their best reply before you move.
              </p>

              <ol style={{ margin: "28px 0 0", padding: 0, listStyle: "none" }}>
                {SLIPS.map((s, i) => (
                  <li
                    key={s.no}
                    style={{
                      display: "flex", gap: 16, padding: "14px 0",
                      borderTop: `1px solid ${ink("line")}`,
                      borderBottom: i === SLIPS.length - 1 ? `1px solid ${ink("line")}` : "none",
                    }}
                  >
                    <span
                      className="sh-num"
                      style={{
                        flex: "0 0 34px", fontFamily: "var(--sh-display)", fontSize: 13,
                        fontWeight: 600, paddingTop: 2,
                        color: s.hot ? ink("ember") : ink("ghost"),
                      }}
                    >
                      {s.no}
                    </span>
                    <span
                      style={{
                        fontSize: 14.5, lineHeight: 1.6,
                        color: s.hot ? ink("ink") : ink("ink-2"),
                      }}
                    >
                      {s.move ? <Mark>{s.move}</Mark> : null}
                      {s.text}
                    </span>
                  </li>
                ))}
              </ol>

              <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 28 }}>
                <Link className="sh-btn sh-btn--solid" to="/lab">Open the moment</Link>
                <Link className="sh-btn sh-btn--quiet" to="/play-with-coach">Play it again from here</Link>
              </div>
            </div>
          </div>
        </section>

        <hr className="sh-rule" />

        {/* ── the ledger ─────────────────────────────────── */}
        <section id="ledger" style={{ padding: "48px 0 0", scrollMarginTop: 24 }}>
          <div style={{ maxWidth: 640, marginBottom: 32 }}>
            <p className="sh-eyebrow">The ledger</p>
            <h2 className="sh-display" style={{ fontSize: "clamp(26px, 3vw, 38px)" }}>
              Everything I&rsquo;m still on you about &mdash; and how close each one is to being dropped.
            </h2>
            <p className="sh-prose" style={{ margin: "16px 0 0" }}>
              A habit leaves this list two ways at once: it has to go cold, and you have to
              string together clean games. Both gates, or it stays.
            </p>
          </div>

          <div className="sh-panel" style={{ padding: "32px clamp(18px, 2.6vw, 36px) 28px" }}>
            <div className="sh-track-gates" style={{ display: "flex", marginBottom: 6, paddingLeft: 190 }}>
              <div style={{ width: "20%", textAlign: "center" }}>
                <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: ink("moss") }}>Dropped</span>
              </div>
              <div style={{ width: "20%", textAlign: "center" }}>
                <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: ink("faint") }}>Going quiet</span>
              </div>
              <div style={{ width: "60%", textAlign: "center" }}>
                <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: ink("ember") }}>Still live</span>
              </div>
            </div>

            <div style={{ position: "relative" }}>
              <div
                className="sh-track-gates"
                aria-hidden="true"
                style={{ position: "absolute", left: 190, right: 118, top: 0, bottom: 34, pointerEvents: "none" }}
              >
                <div style={{ position: "absolute", left: "25%", top: 0, bottom: 0, width: 1, background: ink("moss"), opacity: 0.45 }} />
                <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 1, background: ink("dash") }} />
              </div>

              {PATTERNS.map((p) => (
                <TrackRow key={p.name} p={p} max={max} />
              ))}
            </div>

            <p style={{ margin: "18px 0 0", fontSize: 13, lineHeight: 1.6, color: ink("muted"), maxWidth: "74ch" }}>
              The number is how loud a habit still is &mdash; a slip eight games ago counts for
              less than one last night. The three marks are clean games in a row. You need{" "}
              <Mark>three</Mark>, and a score under <Mark>2.0</Mark>, before I ease off.
            </p>
          </div>

          {/* ── dropped ──────────────────────────────────── */}
          <div style={{ padding: "44px 0 0" }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 14, flexWrap: "wrap" }}>
              <h2 className="sh-h2">What you&rsquo;ve dropped</h2>
              <span className="sh-num" style={{ fontSize: 13, color: ink("faint") }}>nothing yet</span>
            </div>

            <div
              style={{
                marginTop: 20, border: `1px dashed ${ink("dash")}`, borderRadius: 5,
                padding: "30px clamp(18px, 2.4vw, 32px)",
              }}
            >
              <p className="sh-prose" style={{ margin: 0, maxWidth: "60ch" }}>
                Nothing has left the list so far. Six habits are still live and none has put
                three clean games together. When one does, it moves here with the date, and I
                stop bringing it up.
              </p>

              <p className="sh-eyebrow" style={{ margin: "26px 0 10px", fontSize: 10.5, letterSpacing: "0.12em", color: ink("ghost") }}>
                What one will look like
              </p>

              <div className="sh-card" style={{ padding: "20px 22px", opacity: 0.62, maxWidth: 620 }}>
                <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
                  <h3
                    style={{
                      margin: 0, fontFamily: "var(--sh-display)", fontSize: 19, fontWeight: 600,
                      textDecoration: "line-through",
                      textDecorationColor: ink("moss"),
                      textDecorationThickness: "1.5px",
                    }}
                  >
                    Hanging a piece
                  </h3>
                  <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: ink("moss") }}>
                    Dropped
                  </span>
                </div>
                <p className="sh-prose" style={{ margin: "10px 0 0", fontSize: 14 }}>
                  Eleven games clean. I used to raise this most weeks; I haven&rsquo;t since late
                  October.
                </p>
                <p className="sh-num" style={{ margin: "12px 0 0", fontSize: 11.5, color: ink("faint") }}>
                  Raised 12 March &mdash; dropped 28 October
                </p>
              </div>

              <p style={{ margin: "18px 0 0", fontSize: 12.5, color: ink("faint"), maxWidth: "60ch" }}>
                Greyed out because it hasn&rsquo;t happened &mdash; this is the shape of the entry, not
                a record of yours.
              </p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
