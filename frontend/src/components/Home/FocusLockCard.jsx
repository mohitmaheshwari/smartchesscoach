import React from 'react';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { 
  Lock, 
  AlertTriangle, 
  CheckCircle2, 
  ChevronRight,
  Target,
  Flame
} from 'lucide-react';

/**
 * Focus Lock Card - Step 9
 * 
 * Displays when a focus lock is active.
 * OVERRIDES Weekly Signal and Breakthrough cards.
 * Reinforces coaching authority through visual hierarchy.
 */

const STATE_CONFIG = {
  ACTIVE: {
    icon: Lock,
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/30',
    iconColor: 'text-blue-400',
    accentColor: 'text-blue-300',
    progressColor: 'bg-blue-500',
  },
  EXTENDED: {
    icon: Target,
    bgColor: 'bg-amber-500/10',
    borderColor: 'border-amber-500/30',
    iconColor: 'text-amber-400',
    accentColor: 'text-amber-300',
    progressColor: 'bg-amber-500',
  },
  STRICT: {
    icon: Flame,
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500/30',
    iconColor: 'text-red-400',
    accentColor: 'text-red-300',
    progressColor: 'bg-red-500',
  },
  COMPLETED: {
    icon: CheckCircle2,
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/30',
    iconColor: 'text-emerald-400',
    accentColor: 'text-emerald-300',
    progressColor: 'bg-emerald-500',
  },
  FAILED: {
    icon: AlertTriangle,
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500/30',
    iconColor: 'text-red-400',
    accentColor: 'text-red-300',
    progressColor: 'bg-red-500',
  },
};

const FocusLockCard = ({ lock, onCtaClick, onDeepSessionClick }) => {
  // Don't render if no lock or lock not active
  if (!lock || !lock.active) {
    return null;
  }

  const config = STATE_CONFIG[lock.state] || STATE_CONFIG.ACTIVE;
  const Icon = config.icon;

  const handleCtaClick = () => {
    if (lock.should_trigger_deep_session && onDeepSessionClick) {
      onDeepSessionClick();
    } else if (onCtaClick) {
      onCtaClick();
    }
  };

  // Calculate progress percentage
  const progressPercent = lock.progress 
    ? (lock.progress.completed / lock.progress.required) * 100 
    : 0;

  // Get compliance color
  const complianceColor = {
    green: 'text-emerald-400',
    yellow: 'text-amber-400',
    red: 'text-red-400',
  }[lock.compliance?.color] || 'text-slate-400';

  return (
    <Card 
      className={`${config.bgColor} ${config.borderColor} border backdrop-blur-sm`}
      data-testid="focus-lock-card"
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
            <div className="flex items-center gap-2 mb-1">
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wide">
                Focus Lock
              </p>
              {lock.strict_mode && (
                <span className="px-1.5 py-0.5 text-[10px] font-medium bg-red-500/20 text-red-400 rounded">
                  STRICT
                </span>
              )}
            </div>
            
            {/* Headline */}
            <h3 className={`text-sm font-semibold ${config.accentColor} mb-1`}>
              {lock.headline}
            </h3>
            
            {/* Rule Description */}
            <p className="text-xs text-slate-300 mb-2">
              {lock.rule_description}
            </p>
            
            {/* Progress Bar */}
            <div className="mb-2">
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>{lock.progress?.text || `${lock.progress?.completed || 0} of ${lock.progress?.required || 5} games`}</span>
                <span className={complianceColor}>{lock.compliance?.text || ''}</span>
              </div>
              <div className="h-2 bg-slate-700/50 rounded-full overflow-hidden">
                <div 
                  className={`h-full ${config.progressColor} transition-all duration-500`}
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
            </div>
            
            {/* Message */}
            <p className="text-xs text-slate-300 leading-relaxed mb-3">
              {lock.message}
            </p>
            
            {/* CTA Button */}
            <Button
              variant="outline"
              size="sm"
              onClick={handleCtaClick}
              className={`${config.borderColor} ${config.accentColor} hover:${config.bgColor} text-xs`}
              data-testid="focus-lock-cta"
            >
              {lock.should_trigger_deep_session ? 'Start Deep Session' : (lock.cta || 'Start Next Game')}
              <ChevronRight className="w-3 h-3 ml-1" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default FocusLockCard;
