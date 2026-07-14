use test_database;
var game = db.games.findOne({is_analyzed: true});
if (game) {
  print("GAME: " + game.game_id);
  var a = db.game_analyses.findOne({game_id: game.game_id});
  if (a && a.stockfish_analysis && a.stockfish_analysis.move_evaluations) {
    var moves = a.stockfish_analysis.move_evaluations;
    print("Total moves: " + moves.length);
    var user_moves = moves.filter(m => m.is_user_move);
    print("User moves: " + user_moves.length);
    print("\nFirst 3 user moves:");
    user_moves.slice(0, 3).forEach((m, i) => {
      print((i+1) + ". " + m.move + " | cp_loss: " + m.cp_loss + " | gap: " + m.cognitive_gap);
    });
    print("\ncp_loss distribution:");
    var r0_50 = user_moves.filter(m => m.cp_loss < 50).length;
    var r50_100 = user_moves.filter(m => m.cp_loss >= 50 && m.cp_loss < 100).length;
    var r100_200 = user_moves.filter(m => m.cp_loss >= 100 && m.cp_loss < 200).length;
    var r200 = user_moves.filter(m => m.cp_loss >= 200).length;
    print("  0-50cp: " + r0_50);
    print("  50-100cp: " + r50_100);
    print("  100-200cp: " + r100_200);
    print("  200+cp: " + r200);
  } else {
    print("No stockfish_analysis found");
  }
} else {
  print("No analyzed games found");
}
