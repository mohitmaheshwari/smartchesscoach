/**
 * The client half of the coaching-room presentation gate.
 *
 * Relative imports on purpose: this project has no jest moduleNameMapper, so
 * "@/..." does not resolve under the local runner.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";
import {
  COACHING_ROOM_CLASS,
  CoachingRoomProvider,
  isCoachingRoomEnabled,
  useCoachingRoom,
} from "./coachingRoom";

const render = (element) => {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  act(() => root.render(element));
  return {
    host,
    unmount: () => act(() => root.unmount()),
  };
};

afterEach(() => {
  document.documentElement.classList.remove(COACHING_ROOM_CLASS);
});

describe("isCoachingRoomEnabled", () => {
  it("is off when the server says nothing", () => {
    expect(isCoachingRoomEnabled(null)).toBe(false);
    expect(isCoachingRoomEnabled(undefined)).toBe(false);
    expect(isCoachingRoomEnabled({})).toBe(false);
  });

  it("is off unless the server said exactly true", () => {
    expect(isCoachingRoomEnabled({ coaching_room_v2: false })).toBe(false);
    // A truthy string must not be mistaken for enrolment.
    expect(isCoachingRoomEnabled({ coaching_room_v2: "true" })).toBe(false);
  });

  it("is on when the server enrolled this account", () => {
    expect(isCoachingRoomEnabled({ coaching_room_v2: true })).toBe(true);
  });
});

function Probe() {
  return <span data-testid="probe">{useCoachingRoom() ? "on" : "off"}</span>;
}

describe("CoachingRoomProvider", () => {
  it("leaves the document untouched for an account that is not enrolled", () => {
    const { host, unmount } = render(
      <CoachingRoomProvider user={{ coaching_room_v2: false }}>
        <Probe />
      </CoachingRoomProvider>
    );
    expect(document.documentElement.classList.contains(COACHING_ROOM_CLASS)).toBe(false);
    expect(host.textContent).toBe("off");
    unmount();
  });

  it("marks the document and the tree for an enrolled account", () => {
    const { host, unmount } = render(
      <CoachingRoomProvider user={{ coaching_room_v2: true }}>
        <Probe />
      </CoachingRoomProvider>
    );
    expect(document.documentElement.classList.contains(COACHING_ROOM_CLASS)).toBe(true);
    expect(host.textContent).toBe("on");
    unmount();
  });

  it("removes the class on unmount, so signing out cannot leave it applied", () => {
    const { unmount } = render(
      <CoachingRoomProvider user={{ coaching_room_v2: true }}>
        <Probe />
      </CoachingRoomProvider>
    );
    expect(document.documentElement.classList.contains(COACHING_ROOM_CLASS)).toBe(true);
    unmount();
    expect(document.documentElement.classList.contains(COACHING_ROOM_CLASS)).toBe(false);
  });

  it("defaults to off with no provider at all", () => {
    const { host, unmount } = render(<Probe />);
    expect(host.textContent).toBe("off");
    unmount();
  });
});
