/**
 * The academy set-up flow.
 *
 * Two things here are worth guarding beyond "it renders":
 *
 *  - the landing page's parent-or-coach choice must REACH this page. Until
 *    2026-11-27 both landing buttons sent the same URL and the answer went to
 *    track() and nowhere else, so /academy had to show both set-up cards to
 *    everyone with the parent one on top.
 *  - a child cannot be added without a parent's WhatsApp number. That is the
 *    server's rule (routes/academy.py:460), so the form must hold the line
 *    rather than let the server say no after the fact.
 */

import { act } from "react";
import { createRoot } from "react-dom/client";
import AcademyStart from "./AcademyStart";

const mockNavigate = jest.fn();

jest.mock("react-router-dom", () => ({ useNavigate: () => mockNavigate }), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });

const setUrl = (search) => {
  window.history.replaceState({}, "", `/academy/start${search}`);
};

describe("academy set-up", () => {
  let container;
  let root;
  let posts;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    mockNavigate.mockReset();
    window.sessionStorage.clear();
    setUrl("");
    posts = [];

    global.fetch = jest.fn((url, options) => {
      const path = String(url);
      const body = options && options.body ? JSON.parse(options.body) : null;
      if (options && options.method === "POST") posts.push({ path, body });
      const json = (data) =>
        Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(data) });

      if (path.includes("/auth/me")) return json({ user_id: "u1", name: "Priya Nair" });
      if (/\/api\/academy$/.test(path)) {
        return json(
          body && body.kind === "family"
            ? { academy_id: "acad_1", name: "Priya Nair's family", batch_id: "batch_home" }
            : { academy_id: "acad_1", name: body.name, city: body.city }
        );
      }
      if (path.includes("/batches")) return json({ batch_id: "batch_1", name: body.name });
      if (path.includes("/students")) {
        return json({
          student_id: `kid_${posts.length}`,
          links: { consent: "https://chessguru.ai/consent/tok1" },
          whatsapp: "https://wa.me/919876543210?text=Hello",
        });
      }
      return json({});
    });

    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  const render = () => act(async () => { root.render(<AcademyStart />); });
  const el = (id) => container.querySelector(`[data-testid="${id}"]`);
  const byId = (id) => container.querySelector(`#${id}`);
  const click = (id) =>
    act(async () => {
      el(id).dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
  const type = (id, value) =>
    act(async () => {
      const input = byId(id);
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, "value"
      ).set;
      setter.call(input, value);
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
  const submit = (id) =>
    act(async () => {
      el(id).closest("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });

  // --- who arrived, and how we know ------------------------------------

  test("a coach from the landing page is never asked who they are", async () => {
    setUrl("?who=coach");
    await render();

    expect(el("start-who-coach")).toBeNull();
    expect(el("start-step").textContent).toBe("Step 1 of 3");
    expect(container.querySelector("h1").textContent).toMatch(/academy called/i);
  });

  test("a parent from the landing page gets one step, not three", async () => {
    setUrl("?who=parent");
    await render();

    expect(el("start-step").textContent).toBe("Step 1 of 1");
    expect(byId("start-child-name")).not.toBeNull();
  });

  test("the session remembers, for when the query string is lost", async () => {
    // A redirect through sign-up is exactly where a query string goes missing.
    window.sessionStorage.setItem("chessguru.academy_who", "parent");
    setUrl("");
    await render();

    expect(el("start-step").textContent).toBe("Step 1 of 1");
  });

  test("asks only when genuinely nobody said", async () => {
    await render();

    expect(el("start-who-coach")).not.toBeNull();
    expect(el("start-who-parent")).not.toBeNull();
    expect(el("start-step")).toBeNull();
  });

  test("back from the first step returns to that question", async () => {
    setUrl("?who=coach");
    await render();

    await click("start-back");

    expect(el("start-who-coach")).not.toBeNull();
  });

  // --- the coach's three steps -----------------------------------------

  const walkCoachToChildren = async () => {
    setUrl("?who=coach");
    await render();
    await type("start-academy-name", "Knight School Pune");
    await type("start-academy-city", "Pune");
    await submit("start-academy-next");
    await type("start-batch-name", "Saturday batch");
    await submit("start-batch-next");
  };

  test("creates the academy, then the batch, then the children, in that order", async () => {
    await walkCoachToChildren();
    await type("start-kid-name-0", "Aarav");
    await type("start-kid-phone-0", "9876543210");
    await submit("start-finish-coach");

    expect(posts.map((p) => p.path.replace("https://api.test/api", ""))).toEqual([
      "/academy",
      "/academy/acad_1/batches",
      "/academy/batch/batch_1/students",
    ]);
    expect(posts[0].body).toEqual({ name: "Knight School Pune", city: "Pune" });
    expect(posts[1].body.name).toBe("Saturday batch");
    expect(posts[2].body).toEqual({ display_name: "Aarav", parent_phone: "9876543210" });
  });

  test("offers their own name as the coach rather than making them type it", async () => {
    setUrl("?who=coach");
    await render();
    await type("start-academy-name", "Knight School Pune");
    await submit("start-academy-next");

    expect(byId("start-batch-coach").value).toBe("Priya Nair");
  });

  test("will not add a child without a parent's number", async () => {
    // The server refuses it (routes/academy.py:460). Finding that out after
    // pressing Finish is the rough version.
    await walkCoachToChildren();
    await type("start-kid-name-0", "Aarav");

    expect(el("start-finish-coach").disabled).toBe(true);

    await type("start-kid-phone-0", "9876543210");
    expect(el("start-finish-coach").disabled).toBe(false);
  });

  test("adds every child that is filled in, and ignores a half-filled row", async () => {
    await walkCoachToChildren();
    await type("start-kid-name-0", "Aarav");
    await type("start-kid-phone-0", "9876543210");
    await click("start-add-kid");
    await type("start-kid-name-1", "Diya");
    await type("start-kid-phone-1", "9876500000");
    await click("start-add-kid");
    await type("start-kid-name-2", "Half");          // no number
    await submit("start-finish-coach");

    const students = posts.filter((p) => p.path.includes("/students"));
    expect(students).toHaveLength(2);
    expect(students.map((p) => p.body.display_name)).toEqual(["Aarav", "Diya"]);
  });

  test("lets a coach finish with nobody added rather than trapping them", async () => {
    await walkCoachToChildren();

    await click("start-kids-skip");

    expect(posts.filter((p) => p.path.includes("/students"))).toHaveLength(0);
    expect(container.querySelector("h1").textContent).toMatch(/is set up/i);
  });

  // --- the finish screen, which is the point ---------------------------

  test("ends on the parent's agreement, using the server's own link", async () => {
    // Production on 2026-11-27: two children, zero parents who ever agreed.
    // This screen exists because that is where the product stops.
    await walkCoachToChildren();
    await type("start-kid-name-0", "Aarav");
    await type("start-kid-phone-0", "9876543210");
    await submit("start-finish-coach");

    expect(el("start-parent-links")).not.toBeNull();
    // Not a URL we assembled: the one the server returned, with the consent
    // message already written into it.
    expect(el("start-whatsapp").getAttribute("href")).toBe(
      "https://wa.me/919876543210?text=Hello"
    );
    expect(el("start-copy")).not.toBeNull();
  });

  test("a parent is two fields and done", async () => {
    setUrl("?who=parent");
    await render();
    await type("start-child-name", "Aarav");
    await type("start-child-phone", "9876543210");
    await submit("start-finish-parent");

    // kind:"family" makes the academy and its one Home batch together.
    expect(posts[0].body).toEqual({ kind: "family" });
    expect(posts[1].path).toContain("/academy/batch/batch_home/students");
    expect(el("start-parent-links")).not.toBeNull();
  });

  // --- the things that made the old page rough -------------------------

  test("every input has a real label, not just a placeholder", async () => {
    // All five inputs on /academy were placeholder-only, so the label
    // vanished the moment anyone typed.
    await walkCoachToChildren();

    for (const input of container.querySelectorAll("input")) {
      const labelled =
        input.closest("label") ||
        (input.id && container.querySelector(`label[for="${input.id}"]`)) ||
        input.getAttribute("aria-label");
      expect(labelled).toBeTruthy();
    }
  });

  test("every control clears the 44px floor", async () => {
    // /academy had five controls at 40-42px.
    await walkCoachToChildren();

    for (const control of container.querySelectorAll("button, input, a[href]")) {
      const found = /min-h-\[(\d+)px\]/.exec(control.className);
      expect(found).not.toBeNull();
      expect(Number(found[1])).toBeGreaterThanOrEqual(44);
    }
  });

  test("says what went wrong instead of silently doing nothing", async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: false,
        status: 400,
        json: () => Promise.resolve({ detail: "Give the academy a name." }),
      })
    );
    setUrl("?who=coach");
    await render();
    await type("start-academy-name", "Knight School Pune");
    await submit("start-academy-next");

    expect(el("start-error").textContent).toMatch(/Give the academy a name/);
    // and stays on the step it failed on
    expect(el("start-step").textContent).toBe("Step 1 of 3");
  });
});
