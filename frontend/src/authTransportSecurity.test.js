import fs from "fs";
import path from "path";

const source = (relativePath) => fs.readFileSync(path.join(__dirname, relativePath), "utf8");

describe("auth transport security source contract", () => {
  const app = source("App.js");
  const login = source("pages/Login.jsx");
  const landing = source("pages/Landing.jsx");
  const recommendation = source("components/NextRecommendation.jsx");
  const mastery = source("components/MistakeMastery.jsx");
  const layout = source("components/Layout.jsx");
  const settings = source("pages/Settings.jsx");

  test("web route protection never consumes bearer credentials from URLs", () => {
    expect(app).not.toContain("new URLSearchParams(location.search).get('token')");
    expect(app).toContain("params.delete('token')");
    expect(app).toContain("params.delete('session_token')");
  });

  test("stored bearer auth is restricted to the native runtime", () => {
    expect(app).toMatch(/Capacitor\.isNativePlatform\(\)[\s\S]{0,120}localStorage\.getItem\('session_token'\)/);
    expect(app).toContain("localStorage.removeItem('session_token')");
    expect(app).toContain("localStorage.removeItem('authToken')");
  });

  test("native deep links still exchange an explicit mobile bearer", () => {
    expect(app).toContain("localStorage.setItem('session_token', token)");
    expect(app).toContain("Authorization: `Bearer ${token}`");
  });

  test.each([
    ["Login", login],
    ["Landing", landing],
  ])("%s starts native OAuth at the backend and sends web cookies", (_name, file) => {
    expect(file).toContain("&platform=mobile&flow=redirect");
    expect(file).toMatch(/fetch\(startUrl, \{ credentials: ["']include["'] \}\)/);
  });

  test("legacy browser components use cookies instead of localStorage bearer tokens", () => {
    expect(recommendation).not.toContain("authToken");
    expect(recommendation).not.toContain("Authorization");
    expect(recommendation).toContain("credentials: 'include'");
    expect(mastery).not.toContain("Authorization");
    expect(mastery).toContain('credentials: "include"');
  });

  test.each([
    ["Layout", layout],
    ["Settings", settings],
  ])("%s revokes and clears native bearer auth on logout", (_name, file) => {
    expect(file).toContain("Capacitor.isNativePlatform()");
    expect(file).toContain("Authorization: `Bearer ${nativeToken}`");
    expect(file).toMatch(/removeItem\(["']session_token["']\)/);
    expect(file).toMatch(/removeItem\(["']authToken["']\)/);
  });
});
