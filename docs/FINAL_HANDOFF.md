# Final Candidate Handoff

## Current revision status

The source revision is frozen as a **90+ assessment candidate**. Offline validation completed in the packaging environment:

- 37 Python files compiled without syntax errors;
- 15/15 pure unit tests passed;
- every package manifest and SDF model parsed;
- every shell script passed Bash syntax validation;
- the technical report is 11 pages (limit: 20);
- the architecture PDF and report PDF were rendered and visually inspected;
- source-only preflight passed.

ROS 2 Humble, PX4 SITL, MAVROS and Gazebo are not installed in the packaging environment. Therefore runtime PASS claims must be generated on the candidate Ubuntu machine from this exact source revision.

## One final command on Ubuntu

```bash
cd ~/eagle_swarm_ws
./scripts/final_submission_gate.sh
```

The gate deliberately fails if any of the following fails:

1. dependency resolution;
2. clean `colcon build`;
3. `colcon test` / `colcon test-result`;
4. source/document preflight;
5. normal mission reaching `DEMO COMPLETE`;
6. coordinator loss;
7. assigned-drone shutdown;
8. critical-battery RTB, landing and re-award;
9. virtual Wi-Fi isolation and restoration;
10. GPS safe hold and recovery;
11. crossing-path separation intervention and clear;
12. evidence indexing;
13. clean ZIP integrity and SHA-256 generation.

## Generated reviewer evidence

A successful gate creates:

```text
evidence/runtime/campaign_<UTC>/
├── normal/
├── scenarios/
│   ├── coordinator_loss_<UTC>/
│   ├── shutdown_<UTC>/
│   ├── critical_battery_<UTC>/
│   ├── wifi_cut_<UTC>/
│   ├── gps_dropout_<UTC>/
│   └── separation_<UTC>/
└── RUNTIME_EVIDENCE_INDEX.{md,json}
```

The canonical index is copied to:

```text
evidence/RUNTIME_EVIDENCE_INDEX.md
evidence/RUNTIME_EVIDENCE_INDEX.json
```

The final default archive is:

```text
~/Haya_Eagle_Swarm_PhaseII_SUBMISSION.zip
~/Haya_Eagle_Swarm_PhaseII_SUBMISSION.zip.sha256
```

## Final video rule

Record the fixed replay seed shown in `docs/DEMO_SCRIPT.md`. Show the dashboard, Gazebo, and the machine-generated evidence rather than narrating unsupported claims. State clearly that RGB cueing and thermal confirmation are deterministic simulation stages behind a production-ready target-beacon interface.

## Strict score forecast

The documented forecast is **92/100 after the full runtime gate passes**. Missing runtime evidence, failed landing, incomplete reallocation or stale documentation must reduce that score.
