/**
 * AskCoach - Contextual chat input with smart prompts
 * 
 * Suggested quick actions + freeform input
 * Smart prompts are better than a blank chat box
 */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Send, HelpCircle, Target, Lightbulb, Eye, MessageCircle } from "lucide-react";

// Smart prompts based on game context
const SMART_PROMPTS = [
  { id: "explain", label: "Explain my position", icon: Eye, isSpecial: true },
  { id: "why", label: "Why was that better?", icon: HelpCircle },
  { id: "plan", label: "What's my plan?", icon: Target },
  { id: "tactic", label: "Did I miss a tactic?", icon: Lightbulb },
];

// Plan-first prompts - user states intention before moving
const PLAN_PROMPTS = [
  { id: "attack", label: "I want to attack the king", icon: Target },
  { id: "develop", label: "I want to develop my pieces", icon: Lightbulb },
  { id: "defend", label: "I need to defend", icon: Eye },
  { id: "trade", label: "Should I trade pieces?", icon: HelpCircle },
];

const AskCoach = ({ 
  onSendMessage,
  disabled = false,
  placeholder = "Ask the coach anything...",
  showPrompts = true,
  compactMode = false,
  planFirstMode = false  // New: Show plan-first prompts
}) => {
  const [message, setMessage] = useState("");
  const [showInput, setShowInput] = useState(false);
  
  const handleSend = () => {
    if (!message.trim()) return;
    onSendMessage(message);
    setMessage("");
    setShowInput(false);
  };
  
  const handlePromptClick = (prompt) => {
    onSendMessage(prompt.label);
  };
  
  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };
  
  // Compact mode - just shows prompts inline
  if (compactMode) {
    return (
      <div className="space-y-2">
        {showPrompts && (
          <div className="flex flex-wrap gap-1">
            {SMART_PROMPTS.slice(0, 3).map(prompt => (
              <Button
                key={prompt.id}
                variant="ghost"
                size="sm"
                className="h-7 text-xs"
                onClick={() => handlePromptClick(prompt)}
                disabled={disabled}
              >
                <prompt.icon className="w-3 h-3 mr-1" />
                {prompt.label}
              </Button>
            ))}
          </div>
        )}
      </div>
    );
  }
  
  return (
    <div className="space-y-2">
      {/* Plan-first prompts - state your intention before moving */}
      {planFirstMode && showPrompts && !showInput && (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">What do you want to do?</p>
          <div className="flex flex-wrap gap-1">
            {PLAN_PROMPTS.map(prompt => (
              <Button
                key={prompt.id}
                variant="ghost"
                size="sm"
                className="h-7 text-xs"
                onClick={() => handlePromptClick(prompt)}
                disabled={disabled}
              >
                <prompt.icon className="w-3 h-3 mr-1" />
                {prompt.label}
              </Button>
            ))}
          </div>
        </div>
      )}
      
      {/* Smart prompts */}
      {!planFirstMode && showPrompts && !showInput && (
        <div className="flex flex-wrap gap-1">
          {SMART_PROMPTS.map(prompt => (
            <Button
              key={prompt.id}
              variant="ghost"
              size="sm"
              className="h-7 text-xs"
              onClick={() => handlePromptClick(prompt)}
              disabled={disabled}
            >
              <prompt.icon className="w-3 h-3 mr-1" />
              {prompt.label}
            </Button>
          ))}
        </div>
      )}
      
      {/* Text input - shown on click or always */}
      {showInput ? (
        <div className="flex gap-2">
          <Textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            className="min-h-[60px] text-sm resize-none"
            disabled={disabled}
            autoFocus
          />
          <div className="flex flex-col gap-1">
            <Button
              size="sm"
              onClick={handleSend}
              disabled={disabled || !message.trim()}
              className="h-8"
            >
              <Send className="w-4 h-4" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setShowInput(false)}
              className="h-8 text-xs"
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <Button
          variant="outline"
          size="sm"
          className="w-full h-8 text-xs justify-start text-muted-foreground"
          onClick={() => setShowInput(true)}
          disabled={disabled}
        >
          <MessageCircle className="w-3 h-3 mr-2" />
          Type a question...
        </Button>
      )}
    </div>
  );
};

export default AskCoach;
