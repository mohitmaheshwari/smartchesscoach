"""Re-distill the good/opp move templates from the NEW easy-English Opus gold
(skill: distill-caption-template, step 3). One Opus call per move-type: feed the
easy-English gold examples for that type, get back ONE str.format template in the
same easy voice using only {move}/{piece}. Writes a NEW distilled_templates.json.

Approach UNCHANGED — only the template TEXT is re-distilled from the better gold.
Env: LLM_EXPOSER_URL, LLM_EXPOSER_KEY. Usage: python scripts/distill_templates_from_gold.py <gid> [--apply]
"""
import os, sys, json, time, urllib.request
sys.path.insert(0, "/app/backend")

URL = os.environ["LLM_EXPOSER_URL"].rstrip("/"); KEY = os.environ["LLM_EXPOSER_KEY"]
TPL_PATH = "/app/backend/data/distilled_templates.json"

# JSON template types we re-distill (captures/mistakes are handled elsewhere).
JSON_TYPES = ["develop", "pawn", "centralize", "castle", "space", "luft",
              "queen_safety", "rook_activity", "rook_open_file", "other"]

DISTILL = """You are distilling ONE reusable caption template for a chess coaching app, for a 1000-rated learner with BASIC English.

Below are real easy-English gold captions, all for the SAME kind of move: a {who} move of type "{ty}".

GOLD EXAMPLES:
{examples}

Write ONE template string (python str.format) that captures the SHARED teaching of these, using ONLY these slots:
- {{move}} = the move in notation (e.g. Nf3)
- {{piece}} = the piece word (e.g. knight)

RULES:
- VERY easy English: simple everyday words, short sentences, for someone still learning English. No chess jargon (no "develop", "centralize", "tempo"). Say it plainly.
- Do NOT restate the destination square — it is already inside {{move}}.
- {who_rule}
- End with ONE short, simple lesson (a universal principle for this kind of move).
- One short paragraph, about 2 to 3 short sentences. No blank lines, no markdown, no CAPS.
- It must read naturally for ANY move of this type, not just one example.

Return ONLY JSON: {{"template": "<the template string>"}}"""


def call_llm(p):
    h = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    for _ in range(2):
        try:
            d = json.dumps({"provider": "claude", "question": p, "timeout_seconds": 150}).encode()
            r = urllib.request.Request(URL + "/ask", data=d, headers=h, method="POST")
            with urllib.request.urlopen(r, timeout=40) as x:
                tid = json.loads(x.read().decode()).get("task_id")
            for _ in range(50):
                time.sleep(4)
                try:
                    pr = urllib.request.Request(URL + f"/tasks/{tid}", headers=h)
                    with urllib.request.urlopen(pr, timeout=40) as x2:
                        rec = json.loads(x2.read().decode())
                except Exception:
                    continue
                if rec.get("status") in ("completed", "done", "finished", "succeeded"):
                    return (rec.get("answer") or "").strip()
        except Exception:
            time.sleep(2)
    return ""


def parse_tpl(s):
    try:
        i, j = s.index("{"), s.rindex("}")
        return json.loads(s[i:j + 1]).get("template")
    except Exception:
        return None


# type-specific truth hints (skill step 5b: don't let the gold's overclaims into the template)
TYPE_HINT = {
    "rook_activity": "The rook's file still has pawns (it is HALF-open or closed) — NEVER say 'open file/line'. Say the rook is active / on a useful line / eyes a target.",
    "rook_open_file": "The file is fully open (no pawns) — 'open file' is correct and good to say here.",
    "space": "A space-gaining pawn move can be GOOD — do not call it weak or 'does not help'; describe the space/room it gains.",
    "other": "A quiet repositioning move — keep it general and safe; do not invent a specific threat.",
}


def distill_one(ty, who, examples):
    who_rule = ("This is the STUDENT's own move — speak to 'you/your'. Never name a colour (white/black); the student could be either."
                if who == "student" else
                "This is the OPPONENT's move — say what it means for the student and what the student should do; call it 'your opponent', NEVER 'Black'/'White' or 'your friend' (the opponent could be either colour).")
    # screen out gold examples that overclaim 'open' on a half-open/closed file
    if ty == "rook_activity":
        examples = [e for e in examples if "open" not in e.lower()] or examples
    hint = TYPE_HINT.get(ty, "")
    p = DISTILL.format(who=who, ty=ty, examples="\n".join(f'- "{e}"' for e in examples[:16]),
                       who_rule=who_rule + (" " + hint if hint else ""))
    raw = call_llm(p)
    tpl = parse_tpl(raw)
    # sanity: must be a non-empty str with {move}; reject if it invented other slots
    if not tpl or "{move}" not in tpl:
        return None
    import re
    bad = [s for s in re.findall(r"\{(\w+)\}", tpl) if s not in ("move", "piece")]
    if bad:
        return None
    return tpl.strip()


def main():
    apply = "--apply" in sys.argv
    groups = json.load(open("/app/backend/scripts/_gold_corpus.json", encoding="utf-8"))
    data = json.load(open(TPL_PATH, encoding="utf-8"))
    good = dict(data.get("good_move_templates", {}))
    opp = dict(data.get("opp_move_templates", {}))

    for ty in JSON_TYPES:
        for who, prefix, target in (("student", "good_", good), ("opponent", "opp_", opp)):
            ex = groups.get(prefix + ty) or []
            if not ex:
                print(f"  {prefix+ty:24} (no gold examples — keep old)")
                continue
            tpl = distill_one(ty, who, ex)
            if tpl:
                target[ty] = tpl
                print(f"  {prefix+ty:24} (n={len(ex)}) -> {tpl[:70]}")
            else:
                print(f"  {prefix+ty:24} (n={len(ex)}) DISTILL FAILED — keep old")

    if apply:
        data["good_move_templates"] = good
        data["opp_move_templates"] = opp
        with open(TPL_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("\nSAVED distilled_templates.json")
    else:
        print("\n(dry-run — re-run with --apply to write)")


if __name__ == "__main__":
    main()
