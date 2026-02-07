import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Chessboard } from "react-chessboard";
import { 
  AlertTriangle, 
  Zap, 
  CheckCircle2,
  ChevronRight,
  Loader2,
  Trophy,
  XCircle
} from "lucide-react";

const StatsDetailModal = ({ isOpen, onClose, type }) => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (isOpen && type) {
      fetchData();
    }
  }, [isOpen, type]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const endpoint = type === "analyzed" 
        ? `${API}/games/analyzed`
        : type === "blunders"
        ? `${API}/games/blunders`
        : `${API}/games/best-moves`;
      
      const response = await fetch(endpoint, { credentials: 'include' });
      if (response.ok) {
        const result = await response.json();
        setData(result);
      }
    } catch (error) {
      console.error("Error fetching stats detail:", error);
    } finally {
      setLoading(false);
    }
  };

  const getTitle = () => {
    switch (type) {
      case "analyzed": return "Analyzed Games";
      case "blunders": return "Your Blunders";
      case "best-moves": return "Your Best Moves";
      default: return "";
    }
  };

  const getIcon = () => {
    switch (type) {
      case "analyzed": return <CheckCircle2 className="w-5 h-5 text-emerald-500" />;
      case "blunders": return <AlertTriangle className="w-5 h-5 text-red-500" />;
      case "best-moves": return <Zap className="w-5 h-5 text-amber-500" />;
      default: return null;
    }
  };

  const renderAnalyzedGames = () => (
    <div className="space-y-2 max-h-[60vh] overflow-y-auto">
      {data?.games?.map((game) => (
        <Card
          key={game.game_id}
          className="p-3 cursor-pointer hover:bg-muted/50 transition-colors"
          onClick={() => {
            onClose();
            navigate(`/game/${game.game_id}`);
          }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                game.result === "win" ? "bg-emerald-500/20" : 
                game.result === "loss" ? "bg-red-500/20" : "bg-muted"
              }`}>
                {game.result === "win" ? (
                  <Trophy className="w-4 h-4 text-emerald-500" />
                ) : game.result === "loss" ? (
                  <XCircle className="w-4 h-4 text-red-500" />
                ) : (
                  <span className="text-xs">½</span>
                )}
              </div>
              <div>
                <p className="font-medium text-sm">vs {game.opponent}</p>
                <p className="text-xs text-muted-foreground">
                  {game.accuracy}% accuracy · {game.blunders} blunders
                </p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-muted-foreground" />
          </div>
        </Card>
      ))}
      {(!data?.games || data.games.length === 0) && (
        <p className="text-center text-muted-foreground py-8">No analyzed games yet</p>
      )}
    </div>
  );

  const renderBlunders = () => (
    <div className="space-y-4 max-h-[60vh] overflow-y-auto">
      {data?.blunders?.map((blunder, idx) => (
        <Card key={idx} className="p-4">
          <div className="flex gap-4">
            {/* Mini board */}
            <div className="w-32 h-32 flex-shrink-0">
              <Chessboard
                position={blunder.fen}
                boardWidth={128}
                arePiecesDraggable={false}
                customBoardStyle={{
                  borderRadius: "4px",
                }}
              />
            </div>
            
            {/* Details */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="w-4 h-4 text-red-500" />
                <span className="font-mono font-medium text-sm">
                  Move {blunder.move_number}: {blunder.move}
                </span>
              </div>
              
              <p className="text-sm text-muted-foreground mb-2">
                {blunder.feedback}
              </p>
              
              {blunder.threat && (
                <p className="text-xs text-red-400">
                  Threat: {blunder.threat}
                </p>
              )}
              
              <Button
                variant="ghost"
                size="sm"
                className="mt-2 -ml-2 text-xs"
                onClick={() => {
                  onClose();
                  navigate(`/game/${blunder.game_id}`);
                }}
              >
                View full game <ChevronRight className="w-3 h-3 ml-1" />
              </Button>
            </div>
          </div>
        </Card>
      ))}
      {(!data?.blunders || data.blunders.length === 0) && (
        <div className="text-center py-8">
          <Zap className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
          <p className="text-muted-foreground">No blunders found - great job!</p>
        </div>
      )}
    </div>
  );

  const renderBestMoves = () => (
    <div className="space-y-4 max-h-[60vh] overflow-y-auto">
      {data?.best_moves?.map((move, idx) => (
        <Card key={idx} className="p-4">
          <div className="flex gap-4">
            {/* Mini board */}
            <div className="w-32 h-32 flex-shrink-0">
              <Chessboard
                position={move.fen}
                boardWidth={128}
                arePiecesDraggable={false}
                customBoardStyle={{
                  borderRadius: "4px",
                }}
              />
            </div>
            
            {/* Details */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-4 h-4 text-amber-500" />
                <span className="font-mono font-medium text-sm">
                  Move {move.move_number}: {move.move}
                </span>
                <span className="text-xs bg-amber-500/20 text-amber-500 px-2 py-0.5 rounded">
                  {move.evaluation}
                </span>
              </div>
              
              <p className="text-sm text-muted-foreground mb-2">
                {move.feedback || "Great move!"}
              </p>
              
              <Button
                variant="ghost"
                size="sm"
                className="mt-2 -ml-2 text-xs"
                onClick={() => {
                  onClose();
                  navigate(`/game/${move.game_id}`);
                }}
              >
                View full game <ChevronRight className="w-3 h-3 ml-1" />
              </Button>
            </div>
          </div>
        </Card>
      ))}
      {(!data?.best_moves || data.best_moves.length === 0) && (
        <p className="text-center text-muted-foreground py-8">No best moves recorded yet</p>
      )}
    </div>
  );

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {getIcon()}
            {getTitle()}
          </DialogTitle>
        </DialogHeader>
        
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <>
            {type === "analyzed" && renderAnalyzedGames()}
            {type === "blunders" && renderBlunders()}
            {type === "best-moves" && renderBestMoves()}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default StatsDetailModal;
