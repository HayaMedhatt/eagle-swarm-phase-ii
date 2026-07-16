# Requirements Traceability Matrix

Status meanings: **Implemented** means the source path is complete; **Runtime evidence required** means the candidate must execute the supplied acceptance command and retain its generated PASS artifact; **Design justification** is explicitly allowed by the assessment.

| Assessment requirement | Implementation | Acceptance evidence | Status before final recording |
|---|---|---|---|
| Operational architecture for Scout, Worker, Coordinator/Relay, Ground Station, Mission Planner, Digital Twin, PX4/MAVLink and DDS | `docs/ARCHITECTURE.md`, `docs/architecture_diagram.pdf` | Explain graph and safety boundary | Implemented |
| Messages, responsibilities, failure point and Onboard Safety Authority | Custom interfaces plus architecture failure table | Show interfaces and boundary | Implemented |
| Repository builds with `colcon build` | Seven ROS packages and build scripts | Final clean build log | Runtime evidence required |
| Three PX4 units take off, hover, move in sectors and land | `start_integrated_demo.sh`, `px4_adapter.py`, `mission_demo.py`; PX4-disarm touchdown supports raised target | Normal video and `DEMO COMPLETE` | Implemented; recapture final run |
| Coverage partitioning | Constrained random planner with seed, wedges and pairwise safety gate | Three distinct paths and logged seed | Implemented and unit-tested |
| `/swarm/heartbeat` | Aerial adapters and generic Ground Relay | Dashboard / topic echo | Implemented |
| RGB cue then thermal confirmation | Separate deterministic mission stages; confidence gate | Log and target beacon fields | Implemented simulation contract |
| `/swarm/target_beacon` required fields | `TargetBeacon.msg`, `publish_target()` | Dashboard beacon card | Implemented |
| Digital Twin initial/live view | `web_dashboard.py` | Browser screen capture | Implemented |
| Contract-Net four-term cost | `compute_task_cost()` and published `Bid` components | Four bids plus chosen minimum | Implemented and unit-tested |
| Coordinator selects via bids/award | Replicated `coordinator.py` | `ALLOCATE` and retained award | Implemented |
| Local allocation when Coordinator fails | Four deterministic replicas; elected owner's replica is authority | Coordinator-loss PASS artifact | Implemented; runtime evidence required |
| Leader election on coordinator loss | Stable initial membership, weighted deterministic election, epoch | New leader and measured recovery | Implemented; runtime evidence required |
| Mission continues after leader loss | Other replicas remain running; scenario injects after first award | Original or replacement winner reaches `ARRIVED` after failover | Runtime evidence required |
| Virtual battery decreases with time/motion | Aerial adapter virtual battery model | Heartbeat battery trend | Implemented |
| Reserve threshold around 25% triggers RTB | Onboard safety authority in `enter_rtb()` | Critical-battery PASS artifact | Implemented; runtime evidence required |
| Coverage/task re-assigned after RTB | Coordinator reopens assignment and republishes beacon | Different winner reaches `ARRIVED` in evidence JSON | Implemented; runtime evidence required |
| Collision avoidance and near-miss log | 3-D separation monitor, hold/resume, intervention/hard/release margins, one-shot near-miss escalation | Crossing-path scenario produces intervention, clear and measured duration | Implemented; automated runtime evidence required |
| Drone shutdown | Hard unit-loss command stops heartbeat and setpoint stream | Timeout, re-award and replacement `ARRIVED` in PASS artifact | Implemented; runtime evidence required |
| Virtual Wi-Fi cut | DDS isolation while local PX4 setpoint stream continues | Cut/restore/rejoin PASS artifact | Implemented; runtime evidence required |
| GPS dropout | Local safe hold and award rejection; restore previous state | Dropout/restore PASS artifact | Implemented; runtime evidence required |
| Recovery time for every fault | Fault events plus automated scenario wall-clock timeline | `evidence.json` and `EVIDENCE.md` | Implemented; runtime evidence required |
| Ground Relay extension | Generic `SwarmAgent`, same heartbeat/beacon/bid/award contracts | Ground Relay bid and leader candidacy | Implemented |
| Open/Closed Principle | New robot type added by launch configuration, not allocator rewrite | Explain reused interfaces/policies | Implemented |
| Role-change service | Single routed service and role-command topic | Service call | Implemented |
| Go-to-target action | Three namespaced action servers | `ros2 action list` and test goal | Implemented |
| Fault topic | `FaultEvent.msg` and scenario runner | Dashboard/evidence timeline | Implemented |
| Safety/cybersecurity justification | `docs/SAFETY_SECURITY.md` | Oral defense | Design justification complete |
| Repository, diagram, video, tech doc, README/launch | Source, PDFs, demo plan and scripts | Final package/video | Video and final runtime evidence remain |
