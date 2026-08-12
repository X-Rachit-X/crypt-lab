from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import asyncio
import json, tempfile
import psutil
import logging
import random
import subprocess
import os
from typing import Dict, List, Optional
import threading
import time
from google import genai
from fastapi.responses import HTMLResponse, JSONResponse
import subprocess, json
from collections import deque
from config import settings

# ── IDS imports ───────────────────────────────────────────────────
from ids import _recent_log_lines
from ids import capture as ids_capture
from ids import log_capture as ids_log_capture
from ids.aggregator import FlowAggregator
from ids import engine as ids_engine
from ids import llm as ids_llm
from ids import geo as ids_geo
from ids import alerts as ids_alerts
from ids import db as ids_db
from ids import notify as ids_notify
from simulator.templates import SCENARIOS as SIM_SCENARIOS
from simulator.simulator import run_scenario as sim_run_scenario

# ── vm_config graceful import (may not exist after cleanup) ──────
try:
    from vm_config import VMConfig, HostConfig, save_encrypted_config, load_decrypted_config, validate_host_config, test_ssh_connection, ConfigError
except ImportError:
    # Provide stubs so existing code doesn't crash
    class HostConfig:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)
    class VMConfig:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)
    class ConfigError(Exception):
        pass
    def save_encrypted_config(cfg): pass
    def load_decrypted_config(mask_passwords=False): return None
    def validate_host_config(h):
        if not getattr(h, 'host', '') or not getattr(h, 'username', ''):
            raise ConfigError("host and username are required")
    def test_ssh_connection(h): return {"ok": False, "error": "vm_config module not available"}

import pty
import fcntl
import errno

app = FastAPI()

# ── IDS global state ──────────────────────────────────────────────
# Shared detection queue (flows + log events feed into this)
detection_queue: asyncio.Queue = asyncio.Queue()
# Aggregator (initialized after event loop is available)
aggregator: Optional[FlowAggregator] = None
# WebSocket clients for IDS feed and log feed
ids_feed_clients: List[WebSocket] = []
log_feed_clients: List[WebSocket] = []
# Track active simulation
active_simulation: Optional[str] = None

# Runtime overrides for VM credentials (not persisted)
RUNTIME_VM_OVERRIDES: Dict[str, Dict[str, any]] = {}

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Test mode - set to True to simulate VMs locally
TEST_MODE = True

# Configuration - Update these with your VM details when TEST_MODE = False
VM_CONFIG = {
    "vm1": {
        "host": "172.18.36.132",  # Replace with VM1 IP
        "port": 22,
        "username": "server",  # Replace with your username
        "password": "abcd",  # Replace with your password or use key
        "name": "VM1"
    },
    "vm2": {
       "host": "10.174.168.59",  # Replace with VM1 IP
        "port": 22,
        "username": "aka",  # Replace with your username
        "password": "rwinrur",  # Replace with your password or use key
        "name": "VM2"
    }
}

# Store active connections
active_connections: Dict[str, List[WebSocket]] = {"vm1": [], "vm2": []}
# Track last connection error for better UX
last_connection_error: Dict[str, str] = {"vm1": "", "vm2": ""}

# Aggregated terminal buffers per VM (captures both commands and outputs)
terminal_buffers: Dict[str, deque] = {"vm1": deque(maxlen=2000), "vm2": deque(maxlen=2000)}
# Per-VM input accumulator to detect command submit on newline
input_accumulator: Dict[str, str] = {"vm1": "", "vm2": ""}
# Debug event stream
debug_events: deque = deque(maxlen=500)

# For test mode
local_shells: Dict[str, Dict[str, any]] = {}

# For real SSH mode
try:
    import paramiko
    ssh_clients: Dict[str, paramiko.SSHClient] = {}
    ssh_channels: Dict[str, paramiko.Channel] = {}
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False
    ssh_clients = {}
    ssh_channels = {}

def get_vm_credentials(vm_id: str) -> Dict[str, str]:
    """Resolve VM credentials for vm1/vm2 from, in order:
    - runtime overrides (ephemeral quick-connect)
    - encrypted config file
    - static VM_CONFIG fallback
    Mapping: vm1 -> attacker, vm2 -> target
    """
    creds = {"host": "", "port": 22, "username": "", "password": "", "name": vm_id.upper()}
    # 0) Runtime override
    try:
        override = RUNTIME_VM_OVERRIDES.get(vm_id)
        if override:
            creds.update({
                "host": override.get("host", ""),
                "port": int(override.get("port", 22) or 22),
                "username": override.get("username", ""),
                "password": override.get("password", ""),
                "name": override.get("hostname") or override.get("name") or vm_id.upper(),
            })
            return creds
    except Exception:
        pass
    # 1) Encrypted config
    try:
        cfg = load_decrypted_config(mask_passwords=False)
        if cfg:
            if vm_id == "vm1" and cfg.attacker:
                creds.update({
                    "host": cfg.attacker.host,
                    "port": cfg.attacker.port,
                    "username": cfg.attacker.username,
                    "password": cfg.attacker.password,
                    "name": cfg.attacker.hostname or "Attacker"
                })
            elif vm_id == "vm2" and cfg.target:
                creds.update({
                    "host": cfg.target.host,
                    "port": cfg.target.port,
                    "username": cfg.target.username,
                    "password": cfg.target.password,
                    "name": cfg.target.hostname or "Target"
                })
    except Exception as e:
        logging.warning(f"Failed to load encrypted VM config: {e}")
    # Fallback to static config if still empty
    try:
        static = VM_CONFIG.get(vm_id, {})
        if static and not creds["host"]:
            creds.update({
                "host": static.get("host", ""),
                "port": static.get("port", 22),
                "username": static.get("username", ""),
                "password": static.get("password", ""),
                "name": static.get("name", vm_id.upper())
            })
    except Exception:
        pass
    return creds


def create_ssh_connection(vm_id: str):
    """Create SSH connection to VM using saved credentials."""
    try:
        cfg = get_vm_credentials(vm_id)
        if not cfg.get("host") or not cfg.get("username"):
            raise RuntimeError("Missing host/username in VM configuration. Set credentials at /config.")
        last_connection_error[vm_id] = ""

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=cfg["host"],
            port=int(cfg.get("port", 22)),
            username=cfg["username"],
            password=(cfg.get("password") or None),
            timeout=8,
            banner_timeout=8,
            auth_timeout=8,
            look_for_keys=False,
            allow_agent=False,
        )
        # Create interactive shell
        channel = client.invoke_shell(term='xterm', width=80, height=24)

        ssh_clients[vm_id] = client
        ssh_channels[vm_id] = channel

        # Initialize buffers for this VM if missing
        terminal_buffers.setdefault(vm_id, deque(maxlen=2000))
        input_accumulator.setdefault(vm_id, "")

        return True
    except Exception as e:
        msg = str(e)
        last_connection_error[vm_id] = msg
        logging.error(f"Failed to connect to {vm_id}: {msg}")
        return False

def get_system_stats(vm_id: str):
    """Get system statistics from VM or local host in TEST_MODE."""
    try:
        client = ssh_clients.get(vm_id)
        if not client:
            if TEST_MODE:
                # Local stats fallback
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory().percent
                disk = psutil.disk_usage('/').percent
                try:
                    load = os.getloadavg()[0]
                except Exception:
                    load = 0.0
                return {"cpu": cpu, "memory": mem, "disk": disk, "load": load}
            return None
            
        # Get CPU usage
        stdin, stdout, stderr = client.exec_command("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1")
        cpu_usage = stdout.read().decode().strip()
        
        # Get memory usage
        stdin, stdout, stderr = client.exec_command("free | grep Mem | awk '{print ($3/$2) * 100.0}'")
        memory_usage = stdout.read().decode().strip()
        
        # Get disk usage
        stdin, stdout, stderr = client.exec_command("df -h / | awk 'NR==2{print $5}' | cut -d'%' -f1")
        disk_usage = stdout.read().decode().strip()
        
        # Get load average
        stdin, stdout, stderr = client.exec_command("uptime | awk -F'load average:' '{print $2}' | cut -d',' -f1")
        load_avg = stdout.read().decode().strip()
        
        return {
            "cpu": float(cpu_usage) if cpu_usage.replace('.', '').isdigit() else 0,
            "memory": float(memory_usage) if memory_usage.replace('.', '').isdigit() else 0,
            "disk": float(disk_usage) if disk_usage.isdigit() else 0,
            "load": float(load_avg) if load_avg.replace('.', '').isdigit() else 0
        }
    except Exception as e:
        logging.error(f"Error getting stats for {vm_id}: {e}")
        return None

async def read_from_ssh(vm_id: str):
    """Read output from SSH channel and send to WebSocket clients and analysis pipeline"""
    channel = ssh_channels.get(vm_id)
    if not channel:
        return
        
    while True:
        try:
            if channel.recv_ready():
                data = channel.recv(4096).decode('utf-8', errors='ignore')
                if data:
                    # Append to analysis buffer
                    terminal_buffers[vm_id].append(f"OUT: {data}")
                    # Send to all connected clients for this VM
                    for websocket in active_connections[vm_id][:]:
                        try:
                            await websocket.send_text(json.dumps({
                                "type": "terminal_output",
                                "data": data
                            }))
                        except:
                            if websocket in active_connections[vm_id]:
                                active_connections[vm_id].remove(websocket)
            await asyncio.sleep(0.02)
        except Exception as e:
            logging.error(f"Error reading from SSH {vm_id}: {e}")
            break

def start_local_shell(vm_id: str) -> bool:
    try:
        master_fd, slave_fd = pty.openpty()
        proc = subprocess.Popen(['/bin/bash','-l'], stdin=slave_fd, stdout=slave_fd, stderr=slave_fd, close_fds=True)
        os.close(slave_fd)
        # set non-blocking
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        local_shells[vm_id] = {"proc": proc, "fd": master_fd}
        return True
    except Exception as e:
        logging.error(f"Failed to start local shell for {vm_id}: {e}")
        return False

async def read_from_local(vm_id: str):
    shell = local_shells.get(vm_id)
    if not shell:
        return
    fd = shell["fd"]
    while True:
        try:
            try:
                data = os.read(fd, 4096)
            except BlockingIOError:
                data = b""
            except OSError as oe:
                if oe.errno in (errno.EIO, errno.EBADF):
                    break
                data = b""
            if data:
                text = data.decode('utf-8', errors='ignore')
                # broadcast
                for websocket in active_connections.get(vm_id, [])[:]:
                    try:
                        await websocket.send_text(json.dumps({"type": "terminal_output", "data": text}))
                    except Exception:
                        if websocket in active_connections.get(vm_id, []):
                            active_connections[vm_id].remove(websocket)
                # analysis buffer
                terminal_buffers[vm_id].append(f"OUT: {text}")
            await asyncio.sleep(0.01)
        except Exception as e:
            logging.error(f"Local shell read error {vm_id}: {e}")
            break

@app.websocket("/ws/terminal/{vm_id}")
async def terminal_websocket(websocket: WebSocket, vm_id: str):
    await websocket.accept()
    
    if vm_id not in VM_CONFIG:
        await websocket.close(code=1000)
        return
    
    # Add to active connections
    active_connections[vm_id].append(websocket)
    
    # Create SSH connection if not exists or channel closed
    if vm_id not in ssh_clients or vm_id not in ssh_channels or not ssh_channels.get(vm_id) or ssh_channels.get(vm_id).closed:
        if not PARAMIKO_AVAILABLE and not TEST_MODE:
            await websocket.send_text(json.dumps({"type": "error", "message": "SSH client not available (paramiko not installed)."}))
            await websocket.close()
            return
        if not create_ssh_connection(vm_id):
            if TEST_MODE:
                # fallback to local shell
                if start_local_shell(vm_id):
                    asyncio.create_task(read_from_local(vm_id))
                    await websocket.send_text(json.dumps({
                        "type": "terminal_output",
                        "data": "\r\n[INFO] Using local shell fallback for testing (vm not connected).\r\n"
                    }))
                else:
                    await websocket.send_text(json.dumps({"type": "error", "message": f"Failed to connect to {vm_id}: {last_connection_error.get(vm_id) or 'unknown error'}"}))
                    await websocket.close()
                    return
            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Failed to connect to {vm_id}: {last_connection_error.get(vm_id) or 'unknown error'}"
                }))
                await websocket.close()
                return
        else:
            # Start reading from SSH in background
            asyncio.create_task(read_from_ssh(vm_id))
    
    try:
        while True:
            # Receive input from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "terminal_input":
                payload = message.get("data", "")
                ch = ssh_channels.get(vm_id)
                if ch:
                    ch.send(payload)
                elif vm_id in local_shells:
                    try:
                        os.write(local_shells[vm_id]["fd"], payload.encode())
                    except Exception:
                        pass
                # Accumulate command input and push event on newline
                try:
                    acc = input_accumulator.get(vm_id, "") + payload
                    if "\r" in payload or "\n" in payload:
                        cmd = acc.replace("\r", "\n").split("\n")[-2] if "\n" in acc else acc.strip()
                        if cmd:
                            terminal_buffers[vm_id].append(f"CMD: {cmd}\n")
                        input_accumulator[vm_id] = ""
                    else:
                        input_accumulator[vm_id] = acc
                except Exception:
                    input_accumulator[vm_id] = ""
                    
    except WebSocketDisconnect:
        if websocket in active_connections[vm_id]:
            active_connections[vm_id].remove(websocket)

@app.websocket("/ws/stats/{vm_id}")
async def stats_websocket(websocket: WebSocket, vm_id: str):
    await websocket.accept()
    
    if vm_id not in VM_CONFIG:
        await websocket.close(code=1000)
        return
    
    try:
        while True:
            stats = get_system_stats(vm_id)
            if stats:
                await websocket.send_text(json.dumps({
                    "type": "stats",
                    "data": stats
                }))
            await asyncio.sleep(2)  # Update every 2 seconds
            
    except WebSocketDisconnect:
        pass

# Serve the main HTML file
@app.get("/")
async def get_index():
    return FileResponse('static/index.html')

@app.get("/config")
async def get_config_page():
    return FileResponse('static/vm_config.html')

@app.get("/debug")
async def get_debug_page():
    return FileResponse('static/debug.html')

# Default model name (new SDK reads API key from env automatically)
default_model_name = settings.GEMINI_MODEL or "gemini-2.0-flash"

@app.get("/api/health")
async def api_health():
    import socket
    # Resolve the machine's primary outbound IP (the one used for real traffic)
    try:
        _s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _s.connect(("8.8.8.8", 80))
        sensor_ip = _s.getsockname()[0]
        _s.close()
    except Exception:
        sensor_ip = "unknown"
    return {
        "status": "ok",
        "sensor_ip": sensor_ip,
        "gemini": {
            "enabled": bool(settings.GEMINI_API_KEY),
            "model": settings.GEMINI_MODEL or default_model_name,
        },
        "connections": {k: len(v) for k, v in active_connections.items()},
    }

@app.post("/api/analyze")
async def manual_analyze(payload: dict):
    """Manually trigger analysis.
    Accepts either raw logs (payload.logs) or vm_id to use current terminal buffer.
    """
    if not settings.GEMINI_API_KEY:
        return JSONResponse({"ok": False, "error": "gemini_api_key_missing"}, status_code=400)
    logs = payload.get("logs")
    vm_id = payload.get("vm_id")
    if not logs and vm_id:
        if vm_id not in terminal_buffers:
            return JSONResponse({"ok": False, "error": "unknown_vm_id"}, status_code=400)
        sample_text = "".join(list(terminal_buffers[vm_id]))
        if settings.ANALYSIS_SAMPLE_SIZE and len(sample_text) > settings.ANALYSIS_SAMPLE_SIZE:
            sample_text = sample_text[-settings.ANALYSIS_SAMPLE_SIZE:]
        logs = sample_text
    if not logs:
        return JSONResponse({"ok": False, "error": "no_logs"}, status_code=400)
    try:
        result = await send_logs_to_gemini(logs)
        debug_events.append({"ts": time.time(), "event": "manual_analyze", "vm_id": vm_id, "chars": len(logs)})
        return {"ok": True, "analysis": result}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.get("/api/models")
async def list_models():
    if not settings.GEMINI_API_KEY:
        return JSONResponse({"ok": False, "error": "gemini_api_key_missing"}, status_code=400)
    try:
        models = genai.Client().models.list()
        out = []
        for m in models:
            try:
                out.append({
                    "name": getattr(m, "name", ""),
                    "supported_generation_methods": getattr(m, "supported_generation_methods", []),
                })
            except Exception:
                pass
        return {"ok": True, "models": out}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.get("/api/vm-config")
async def read_vm_config():
    cfg = load_decrypted_config(mask_passwords=True)
    if not cfg:
        return JSONResponse({"exists": False})
    return {
        "exists": True,
        "attacker": cfg.attacker.__dict__,
        "target": cfg.target.__dict__,
    }

@app.post("/api/vm-config")
async def write_vm_config(payload: dict):
    try:
        attacker = payload.get("attacker", {})
        target = payload.get("target", {})
        a = HostConfig(**attacker)
        t = HostConfig(**target)
        validate_host_config(a)
        validate_host_config(t)
        # Do not mask passwords when saving
        cfg = VMConfig(attacker=a, target=t)
        save_encrypted_config(cfg)
        # Proactively reset existing SSH sessions so terminals reconnect with new creds
        for vm_id in ("vm1", "vm2"):
            ch = ssh_channels.get(vm_id)
            if ch:
                try:
                    ch.close()
                except Exception:
                    pass
                ssh_channels.pop(vm_id, None)
            cli = ssh_clients.get(vm_id)
            if cli:
                try:
                    cli.close()
                except Exception:
                    pass
                ssh_clients.pop(vm_id, None)
            # Close websockets to trigger client-side reconnect
            for ws in active_connections.get(vm_id, [])[:]:
                try:
                    await ws.close(code=1012)
                except Exception:
                    pass
            active_connections[vm_id] = []
        return {"ok": True}
    except ConfigError as ce:
        return JSONResponse({"ok": False, "error": str(ce)}, status_code=400)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.post("/api/vm-config/test")
async def test_vm_connections(payload: dict):
    results = {}
    try:
        if "attacker" in payload:
            a = HostConfig(**payload["attacker"])
            validate_host_config(a)
            results["attacker"] = test_ssh_connection(a)
        if "target" in payload:
            t = HostConfig(**payload["target"])
            validate_host_config(t)
            results["target"] = test_ssh_connection(t)
        return {"ok": True, "results": results}
    except ConfigError as ce:
        return JSONResponse({"ok": False, "error": str(ce)}, status_code=400)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# analysis_worker removed — Gemini is now only called on-demand via POST /api/analyze
# (auto-debounce was consuming free-tier quota on every terminal keystroke)

async def send_logs_to_gemini(logs: str) -> Dict:
    """Send terminal commands and output logs to Gemini for security analysis.
    All Gemini SDK calls are offloaded to a thread to avoid blocking the asyncio event loop.
    Robust fallback behavior:
    - Normalize configured model names (with and without "models/" prefix)
    - On 404/unsupported errors, query list_models() and pick a supported model
      favoring fast/compatible models available to this key
    """
    if not settings.GEMINI_API_KEY:
        return {"status": "disabled", "reason": "gemini_api_key_missing"}

    def normalize_variants(name: str) -> List[str]:
        if not name:
            return []
        out = []
        if name.startswith("models/"):
            out.append(name)
            out.append(name.split("/", 1)[1])
        else:
            out.append(name)
            out.append(f"models/{name}")
        # Deduplicate while preserving order
        seen = set()
        res = []
        for n in out:
            if n and n not in seen:
                seen.add(n)
                res.append(n)
        return res

    system_prompt = (
        "You are a cybersecurity analyst monitoring a live attack simulation lab. "
        "Given terminal commands and output logs, identify potential attacks, provide a concise security analysis, "
        "and give actionable recommendations. Respond in compact JSON with keys: security_analysis, attack_detection[], recommendations[]."
    )
    user_payload = {"input": "Terminal commands and output logs", "logs": logs}

    # Helper: blocking generate in a worker thread
    async def generate_with_model(name: str) -> Dict:
        def _call():
            started = time.time()
            client = genai.Client()
            resp = client.models.generate_content(
                model=name,
                contents=[system_prompt, json.dumps(user_payload)],
            )
            elapsed = time.time() - started
            return resp, int(elapsed * 1000)
        resp, dur_ms = await asyncio.to_thread(_call)
        debug_events.append({
            "ts": time.time(),
            "event": "gemini_call",
            "duration_ms": dur_ms,
            "chars": len(logs),
            "model": name,
        })
        return parse_and_format_response(getattr(resp, "text", ""))

    # Helper: blocking list_models in a worker thread
    async def list_supported_models() -> List[str]:
        def _list():
            try:
                return list(genai.Client().models.list())
            except Exception:
                return []
        models = await asyncio.to_thread(_list)
        supported = []
        for m in models:
            try:
                name = getattr(m, "name", "")
                methods = set(getattr(m, "supported_generation_methods", []) or [])
                if "generateContent" in methods and name:
                    supported.append(name)
            except Exception:
                continue
        return supported

    # First, try the configured/default model and its normalized variants
    base_first = settings.GEMINI_MODEL or default_model_name
    tried: List[str] = []
    last_err = None

    async def try_models(model_names: List[str]) -> Optional[Dict]:
        nonlocal last_err
        for name in model_names:
            if name in tried:
                continue
            tried.append(name)
            try:
                return await generate_with_model(name)
            except Exception as e:
                msg = str(e)
                last_err = msg
                debug_events.append({"ts": time.time(), "event": "gemini_error", "error": msg, "model": name})
                # For 404/unsupported we will try fallbacks; otherwise bail
                if not ("404" in msg or "not found" in msg.lower() or "not supported" in msg.lower()):
                    break
        return None

    # 1) Configured model + normalized variants
    out = await try_models(normalize_variants(base_first))
    if out is not None:
        return out

    # 2) Static common fallbacks (both variants)
    static_pref = [
        "gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash",
        "gemini-2.5-pro", "gemini-pro-latest",
    ]
    fallbacks = []
    for n in static_pref:
        fallbacks.extend(normalize_variants(n))
    out = await try_models(fallbacks)
    if out is not None:
        return out

    # 3) Dynamic: query available models and choose a supported one
    try:
        supported = await list_supported_models()
        # Rank by preference substrings
        prefs = [
            "2.5-flash", "gemini-flash-latest", "2.0-flash", "2.5-pro", "pro-latest", "pro",
        ]
        def score(n: str) -> int:
            s = 0
            for i, sub in enumerate(reversed(prefs)):
                if sub in n:
                    s += (i + 1)
            return s
        supported_sorted = sorted(supported, key=score, reverse=True)
        dyn_candidates = []
        for n in supported_sorted:
            dyn_candidates.append(n)
            if n.startswith("models/"):
                dyn_candidates.append(n.split("/", 1)[1])
        out = await try_models(dyn_candidates)
        if out is not None:
            return out
    except Exception as e:
        debug_events.append({"ts": time.time(), "event": "gemini_error", "error": f"list_models_failed: {e}"})

    return {"status": "error", "error": "model_unavailable", "message": last_err or "Model not available"}

def parse_and_format_response(text: str) -> Dict:
    """Parse Gemini output into a stable JSON structure with defaults."""
    if not text:
        return {
            "status": "ok",
            "security_analysis": "No content returned.",
            "attack_detection": [],
            "recommendations": []
        }
    # Try direct JSON parse first
    try:
        data = json.loads(text)
        # Normalize keys
        return {
            "status": "ok",
            "security_analysis": data.get("security_analysis") or data.get("analysis") or data.get("summary") or "",
            "attack_detection": data.get("attack_detection") or data.get("detections") or data.get("alerts") or [],
            "recommendations": data.get("recommendations") or data.get("actions") or []
        }
    except Exception:
        pass
    # Fallback: attempt to extract JSON between braces
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            data = json.loads(text[start:end+1])
            return {
                "status": "ok",
                "security_analysis": data.get("security_analysis") or "",
                "attack_detection": data.get("attack_detection") or [],
                "recommendations": data.get("recommendations") or []
            }
    except Exception:
        pass
    # Last resort: wrap raw text
    return {
        "status": "ok",
        "security_analysis": text.strip(),
        "attack_detection": [],
        "recommendations": []
    }

@app.get("/security-check")
def security_check():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    config = VM_CONFIG["vm1"]  # Change to "vm2" to analyze VM2
    ssh.connect(
        hostname=config["host"],
        port=config["port"],
        username=config["username"],
        password=config["password"]
        )
        

    # Run log collection script on victim
    ssh.exec_command("bash ~/ai/collect_logs_ai.sh")

    # Fetch JSON file back to backend
    sftp = ssh.open_sftp()
    local_tmp = tempfile.NamedTemporaryFile(delete=False)
    sftp.get("/home/server/system_logs/system_logs_ai.json", local_tmp.name)
    sftp.close()
    ssh.close()

    # Load logs
    with open(local_tmp.name) as f:
        logs = json.load(f)

    # Ask Gemini for a structured report
    prompt = (
        "You are a cybersecurity analyst. Analyze the system logs. Respond ONLY in valid JSON with the following structure: "
        "{\n  \"attack_detected\": \"short summary of the attack\",\n  \"evidence\": [\"list of evidence points\"],\n  \"recommendations\": [\"list of security fixes\"]\n}"
    )

    if settings.GEMINI_API_KEY:
        client = genai.Client()
        response = client.models.generate_content(
            model=default_model_name,
            contents=[prompt, json.dumps(logs)],
        )
        # Try to parse as JSON
        try:
            report = json.loads(response.text)
        except Exception:
            report = {"attack_detected": "Parsing error",
                      "evidence": [getattr(response, "text", "")],
                      "recommendations": []}
    else:
        report = {"attack_detected": "Gemini not configured",
                  "evidence": [],
                  "recommendations": []}

    return JSONResponse(report)

# Debug WebSocket for monitoring Gemini calls
debug_ws_clients: List[WebSocket] = []

@app.websocket("/ws/debug")
async def debug_ws(websocket: WebSocket):
    await websocket.accept()
    debug_ws_clients.append(websocket)
    # Send recent events on connect
    try:
        for ev in list(debug_events)[-50:]:
            await websocket.send_text(json.dumps({"type": "event", "data": ev}))
        while True:
            # keep alive; we don't receive anything from client
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        if websocket in debug_ws_clients:
            debug_ws_clients.remove(websocket)

# Quick-connect API: set runtime SSH credentials for vm1/vm2 without persisting
@app.post("/api/vm-connect/{vm_id}")
async def api_vm_connect(vm_id: str, payload: dict):
    if vm_id not in ("vm1", "vm2"):
        return JSONResponse({"ok": False, "error": "invalid_vm_id"}, status_code=400)
    try:
        host_cfg = HostConfig(
            host=payload.get("host", ""),
            hostname=payload.get("hostname"),
            username=payload.get("username", ""),
            password=payload.get("password", ""),
            port=int(payload.get("port", 22) or 22),
        )
        validate_host_config(host_cfg)
        # Set runtime override
        RUNTIME_VM_OVERRIDES[vm_id] = {
            "host": host_cfg.host,
            "hostname": host_cfg.hostname,
            "username": host_cfg.username,
            "password": host_cfg.password,
            "port": host_cfg.port,
        }
        # Tear down existing connection for this vm to force reconnect with new creds
        ch = ssh_channels.get(vm_id)
        if ch:
            try:
                ch.close()
            except Exception:
                pass
            ssh_channels.pop(vm_id, None)
        cli = ssh_clients.get(vm_id)
        if cli:
            try:
                cli.close()
            except Exception:
                pass
            ssh_clients.pop(vm_id, None)
        # Close websockets to trigger client reconnect
        for ws in active_connections.get(vm_id, [])[:]:
            try:
                await ws.close(code=1012)
            except Exception:
                pass
        active_connections[vm_id] = []
        return {"ok": True}
    except ConfigError as ce:
        return JSONResponse({"ok": False, "error": str(ce)}, status_code=400)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# ══════════════════════════════════════════════════════════════════
#  IDS ENDPOINTS
# ══════════════════════════════════════════════════════════════════

@app.get("/api/alerts")
async def api_alerts():
    """Return last 50 alerts, newest first."""
    try:
        alerts = ids_db.fetch_alerts(limit=50)
        return {"ok": True, "alerts": alerts}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/stats")
async def api_stats():
    """Return { attack_type: count } for the doughnut chart."""
    try:
        stats = ids_db.fetch_stats()
        return {"ok": True, "stats": stats}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/stats/extended")
async def api_stats_extended():
    """Return extended statistics: top IPs, hourly activity, severity breakdown."""
    try:
        top_ips     = await asyncio.to_thread(ids_db.fetch_top_ips, 10)
        hourly      = await asyncio.to_thread(ids_db.fetch_hourly_counts, 24)
        severity    = await asyncio.to_thread(ids_db.fetch_severity_counts)
        attack_dist = await asyncio.to_thread(ids_db.fetch_stats)
        return {
            "ok": True,
            "top_ips": top_ips,
            "hourly": hourly,
            "severity": severity,
            "attack_dist": attack_dist,
        }
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/map")
async def api_map():
    """Return map marker data for Leaflet."""
    try:
        data = ids_db.fetch_map_data()
        return {"ok": True, "markers": data}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/logs")
async def api_logs():
    """Return last 100 raw log events for the log viewer."""
    try:
        return {"ok": True, "logs": _recent_log_lines[-100:]}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.delete("/api/alerts/clear")
async def api_alerts_clear():
    """Clear all alerts from the database and broadcast a clear event."""
    try:
        await asyncio.to_thread(ids_db.clear_alerts)
        payload = json.dumps({"type": "clear_alerts"})
        for ws in ids_feed_clients[:]:
            try:
                await ws.send_text(payload)
            except Exception:
                if ws in ids_feed_clients:
                    ids_feed_clients.remove(ws)
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.delete("/api/logs/clear")
async def api_logs_clear():
    """Clear the in-memory log buffer."""
    try:
        _recent_log_lines.clear()
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/simulate")
async def api_simulate(payload: dict):
    """Trigger a simulation scenario."""
    global active_simulation
    scenario_name = payload.get("scenario", "").upper()
    if scenario_name not in SIM_SCENARIOS:
        return JSONResponse(
            {"ok": False, "error": f"Unknown scenario: {scenario_name}"},
            status_code=400,
        )
    if active_simulation:
        return JSONResponse(
            {"ok": False, "error": f"Simulation '{active_simulation}' already running"},
            status_code=409,
        )
    scenario = SIM_SCENARIOS[scenario_name]
    active_simulation = scenario_name
    expected = scenario.get("expected_seconds", 5)

    async def _run():
        global active_simulation
        try:
            await sim_run_scenario(scenario, aggregator, detection_queue)
        except Exception as exc:
            logging.error(f"Simulation error: {exc}")
        finally:
            await asyncio.sleep(expected + 2)
            active_simulation = None

    asyncio.create_task(_run())
    return {
        "ok": True,
        "status": "started",
        "scenario": scenario_name,
        "expected_seconds": expected,
    }


@app.websocket("/ws/ids-feed")
async def ws_ids_feed(websocket: WebSocket):
    """Push full alert JSON to connected dashboard clients."""
    await websocket.accept()
    ids_feed_clients.append(websocket)
    try:
        while True:
            await asyncio.sleep(5)  # keep-alive
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in ids_feed_clients:
            ids_feed_clients.remove(websocket)


@app.websocket("/ws/log-feed")
async def ws_log_feed(websocket: WebSocket):
    """Push each new log event as it is captured."""
    await websocket.accept()
    log_feed_clients.append(websocket)
    last_idx = len(_recent_log_lines)
    try:
        while True:
            await asyncio.sleep(0.5)
            current_len = len(_recent_log_lines)
            if current_len > last_idx:
                new_items = _recent_log_lines[last_idx:current_len]
                for item in new_items:
                    try:
                        await websocket.send_text(json.dumps({"type": "log", "data": item}))
                    except Exception:
                        return
                last_idx = current_len
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in log_feed_clients:
            log_feed_clients.remove(websocket)


# ══════════════════════════════════════════════════════════════════
#  IDS DETECTION LOOP
# ══════════════════════════════════════════════════════════════════

async def detection_loop():
    """
    Main IDS detection loop. Pulls events from the shared queue,
    runs the full pipeline: classify → geo+LLM → alert → encrypt → store → broadcast.
    """
    # Deduplication: track last alert time per src_ip
    _dedup: dict[str, float] = {}
    DEDUP_COOLDOWN = 60.0  # seconds — same IP won't fire more than once per minute

    while True:
        try:
            event = await detection_queue.get()
        except Exception:
            await asyncio.sleep(0.1)
            continue

        try:
            if event.get("source") == "flow":
                # Flow-based detection
                features = event["features"]
                meta = event["meta"]
                result = ids_engine.classify(features)

                if not result["is_attack"]:
                    continue  # Benign — discard

                src_ip = meta.get("src_ip", "0.0.0.0")

                # Deduplication: skip if same src_ip fired within cooldown window
                now_ts = time.time()
                dedup_key = f"{src_ip}:{result['label']}"
                if now_ts - _dedup.get(dedup_key, 0) < DEDUP_COOLDOWN:
                    continue
                _dedup[dedup_key] = now_ts

                # Enrichment: geo + LLM in parallel
                severity = ids_alerts.get_severity(result["label"])

                # Collect recent log lines from same src_ip (max 5)
                related_logs = [
                    lg["raw_line"]
                    for lg in _recent_log_lines[-200:]
                    if lg.get("src_ip") == src_ip
                ][-5:]

                llm_context = {
                    "attack_type": result["label"],
                    "src_ip": src_ip,
                    "dst_ip": meta.get("dst_ip", "0.0.0.0"),
                    "dst_port": meta.get("dst_port", 0),
                    "protocol": meta.get("proto", 0),
                    "confidence": result["confidence"],
                    "severity": severity,
                    "geo_city": "",
                    "geo_country": "",
                    "flow_packets_per_s": float(features[4]) if len(features) > 4 else 0.0,
                    "flow_bytes_per_s": float(features[3]) if len(features) > 3 else 0.0,
                    "syn_flag_count": int(features[8]) if len(features) > 8 else 0,
                    "packet_length_mean": float(features[5]) if len(features) > 5 else 0.0,
                    "log_events": related_logs,
                }

                # Run geo + LLM in parallel
                # Gemini is only called for High severity to preserve daily quota.
                # Medium/Low severity alerts get fast static countermeasures.
                if severity == "High":
                    geo_result, llm_result = await asyncio.gather(
                        asyncio.to_thread(ids_geo.lookup, src_ip, settings.IPINFO_TOKEN),
                        ids_llm.enrich(
                            {**llm_context, "geo_city": "", "geo_country": ""},
                            gemini_model=settings.GEMINI_MODEL or "gemini-1.5-flash",
                        ),
                    )
                else:
                    geo_result = await asyncio.to_thread(ids_geo.lookup, src_ip, settings.IPINFO_TOKEN)
                    llm_result = ids_llm.get_static_response(result["label"])

                # Update LLM context with geo info (for alert building)
                llm_context["geo_city"] = geo_result.get("city", "Unknown")
                llm_context["geo_country"] = geo_result.get("country", "Unknown")

                # Build complete alert
                alert = ids_alerts.build_alert(
                    detection=result,
                    geo=geo_result,
                    llm=llm_result,
                    meta=meta,
                    related_logs=related_logs,
                )

                # Encrypt and store
                encrypted = ids_alerts.encrypt_alert(alert)
                await asyncio.to_thread(ids_db.store_alert, alert, encrypted)

                # Telegram notification (non-blocking, High/Medium only)
                ids_notify.notify(alert, settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID)

                # Broadcast to all IDS feed clients
                payload = json.dumps({"type": "ids_alert", "data": alert})
                for ws in ids_feed_clients[:]:
                    try:
                        await ws.send_text(payload)
                    except Exception:
                        if ws in ids_feed_clients:
                            ids_feed_clients.remove(ws)

            elif event.get("source") == "log":
                # Log-based detection — treat as an alert directly
                log_type = event.get("log_type", "generic")
                src_ip = event.get("src_ip", "0.0.0.0") or "0.0.0.0"
                severity = event.get("severity", "Medium")

                # Map log types to attack labels
                log_to_label = {
                    "auth_failure": "Brute Force",
                    "privilege_escalation": "Infiltration",
                    "http_scan": "Web Attack",
                    "http_error": "Web Attack",
                }
                label = log_to_label.get(log_type, "Unknown")
                if label == "Unknown" or log_type == "ssh_success":
                    continue  # not an attack

                # Deduplication: same IP + label within cooldown window
                now_ts = time.time()
                dedup_key = f"{src_ip}:{label}"
                if now_ts - _dedup.get(dedup_key, 0) < DEDUP_COOLDOWN:
                    continue
                _dedup[dedup_key] = now_ts

                # Collect related log lines
                related_logs = [
                    lg["raw_line"]
                    for lg in _recent_log_lines[-200:]
                    if lg.get("src_ip") == src_ip
                ][-5:]

                detection = {
                    "label": label,
                    "confidence": 0.85,
                    "is_attack": True,
                    "source": "log",
                    "all_probs": {label: 0.85},
                }

                meta = {
                    "src_ip": src_ip,
                    "dst_ip": "0.0.0.0",
                    "src_port": 0,
                    "dst_port": 22 if "ssh" in log_type.lower() or "auth" in log_type.lower() else 80,
                    "proto": 6,
                }

                llm_context = {
                    "attack_type": label,
                    "src_ip": src_ip,
                    "dst_ip": "0.0.0.0",
                    "dst_port": meta["dst_port"],
                    "protocol": 6,
                    "confidence": 0.85,
                    "severity": severity,
                    "geo_city": "",
                    "geo_country": "",
                    "flow_packets_per_s": 0.0,
                    "flow_bytes_per_s": 0.0,
                    "syn_flag_count": 0,
                    "packet_length_mean": 0.0,
                    "log_events": related_logs,
                }

                # Run geo + LLM in parallel
                # Gemini is only called for High severity to preserve daily quota.
                if severity == "High":
                    geo_result, llm_result = await asyncio.gather(
                        asyncio.to_thread(ids_geo.lookup, src_ip, settings.IPINFO_TOKEN),
                        ids_llm.enrich(
                            llm_context,
                            gemini_model=settings.GEMINI_MODEL or "gemini-1.5-flash",
                        ),
                    )
                else:
                    geo_result = await asyncio.to_thread(ids_geo.lookup, src_ip, settings.IPINFO_TOKEN)
                    llm_result = ids_llm.get_static_response(label)

                alert = ids_alerts.build_alert(
                    detection=detection,
                    geo=geo_result,
                    llm=llm_result,
                    meta=meta,
                    related_logs=related_logs,
                )

                encrypted = ids_alerts.encrypt_alert(alert)
                await asyncio.to_thread(ids_db.store_alert, alert, encrypted)

                # Telegram notification (non-blocking, High/Medium only)
                ids_notify.notify(alert, settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID)

                payload = json.dumps({"type": "ids_alert", "data": alert})
                for ws in ids_feed_clients[:]:
                    try:
                        await ws.send_text(payload)
                    except Exception:
                        if ws in ids_feed_clients:
                            ids_feed_clients.remove(ws)

                # Also push to log feed
                log_payload = json.dumps({"type": "log", "data": {
                    "timestamp": event.get("timestamp", time.time()),
                    "log_file": event.get("log_file", ""),
                    "raw_line": event.get("raw_line", ""),
                    "log_type": log_type,
                    "severity": severity,
                }})
                for ws in log_feed_clients[:]:
                    try:
                        await ws.send_text(log_payload)
                    except Exception:
                        if ws in log_feed_clients:
                            log_feed_clients.remove(ws)

        except Exception as exc:
            logging.error(f"Detection loop error: {exc}")
            await asyncio.sleep(0.1)


# ══════════════════════════════════════════════════════════════════
#  STARTUP SEQUENCE
# ══════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup():
    """Initialize IDS subsystems when the FastAPI app starts."""
    global aggregator

    # 1. Initialize database
    ids_db.init_db()

    # 2. Load ML model (exits if missing)
    model_dir = settings.IDS_MODEL_DIR
    if not os.path.isdir(model_dir):
        logging.error(
            f"FATAL: Model directory '{model_dir}' not found. "
            "Run 'python create_placeholder_model.py' first."
        )
        # Don't exit — allow the rest of the app to work; IDS will use rule engine only
        logging.warning("IDS ML model not available — rule engine only.")
    else:
        try:
            ids_engine.load_model(model_dir)
        except SystemExit:
            logging.warning("IDS ML model files incomplete — rule engine only.")

    # 3. Gemini SDK reads GEMINI_API_KEY / GOOGLE_API_KEY from env automatically

    # 4. Create aggregator with the current event loop
    loop = asyncio.get_event_loop()
    aggregator = FlowAggregator(detection_queue, loop=loop)

    # 5. Start packet capture thread (daemon)
    capture_thread = threading.Thread(
        target=ids_capture.start,
        args=(settings.CAPTURE_INTERFACE, aggregator),
        daemon=True,
    )
    capture_thread.start()

    # 6. Start log capture thread (daemon)
    log_paths = [p.strip() for p in settings.LOG_PATHS.split(",") if p.strip()]
    if log_paths:
        log_thread = threading.Thread(
            target=ids_log_capture.start,
            args=(log_paths, detection_queue, loop),
            daemon=True,
        )
        log_thread.start()

    # 7. Start async detection loop
    asyncio.create_task(detection_loop())

    logging.info("🛡️  Crypt Lab IDS startup complete.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
