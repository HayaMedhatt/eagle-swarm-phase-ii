# Strict Assessment Scorecard and 90+ Gate

## Projected score after all generated runtime evidence passes: **92/100**

This is intentionally harsh. Source code alone is not credited where the assessment requires a running recovery demonstration.

| Rubric | Points | Strict forecast | Reason |
|---|---:|---:|---|
| Architecture & Extensibility | 12 | 12 | Clear responsibility split, replicated coordinator, generic Ground Relay and explicit onboard safety boundary |
| ROS 2 Code Quality | 10 | 9 | Seven packages, custom interfaces, launch/scripts, pure policies, 15 unit tests and static CI; full PX4 integration CI remains hardware/simulator-host dependent |
| PX4/Gazebo Integration | 10 | 10 | Three independent SITL/MAVROS vehicles, health-gated takeoff, distinct coverage, target transit and landing |
| Swarm Communication | 10 | 9 | Heartbeat, beacon, bids, awards, leader, fault and safety topics; deterministic perception contract is documented |
| Coverage / Task Allocation | 10 | 10 | Reproducible constrained random coverage and fully explainable four-term Contract-Net |
| Leader Election | 10 | 10 | Stable initial membership, deterministic scoring, replicated authority and automated measured failover test |
| Battery & RTB | 8 | 8 | Local reserve authority, task release, home landing, re-auction and measured evidence runner |
| Collision Safety | 8 | 7 | Active 3-D separation hold/resume and near-miss logging; intentionally not full ORCA/RVO |
| Digital Twin | 8 | 8 | Live operational visibility across members, targets, bids, leader, faults and safety |
| Ground Relay Extension | 8 | 8 | Same agent/policies/interfaces; no core allocator rewrite |
| Documentation & Demo | 6 | 6 | Reproducible README, architecture/report PDFs, traceability, automated evidence and 15-minute script |
| **Total** | **100** | **92** | Technical-lead threshold reached if evidence campaign passes |

## Conditions that reduce the score

- Missing any one of the five generated fault PASS artifacts: minus 3-6 points.
- No final clean `colcon build` and `colcon test` output: minus 2-4.
- Video cuts before all three land or hides recovery logs: minus 2-5.
- Claiming a real AI perception model is running: credibility penalty and possible rejection.
- Submitting build/install/log clutter or patch-backup files: code-quality penalty.

## Submission gate for 90+

All must be true:

```text
[ ] final source-only workspace passes preflight_submission.sh
[ ] clean colcon build and colcon test pass
[ ] final normal run reaches DEMO COMPLETE
[ ] coordinator_loss evidence = PASS
[ ] shutdown evidence = PASS
[ ] critical_battery evidence = PASS
[ ] wifi_cut evidence = PASS
[ ] gps_dropout evidence = PASS
[ ] separation evidence = PASS
[ ] RUNTIME_EVIDENCE_INDEX says overall PASS
[ ] 15-minute video follows DEMO_SCRIPT.md
[ ] report and diagram match the exact submitted commit
```
