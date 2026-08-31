import { act } from "react";
import { createRoot } from "react-dom/client";
import CoachingPrescriptions from "../CoachingPrescriptions";

jest.mock("react-router-dom", () => ({
  useNavigate: () => jest.fn(),
}), { virtual: true });

const response = (body, ok = true) => Promise.resolve({
  ok,
  json: () => Promise.resolve(body),
});

const activePrescription = {
  prescription_id: "pres-1",
  plan_name: "Piece Safety Fundamentals",
  priority_order: 1,
  status: "active",
  issue_detected: "piece_safety",
  reasoning: "Your recent games contain repeated loose pieces.",
  baseline_metric: 2.5,
  current_metric: 1.8,
  improvement_pct: 28,
};

const recommendation = {
  recommended_plan_id: "plan-2",
  plan_name: "Tactical Vision Advanced",
  description: "Practise the patterns that recur in your games.",
  reasoning: "This has appeared in several recent games.",
  issue_severity: "medium",
  occurrence_count: 3,
  trend: "stable",
  alternatives: [],
};

describe("CoachingPrescriptions", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    global.fetch = jest.fn();
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    delete global.fetch;
    console.error.mockRestore();
  });

  const renderComponent = async () => {
    await act(async () => {
      root.render(<CoachingPrescriptions />);
    });
  };

  const settle = async () => {
    await act(async () => {
      for (let index = 0; index < 6; index += 1) {
        await Promise.resolve();
      }
    });
  };

  test("renders the loading state while both coaching requests are pending", async () => {
    global.fetch.mockReturnValue(new Promise(() => {}));

    await renderComponent();

    expect(container.textContent).toContain("Loading training plans");
  });

  test("renders the primary prescription and server-owned progress", async () => {
    global.fetch.mockImplementation((url) => {
      if (url.includes("current-prescriptions")) {
        return response({ prescriptions: [activePrescription] });
      }
      if (url.includes("next-prescription")) {
        return response({ recommendation: null });
      }
      if (url.includes("/progress")) {
        return response({
          improvement_pct: 28,
          current_metric: 1.8,
          games_analyzed_since_start: 4,
          puzzles_completed: 12,
          puzzle_accuracy: 85,
          auto_close_eligible: false,
        });
      }
      return response({});
    });

    await renderComponent();
    await settle();

    expect(container.textContent).toContain("Piece Safety Fundamentals");
    expect(container.textContent).toContain("piece_safety");
    expect(container.textContent).toContain("12 solved at 85% accuracy");
  });

  test("renders the next recommendation when there is no active plan", async () => {
    global.fetch.mockImplementation((url) => (
      url.includes("current-prescriptions")
        ? response({ prescriptions: [] })
        : response({ recommendation })
    ));

    await renderComponent();
    await settle();

    expect(container.textContent).toContain("Tactical Vision Advanced");
    expect(container.textContent).toContain("Why this training plan?");
  });

  test("renders the honest empty state", async () => {
    global.fetch.mockImplementation((url) => (
      url.includes("current-prescriptions")
        ? response({ prescriptions: [] })
        : response({ recommendation: null })
    ));

    await renderComponent();
    await settle();

    expect(container.textContent).toContain("No active training plans");
  });

  test("renders the current error contract when loading fails", async () => {
    global.fetch.mockRejectedValue(new Error("Network error"));

    await renderComponent();
    await settle();

    expect(container.textContent).toContain(
      "Failed to load coaching plans: Network error"
    );
  });
});
