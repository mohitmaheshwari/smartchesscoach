/**
 * copy-stockfish.js — bundle the client-side Stockfish (WASM) engine.
 *
 * Runs automatically before `start` and `build` (prestart/prebuild hooks), so the
 * engine ships with the app on every build — zero manual step, nothing committed
 * as a binary, no browser "install" (it's served as a static asset, exactly like
 * chess.com bundles its engine). docs/pwc_client_eval_scope.md.
 *
 * Light SF11-class build (~2.2MB total, no 39MB net) — plenty for the 600-1300
 * audience at the time-bounded ~800ms / depth-12 floor we locked on data.
 */
const fs = require("fs");
const path = require("path");

const SRC = path.join(__dirname, "..", "node_modules", "stockfish.js");
const DEST = path.join(__dirname, "..", "public", "stockfish");
const FILES = ["stockfish.js", "stockfish.wasm", "stockfish.wasm.js"];

try {
  if (!fs.existsSync(SRC)) {
    console.warn("[copy-stockfish] stockfish.js not in node_modules — skipping " +
      "(client eval will fall back to the server path). Run `npm i`.");
    process.exit(0);
  }
  fs.mkdirSync(DEST, { recursive: true });
  let copied = 0;
  for (const f of FILES) {
    const src = path.join(SRC, f);
    if (fs.existsSync(src)) {
      fs.copyFileSync(src, path.join(DEST, f));
      copied++;
    }
  }
  console.log(`[copy-stockfish] bundled ${copied}/${FILES.length} engine files -> public/stockfish/`);
} catch (e) {
  // Never fail the build over this — client eval simply falls back to server eval.
  console.warn("[copy-stockfish] copy failed (non-fatal):", e.message);
}

// Stockfish 17.1, lite single-threaded build (~7MB), for the line board on game
// review: the reply and arrows come from the browser at once
// (docs/play_any_line_scope.md, section 10). Single-threaded, so no COOP/COEP
// headers are needed. The worker finds its .wasm next to its .js by name, so
// both keep the package's own (hashed) names.
const SF17_SRC = path.join(__dirname, "..", "node_modules", "stockfish", "src");
const SF17_DEST = path.join(__dirname, "..", "public", "stockfish17");
const SF17_FILES = ["stockfish-17.1-lite-single-03e3232.js", "stockfish-17.1-lite-single-03e3232.wasm"];
try {
  if (!fs.existsSync(SF17_SRC)) {
    console.warn("[copy-stockfish] stockfish@17.1 not in node_modules — skipping " +
      "(the line board falls back to the server engine).");
  } else {
    fs.mkdirSync(SF17_DEST, { recursive: true });
    let n = 0;
    for (const f of SF17_FILES) {
      const src = path.join(SF17_SRC, f);
      if (fs.existsSync(src)) {
        fs.copyFileSync(src, path.join(SF17_DEST, f));
        n++;
      }
    }
    console.log(`[copy-stockfish] bundled ${n}/${SF17_FILES.length} Stockfish 17.1 lite files -> public/stockfish17/`);
  }
} catch (e) {
  console.warn("[copy-stockfish] Stockfish 17.1 copy failed (non-fatal):", e.message);
}
