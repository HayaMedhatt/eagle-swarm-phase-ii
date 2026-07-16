#!/usr/bin/env python3
"""Browser-based Digital Twin for the EAGLE SWARM ROS 2 prototype.

Uses only Python's standard library plus rclpy, so no Flask/PyQt installation is
required. The ROS node owns the live state while a small HTTP server exposes a
JSON snapshot and a responsive operations dashboard at http://127.0.0.1:8080.
"""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

from eagle_swarm_msgs.msg import (
    Bid,
    FaultEvent,
    Heartbeat,
    LeaderState,
    SafetyEvent,
    TargetBeacon,
    TaskAward,
)


def retained_qos(depth: int = 10) -> QoSProfile:
    return QoSProfile(
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
        history=HistoryPolicy.KEEP_LAST,
        depth=depth,
    )


HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>EAGLE SWARM Digital Twin</title>
<style>
:root { --bg:#07111d; --panel:#0d1b2b; --panel2:#102237; --text:#eaf2ff; --muted:#8fa8c3; --ok:#53d18b; --warn:#ffc857; --bad:#ff6b6b; --accent:#55a8ff; --line:#203a57; }
*{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at 20% 0%,#102742 0,#07111d 42%);color:var(--text);font-family:Inter,Segoe UI,Arial,sans-serif;min-height:100vh}
header{display:flex;align-items:center;justify-content:space-between;padding:18px 24px;border-bottom:1px solid var(--line);background:rgba(7,17,29,.85);position:sticky;top:0;z-index:5;backdrop-filter:blur(10px)}
.brand{display:flex;gap:12px;align-items:center}.logo{width:40px;height:40px;border:2px solid var(--accent);border-radius:50%;display:grid;place-items:center;font-weight:800;color:var(--accent)}
h1{font-size:18px;margin:0;letter-spacing:.12em}.sub{font-size:12px;color:var(--muted);margin-top:4px}.live{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--ok)}.dot{width:9px;height:9px;background:var(--ok);border-radius:50%;box-shadow:0 0 12px var(--ok)}
main{padding:18px;display:grid;grid-template-columns:minmax(540px,1.55fr) minmax(320px,.85fr);gap:16px}.panel{background:linear-gradient(180deg,rgba(16,34,55,.96),rgba(10,24,40,.96));border:1px solid var(--line);border-radius:15px;box-shadow:0 18px 50px rgba(0,0,0,.22)}
.panel h2{font-size:12px;letter-spacing:.16em;color:var(--muted);margin:0;padding:15px 16px;border-bottom:1px solid var(--line)}
.map-wrap{padding:14px}.map{position:relative;height:530px;border-radius:12px;overflow:hidden;background-image:linear-gradient(rgba(85,168,255,.10) 1px,transparent 1px),linear-gradient(90deg,rgba(85,168,255,.10) 1px,transparent 1px);background-size:42px 42px;background-color:#081522;border:1px solid #183552}
.zone{position:absolute;border:1px dashed rgba(85,168,255,.55);background:rgba(85,168,255,.055);font-size:11px;color:#6fb8ff;padding:8px}.z1{left:3%;top:4%;width:45%;height:43%}.z2{right:3%;top:4%;width:45%;height:43%}.z3{left:3%;bottom:4%;width:45%;height:43%}.z4{right:3%;bottom:4%;width:45%;height:43%}
.robot{position:absolute;transform:translate(-50%,-50%);transition:left .7s linear,top .7s linear;z-index:3}.robot .icon{width:34px;height:34px;border:2px solid var(--ok);border-radius:50%;background:#0b1f30;display:grid;place-items:center;box-shadow:0 0 16px rgba(83,209,139,.35);font-size:16px}.robot.offline .icon{border-color:var(--bad);box-shadow:0 0 16px rgba(255,107,107,.35)}.robot.rtb .icon{border-color:var(--warn)}.robot label{position:absolute;white-space:nowrap;left:42px;top:2px;font-size:11px;background:rgba(5,14,24,.85);padding:4px 6px;border-radius:5px;color:#dcecff}
.target{position:absolute;transform:translate(-50%,-50%);z-index:2}.target .ring{width:42px;height:42px;border:2px solid var(--bad);border-radius:50%;animation:pulse 1.4s infinite}.target:before,.target:after{content:"";position:absolute;background:var(--bad);left:50%;top:50%;transform:translate(-50%,-50%)}.target:before{width:22px;height:2px}.target:after{height:22px;width:2px}@keyframes pulse{50%{box-shadow:0 0 0 12px rgba(255,107,107,0)}}
.right{display:grid;gap:16px;align-content:start}.summary{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:12px}.metric{background:#0a1929;border:1px solid #1b3855;border-radius:10px;padding:11px}.metric .k{font-size:10px;color:var(--muted);letter-spacing:.12em}.metric .v{font-size:15px;font-weight:700;margin-top:6px;word-break:break-word}
.cards{padding:10px;display:grid;gap:8px}.card{border:1px solid #1d3b58;background:#0a1929;border-radius:10px;padding:10px}.card-top{display:flex;justify-content:space-between;align-items:center}.name{font-weight:700}.state{font-size:10px;padding:4px 7px;border-radius:20px;background:rgba(83,209,139,.15);color:var(--ok)}.state.offline{background:rgba(255,107,107,.15);color:var(--bad)}.state.rtb{background:rgba(255,200,87,.15);color:var(--warn)}.small{font-size:11px;color:var(--muted);margin-top:5px}.bar{height:6px;background:#162b40;border-radius:6px;margin-top:8px;overflow:hidden}.fill{height:100%;background:linear-gradient(90deg,var(--accent),var(--ok));border-radius:6px}
.bids{padding:10px;display:grid;gap:8px}.bid{border:1px solid #1d3b58;background:#0a1929;border-radius:10px;padding:10px}.bid.win{border-color:var(--ok);box-shadow:0 0 12px rgba(83,209,139,.14)}.bid-head{display:flex;justify-content:space-between;font-size:12px;font-weight:700}.bid-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:5px;margin-top:8px}.bid-cell{font-size:10px;color:var(--muted)}.bid-cell b{display:block;color:#fff;font-size:11px;margin-top:2px}.events{padding:10px;max-height:210px;overflow:auto}.event{font-size:11px;color:#b8cbe0;padding:8px;border-bottom:1px solid #172e46}.event b{color:#fff}.empty{color:var(--muted);font-size:12px;padding:10px}.footer{padding:0 18px 16px;color:var(--muted);font-size:10px}
@media(max-width:900px){main{grid-template-columns:1fr}.map{height:470px}}
</style>
</head>
<body>
<header><div class="brand"><div class="logo">ES</div><div><h1>EAGLE SWARM · DIGITAL TWIN</h1><div class="sub">ROS 2 operational picture · civilian sensing prototype</div></div></div><div class="live"><span class="dot"></span><span id="status">LIVE DDS FEED</span></div></header>
<main>
<section class="panel"><h2>MISSION AREA / COVERAGE PARTITION</h2><div class="map-wrap"><div class="map" id="map"><div class="zone z1">SECTOR A · SCOUT</div><div class="zone z2">SECTOR B · WORKER</div><div class="zone z3">SECTOR C · RELAY</div><div class="zone z4">SECTOR D · RESERVE</div><div id="robots"></div><div id="target"></div></div></div><div class="footer">Coordinates are normalized to the simulated mission area. Heartbeat age controls online/offline rendering.</div></section>
<div class="right">
<section class="panel"><h2>MISSION SUMMARY</h2><div class="summary"><div class="metric"><div class="k">ELECTED LEADER</div><div class="v" id="leader">—</div></div><div class="metric"><div class="k">ACTIVE TARGET</div><div class="v" id="targetText">—</div></div><div class="metric"><div class="k">TASK AWARD</div><div class="v" id="award">—</div></div><div class="metric"><div class="k">LATEST FAULT</div><div class="v" id="fault">—</div></div></div></section>
<section class="panel"><h2>FLEET HEALTH</h2><div class="cards" id="cards"></div></section>
<section class="panel"><h2>CONTRACT NET BIDS</h2><div class="bids" id="bids"></div></section>
<section class="panel"><h2>EVENT / RECOVERY LOG</h2><div class="events" id="events"></div></section>
</div>
</main>
<script>
const clamp=(v,a,b)=>Math.min(b,Math.max(a,v));
function pos(x,y){ return {left:(clamp((x+12)/24,0.04,.96)*100)+'%', top:((1-clamp((y+12)/24,.04,.96))*100)+'%'} }
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function tick(){try{const r=await fetch('/api/state',{cache:'no-store'});const d=await r.json();document.getElementById('status').textContent='LIVE DDS FEED · '+new Date().toLocaleTimeString();document.getElementById('leader').textContent=d.leader.text;document.getElementById('targetText').textContent=d.target.text;document.getElementById('award').textContent=d.award.text;document.getElementById('fault').textContent=d.fault.text;
let rm='',cards='';for(const bot of d.robots){const p=pos(bot.x,bot.y);const cls=bot.online?(bot.state==='RTB'?'rtb':''):'offline';const glyph=bot.role==='ground_relay'?'▣':'✈';rm+=`<div class="robot ${cls}" style="left:${p.left};top:${p.top}"><div class="icon">${glyph}</div><label>${esc(bot.id)} · ${esc(bot.state)}</label></div>`;cards+=`<div class="card"><div class="card-top"><div class="name">${esc(bot.id)}</div><div class="state ${cls}">${esc(bot.online?bot.state:'OFFLINE')}</div></div><div class="small">${esc(bot.role)} · link ${(bot.link*100).toFixed(0)}% · age ${bot.age.toFixed(1)} s · (${bot.x.toFixed(1)}, ${bot.y.toFixed(1)})</div><div class="bar"><div class="fill" style="width:${clamp(bot.battery,0,100)}%"></div></div><div class="small">Battery ${bot.battery.toFixed(1)}%</div></div>`}document.getElementById('robots').innerHTML=rm;document.getElementById('cards').innerHTML=cards||'<div class="empty">Waiting for heartbeats…</div>';
if(d.target.visible){const p=pos(d.target.x,d.target.y);document.getElementById('target').innerHTML=`<div class="target" style="left:${p.left};top:${p.top}"><div class="ring"></div></div>`}else document.getElementById('target').innerHTML='';
document.getElementById('bids').innerHTML=d.bids.length?d.bids.map(b=>`<div class="bid ${b.winner?'win':''}"><div class="bid-head"><span>${esc(b.id)}</span><span>${b.winner?'WINNER · ':''}${b.total.toFixed(2)}</span></div><div class="bid-grid"><div class="bid-cell">Distance<b>${b.distance.toFixed(2)}</b></div><div class="bid-cell">Battery<b>${b.battery.toFixed(2)}</b></div><div class="bid-cell">Role<b>${b.role.toFixed(2)}</b></div><div class="bid-cell">Link<b>${b.link.toFixed(2)}</b></div><div class="bid-cell">ETA<b>${b.eta.toFixed(2)}s</b></div></div></div>`).join(''):'<div class="empty">Waiting for target bids…</div>';
document.getElementById('events').innerHTML=d.events.length?d.events.map(e=>`<div class="event"><b>${esc(e.kind)}</b> · ${esc(e.text)}<br><span>${esc(e.time)}</span></div>`).join(''):'<div class="empty">No events yet.</div>';
}catch(e){document.getElementById('status').textContent='DASHBOARD DISCONNECTED'} }
setInterval(tick,1000);tick();
</script>
</body></html>'''


class DigitalTwin(Node):
    def __init__(self, host: str = '127.0.0.1', port: int = 8080) -> None:
        super().__init__('digital_twin')
        self.host = host
        self.port = port
        self.lock = threading.RLock()
        self.robots: Dict[str, Dict[str, Any]] = {}
        self.leader = {'text': '—'}
        self.target = {'text': '—', 'visible': False, 'x': 0.0, 'y': 0.0}
        self.award = {'text': '—'}
        self.latest_target_id = ''
        self.winner_id = ''
        self.bids: Dict[str, Dict[str, Any]] = {}
        self.fault = {'text': '—'}
        self.events = deque(maxlen=40)

        self.create_subscription(Heartbeat, '/swarm/heartbeat', self.on_heartbeat, 50)
        self.create_subscription(Bid, '/swarm/bids', self.on_bid, 50)
        self.create_subscription(LeaderState, '/swarm/leader', self.on_leader, retained_qos())
        self.create_subscription(TargetBeacon, '/swarm/target_beacon', self.on_target, retained_qos())
        self.create_subscription(TaskAward, '/swarm/task_award', self.on_award, retained_qos())
        self.create_subscription(FaultEvent, '/swarm/faults', self.on_fault, 20)
        self.create_subscription(SafetyEvent, '/swarm/safety_events', self.on_safety, 20)

        node = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path == '/' or self.path.startswith('/index'):
                    self._send(200, 'text/html; charset=utf-8', HTML.encode('utf-8'))
                elif self.path.startswith('/api/state'):
                    payload = json.dumps(node.snapshot()).encode('utf-8')
                    self._send(200, 'application/json', payload)
                else:
                    self._send(404, 'text/plain', b'Not found')

            def _send(self, status: int, content_type: str, payload: bytes) -> None:
                self.send_response(status)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(payload)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, _format: str, *_args: Any) -> None:
                return

        self.server = ThreadingHTTPServer((host, port), Handler)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.get_logger().info(f'Digital Twin ready at http://{host}:{port}')

    def add_event(self, kind: str, text: str) -> None:
        with self.lock:
            self.events.appendleft({
                'kind': kind,
                'text': text,
                'time': time.strftime('%H:%M:%S'),
            })

    def on_heartbeat(self, msg: Heartbeat) -> None:
        with self.lock:
            self.robots[msg.robot_id] = {
                'id': msg.robot_id,
                'role': msg.role,
                'state': msg.state,
                'battery': float(msg.battery),
                'link': float(msg.link_quality),
                'x': float(msg.pose.position.x),
                'y': float(msg.pose.position.y),
                'gps_ok': bool(msg.gps_ok),
                'received': time.monotonic(),
            }


    def on_bid(self, msg: Bid) -> None:
        with self.lock:
            self.bids[msg.bidder_id] = {
                'id': msg.bidder_id,
                'target_id': msg.target_id,
                'distance': float(msg.distance_cost),
                'battery': float(msg.battery_penalty),
                'role': float(msg.role_penalty),
                'link': float(msg.link_penalty),
                'total': float(msg.total_cost),
                'eta': float(msg.eta),
            }
        self.add_event(
            'BID',
            f'{msg.bidder_id} total={msg.total_cost:.2f} '
            f'(d={msg.distance_cost:.2f}, batt={msg.battery_penalty:.2f}, '
            f'role={msg.role_penalty:.2f}, link={msg.link_penalty:.2f})',
        )

    def on_leader(self, msg: LeaderState) -> None:
        text = f'{msg.leader_id or "none"} · epoch {msg.election_epoch}'
        with self.lock:
            changed = self.leader.get('text') != text
            self.leader = {'text': text}
        if changed:
            self.add_event('LEADER', f'{text} · {msg.reason}')

    def on_target(self, msg: TargetBeacon) -> None:
        text = f'{msg.target_id} · confidence {msg.confidence:.2f}'
        with self.lock:
            changed = self.target.get('text') != text
            self.latest_target_id = msg.target_id
            self.winner_id = ''
            self.bids.clear()
            self.target = {
                'text': text,
                'visible': True,
                'x': float(msg.position.x),
                'y': float(msg.position.y),
            }
        if changed:
            self.add_event('TARGET', f'{text} · {msg.confirmation_source}')

    def on_award(self, msg: TaskAward) -> None:
        text = f'{msg.target_id} → {msg.winner_id} · cost {msg.winning_cost:.2f}'
        with self.lock:
            changed = self.award.get('text') != text
            self.winner_id = msg.winner_id
            self.award = {'text': text}
        if changed:
            self.add_event('TASK AWARD', text)

    def on_fault(self, msg: FaultEvent) -> None:
        text = f'{msg.fault_type} @ {msg.robot_id} · {msg.action}'
        with self.lock:
            self.fault = {'text': text}
        suffix = f' · recovery {msg.recovery_time:.2f}s' if msg.recovery_time > 0.0 else ''
        self.add_event('FAULT', text + suffix)

    def on_safety(self, msg: SafetyEvent) -> None:
        text = f'{msg.event_type}: {msg.robot_a}/{msg.robot_b} · {msg.separation:.2f}m · {msg.action}'
        self.add_event('SAFETY', text)

    def snapshot(self) -> Dict[str, Any]:
        now = time.monotonic()
        with self.lock:
            robots = []
            for robot in self.robots.values():
                copy = dict(robot)
                copy['age'] = now - copy.pop('received')
                copy['online'] = copy['age'] < 3.2
                robots.append(copy)
            robots.sort(key=lambda item: item['id'])
            bids = []
            for bid in self.bids.values():
                copy = dict(bid)
                copy['winner'] = copy['id'] == self.winner_id
                bids.append(copy)
            bids.sort(key=lambda item: (item['total'], item['id']))
            return {
                'leader': dict(self.leader),
                'target': dict(self.target),
                'award': dict(self.award),
                'fault': dict(self.fault),
                'robots': robots,
                'bids': bids,
                'events': list(self.events),
            }

    def destroy_node(self) -> bool:
        self.server.shutdown()
        self.server.server_close()
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = DigitalTwin()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
