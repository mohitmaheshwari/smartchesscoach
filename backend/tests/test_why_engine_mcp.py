"""The engine MCP server the Why queue's agents use: protocol and board answers
(no engine needed for these; `analyse` is covered by the live smoke test)."""
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND / "scripts"))

import why_engine_mcp as mcp  # noqa: E402

FEN = "r1bqkbnr/pppp1pp1/2n4p/4p3/2B1P3/5N2/PPPP1PPP/RNBQ1RK1 b kq -"


def _call(name, args):
    reply = mcp.handle(mcp.Engine("unused"), {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                                               "params": {"name": name, "arguments": args}})
    return reply["result"]


def test_initialize_and_list_offer_only_the_two_tools():
    eng = mcp.Engine("unused")
    init = mcp.handle(eng, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "x"}})
    assert init["result"]["protocolVersion"] == "x" and "tools" in init["result"]["capabilities"]
    assert mcp.handle(eng, {"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    names = [t["name"] for t in mcp.handle(eng, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]]
    assert names == ["analyse", "board"]


def test_board_after_moves_reports_side_material_and_unguarded():
    res = _call("board", {"fen": FEN, "moves": ["Bc5", "c3", "Bxf2+"]})
    assert not res["isError"]
    out = json.loads(res["content"][0]["text"])
    assert out["side_to_move"] == "white" and out["in_check"]
    assert out["material"]["white"]["pieces"]["pawn"] == 7
    assert "bishop on f2" in out["attacked_with_nothing_guarding"]["black"]


def test_an_illegal_move_is_an_error_the_agent_can_read():
    res = _call("board", {"fen": FEN, "moves": ["Bc5", "Qq9"]})
    assert res["isError"] and "move 2 (Qq9) is not legal" in res["content"][0]["text"]


def test_unknown_tool_and_method():
    eng = mcp.Engine("unused")
    assert "error" in mcp.handle(eng, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                       "params": {"name": "shell", "arguments": {}}})
    assert "error" in mcp.handle(eng, {"jsonrpc": "2.0", "id": 4, "method": "resources/list"})
