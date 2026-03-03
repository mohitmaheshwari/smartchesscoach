import React from 'react';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { TrendingUp, TrendingDown, AlertTriangle, Sparkles, Target, ChevronRight } from 'lucide-react';

/**
 * Coach Weekly Signal Card - Step 8
 * 
 * Displays breakthrough/plateau detection signal on Home page.
 * Shows only if user has >= 10 analyzed games.
 */

const STATE_CONFIG = {
  BREAKTHROUGH: {
    icon: Sparkles,
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/30',
    iconColor: 'text-emerald-400',
    accentColor: 'text-emerald-300',
  },
  PLATEAU: {
    icon: Target,
    bgColor: 'bg-amber-500/10',
    borderColor: 'border-amber-500/30',
    iconColor: 'text-amber-400',
    accentColor: 'text-amber-300',
  },
  CONFIDENCE_ILLUSION: {
    icon: AlertTriangle,
    bgColor: 'bg-orange-500/10',
    borderColor: 'border-orange-500/30',
    iconColor: 'text-orange-400',
    accentColor: 'text-orange-300',
  },
  TILT_RISK: {
    icon: TrendingDown,
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500/30',
    iconColor: 'text-red-400',
    accentColor: 'text-red-300',
  },
  STABLE_GROWTH: {
    icon: TrendingUp,
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/30',
    iconColor: 'text-blue-400',
    accentColor: 'text-blue-300',
  },
  NORMAL: {
    icon: ChevronRight,
    bgColor: 'bg-slate-500/10',
    borderColor: 'border-slate-500/30',
    iconColor: 'text-slate-400',
    accentColor: 'text-slate-300',
  },
};

const CoachWeeklySignalCard = ({ signal, onCtaClick }) => {
  // Don't render if no signal or shouldn't show card
  if (!signal || !signal.show_card) {
    return null;
  }

  const config = STATE_CONFIG[signal.state] || STATE_CONFIG.NORMAL;
  const Icon = config.icon;

  const handleCtaClick = () => {
    if (onCtaClick) {
      onCtaClick(signal.cta);
    }
  };

  return (
    <Card 
      className={`${config.bgColor} ${config.borderColor} border backdrop-blur-sm`}
      data-testid="coach-weekly-signal-card"
    >
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          {/* Icon */}
          <div className={`p-2 rounded-lg ${config.bgColor}`}>
            <Icon className={`w-5 h-5 ${config.iconColor}`} />
          </div>
          
          {/* Content */}
          <div className="flex-1 min-w-0">
            {/* Title */}
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-1">
              Coach Weekly Signal
            </p>
            
            {/* Headline */}
            <h3 className={`text-sm font-semibold ${config.accentColor} mb-1`}>
              {signal.headline}
            </h3>
            
            {/* Message */}
            <p className="text-xs text-slate-300 leading-relaxed mb-3">
              {signal.message}
            </p>
            
            {/* CTA Button */}
            <Button
              variant="outline"
              size="sm"
              onClick={handleCtaClick}
              className={`${config.borderColor} ${config.accentColor} hover:${config.bgColor} text-xs`}
              data-testid="coach-signal-cta"
            >
              {signal.cta?.label || 'Continue'}
              <ChevronRight className="w-3 h-3 ml-1" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default CoachWeeklySignalCard;
