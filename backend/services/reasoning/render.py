"""Controlled experimental frames. This module never computes chess facts."""
from __future__ import annotations


def render(selected: dict | None, propositions: dict, comparison_status: str, context: dict) -> dict:
    if selected is None:
        return {"text": "I could not establish a clear explanation within this search.", "sentences": []}
    facts = [propositions[p] for p in selected["proposition_ids"]]
    if selected["objective"].get("root_capture_contrast"):
        return render_capture_contrast(selected, facts)
    if selected["objective"]["kind"] == "comparative_recapture":
        return render_recapture(selected, facts)
    if selected["objective"]["kind"] == "comparative_piece_pressure":
        return render_piece_pressure(selected, facts)
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


def render_piece_pressure(selected, facts):
    obj = selected['objective']
    played = next(p for p in facts if p['relation'] == 'legal_move' and p['timeline_id'] == obj['played_timeline_id'])
    alternative = next(p for p in facts if p['relation'] == 'legal_move' and p['timeline_id'] == obj['alternative_timeline_id'])
    attack = next(p for p in facts if p['id'] == obj['attack_proposition_id'])
    opponent = 'Black' if attack['actor'] == 'white' else 'White'
    own = attack['actor'].capitalize()
    target = attack['data']['target_piece']
    witness = ' '.join(obj['witness_san'])
    text = [f"{alternative['data']['move']} uses the pawn on {alternative['data']['square']} to attack {opponent}'s {target} on {attack['data']['square']}; {played['data']['move']} leaves that {target} without a pawn attack.",
            f"The best replies found after {alternative['data']['move']} move that {target} away.",
            f"Leaving it there is worse for {opponent} in both comparisons: for example, {witness} exchanges {own}'s pawn for that {target}."]
    habit = 'Check whether a pawn can challenge an active enemy piece before starting another plan.'
    return {'title': 'Challenge the active piece', 'text': ' '.join([*text, habit]),
            'sentences': [{'frame': 'comparative_piece_pressure', 'proposition_ids': selected['proposition_ids'],
                           'search_ids': selected['search_ids'], 'text': sentence} for sentence in text],
            'teaching_habit': habit, 'comparison_text': '', 'scope': selected['wording_strength']}


def render_recapture(selected, facts):
    obj = selected['objective']
    played = next(p for p in facts if p['relation'] == 'legal_move' and p['timeline_id'] == obj['played_timeline_id'])
    alternative = next(p for p in facts if p['relation'] == 'legal_move' and p['timeline_id'] == obj['alternative_timeline_id'])
    placement = next(p for p in facts if p['id'] == obj['placement_proposition_id'])
    recapture = next(p for p in facts if p['relation'] == 'captures' and p['timeline_id'] == obj['played_timeline_id'] and p['ply'] == 2)
    attack = next(p for p in facts if p['relation'] == 'attacks_piece' and p['timeline_id'] == obj['alternative_timeline_id']
                  and p['ply'] == 1 and p['object'] == obj['defender_id'])
    final = next(p for p in facts if p['relation'] == 'captures' and p['timeline_id'] == obj['alternative_timeline_id']
                 and p['ply'] == obj['recapture_ply'])
    own, opponent = played['actor'].capitalize(), placement['actor'].capitalize()
    support = ' and '.join(placement['data']['pawn_defenders'])
    where = 'in the centre on' if placement['data']['central_square'] else 'on'
    pawn = 'pawn' if len(placement['data']['pawn_defenders']) == 1 else 'pawns'
    continuation = ' '.join(obj['demonstration_san'][1:])
    text = [f"After {own}'s {played['data']['move']}, {opponent} can play {recapture['data']['move']}, placing the {placement['data']['piece']} {where} {placement['object']}.",
            f"That {placement['data']['piece']} is protected by the {pawn} on {support}, and no {own} piece attacks it at that point.",
            f"No {own} pawn currently on an adjacent file can chase it away by advancing.",
            f"In the compared line, {alternative['data']['move']} instead attacks the defending {attack['data']['target_piece']} on {attack['data']['square']} first. After {continuation}, {opponent} has a {final['data']['piece']} on {final['data']['square']} instead."]
    habit = 'Before an exchange, check which piece would take back.'
    return {'title': 'Change which piece takes back', 'text': ' '.join([*text, habit]),
            'sentences': [{'frame': 'comparative_recapture', 'proposition_ids': selected['proposition_ids'],
                           'search_ids': selected['search_ids'], 'text': sentence} for sentence in text],
            'teaching_habit': habit, 'comparison_text': '', 'scope': selected['wording_strength']}


def render_capture_contrast(selected, facts):
    obj = selected["objective"]["root_capture_contrast"]
    capture = next(p for p in facts if p["relation"] == "captures" and p["ply"] == 1)
    own = capture["actor"].capitalize()
    opponent = "Black" if own == "White" else "White"
    data = capture["data"]
    text = f"{obj['best_san']} takes {opponent}'s {data['captured_piece']} on {data['square']} immediately; {obj['played_san']} leaves that {data['captured_piece']} there."
    gap = obj["comparisons"][-1]
    comparison_text = f"In the deeper search, {obj['best_san']} improves {own}'s engine score by {gap['gap_cp'] / 100:.2f} compared with {obj['played_san']}."
    habit = "Check available captures before choosing a quiet move, then follow the opponent's reply."
    return {"title": "Check the available capture", "text": " ".join((text, comparison_text, habit)),
            "sentences": [{"frame": "root_capture_contrast", "proposition_ids": selected["proposition_ids"],
                           "search_ids": selected["search_ids"], "text": text}],
            "teaching_habit": habit, "comparison_text": comparison_text,
            "scope": "exact_root_capture_with_stable_engine_comparison"}


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
                sentences.append(f"After {obj['played_san']} {obj['setup_san']} {defence['first_reply_san']}, the engine score is {score['value'] / 100:+.2f} from {own}'s side.")
            else:
                winner = own if score["value"] > 0 else opponent
                sentences.append(f"After {obj['played_san']} {obj['setup_san']} {defence['first_reply_san']}, the engine finds mate in {abs(score['value'])} for {winner}.")
        title, habit = "Cover the square behind the threat", "When a quiet move prepares a check, check which squares your pieces need to cover."
    return {"title": title, "text": " ".join([*sentences, habit]),
            "sentences": [{"frame": obj["kind"], "proposition_ids": ids,
                           "search_ids": [obj["defence_scope"]["search_id"]] if obj["kind"] == "comparative_threat" and text.startswith(f"After {obj['played_san']} {obj['setup_san']} ") else [],
                           "text": text} for text in sentences],
            "teaching_habit": habit, "comparison_text": "", "scope": selected["wording_strength"]}
