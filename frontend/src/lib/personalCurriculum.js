export const CURRICULUM_ROUTES = Object.freeze({
  home: "/home",
  learn: "/learn",
  gameReview: "/games",
});

export const EXPLORE_DESTINATIONS = Object.freeze([
  { id: "openings", label: "Openings", href: "/openings" },
  { id: "tactics_traps", label: "Tactics \u0026 traps", href: "/training" },
  { id: "endgames", label: "Endgames", href: "/openings-overview?tab=endgames" },
  { id: "plans", label: "Plans", href: "/coach" },
  { id: "thinking_habits", label: "Thinking habits", href: "/training" },
]);

export const curriculumHeadline = (outcome) => ({
  observe: "Let me learn how you play.",
  repair: "Let's fix one thing that keeps getting in your way.",
  expand: "Let's add one idea to your game.",
  continue: "Let's pick up where we left off.",
  review: "Let's keep this idea fresh.",
  apply: "Let's use this in a real game.",
}[outcome] || "Here's what we'll work on next.");

export const curriculumCta = (outcome) => ({
  observe: "Play with your coach",
  repair: "Practise with your coach",
  expand: "Learn with your coach \u00b7 6 min",
  continue: "Continue",
  review: "Review now",
  apply: "Play a focus game",
}[outcome] || "Continue");

export const curriculumStateLabel = (state) => ({
  new: "New",
  learning: "Learning",
  can_do_with_help: "Can do with help",
  can_do_alone: "Can do alone",
  used_in_games: "Used in games",
}[state] || "Learning");

const curriculumRequests = new Map();

export const loadPersonalCurriculum = (api, userId, surface = null) => {
  const key = api + "|" + (userId || "anonymous") + "|" + (surface || "shared");
  if (!curriculumRequests.has(key)) {
    const query = surface ? "?surface=" + encodeURIComponent(surface) : "";
    const request = fetch(api + "/coach/personal-curriculum" + query, {
      credentials: "include",
    })
      .then((response) => {
        if (!response.ok) throw new Error("curriculum unavailable");
        return response.json();
      })
      .catch((error) => {
        curriculumRequests.delete(key);
        throw error;
      });
    curriculumRequests.set(key, request);
  }
  return curriculumRequests.get(key);
};

export const resetPersonalCurriculumRequestsForTests = () => {
  curriculumRequests.clear();
};

export const invalidatePersonalCurriculum = () => {
  curriculumRequests.clear();
};
