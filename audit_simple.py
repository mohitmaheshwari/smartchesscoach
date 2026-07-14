"""Simple audit - just show raw data structure"""
import subprocess
import json

result = subprocess.run([
    'ssh', '-i', '/home/root/.ssh/id_rsa', 'root@72.60.204.176',
    'docker', 'exec', 'chess-coach-backend',
    'mongosh', '--eval', '''
    use test_database;
    print("=== GAMES ===");
    db.games.findOne({is_analyzed: true}, {_id:0, game_id:1, is_analyzed:1});
    print("\\n=== ANALYSIS SAMPLE ===");
    var g = db.games.findOne({is_analyzed: true});
    if(g) {
      var a = db.game_analyses.findOne({game_id: g.game_id});
      if(a && a.stockfish_analysis && a.stockfish_analysis.move_evaluations) {
        var moves = a.stockfish_analysis.move_evaluations.slice(0, 3);
        moves.forEach(m => {
          print("Move: " + m.move + " | is_user: " + m.is_user_move + " | cp_loss: " + m.cp_loss + " | gap: " + m.cognitive_gap);
        });
      }
    }
    print("\\n=== COUNTS ===");
    print("Analyzed games: " + db.games.countDocuments({is_analyzed: true}));
    print("Analyses: " + db.game_analyses.countDocuments({}));
    '''
], capture_output=True, text=True)

print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)
