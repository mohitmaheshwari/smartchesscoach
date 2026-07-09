import React, { useEffect, useState } from 'react';
import { CheckCircle2, AlertCircle, TrendingUp, RotateCw } from 'lucide-react';

export default function SessionReflectionCard({ sessionId, reflection, onClose }) {
  const [animate, setAnimate] = useState(false);

  useEffect(() => {
    // Trigger animation on mount
    setTimeout(() => setAnimate(true), 100);
  }, []);

  if (!reflection) return null;

  const {
    goal,
    focus_topic,
    achieved,
    evidence,
    stat_label,
    encouragement,
    next_focus,
    confidence
  } = reflection;

  const bgColor = achieved
    ? 'bg-gradient-to-r from-emerald-50 to-emerald-100 dark:from-emerald-950/50 dark:to-emerald-900/30'
    : 'bg-gradient-to-r from-amber-50 to-amber-100 dark:from-amber-950/50 dark:to-amber-900/30';

  const borderColor = achieved
    ? 'border-emerald-300 dark:border-emerald-600'
    : 'border-amber-300 dark:border-amber-600';

  const textPrimary = achieved ? 'text-emerald-900 dark:text-emerald-100' : 'text-amber-900 dark:text-amber-100';
  const textSecondary = achieved ? 'text-emerald-700 dark:text-emerald-200' : 'text-amber-700 dark:text-amber-200';

  return (
    <div
      className={`
        fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4
        transition-opacity duration-300
        ${animate ? 'opacity-100' : 'opacity-0'}
      `}
      onClick={onClose}
    >
      <div
        className={`
          ${bgColor} border-2 ${borderColor} rounded-lg shadow-2xl
          max-w-md w-full p-6 space-y-4
          transform transition-all duration-500 ease-out
          ${animate ? 'scale-100 translate-y-0' : 'scale-95 translate-y-8'}
        `}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1">
            <h2 className={`text-xl font-bold ${textPrimary}`}>
              {achieved ? '🎯 Goal Achieved!' : '⚠ Keep Working'}
            </h2>
            <p className={`text-sm ${textSecondary}`}>
              Today&apos;s focus: <span className="font-semibold">{goal}</span>
            </p>
          </div>
          {achieved ? (
            <CheckCircle2 className="w-8 h-8 text-emerald-600 dark:text-emerald-400 flex-shrink-0 mt-1" />
          ) : (
            <AlertCircle className="w-8 h-8 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-1" />
          )}
        </div>

        {/* Stats */}
        <div className={`
          bg-white/60 dark:bg-black/20 rounded-lg p-3
          border border-white/40 dark:border-white/10
        `}>
          <div className={`text-sm ${textSecondary} font-medium`}>
            {stat_label}
          </div>
          <div className={`text-xs ${textSecondary} mt-1`}>
            {evidence}
          </div>
        </div>

        {/* Encouragement */}
        <div className={`
          bg-white/40 dark:bg-white/5 rounded-lg p-3 border-l-4
          ${achieved ? 'border-emerald-500' : 'border-amber-500'}
        `}>
          <div className={`text-sm leading-relaxed ${textPrimary}`}>
            {encouragement}
          </div>
        </div>

        {/* Next Focus (if applicable) */}
        {next_focus && (
          <div className={`
            flex items-start gap-2 p-3 rounded-lg
            bg-blue-50/60 dark:bg-blue-950/30 border border-blue-200/50 dark:border-blue-800/50
          `}>
            <TrendingUp className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
            <div>
              <div className="text-xs font-semibold text-blue-900 dark:text-blue-200">Next Step</div>
              <div className="text-sm text-blue-800 dark:text-blue-300 capitalize">
                Ready to focus on <span className="font-semibold">{next_focus.replace('_', ' ')}</span>?
              </div>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2 pt-2">
          <button
            onClick={onClose}
            className={`
              flex-1 py-2 px-3 rounded-lg font-medium text-sm
              transition-colors duration-200
              ${achieved
                ? 'bg-emerald-600 hover:bg-emerald-700 text-white dark:bg-emerald-700 dark:hover:bg-emerald-600'
                : 'bg-amber-600 hover:bg-amber-700 text-white dark:bg-amber-700 dark:hover:bg-amber-600'
              }
            `}
          >
            Play Again
          </button>
          <button
            onClick={() => window.location.href = '/lab'}
            className={`
              flex-1 py-2 px-3 rounded-lg font-medium text-sm
              transition-colors duration-200
              bg-white/70 dark:bg-white/10 hover:bg-white dark:hover:bg-white/20
              ${textPrimary}
            `}
          >
            <RotateCw className="w-4 h-4 inline mr-1" />
            Puzzles
          </button>
        </div>

        {/* Close hint */}
        <div className="text-xs text-center opacity-60">
          Click outside to close
        </div>
      </div>
    </div>
  );
}
