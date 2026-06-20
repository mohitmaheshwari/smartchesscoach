"""Census of the 6215 gold captions by TEACHING CONCEPT. Multi-label concept tags +
a single primary bucket (tactical / positional / opening / recurrence / routine /
uncategorized) so we can see coverage: are they all categorized, and what's the
positional breakdown. Reads scripts/_gold_records_wg.jsonl (no engine needed).
"""
import json, re, collections

CONCEPTS = {
    # ── positional ──
    "center":        r"\b(center|centre|central)\b|controll?ing the cent",
    "develop":       r"\bdevelop|bring(s|ing)? .*piece|new piece into|knights before",
    "king_safety":   r"\bcastl|king('s)? saf|king to safety|tuck.*king|safe king",
    "open_file":     r"open file|open .-file|rook.*open|rooks? (belong|love)|behind the pass",
    "outpost":       r"outpost|strong (central )?square|cannot be (kicked|attacked)|no pawn can",
    "bad_bishop":    r"bad bishop|bishop.*blocked|blocked.*bishop|bishop.*own pawns",
    "structure":     r"\bstructure|doubled pawn|pawn structure|keeps? your pawns|isolated pawn|weak pawn",
    "space":         r"\bspace\b|claim.*space|gain.*space|cramp",
    "weak_square":   r"weak square|weakens?.*square|hole on|weak.*(light|dark) square",
    "queen_safety":  r"queen.*(early|exposed|chased)|expose.*queen|chase.*queen|queen comes? out",
    "piece_activity":r"more active|active (rook|piece|bishop|knight)|passive|improve.*piece|worst piece",
    "trade_off":     r"trade off|trades? off|trading off|exchange.*active|remove.*(defender|attacker)",
    # ── tactical ──
    "win_material":  r"\bwins? (the|a|an|material|back)|free (pawn|piece)|grab.*pawn|hangs?\b|undefended",
    "fork_pin":      r"\bfork|\bpin\b|skewer|double attack|discovered",
    "check_mate":    r"checkmate|\bmate\b|\bcheck\b",
    "recapture":     r"recaptur|take back|take it back|trade back",
    "threat":        r"threat|threaten|attacks the|hits the|target",
    # ── opening / meta ──
    "opening_name":  r"\b(defense|defence|gambit|opening|sicilian|italian|scandinavian|"
                     r"french|caro|ruy|london|philidor|english|giuoco|king'?s pawn|open game)\b",
    "recurrence":    r"\bagain\b|\bfinally\b|still (the move|available|there)|once more",
}
POSITIONAL = {"center","develop","king_safety","open_file","outpost","bad_bishop",
              "structure","space","weak_square","queen_safety","piece_activity","trade_off"}
TACTICAL = {"win_material","fork_pin","check_mate","recapture","threat"}
ROUTINE_RX = re.compile(r"^\W*(fine|good|solid|calm|nice|okay|a quiet|well played|"
                        r"a calm move|no danger|exactly right|keep developing)\b", re.I)


def main():
    recs = [json.loads(l) for l in open("scripts/_gold_records_wg.jsonl", encoding="utf-8")]
    n = len(recs)
    label = collections.Counter()
    primary = collections.Counter()
    pos_only = collections.Counter()
    uncat = []
    for r in recs:
        c = r["caption"]
        hits = [k for k, rx in CONCEPTS.items() if re.search(rx, c, re.I)]
        for h in hits:
            label[h] += 1
        for h in hits:
            if h in POSITIONAL:
                pos_only[h] += 1
        # primary bucket
        if "opening_name" in hits:
            primary["opening"] += 1
        elif "recurrence" in hits:
            primary["recurrence"] += 1
        elif any(h in TACTICAL for h in hits):
            primary["tactical"] += 1
        elif any(h in POSITIONAL for h in hits):
            primary["positional"] += 1
        elif ROUTINE_RX.search(c):
            primary["routine_ack"] += 1
        else:
            primary["uncategorized"] += 1
            if len(uncat) < 12:
                uncat.append((r["move_san"], c[:80]))

    print(f"=== {n} gold captions ===\n")
    print("PRIMARY bucket (each caption counted once):")
    for k, v in primary.most_common():
        print(f"  {v:5} ({v*100//n:2}%)  {k}")
    print(f"\nPOSITIONAL sub-concepts (multi-label, captions can hit several):")
    for k, v in pos_only.most_common():
        print(f"  {v:5} ({v*100//n:2}%)  {k}")
    print(f"\nALL concept tags (multi-label):")
    for k, v in label.most_common():
        tag = "POS" if k in POSITIONAL else ("TAC" if k in TACTICAL else "---")
        print(f"  {v:5} ({v*100//n:2}%)  [{tag}] {k}")
    print(f"\nUNCATEGORIZED samples:")
    for san, cap in uncat:
        print(f"  [{san}] {cap}")


if __name__ == "__main__":
    main()
