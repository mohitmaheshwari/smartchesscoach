"""Bounded, isolated Stockfish queries with typed scores and completed iterations."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import platform
import sys
import time

import chess
import chess.engine

from .contracts import ReasoningConfig, Score, SearchRecord, VERSION, fingerprint


class SearchSession:
    def __init__(self, config: ReasoningConfig, pov: chess.Color, history_id: str):
        self.config = config
        self.pov = pov
        self.history_id = history_id
        self.records: list[SearchRecord] = []
        self.requested_nodes = 0
        self.executed_queries = 0
        self.engine_manifest: dict = {}
        self._cache: dict[str, SearchRecord] = {}
        path = Path(config.engine_path).resolve(strict=True)
        if not path.is_file():
            raise ValueError("engine_path must name a file")
        self.manifest = {"version": VERSION, "config": asdict(config), "config_digest": fingerprint(asdict(config)),
                         "engine_sha256": fingerprint_bytes(path), "engine_path": str(path),
                         "python": sys.version, "python_chess": chess.__version__,
                         "machine": platform.machine(), "processor": platform.processor(),
                         "isolation": "fresh_process_per_query", "history_digest": history_id,
                         "score_pov": "white" if pov else "black"}

    def can_query(self, nodes=None):
        nodes = self.config.nodes if nodes is None else nodes
        return self.executed_queries < self.config.max_queries and self.requested_nodes + nodes <= self.config.max_total_nodes

    def query(self, board: chess.Board, purpose: str, *, roots=(), width=1, nodes=None) -> SearchRecord:
        nodes = self.config.nodes if nodes is None else nodes
        moves = sorted(set(roots), key=lambda m: m.uci())
        if any(m not in board.legal_moves for m in moves):
            raise ValueError("search root must be legal")
        legal_count = len(moves) if moves else board.legal_moves.count()
        width = min(width, legal_count)
        identity = {"fen": board.fen(), "history": [m.uci() for m in board.move_stack],
                    "history_root": board.root().fen(), "history_digest": self.history_id,
                    "engine_sha256": self.manifest["engine_sha256"],
                    "roots": [m.uci() for m in moves], "nodes": nodes, "width": width,
                    "config": self.manifest["config_digest"]}
        key = fingerprint(identity)
        if key in self._cache:
            return self._cache[key]
        record = SearchRecord(key, purpose, board.fen(), identity["roots"], nodes, width, "unavailable")
        if not width:
            record.stop_reason = "terminal_no_legal_moves"
            self.records.append(record)
            self._cache[key] = record
            return record
        if not self.can_query(nodes):
            record.stop_reason = "query_or_node_budget_exhausted"
            # Attempted queries are evidence too; they cannot consume engine resources.
            self.records.append(record)
            self._cache[key] = record
            return record
        self.requested_nodes += nodes
        self.executed_queries += 1
        started, cpu = time.perf_counter(), time.process_time()
        peak_rss, parent_rss, combined_rss, child_cpu = None, None, None, None
        try:
            with chess.engine.SimpleEngine.popen_uci(self.config.engine_path) as engine:
                options = {"Threads": 1, "Hash": self.config.hash_mb}
                if "UCI_LimitStrength" in engine.options:
                    options["UCI_LimitStrength"] = False
                if "Skill Level" in engine.options:
                    options["Skill Level"] = engine.options["Skill Level"].max
                engine.configure(options)
                self.engine_manifest = {"id": dict(engine.id), "configured_options": options,
                    "option_defaults": {k: v.default for k, v in sorted(engine.options.items())},
                    "nnue": "engine defaults recorded; embedded networks covered by binary hash; external files not independently certified"}
                process = None
                parent = None
                try:
                    import psutil
                    process = psutil.Process(engine.transport.get_pid())
                    parent = psutil.Process()
                except (ImportError, OSError):
                    pass
                iterations: dict[int, dict[int, dict]] = {}
                kwargs = {"multipv": width}
                if moves:
                    kwargs["root_moves"] = moves
                with engine.analysis(board, chess.engine.Limit(nodes=nodes), **kwargs) as stream:
                    for info in stream:
                        record.actual_nodes = max(record.actual_nodes, info.get("nodes", 0))
                        if process is not None:
                            try:
                                child_sample, parent_sample = process.memory_info().rss, parent.memory_info().rss
                                peak_rss = max(peak_rss or 0, child_sample)
                                parent_rss = max(parent_rss or 0, parent_sample)
                                combined_rss = max(combined_rss or 0, child_sample + parent_sample)
                                times = process.cpu_times()
                                child_cpu = max(child_cpu or 0, 1000 * (times.user + times.system))
                            except OSError:
                                process = None
                        if (info.get("pv") and info.get("score") is not None
                                and not info.get("lowerbound") and not info.get("upperbound")):
                            iterations.setdefault(info.get("depth", 0), {})[info.get("multipv", 1)] = dict(info)
                    record.final_bounds = [{"lower": bool(i.get("lowerbound")), "upper": bool(i.get("upperbound"))}
                                           for i in stream.multipv]
                complete = {d: rows for d, rows in iterations.items() if len(rows) == width
                            and len({i["pv"][0].uci() for i in rows.values()}) == width}
                if complete:
                    rows = complete[max(complete)]
                    for rank in sorted(rows):
                        info = rows[rank]
                        score = info["score"].pov(self.pov)
                        typed = Score("mate" if score.is_mate() else "cp",
                                      score.mate() if score.is_mate() else score.score(), self.manifest["score_pov"])
                        walker, sans = board.copy(), []
                        for move in info["pv"]:
                            if move not in walker.legal_moves:
                                raise ValueError("illegal_engine_line")
                            sans.append(walker.san(move))
                            walker.push(move)
                        record.lines.append({"root_uci": info["pv"][0].uci(), "moves_uci": [m.uci() for m in info["pv"]],
                                             "moves_san": sans, "score": asdict(typed), "depth": info["depth"],
                                             "nodes": info.get("nodes", 0)})
                    record.status, record.stop_reason = "complete_iteration", "node_limit"
                else:
                    record.stop_reason = "no_complete_unbounded_iteration"
        except Exception as exc:
            record.lines.clear()
            record.stop_reason = f"engine_error:{type(exc).__name__}:{exc}"
        record.runtime = {"wall_ms": round(1000 * (time.perf_counter() - started), 3),
                          "parent_cpu_ms": round(1000 * (time.process_time() - cpu), 3),
                          "sampled_child_rss_bytes": peak_rss, "sampled_parent_rss_bytes": parent_rss,
                          "sampled_combined_rss_bytes": combined_rss, "sampled_child_cpu_ms": child_cpu}
        self.records.append(record)
        self._cache[key] = record
        return record

    def document(self):
        return {**self.manifest, "engine": self.engine_manifest,
                "query_log_digest": fingerprint([{k: v for k, v in r.document().items() if k != "runtime"} for r in self.records])}


def fingerprint_bytes(path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def score_order(score: dict):
    if score["kind"] == "cp":
        return (1, score["value"])
    # Mate zero denotes the already-mated side to move and is not positive mate.
    return (2, -score["value"]) if score["value"] > 0 else (0, -score["value"])


def comparison(best: dict | None, other: dict | None, epsilon: int) -> str:
    if best is None or other is None:
        return "unknown"
    if best["kind"] == other["kind"] == "cp":
        return "equivalent" if abs(best["value"] - other["value"]) < epsilon else "inferior" if best["value"] > other["value"] else "better"
    if best == other:
        return "equivalent"
    return "inferior" if score_order(best) > score_order(other) else "better"
