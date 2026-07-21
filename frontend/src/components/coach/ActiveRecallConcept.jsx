import React, { useState } from "react";
import { Button } from "../ui/button";
import "./ActiveRecallConcept.css";

/**
 * CONCEPT QUESTION: "Why was your move worse?"
 *
 * MCQ with 4 options (1 correct + 3 distractors).
 * Verified by backend before showing - only appears if gap verification passes.
 */
export default function ActiveRecallConcept({
  concept,
  onAnswer,
  isLoading = false
}) {
  const [selected, setSelected] = useState(null);

  if (!concept) return null;

  const handleSubmit = () => {
    if (selected === null) return;

    onAnswer({
      selected_index: selected,
      correct_index: concept.correct_index,
      cognitive_gap: concept.cognitive_gap
    });
  };

  return (
    <div className="active-recall-concept">
      <div className="ar-question">
        <span className="ar-badge">Why?</span>
        <p className="ar-question-text">{concept.question}</p>
      </div>

      <div className="ar-mcq-container">
        <div className="ar-options">
          {concept.options.map((option, index) => (
            <label key={index} className="ar-mcq-option">
              <input
                type="radio"
                name="concept"
                value={index}
                checked={selected === index}
                onChange={() => setSelected(index)}
              />
              <span className="ar-option-text">{option}</span>
            </label>
          ))}
        </div>
      </div>

      <Button
        onClick={handleSubmit}
        disabled={isLoading || selected === null}
        className="ar-submit-btn"
      >
        {isLoading ? "Checking..." : "Check Answer"}
      </Button>
    </div>
  );
}
