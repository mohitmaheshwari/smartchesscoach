"""Controlled experimental frames. This module never computes chess facts."""
from __future__ import annotations


def render(selected: dict | None, propositions: dict, comparison_status: str, context: dict) -> dict:
    if selected is None:
        return {"text": "I could not establish a clear explanation within this search.", "sentences": []}
    facts = [propositions[p] for p in selected["proposition_ids"]]
    if selected["objective"]["kind"] in ("comparative_sequence", "comparative_threat"):
        return render_comparative(selected, facts)
    root = next((p for p in facts if p["relation"] == "legal_move"), None)
    sentences = []
    for relation in ("checkmates", "promotes_to", "captures", "clears_castling_path", "reaches"):
        match = next((p for p in facts if p["relation"] == relation), None)
        if match is None:
            continue
        actor = match["actor"].capitalize()
        data = match["data"]
        if relation == "checkmates":
            text = f"{data['move']} is checkmate." if match["ply"] == 1 else f"In this line, {data['move']} is checkmate."
            title, habit = "Look for checkmate", "Before choosing a move, check for mate."
        elif relation == "promotes_to":
            text = f"In this line, {actor}'s pawn reaches {data['square']} and becomes a {match['object']}."
            title, habit = "Watch the pawn's next step", "Check whether either side can get a pawn to the last row."
        elif relation == "captures":
            checking = next((p for p in facts if p["relation"] == "gives_check" and p["ply"] == match["ply"]), None)
            text = f"In this line, {actor}'s {data['piece']} takes the {data['captured_piece']} on {data['square']}"
            text += " with check." if checking else "."
            title = "Look for a capture with check" if checking else "Follow the whole exchange"
            habit = "Before taking back, look for a stronger move with check." if checking else "Follow the replies before deciding what an exchange wins."
        elif relation == "clears_castling_path":
            text = f"{data['move']} moves the {data['piece']} off {data['cleared_square']}, making room to castle."
            title, habit = "Make room for the king", "Check the opponent's threats while getting the king to safety."
        else:
            attack = next((p for p in facts if p["relation"] == "attacks_piece" and p["ply"] == match["ply"]), None)
            if attack is None:
                continue
            text = f"In this line, the {data['piece']} reaches {match['object']} and attacks the {attack['data']['target_piece']} on {attack['data']['square']}."
            title, habit = "Find a square that creates a target", "Look at what a piece can attack after it moves."
        if root is not None and relation != "clears_castling_path":
            if text.startswith("In this line, "):
                text = f"In the line after {root['data']['move']}, " + text[len("In this line, "):]
        sentences.append({"frame": relation, "proposition_ids": [match["id"]] + ([checking["id"]] if relation == "captures" and checking else []), "text": text})
        if root is not None:
            sentences[-1]["proposition_ids"].append(root["id"])
        if relation == "reaches":
            sentences[-1]["proposition_ids"].append(attack["id"])
        if relation == "captures":
            only = next((p for p in facts if p["relation"] == "only_legal_reply" and p["ply"] == match["ply"]), None)
            if only:
                sentences.append({"frame": "only_legal_reply", "proposition_ids": [only["id"]],
                                  "text": f"At that point, {only['data']['move']} is the only legal reply."})
        break
    if not sentences:
        return {"text": "The proposed explanation still needs investigation.", "sentences": []}
    # Comparison and scope are deliberately independent of an invented causal allocation.
    comparison_text = {"equivalent": "The compared moves are close in these searches.",
                       "played_is_best": "The played move is among the strongest choices checked.",
                       "inferior": "The engine prefers the alternative in both searches.",
                       "unstable": "The comparison changed with more search.",
                       "unknown": "The comparison remains unresolved.", "not_played": ""}.get(comparison_status, "")
    mate = context.get("mate_comparison")
    if mate and mate["kind"] == "faster_mate":
        comparison_text = f"The engine finds mate in {mate['played_in']} after {mate['played_san']}, but this choice finishes "
        comparison_text += "immediately." if mate["best_in"] == 1 else f"in {mate['best_in']}."
    return {"title": title, "text": " ".join([*(s["text"] for s in sentences), comparison_text, habit]).replace("  ", " "),
            "sentences": sentences, "teaching_habit": habit, "comparison_text": comparison_text,
            "scope": selected["wording_strength"]}


def add_resource(coaching: dict, fact: dict | None) -> dict:
    if fact is None or not coaching.get("sentences"):
        return coaching
    data = fact["data"]
    text = f"Later in this line, {fact['actor'].capitalize()} plays {data['move']}, attacking the {data['target_piece']} on {data['square']}."
    coaching["sentences"].append({"frame": "attacks_piece", "proposition_ids": [fact["id"]], "text": text})
    # Keep the transferable habit last.
    habit = coaching["teaching_habit"]
    coaching["text"] = coaching["text"].removesuffix(habit).rstrip() + " " + text + " " + habit
    return coaching


def render_comparative(selected, facts):
    """Every field in these frames is bound to verified comparative evidence."""
    obj = selected["objective"]
    ids = [p["id"] for p in facts]
    played = next(p for p in facts if p["relation"] == "legal_move" and p["timeline_id"] == obj["played_timeline_id"])
    own = played["actor"].capitalize()
    opponent = "Black" if own == "White" else "White"
    if obj["kind"] == "comparative_sequence":
        exchange = " ".join(obj["exchange_san"])
        sentences = [f"After {opponent}'s {obj['setup_san']}, {obj['played_san']} still allows {exchange}, exchanging queens.",
                     f"{obj['alternative_san']} instead allows {obj['resource_san']}, taking the {obj['extra_piece']} on {obj['target_square']} with check before that exchange; {obj['played_san']} has no such checking capture."]
        reply = next((p for p in facts if p["relation"] == "only_legal_reply" and p["timeline_id"] == obj["alternative_timeline_id"] and p["ply"] == 3), None)
        if reply:
            sentences.append(f"At that point, {reply['data']['move']} is the only legal reply.")
        title, habit = "Check before exchanging", "Before taking back, look for a stronger move with check."
    else:
        missing = next(p for p in facts if p["relation"] in ("coverage_not_gained", "coverage_abandoned"))
        coverage = "leaves" if missing["relation"] == "coverage_abandoned" else "adds no cover on"
        sentences = [f"{obj['played_san']} {coverage} {obj['target_square']}; {obj['alternative_san']} would let {own}'s {played['data']['piece']} cover it."]
        mating_line = " ".join(obj["mate_line_san"])
        text = f"{opponent}'s {obj['setup_san']} prepares {obj['check_san']}: for example, after {own}'s {obj['wait_san']}, {mating_line} is mate"
        support = next((p for p in facts if p["relation"] == "retained_coverage"), None)
        text += f", with the {support['data']['piece']} on {support['data']['square']} still protecting {support['object']}." if support else "."
        sentences.append(text)
        answer = " ".join(obj["answer_line_san"])
        text = f"After {obj['alternative_san']}, the same plan can be met by {answer}"
        sentences.append(text + (", trading queens." if obj["queen_exchange"] else ", capturing the checking piece."))
        defence = obj["defence_scope"]
        if defence.get("refutes_ignoring_reply_mate_tree"):
            score = defence["first_reply_score"]
            if score["kind"] == "cp":
                sentences.append(f"After {own}'s {defence['first_reply_san']}, the engine score is {score['value'] / 100:+.2f} from {own}'s side.")
            else:
                winner = own if score["value"] > 0 else opponent
                sentences.append(f"After {own}'s {defence['first_reply_san']}, the engine finds mate in {abs(score['value'])} for {winner}.")
        title, habit = "Cover the square behind the threat", "When a quiet move prepares a check, check which squares your pieces need to cover."
    return {"title": title, "text": " ".join([*sentences, habit]),
            "sentences": [{"frame": obj["kind"], "proposition_ids": ids,
                           "search_ids": [obj["defence_scope"]["search_id"]] if obj["kind"] == "comparative_threat" and text.startswith("After " + own + "'s ") else [],
                           "text": text} for text in sentences],
            "teaching_habit": habit, "comparison_text": "", "scope": selected["wording_strength"]}
