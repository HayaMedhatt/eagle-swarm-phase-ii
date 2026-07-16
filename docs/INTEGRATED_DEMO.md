# Integrated PX4/Gazebo Demo

## Launch behavior

`start_integrated_demo.sh` is health-gated. It refuses to start over stale PX4/Gazebo processes, creates a timestamped log directory, starts three PX4 instances, waits for Gazebo, starts a GCS heartbeat and three MAVROS bridges, verifies all FCU links, spawns the physical target platform, and only then launches swarm logic.

## Parameters

```bash
TARGET_X=10.0 TARGET_Y=0.0 \
COVERAGE_SEED=2180021560 \
AUTO_LAND=true OPEN_DASHBOARD=1 \
./scripts/start_integrated_demo.sh
```

- `TARGET_X`, `TARGET_Y`: target platform and beacon location.
- `COVERAGE_SEED`: exact coverage replay; omit for a fresh pattern.
- `AUTO_LAND=false`: hold after target arrival for fault testing.
- `OPEN_DASHBOARD=0`: lower graphical load during evidence campaigns.

## Normal mission state sequence

```text
WAIT_FCU -> WAIT_POSE -> PRESTREAM -> ARMING -> TAKEOFF -> ACTIVE
ACTIVE -> COVERAGE -> SECTOR_READY
winner: EXECUTING -> ARRIVED -> LANDING -> LANDED
non-winners: SECTOR_READY -> RTB -> LANDING -> LANDED
```

## Target landing platform

The SDF model includes matching visual and collision cylinders. The target is a wide, low static platform so the winner lands on a physical surface rather than passing through a marker.

## Diagnostics

```bash
./scripts/diagnose_integrated_demo.sh
grep -E 'ERROR|WARN|ACTIVE|SECTOR|ALLOCATE|ARRIVED|LANDED|DEMO COMPLETE' \
  log/integrated_latest/real_swarm.log
```
