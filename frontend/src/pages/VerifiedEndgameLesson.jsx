import { useParams } from "react-router-dom";
import PersonalizedLessonWorkspace from "@/components/training/PersonalizedLessonWorkspace";

export default function VerifiedEndgameLesson() {
  const { categoryKey, lessonKey } = useParams();
  return (
    <PersonalizedLessonWorkspace
      contentKind="endgame"
      contentId={`${categoryKey}/${lessonKey}`}
    />
  );
}
