import { toneForMessageType, panelClassForTone, TONES } from "./coachMessageTone";

// The 41 types the sidebar's ternary chain actually branches on today.
const AFFIRMS = ["piece_safe_affirm","king_safety_affirm","piece_activity_affirm",
  "endgame_technique_affirm","pawn_structure_affirm","missed_tactic_affirm",
  "tactical_oversight_affirm","calculation_depth_affirm","fast_good_affirm"];
const NAGS = ["piece_safety_nag","king_safety_nag","piece_activity_nag",
  "endgame_technique_nag","pawn_structure_nag","missed_tactic_nag",
  "tactical_oversight_nag","calculation_depth_nag","pre_move_nag"];
const WARNINGS = ["piece_safety_warning","king_safety_warning","piece_activity_warning",
  "endgame_technique_warning","pawn_structure_warning","missed_tactic_warning",
  "tactical_oversight_warning","calculation_depth_warning","impulse_warning"];
const STREAKS = ["piece_safety_streak","king_safety_streak","piece_activity_streak",
  "endgame_technique_streak","pawn_structure_streak","missed_tactic_streak",
  "tactical_oversight_streak","calculation_depth_streak"];

test("every affirm reads as good", () => {
  AFFIRMS.forEach(t => expect([t, toneForMessageType(t)]).toEqual([t, "good"]));
});

test("every nag is a quiet nudge, not a warning", () => {
  NAGS.forEach(t => expect([t, toneForMessageType(t)]).toEqual([t, "nudge"]));
});

test("every warning reads as warn regardless of topic", () => {
  WARNINGS.forEach(t => expect([t, toneForMessageType(t)]).toEqual([t, "warn"]));
});

test("a streak is the same concern repeating, not a louder one", () => {
  // Deliberate: no escalation to a 'critical' tone. A sidebar that reddens as
  // the game goes on is a failure scoreboard.
  STREAKS.forEach(t => expect([t, toneForMessageType(t)]).toEqual([t, "warn"]));
});

test("teaching and context carry no verdict", () => {
  ["v5_teaching","habit_prompt","opening_announcement","focus_coach"]
    .forEach(t => expect([t, toneForMessageType(t)]).toEqual([t, "info"]));
});

test("the topic no longer changes the colour", () => {
  const topics = ["piece_safety","king_safety","piece_activity","endgame_technique",
                  "pawn_structure","missed_tactic","tactical_oversight","calculation_depth"];
  const tones = new Set(topics.map(t => toneForMessageType(t + "_warning")));
  expect([...tones]).toEqual(["warn"]);   // was 7 different hues
});

test("a brand new message type degrades to neutral, not to a crash", () => {
  expect(toneForMessageType("some_future_type")).toBe("info");
  expect(toneForMessageType(undefined)).toBe("info");
  expect(toneForMessageType("")).toBe("info");
});

test("a new topic warning is handled without editing anything", () => {
  expect(toneForMessageType("zugzwang_awareness_warning")).toBe("warn");
  expect(toneForMessageType("zugzwang_awareness_affirm")).toBe("good");
});

test("every tone has a panel class and none hardcode a hue", () => {
  TONES.forEach(tone => {
    const cls = panelClassForTone(tone);
    expect(cls).toBeTruthy();
    expect(cls).not.toMatch(/-(rose|violet|purple|indigo|sky|teal|emerald|orange|amber|yellow|slate|red)-\d/);
  });
});
