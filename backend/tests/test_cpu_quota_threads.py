"""Maia's torch threads follow the container's CPU cap (human_behavior_engine.cpu_quota_threads).

Measured 2026-11-17: under `cpus: 1`, 4 torch threads made Maia 25x slower.
"""
from services.human_behavior_engine import cpu_quota_threads


def test_cgroup_v2_quota_of_one_cpu(tmp_path):
    (tmp_path / "cpu.max").write_text("100000 100000\n")
    assert cpu_quota_threads(str(tmp_path)) == 1


def test_cgroup_v2_uncapped_and_fractional(tmp_path):
    (tmp_path / "cpu.max").write_text("max 100000\n")
    assert cpu_quota_threads(str(tmp_path)) is None
    (tmp_path / "cpu.max").write_text("50000 100000\n")
    assert cpu_quota_threads(str(tmp_path)) == 1


def test_cgroup_v1_quota(tmp_path):
    (tmp_path / "cpu").mkdir()
    (tmp_path / "cpu" / "cpu.cfs_quota_us").write_text("200000")
    (tmp_path / "cpu" / "cpu.cfs_period_us").write_text("100000")
    assert cpu_quota_threads(str(tmp_path)) == 2
    (tmp_path / "cpu" / "cpu.cfs_quota_us").write_text("-1")
    assert cpu_quota_threads(str(tmp_path)) is None


def test_no_cgroup_files_means_uncapped(tmp_path):
    assert cpu_quota_threads(str(tmp_path)) is None
