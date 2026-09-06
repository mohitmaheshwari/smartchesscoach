import fs from "fs";
import path from "path";


const source = (relativePath) =>
  fs.readFileSync(path.join(process.cwd(), "src", relativePath), "utf8");


describe("analytics identity lifecycle wiring", () => {
  test("configures context only after the authenticated user resolves", () => {
    const app = source("App.js");
    expect(app).toMatch(/configureAnalyticsContext\(userData,\s*\{ demoMode: demoBypass \}\)/);
    expect(app).toMatch(/catch \(error\) \{[\s\S]*resetAnalyticsContext\(\)/);
  });

  test.each(["components/Layout.jsx", "pages/Settings.jsx"])(
    "%s resets analytics identity on logout",
    (relativePath) => {
      const file = source(relativePath);
      expect(file).toMatch(/auth\/logout[\s\S]*resetAnalyticsContext\(\)/);
    }
  );
});
