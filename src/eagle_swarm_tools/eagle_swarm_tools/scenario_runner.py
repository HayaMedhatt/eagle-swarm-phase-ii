"""Automated acceptance-scenario runner and evidence recorder.

Run this node against the integrated PX4/Gazebo launch.  It injects one fault,
observes the DDS recovery evidence, writes JSON/Markdown artifacts, and exits
non-zero if the assessment acceptance criteria are not observed before timeout.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Dict, List, Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from rclpy.utilities import remove_ros_args
from std_msgs.msg import String

from eagle_swarm_msgs.msg import (
    FaultEvent,
    Heartbeat,
    LeaderState,
    SafetyEvent,
    TaskAward,
)


OPERATIONAL_STATES = {
    "ACTIVE",
    "COVERAGE",
    "SECTOR_READY",
    "EXECUTING",
    "ARRIVED",
    "SAFE_HOLD",
}


def retained_qos(depth: int = 20) -> QoSProfile:
    """Match retained leader/award publishers and receive their latest sample."""
    return QoSProfile(
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
        history=HistoryPolicy.KEEP_LAST,
        depth=depth,
    )


RECOVERY_EVENT_TYPES = {
    "shutdown": {"heartbeat_timeout"},
    "coordinator_loss": {"coordinator_loss_recovery"},
    "wifi_cut": {"wifi_cut", "heartbeat_restored"},
    "gps_dropout": {"gps_dropout"},
    "critical_battery": {"critical_battery"},
    "separation": set(),
}


@dataclass
class RecordedEvent:
    elapsed_sec: float
    kind: str
    summary: str
    data: dict


class ScenarioRunner(Node):
    """Inject one deterministic scenario and prove its acceptance conditions."""

    def __init__(
        self,
        scenario: str,
        requested_robot: str,
        output_root: Path,
        timeout_sec: float,
        restore_delay_sec: float,
    ) -> None:
        super().__init__(f"scenario_runner_{scenario}")
        self.scenario = scenario
        self.requested_robot = requested_robot
        self.timeout_sec = timeout_sec
        self.restore_delay_sec = restore_delay_sec
        self.started_wall = time.monotonic()
        self.started_utc = datetime.now(timezone.utc)
        run_stamp = self.started_utc.strftime("%Y%m%dT%H%M%SZ")
        self.output_dir = output_root / f"{scenario}_{run_stamp}"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.heartbeats: Dict[str, Heartbeat] = {}
        self.leader: Optional[LeaderState] = None
        self.leader_history: List[str] = []
        self.awards: List[TaskAward] = []
        self.faults: List[FaultEvent] = []
        self.safety_events: List[SafetyEvent] = []
        self.events: List[RecordedEvent] = []

        self.phase = "WAIT_READY"
        self.target_robot = ""
        self.initial_leader = ""
        self.initial_award: Optional[TaskAward] = None
        self.injected_at: Optional[float] = None
        self.restore_sent = False
        self.finished = False
        self.passed = False
        self.failure_reason = ""

        self.command_pub = self.create_publisher(
            String, "/swarm/fault_command", 10
        )
        self.mission_pub = self.create_publisher(
            String, "/swarm/mission_command", 20
        )
        self.create_subscription(Heartbeat, "/swarm/heartbeat", self.on_hb, 50)
        self.create_subscription(
            LeaderState, "/swarm/leader", self.on_leader, retained_qos()
        )
        self.create_subscription(FaultEvent, "/swarm/faults", self.on_fault, 50)
        self.create_subscription(
            TaskAward, "/swarm/task_award", self.on_award, retained_qos()
        )
        self.create_subscription(
            SafetyEvent, "/swarm/safety_events", self.on_safety, 20
        )
        self.create_timer(0.2, self.tick)
        self.record(
            "scenario",
            f"started {scenario}; requested_robot={requested_robot}",
            {"scenario": scenario, "requested_robot": requested_robot},
        )
        self.get_logger().warn(
            f"Acceptance scenario '{scenario}' waiting for readiness; "
            f"evidence={self.output_dir}"
        )

    def elapsed(self) -> float:
        return time.monotonic() - self.started_wall

    def record(self, kind: str, summary: str, data: dict) -> None:
        self.events.append(
            RecordedEvent(
                elapsed_sec=round(self.elapsed(), 3),
                kind=kind,
                summary=summary,
                data=data,
            )
        )

    @staticmethod
    def stamp_dict(msg_stamp) -> dict:
        return {"sec": int(msg_stamp.sec), "nanosec": int(msg_stamp.nanosec)}

    def on_hb(self, msg: Heartbeat) -> None:
        previous = self.heartbeats.get(msg.robot_id)
        self.heartbeats[msg.robot_id] = msg
        if previous is None or previous.state != msg.state or previous.gps_ok != msg.gps_ok:
            self.record(
                "heartbeat",
                f"{msg.robot_id} state={msg.state} gps_ok={msg.gps_ok}",
                {
                    "robot_id": msg.robot_id,
                    "role": msg.role,
                    "state": msg.state,
                    "battery": round(float(msg.battery), 3),
                    "link_quality": round(float(msg.link_quality), 3),
                    "gps_ok": bool(msg.gps_ok),
                    "stamp": self.stamp_dict(msg.stamp),
                },
            )

    def on_leader(self, msg: LeaderState) -> None:
        if not self.leader_history or self.leader_history[-1] != msg.leader_id:
            self.leader_history.append(msg.leader_id)
            self.record(
                "leader",
                f"leader={msg.leader_id} epoch={msg.election_epoch}",
                {
                    "leader_id": msg.leader_id,
                    "reason": msg.reason,
                    "election_epoch": int(msg.election_epoch),
                    "stamp": self.stamp_dict(msg.stamp),
                },
            )
        self.leader = msg

    def on_award(self, msg: TaskAward) -> None:
        duplicate = any(
            old.target_id == msg.target_id
            and old.winner_id == msg.winner_id
            and old.assigned_by == msg.assigned_by
            for old in self.awards
        )
        if duplicate:
            return
        self.awards.append(msg)
        self.record(
            "award",
            f"{msg.target_id}->{msg.winner_id} cost={msg.winning_cost:.2f}",
            {
                "target_id": msg.target_id,
                "winner_id": msg.winner_id,
                "assigned_by": msg.assigned_by,
                "winning_cost": round(float(msg.winning_cost), 3),
                "stamp": self.stamp_dict(msg.stamp),
            },
        )

    def on_fault(self, msg: FaultEvent) -> None:
        self.faults.append(msg)
        self.record(
            "fault",
            f"{msg.fault_type}@{msg.robot_id}: {msg.action}",
            {
                "fault_type": msg.fault_type,
                "robot_id": msg.robot_id,
                "severity": int(msg.severity),
                "action": msg.action,
                "recovery_time": round(float(msg.recovery_time), 3),
                "stamp": self.stamp_dict(msg.stamp),
            },
        )

    def on_safety(self, msg: SafetyEvent) -> None:
        self.safety_events.append(msg)
        self.record(
            "safety",
            f"{msg.event_type} {msg.robot_a}/{msg.robot_b} {msg.separation:.2f}m",
            {
                "event_type": msg.event_type,
                "robot_a": msg.robot_a,
                "robot_b": msg.robot_b,
                "separation": round(float(msg.separation), 3),
                "action": msg.action,
                "stamp": self.stamp_dict(msg.stamp),
            },
        )

    def publish_fault_command(self, fault_type: str, robot_id: str) -> None:
        command = f"{fault_type}:{robot_id}"
        for _ in range(3):
            self.command_pub.publish(String(data=command))
        self.record("injection", f"INJECT {command}", {"command": command})
        self.get_logger().warn(f"INJECT {command}")

    def operational(self, robot_id: str) -> bool:
        heartbeat = self.heartbeats.get(robot_id)
        return heartbeat is not None and heartbeat.state in OPERATIONAL_STATES

    def select_ready_robot(self, default: str = "worker_1") -> Optional[str]:
        requested = self.requested_robot
        robot_id = default if requested == "auto" else requested
        return robot_id if self.operational(robot_id) else None

    def start_simple_recoverable(self, fault_type: str, default_robot: str) -> None:
        robot_id = self.select_ready_robot(default_robot)
        if robot_id is None:
            return
        self.target_robot = robot_id
        self.publish_fault_command(fault_type, robot_id)
        self.injected_at = time.monotonic()
        self.phase = "WAIT_RESTORE"

    def start_award_disruption(self, fault_type: str) -> None:
        if not self.awards:
            return
        award = self.awards[-1]
        robot_id = award.winner_id if self.requested_robot == "auto" else self.requested_robot
        if award.winner_id != robot_id:
            self.fail(
                f"requested robot {robot_id} is not current winner {award.winner_id}; "
                "use --robot auto for deterministic reassignment evidence"
            )
            return
        self.initial_award = award
        self.target_robot = robot_id
        self.publish_fault_command(fault_type, robot_id)
        self.injected_at = time.monotonic()
        self.phase = "WAIT_ACCEPTANCE"

    def start_coordinator_loss(self) -> None:
        # Inject only after the first allocation so recovery proves that the
        # active mission continues under the replacement authority.
        if self.leader is None or not self.leader.leader_id or not self.awards:
            return
        selected = (
            self.leader.leader_id
            if self.requested_robot == "auto"
            else self.requested_robot
        )
        if selected != self.leader.leader_id:
            return
        self.target_robot = selected
        self.initial_leader = self.leader.leader_id
        self.initial_award = self.awards[-1]
        self.publish_fault_command("coordinator_loss", selected)
        self.injected_at = time.monotonic()
        self.phase = "WAIT_ACCEPTANCE"

    def start_separation(self) -> None:
        required = ("scout_1", "worker_1", "relay_1")
        if not all(
            robot_id in self.heartbeats
            and self.heartbeats[robot_id].state == "SECTOR_READY"
            for robot_id in required
        ):
            return

        scout = self.heartbeats["scout_1"]
        worker = self.heartbeats["worker_1"]
        scout_start = (
            float(scout.pose.position.x),
            float(scout.pose.position.y),
        )
        worker_start = (
            float(worker.pose.position.x),
            float(worker.pose.position.y),
        )
        commands = [
            f"sector:scout_1:{worker_start[0]:.3f}:{worker_start[1]:.3f}",
            f"sector:worker_1:{scout_start[0]:.3f}:{scout_start[1]:.3f}",
        ]
        for command in commands:
            for _ in range(3):
                self.mission_pub.publish(String(data=command))
            self.record("injection", f"CROSSING {command}", {"command": command})
        self.target_robot = "scout_1/worker_1"
        self.injected_at = time.monotonic()
        self.phase = "WAIT_ACCEPTANCE"
        self.get_logger().warn(
            "Injected crossing goals for scout_1 and worker_1; "
            "waiting for intervention and clear"
        )

    def fault_exists(
        self,
        fault_type: str,
        robot_id: Optional[str] = None,
        recovered: Optional[bool] = None,
    ) -> bool:
        for event in self.faults:
            if event.fault_type != fault_type:
                continue
            if robot_id is not None and event.robot_id != robot_id:
                continue
            is_recovered = float(event.recovery_time) > 0.0
            if recovered is None or recovered == is_recovered:
                return True
        return False

    def reassigned_award(self) -> Optional[TaskAward]:
        if self.initial_award is None:
            return None
        for award in self.awards:
            if (
                award.target_id == self.initial_award.target_id
                and award.winner_id != self.initial_award.winner_id
            ):
                return award
        return None

    def evaluate_acceptance(self) -> None:
        robot_id = self.target_robot
        if self.scenario == "wifi_cut":
            hb = self.heartbeats.get(robot_id)
            if (
                self.restore_sent
                and hb is not None
                and self.fault_exists("wifi_cut", robot_id, recovered=True)
                and self.fault_exists("heartbeat_restored", robot_id, recovered=True)
            ):
                self.succeed("Wi-Fi partition detected, restored, and member rejoined")

        elif self.scenario == "gps_dropout":
            hb = self.heartbeats.get(robot_id)
            if (
                self.restore_sent
                and hb is not None
                and hb.gps_ok
                and hb.state != "SAFE_HOLD"
                and self.fault_exists("gps_dropout", robot_id, recovered=True)
            ):
                self.succeed("GPS dropout caused hold; restore resumed previous state")

        elif self.scenario == "coordinator_loss":
            leader_changed = (
                self.leader is not None
                and self.leader.leader_id
                and self.leader.leader_id != self.initial_leader
            )
            mission_continued = False
            continuation_summary = ""
            if self.initial_award is not None:
                original_winner = self.initial_award.winner_id
                if original_winner != self.initial_leader:
                    hb = self.heartbeats.get(original_winner)
                    mission_continued = hb is not None and hb.state == "ARRIVED"
                    continuation_summary = (
                        f"original winner {original_winner} reached ARRIVED"
                    )
                else:
                    replacement = self.reassigned_award()
                    if replacement is not None:
                        hb = self.heartbeats.get(replacement.winner_id)
                        mission_continued = hb is not None and hb.state == "ARRIVED"
                        continuation_summary = (
                            f"target re-awarded to {replacement.winner_id} and ARRIVED"
                        )

            if (
                leader_changed
                and mission_continued
                and self.fault_exists(
                    "coordinator_loss_recovery",
                    self.initial_leader,
                    recovered=True,
                )
            ):
                self.succeed(
                    f"Leader changed {self.initial_leader}->{self.leader.leader_id}; "
                    f"{continuation_summary}"
                )

        elif self.scenario == "separation":
            relevant = [
                event
                for event in self.safety_events
                if {event.robot_a, event.robot_b} == {"scout_1", "worker_1"}
            ]
            intervention = next(
                (
                    event
                    for event in relevant
                    if event.event_type
                    in {"SEPARATION_INTERVENTION", "NEAR_MISS"}
                ),
                None,
            )
            clear = next(
                (
                    event
                    for event in relevant
                    if event.event_type == "SEPARATION_CLEAR"
                ),
                None,
            )
            both_healthy = all(
                robot_id in self.heartbeats
                and self.heartbeats[robot_id].state not in {"SHUTDOWN", "LANDED"}
                for robot_id in ("scout_1", "worker_1")
            )
            if intervention is not None and clear is not None and both_healthy:
                self.succeed(
                    "Crossing paths triggered active hold and hysteretic release "
                    "without losing either aircraft"
                )

        elif self.scenario == "shutdown":
            replacement = self.reassigned_award()
            replacement_hb = (
                self.heartbeats.get(replacement.winner_id)
                if replacement is not None
                else None
            )
            if (
                replacement is not None
                and replacement_hb is not None
                and replacement_hb.state == "ARRIVED"
                and self.fault_exists("shutdown", robot_id)
                and self.fault_exists("heartbeat_timeout", robot_id, recovered=True)
                and self.fault_exists("task_reassignment", robot_id)
            ):
                self.succeed(
                    f"Failed winner excluded; {replacement.winner_id} accepted the "
                    "re-award and reached ARRIVED"
                )

        elif self.scenario == "critical_battery":
            replacement = self.reassigned_award()
            replacement_hb = (
                self.heartbeats.get(replacement.winner_id)
                if replacement is not None
                else None
            )
            if (
                replacement is not None
                and replacement_hb is not None
                and replacement_hb.state == "ARRIVED"
                and self.fault_exists("task_reassignment", robot_id)
                and self.fault_exists("critical_battery", robot_id, recovered=True)
            ):
                self.succeed(
                    f"Critical-battery winner returned and landed; "
                    f"{replacement.winner_id} accepted the re-award and reached ARRIVED"
                )

    def tick(self) -> None:
        if self.finished:
            return
        if self.elapsed() > self.timeout_sec:
            self.fail(
                f"timeout after {self.timeout_sec:.1f}s in phase={self.phase}"
            )
            return

        if self.phase == "WAIT_READY":
            if self.scenario == "wifi_cut":
                self.start_simple_recoverable("wifi_cut", "worker_1")
            elif self.scenario == "gps_dropout":
                self.start_simple_recoverable("gps_dropout", "scout_1")
            elif self.scenario == "coordinator_loss":
                self.start_coordinator_loss()
            elif self.scenario == "shutdown":
                self.start_award_disruption("shutdown")
            elif self.scenario == "critical_battery":
                self.start_award_disruption("critical_battery")
            elif self.scenario == "separation":
                self.start_separation()

        elif self.phase == "WAIT_RESTORE":
            if (
                self.injected_at is not None
                and not self.restore_sent
                and time.monotonic() - self.injected_at >= self.restore_delay_sec
            ):
                restore = (
                    "wifi_restore"
                    if self.scenario == "wifi_cut"
                    else "gps_restore"
                )
                self.publish_fault_command(restore, self.target_robot)
                self.restore_sent = True
                self.phase = "WAIT_ACCEPTANCE"

        if self.phase == "WAIT_ACCEPTANCE":
            self.evaluate_acceptance()

    def succeed(self, reason: str) -> None:
        self.passed = True
        self.finished = True
        self.record("result", f"PASS: {reason}", {"passed": True, "reason": reason})
        self.write_evidence(reason)
        self.get_logger().warn(f"SCENARIO PASS: {reason}")

    def fail(self, reason: str) -> None:
        if self.finished:
            return
        self.passed = False
        self.finished = True
        self.failure_reason = reason
        self.record("result", f"FAIL: {reason}", {"passed": False, "reason": reason})
        self.write_evidence(reason)
        self.get_logger().error(f"SCENARIO FAIL: {reason}")

    def write_evidence(self, reason: str) -> None:
        accepted_recovery_types = RECOVERY_EVENT_TYPES[self.scenario]
        recovery_events = [
            {
                "fault_type": event.fault_type,
                "robot_id": event.robot_id,
                "recovery_time": round(float(event.recovery_time), 3),
                "action": event.action,
            }
            for event in self.faults
            if event.fault_type in accepted_recovery_types
            and float(event.recovery_time) > 0.0
        ]
        measured_recovery_sec = max(
            (item["recovery_time"] for item in recovery_events),
            default=0.0,
        )
        if self.scenario == "separation":
            intervention_time = next(
                (
                    event.elapsed_sec
                    for event in self.events
                    if event.kind == "safety"
                    and (
                        "SEPARATION_INTERVENTION" in event.summary
                        or "NEAR_MISS" in event.summary
                    )
                ),
                None,
            )
            clear_time = next(
                (
                    event.elapsed_sec
                    for event in self.events
                    if event.kind == "safety"
                    and "SEPARATION_CLEAR" in event.summary
                ),
                None,
            )
            if intervention_time is not None and clear_time is not None:
                measured_recovery_sec = round(
                    max(0.0, clear_time - intervention_time), 3
                )
                recovery_events = [
                    {
                        "event_type": "SEPARATION_CLEAR",
                        "recovery_time": measured_recovery_sec,
                        "action": "held aircraft released above hysteresis margin",
                    }
                ]
        payload = {
            "schema_version": 2,
            "scenario": self.scenario,
            "requested_robot": self.requested_robot,
            "target_robot": self.target_robot,
            "started_utc": self.started_utc.isoformat(),
            "duration_sec": round(self.elapsed(), 3),
            "measured_recovery_sec": measured_recovery_sec,
            "recovery_events": recovery_events,
            "passed": self.passed,
            "reason": reason,
            "initial_leader": self.initial_leader,
            "final_leader": self.leader.leader_id if self.leader else "",
            "leader_history": self.leader_history,
            "initial_award": (
                {
                    "target_id": self.initial_award.target_id,
                    "winner_id": self.initial_award.winner_id,
                    "assigned_by": self.initial_award.assigned_by,
                    "winning_cost": round(
                        float(self.initial_award.winning_cost), 3
                    ),
                }
                if self.initial_award is not None
                else None
            ),
            "events": [asdict(event) for event in self.events],
        }
        json_path = self.output_dir / "evidence.json"
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True))

        status = "PASS" if self.passed else "FAIL"
        rows = [
            f"# {self.scenario.replace('_', ' ').title()} Evidence",
            "",
            f"**Result:** {status}",
            "",
            f"**Target robot:** `{self.target_robot or 'not selected'}`  ",
            f"**Scenario duration:** {payload['duration_sec']:.2f} s  ",
            f"**Measured recovery:** {payload['measured_recovery_sec']:.2f} s  ",
            f"**Reason:** {reason}",
            "",
            "## Timeline",
            "",
            "| t (s) | Kind | Evidence |",
            "|---:|---|---|",
        ]
        for event in self.events:
            safe_summary = event.summary.replace("|", "\\|")
            rows.append(
                f"| {event.elapsed_sec:.3f} | {event.kind} | {safe_summary} |"
            )
        rows.extend(
            [
                "",
                "## Machine-readable artifact",
                "",
                "See `evidence.json` in this directory.",
                "",
            ]
        )
        (self.output_dir / "EVIDENCE.md").write_text("\n".join(rows))
        (self.output_dir / ("PASS" if self.passed else "FAIL")).write_text(
            reason + "\n"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one EAGLE SWARM acceptance scenario and record evidence."
    )
    parser.add_argument(
        "--scenario",
        required=True,
        choices=[
            "shutdown",
            "coordinator_loss",
            "wifi_cut",
            "gps_dropout",
            "critical_battery",
            "separation",
        ],
    )
    parser.add_argument(
        "--robot",
        default="auto",
        help="Robot ID or 'auto'. Auto targets the current winner/leader where relevant.",
    )
    parser.add_argument(
        "--output",
        default=str(Path.home() / "eagle_swarm_ws/evidence/runtime"),
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--restore-delay", type=float, default=5.0)
    return parser


def main(args=None) -> None:
    cli = remove_ros_args(args=sys.argv if args is None else args)[1:]
    parsed = build_parser().parse_args(cli)
    rclpy.init(args=None)
    node = ScenarioRunner(
        scenario=parsed.scenario,
        requested_robot=parsed.robot,
        output_root=Path(parsed.output).expanduser(),
        timeout_sec=float(parsed.timeout),
        restore_delay_sec=float(parsed.restore_delay),
    )
    try:
        while rclpy.ok() and not node.finished:
            rclpy.spin_once(node, timeout_sec=0.2)
    except KeyboardInterrupt:
        node.fail("interrupted by operator")
    finally:
        passed = node.passed
        output_dir = node.output_dir
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    print(f"Evidence written to: {output_dir}")
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
