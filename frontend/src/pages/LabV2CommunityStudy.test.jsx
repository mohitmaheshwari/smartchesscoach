import React, { act } from "react";
import { createRoot } from "react-dom/client";

import LabV2 from "./LabV2";

const mockNavigate = jest.fn();
const mockInvalidate = jest.fn();
jest.mock("@/lib/personalCurriculum", () => ({ invalidatePersonalCurriculum: () => mockInvalidate() }));

jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
  useParams: () => ({ gameId: "study-1" }),
  useSearchParams: () => [
    new URLSearchParams("community=1&prescription=prescription-1"),
    jest.fn(),
  ],
}), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("@/lib/analytics", () => ({
  ANALYTICS_EVENTS: { FUNNEL_REVIEW_OPENED: "review_opened" },
  track: jest.fn(),
}), { virtual: true });
jest.mock("@/components/Layout", () => ({ children }) => <div>{children}</div>, { virtual: true });
jest.mock("@/components/LichessBoard", () => () => null, { virtual: true });
jest.mock("@/components/FeedbackModal", () => () => null, { virtual: true });
jest.mock("@/components/GameDecryptionV5", () => ({
  communityStudy,
  communityPrescriptionId,
  onCommunityComplete,
}) => (
  <div>
    <div
      data-testid="community-decryption"
      data-study-id={communityStudy?.study_id || ""}
      data-prescription-id={communityPrescriptionId}
    />
    <button data-testid="finish-community" onClick={onCommunityComplete}>
      Finish
    </button>
  </div>
), { virtual: true });
jest.mock("@/components/Lab/CoachInsightPanel", () => () => null, { virtual: true });
jest.mock("@/components/coach/CoachSession", () => () => null, { virtual: true });
jest.mock("@/components/Lab/CoachAction", () => () => null, { virtual: true });
jest.mock("@/components/coach/CoachMovePanel", () => () => null, { virtual: true });
jest.mock("@/components/experience/CanonicalReviewFocus", () => () => null, { virtual: true });
jest.mock("@/components/shared/FlagMoveDialog", () => ({ InlineFlag: () => null }), { virtual: true });
jest.mock("@/hooks/usePuzzleSubmissionIdentity", () => () => ["submission-1", jest.fn()], { virtual: true });
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock("framer-motion", () => ({
  motion: new Proxy({}, { get: () => ({ children, ...props }) => <div {...props}>{children}</div> }),
}));

const study = {
  study_id: "study-1",
  game: { initial_fen: "8/8/8/8/8/8/4K3/6k1 w - - 0 1", moves_uci: ["e2e3"] },
  chapters: [{
    event_id: "event-1",
    position: {
      fen: "8/8/8/8/8/8/4K3/6k1 w - - 0 1",
      side_to_move: "white",
    },
  }],
  progress: {},
  hints: {},
  reveals: {},
};

describe("LabV2 community study loading", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    mockNavigate.mockReset();
    mockInvalidate.mockReset();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    delete global.fetch;
  });

  test("loads only the owned answer-hidden study and mounts canonical review", async () => {
    global.fetch = jest.fn((url) => {
      if (url.endsWith(
        "/game-review/recommendation/prescription-1/study",
      )) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(study),
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    await act(async () => root.render(
      <LabV2 user={{ user_id: "learner-1" }} />,
    ));
    await act(async () => {
      for (let index = 0; index < 16; index += 1) await Promise.resolve();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(container.innerHTML).toContain("community-decryption");
    const mounted = container.querySelector("[data-testid='community-decryption']");
    expect(mounted).not.toBeNull();
    expect(mounted.dataset.studyId).toBe("study-1");
    expect(mounted.dataset.prescriptionId).toBe("prescription-1");
    expect(container.textContent).toContain("A player near your level");
    expect(container.querySelector("[data-testid='view-mode-tabs']")).toBeNull();
  });

  test("completion keeps the learner on the coach-authored next action", async () => {
    global.fetch = jest.fn((url, options = {}) => {
      if (url.endsWith(
        "/game-review/recommendation/prescription-1/study",
      )) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(study),
        });
      }
      if (url.endsWith("/lab/study-1/complete-review")) {
        expect(options.method).toBe("POST");
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            summary: {
              lesson_label: "Guided game study",
              lesson: "You replayed both key decisions.",
              takeaway: "Your own games will show whether this held.",
            },
            next_game: null,
            next_action: {
              kind: "coach_action",
              label: "Play with Coach",
              href: "/play-with-coach",
            },
          }),
        });
      }
      if (url.endsWith(
        "/game-review/recommendation/prescription-1/next-action",
      )) {
        expect(options.method).toBe("POST");
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            kind: "coach_action",
            label: "Play with Coach",
            href: "/play-with-coach",
          }),
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    await act(async () => root.render(
      <LabV2 user={{ user_id: "learner-1" }} />,
    ));
    await act(async () => {
      for (let index = 0; index < 12; index += 1) await Promise.resolve();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    await act(async () => {
      container.querySelector("[data-testid='finish-community']").click();
      for (let index = 0; index < 12; index += 1) await Promise.resolve();
    });
    expect(container.textContent).toContain("Play with Coach");
    expect(mockInvalidate).toHaveBeenCalledTimes(1);

    await act(async () => {
      container.querySelector("[data-testid='review-next-game-btn']").click();
      for (let index = 0; index < 12; index += 1) await Promise.resolve();
    });
    expect(mockNavigate).toHaveBeenCalledWith("/play-with-coach");
  });

  test("failed completion keeps the review open and does not invalidate its plan", async () => {
    global.fetch = jest.fn((url) => Promise.resolve({
      ok: url.endsWith('/study'),
      json: async () => url.endsWith('/study') ? study : { detail: 'Could not save review' },
    }));
    await act(async () => root.render(<LabV2 user={{ user_id: 'learner-1' }} />));
    await act(async () => {
      for (let index = 0; index < 16; index += 1) await Promise.resolve();
    });
    await act(async () => container.querySelector('[data-testid="finish-community"]').click());
    expect(container.querySelector('[data-testid="review-complete-overlay"]')).toBeNull();
    expect(container.querySelector('[data-testid="community-decryption"]')).toBeTruthy();
    expect(mockInvalidate).not.toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  test("failed community studies return to Game Review", async () => {
    global.fetch = jest.fn(() => Promise.resolve({
      ok: false,
      json: () => Promise.resolve({ detail: "This study was withdrawn." }),
    }));

    await act(async () => root.render(
      <LabV2 user={{ user_id: "learner-1" }} />,
    ));
    await act(async () => {
      for (let index = 0; index < 12; index += 1) await Promise.resolve();
    });

    expect(mockNavigate).toHaveBeenCalledWith("/games");
    expect(mockNavigate).not.toHaveBeenCalledWith("/lab");
  });
});
