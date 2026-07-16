# Prototype BOM and First 90 Days

## Illustrative three-aircraft engineering BOM

Prices are planning ranges, not vendor quotations.

| Item | Qty | EUR each | Subtotal range | Buy/build decision |
|---|---:|---:|---:|---|
| 450-650 mm multirotor platform, motors, ESCs, propulsion spares | 3 | 900-1,500 | 2,700-4,500 | Buy/integrate |
| Pixhawk-class autopilot, power module, safety switch | 3 | 350-600 | 1,050-1,800 | Buy |
| Jetson Orin NX carrier and storage | 3 | 700-1,100 | 2,100-3,300 | Buy; build software |
| GNSS/compass, optional RTK rover/base share | 3 + base | 300-900 | 1,200-3,300 | Buy |
| RGB global-shutter camera | 3 | 250-600 | 750-1,800 | Buy |
| Compact radiometric thermal camera | 1-3 | 1,500-3,500 | 1,500-10,500 | Buy; scale by budget |
| Telemetry/mesh radios and antennas | 4 | 300-800 | 1,200-3,200 | Buy; build networking policy |
| Batteries, chargers, fire-safe storage and spares | set | - | 1,500-2,500 | Buy |
| Ground laptop/router/field cases/fixtures | set | - | 1,500-2,500 | Buy/integrate |
| **Engineering hardware total** | | | **13,500-33,400** | Excludes labor, certification and insurance |

A credible target for a balanced first prototype is roughly EUR 18k-30k.

## Build in-house

- Swarm membership, allocation and leader election.
- Mission assurance and fault recovery.
- RGB/thermal fusion and target lifecycle.
- Digital Twin, evidence and replay tooling.
- DDS security governance and fleet identity.
- Test automation, network emulation and safety case.

## First 30 days - reproduce and specify

- Reproduce the repository in CI and freeze interfaces/QoS.
- Build requirement, hazard and fault traceability.
- Add deterministic network delay/loss emulation.
- Define perception datasets and metrics.
- Select autopilot, companion compute, radios and sensors.

## Days 31-60 - HIL and one-aircraft integration

- PX4 HIL with real companion computer and radios.
- Real RGB/thermal timestamping, calibration and fusion prototype.
- Secure DDS identities and signed software artifacts.
- Hardware watchdog, E-stop and lost-link behavior.
- One-aircraft indoor/tethered validation with rosbag replay.

## Days 61-90 - three-aircraft field prototype

- Three-aircraft networking and time synchronization.
- Controlled task allocation and leader-loss tests.
- Battery rotation and charger/turnaround operations.
- Staged outdoor tests under approved operating procedures.
- Performance report: coverage efficiency, recovery latency, link margin, false alerts and safety interventions.
