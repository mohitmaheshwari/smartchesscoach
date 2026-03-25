import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Search,
  Loader2,
  ChevronRight,
  Import,
  AlertTriangle,
  CheckCircle2,
  Clock,
  RefreshCw,
} from "lucide-react";

const resultDisplay = (result, userColor) => {
  if (!result) return { label: "?", color: "text-zinc-500" };
  const isWhiteWin = result === "1-0";
  const isBlackWin = result === "0-1";
  const isDraw = result === "1/2-1/2";
  const userWon =
    (userColor === "white" && isWhiteWin) ||
    (userColor === "black" && isBlackWin);
  const userLost =
    (userColor === "white" && isBlackWin) ||
    (userColor === "black" && isWhiteWin);
  if (userWon) return { label: "Won", color: "text-emerald-400" };
  if (userLost) return { label: "Lost", color: "text-red-400" };
  if (isDraw) return { label: "Draw", color: "text-amber-400" };
  return { label: result, color: "text-zinc-400" };
};

const mainMistake = (game) => {
  const b = game.blunders || 0;
  const m = game.mistakes || 0;
  if (b > 0) return { text: `${b} blunder${b > 1 ? "s" : ""}`, severity: "high" };
  if (m > 0) return { text: `${m} mistake${m > 1 ? "s" : ""}`, severity: "med" };
  return { text: "Clean game", severity: "none" };
};

const Dashboard = ({ user }) => {
  const navigate = useNavigate();
  const [games, setGames] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all"); // all | wins | losses | draws

  useEffect(() => {
    fetchGames();
  }, []);

  const fetchGames = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API}/dashboard-stats`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setGames(data.analyzed_list || []);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const filtered = games.filter((g) => {
    const opponent = g.opponent || (g.user_color === "white" ? g.black_player : g.white_player) || "";
    if (search && !opponent.toLowerCase().includes(search.toLowerCase())) return false;

    if (filter === "all") return true;
    const r = resultDisplay(g.result, g.user_color);
    if (filter === "wins") return r.label === "Won";
    if (filter === "losses") return r.label === "Lost";
    if (filter === "draws") return r.label === "Draw";
    return true;
  });

  return (
    <Layout user={user}>
      <div className="max-w-2xl mx-auto py-8 px-4 space-y-5">
        {/* Title + Import */}
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-white" data-testid="lab-title">
            Your Games
          </h1>
          <Button
            size="sm"
            variant="outline"
            onClick={() => navigate("/import")}
            className="text-xs border-zinc-700 text-zinc-300 hover:bg-zinc-800"
            data-testid="import-games-btn"
          >
            <Import className="w-3.5 h-3.5 mr-1.5" />
            Import
          </Button>
        </div>

        {/* Search + Filters */}
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-500" />
            <Input
              placeholder="Search opponent..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 h-9 bg-zinc-900 border-zinc-800 text-sm"
              data-testid="game-search"
            />
          </div>
          <div className="flex rounded-lg border border-zinc-800 overflow-hidden">
            {["all", "wins", "losses", "draws"].map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 text-xs capitalize transition-colors ${
                  filter === f
                    ? "bg-zinc-700 text-white"
                    : "bg-zinc-900 text-zinc-500 hover:text-zinc-300"
                }`}
                data-testid={`filter-${f}`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        {/* Game List */}
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-6 h-6 animate-spin text-amber-500" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-zinc-500 text-sm">
              {games.length === 0
                ? "No games yet. Import some to get started."
                : "No games match your filter."}
            </p>
            {games.length === 0 && (
              <Button
                size="sm"
                onClick={() => navigate("/import")}
                className="mt-3 bg-amber-600 hover:bg-amber-700"
              >
                Import Games
              </Button>
            )}
          </div>
        ) : (
          <div className="space-y-2" data-testid="game-list">
            {filtered.map((game) => (
              <GameRow key={game.game_id} game={game} navigate={navigate} />
            ))}
          </div>
        )}

        {!loading && games.length > 0 && (
          <p className="text-center text-xs text-zinc-600">
            {filtered.length} of {games.length} games
          </p>
        )}
      </div>
    </Layout>
  );
};

const GameRow = ({ game, navigate }) => {
  const opponent =
    game.opponent ||
    (game.user_color === "white" ? game.black_player : game.white_player) ||
    "Unknown";
  const result = resultDisplay(game.result, game.user_color);
  const mistake = mainMistake(game);
  const isAnalyzed = game.is_analyzed || game.analysis_status === "analyzed";
  const status = game.analysis_status || "pending";

  return (
    <button
      onClick={() => isAnalyzed && navigate(`/game/${game.game_id}`)}
      disabled={!isAnalyzed}
      className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl border transition-colors group text-left ${
        isAnalyzed
          ? "bg-zinc-900/50 border-zinc-800/60 hover:border-zinc-700 cursor-pointer"
          : "bg-zinc-900/30 border-zinc-800/40 cursor-default opacity-70"
      }`}
      data-testid={`game-row-${game.game_id}`}
    >
      {/* Result indicator */}
      <div
        className={`w-1.5 h-10 rounded-full flex-shrink-0 ${
          !isAnalyzed
            ? "bg-zinc-700"
            : result.label === "Won"
            ? "bg-emerald-500"
            : result.label === "Lost"
            ? "bg-red-500"
            : "bg-zinc-600"
        }`}
      />

      {/* Main info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-white truncate">
            {opponent}
          </span>
          {isAnalyzed ? (
            <span className={`text-xs font-medium ${result.color}`}>
              {result.label}
            </span>
          ) : (
            <StatusBadge status={status} />
          )}
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          {isAnalyzed ? (
            <>
              {mistake.severity === "high" && (
                <span className="flex items-center gap-1 text-xs text-red-400">
                  <AlertTriangle className="w-3 h-3" />
                  {mistake.text}
                </span>
              )}
              {mistake.severity === "med" && (
                <span className="flex items-center gap-1 text-xs text-amber-400">
                  <AlertTriangle className="w-3 h-3" />
                  {mistake.text}
                </span>
              )}
              {mistake.severity === "none" && (
                <span className="flex items-center gap-1 text-xs text-emerald-400">
                  <CheckCircle2 className="w-3 h-3" />
                  {mistake.text}
                </span>
              )}
            </>
          ) : (
            <span className="text-xs text-zinc-500">
              {status === "analyzing" ? "Analyzing moves..." : "Waiting in queue"}
            </span>
          )}
          {game.platform && (
            <span className="text-[10px] text-zinc-600">{game.platform}</span>
          )}
        </div>
      </div>

      {/* Right side */}
      {isAnalyzed ? (
        <ChevronRight className="w-4 h-4 text-zinc-600 group-hover:text-zinc-400 transition-colors flex-shrink-0" />
      ) : (
        status === "analyzing" ? (
          <RefreshCw className="w-4 h-4 text-amber-500 animate-spin flex-shrink-0" />
        ) : (
          <Clock className="w-4 h-4 text-zinc-600 flex-shrink-0" />
        )
      )}
    </button>
  );
};

const StatusBadge = ({ status }) => {
  if (status === "analyzing") {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded">
        <RefreshCw className="w-2.5 h-2.5 animate-spin" />
        Analyzing
      </span>
    );
  }
  if (status === "queued" || status === "pending") {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-zinc-400 bg-zinc-700/50 px-1.5 py-0.5 rounded">
        <Clock className="w-2.5 h-2.5" />
        In queue
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded">
        Failed
      </span>
    );
  }
  return null;
};

export default Dashboard;
