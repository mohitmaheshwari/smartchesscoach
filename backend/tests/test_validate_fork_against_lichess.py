from scripts.validate_fork_against_lichess import evaluate_tagged_puzzle


def test_fork_theme_can_match_first_player_solution_ply():
    result = evaluate_tagged_puzzle({
        "fen": "r3k3/7p/8/1N6/8/8/8/4K3 b q - 0 1",
        "moves": ["h7h6", "b5c7"],
    })
    assert result["setup_error"] is False
    assert result["detected"] is True
    assert result["match"]["solution_ply"] == 1


def test_fork_theme_can_match_later_player_solution_ply():
    result = evaluate_tagged_puzzle({
        "fen": "r3k3/7p/8/1N6/8/8/P7/4K3 b q - 0 1",
        "moves": ["h7h6", "a2a3", "h6h5", "b5c7"],
    })
    assert result["setup_error"] is False
    assert result["detected"] is True
    assert result["match"]["solution_ply"] == 2
    assert len(result["checks"]) == 2


def test_invalid_solution_is_reported_as_setup_error():
    result = evaluate_tagged_puzzle({
        "fen": "r3k3/7p/8/1N6/8/8/8/4K3 b q - 0 1",
        "moves": ["a1a8", "b5c7"],
    })
    assert result["setup_error"] is True
