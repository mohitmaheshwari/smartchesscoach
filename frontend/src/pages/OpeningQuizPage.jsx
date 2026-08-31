/** Compatibility route for the retired answer-bearing opening quiz. */
import { Navigate, useParams } from "react-router-dom";

export default function OpeningQuizPage() {
  const { openingKey } = useParams();
  const target = `/training?personalized=1&kind=opening&lesson=${encodeURIComponent(openingKey || "")}`;
  return <Navigate to={target} replace />;
}
