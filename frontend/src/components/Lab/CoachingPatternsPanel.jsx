/**
 * CoachingPatternsPanel — Display all 5 coaching patterns in Lab
 *
 * Shows:
 * 1. Motif weaknesses (fork/pin/skewer)
 * 2. Phase accuracy gaps
 * 3. Coordination gaps
 * 4. Prophylaxis gaps
 * 5. Opening deviations
 */

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { API } from '@/App';
import PatternWeaknessCard from './PatternWeaknessCard';
import { fadeInUp, staggerContainer, staggerItem, revealOnScroll } from '@/lib/motion';

const CoachingPatternsPanel = ({ user }) => {
  const navigate = useNavigate();
  const [patterns, setPatterns] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchPatterns = async () => {
      try {
        setLoading(true);
        const res = await fetch(`${API}/coaching-patterns/all-patterns`, {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });

        if (!res.ok) throw new Error('Failed to fetch patterns');

        const data = await res.json();
        setPatterns(data);
      } catch (err) {
        console.error('Error fetching coaching patterns:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    if (user) {
      fetchPatterns();
    }
  }, [user]);

  if (loading) {
    return (
      <section className="mb-16 md:mb-24">
        <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-5">
          Your coaching patterns
        </div>
        <div className="animate-pulse space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-32 bg-muted rounded-lg" />
          ))}
        </div>
      </section>
    );
  }

  if (error || !patterns) {
    return null; // Silent fail; doesn't block the page
  }

  // Collect all patterns that have meaningful data
  const activePatterns = [];

  // Add motif weaknesses
  if (patterns.motifs && patterns.motifs.length > 0) {
    patterns.motifs.forEach(motif => {
      activePatterns.push({
        id: `motif_${motif.motif}`,
        type: 'motif',
        pattern: motif.motif,
        stats: [
          { label: 'Total', value: `${motif.weakness_count}x` },
          { label: 'Recent', value: `${motif.recent_count}x` },
          { label: 'Trend', value: `${Math.round(motif.recovery_trend * 100)}%` }
        ]
      });
    });
  }

  // Add phase weakness
  if (
    patterns.phase_accuracy &&
    patterns.phase_accuracy.weak_phase &&
    patterns.phase_accuracy.divergence_pct > 15
  ) {
    activePatterns.push({
      id: 'phase_' + patterns.phase_accuracy.weak_phase,
      type: 'phase',
      pattern: patterns.phase_accuracy.weak_phase,
      stats: [
        { label: 'Strong phase', value: `${patterns.phase_accuracy.opening || patterns.phase_accuracy.middlegame || patterns.phase_accuracy.endgame}%` },
        { label: 'Weak phase', value: `${patterns.phase_accuracy[patterns.phase_accuracy.weak_phase] || 0}%` },
        { label: 'Gap', value: `${patterns.phase_accuracy.divergence_pct}%` }
      ]
    });
  }

  // Add coordination gap
  if (patterns.coordination && patterns.coordination.has_gap) {
    activePatterns.push({
      id: 'coordination',
      type: 'coordination',
      pattern: 'coordination',
      stats: [
        { label: 'Gap type', value: patterns.coordination.gap_type || 'unknown' },
        { label: 'Confidence', value: `${Math.round(patterns.coordination.confidence * 100)}%` },
        { label: 'Examples', value: `${patterns.coordination.example_moves}` }
      ]
    });
  }

  // Add prophylaxis gap
  if (patterns.prophylaxis && patterns.prophylaxis.has_gap) {
    activePatterns.push({
      id: 'prophylaxis',
      type: 'prophylaxis',
      pattern: 'prophylaxis',
      stats: [
        { label: 'Reactive moves', value: `${patterns.prophylaxis.reactive_move_count}` },
        { label: 'Confidence', value: `${Math.round(patterns.prophylaxis.confidence * 100)}%` },
        { label: 'Trend', value: patterns.prophylaxis.trend }
      ]
    });
  }

  // Add opening deviations
  if (patterns.openings && patterns.openings.has_significant_deviation) {
    patterns.openings.deviation_openings.forEach(opening => {
      activePatterns.push({
        id: `opening_${opening.opening}`,
        type: 'opening',
        pattern: 'opening',
        label: opening.opening,
        stats: [
          { label: 'Deviations', value: `${opening.deviation_count}x` },
          { label: 'Recent', value: `${opening.recent}x` }
        ]
      });
    });
  }

  if (activePatterns.length === 0) {
    return null; // No patterns to show
  }

  const handlePatternAction = (patternId) => {
    // Route to appropriate coaching surface
    const type = patternId.split('_')[0];

    if (type === 'motif') {
      const motif = patternId.replace('motif_', '');
      navigate(`/training/pattern/${motif}`);
    } else if (type === 'phase') {
      navigate('/training/phase-transitions');
    } else if (type === 'coordination') {
      navigate('/training/coordination');
    } else if (type === 'prophylaxis') {
      navigate('/training/prophylaxis');
    } else if (type === 'opening') {
      navigate('/openings');
    }
  };

  return (
    <motion.section
      variants={revealOnScroll}
      initial="initial"
      whileInView="animate"
      viewport={{ once: true, amount: 0.2 }}
      className="mb-16 md:mb-24"
    >
      <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-5">
        Your coaching patterns
      </div>

      <motion.div
        variants={staggerContainer}
        initial="initial"
        whileInView="animate"
        viewport={{ once: true, amount: 0.2 }}
        className="space-y-4"
      >
        {activePatterns.map(p => (
          <motion.div
            key={p.id}
            variants={staggerItem}
          >
            <PatternWeaknessCard
              pattern={p.pattern}
              stats={p.stats}
              onAction={handlePatternAction}
            />
          </motion.div>
        ))}
      </motion.div>
    </motion.section>
  );
};

export default CoachingPatternsPanel;
