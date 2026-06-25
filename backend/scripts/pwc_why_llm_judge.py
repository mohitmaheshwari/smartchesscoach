"""pwc_why_llm_judge.py — TRUE coverage of why-bad / why-better in PWC mistake
captions, via an LLM judge (offline measurement only — NOT the serving path).
The regex detector undercounts (misses "grabs", "clears", "passive", "moved away
from defending"...). This measures semantic presence.

Step 1: VALIDATE the judge on hand-labeled captions (must match) before trusting
        the corpus numbers.
Step 2: run over real mistake captions (cp>=120) rendered by the REAL PWC path.
"""
from __future__ import annotations
import os, sys, io, re, json, asyncio
sys.path.insert(0, "/app/backend")
import chess, chess.pgn
from motor.motor_asyncio import AsyncIOMotorClient
from openai import OpenAI

MONGO = os.environ.get("MONGO_URL")
DB = os.environ.get("DB_NAME", "chess_coach")
LIMIT_GAMES = int(os.environ.get("LIMIT_GAMES", "60"))
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

JUDGE_SYS = """You grade chess COACHING captions for a 600-1500 player. For the move PLAYED and the engine's BEST move, decide if the caption contains each teaching, judging MEANING not wording:

- why_bad: a CONCRETE reason the played move is bad — names a consequence (loses/hangs/drops material, allows a specific tactic like Qxf2+, walks into a threat, weakens/undefends a named square or pawn, leaves a piece passive/trapped). NOT present if it only says "is a mistake/inaccuracy/blunder" or a generic line like "the position turns against you".
- why_better: the PURPOSE of the better move — what it ACHIEVES (attacks/defends/wins/develops/castles to safety/keeps a piece active/breaks open the king/grabs a pawn/clears a line, etc.). NOT present if it only NAMES the move ("Ke2 was better.") or says it "only slows it / problem started earlier".

Return STRICT JSON: {"why_bad": 0 or 1, "why_better": 0 or 1}. Nothing else."""

def judge(move, best, fen, caption):
    u = f"PLAYED: {move}\nBEST: {best}\nFEN: {fen}\nCAPTION: {caption}"
    r = client.chat.completions.create(
        model="gpt-4o-mini", temperature=0,
        messages=[{"role":"system","content":JUDGE_SYS},{"role":"user","content":u}],
        response_format={"type":"json_object"})
    d = json.loads(r.choices[0].message.content)
    return int(bool(d.get("why_bad"))), int(bool(d.get("why_better")))

def _whybad_rx(c): return bool(re.search(r"(loses to \S+|lets \S+ (win|capture)|allows \S+ (fork|forking|pin|skew)|walks into \S+|drops the \w+|\bhangs\b|win your \w+ on|forking your|losing material|loses material|it drops the)", c, re.I))
def _whybetter_rx(c):
    m = re.search(r"was (?:the )?(?:better|stronger)\b\s*[—-]\s*(.*?)(?:\.|$)", c)
    if not m: return False
    t = m.group(1).lower()
    return bool(re.search(r"\b(it )?(attacks?|captures?|wins?|forks?|develops?|defends?|trades?|recaptur|sacrifices?|opens|keeps?|puts your|hits|breaks|protects?|saves?|covers?|untangl|connects?|pins?|skewers?|moves your|gets your king|takes the)\b", t))

VALIDATION = [  # (caption, move, best, expected_why_bad, expected_why_better)
    ("Kf1 loses to Qxd3+. Ke2 was better.", "Kf1", "Ke2", 1, 0),
    ("Qd2 — the position now turns against you. Opponent has a winning attack here.", "Qd2", "Qxf5+", 0, 0),
    ("Bxf3 hangs your bishop — opponent recaptures on f3. Nxf3+ was better — it grabs material with check AND clears the way for your queen to take the rook on a1.", "Bxf3", "Nxf3+", 1, 1),
    ("Ng4 is a mistake. O-O was better — it castles to safety.", "Ng4", "O-O", 0, 1),
    ("Qd7 lets Bxe5 win your pawn on e5. Qxc4 was better — it grabs the undefended pawn on c4.", "Qd7", "Qxc4", 1, 1),
    ("Ra6 is a serious mistake. Nxh3+ was better — it sacrifices your knight to break open the pawn shield.", "Ra6", "Nxh3+", 0, 1),
]

def _fen4(f): return " ".join(f.split()[:4])

async def main():
    print("=== STEP 1: validate the judge (must match hand labels) ===")
    ok = 0
    for cap, mv, bm, eb, ebet in VALIDATION:
        jb, jbet = judge(mv, bm, "", cap)
        good = (jb == eb and jbet == ebet)
        ok += good
        print(f"  {'OK ' if good else 'X  '} bad={jb}(exp{eb}) better={jbet}(exp{ebet})  {cap[:55]}")
    print(f"  judge agreement: {ok}/{len(VALIDATION)}")
    if ok < len(VALIDATION) - 1:
        print("  JUDGE NOT TRUSTWORTHY — fix the rubric before believing corpus numbers."); return

    from services.shared_coaching_v5 import generate_move_coaching, CoachingContext
    try: from services.game_decryption_v5_service import detect_phase
    except Exception: detect_phase = None
    db = AsyncIOMotorClient(MONGO, serverSelectionTimeoutMS=15000)[DB]
    games = await db.games.find({"is_analyzed": True}, {"_id":0,"game_id":1,"pgn":1,"user_color":1}).limit(LIMIT_GAMES).to_list(LIMIT_GAMES)

    n = 0
    j_bad = j_bet = rx_bad = rx_bet = 0
    disagree = []
    for g in games:
        gid=g["game_id"]; uc=(g.get("user_color") or "white").lower()
        a = await db.game_analyses.find_one({"game_id":gid},{"_id":0,"stockfish_analysis":1})
        if not a: continue
        mes=(a.get("stockfish_analysis") or {}).get("move_evaluations") or []
        by_fen={_fen4(m.get("fen_before","")):m for m in mes if m.get("fen_before")}
        try: pg=chess.pgn.read_game(io.StringIO(g.get("pgn") or ""))
        except Exception: continue
        if pg is None: continue
        board=pg.board(); hist=[]; uw=(uc=="white")
        for mv in pg.mainline_moves():
            is_user=(board.turn==chess.WHITE)==uw
            try: san=board.san(mv)
            except Exception: break
            me=by_fen.get(_fen4(board.fen()))
            if me is None or not is_user or int(me.get("cp_loss") or 0)<120:
                board.push(mv); hist.append(san); continue
            cp=int(me.get("cp_loss") or 0); ph="opening"
            if detect_phase:
                try: ph=detect_phase(board,board.fullmove_number)
                except Exception: pass
            _eb,_ea=me.get("eval_before"),me.get("eval_after")
            try:
                c=await generate_move_coaching(board_before=board.copy(),move=mv,best_move_san=me.get("best_move"),
                    pv_after_played=me.get("pv_after_played") or [],pv_after_best=me.get("pv_after_best") or [],
                    cp_loss=cp,phase=ph,is_user_move=True,context=CoachingContext.LIVE_AFTER_USER,user_color=uc,
                    move_history_san=list(hist),eval_before_cp=int(_eb) if isinstance(_eb,(int,float)) else None,
                    eval_after_cp=int(_ea) if isinstance(_ea,(int,float)) else None,move_evaluations=mes)
                narr=(getattr(c,"narrative","") or "").strip()
            except Exception: narr=""
            if narr:
                n+=1
                jb,jbet=judge(san,me.get("best_move") or "",board.fen(),narr)
                rb,rbet=int(_whybad_rx(narr)),int(_whybetter_rx(narr))
                j_bad+=jb; j_bet+=jbet; rx_bad+=rb; rx_bet+=rbet
                # capture where regex said NO but judge said YES (the undercount)
                if (jb and not rb) or (jbet and not rbet):
                    if len(disagree)<12:
                        disagree.append(f"  judge_bad={jb}/rx={rb} judge_bet={jbet}/rx={rbet}  {san}: {narr[:80]}")
            board.push(mv); hist.append(san)

    p=lambda a:f"{round(100*a/n)}%" if n else "—"
    print(f"\n=== STEP 2: TRUE coverage over {n} real mistake captions (cp>=120) ===")
    print(f"               LLM JUDGE      regex (old)")
    print(f"  why_bad      {j_bad:3d} ({p(j_bad)})     {rx_bad:3d} ({p(rx_bad)})")
    print(f"  why_better   {j_bet:3d} ({p(j_bet)})     {rx_bet:3d} ({p(rx_bet)})")
    print(f"\n--- regex MISSED these (judge=yes, regex=no): the undercount ---")
    for d in disagree: print(d)

if __name__ == "__main__":
    asyncio.run(main()); sys.stdout.flush()
    import os as _os; _os._exit(0)
