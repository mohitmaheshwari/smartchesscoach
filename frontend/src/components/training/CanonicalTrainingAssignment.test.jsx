import { act } from "react";
import { createRoot } from "react-dom/client";
import CanonicalTrainingAssignment from "./CanonicalTrainingAssignment";


describe("CanonicalTrainingAssignment", () => {
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

  test("renders the exact server assignment and evidence message", () => {
    const context = {
      primary_focus: { label: "Keeping your pieces safe" },
      evidence: {
        message: "Improvement is not claimed until later games test this check.",
      },
      surface_context: {
        assignment: {
          focus_id: "focus-1",
          instruction_id: "instruction-1",
          instruction_text: "Before every move, ask: can this piece be taken?",
        },
      },
    };

    act(() => root.render(<CanonicalTrainingAssignment context={context} />));

    expect(container.textContent).toContain("Today's assignment");
    expect(container.textContent).toContain("Keeping your pieces safe");
    expect(container.textContent).toContain("Before every move, ask: can this piece be taken?");
    expect(container.textContent).toContain("Improvement is not claimed");
    expect(container.querySelector("[data-instruction-id='instruction-1']")).not.toBeNull();
  });

  test("renders nothing when there is no canonical assignment", () => {
    act(() => root.render(
      <CanonicalTrainingAssignment context={{ surface_context: { assignment: null } }} />
    ));

    expect(container.textContent).toBe("");
  });
});

