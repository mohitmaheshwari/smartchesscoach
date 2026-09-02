import fs from "fs";
import path from "path";

import { createPuzzleSubmissionId } from "./usePuzzleSubmissionIdentity";


const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

describe("puzzle submission identity", () => {
  test("creates opaque RFC 4122 version-4 identities", () => {
    const ids = Array.from({ length: 64 }, () => createPuzzleSubmissionId());

    ids.forEach((value) => expect(value).toMatch(UUID_V4));
    expect(new Set(ids).size).toBe(ids.length);
  });

  test("keeps identity in React state and rotates only explicitly", () => {
    const source = fs.readFileSync(
      path.join(__dirname, "usePuzzleSubmissionIdentity.js"),
      "utf8",
    );

    expect(source).toContain("useMemo");
    expect(source).toContain("[normalizedKey, revision]");
    expect(source).toContain("setRevision((value) => value + 1)");
    expect(source).not.toContain("Date.now()");
  });
});

describe("active puzzle surfaces carry the server idempotency key", () => {
  const pages = [
    "Challenge.jsx",
    "DailyFixDrill.jsx",
    "LabV2.jsx",
    "MissionRunner.jsx",
    "OpeningWalkthrough.jsx",
    "PrescribedTraining.jsx",
    "SkillDrill.jsx",
  ];

  test.each(pages)("%s sends and advances a puzzle submission identity", (file) => {
    const source = fs.readFileSync(
      path.join(__dirname, "..", "pages", file),
      "utf8",
    );

    expect(source).toContain("usePuzzleSubmissionIdentity");
    expect(source).toContain("submission_id: puzzleSubmissionId");
    expect(source).toContain("rotatePuzzleSubmissionId()");
  });
});
