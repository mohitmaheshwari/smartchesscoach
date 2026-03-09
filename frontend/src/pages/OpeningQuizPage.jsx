/**
 * Opening Quiz Page
 * 
 * Wrapper page for the OpeningQuiz component.
 * Handles routing and navigation.
 */

import React from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import Layout from "@/components/Layout";
import OpeningQuiz from "@/components/OpeningQuiz";

const OpeningQuizPage = ({ user }) => {
  const { openingKey } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  
  const openingName = searchParams.get("name") || openingKey?.replace(/_/g, " ");

  const handleClose = () => {
    navigate("/training");
  };

  const handleComplete = (result) => {
    console.log("Quiz completed:", result);
    // Could show a toast or navigate based on result
  };

  return (
    <Layout user={user}>
      <div className="container max-w-4xl mx-auto py-8 px-4">
        <OpeningQuiz
          openingKey={openingKey}
          openingName={openingName}
          onClose={handleClose}
          onComplete={handleComplete}
        />
      </div>
    </Layout>
  );
};

export default OpeningQuizPage;
