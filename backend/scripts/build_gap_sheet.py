"""build_gap_sheet.py — extract the mistake/blunder captions where the SYSTEM
can't derive real teaching (the right-or-silent boundary), for Parth to author
the human insight or confirm they're un-teachable.

Reads _mistake_4parts.jsonl (fresh render + engine facts) and groups:
  A. NO WHY EITHER SIDE  — names mistake + better move but no position-specific
     why for either (generic principle filler).
  B. WHY-BAD MISSING     — has a real why-better but doesn't say why the PLAYED
     move was bad.
  C. WHY-BETTER WEAK/BARE — better move named with only a board-state note / bare.
  D. ALREADY LOST        — no better move offered (position already decided).

Out: gap_captions_for_parth.html (repo root).  Pure host python (jsonl has fen+pv).
"""
import json, re, html, chess
from pathlib import Path

ROWS = [json.loads(l) for l in open("backend/scripts/_mistake_4parts.jsonl", encoding="utf-8")]
OUT = Path("gap_captions_for_parth.html")


def whybad(c):
    return bool(re.search(r"(loses to \S+|lets \S+ (win|capture)|allows \S+ (fork|forking|pin|skew)|walks into \S+|drops the \w+|\bhangs\b|win your \w+ on|forking your|losing material|loses material in the trade)", c, re.I))

def whybetter(c):
    m = re.search(r"was (?:the )?(?:better|stronger)\b\s*[—-]\s*(.*?)(?:\.|$)", c)
    if not m:
        return False
    t = m.group(1).lower()
    return bool(re.search(r"\b(it )?(attacks?|captures?|wins?|forks?|develops?|defends?|trades?|recaptur|sacrifices?|opens|keeps?|puts your|hits|breaks|protects?|saves?|covers?|untangl|connects?|pins?|skewers?|moves your|gets your king|takes the)\b", t))

def has_better(r):
    b = (r["best"] or "").replace("+", "").replace("#", "")
    return bool(b and b in r["caption"]) or bool(re.search(r"\bwas (the )?(better|stronger)\b", r["caption"]))


def bucket(r):
    c = r["caption"]
    if not r.get("best") or not has_better(r):
        return "D"        # no better move (already-lost / terminal)
    wb, wbet = whybad(c), whybetter(c)
    if not wb and not wbet:
        return "A"        # no why either side
    if wbet and not wb:
        return "B"        # why-bad missing
    if wb and not wbet:
        return "C"        # why-better weak/bare
    return None           # all-4 ok — exclude


GROUPS = {
    "A": "A · No why for EITHER move (generic-principle filler)",
    "B": "B · WHY-BAD missing (why was the played move bad?)",
    "C": "C · WHY-BETTER weak / bare (why is the better move better?)",
    "D": "D · No better move offered (already-lost / terminal)",
}

by = {k: [] for k in GROUPS}
for r in ROWS:
    b = bucket(r)
    if b:
        by[b].append(r)


def pv_str(pv):
    return " ".join(pv) if pv else "—"


parts = ["""<html><head><meta charset='utf-8'><style>
body{font-family:-apple-system,Segoe UI,Arial;margin:24px;background:#faf9f7;color:#222}
h1{margin-bottom:4px} h2{margin-top:30px;border-bottom:2px solid #ddd;padding-bottom:6px}
.leg{color:#555;font-size:13px;margin:8px 0 18px}
table{border-collapse:collapse;width:100%;margin-bottom:18px}
th,td{border:1px solid #ddd;padding:7px 9px;vertical-align:top;font-size:13px}
th{background:#2d2a26;color:#fff;text-align:left}
td.pos{white-space:nowrap;font-weight:600}
td.sys{width:38%;background:#fff4f4}
td.parth{width:30%;background:#f3fff3;color:#888}
.fen{font-family:Consolas,monospace;font-size:11px;color:#666}
.pv{font-family:Consolas,monospace;font-size:11px;color:#444}
.cp{color:#b00;font-weight:600}
</style></head><body>
<h1>Captions the system can't fully teach — for Parth</h1>
<div class='leg'>These are mistake/blunder positions where the deterministic engine
<b>can't derive real teaching</b> (right-or-silent boundary). The system caption is shown;
the green column is for your authored version OR a note that it's genuinely un-teachable.
Engine lines given so you have the data. cp = centipawns the played move lost.</div>"""]

for k, title in GROUPS.items():
    rows = by[k]
    parts.append(f"<h2>{html.escape(title)} &nbsp;<span style='color:#888;font-weight:400'>({len(rows)})</span></h2>")
    parts.append("<table><tr><th>Position</th><th>Engine lines</th><th>System caption</th><th>Parth — better caption / verdict</th></tr>")
    for r in rows:
        pos = (f"{html.escape(r['game'][:14])}<br>m{r['mv']} <b>{html.escape(str(r['san']))}</b> "
               f"<span class='cp'>(-{r['cp']})</span><br>best: <b>{html.escape(str(r['best']))}</b>"
               f"<br><span class='fen'>{html.escape(r.get('fen',''))}</span>")
        eng = (f"<span class='pv'>after played: {html.escape(pv_str(r.get('pv_played')))}<br>"
               f"after best: {html.escape(pv_str(r.get('pv_best')))}</span>")
        parts.append(
            f"<tr><td class='pos'>{pos}</td><td>{eng}</td>"
            f"<td class='sys'>{html.escape(r['caption'])}</td><td class='parth'></td></tr>")
    parts.append("</table>")

parts.append("</body></html>")
OUT.write_text("\n".join(parts), encoding="utf-8")
total = sum(len(v) for v in by.values())
print(f"WROTE {OUT.resolve()}")
for k in GROUPS:
    print(f"  {k}: {len(by[k])}")
print(f"  total gap rows: {total} / {len(ROWS)} mistakes")
