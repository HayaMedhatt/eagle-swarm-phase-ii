#!/usr/bin/env python3
"""Emit MAVLink v1 GCS heartbeats to local PX4 SITL instances."""

from __future__ import annotations

import argparse
import select
import socket
import struct
import time
from typing import Iterable

MAVLINK_V1_STX = 0xFE
MAVLINK_MSG_ID_HEARTBEAT = 0
MAVLINK_MSG_HEARTBEAT_LEN = 9
MAVLINK_MSG_HEARTBEAT_CRC_EXTRA = 50

MAV_TYPE_GCS = 6
MAV_AUTOPILOT_INVALID = 8
MAV_MODE_FLAG_NONE = 0
MAV_STATE_ACTIVE = 4
MAVLINK_VERSION = 3


def x25_crc(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        tmp = byte ^ (crc & 0xFF)
        tmp ^= (tmp << 4) & 0xFF
        crc = (
            (crc >> 8)
            ^ (tmp << 8)
            ^ (tmp << 3)
            ^ (tmp >> 4)
        ) & 0xFFFF
    return crc


def heartbeat_packet(sequence: int, system_id: int, component_id: int) -> bytes:
    payload = struct.pack(
        "<IBBBBB",
        0,
        MAV_TYPE_GCS,
        MAV_AUTOPILOT_INVALID,
        MAV_MODE_FLAG_NONE,
        MAV_STATE_ACTIVE,
        MAVLINK_VERSION,
    )
    header = bytes(
        [
            MAVLINK_MSG_HEARTBEAT_LEN,
            sequence & 0xFF,
            system_id & 0xFF,
            component_id & 0xFF,
            MAVLINK_MSG_ID_HEARTBEAT,
        ]
    )
    checksum = x25_crc(
        header + payload + bytes([MAVLINK_MSG_HEARTBEAT_CRC_EXTRA])
    )
    return (
        bytes([MAVLINK_V1_STX])
        + header
        + payload
        + struct.pack("<H", checksum)
    )


def drain_socket(sock: socket.socket) -> None:
    while True:
        readable, _, _ = select.select([sock], [], [], 0.0)
        if not readable:
            return
        try:
            sock.recvfrom(65535)
        except BlockingIOError:
            return


def run(
    host: str,
    ports: Iterable[int],
    bind_port: int,
    rate_hz: float,
    system_id: int,
    component_id: int,
) -> None:
    destinations = [(host, int(port)) for port in ports]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)

    try:
        sock.bind((host, bind_port))
        bound = sock.getsockname()
    except OSError as exc:
        print(
            f"[gcs_heartbeat] Could not bind {host}:{bind_port}: {exc}; "
            "using an ephemeral port",
            flush=True,
        )
        sock.bind((host, 0))
        bound = sock.getsockname()

    print(
        "[gcs_heartbeat] Sending MAVLink GCS heartbeat "
        f"from {bound[0]}:{bound[1]} to "
        + ", ".join(f"{h}:{p}" for h, p in destinations),
        flush=True,
    )

    period = 1.0 / max(rate_hz, 0.2)
    sequence = 0
    while True:
        packet = heartbeat_packet(sequence, system_id, component_id)
        for destination in destinations:
            sock.sendto(packet, destination)
        sequence = (sequence + 1) & 0xFF
        drain_socket(sock)
        time.sleep(period)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--ports",
        type=int,
        nargs="+",
        default=[18570, 18571, 18572],
    )
    parser.add_argument("--bind-port", type=int, default=14550)
    parser.add_argument("--rate-hz", type=float, default=1.0)
    parser.add_argument("--system-id", type=int, default=255)
    parser.add_argument("--component-id", type=int, default=190)
    args = parser.parse_args()

    try:
        run(
            host=args.host,
            ports=args.ports,
            bind_port=args.bind_port,
            rate_hz=args.rate_hz,
            system_id=args.system_id,
            component_id=args.component_id,
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
