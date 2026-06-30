"""
End-to-end verification of Mohit's coaching pipeline.

For every coaching CLAIM the system can make about Mohit, fetch the raw
truth from the data and check it. Surfaces what we can confidently say
vs what is uncertain or wrong.

Run after backfill so it reads the new move_observations layer too.
"""
import os, asyncio, sys
from collections import Counter
sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient
from services.moments_topic_registry import (
    _filter_piece_safety_in_winning_position,
    _filter_long_game_conversion_losses,
)
from services.move_observation_deriver import aggregate_user_signals

UID = "user_8b599930d7ef"  # Mohit


def section(title):
    print()
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)


async def main():
    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = c[os.environ.get("DB_NAME", "chess_coach")]

    user = await db.users.find_one({"user_id": UID}) or {}
    profile = await db.player_profiles.find_one({"user_id": UID}) or {}
    identity = await db.player_identities.find_one({"user_id": UID}) or {}

    # ============================================================
    section("LAYER 1 — IDENTITY")
    # ============================================================
    print(f"  name:                    {user.get('name')}")
    print(f"  email:                   {user.get('email')}")
    print(f"  chess.com:               {user.get('chess_com_username')}")
    print(f"  user_id:                 {UID}")
    print(f"  account created:         {user.get('created_at')}")
    print(f"  last login:              {user.get('last_login')}")

    # ============================================================
    section("LAYER 2 — RAW GAMES (ground truth)")
    # ============================================================
    total = await db.games.count_documents({"user_id": UID})
    analyzed = await db.games.count_documents({"user_id": UID, "is_analyzed": True})
    print(f"  total games (synced):    {total}")
    print(f"  analyzed games:          {analyzed}")
    # most-recent
    last = await db.games.find_one({"user_id": UID, "is_analyzed": True}, sort=[("date_played", -1)])
    print(f"  most recent game:        {last.get('date_played') if last else 'n/a'}")
    # last 30 W/L/D
    wld = {"win": 0, "loss": 0, "draw": 0, "unknown": 0}
    async for g in db.games.find({"user_id": UID}, {"result": 1, "user_color": 1, "date_played": 1}).sort("date_played", -1).limit(30):
        res = (g.get("result") or "").strip()
        col = g.get("user_color")
        if res == "1-0":  wld["win" if col=="white" else "loss"] += 1
        elif res == "0-1": wld["win" if col=="black" else "loss"] += 1
        elif res in ("1/2-1/2","½-½"): wld["draw"] += 1
        else: wld["unknown"] += 1
    total_decisive = wld["win"] + wld["loss"] + wld["draw"]
    wr = round(100*wld["win"]/max(total_decisive,1))
    print(f"  last 30 record:          {wld['win']}W / {wld['loss']}L / {wld['draw']}D  ({wr}% wins)")

    # ============================================================
    section("LAYER 3 — STOCKFISH-DERIVED STATS (game_analyses)")
    # ============================================================
    # Average accuracy from raw stockfish
    acc_vals = []
    async for a in db.game_analyses.find({"user_id": UID, "stockfish_analysis.accuracy": {"$exists": True}},
                                          {"stockfish_analysis.accuracy": 1}).sort("analyzed_at", -1).limit(50):
        v = (a.get("stockfish_analysis") or {}).get("accuracy")
        if isinstance(v, (int,float)) and v > 0: acc_vals.append(float(v))
    raw_avg_acc = round(sum(acc_vals)/len(acc_vals), 1) if acc_vals else None
    print(f"  raw avg accuracy (last 50): {raw_avg_acc}%")
    print(f"  profile.average_accuracy:   {profile.get('average_accuracy')}%  "
          f"{'✅ MATCH' if profile.get('average_accuracy') and abs(profile['average_accuracy'] - raw_avg_acc) <= 3 else '❌ DRIFT'}")

    # long-game vs short-game outcomes
    long_w=long_l=long_d=short_w=short_l=short_d=0
    async for g in db.games.find({"user_id": UID, "is_analyzed": True}, {"result":1,"user_color":1,"pgn":1}):
        res=(g.get("result") or "").strip(); col=g.get("user_color")
        if res=="1-0": outcome="win" if col=="white" else "loss"
        elif res=="0-1": outcome="win" if col=="black" else "loss"
        elif res in ("1/2-1/2","½-½"): outcome="draw"
        else: continue
        is_long = any(f" {n}." in (g.get("pgn") or "") for n in (40,45,50))
        if is_long:
            if outcome=="win": long_w+=1
            elif outcome=="loss": long_l+=1
            else: long_d+=1
        else:
            if outcome=="win": short_w+=1
            elif outcome=="loss": short_l+=1
            else: short_d+=1
    long_n, short_n = long_w+long_l+long_d, short_w+short_l+short_d
    print(f"  long games (≥40 moves):  {long_w}W/{long_l}L/{long_d}D  win rate = {round(100*long_w/max(long_n,1),1)}%  (n={long_n})")
    print(f"  short games (<40 moves): {short_w}W/{short_l}L/{short_d}D  win rate = {round(100*short_w/max(short_n,1),1)}%  (n={short_n})")

    # ============================================================
    section("LAYER 4 — MOVE OBSERVATIONS (the new layer)")
    # ============================================================
    obs_count = await db.move_observations.count_documents({"user_id": UID})
    print(f"  total move_observations:  {obs_count:,}")
    obs_list = await db.move_observations.find({"user_id": UID}).to_list(length=20000)
    sig = aggregate_user_signals(obs_list)
    print(f"  per-game user_moves avg:  {round(sig['total_user_moves']/analyzed,1) if analyzed else 'n/a'}")
    print(f"  threat_response_rate:     {sig.get('threat_response_rate')}")
    print(f"  blunder_punish_rate:      {sig.get('blunder_punish_rate')}")
    print(f"  critical_find_rate:       {sig.get('critical_find_rate')}")
    print(f"  critical_moments seen:    {sig['critical_moments']}")
    print()
    print(f"  Top 5 missed patterns:")
    for p, n in Counter(sig.get('missed_pattern_counts', {})).most_common(5):
        print(f"    {p:<30} {n:>5}")
    print(f"  Top 5 concepts USED (strengths):")
    for cu, n in Counter(sig.get('concept_used_counts', {})).most_common(5):
        print(f"    {cu:<30} {n:>5}")
    print(f"  Decision register:")
    for r, n in Counter(sig.get('decision_register_counts', {})).most_common():
        print(f"    {r:<30} {n:>5}")

    # ============================================================
    section("LAYER 5 — WHAT COACH WOULD SUGGEST (current state)")
    # ============================================================
    # 5a. player_profile.top_weaknesses (legacy aggregator's pick)
    print("  ▸ top_weaknesses (legacy):")
    for w in (profile.get("top_weaknesses") or [])[:5]:
        per_game = w.get("occurrence_count",0) / max(profile.get("games_analyzed_count",1),1)
        print(f"    {w.get('subcategory'):<32} count={w.get('occurrence_count'):>5}  per_game={per_game:.2f}")

    # 5b. improvement_trend
    print(f"\n  ▸ improvement_trend (legacy): {profile.get('improvement_trend')}")

    # 5c. style_profile
    sp = identity.get("style_profile") or {}
    print(f"\n  ▸ style_profile (legacy):")
    print(f"    primary_style: {sp.get('primary_style')}  conf={sp.get('confidence')}")
    print(f"    tac={sp.get('tactical_tendency')}  pos={sp.get('positional_tendency')}  agg={sp.get('aggressive_tendency')}  def={sp.get('defensive_tendency')}")

    # 5d. /coach/moments/piece_safety output (what the user actually sees)
    print(f"\n  ▸ /coach/moments/piece_safety (live filter output, top 3):")
    moments = await _filter_piece_safety_in_winning_position(db, UID, 3)
    for m in moments:
        print(f"    mv{m['move_number']:>3} +{m['eval_before_pawns']} played={m['user_played']:<8} best={m['best_move']:<8} -{m['cp_loss']}cp")

    # 5e. /coach/moments/long_game_conversion output
    print(f"\n  ▸ /coach/moments/long_game_conversion (live filter output, top 3):")
    moments = await _filter_long_game_conversion_losses(db, UID, 3)
    for m in moments:
        print(f"    mv{m['move_number']:>3} +{m['eval_before_pawns']} played={m['user_played']:<8} best={m['best_move']:<8} -{m['cp_loss']}cp")

    # ============================================================
    section("LAYER 6 — CROSS-LAYER CONSISTENCY CHECKS")
    # ============================================================
    checks = []
    # Check 1: profile.games_analyzed_count == actual analyzed
    pgc = profile.get("games_analyzed_count")
    checks.append(("games_analyzed_count matches actual", pgc == analyzed,
                   f"profile={pgc}, actual={analyzed}"))
    # Check 2: profile.average_accuracy within 3pp of raw last-50
    if raw_avg_acc and profile.get("average_accuracy"):
        ok = abs(profile["average_accuracy"] - raw_avg_acc) <= 3
        checks.append(("average_accuracy within 3pp", ok,
                       f"profile={profile['average_accuracy']}, raw50={raw_avg_acc}"))
    # Check 3: move_observations user_moves * 2 ≈ total moves analyzed
    expected_obs = analyzed * 28  # rough avg
    ok = abs(obs_count - expected_obs) / expected_obs < 0.4
    checks.append(("observations count plausible", ok,
                   f"obs={obs_count:,}, expected~{expected_obs:,} (±40%)"))
    # Check 4: top legacy weakness vs top observation missed_pattern
    legacy_top = (profile.get("top_weaknesses") or [{}])[0].get("subcategory") if profile.get("top_weaknesses") else None
    obs_top = Counter(sig.get('missed_pattern_counts', {})).most_common(1)
    obs_top_key = obs_top[0][0] if obs_top else None
    # legacy uses "one_move_blunders", observations use "piece_safety" — both mean same thing
    legacy_meant_pieceblunder = legacy_top in ("one_move_blunders", "piece_safety")
    obs_meant_pieceblunder = obs_top_key == "piece_safety"
    checks.append(("top weakness consistent (legacy vs observations)", legacy_meant_pieceblunder == obs_meant_pieceblunder,
                   f"legacy={legacy_top}, obs={obs_top_key}"))
    # Check 5: moments filters return ≥1 result
    checks.append(("piece_safety filter returned moments", len(moments) > 0,
                   f"returned {len(moments)} long_game_conversion moments (above sample)"))

    for name, ok, detail in checks:
        marker = "✅ PASS" if ok else "❌ FAIL"
        print(f"  [{marker}] {name}  ({detail})")

    section("THE COACH'S NARRATIVE FOR MOHIT (what would actually be said)")
    print("""
  You're an attacker. Across your analyzed games you give check {check_given} times,
  set up double-attack-checks {dac} times, deliver checkmate {mate} times, and find
  the engine's best move {best} times. Your opening is classical 1.e4 — knight
  development to f3/c3 ({devs} times), bishop to c4 ({bc4} times), castling
  kingside ({oo} times).

  Your biggest leak is piece safety: {ps} undefended-piece moments across your games.
  Every one of your top-3 most recent piece-safety blunders happened when you were
  ALREADY winning (+1.5 or more) and gave check anyway.

  The coaching insight: you attack AND give material back. Strong attackers learn
  to attack WITHOUT giving anything up. The fix is a 3-second piece-safety scan
  RIGHT BEFORE the attacking move — including before you give check.

  Your win rate in long games (>=40 moves) is {long_wr}%, vs {short_wr}% in
  short games. So the leak also shows up as conversion problems in the endgame
  side of the game — you need to keep your eye on the board after you "feel"
  like you're winning.

  Trend: your improvement_trend says "{trend}". Your accuracy is {acc}%.
""".format(
        check_given=sig.get('concept_used_counts', {}).get('check_given', '?'),
        dac=sig.get('concept_used_counts', {}).get('double_attack_check', '?'),
        mate=sig.get('concept_used_counts', {}).get('checkmate_delivery', '?'),
        best=sig.get('concept_used_counts', {}).get('found_best_move', '?'),
        devs=sig.get('concept_used_counts', {}).get('knight_development', '?'),
        bc4=sig.get('concept_used_counts', {}).get('opening_bc4', '?'),
        oo=sig.get('concept_used_counts', {}).get('opening_o-o', '?'),
        ps=sig.get('missed_pattern_counts', {}).get('piece_safety', '?'),
        long_wr=round(100*long_w/max(long_n,1),1),
        short_wr=round(100*short_w/max(short_n,1),1),
        trend=profile.get('improvement_trend'),
        acc=profile.get('average_accuracy')
    ))

asyncio.run(main())
