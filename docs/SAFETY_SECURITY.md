# Safety and Cybersecurity Design Justification

## Safety architecture

### Command authority order

```text
E-Stop / hard shutdown
> landing
> critical-battery RTB
> GPS safe hold / collision hold
> normal mission execution
> coverage patrol
```

The allocator never bypasses the aerial adapter. The adapter is the Onboard Safety Authority and may reject awards based on state, GPS validity, battery reserve or landing state.

### Implemented simulation controls

- Continuous OFFBOARD setpoint stream and health-gated arming.
- Battery reserve at approximately 25%, automatic task release, RTB and landing.
- GPS dropout safe hold and rejection of new awards.
- Independent 3-D separation monitor with intervention, hard and release margins.
- Deterministic yielding policy that preserves the executing/higher-priority path.
- Landing transition protected from delayed hold/resume commands.
- Heartbeat timeout, assignment reopening and measured recovery events.
- Physical collision geometry on the target landing platform.

### Production additions

- Hardware E-stop and geofence enforced below ROS.
- Flight-controller watchdog and companion-computer heartbeat.
- Redundant GNSS plus VIO/INS and sensor-consistency checks.
- Independent low-battery and lost-link failsafes configured in PX4.
- Formal operating envelope, weather limits, preflight checklist and maintenance records.
- HIL and fault-tree testing before outdoor multi-vehicle operation.

## Cybersecurity threats and controls

| Threat | Design control |
|---|---|
| Robot hijacking | DDS Security identity, encrypted/authenticated transport, least-privilege governance, signed operator commands |
| Fake robot joining | Per-device certificates, allowlisted identities, role authorization and membership audit |
| Replay attack | DDS sequence/timestamp checks, bounded message age, nonce/session protection for external gateways |
| GPS spoofing | Multi-sensor innovation checks, GNSS/VIO disagreement detection, safe hold/RTB, map/geofence plausibility |
| Firmware tampering | Secure boot, signed PX4/companion images, measured update process and artifact hashes |
| Ground-station compromise | Segmented networks, MFA, read-only dashboard role, signed mission releases and audit logs |
| Denial of service | QoS limits, rate limiting, separate safety topics, local autonomy during partition and radio diversity |
| Malicious target beacon | Sensor-source authentication, confidence/confirmation policy, plausibility bounds and human authorization |

## Civilian-use boundary

The system performs sensing, mapping, alerting and safe navigation only. It contains no engagement, targeting-for-force or autonomous response logic. Human operators or competent authorities decide any real-world response.
