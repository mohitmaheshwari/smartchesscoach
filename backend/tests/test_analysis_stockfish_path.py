"""Game analysis picks the AVX2 build only when it exists and the CPU can run it;
Play with Coach's STOCKFISH_PATH is never changed by this."""
import config


def test_override_wins(tmp_path, monkeypatch):
    sf = tmp_path / "sf"; sf.write_text("x")
    monkeypatch.setenv("ANALYSIS_STOCKFISH_PATH", str(sf))
    assert config._analysis_stockfish_path() == str(sf)


def test_avx2_build_needs_the_binary_and_the_cpu(tmp_path, monkeypatch):
    sf = tmp_path / "sf-avx2"; sf.write_text("x")
    monkeypatch.delenv("ANALYSIS_STOCKFISH_PATH", raising=False)
    monkeypatch.setattr(config, "STOCKFISH_AVX2_PATH", str(sf))
    monkeypatch.setattr(config, "_cpu_runs_avx2_build", lambda: True)
    assert config._analysis_stockfish_path() == str(sf)
    monkeypatch.setattr(config, "_cpu_runs_avx2_build", lambda: False)
    assert config._analysis_stockfish_path() == config.STOCKFISH_PATH
    monkeypatch.setattr(config, "STOCKFISH_AVX2_PATH", str(tmp_path / "missing"))
    monkeypatch.setattr(config, "_cpu_runs_avx2_build", lambda: True)
    assert config._analysis_stockfish_path() == config.STOCKFISH_PATH


def test_prefetch_defaults_to_the_old_single_engine_path():
    assert config.STOCKFISH_PREFETCH_WORKERS >= 1
