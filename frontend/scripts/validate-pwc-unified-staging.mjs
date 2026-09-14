import { spawn } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

const baseUrl = process.env.PWC_STAGING_URL || "http://127.0.0.1:3001";
const apiBaseUrl = process.env.PWC_STAGING_API_URL || "http://127.0.0.1:8010/api";
const chromePath = process.env.CHROME_PATH
  || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const artifactDir = process.env.PWC_STAGING_ARTIFACT_DIR
  || path.resolve("..", "docs", "qa");
const expectedFocus = process.env.PWC_STAGING_EXPECTED_FOCUS || "";
const expectedInstruction = process.env.PWC_STAGING_EXPECTED_INSTRUCTION || "";
const port = 9300 + Math.floor(Math.random() * 500);
const profileDir = mkdtempSync(path.join(tmpdir(), "chessguru-pwc-stage-"));

mkdirSync(artifactDir, { recursive: true });

const chrome = spawn(chromePath, [
  "--headless=new",
  "--disable-gpu",
  "--no-first-run",
  "--no-default-browser-check",
  `--remote-debugging-port=${port}`,
  `--user-data-dir=${profileDir}`,
  "about:blank",
], {
  stdio: ["ignore", "ignore", "pipe"],
  windowsHide: true,
});

let chromeError = "";
chrome.stderr.on("data", (chunk) => {
  chromeError = `${chromeError}${chunk.toString()}`.slice(-4000);
});

const delay = (milliseconds) => new Promise((resolve) => {
  setTimeout(resolve, milliseconds);
});

async function pollJson(url, timeoutMs = 20_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return await response.json();
    } catch (_error) {
      // Chrome is still starting.
    }
    await delay(200);
  }
  throw new Error(`Chrome DevTools did not become ready: ${chromeError}`);
}

function connect(webSocketUrl) {
  const socket = new WebSocket(webSocketUrl);
  const pending = new Map();
  const handlers = new Map();
  let nextId = 1;

  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else resolve(message.result || {});
      return;
    }
    for (const handler of handlers.get(message.method) || []) {
      handler(message.params || {});
    }
  });

  const ready = new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });

  return {
    ready,
    close: () => socket.close(),
    on(method, handler) {
      if (!handlers.has(method)) handlers.set(method, []);
      handlers.get(method).push(handler);
    },
    send(method, params = {}) {
      const id = nextId++;
      return new Promise((resolve, reject) => {
        pending.set(id, { resolve, reject });
        socket.send(JSON.stringify({ id, method, params }));
      });
    },
  };
}

async function evaluate(client, expression) {
  const result = await client.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.text || "Browser evaluation failed");
  }
  return result.result?.value;
}

async function waitFor(client, expression, label, timeoutMs = 20_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await evaluate(client, `Boolean(${expression})`)) return;
    await delay(200);
  }
  const visibleText = await evaluate(
    client,
    "document.body?.innerText?.slice(0, 3000) || ''",
  );
  throw new Error(`Timed out waiting for ${label}. Visible text:\n${visibleText}`);
}

async function clickSelector(client, selector) {
  const clicked = await evaluate(client, `(() => {
    const element = document.querySelector(${JSON.stringify(selector)});
    if (!element) return false;
    element.click();
    return true;
  })()`);
  if (!clicked) throw new Error(`Missing clickable element: ${selector}`);
}

async function clickButton(client, text) {
  const clicked = await evaluate(client, `(() => {
    const expected = ${JSON.stringify(text)};
    const element = [...document.querySelectorAll('button')]
      .find((button) => button.textContent.trim() === expected);
    if (!element) return false;
    element.click();
    return true;
  })()`);
  if (!clicked) throw new Error(`Missing button: ${text}`);
}

async function capture(client, name) {
  const { data } = await client.send("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: false,
  });
  const outputPath = path.join(artifactDir, name);
  writeFileSync(outputPath, Buffer.from(data, "base64"));
  return outputPath;
}

async function clickBoardSquare(client, square, orientation = "white") {
  const point = await evaluate(client, `(() => {
    const board = document.querySelector('[data-testid="coach-play-board-stage"] cg-board');
    if (!board) return null;
    const rect = board.getBoundingClientRect();
    const file = ${JSON.stringify(square)}.charCodeAt(0) - 97;
    const rank = Number(${JSON.stringify(square)}[1]) - 1;
    const visualFile = ${JSON.stringify(orientation)} === 'white' ? file : 7 - file;
    const visualRank = ${JSON.stringify(orientation)} === 'white' ? 7 - rank : rank;
    return {
      x: rect.left + ((visualFile + 0.5) * rect.width / 8),
      y: rect.top + ((visualRank + 0.5) * rect.height / 8),
    };
  })()`);
  if (!point) throw new Error(`Could not locate board square ${square}`);
  await client.send("Input.dispatchMouseEvent", {
    type: "mousePressed",
    x: point.x,
    y: point.y,
    button: "left",
    clickCount: 1,
  });
  await client.send("Input.dispatchMouseEvent", {
    type: "mouseReleased",
    x: point.x,
    y: point.y,
    button: "left",
    clickCount: 1,
  });
  await delay(120);
}

async function playE4(client) {
  await clickBoardSquare(client, "e2");
  await clickBoardSquare(client, "e4");
}

async function waitForCompletedPlyPair(client, label) {
  await waitFor(client, `(async () => {
    const sessionId = new URL(window.location.href).searchParams.get('session');
    if (!sessionId) return false;
    const response = await fetch(
      ${JSON.stringify(`${apiBaseUrl}/coach/play/state/`)} + sessionId,
      { credentials: 'include' },
    );
    if (!response.ok) return false;
    const payload = await response.json();
    return (payload.session?.move_history?.length || 0) >= 2
      && payload.is_player_turn === true;
  })()`, label, 60_000);
}

async function openPage({ width, height, mobile = false }) {
  const target = await fetch(
    `http://127.0.0.1:${port}/json/new?${encodeURIComponent("about:blank")}`,
    { method: "PUT" },
  ).then((response) => response.json());
  const client = connect(target.webSocketDebuggerUrl);
  await client.ready;
  await client.send("Page.enable");
  await client.send("Runtime.enable");
  await client.send("Network.enable");
  client.diagnostics = {
    consoleErrors: [],
    exceptions: [],
    coachApiFailures: [],
  };
  client.on("Runtime.consoleAPICalled", ({ type, args = [] }) => {
    if (type !== "error") return;
    client.diagnostics.consoleErrors.push(
      args.map((arg) => arg.value || arg.description || "").join(" "),
    );
  });
  client.on("Runtime.exceptionThrown", ({ exceptionDetails }) => {
    client.diagnostics.exceptions.push(
      exceptionDetails?.exception?.description
        || exceptionDetails?.text
        || "Uncaught browser exception",
    );
  });
  client.on("Network.responseReceived", ({ response }) => {
    if (response?.url?.includes("/api/coach/play/") && response.status >= 400) {
      client.diagnostics.coachApiFailures.push({
        status: response.status,
        url: response.url,
      });
    }
  });
  await client.send("Emulation.setDeviceMetricsOverride", {
    width,
    height,
    deviceScaleFactor: 1,
    mobile,
  });
  await client.send("Page.navigate", {
    url: `${baseUrl}/play-with-coach`,
  });
  await waitFor(
    client,
    "document.readyState === 'complete'",
    "document readiness",
  );
  await waitFor(
    client,
    "document.querySelector('[data-testid=\"unified-coach-play-setup\"]')",
    "unified setup",
  );
  return client;
}

function assertCleanBrowser(client, label) {
  const diagnostics = client.diagnostics || {};
  assert((diagnostics.consoleErrors || []).length === 0,
    `${label} logged browser errors: ${JSON.stringify(diagnostics.consoleErrors)}`);
  assert((diagnostics.exceptions || []).length === 0,
    `${label} threw browser exceptions: ${JSON.stringify(diagnostics.exceptions)}`);
  assert((diagnostics.coachApiFailures || []).length === 0,
    `${label} received failing coach API responses: ${JSON.stringify(diagnostics.coachApiFailures)}`);
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function endActiveSessions() {
  const response = await fetch(`${apiBaseUrl}/coach/play/active`);
  if (!response.ok) {
    throw new Error(`Could not read active staging sessions: HTTP ${response.status}`);
  }
  const payload = await response.json();
  for (const session of payload.active_sessions || []) {
    const ended = await fetch(`${apiBaseUrl}/coach/play/end`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: session.session_id,
        reason: "staging_harness_cleanup",
      }),
    });
    if (!ended.ok) {
      throw new Error(
        `Could not end staging session ${session.session_id}: HTTP ${ended.status}`,
      );
    }
  }
}

async function setupSnapshot(client) {
  return evaluate(client, `(() => ({
    innerWidth: window.innerWidth,
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    modeCount: document.querySelectorAll('[role="radiogroup"] [role="radio"]').length,
    coachChecked: document.querySelector('[data-testid="unified-mode-coach"]')?.getAttribute('aria-checked'),
    playChecked: document.querySelector('[data-testid="unified-mode-play"]')?.getAttribute('aria-checked'),
    text: document.body.innerText,
  }))()`);
}

async function validateSetup(client, viewportName) {
  const initial = await setupSnapshot(client);
  assert(initial.scrollWidth <= initial.innerWidth + 1,
    `${viewportName} horizontally overflows: ${initial.scrollWidth}px > ${initial.innerWidth}px`);
  assert(initial.bodyScrollWidth <= initial.innerWidth + 1,
    `${viewportName} body horizontally overflows: ${initial.bodyScrollWidth}px > ${initial.innerWidth}px`);
  assert(initial.modeCount === 2,
    `${viewportName} must show exactly two modes; found ${initial.modeCount}. `
      + `Visible text: ${initial.text.slice(0, 800)}`);
  assert(initial.coachChecked === "true", `${viewportName} must default to Coach mode`);
  assert(initial.text.includes("White · 15+10"), `${viewportName} lost the 15+10 White default`);
  assert(initial.text.includes("Play with Coach") && initial.text.includes("Play a Game"),
    `${viewportName} mode labels are missing`);
  if (expectedFocus) {
    assert(initial.text.includes(expectedFocus),
      `${viewportName} setup lost the expected personal focus: ${expectedFocus}`);
  }
  if (expectedInstruction) {
    assert(initial.text.includes(expectedInstruction),
      `${viewportName} setup lost the expected personal instruction`);
  }

  await clickSelector(client, "[data-testid='unified-work-choice-toggle']");
  await waitFor(client,
    `(() => {
      const choices = document.querySelector('[data-testid="unified-work-choices"]');
      if (!choices) return false;
      return choices.querySelectorAll('button').length > 0
        || choices.innerText.includes('need a few games');
    })()`,
    `${viewportName} work choices`);
  const workChoiceState = await evaluate(client, `(() => ({
    count: document.querySelectorAll('[data-testid="unified-work-choices"] button').length,
    text: document.querySelector('[data-testid="unified-work-choices"]')?.innerText || '',
  }))()`);
  assert(workChoiceState.count <= 3, `${viewportName} exposed more than three work choices`);
  assert(workChoiceState.count > 0 || workChoiceState.text.includes("need a few games"),
    `${viewportName} work-choice empty state is missing`);

  await clickSelector(client, "[data-testid='unified-settings-toggle']");
  await waitFor(client,
    "document.querySelector('[data-testid=\"unified-settings\"]')",
    `${viewportName} settings`);
  const settingsText = await evaluate(
    client,
    "document.querySelector('[data-testid=\"unified-settings\"]')?.innerText || ''",
  );
  assert(settingsText.includes("White") && settingsText.includes("Black"),
    `${viewportName} side settings are incomplete`);
}

let browser;
try {
  await pollJson(`http://127.0.0.1:${port}/json/version`);
  await endActiveSessions();

  const mobile = await openPage({ width: 390, height: 844, mobile: true });
  await validateSetup(mobile, "mobile");
  const mobileSetup = await capture(
    mobile,
    "pwc-unified-staging-setup-mobile.png",
  );
  await clickSelector(mobile, "[data-testid='unified-start-game']");
  await waitFor(mobile,
    "document.querySelector('[data-testid=\"unified-coach-panel\"]')",
    "mobile unified live coach panel",
    45_000);
  const mobileLiveState = await evaluate(mobile, `(() => {
    const board = document.querySelector('[data-testid="coach-play-board-stage"]');
    const rect = board?.getBoundingClientRect();
    const sheetRect = document.querySelector('.pwc-coach-col')?.getBoundingClientRect();
    const shell = document.querySelector('.pwc-shell');
    const sheet = document.querySelector('.pwc-coach-col');
    const navRect = document.querySelector('.experience-mobile-nav')?.getBoundingClientRect();
    return {
      innerHeight: window.innerHeight,
      visualHeight: window.visualViewport?.height || 0,
      scrollWidth: document.documentElement.scrollWidth,
      boardWidth: rect?.width || 0,
      panelCount: document.querySelectorAll('[data-testid="unified-coach-panel"]').length,
      sheetBottom: sheetRect?.bottom || 0,
      sheetHeight: sheetRect?.height || 0,
      sheetCssBottom: sheet ? getComputedStyle(sheet).bottom : '',
      shellRect: shell ? { top: shell.getBoundingClientRect().top, bottom: shell.getBoundingClientRect().bottom } : null,
      shellTransform: shell ? getComputedStyle(shell).transform : '',
      shellWillChange: shell ? getComputedStyle(shell).willChange : '',
      navTop: navRect?.top || 0,
    };
  })()`);
  assert(mobileLiveState.scrollWidth <= 391,
    `Mobile live game horizontally overflows: ${mobileLiveState.scrollWidth}px`);
  assert(mobileLiveState.boardWidth >= 280 && mobileLiveState.boardWidth <= 390,
    `Mobile board width is not usable: ${mobileLiveState.boardWidth}px`);
  assert(mobileLiveState.panelCount === 1, "Mobile must have one coach panel");
  assert(mobileLiveState.sheetBottom <= mobileLiveState.navTop,
    `Mobile coach sheet is hidden behind navigation: ${JSON.stringify(mobileLiveState)}`);
  assert(mobileLiveState.sheetHeight >= 100,
    `Mobile coach preview is too small: ${mobileLiveState.sheetHeight}px`);
  await delay(500);
  const mobileLive = await capture(
    mobile,
    "pwc-unified-staging-live-coach-mobile.png",
  );
  await clickButton(mobile, "Resign");
  await waitFor(mobile,
    "document.body.innerText.toLowerCase().includes('one clear takeaway')",
    "mobile unified postgame story",
    45_000);
  const mobilePostgameState = await evaluate(mobile, `(() => ({
    boardNewGameCount: document.querySelectorAll('[data-testid="new-game-btn"]').length,
    panelButtonCount: document.querySelectorAll('[data-testid="unified-coach-panel"] button').length,
    scrollWidth: document.documentElement.scrollWidth,
    sheetBottom: document.querySelector('.pwc-coach-col')?.getBoundingClientRect().bottom || 0,
    navTop: document.querySelector('.experience-mobile-nav')?.getBoundingClientRect().top || 0,
  }))()`);
  assert(mobilePostgameState.boardNewGameCount === 0,
    "Mobile unified postgame leaked the board-level New Game action");
  assert(mobilePostgameState.panelButtonCount === 1,
    `Mobile unified postgame must have one action; found ${mobilePostgameState.panelButtonCount}`);
  assert(mobilePostgameState.scrollWidth <= 391,
    `Mobile postgame horizontally overflows: ${mobilePostgameState.scrollWidth}px`);
  assert(mobilePostgameState.sheetBottom <= mobilePostgameState.navTop,
    `Mobile postgame action is hidden behind navigation: ${JSON.stringify(mobilePostgameState)}`);
  const mobilePostgameText = await evaluate(mobile, "document.body.innerText");
  assert(!mobilePostgameText.includes("Better luck next time"),
    "Unified mobile postgame leaked the generic resignation toast");
  const mobilePostgame = await capture(
    mobile,
    "pwc-unified-staging-postgame-mobile.png",
  );
  assertCleanBrowser(mobile, "Mobile Coach journey");
  mobile.close();

  const desktop = await openPage({ width: 1440, height: 1000 });
  await validateSetup(desktop, "desktop");
  const desktopSetup = await capture(
    desktop,
    "pwc-unified-staging-setup-desktop.png",
  );

  await clickSelector(desktop, "[data-testid='unified-mode-play']");
  const playState = await setupSnapshot(desktop);
  assert(playState.playChecked === "true", "Play mode did not become active");
  assert(playState.text.includes("Start the Game"), "Play mode start label is wrong");

  await clickSelector(desktop, "[data-testid='unified-mode-coach']");
  await clickSelector(desktop, "[data-testid='unified-start-game']");
  await waitFor(desktop,
    "document.querySelector('[data-testid=\"unified-coach-panel\"]')",
    "unified live coach panel",
    45_000);
  const liveText = await evaluate(desktop, "document.body.innerText");
  assert(liveText.includes("Your turn. Take your time."),
    "Coach mode did not reach the quiet live state");
  if (expectedFocus) {
    assert(liveText.includes(expectedFocus),
      "Coach mode did not carry the personal focus into the live panel");
  }
  if (expectedInstruction) {
    assert(liveText.includes(expectedInstruction),
      "Coach mode did not carry the personal instruction into the live panel");
  }
  for (const legacyText of ["Rate this move", "Predict their move", "escape squares"]) {
    assert(!liveText.toLowerCase().includes(legacyText.toLowerCase()),
      `Legacy live UI leaked into unified mode: ${legacyText}`);
  }

  await playE4(desktop);
  await waitForCompletedPlyPair(desktop, "Coach-mode e4 and engine reply");

  await clickSelector(desktop, "[data-testid='unified-ask-coach']");
  await waitFor(desktop,
    "[...document.querySelectorAll('button')].some((button) => button.textContent.trim() === 'Explain their move')",
    "explain-last-move help action");
  await clickButton(desktop, "Explain their move");
  await waitFor(desktop,
    "document.body.innerText.toLowerCase().includes('coach’s answer')",
    "bounded coach answer",
    20_000);
  const liveCoach = await capture(
    desktop,
    "pwc-unified-staging-live-coach-desktop.png",
  );

  await clickButton(desktop, "Got it");
  await clickButton(desktop, "Resign");
  await waitFor(desktop,
    "document.body.innerText.toLowerCase().includes('one clear takeaway')",
    "unified postgame story",
    45_000);
  const postgameState = await evaluate(desktop, `(() => ({
    board: (() => {
      const element = document.querySelector('[data-testid="coach-play-board-stage"]');
      if (!element) return null;
      const rect = element.getBoundingClientRect();
      return { width: rect.width, height: rect.height };
    })(),
    boardNewGameCount: document.querySelectorAll('[data-testid="new-game-btn"]').length,
    panelButtons: [...document.querySelectorAll('[data-testid="unified-coach-panel"] button')]
      .map((button) => button.textContent.trim()),
  }))()`);
  assert(postgameState.board?.width > 300 && postgameState.board?.height > 300,
    `Postgame board context disappeared: ${JSON.stringify(postgameState.board)}`);
  assert(postgameState.boardNewGameCount === 0,
    "Unified postgame leaked the board-level New Game action");
  assert(postgameState.panelButtons.length === 1,
    `Unified postgame must have one next action; found ${postgameState.panelButtons.join(", ")}`);
  const desktopPostgameText = await evaluate(desktop, "document.body.innerText");
  assert(!desktopPostgameText.includes("Better luck next time"),
    "Unified desktop postgame leaked the generic resignation toast");
  if (expectedFocus) {
    assert(desktopPostgameText.includes(expectedFocus),
      "Unified postgame did not carry forward the personal focus");
  }
  const postgame = await capture(
    desktop,
    "pwc-unified-staging-postgame-desktop.png",
  );
  assertCleanBrowser(desktop, "Desktop Coach journey");
  desktop.close();

  const desktopPlay = await openPage({ width: 1440, height: 1000 });
  await clickSelector(desktopPlay, "[data-testid='unified-mode-play']");
  await clickSelector(desktopPlay, "[data-testid='unified-start-game']");
  await waitFor(desktopPlay,
    "document.body.innerText.includes('Your game. No hints.')",
    "strict-silence Play mode",
    45_000);
  const playLiveState = await evaluate(desktopPlay, `(() => ({
    askCoachCount: document.querySelectorAll('[data-testid="unified-ask-coach"]').length,
    text: document.querySelector('[data-testid="unified-coach-panel"]')?.innerText || '',
  }))()`);
  assert(playLiveState.askCoachCount === 0, "Play mode exposed Ask coach");
  assert(!playLiveState.text.toLowerCase().includes("coach’s note"),
    "Play mode exposed a coaching note");
  await playE4(desktopPlay);
  await waitForCompletedPlyPair(desktopPlay, "Play-mode e4 and engine reply");
  const playAfterMove = await evaluate(
    desktopPlay,
    "document.querySelector('[data-testid=\"unified-coach-panel\"]')?.innerText || ''",
  );
  assert(playAfterMove.includes("Your game. No hints."),
    `Play mode changed its silence contract after a move: ${playAfterMove}`);
  const livePlay = await capture(
    desktopPlay,
    "pwc-unified-staging-live-play-desktop.png",
  );
  await clickButton(desktopPlay, "Resign");
  await waitFor(desktopPlay,
    "document.body.innerText.toLowerCase().includes('one clear takeaway')",
    "Play-mode postgame story",
    45_000);
  const playPostgameButtons = await evaluate(
    desktopPlay,
    "document.querySelectorAll('[data-testid=\"unified-coach-panel\"] button').length",
  );
  assert(playPostgameButtons === 1,
    `Play-mode postgame must have one next action; found ${playPostgameButtons}`);
  assertCleanBrowser(desktopPlay, "Desktop Play journey");
  desktopPlay.close();

  browser = {
    status: "pass",
    mobile: {
      viewport: "390x844",
      setupScreenshot: mobileSetup,
      liveCoachScreenshot: mobileLive,
      postgameScreenshot: mobilePostgame,
    },
    desktop: {
      viewport: "1440x1000",
      setupScreenshot: desktopSetup,
      liveCoachScreenshot: liveCoach,
      postgameScreenshot: postgame,
      livePlayScreenshot: livePlay,
    },
  };
  console.log(JSON.stringify(browser, null, 2));
} finally {
  chrome.kill();
  try {
    rmSync(profileDir, { recursive: true, force: true });
  } catch (_error) {
    // Chrome can briefly retain a profile file on Windows; it is temp-only.
  }
}
