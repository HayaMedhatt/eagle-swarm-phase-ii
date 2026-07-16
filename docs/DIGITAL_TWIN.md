# Digital Twin

The browser dashboard at `http://127.0.0.1:8080` is an operational view, not the safety controller.

It displays:

- member role, state, battery, pose, link quality, capability and GPS health;
- current leader, election epoch and reason;
- confirmed target and source;
- bid component breakdown and winning award;
- fault actions and measured recovery times;
- separation interventions and release events.

The dashboard may fail without stopping the mission. This separation is intentional: visualization is ground-station functionality, while landing, battery, GPS and collision precedence remain local to the aerial adapter.
