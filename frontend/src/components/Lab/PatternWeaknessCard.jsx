import React from 'react';
import './PatternWeaknessCard.css';

/**
 * PatternWeaknessCard — displays one coaching pattern weakness
 *
 * Used in Lab page for:
 * - Motif weaknesses (fork/pin/skewer)
 * - Phase accuracy gaps
 * - Coordination gaps
 * - Prophylaxis gaps
 * - Opening deviations
 */

const PatternWeaknessCard = ({ pattern, type, stats, onAction }) => {
  const patternConfig = {
    fork: {
      icon: '🔴',
      title: 'Motif Weakness: Fork',
      description: 'You got forked 47 times. 41 in games, 12 times after training (1 per 5 games now — improving)',
      cta: 'Drill fork puzzles →'
    },
    pin: {
      icon: '📌',
      title: 'Motif Weakness: Pin',
      description: 'Pins catch you regularly. Your pieces get trapped.',
      cta: 'Drill pin puzzles →'
    },
    skewer: {
      icon: '🎯',
      title: 'Motif Weakness: Skewer',
      description: 'Skewers expose your pieces. Work on pattern recognition.',
      cta: 'Drill skewer puzzles →'
    },
    middlegame: {
      icon: '📊',
      title: 'Phase Weakness: Middlegame',
      description: 'Your opening is solid (82% accuracy). Your middlegame has gaps (61% accuracy). Practice middlegame transitions.',
      cta: 'Practice transitions →'
    },
    coordination: {
      icon: '🔄',
      title: 'Coordination Gap',
      description: 'Your rooks rarely support each other. Pieces should work as a team.',
      cta: 'Practice coordination →'
    },
    prophylaxis: {
      icon: '🛡️',
      title: 'Prophylaxis Gap',
      description: 'You react instead of prevent threats. Anticipate opponent\'s plans.',
      cta: 'Practice prevention →'
    },
    opening: {
      icon: '📖',
      title: 'Opening Choices',
      description: 'You deviate from Sicilian (41 times). Are you exploring or lost?',
      cta: 'Review your choices →'
    }
  };

  const config = patternConfig[pattern] || {};

  return (
    <div className="pattern-weakness-card">
      <div className="pattern-header">
        <span className="pattern-icon">{config.icon}</span>
        <h3>{config.title}</h3>
      </div>

      <p className="pattern-description">{config.description}</p>

      {stats && (
        <div className="pattern-stats">
          {stats.map((stat, idx) => (
            <div key={idx} className="stat-row">
              <span className="stat-label">{stat.label}</span>
              <span className="stat-value">{stat.value}</span>
            </div>
          ))}
        </div>
      )}

      <button
        className="pattern-cta"
        onClick={() => onAction && onAction(pattern)}
      >
        {config.cta}
      </button>
    </div>
  );
};

export default PatternWeaknessCard;
