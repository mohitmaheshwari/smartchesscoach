import React, { useState } from "react";
import { Button } from "../ui/button";
import "./ActiveRecallRanking.css";

/**
 * RANKING QUESTION: "Which move is best?"
 *
 * User drags to rank 3-4 options. Calculates correctness based on selected order.
 * Verified by backend before showing - only appears if chess verification passes.
 */
export default function ActiveRecallRanking({
  ranking,
  onAnswer,
  isLoading = false
}) {
  const [order, setOrder] = useState([...ranking.options]);
  const [draggedIndex, setDraggedIndex] = useState(null);

  if (!ranking) return null;

  const handleDragStart = (index) => {
    setDraggedIndex(index);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (targetIndex) => {
    if (draggedIndex === null) return;

    const newOrder = [...order];
    const draggedItem = newOrder[draggedIndex];
    newOrder.splice(draggedIndex, 1);
    newOrder.splice(targetIndex, 0, draggedItem);
    setOrder(newOrder);
    setDraggedIndex(null);
  };

  const handleSubmit = () => {
    // Find index of correct move in user's ranking
    const correctMove = ranking.options[ranking.correct_index];
    const selectedIndex = order.indexOf(correctMove);

    onAnswer({
      selected_index: selectedIndex,
      correct_index: ranking.correct_index,
      user_order: order
    });
  };

  return (
    <div className="active-recall-ranking">
      <div className="ar-question">
        <span className="ar-badge">Ranking</span>
        <p className="ar-question-text">{ranking.question}</p>
      </div>

      <div className="ar-ranking-container">
        <div className="ar-instruction">Drag to rank (1st = best):</div>

        <div className="ar-options">
          {order.map((move, index) => (
            <div
              key={index}
              className={`ar-option ar-rank-${index + 1} ${
                draggedIndex === index ? "dragging" : ""
              }`}
              draggable
              onDragStart={() => handleDragStart(index)}
              onDragOver={handleDragOver}
              onDrop={() => handleDrop(index)}
            >
              <span className="ar-rank-number">{index + 1}</span>
              <span className="ar-move-text">{move}</span>
            </div>
          ))}
        </div>
      </div>

      <Button
        onClick={handleSubmit}
        disabled={isLoading}
        className="ar-submit-btn"
      >
        {isLoading ? "Checking..." : "Check Answer"}
      </Button>
    </div>
  );
}
