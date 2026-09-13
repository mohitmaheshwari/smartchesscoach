import React, { act, useState } from "react";
import { createRoot } from "react-dom/client";

import UnifiedCoachPlaySetup from "./UnifiedCoachPlaySetup";


const mockNavigate = jest.fn();

jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("@/components/Layout", () => ({ children }) => <div>{children}</div>, { virtual: true });
jest.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }) => <button {...props}>{children}</button>,
}), { virtual: true });
jest.mock("lucide-react", () => new Proxy({}, {
  get: () => (props) => <span {...props} />,
}));


const allowedConfig = {
  experience_version: "unified_v1",
  access: {
    coach: { allowed: true },
    play: { allowed: true },
  },
  coaching_context: {
    primary_focus: {
      label: "Keeping your pieces safe",
      instruction_text: "Before moving a defender, check what it leaves loose.",
    },
  },
};


const Harness = ({ config = allowedConfig, startGame = jest.fn() }) => {
  const [gameMode, setGameMode] = useState("coach");
  const [selectedColor, setSelectedColor] = useState("white");
  const [selectedOpening, setSelectedOpening] = useState(null);
  return (
    <UnifiedCoachPlaySetup
      user={{ user_id: "student-1" }}
      loading={false}
      experienceLoading={false}
      experienceConfig={config}
      upgradeInfo={null}
      practiceMode={false}
      practicePosition={null}
      selectedColor={selectedColor}
      setSelectedColor={setSelectedColor}
      selectedOpening={selectedOpening}
      setSelectedOpening={setSelectedOpening}
      gameMode={gameMode}
      setGameMode={setGameMode}
      timeControl="15+10"
      startGame={startGame}
    />
  );
};


describe("UnifiedCoachPlaySetup", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    mockNavigate.mockReset();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    delete global.fetch;
  });

  test("shows one personal focus and exactly two player-facing modes", () => {
    act(() => root.render(<Harness />));

    expect(container.textContent).toContain("Keeping your pieces safe");
    expect(container.textContent).toContain(
      "Before moving a defender, check what it leaves loose."
    );
    expect(container.querySelectorAll("[role='radio']")).toHaveLength(2);
    expect(container.textContent).toContain("Play with Coach");
    expect(container.textContent).toContain("Play a Game");
    expect(container.textContent).not.toContain("Test this lesson");
    expect(container.textContent).not.toContain("Just play");
  });

  test("Play a Game is a visible quiet-mode choice", () => {
    act(() => root.render(<Harness />));

    act(() => {
      container.querySelector("[data-testid='unified-mode-play']").click();
    });

    expect(
      container.querySelector("[data-testid='unified-mode-play']").getAttribute("aria-checked")
    ).toBe("true");
    expect(container.textContent).toContain(
      "No help during the game. We’ll review it afterward."
    );
  });

  test("shows coaching access before start and routes to pricing", () => {
    const startGame = jest.fn();
    const blocked = {
      ...allowedConfig,
      access: {
        ...allowedConfig.access,
        coach: {
          allowed: false,
          message: "Today’s free coached game has been used.",
          upgrade_url: "/pricing",
        },
      },
    };
    act(() => root.render(<Harness config={blocked} startGame={startGame} />));

    expect(container.textContent).toContain("Today’s free coached game has been used.");
    expect(container.textContent).toContain("See coaching access");

    act(() => {
      container.querySelector("[data-testid='unified-start-game']").click();
    });

    expect(startGame).not.toHaveBeenCalled();
    expect(mockNavigate).toHaveBeenCalledWith("/pricing");
  });

  test("work on something else offers at most three openings from recent games", async () => {
    global.fetch = jest.fn(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        white: [
          { name: "Italian Game" },
          { name: "Bishop's Opening" },
          { name: "Vienna Game" },
          { name: "Scotch Game" },
        ],
        black: [],
      }),
    }));
    act(() => root.render(<Harness />));

    await act(async () => {
      container.querySelector("[data-testid='unified-work-choice-toggle']").click();
      await Promise.resolve();
      await Promise.resolve();
    });

    const choices = container.querySelector("[data-testid='unified-work-choices']");
    const openingButtons = Array.from(choices.querySelectorAll("button"));
    expect(openingButtons).toHaveLength(3);
    expect(choices.textContent).toContain("Italian Game");
    expect(choices.textContent).not.toContain("Scotch Game");

    act(() => openingButtons[0].click());
    expect(container.textContent).toContain("Italian Game");
    expect(container.textContent).toContain(
      "connect Italian Game to the position without choosing your moves"
    );
  });
});
