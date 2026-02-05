import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { 
  BookOpen, 
  AlertTriangle,
  Target,
  Loader2,
  ChevronDown,
  ChevronUp,
  GraduationCap,
  Lightbulb,
  CheckCircle2,
  XCircle,
  ArrowRight
} from "lucide-react";
import InteractiveChessBoard from "./InteractiveChessBoard";

// Opening move sequences for interactive board
const OPENING_MOVES = {
  "Italian Game": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "c3", "Nf6", "d4", "exd4", "cxd4", "Bb4+"],
  "Ruy Lopez": ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6", "O-O", "Be7", "Re1", "b5", "Bb3", "d6"],
  "French Defense": ["e4", "e6", "d4", "d5", "e5", "c5", "c3", "Nc6", "Nf3", "Qb6", "Be2", "cxd4", "cxd4"],
  "Caro-Kann Defense": ["e4", "c6", "d4", "d5", "e5", "Bf5", "Nf3", "e6", "Be2", "Nd7", "O-O", "Ne7"],
  "Sicilian Defense": ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"],
  "Sicilian Alapin": ["e4", "c5", "c3", "d5", "exd5", "Qxd5", "d4", "Nc6", "Nf3", "Bg4", "Be2"],
  "Queen's Gambit": ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Be7", "e3", "O-O", "Nf3", "h6", "Bh4"],
  "London System": ["d4", "d5", "Bf4", "Nf6", "e3", "c5", "c3", "Nc6", "Nd2", "e6", "Ngf3", "Bd6", "Bg3"],
  "Scandinavian Defense": ["e4", "d5", "exd5", "Qxd5", "Nc3", "Qa5", "d4", "Nf6", "Nf3", "Bf5", "Bc4", "e6"],
  "King's Indian Defense": ["d4", "Nf6", "c4", "g6", "Nc3", "Bg7", "e4", "d6", "Nf3", "O-O", "Be2", "e5"],
  "Nimzo-Indian Defense": ["d4", "Nf6", "c4", "e6", "Nc3", "Bb4", "Qc2", "O-O", "a3", "Bxc3+", "Qxc3", "d5"],
  "Open Game": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"],
  "Closed Game": ["d4", "d5", "c4", "e6", "Nc3", "Nf6"],
};

// Helper functions
const getWinRateColor = (rate) => {
  if (rate >= 60) return "text-green-500";
  if (rate >= 40) return "text-amber-500";
  return "text-red-500";
};

// Get moves for an opening
const getOpeningMoves = (openingName) => {
  // Try exact match
  if (OPENING_MOVES[openingName]) return OPENING_MOVES[openingName];
  
  // Try partial match
  for (const [name, moves] of Object.entries(OPENING_MOVES)) {
    if (openingName.toLowerCase().includes(name.toLowerCase()) ||
        name.toLowerCase().includes(openingName.toLowerCase())) {
      return moves;
    }
  }
  
  // Default basic moves
  return ["e4", "e5", "Nf3", "Nc6"];
};

// Opening Card Component
const OpeningCard = ({ opening, color, onLearnMore }) => (
  <div className="p-3 rounded-lg bg-card border border-border/50 hover:border-border transition-colors">
    <div className="flex items-start justify-between gap-2">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${color === 'white' ? 'bg-zinc-100' : 'bg-zinc-800 border border-zinc-600'}`} />
          <h4 className="font-medium text-sm truncate">{opening.name}</h4>
        </div>
        <div className="flex items-center gap-3 mt-1.5 text-xs text-muted-foreground">
          <span>{opening.games_played} games</span>
          <span className="text-green-500">{opening.wins}W</span>
          <span className="text-red-500">{opening.losses}L</span>
          {opening.draws > 0 && <span className="text-zinc-500">{opening.draws}D</span>}
        </div>
      </div>
      
      <div className="text-right">
        <div className={`text-lg font-bold ${getWinRateColor(opening.win_rate)}`}>
          {opening.win_rate}%
        </div>
        <div className="text-[10px] text-muted-foreground">win rate</div>
      </div>
    </div>
    
    {/* Coaching Tips Preview */}
    {opening.coaching && (
      <div className="mt-3 pt-3 border-t border-border/50">
        <div className="text-xs text-muted-foreground mb-1">Simple Plan:</div>
        <div className="text-xs text-primary font-medium">{opening.coaching.simple_plan}</div>
        
        {opening.win_rate < 40 && (
          <Button 
            variant="ghost" 
            size="sm" 
            className="mt-2 h-7 text-xs text-amber-500 hover:text-amber-400 p-0"
            onClick={() => onLearnMore(opening)}
          >
            <GraduationCap className="w-3 h-3 mr-1" />
            Learn how to fix this
            <ArrowRight className="w-3 h-3 ml-1" />
          </Button>
        )}
      </div>
    )}
  </div>
);

// Detailed Lesson Modal/Card
const OpeningLesson = ({ lesson, onClose }) => {
  const openingMoves = getOpeningMoves(lesson.opening);
  const flipBoard = lesson.color === 'black';
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60"
      onClick={onClose}
    >
      <div 
        className="bg-background rounded-xl border border-border max-w-2xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-4 border-b border-border bg-gradient-to-r from-amber-500/10 to-orange-500/10">
          <div className="flex items-center gap-2 text-amber-500 text-sm font-medium mb-1">
            <GraduationCap className="w-4 h-4" />
            Coach&apos;s Lesson
          </div>
          <h2 className="text-xl font-bold">{lesson.opening}</h2>
          <div className="flex items-center gap-2 mt-1 text-sm text-muted-foreground">
            <span className={`w-2 h-2 rounded-full ${lesson.color === 'white' ? 'bg-zinc-100' : 'bg-zinc-800 border border-zinc-600'}`} />
            Playing as {lesson.color}
            <span className="text-red-500 ml-2">{lesson.win_rate}% win rate</span>
          </div>
        </div>
        
        {/* Interactive Board Section */}
        <div className="p-4 bg-zinc-900/50 border-b border-border">
          <div className="flex items-center gap-2 mb-3 text-sm font-medium text-amber-400">
            <Target className="w-4 h-4" />
            Watch the Opening Moves
          </div>
          <div className="flex justify-center">
            <InteractiveChessBoard
              moves={openingMoves}
              size={280}
              autoPlay={false}
              autoPlaySpeed={1200}
              showMoveList={true}
              flipBoard={flipBoard}
            />
          </div>
          <p className="text-xs text-center text-muted-foreground mt-3">
            Use the controls to step through each move, or press play to watch automatically
          </p>
        </div>
        
        {/* Coach Intro */}
        <div className="p-4 bg-muted/30">
          <p className="text-sm italic text-foreground/80">&quot;{lesson.coach_intro}&quot;</p>
        </div>
        
        {/* Main Content */}
        <div className="p-4 space-y-4">
          {/* Key Moves - Text version */}
          <div>
            <h3 className="text-sm font-semibold flex items-center gap-2 mb-2">
              <Target className="w-4 h-4 text-primary" />
              Key Moves (Notation)
            </h3>
            <div className="bg-zinc-900 rounded-lg p-3 font-mono text-sm text-amber-400">
              {lesson.key_moves}
            </div>
          </div>
        
        {/* Main Idea */}
        <div>
          <h3 className="text-sm font-semibold flex items-center gap-2 mb-2">
            <Lightbulb className="w-4 h-4 text-yellow-500" />
            Main Idea
          </h3>
          <p className="text-sm text-foreground/80">{lesson.main_idea}</p>
        </div>
        
        {/* Must Know */}
        {lesson.must_know?.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold flex items-center gap-2 mb-2">
              <CheckCircle2 className="w-4 h-4 text-green-500" />
              You MUST Know This
            </h3>
            <ul className="space-y-2">
              {lesson.must_know.map((item, idx) => (
                <li key={idx} className="flex items-start gap-2 text-sm">
                  <span className="text-green-500 mt-0.5">✓</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        
        {/* Common Mistakes & Fixes */}
        {lesson.common_mistakes?.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold flex items-center gap-2 mb-2">
              <XCircle className="w-4 h-4 text-red-500" />
              Common Mistakes & How to Fix
            </h3>
            <div className="space-y-2">
              {lesson.common_mistakes.map((m, idx) => (
                <div key={idx} className="bg-red-500/5 border border-red-500/20 rounded-lg p-3">
                  <div className="flex items-start gap-2">
                    <span className="text-red-500 text-xs font-medium">MISTAKE:</span>
                    <span className="text-sm">{m.mistake}</span>
                  </div>
                  <div className="flex items-start gap-2 mt-1.5">
                    <span className="text-green-500 text-xs font-medium">FIX:</span>
                    <span className="text-sm text-green-400">{m.fix}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Simple Plan */}
        <div className="bg-gradient-to-r from-primary/10 to-primary/5 rounded-lg p-4">
          <h3 className="text-sm font-semibold mb-2">📋 Simple Plan to Follow</h3>
          <p className="text-base font-medium text-primary">{lesson.simple_plan}</p>
        </div>
        
        {/* Homework */}
        <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-amber-500 mb-2">📝 Your Homework</h3>
          <p className="text-sm">{lesson.homework}</p>
        </div>
        
        {/* Practice Tip */}
        {lesson.practice_tip && (
          <div className="text-sm text-muted-foreground italic">
            💡 Tip: {lesson.practice_tip}
          </div>
        )}
      </div>
      
      {/* Footer */}
      <div className="p-4 border-t border-border">
        <Button onClick={onClose} className="w-full">
          Got it, Coach! 
        </Button>
      </div>
    </div>
  </motion.div>
);

const OpeningRepertoire = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expandedWhite, setExpandedWhite] = useState(true);
  const [expandedBlack, setExpandedBlack] = useState(true);
  const [selectedLesson, setSelectedLesson] = useState(null);

  useEffect(() => {
    fetchRepertoire();
  }, []);

  const fetchRepertoire = async () => {
    try {
      const res = await fetch(`${API}/openings/repertoire`, { credentials: "include" });
      if (res.ok) {
        setData(await res.json());
      }
    } catch (e) {
      console.error("Failed to fetch opening repertoire:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleLearnMore = (opening) => {
    // Find lesson for this opening
    const lesson = data?.opening_lessons?.find(l => l.opening === opening.name);
    if (lesson) {
      setSelectedLesson(lesson);
    } else if (opening.coaching) {
      // Create a lesson from coaching data
      setSelectedLesson({
        opening: opening.name,
        color: opening.coaching.color || "white",
        win_rate: opening.win_rate,
        coach_intro: `Let me teach you how to improve your ${opening.name}. With the right approach, you can turn this around!`,
        key_moves: opening.coaching.key_moves,
        main_idea: opening.coaching.main_idea,
        must_know: opening.coaching.must_know,
        common_mistakes: opening.coaching.common_mistakes,
        simple_plan: opening.coaching.simple_plan,
        practice_tip: opening.coaching.practice_tip,
        homework: `Play 5 games with ${opening.name} focusing on: ${opening.coaching.simple_plan}`,
      });
    }
  };

  if (loading) {
    return (
      <Card className="border-border/50">
        <CardContent className="py-12 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (!data?.has_data) {
    return (
      <Card className="border-border/50">
        <CardContent className="py-8 text-center">
          <BookOpen className="w-10 h-10 mx-auto mb-3 text-muted-foreground/50" />
          <p className="text-muted-foreground">Import and analyze games to see your opening repertoire</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Opening Lessons - Show first if there are problem openings */}
      {data.opening_lessons?.length > 0 && (
        <Card className="border-amber-500/30 bg-gradient-to-r from-amber-500/5 to-orange-500/5">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <GraduationCap className="w-5 h-5 text-amber-500" />
              Coach&apos;s Lessons for You
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="space-y-3">
              {data.opening_lessons.map((lesson, idx) => (
                <div 
                  key={idx} 
                  className="p-4 rounded-lg bg-background border border-border cursor-pointer hover:border-amber-500/50 transition-colors"
                  onClick={() => setSelectedLesson(lesson)}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${lesson.color === 'white' ? 'bg-zinc-100' : 'bg-zinc-800 border border-zinc-600'}`} />
                        <h4 className="font-semibold">{lesson.opening}</h4>
                        <Badge variant="destructive" className="text-[10px]">{lesson.win_rate}% win</Badge>
                      </div>
                      <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                        {lesson.diagnosis || lesson.coach_intro}
                      </p>
                    </div>
                    <Button variant="ghost" size="sm" className="text-amber-500">
                      Learn <ArrowRight className="w-3 h-3 ml-1" />
                    </Button>
                  </div>
                  
                  {/* Quick preview of simple plan */}
                  <div className="mt-3 p-2 bg-muted/50 rounded text-xs">
                    <span className="text-muted-foreground">Simple plan: </span>
                    <span className="text-primary font-medium">{lesson.simple_plan}</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Coaching Focus Banner */}
      {data.coaching_focus && data.coaching_focus.area !== "maintain" && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-4 rounded-xl bg-gradient-to-r from-amber-500/10 to-orange-500/10 border border-amber-500/20"
        >
          <div className="flex items-start gap-3">
            <Target className="w-5 h-5 text-amber-500 mt-0.5" />
            <div>
              <h3 className="font-semibold text-sm text-amber-500">Coach&apos;s Focus Area</h3>
              <p className="text-sm text-foreground/80 mt-1">{data.coaching_focus.message}</p>
            </div>
          </div>
        </motion.div>
      )}

      {/* Problem Openings Alert */}
      {data.problem_openings?.length > 0 && !data.opening_lessons?.length && (
        <Card className="border-red-500/20 bg-red-500/5">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-500" />
              Problem Openings
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="space-y-2">
              {data.problem_openings.map((problem, idx) => (
                <div key={idx} className="flex items-center justify-between p-2 rounded bg-background/50">
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${problem.color === 'white' ? 'bg-zinc-100' : 'bg-zinc-800 border border-zinc-600'}`} />
                    <span className="text-sm font-medium">{problem.name}</span>
                  </div>
                  <span className="text-xs text-red-500">{problem.message}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stats Overview */}
      <div className="grid grid-cols-3 gap-3">
        <div className="p-3 rounded-lg bg-card border border-border/50 text-center">
          <div className="text-2xl font-bold">{data.total_games}</div>
          <div className="text-xs text-muted-foreground">Total Games</div>
        </div>
        <div className="p-3 rounded-lg bg-card border border-border/50 text-center">
          <div className="text-2xl font-bold">{data.games_as_white}</div>
          <div className="text-xs text-muted-foreground">As White</div>
        </div>
        <div className="p-3 rounded-lg bg-card border border-border/50 text-center">
          <div className="text-2xl font-bold">{data.games_as_black}</div>
          <div className="text-xs text-muted-foreground">As Black</div>
        </div>
      </div>

      {/* White Repertoire */}
      <Card className="border-border/50">
        <CardHeader 
          className="pb-3 cursor-pointer"
          onClick={() => setExpandedWhite(!expandedWhite)}
        >
          <CardTitle className="text-base flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-zinc-100 border border-zinc-300" />
              White Repertoire
              <Badge variant="outline" className="text-xs ml-2">
                {data.white_repertoire?.length || 0} openings
              </Badge>
            </div>
            {expandedWhite ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </CardTitle>
        </CardHeader>
        {expandedWhite && (
          <CardContent className="pt-0">
            <div className="space-y-2">
              {data.white_repertoire?.map((opening, idx) => (
                <OpeningCard 
                  key={idx} 
                  opening={opening} 
                  color="white" 
                  onLearnMore={handleLearnMore}
                />
              ))}
            </div>
          </CardContent>
        )}
      </Card>

      {/* Black Repertoire */}
      <Card className="border-border/50">
        <CardHeader 
          className="pb-3 cursor-pointer"
          onClick={() => setExpandedBlack(!expandedBlack)}
        >
          <CardTitle className="text-base flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-zinc-800 border border-zinc-600" />
              Black Repertoire
              <Badge variant="outline" className="text-xs ml-2">
                {data.black_repertoire?.length || 0} openings
              </Badge>
            </div>
            {expandedBlack ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </CardTitle>
        </CardHeader>
        {expandedBlack && (
          <CardContent className="pt-0">
            <div className="space-y-2">
              {data.black_repertoire?.map((opening, idx) => (
                <OpeningCard 
                  key={idx} 
                  opening={opening} 
                  color="black" 
                  onLearnMore={handleLearnMore}
                />
              ))}
            </div>
          </CardContent>
        )}
      </Card>

      {/* Lesson Modal */}
      <AnimatePresence>
        {selectedLesson && (
          <OpeningLesson 
            lesson={selectedLesson} 
            onClose={() => setSelectedLesson(null)} 
          />
        )}
      </AnimatePresence>
    </div>
  );
};

export default OpeningRepertoire;
