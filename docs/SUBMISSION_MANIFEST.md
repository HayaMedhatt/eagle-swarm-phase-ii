# Submission Manifest

This manifest maps each reviewer deliverable to its exact location.

| Deliverable | Path | Reviewer purpose |
|---|---|---|
| Source repository | repository root | Seven ROS 2 packages, scripts, tests, Apache-2.0 license and configuration |
| Reproduction guide | `README.md` | Clean build, normal run, faults, interfaces and final gate |
| Architecture diagram | `docs/architecture_diagram.pdf` | One-page operational graph with nodes, DDS contracts and safety boundary |
| Architecture narrative | `docs/ARCHITECTURE.md` | Responsibilities, data flow, failure points and recovery |
| Technical report | `docs/TECHNICAL_REPORT.pdf` | Decisions, trade-offs, limitations, verification and score forecast |
| Requirements matrix | `docs/REQUIREMENTS_TRACEABILITY.md` | Requirement-to-code-to-evidence traceability |
| Fault matrix | `docs/FAULT_TEST_MATRIX.md` | Injection, detection, action, recovery and PASS conditions |
| 15-minute video plan | `docs/DEMO_SCRIPT.md` | Timed recording sequence and evidence shots |
| Technical defense | `docs/TECHNICAL_DEFENSE.md` | Prepared answers to the committee questions |
| Safety/security | `docs/SAFETY_SECURITY.md` | Required design justification and production controls |
| Perception scope | `docs/PERCEPTION_SCOPE.md` | Honest deterministic RGB/thermal simulation boundary |
| BOM / first 90 days | `docs/BOM_AND_90_DAY_PLAN.md` | Cost and roadmap defense preparation |
| Strict scorecard | `docs/ASSESSMENT_SCORECARD.md` | Rubric forecast and deductions |
| Submission checklist | `docs/FINAL_SUBMISSION_CHECKLIST.md` | Freeze/build/evidence/video/archive gate |
| Final handoff | `docs/FINAL_HANDOFF.md` | Exact final gate, evidence tree, archive output and honest runtime boundary |
| Baseline evidence | `evidence/baseline_normal/` | Selected successful candidate-machine milestones |
| Generated final evidence | `evidence/runtime/campaign_<UTC>/` | Immutable normal-run logs, five machine-checked fault timelines and scored separation timeline |
| Generated evidence index | `evidence/RUNTIME_EVIDENCE_INDEX.md` | Overall normal + five-fault + separation PASS status |

## One-command acceptance path

After the workspace builds on the Ubuntu/PX4 machine:

```bash
./scripts/run_full_acceptance_campaign.sh
```

For the strict build, test, runtime, preflight and packaging sequence:

```bash
./scripts/final_submission_gate.sh
```

The source package is deliberately free of `build/`, `install/`, raw `log/`, patch backups and bytecode. Runtime evidence is generated rather than pre-claimed.
