import { useCallback, useMemo, useState } from "react";

const fallbackUuid = () => {
  const bytes = new Uint8Array(16);
  if (globalThis.crypto?.getRandomValues) {
    globalThis.crypto.getRandomValues(bytes);
  } else {
    for (let index = 0; index < bytes.length; index += 1) {
      bytes[index] = Math.floor(Math.random() * 256);
    }
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, "0"));
  return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10).join("")}`;
};

export const createPuzzleSubmissionId = () => (
  globalThis.crypto?.randomUUID?.() || fallbackUuid()
);

/**
 * Keep one UUID stable while a request is in flight. Rotate only after the
 * server answered, so a network retry reuses the same logical identity while
 * a deliberate second move is a new attempt.
 */
export default function usePuzzleSubmissionIdentity(puzzleKey) {
  const [revision, setRevision] = useState(0);
  const normalizedKey = String(puzzleKey || "");
  const submissionId = useMemo(
    () => (
      normalizedKey && revision >= 0 ? createPuzzleSubmissionId() : null
    ),
    [normalizedKey, revision],
  );
  const rotate = useCallback(() => setRevision((value) => value + 1), []);
  return [submissionId, rotate];
}
