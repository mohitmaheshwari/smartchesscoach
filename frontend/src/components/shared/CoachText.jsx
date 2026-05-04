/**
 * CoachText — wrapper around any coach-generated string that
 * auto-attaches an InlineFlag for tester feedback.
 *
 * Why this exists:
 *   The InlineFlag pattern was scattered across a few files but
 *   missing from most coach surfaces. Tester reports kept landing
 *   without enough position context because the flag wasn't on the
 *   specific text they wanted to flag. This wrapper makes "every
 *   coach string is flaggable" the default — wrap once, get the
 *   flag for free.
 *
 * Usage:
 *   <CoachText section="narrative" context={flagCtx}>
 *     {move.narrative}
 *   </CoachText>
 *
 * As a paragraph (default):
 *   <CoachText section="goal" context={flagCtx} className="text-sm">
 *     {goalText}
 *   </CoachText>
 *
 * Inline (no wrapping element):
 *   <CoachText as="span" inline section="...">{...}</CoachText>
 *
 * The component renders nothing when children is empty/falsy, so
 * existing `{text && <p>{text}</p>}` patterns become
 * `<CoachText>{text}</CoachText>` without breaking layout.
 */

import { InlineFlag } from "@/components/shared/FlagMoveDialog";

const CoachText = ({
  children,
  section,
  context = {},
  as: Tag = "p",
  className = "",
  inline = false,
  flagPosition = "after", // "after" | "none"
}) => {
  // Empty / null / undefined → render nothing. Matches the
  // `{text && <p>{text}</p>}` pattern callers were using.
  if (children === null || children === undefined || children === "") {
    return null;
  }

  // Pass-through option for places that want the flag elsewhere
  // (e.g., on a parent card header) without duplicating it.
  const showFlag = flagPosition !== "none" && section;

  // Inline mode just wraps in a fragment — no <p> / <div> added.
  if (inline) {
    return (
      <span className="group inline">
        <span className={className}>{children}</span>
        {showFlag && (
          <InlineFlag
            section={section}
            flaggedText={typeof children === "string" ? children : null}
            context={context}
          />
        )}
      </span>
    );
  }

  return (
    <Tag className={`group ${className}`.trim()}>
      <span className="inline">{children}</span>
      {showFlag && (
        <InlineFlag
          section={section}
          flaggedText={typeof children === "string" ? children : null}
          context={context}
        />
      )}
    </Tag>
  );
};

export default CoachText;
export { CoachText };
