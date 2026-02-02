import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import Layout from "@/components/Layout";
import { toast } from "sonner";
import { 
  Import, 
  CheckCircle2, 
  Loader2, 
  ExternalLink,
  ChevronRight
} from "lucide-react";

const ImportGames = ({ user }) => {
  const navigate = useNavigate();
  const [chessComUsername, setChessComUsername] = useState(user?.chess_com_username || '');
  const [lichessUsername, setLichessUsername] = useState(user?.lichess_username || '');
  const [importing, setImporting] = useState(false);
  const [importPlatform, setImportPlatform] = useState(null);
  const [games, setGames] = useState([]);
  const [loadingGames, setLoadingGames] = useState(true);

  useEffect(() => {
    const fetchGames = async () => {
      try {
        const response = await fetch(`${API}/games`, {
          credentials: 'include'
        });
        if (response.ok) {
          const data = await response.json();
          setGames(data);
        }
      } catch (error) {
        console.error('Error fetching games:', error);
      } finally {
        setLoadingGames(false);
      }
    };
    fetchGames();
  }, []);

  const handleImport = async (platform) => {
    const username = platform === 'chess.com' ? chessComUsername : lichessUsername;
    
    if (!username.trim()) {
      toast.error(`Please enter your ${platform} username`);
      return;
    }

    setImporting(true);
    setImportPlatform(platform);

    try {
      const response = await fetch(`${API}/import-games`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          platform: platform,
          username: username.trim()
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Import failed');
      }

      const result = await response.json();
      toast.success(`Imported ${result.imported} games from ${platform}`);

      // Refresh games list
      const gamesResponse = await fetch(`${API}/games`, {
        credentials: 'include'
      });
      if (gamesResponse.ok) {
        const data = await gamesResponse.json();
        setGames(data);
      }
    } catch (error) {
      toast.error(error.message || 'Failed to import games');
    } finally {
      setImporting(false);
      setImportPlatform(null);
    }
  };

  return (
    <Layout user={user}>
      <div className="space-y-8" data-testid="import-games-page">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">Import Games</h1>
          <p className="text-muted-foreground">
            Connect your chess accounts and import games for AI analysis
          </p>
        </div>

        {/* Import Cards */}
        <Tabs defaultValue="chess.com" className="w-full">
          <TabsList className="grid w-full max-w-md grid-cols-2">
            <TabsTrigger value="chess.com" data-testid="chesscom-tab">Chess.com</TabsTrigger>
            <TabsTrigger value="lichess" data-testid="lichess-tab">Lichess</TabsTrigger>
          </TabsList>
          
          <TabsContent value="chess.com" className="mt-6">
            <Card>
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-lg bg-green-500/10 flex items-center justify-center">
                    <span className="text-2xl font-bold text-green-500">♟</span>
                  </div>
                  <div>
                    <CardTitle>Chess.com</CardTitle>
                    <CardDescription>Import your recent games from Chess.com</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="chesscom-username">Username</Label>
                  <div className="flex gap-2">
                    <Input
                      id="chesscom-username"
                      placeholder="Enter your Chess.com username"
                      value={chessComUsername}
                      onChange={(e) => setChessComUsername(e.target.value)}
                      data-testid="chesscom-username-input"
                    />
                    <Button 
                      onClick={() => handleImport('chess.com')}
                      disabled={importing}
                      data-testid="chesscom-import-btn"
                    >
                      {importing && importPlatform === 'chess.com' ? (
                        <Loader2 className="w-4 h-4 animate-spin mr-2" />
                      ) : (
                        <Import className="w-4 h-4 mr-2" />
                      )}
                      Import
                    </Button>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">
                  We'll import your last 30 games from the past 3 months
                </p>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="lichess" className="mt-6">
            <Card>
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-lg bg-orange-500/10 flex items-center justify-center">
                    <span className="text-2xl font-bold text-orange-500">♞</span>
                  </div>
                  <div>
                    <CardTitle>Lichess</CardTitle>
                    <CardDescription>Import your recent games from Lichess</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="lichess-username">Username</Label>
                  <div className="flex gap-2">
                    <Input
                      id="lichess-username"
                      placeholder="Enter your Lichess username"
                      value={lichessUsername}
                      onChange={(e) => setLichessUsername(e.target.value)}
                      data-testid="lichess-username-input"
                    />
                    <Button 
                      onClick={() => handleImport('lichess')}
                      disabled={importing}
                      data-testid="lichess-import-btn"
                    >
                      {importing && importPlatform === 'lichess' ? (
                        <Loader2 className="w-4 h-4 animate-spin mr-2" />
                      ) : (
                        <Import className="w-4 h-4 mr-2" />
                      )}
                      Import
                    </Button>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">
                  We'll import your last 30 games
                </p>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Games List */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold">Your Games ({games.length})</h2>
          </div>

          {loadingGames ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : games.length > 0 ? (
            <div className="grid gap-3">
              {games.map((game) => (
                <Card 
                  key={game.game_id}
                  className="cursor-pointer hover:border-primary/50 transition-colors"
                  onClick={() => navigate(`/game/${game.game_id}`)}
                  data-testid={`game-card-${game.game_id}`}
                >
                  <CardContent className="flex items-center justify-between p-4">
                    <div className="flex items-center gap-4">
                      <div className={`w-3 h-3 rounded-full ${game.is_analyzed ? 'bg-emerald-500' : 'bg-muted-foreground'}`} />
                      <div>
                        <p className="font-medium">
                          {game.white_player} vs {game.black_player}
                        </p>
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <span className="capitalize">{game.platform}</span>
                          <span>•</span>
                          <span>{game.result}</span>
                          {game.time_control && (
                            <>
                              <span>•</span>
                              <span>{game.time_control}</span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`text-xs px-2 py-1 rounded ${game.user_color === 'white' ? 'bg-white text-black border' : 'bg-black text-white'}`}>
                        {game.user_color}
                      </span>
                      {game.is_analyzed ? (
                        <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                      ) : (
                        <Button variant="ghost" size="sm">
                          Analyze
                          <ChevronRight className="w-4 h-4 ml-1" />
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <Card className="border-dashed">
              <CardContent className="flex flex-col items-center justify-center py-12 space-y-4">
                <Import className="w-12 h-12 text-muted-foreground" />
                <p className="text-muted-foreground text-center">
                  No games imported yet. Enter your username above to get started.
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </Layout>
  );
};

export default ImportGames;
