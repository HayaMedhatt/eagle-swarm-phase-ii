# Mandatory Fault and Recovery Test Matrix

## Test policy

Use a **fresh run per destructive scenario**. Start with `AUTO_LAND=false` so mission completion does not race the fault. The automated runner selects the current leader or task winner when `--robot auto` is used and writes a PASS only after observing the required ROS evidence.

The complete one-command campaign is:

```bash
cd ~/eagle_swarm_ws
./scripts/run_full_acceptance_campaign.sh
```

Use `run_fault_campaign.sh` when only the five mandatory faults need to be repeated.

## Acceptance scenarios

| Scenario | Injection point | Required detection | Recovery action | PASS condition produced by runner |
|---|---|---|---|---|
| Coordinator loss | Immediately after first task award | Leader heartbeat/state loss and disabled colocated replica | Another already-running replica becomes authority while the assigned target continues | Leader changes; measured `coordinator_loss_recovery`; original or replacement winner reaches `ARRIVED` |
| Drone shutdown | Immediately after first task award | Winner heartbeat timeout | Assignment released, beacon reopened and different unit selected | `shutdown`, `heartbeat_timeout`, `task_reassignment`, second award to another robot and replacement reaches `ARRIVED` |
| Critical battery | Immediately after first task award | Winner battery below 25% / state becomes RTB | Release task, return home, land and re-auction | Different winner reaches `ARRIVED` plus measured original-unit `critical_battery` RTB/landing completion event |
| Virtual Wi-Fi cut | Any operational aerial member | Swarm heartbeat isolation / timeout | Suppress bids, awards and mission/role commands while local PX4 setpoint/safety continue; restore DDS membership and cached-target bidding | Cut event, restore event, heartbeat-restored event and resumed heartbeat |
| GPS dropout | Any operational aerial member | `gps_ok=false`, state `SAFE_HOLD` | Hold local estimate and reject awards; restore previous setpoint/state | Recovery event with non-zero duration and heartbeat shows GPS restored |

## Manual single-scenario procedure

```bash
cd ~/eagle_swarm_ws
AUTO_LAND=false OPEN_DASHBOARD=0 COVERAGE_SEED=9003 \
  ./scripts/start_integrated_demo.sh

./scripts/run_fault_scenario.sh critical_battery auto
./scripts/stop_integrated_demo.sh
```

## Evidence structure

```text
evidence/runtime/campaign_<UTC>/scenarios/critical_battery_<UTC>/
├── PASS
├── EVIDENCE.md
└── evidence.json
```

The JSON contains the selected robot, initial/final leader, initial award, fault events, heartbeat state transitions, scenario duration, measured recovery time and exact reason. The Markdown timeline is suitable for the report appendix and video narration.

## Negative tests

The evaluator may also try incorrect conditions. Expected behavior:

- Low-confidence target (<0.75): no auction.
- Award to RTB/LANDING/SAFE_HOLD unit: ignored.
- Repeated retained award: no duplicate assignment cycle.
- Completed target: never reopened.
- Ground Relay near an aircraft: excluded from aerial collision checks.
- Delayed safety hold during landing: ignored.
- Invalid coverage configuration: startup fails loudly instead of generating unsafe goals.

## Scored collision-safety acceptance

`run_separation_acceptance.sh` starts a fresh mission with delayed target cueing, waits until all three aircraft are `SECTOR_READY`, then swaps Scout and Worker goals to create crossing paths. The scenario passes only after the independent safety monitor publishes an intervention (or hard-margin near miss), holds one aircraft, publishes `SEPARATION_CLEAR`, and both aircraft remain healthy. The measured intervention-to-clear time is stored in the same JSON/Markdown evidence format.
