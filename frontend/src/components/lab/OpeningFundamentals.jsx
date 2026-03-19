/**
 * OpeningFundamentals - Shows opening principle analysis
 * 
 * This teaches the THINKING PROCESS, not just answers:
 * - What principles were followed/violated
 * - What to THINK before each move
 * - The habit to build
 */

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { 
  CheckCircle2, 
  AlertTriangle, 
  Brain, 
  ChevronDown, 
  ChevronUp,
  BookOpen,
  Target,
  Shield,
  Lightbulb
} from "lucide-react";
import { API } from "@/App";

const PRINCIPLE_ICONS = {
  same_piece_twice: "♞",
  castle_early: "♚",
  queen_out_early: "♛",
  center_control: "⊕",
  develop_minor_pieces: "♗",
  develop_before_attack: "⚔️",
  connect_rooks: "♖",
  unnecessary_pawn_moves: "♙",
  king_safety: "🛡️",
  develop_toward_center: "🎯"
};

const OpeningFundamentals = ({ gameId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expandedViolation, setExpandedViolation] = useState(null);

  useEffect(() => {
    if (!gameId) return;
    
    fetch(`${API}/analysis/${gameId}/opening-fundamentals`, { credentials: "include" })
      .then(res => res.ok ? res.json() : null)
      .then(d => {
        setData(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [gameId]);

  if (loading) {
    return (
      <div className="p-4 text-center text-muted-foreground">
        Analyzing opening principles...
      </div>
    );
  }

  if (!data || data.error) {
    return null;
  }

  const { violations, adherences, score, summary } = data;

  return (
    <div className="space-y-4" data-testid="opening-fundamentals">
      {/* Score Card */}
      <Card className={`border-l-4 ${
        score >= 80 ? 'border-l-green-500 bg-green-500/5' :
        score >= 60 ? 'border-l-yellow-500 bg-yellow-500/5' :
        'border-l-red-500 bg-red-500/5'
      }`}>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <BookOpen className={`w-5 h-5 ${
                score >= 80 ? 'text-green-500' :
                score >= 60 ? 'text-yellow-500' :
                'text-red-500'
              }`} />
              <div>
                <h3 className="font-semibold">Opening Fundamentals</h3>
                <p className="text-sm text-muted-foreground">{summary}</p>
              </div>
            </div>
            <div className={`text-2xl font-bold ${
              score >= 80 ? 'text-green-500' :
              score >= 60 ? 'text-yellow-500' :
              'text-red-500'
            }`}>
              {score}%
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Violations - Things to Improve */}
      {violations && violations.length > 0 && (
        <Card className="border-orange-500/30">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2 text-orange-400">
              <AlertTriangle className="w-4 h-4" />
              Principles to Work On
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {violations.map((v, idx) => (
              <div 
                key={idx}
                className="p-3 rounded-lg bg-orange-500/10 border border-orange-500/20"
              >
                <div 
                  className="flex items-center justify-between cursor-pointer"
                  onClick={() => setExpandedViolation(expandedViolation === idx ? null : idx)}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{PRINCIPLE_ICONS[v.principle] || "📖"}</span>
                    <div>
                      <p className="font-medium text-sm">{v.principle_name}</p>
                      <p className="text-xs text-muted-foreground">
                        Move {v.move_number}{v.move ? `: ${v.move}` : ''}
                      </p>
                    </div>
                  </div>
                  <Badge variant="outline" className={`text-xs ${
                    v.severity === 'major' ? 'border-red-500 text-red-400' :
                    v.severity === 'moderate' ? 'border-orange-500 text-orange-400' :
                    'border-yellow-500 text-yellow-400'
                  }`}>
                    {v.severity}
                  </Badge>
                </div>
                
                {expandedViolation === idx && (
                  <div className="mt-3 space-y-3 pt-3 border-t border-orange-500/20">
                    <p className="text-sm text-muted-foreground">
                      {v.explanation}
                    </p>
                    
                    {/* The key coaching part - what to THINK */}
                    <div className="p-2.5 rounded bg-blue-500/10 border border-blue-500/20">
                      <div className="flex items-start gap-2">
                        <Brain className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
                        <div>
                          <p className="text-xs font-medium text-blue-400 mb-1">
                            What to Think Before Moving:
                          </p>
                          <p className="text-sm text-blue-200">
                            {v.what_to_think}
                          </p>
                        </div>
                      </div>
                    </div>
                    
                    {v.exceptions && (
                      <p className="text-xs text-muted-foreground italic">
                        <span className="font-medium">Exceptions:</span> {v.exceptions}
                      </p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Adherences - Things Done Well */}
      {adherences && adherences.length > 0 && (
        <Card className="border-green-500/30">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2 text-green-400">
              <CheckCircle2 className="w-4 h-4" />
              Principles Followed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {adherences.map((a, idx) => (
                <div 
                  key={idx}
                  className="flex items-center gap-2 p-2 rounded bg-green-500/10"
                >
                  <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />
                  <p className="text-sm text-green-200">{a.message}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Coaching Tip */}
      <Card className="border-purple-500/30 bg-purple-500/5">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <Lightbulb className="w-5 h-5 text-purple-400 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-purple-300 mb-1">
                Coach's Advice
              </p>
              <p className="text-sm text-muted-foreground">
                {violations && violations.length > 0 
                  ? `Focus on one principle at a time. This game, work on: "${violations[0].principle_name}". Before your next game, remind yourself: "${violations[0].what_to_think}"`
                  : "Great opening play! Now challenge yourself: Try a new opening and see if you can maintain these fundamentals."
                }
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default OpeningFundamentals;
