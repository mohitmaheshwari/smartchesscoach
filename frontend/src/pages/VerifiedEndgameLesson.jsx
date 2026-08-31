import { useParams } from "react-router-dom";
import PersonalizedLessonWorkspace from "@/components/training/PersonalizedLessonWorkspace";

export default function VerifiedEndgameLesson({ user }) {
  const { categoryKey, lessonKey } = useParams();
  return (
    <PersonalizedLessonWorkspace
      user={user}
      contentKind="endgame"
      contentId={`${categoryKey}/${lessonKey}`}
    />
  );
}
