# Evidence Status

- `baseline_normal/real_swarm_excerpt.log` contains selected milestones from successful candidate-machine runs before final packaging.
- `runtime/` is intentionally generated on the final Ubuntu/PX4 machine by `run_full_acceptance_campaign.sh`.
- `RUNTIME_EVIDENCE_INDEX.md` is generated only after the normal mission and all five mandatory fault scenarios and the scored separation scenario are evaluated.

A source archive without generated runtime PASS artifacts is implementation-complete but not evidence-complete. The repository never converts missing evidence into a claimed PASS.
