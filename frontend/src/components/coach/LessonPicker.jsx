/**
 * LessonPicker — In-game lesson browser for Play with Coach
 *
 * Shows available lessons: Traps, Endgames (with opening lessons handled by existing flow).
 * Appears in the coaching sidebar when user has an active session.
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Swords,
  BookOpen,
  ChevronRight,
  Crown,
  Loader2,
  X,
  Zap,
} from "lucide-react";

const difficultyColors = {
  beginner: "bg-emerald-500/10 text-emerald-600 border-emerald-500/20",
  intermediate: "bg-amber-500/10 text-amber-600 border-amber-500/20",
  advanced: "bg-red-500/10 text-red-500 border-red-500/20",
};

const LessonPicker = ({ sessionId, onStartLesson, onClose }) => {
  const [catalog, setCatalog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(null);
  const [activeTab, setActiveTab] = useState("traps");

  useEffect(() => {
    fetch(`${API}/coach/play/teaching/catalog`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        setCatalog(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const handleStart = async (lessonType, params) => {
    setStarting(params.trap_key || params.lesson_key || "loading");
    try {
      const res = await fetch(`${API}/coach/play/teaching/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: sessionId,
          lesson_type: lessonType,
          ...params,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        onStartLesson(data);
      }
    } catch (e) {
      console.error("Failed to start lesson:", e);
    } finally {
      setStarting(null);
    }
  };

  if (loading) {
    return (
      <div className="p-4 flex items-center justify-center gap-2 text-muted-foreground">
        <Loader2 className="w-4 h-4 animate-spin" />
        <span className="text-sm">Loading lessons...</span>
      </div>
    );
  }

  if (!catalog) return null;

  const tabs = [
    { key: "traps", label: "Traps", icon: Zap, count: catalog.traps?.length || 0 },
    { key: "endgames", label: "Endgames", icon: Crown, count: catalog.endgames?.length || 0 },
  ];

  return (
    <div className="flex flex-col h-full" data-testid="lesson-picker">
      {/* Header */}
      <div className="p-3 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-primary" />
          <span className="text-sm font-medium">Lesson Library</span>
        </div>
        <button
          onClick={onClose}
          className="text-muted-foreground hover:text-foreground"
          data-testid="close-lesson-picker"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex-1 px-3 py-2 text-xs font-medium flex items-center justify-center gap-1.5 transition-colors ${
              activeTab === tab.key
                ? "text-primary border-b-2 border-primary"
                : "text-muted-foreground hover:text-foreground"
            }`}
            data-testid={`tab-${tab.key}`}
          >
            <tab.icon className="w-3.5 h-3.5" />
            {tab.label}
            <Badge variant="secondary" className="text-[10px] px-1 py-0 h-4">
              {tab.count}
            </Badge>
          </button>
        ))}
      </div>

      {/* Lesson List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
        {activeTab === "traps" &&
          catalog.traps?.map((trap) => (
            <button
              key={trap.key}
              onClick={() => handleStart("trap", { trap_key: trap.key })}
              disabled={starting === trap.key}
              className="w-full text-left p-3 rounded-lg border border-border hover:border-primary/30 hover:bg-primary/5 transition-all group"
              data-testid={`trap-${trap.key}`}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <Zap className="w-3.5 h-3.5 text-amber-500" />
                  <span className="text-sm font-medium group-hover:text-primary transition-colors">
                    {trap.name}
                  </span>
                </div>
                {starting === trap.key ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" />
                ) : (
                  <ChevronRight className="w-3.5 h-3.5 text-muted-foreground group-hover:text-primary" />
                )}
              </div>
              <div className="flex items-center gap-2 mt-1">
                {trap.opening && (
                  <span className="text-[10px] text-muted-foreground">
                    {trap.opening}
                  </span>
                )}
                <Badge
                  variant="outline"
                  className={`text-[10px] ${difficultyColors[trap.difficulty] || ""}`}
                >
                  {trap.difficulty}
                </Badge>
                {trap.tactical_theme && (
                  <Badge variant="outline" className="text-[10px]">
                    {trap.tactical_theme}
                  </Badge>
                )}
              </div>
            </button>
          ))}

        {activeTab === "endgames" &&
          catalog.endgames?.map((eg) => (
            <button
              key={`${eg.category}-${eg.lesson_key}`}
              onClick={() =>
                handleStart("endgame", {
                  category: eg.category,
                  lesson_key: eg.lesson_key,
                })
              }
              disabled={starting === eg.lesson_key}
              className="w-full text-left p-3 rounded-lg border border-border hover:border-primary/30 hover:bg-primary/5 transition-all group"
              data-testid={`endgame-${eg.lesson_key}`}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <Crown className="w-3.5 h-3.5 text-purple-500" />
                  <span className="text-sm font-medium group-hover:text-primary transition-colors">
                    {eg.name}
                  </span>
                </div>
                {starting === eg.lesson_key ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" />
                ) : (
                  <ChevronRight className="w-3.5 h-3.5 text-muted-foreground group-hover:text-primary" />
                )}
              </div>
              <p className="text-[11px] text-muted-foreground line-clamp-1 mt-0.5">
                {eg.rule || eg.description}
              </p>
              <div className="flex items-center gap-2 mt-1">
                <Badge variant="outline" className="text-[10px]">
                  {eg.category_name}
                </Badge>
                <span className="text-[10px] text-muted-foreground">
                  {eg.positions_count} position{eg.positions_count !== 1 ? "s" : ""}
                </span>
              </div>
            </button>
          ))}
      </div>
    </div>
  );
};

export default LessonPicker;
