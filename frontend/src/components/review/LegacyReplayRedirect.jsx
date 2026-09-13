import { Navigate, useParams } from "react-router-dom";

import { canonicalGameReviewPath } from "../../lib/reviewRoutes";


export default function LegacyReplayRedirect() {
  const { gameId } = useParams();
  return <Navigate to={canonicalGameReviewPath(gameId)} replace />;
}
