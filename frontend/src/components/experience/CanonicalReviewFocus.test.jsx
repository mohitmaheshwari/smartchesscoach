import { act } from "react";
import { createRoot } from "react-dom/client";
import CanonicalReviewFocus from "./CanonicalReviewFocus";


describe("CanonicalReviewFocus", () => {
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

  test("leads with the instruction and opens verified matching moves", () => {
    const onMoveSelect = jest.fn();
    const context = {
      primary_focus: {
        label: "Keeping your pieces safe",
        instruction_text: "Before every move, ask: can this piece be taken?",
      },
      surface_context: {
        focus_evidence_state: "observed",
        message: "Your current check showed up in this game.",
        primary_matches: [
          { move_number: 12, move_san: "Qd5", severity: "blunder" },
          { move_number: 19, move_san: "Ra2", severity: "mistake" },
        ],
      },
    };

    act(() => root.render(
      <CanonicalReviewFocus context={context} onMoveSelect={onMoveSelect} />
    ));

    expect(container.textContent).toContain("Your focus in this game");
    expect(container.textContent).toContain("Before every move, ask: can this piece be taken?");
    expect(container.querySelectorAll("[data-testid='canonical-review-move']")).toHaveLength(2);

    act(() => {
      container.querySelector("[data-testid='canonical-review-move']").dispatchEvent(
        new MouseEvent("click", { bubbles: true })
      );
    });
    expect(onMoveSelect).toHaveBeenCalledWith(12);
  });

  test("shows the honest no-opportunity message without a false clean claim", () => {
    const context = {
      primary_focus: {
        label: "Keeping your pieces safe",
        instruction_text: "Before every move, ask: can this piece be taken?",
      },
      surface_context: {
        focus_evidence_state: "not_observed",
        message: "This game did not give us a verified chance to test your focus. That does not mean the problem is fixed.",
        primary_matches: [],
      },
    };

    act(() => root.render(<CanonicalReviewFocus context={context} />));

    expect(container.textContent).toContain("does not mean the problem is fixed");
    expect(container.textContent.toLowerCase()).not.toContain("you improved");
    expect(container.textContent.toLowerCase()).not.toContain("you followed");
  });
});

