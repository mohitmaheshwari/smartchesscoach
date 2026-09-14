import React, { act } from "react";
import { createRoot } from "react-dom/client";

import CoachPlaySetup from "./CoachPlaySetup";

jest.mock("react-router-dom", () => ({
  useNavigate: () => jest.fn(),
}), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("@/components/Layout", () => ({ children }) => <div>{children}</div>, { virtual: true });
jest.mock("@/components/coach/UnifiedCoachPlaySetup", () => () => (
  <div data-testid="unified-setup-stub" />
), { virtual: true });
jest.mock("@/components/curriculum/CurriculumStateStrip", () => () => null, { virtual: true });
jest.mock("@/components/streak", () => ({ PreGameStreakPopup: () => null }), { virtual: true });
jest.mock("@/lib/motion", () => ({ scaleIn: {}, staggerContainer: {}, staggerItem: {} }), { virtual: true });
jest.mock("framer-motion", () => ({
  motion: new Proxy({}, { get: () => ({ children, ...props }) => <div {...props}>{children}</div> }),
}));

const props = {
  user: { user_id: "student-1" },
  loading: false,
  practiceMode: false,
  practicePosition: null,
  selectedColor: "white",
  setSelectedColor: jest.fn(),
  selectedOpening: null,
  setSelectedOpening: jest.fn(),
  guidedMode: true,
  setGuidedMode: jest.fn(),
  gameMode: "coach",
  setGameMode: jest.fn(),
  evidenceMode: null,
  setEvidenceMode: jest.fn(),
  pastGamesHistory: [],
  playerIdentityData: null,
  startGame: jest.fn(),
  showPreGameStreakPopup: false,
  setShowPreGameStreakPopup: jest.fn(),
  actuallyStartGame: jest.fn(),
};

describe("CoachPlaySetup experience preload", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  test("does not flash the legacy setup while the experience is unresolved", () => {
    act(() => root.render(
      <CoachPlaySetup
        {...props}
        unifiedExperience={false}
        experienceLoading
        experienceConfig={null}
      />,
    ));

    expect(container.querySelector("[data-testid='coach-play-experience-loading']")).not.toBeNull();
    expect(container.querySelector("[data-testid='coach-play-setup']")).toBeNull();
  });

  test("hands ownership to the unified setup after rollout resolves", () => {
    act(() => root.render(
      <CoachPlaySetup
        {...props}
        unifiedExperience
        experienceLoading={false}
        experienceConfig={{ experience_version: "unified_v1" }}
      />,
    ));

    expect(container.querySelector("[data-testid='unified-setup-stub']")).not.toBeNull();
    expect(container.querySelector("[data-testid='coach-play-setup']")).toBeNull();
  });
});
