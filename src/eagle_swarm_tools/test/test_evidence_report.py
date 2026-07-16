from pathlib import Path

from eagle_swarm_tools.evidence_report import MILESTONES, load_scenarios, scan_normal_log


def test_normal_log_scanner_detects_expected_milestones(tmp_path: Path):
    log = tmp_path / "real_swarm.log"
    log.write_text(
        "All three aerial units ACTIVE\n"
        "COVERAGE SECTORS commanded\n"
        "All three aerial units completed coverage-sector movement\n"
        "RGB CUE\nTHERMAL CONFIRMED\nALLOCATE person_001\n"
        "ARRIVED at person_001\nDIRECT LAND at current target position\n"
        "RETURN HOME\nDEMO COMPLETE\n"
    )
    results = scan_normal_log(log)
    assert set(results) == set(MILESTONES)
    assert all(item["passed"] for item in results.values())


def test_scenario_loader_reads_nested_json(tmp_path: Path):
    scenario_dir = tmp_path / "runtime" / "gps_dropout_1"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "evidence.json").write_text(
        '{"scenario": "gps_dropout", "passed": true}'
    )
    loaded = load_scenarios(tmp_path)
    assert len(loaded) == 1
    assert loaded[0]["scenario"] == "gps_dropout"
    assert loaded[0]["passed"] is True
    assert loaded[0]["path"] == "runtime/gps_dropout_1/evidence.json"


def test_scenario_loader_ignores_invalid_json(tmp_path: Path):
    scenario_dir = tmp_path / "runtime" / "broken"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "evidence.json").write_text("not-json")
    assert load_scenarios(tmp_path) == []
