# Final Engineering Changelog

## Flight and mission behavior

- Moved the default target from `(6, 0)` to `(10, 0)` for clearer spatial separation.
- Added matching physical collision geometry to the target platform and a retrying startup health gate that fails loudly if Gazebo does not create it.
- Corrected final behavior: the Contract-Net winner lands directly on the target; non-winners return to their individual launch points and land. LANDED detection now uses PX4 disarm rather than a ground-level altitude threshold, so raised-platform touchdown completes correctly.
- Reduced arrival-to-land transition delay and froze the current target pose until PX4 accepts landing, removing the illogical climb before descent.
- Protected terminal landing from delayed separation `hold` commands.

## Coverage

- Replaced identical parallel steps with constrained randomized fan-out.
- Added role-specific angular sectors, radial limits, pairwise-goal separation and bounded rejection sampling.
- Logged the random seed and minimum planned separation for replay and defense.
- Extracted the planner into a ROS-independent, unit-tested policy module.

## Swarm coordination

- Added four deterministic coordinator replicas: three aerial owners plus Ground Relay.
- Limited award/fault authority to the elected owner's replica.
- Added stable initial DDS-membership gating to avoid transient startup leader churn.
- Added deterministic leader tie-breaking and explicit `coordinator_loss` semantics.
- Preserved retained target/award/leader state for takeover continuity.

## Fault acceptance

- Added automated scenarios for shutdown, coordinator loss, Wi-Fi cut, GPS dropout and critical battery.
- Added exact readiness gates, auto-selection of the current leader/winner and non-zero exit on failed acceptance. Coordinator loss is injected after allocation and must prove post-failover target arrival.
- Added JSON and Markdown timelines with measured recovery events. Destructive winner faults pass only after a replacement reaches `ARRIVED`.
- Hardened virtual Wi-Fi partition semantics: heartbeat, bids, awards and mission/role commands are suppressed while onboard PX4 setpoints and local safety continue; cached targets are rebid after restoration.
- Added isolated campaign execution using fixed replayable seeds and immutable timestamped campaign directories, preventing stale evidence from satisfying a new run.
- Added a scored crossing-path separation scenario and an overall evidence index that cannot report PASS unless the normal mission, all five mandatory faults and separation recovery pass.

## Verification and delivery

- Added one-shot hard-margin near-miss escalation while preserving hysteretic hold/resume behavior.
- Added fifteen pure unit tests for cost, election, safety priority, coverage and evidence processing.
- Added Python/XML/SDF/Bash/artifact preflight.
- Added source-only packaging with ZIP integrity and SHA-256 output.
- Rebuilt architecture, traceability, technical report, defense, safety, demo and checklist documentation around the final behavior.
