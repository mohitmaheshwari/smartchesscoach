/**
 * CoachChat - Chat interface with the coach during games
 * 
 * Allows users to ask questions and get personalized coaching responses.
 */

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { 
  MessageCircle, 
  Send, 
  Loader2,
  Brain,
  User,
  Sparkles
} from "lucide-react";
import { API } from "@/App";
import { toast } from "sonner";
import { InlineFlag } from "@/components/shared/FlagMoveDialog";

const CoachChat = ({ sessionId, disabled = false, gameId, fen }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const messagesEndRef = useRef(null);
  
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  
  useEffect(() => {
    scrollToBottom();
  }, [messages]);
  
  const sendMessage = async () => {
    if (!input.trim() || !sessionId || sending) return;
    
    const userMessage = input.trim();
    setInput("");
    setSending(true);
    
    // Add user message immediately
    setMessages(prev => [...prev, {
      role: "user",
      content: userMessage,
      timestamp: new Date().toISOString()
    }]);
    
    try {
      const res = await fetch(`${API}/coach/play/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: sessionId,
          message: userMessage
        })
      });
      
      if (res.ok) {
        const data = await res.json();
        
        // Add coach response
        setMessages(prev => [...prev, {
          role: "coach",
          content: data.response,
          suggestion: data.suggestion_arrow,
          insight: data.personal_insight,
          plan: data.position_plan,
          timestamp: new Date().toISOString()
        }]);
      } else {
        throw new Error("Failed to get response");
      }
    } catch (err) {
      console.error("Chat error:", err);
      toast.error("Coach didn't respond. Try again.");
      
      // Add error message
      setMessages(prev => [...prev, {
        role: "coach",
        content: "Couldn't process that — try again.",
        isError: true,
        timestamp: new Date().toISOString()
      }]);
    } finally {
      setSending(false);
    }
  };
  
  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };
  
  if (!isOpen) {
    return (
      <Button
        variant="outline"
        size="sm"
        className="fixed bottom-4 right-4 z-40"
        onClick={() => setIsOpen(true)}
        disabled={disabled || !sessionId}
        data-testid="coach-chat-toggle"
      >
        <MessageCircle className="w-4 h-4 mr-2" />
        Ask Coach
      </Button>
    );
  }
  
  return (
    <Card className="fixed bottom-4 right-4 w-80 max-h-[400px] z-40 flex flex-col">
      <CardHeader className="py-2 px-3 border-b flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Brain className="w-4 h-4 text-primary" />
            <CardTitle className="text-sm">Ask Coach</CardTitle>
          </div>
          <Button 
            variant="ghost" 
            size="icon" 
            className="h-6 w-6"
            onClick={() => setIsOpen(false)}
          >
            ×
          </Button>
        </div>
      </CardHeader>
      
      <CardContent className="flex-1 overflow-y-auto p-3 space-y-3 min-h-[200px]">
        {messages.length === 0 && (
          <div className="text-center text-muted-foreground text-sm py-8">
            <Sparkles className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>Ask me anything about the position!</p>
            <p className="text-xs mt-1">Try: "What should I do here?"</p>
          </div>
        )}
        
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "coach" && (
              <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                <Brain className="w-3 h-3 text-primary" />
              </div>
            )}
            
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                msg.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : msg.isError
                  ? "bg-red-500/10 text-red-400"
                  : "bg-muted"
              }`}
            >
              <p className="group">
                {msg.content}
                {msg.role === "coach" && !msg.isError && (
                  <InlineFlag
                    section="coach_chat_response"
                    flaggedText={msg.content}
                    context={{
                      source: "play_with_coach",
                      sessionId, gameId, fen: fen || "",
                      component: "CoachChat",
                    }}
                  />
                )}
              </p>

              {msg.insight && (
                <p className="group mt-2 text-xs opacity-80 italic">
                  💡 {msg.insight}
                  <InlineFlag
                    section="coach_chat_insight"
                    flaggedText={msg.insight}
                    context={{
                      source: "play_with_coach",
                      sessionId, gameId, fen: fen || "",
                      component: "CoachChat",
                    }}
                  />
                </p>
              )}

              {msg.plan && (
                <p className="group mt-2 text-xs opacity-80">
                  📋 Plan: {msg.plan}
                  <InlineFlag
                    section="coach_chat_plan"
                    flaggedText={msg.plan}
                    context={{
                      source: "play_with_coach",
                      sessionId, gameId, fen: fen || "",
                      component: "CoachChat",
                    }}
                  />
                </p>
              )}
            </div>
            
            {msg.role === "user" && (
              <div className="w-6 h-6 rounded-full bg-muted flex items-center justify-center flex-shrink-0">
                <User className="w-3 h-3" />
              </div>
            )}
          </div>
        ))}
        
        {sending && (
          <div className="flex gap-2">
            <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center">
              <Brain className="w-3 h-3 text-primary animate-pulse" />
            </div>
            <div className="bg-muted rounded-lg px-3 py-2">
              <Loader2 className="w-4 h-4 animate-spin" />
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </CardContent>
      
      <div className="p-2 border-t flex-shrink-0">
        <div className="flex gap-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about the position..."
            className="min-h-[36px] max-h-[80px] text-sm resize-none"
            disabled={sending || disabled}
            data-testid="coach-chat-input"
          />
          <Button
            size="icon"
            onClick={sendMessage}
            disabled={!input.trim() || sending || disabled}
            data-testid="coach-chat-send"
          >
            {sending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </Button>
        </div>
      </div>
    </Card>
  );
};

export default CoachChat;
