"""Unit-level proof of the truth layer, using the real qBNJQg3g shape.

Case A reproduces the motivating game: a clock loss where the player stayed
winning on every move after the blamed one. Pre-fix, the review said
"Move 16 flipped the game - and it never came back."
"""
import sys
sys.path.insert(0, "/app/backend")

from services.decryption_voice.game_trajectory import compute_trajectory
from services.decryption_voice.validators import validate_narrative_claims
from services.decryption_voice.truth_line import (
    generate_truth_line, classify_scenario,
    SCENARIO_TIME_WINNING, SCENARIO_TIME, SCENARIO_BLUNDERED,
)
from services.decryption_voice.player_decryption import build_player_decryption

FAILS = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (("  -- " + detail) if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def cards_qbnj():
    """Move 16 blunder (468cp), then 54 user moves all still winning."""
    out = [{
        "is_user_move": True, "move_number": 16, "move_san": "Qf6",
        "cp_loss": 468, "severity": "blunder", "is_mistake": True,
        "mover_state_after": "balanced",
    }]
    for n in range(17, 71):
        out.append({
            "is_user_move": True, "move_number": n, "move_san": "Kg4",
            "cp_loss": 5, "severity": "good", "is_mistake": False,
            "mover_state_after": "winning",
        })
    return out


def cards_real_collapse():
    """Winning up to move 15, blunder at 16, losing from there on — the case
    the original collapse copy was written for. Both halves matter: without the
    winning prefix, "You were winning" would itself be a false claim."""
    out = [{
        "is_user_move": True, "move_number": n, "move_san": "Nf3",
        "cp_loss": 5, "severity": "good", "is_mistake": False,
        "mover_state_after": "winning",
    } for n in range(1, 16)]
    out.append({
        "is_user_move": True, "move_number": 16, "move_san": "Qf6",
        "cp_loss": 468, "severity": "blunder", "is_mistake": True,
        "mover_state_after": "losing",
    })
    for n in range(17, 40):
        out.append({
            "is_user_move": True, "move_number": n, "move_san": "Kg4",
            "cp_loss": 5, "severity": "good", "is_mistake": False,
            "mover_state_after": "losing",
        })
    return out


# ── A. the motivating game ────────────────────────────────────────────
print("\n=== A. clock loss, player stayed winning (qBNJQg3g) ===")
cards = cards_qbnj()
traj = compute_trajectory(cards, critical_move_number=16, termination="timeout",
                          game_result="1-0", user_color="black")
print("   trajectory:", {k: traj[k] for k in
      ("stayed_winning_after_critical", "ended_winning", "is_timeout",
       "n_user_moves_after_critical")})
check("A1 trajectory sees the recovery", traj["stayed_winning_after_critical"])
check("A2 trajectory sees the flag", traj["is_timeout"])
check("A3 scenario is time-winning, not blundered",
      classify_scenario("time_collapse", 1, traj) == SCENARIO_TIME_WINNING,
      classify_scenario("time_collapse", 1, traj))

old_line = "You were winning. Move 16 flipped the game — and it never came back."
v = validate_narrative_claims(old_line, traj)
check("A4 the exact shipped sentence is now rejected", bool(v), str(v))
print("   violation:", v[0] if v else "(none)")

t = generate_truth_line(decryption_v5_data=cards, game_reason="time_collapse",
                        game_id="qBNJQg3g", user_won=False, user_color="black",
                        trajectory=traj)
print("   TRUTH:", t)
check("A5 truth renders", bool(t))
if t:
    blob = " ".join(t[k] for k in ("identity", "anchor", "trigger"))
    check("A6 truth mentions the clock", any(w in blob.lower() for w in
          ("clock", "time", "seconds")), blob)
    check("A7 truth makes no false claim",
          not validate_narrative_claims(blob, traj))
    check("A8 truth does not say the move ended the game",
          "ended the game" not in blob.lower() and "lost the game" not in blob.lower(),
          blob)

p = build_player_decryption(decryption_v5_data=cards, game_reason="time_collapse",
                            game_id="qBNJQg3g", user_color="black", trajectory=traj)
print("   PLAYER:", p)
check("A9 player decryption renders", bool(p))
if p:
    blob = " ".join(p[k] for k in ("story", "pattern", "carry_forward"))
    check("A10 story no longer claims it never came back",
          not validate_narrative_claims(blob, traj), blob)
    check("A11 story mentions the clock",
          any(w in blob.lower() for w in ("clock", "time")), blob)

# ── B. a real collapse must keep the old, correct copy ────────────────
print("\n=== B. real collapse (regression guard) ===")
cards2 = cards_real_collapse()
traj2 = compute_trajectory(cards2, critical_move_number=16,
                           termination="resignation", game_result="1-0",
                           user_color="black")
check("B1 no false recovery detected", not traj2["stayed_winning_after_critical"])
check("B2 scenario still blundered",
      classify_scenario("one_move_blunder", 1, traj2) == SCENARIO_BLUNDERED)
check("B3 collapse language still allowed",
      not validate_narrative_claims(old_line, traj2))
p2 = build_player_decryption(decryption_v5_data=cards2,
                             game_reason="one_move_blunder", game_id="g2",
                             user_color="black", trajectory=traj2)
print("   PLAYER:", p2)
check("B4 player decryption still renders on a real collapse", bool(p2))

# ── C. clock loss in a position already going wrong ───────────────────
print("\n=== C. clock loss, position already lost ===")
traj3 = compute_trajectory(cards2, critical_move_number=16, termination="timeout",
                           game_result="1-0", user_color="black")
check("C1 scenario is plain time, not time-winning",
      classify_scenario("time_collapse", 1, traj3) == SCENARIO_TIME,
      classify_scenario("time_collapse", 1, traj3))
p3 = build_player_decryption(decryption_v5_data=cards2, game_reason="time_collapse",
                             game_id="g3", user_color="black", trajectory=traj3)
print("   PLAYER:", p3)
check("C2 renders", bool(p3))

# ── D. no trajectory supplied = old behaviour (back-compat) ───────────
print("\n=== D. back-compat: no trajectory ===")
t4 = generate_truth_line(decryption_v5_data=cards, game_reason="one_move_blunder",
                         game_id="g4", user_won=False, user_color="black")
check("D1 still renders without trajectory", bool(t4))

print("\n%s (%d failures)" % ("ALL PASS" if not FAILS else "FAILURES: " + ", ".join(FAILS), len(FAILS)))
sys.exit(1 if FAILS else 0)
