import fs from "fs";
import path from "path";

const source = (relativePath) => fs.readFileSync(
  path.join(process.cwd(), "src", relativePath),
  "utf8"
);

test("Lab, Progress, Game Review, and Play with Coach use one curriculum state projection", () => {
  const surfaces = {
    "pages/Dashboard.jsx": 'surface="lab"',
    "pages/AllGames.jsx": 'surface="game_review"',
    "components/coach/CoachPlaySetup.jsx": 'surface="play_with_coach"',
  };

  Object.entries(surfaces).forEach(([file, marker]) => {
    const text = source(file);
    expect(text).toContain("CurriculumStateStrip");
    expect(text).toContain(marker);
  });

  const progress = source("pages/UnifiedProgress.jsx");
  expect(progress).toContain("loadPersonalCurriculum");
  expect(progress).toContain('user?.user_id, "progress"');
  expect(progress).not.toContain("CurriculumStateStrip");
});
