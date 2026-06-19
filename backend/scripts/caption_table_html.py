"""Render an HTML table (System caption vs Claude gold, per move) for a few games,
using the CURRENT pipeline fresh (not stale stored data). Open the file in a browser.

Env: PMONGO. Usage: python scripts/caption_table_html.py <gid> [<gid> ...]
Out: /app/backend/scripts/_caption_table.html
"""
import os, sys, json, asyncio, html
sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient
from services.caption_classifier import classifier as C

REC = "/app/backend/scripts/_gold_records_wg.jsonl"
OUT = "/app/backend/scripts/_caption_table.html"
TEACH = {"HIGH", "MID"}


async def main():
    gids = [a for a in sys.argv[1:] if not a.startswith("-")]
    from services import game_decryption_v5_service as v5_mod
    from services.game_decryption_v5_service import generate_game_decryption_v5
    async def _noop(*_a, **_kw): return []
    v5_mod._get_stockfish_candidates = _noop  # candidates don't change the caption text we compare

    recs = [json.loads(l) for l in open(REC, encoding="utf-8")]
    gold = {(r["game"], r.get("move_number"), r["move_san"]): r for r in recs}
    db = AsyncIOMotorClient(os.environ["PMONGO"])["chess_coach"]

    parts = ["""<html><head><meta charset='utf-8'><style>
    body{font-family:-apple-system,Segoe UI,Arial;margin:24px;background:#faf9f7;color:#222}
    h2{margin-top:34px;border-bottom:2px solid #ddd;padding-bottom:6px}
    table{border-collapse:collapse;width:100%;margin-bottom:20px}
    th,td{border:1px solid #ddd;padding:8px 10px;vertical-align:top;font-size:14px}
    th{background:#2d2a26;color:#fff;text-align:left}
    td.mv{white-space:nowrap;font-weight:600;width:90px}
    td.sys{width:44%} td.gold{width:44%}
    tr.silent td.sys{background:#ffe6e6;color:#b00;font-style:italic}
    tr.opp{background:#f3f6ff}
    .tier{font-size:11px;color:#888;font-weight:400}
    .leg{margin:10px 0;font-size:13px;color:#555}
    </style></head><body>
    <h1>System caption vs Claude gold (current pipeline, fresh render)</h1>
    <div class='leg'>Red/italic = system silent or filler. Blue row = opponent move.
    Tier from caption_classifier (HIGH/MID = teaching).</div>"""]

    for gid in gids:
        game = await db.games.find_one({"game_id": gid}, {"_id": 0})
        analysis = await db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "stockfish_analysis": 1})
        if not game or not analysis:
            continue
        mevals = (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []
        fresh = await generate_game_decryption_v5(
            pgn=game.get("pgn") or "", user_color=(game.get("user_color") or "white").lower(),
            move_evaluations=mevals, user_id=game.get("user_id") or "unknown", db=db,
        )
        parts.append(f"<h2>{gid} &middot; you play {game.get('user_color','white')}</h2>")
        parts.append("<table><tr><th>Move</th><th>System</th><th>Claude gold</th></tr>")
        for m in fresh:
            g = gold.get((gid, m.get("move_number"), m.get("move_san")))
            sys_cap = (m.get("caption") or "").strip()
            sys_tier = m.get("caption_tier") or (C.classify_freetext(sys_cap)["tier"] if sys_cap else "NONE")
            sys_teach = (sys_tier in TEACH) or bool(m.get("has_teaching_content"))
            gold_cap = g["caption"] if g else ""
            gold_tier = C.classify_freetext(gold_cap)["tier"] if gold_cap else "—"
            who = "you" if m.get("is_user_move") else "opp"
            cls = []
            if not sys_teach: cls.append("silent")
            if not m.get("is_user_move"): cls.append("opp")
            sys_disp = html.escape(sys_cap) if sys_cap else "(silent — nothing shown)"
            parts.append(
                f"<tr class='{' '.join(cls)}'>"
                f"<td class='mv'>{m.get('move_number')}.{html.escape(str(m.get('move_san')))}<br><span class='tier'>{who}</span></td>"
                f"<td class='sys'>{sys_disp}<br><span class='tier'>{sys_tier}</span></td>"
                f"<td class='gold'>{html.escape(gold_cap)}<br><span class='tier'>{gold_tier}</span></td></tr>"
            )
        parts.append("</table>")
    parts.append("</body></html>")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print(f"WROTE {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
