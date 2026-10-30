"""Controlled experimental frames. This module never computes chess facts."""
from __future__ import annotations


def render(selected: dict | None, propositions: dict, comparison_status: str, context: dict) -> dict:
    if selected is None:
        return {"text": "I could not establish a clear explanation within this search.", "sentences": []}
    facts = [propositions[p] for p in selected["proposition_ids"]]
    root = next((p for p in facts if p["relation"] == "legal_move"), None)
    sentences = []
    for relation in ("checkmates", "promotes_to", "captures", "clears_castling_path", "reaches"):
        match = next((p for p in facts if p["relation"] == relation), None)
        if match is None:
            continue
        actor = match["actor"].capitalize()
        data = match["data"]
        if relation == "checkmates":
            text = f"In this line, {data['move']} is checkmate."
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
            text = f"{data['move']} moves the {data['piece']} out of the way for castling."
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
                       "same_mate_class": "Both choices have the same mate outcome in these searches.",
                       "inferior": "The engine prefers the alternative in both searches.",
                       "unstable": "The comparison changed with more search.",
                       "unknown": "The comparison remains unresolved.", "not_played": ""}.get(comparison_status, "")
    return {"title": title, "text": " ".join([*(s["text"] for s in sentences), comparison_text, habit]).replace("  ", " "),
            "sentences": sentences, "teaching_habit": habit, "comparison_text": comparison_text,
            "scope": selected["wording_strength"]}


def add_resource(coaching: dict, fact: dict | None) -> dict:
    if fact is None or not coaching.get("sentences"):
        return coaching
    data = fact["data"]
    move = ("..." if fact["actor"] == "black" else "") + data["move"]
    text = f"In one line, {move} attacks the {data['target_piece']} on {data['square']}."
    coaching["sentences"].append({"frame": "attacks_piece", "proposition_ids": [fact["id"]], "text": text})
    # Keep the transferable habit last.
    habit = coaching["teaching_habit"]
    coaching["text"] = coaching["text"].removesuffix(habit).rstrip() + " " + text + " " + habit
    return coaching
