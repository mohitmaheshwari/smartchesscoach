import fs from "fs";
import path from "path";


describe("PostHog privacy configuration", () => {
  const html = fs.readFileSync(path.join(process.cwd(), "public", "index.html"), "utf8");

  test("uses explicit events and disables session replay", () => {
    expect(html).toMatch(/autocapture:\s*false/);
    expect(html).toMatch(/capture_pageview:\s*false/);
    expect(html).toMatch(/capture_pageleave:\s*false/);
    expect(html).toMatch(/disable_session_recording:\s*true/);
  });

  test("does not configure a session recording payload", () => {
    expect(html).not.toMatch(/session_recording\s*:\s*\{/);
    expect(html).not.toMatch(/recordCrossOriginIframes|capturePerformance/);
  });

  test("strips query strings and fragments from automatic URL properties", () => {
    expect(html).toMatch(/before_send:\s*function/);
    expect(html).toContain('"$current_url"');
    expect(html).toContain('"$initial_current_url"');
    expect(html).toMatch(/parsed\.origin\s*\+\s*parsed\.pathname/);
  });
});
