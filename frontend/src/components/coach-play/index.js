/**
 * Coach Play Components
 * 
 * Extracted components from CoachPlay.jsx for better maintainability
 */

export { default as EvalBar } from './EvalBar';
export { default as MoveFeedbackPanel } from './MoveFeedbackPanel';
export { default as GuardianWarning } from './GuardianWarning';
export { default as CoachChat } from './CoachChat';
export { default as GameSetupPanel } from './GameSetupPanel';
export { default as InlineOpeningLesson } from './InlineOpeningLesson';
export { default as InlineTrapLesson } from './InlineTrapLesson';

// NEW: Clean UX Components (One move → one insight → one next action)
export { default as CoachInsightCard } from './CoachInsightCard';
export { default as TrapAlert } from './TrapAlert';
export { default as AskCoach } from './AskCoach';
export { MoveHistory, MoveHistorySection } from './MoveHistoryCompact';

