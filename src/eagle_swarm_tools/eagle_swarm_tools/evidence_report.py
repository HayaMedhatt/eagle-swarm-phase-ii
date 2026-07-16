"""Build an assessment evidence index from normal logs and scenario JSON."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Dict, List


MILESTONES = {
    "three_active": r"All three aerial units ACTIVE",
    "coverage": r"COVERAGE SECTORS commanded",
    "all_sector_ready": r"completed coverage-sector movement",
    "rgb_cue": r"RGB CUE",
    "thermal_confirmation": r"THERMAL CONFIRMED",
    "contract_net": r"ALLOCATE person_001",
    "target_arrival": r"ARRIVED at person_001",
    "direct_target_landing": r"DIRECT LAND at current target position",
    "non_winner_rtb": r"RETURN HOME",
    "all_landed": r"DEMO COMPLETE",
}


def scan_normal_log(path: Path) -> Dict[str, dict]:
    text = path.read_text(errors="replace") if path.exists() else ""
    results = {}
    lines = text.splitlines()
    for key, pattern in MILESTONES.items():
        match_line = next((line for line in lines if re.search(pattern, line)), "")
        results[key] = {"passed": bool(match_line), "evidence": match_line[-400:]}
    return results


def load_scenarios(root: Path) -> List[dict]:
    scenarios = []
    if not root.exists():
        return scenarios
    for path in sorted(root.rglob("evidence.json")):
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        data["path"] = str(path.relative_to(root))
        scenarios.append(data)
    return scenarios


def main(args=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normal-log", required=True)
    parser.add_argument("--scenario-root", required=True)
    parser.add_argument("--output", required=True)
    parsed = parser.parse_args(args=args)

    normal_log = Path(parsed.normal_log).expanduser()
    scenario_root = Path(parsed.scenario_root).expanduser()
    output = Path(parsed.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)

    normal = scan_normal_log(normal_log)
    scenarios = load_scenarios(scenario_root)
    latest_by_name = {}
    for scenario in scenarios:
        latest_by_name[scenario.get("scenario", "unknown")] = scenario

    required = [
        "shutdown",
        "coordinator_loss",
        "wifi_cut",
        "gps_dropout",
        "critical_battery",
        "separation",
    ]
    generated = datetime.now(timezone.utc).isoformat()
    rows = [
        "# EAGLE SWARM Runtime Evidence Index",
        "",
        f"Generated: `{generated}`",
        "",
        "## Normal integrated mission",
        "",
        "| Criterion | Result | Evidence excerpt |",
        "|---|---|---|",
    ]
    for key, result in normal.items():
        excerpt = result["evidence"].replace("|", "\\|")
        rows.append(
            f"| {key.replace('_', ' ')} | {'PASS' if result['passed'] else 'MISSING'} | `{excerpt}` |"
        )

    rows.extend(
        [
            "",
            "## Mandatory fault and scored safety scenarios",
            "",
            "| Scenario | Result | Recovery time / reason | Artifact |",
            "|---|---|---|---|",
        ]
    )
    for name in required:
        scenario = latest_by_name.get(name)
        if scenario is None:
            rows.append(f"| {name} | MISSING | not recorded | - |")
            continue
        result = "PASS" if scenario.get("passed") else "FAIL"
        reason = str(scenario.get("reason", "")).replace("|", "\\|")
        recovery = float(scenario.get("measured_recovery_sec", 0.0))
        recovery_text = (
            f"{recovery:.2f}s measured - {reason}"
            if recovery > 0.0
            else f"no positive recovery event - {reason}"
        )
        rows.append(
            f"| {name} | {result} | {recovery_text} | "
            f"`{scenario.get('path')}` |"
        )

    overall = all(item["passed"] for item in normal.values()) and all(
        latest_by_name.get(name, {}).get("passed", False) for name in required
    )
    rows.extend(
        [
            "",
            f"## Overall acceptance evidence: {'PASS' if overall else 'INCOMPLETE'}",
            "",
            "This index is generated from machine-readable evidence rather than manually edited claims.",
            "",
        ]
    )
    output.write_text("\n".join(rows))
    json_output = output.with_suffix(".json")
    json_output.write_text(
        json.dumps(
            {
                "generated": generated,
                "overall_pass": overall,
                "normal": normal,
                "scenarios": latest_by_name,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(output)


if __name__ == "__main__":
    main()
