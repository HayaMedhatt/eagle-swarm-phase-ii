# Technical Defense Preparation

## 1. Explain the ROS 2 graph without opening the document

Three PX4 SITL aircraft expose separate MAVROS namespaces. Each aircraft has one adapter that translates PX4 state into a common heartbeat and translates swarm mission commands into local OFFBOARD setpoints. The DDS bus carries heartbeat, target beacon, bids, retained task awards, leader state, fault events and safety events. Four coordinator replicas observe identical traffic. A deterministic election selects one owner, and only that owner's replica may publish an award. The Ground Relay uses the same generic agent and interfaces. The mission orchestrator gates the demonstration, while the safety monitor is independent of allocation. The browser Digital Twin subscribes only; it cannot control safety.

## 2. Biggest failure point

The largest remaining system-level failure point is the single host running PX4, Gazebo and DDS. Replicated application nodes protect against a coordinator-process or robot-member loss, but not host, power or DDS-domain failure. A production design distributes robots across independent compute and radios, uses DDS security and partitions, and keeps safety locally executable even when the mission network is absent.

## 3. Why this cost equation?

```text
cost = distance + 0.4(100-battery) + role_penalty + 30(1-link)
```

Distance captures response time. Battery penalizes low endurance before it becomes a safety event. Role penalty preserves scarce capabilities: worker is preferred for routine action, scout has a small penalty, Ground Relay a larger penalty, and Coordinator the largest movement penalty. Link penalty strongly discourages assignments that may disconnect. Every component is published, so the winner is explainable. The values are engineering weights, not learned constants; sensitivity testing is a planned calibration activity.

## 4. RGB cue versus thermal confirmation and false positives

The submitted simulation separates the two logical stages. RGB cueing creates a candidate but cannot publish an alert. Thermal confirmation independently authorizes the beacon, which carries `confirmation_source` and confidence. The prototype validates the interface and swarm response, not model accuracy. Production evaluation uses paired labeled RGB/thermal data and reports RGB precision/recall, thermal confirmation precision, fused false-positive rate, false-negative rate and confirmation latency. A confidence threshold is tuned on validation data and frozen before field testing.

## 5. Prove Open/Closed for Ground Relay

No Contract-Net or coordinator branch was added for a Ground Relay. The launch creates a generic `SwarmAgent` with role `ground_relay`. It publishes the same `Heartbeat` and `Bid` and consumes the same beacon and award. Role-specific behavior is configuration in pure policy dictionaries. The allocator accepts any compliant bidder. Adding another ground unit therefore adds configuration and perhaps a platform adapter, not changes to core allocation.

## 6. First 90 days

See `BOM_AND_90_DAY_PLAN.md`. In summary: reproduce the simulation in CI; establish message/QoS and safety requirements; replace deterministic perception with calibrated sensor nodes; add network emulation, HIL and authenticated DDS; build one instrumented three-vehicle prototype; then run staged indoor/outdoor tests with traceable safety cases.

## 7. Prototype BOM and buy versus build

Buy flight-critical commodity hardware: airframes, motors/ESCs, batteries, autopilots, GNSS, radios, cameras and Jetson modules. Build the swarm allocation, perception fusion, mission assurance, Digital Twin, security policy and evidence tooling. A realistic three-aircraft engineering prototype is roughly EUR 18k-30k before labor and regulatory/insurance costs, depending on sensors and radio choice.

## Likely follow-up questions

### Why not full ORCA?

The assessment time box favors an active, testable safety layer. The implementation uses 3-D margins, deterministic yielding and hold/resume. It is honest about being reactive. Full ORCA requires velocity-state quality, dynamic feasibility and more validation than a superficial implementation would receive.

### Why transient-local QoS on beacon/award/leader?

A late-joining or newly authoritative replica must immediately learn the latest target, assignment and leader state. Heartbeats remain volatile because stale health is unsafe.

### What prevents duplicate awards?

Every replica computes the same leader, but only the elected owner's replica publishes. It stores the assignment before publishing, consumes retained awards, ignores bids for assigned/completed targets and uses deterministic bid tie-breaking.

### Why can the Ground Relay become leader?

Leadership is coordination authority, not flight authority. A ground relay may have reliable power and networking. It cannot issue unsafe local flight behavior because each aerial adapter retains the onboard safety boundary.

### What would invalidate the demo?

A scripted log without three PX4 vehicles, failure recovery that requires restarting the full launch, re-auctioning a completed target, collision warnings without intervention, or claims of unimplemented perception accuracy.
