import { act } from "react";
import { createRoot } from "react-dom/client";
import CanonicalFocusRail from "./CanonicalFocusRail";


describe("CanonicalFocusRail", () => {
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

  test("renders one primary instruction, one support, and the canonical action", () => {
    const onAction = jest.fn();
    const context = {
      state: "primary_with_support",
      primary_focus: {
        focus_id: "focus-1",
        label: "Keeping your pieces safe",
        instruction_id: "instruction-1",
        instruction_text: "Before every move, ask: can this piece be taken?",
      },
      supporting_focuses: [{ topic_key: "king_safety", label: "King safety" }],
      evidence: {
        message: "Your instruction is ready. Improvement is not claimed yet.",
      },
      next_action: {
        type: "practice",
        href: "/training/pattern/piece_safety",
        label: "Practise this check",
      },
    };

    act(() => root.render(
      <CanonicalFocusRail context={context} onAction={onAction} />
    ));

    expect(container.textContent).toContain("Your main focus");
    expect(container.textContent).toContain("Keeping your pieces safe");
    expect(container.textContent).toContain("Before every move, ask: can this piece be taken?");
    expect(container.textContent).toContain("Also watching: King safety");
    expect(container.querySelectorAll("[data-testid='canonical-supporting-focus']")).toHaveLength(1);

    act(() => {
      container.querySelector("[data-testid='canonical-context-action']").dispatchEvent(
        new MouseEvent("click", { bubbles: true })
      );
    });
    expect(onAction).toHaveBeenCalledWith(context.next_action);
  });

  test("renders the honest no-focus state without inventing a diagnosis", () => {
    const context = {
      state: "no_focus",
      primary_focus: null,
      supporting_focuses: [],
      evidence: {
        message: "I need enough verified games before choosing your main focus.",
      },
      next_action: {
        type: "review",
        href: "/import",
        label: "Build my coaching evidence",
      },
    };

    act(() => root.render(<CanonicalFocusRail context={context} />));

    expect(container.textContent).toContain("Your coaching plan");
    expect(container.textContent).toContain("I need enough verified games");
    expect(container.textContent).not.toContain("Your main focus");
  });
});

