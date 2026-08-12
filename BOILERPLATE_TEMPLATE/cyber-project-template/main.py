"""
Cyber Project Template - FastAPI Backend
Provides WebSocket endpoints for real-time monitoring with optimized Gemini analysis.

Key optimizations:
1. Debounced analysis worker: Groups events into windows, reduces API calls
2. Async/await architecture: Non-blocking I/O, efficient resource usage
3. Page Visibility API support: Frontend automatically pauses stats polling when hidden
4. Debug WebSocket: Monitor Gemini calls and errors in real-time
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import asyncio
import json
import logging
import time
from typing import Dict, List, Optional
from collections import deque

from config import settings

# Configure logging
logging.basicConfig(level=logging.DEBUG if settings.DEBUG else logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Cyber Project Template")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# ============================================================================
# Data Structures
# ============================================================================

# Active WebSocket connections per resource
active_connections: Dict[str, List[WebSocket]] = {}

# Terminal/resource buffers (circular, max 2000 entries)
resource_buffers: Dict[str, deque] = {}

# Analysis event queues for debouncing (per resource)
analysis_queues: Dict[str, asyncio.Queue] = {}

# Debug event stream (observability for Gemini calls)
debug_events: deque = deque(maxlen=500)
debug_ws_clients: List[WebSocket] = []


# ============================================================================
# Helper Functions
# ============================================================================

def get_or_create_buffers(resource_id: str):
    """Initialize buffers and queues for a resource if not already created."""
    if resource_id not in active_connections:
        active_connections[resource_id] = []
    if resource_id not in resource_buffers:
        resource_buffers[resource_id] = deque(maxlen=2000)
    if resource_id not in analysis_queues:
        analysis_queues[resource_id] = asyncio.Queue()


def log_debug_event(event_type: str, data: dict):
    """Log an event to debug stream (Gemini calls, errors, etc.)."""
    event = {
        "ts": time.time(),
        "event": event_type,
        **data
    }
    debug_events.append(event)
    logger.debug(f"[DEBUG] {event_type}: {data}")
    
    # Broadcast to all debug clients
    for ws in debug_ws_clients[:]:
        try:
            asyncio.create_task(ws.send_text(json.dumps({"type": "event", "data": event})))
        except:
            if ws in debug_ws_clients:
                debug_ws_clients.remove(ws)


# ============================================================================
# WebSocket Endpoints
# ============================================================================

@app.websocket("/ws/monitor/{resource_id}")
async def monitor_websocket(websocket: WebSocket, resource_id: str):
    """
    Real-time monitoring WebSocket.
    Receives user input and broadcasts resource output to all connected clients.
    """
    await websocket.accept()
    get_or_create_buffers(resource_id)
    active_connections[resource_id].append(websocket)
    
    logger.info(f"[WS] Monitor connection opened: {resource_id}")
    
    try:
        while True:
            # Receive input from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "input":
                payload = message.get("data", "")
                logger.debug(f"[Monitor] Input from {resource_id}: {payload[:50]}")
                
                # TODO: Process input (send to resource, etc.)
                # For now, just log it
                resource_buffers[resource_id].append(f"INPUT: {payload}")
                
                # Trigger analysis on newline (optional)
                if settings.ANALYSIS_ENABLED and "\n" in payload:
                    try:
                        analysis_queues[resource_id].put_nowait({
                            "type": "command",
                            "data": payload.strip(),
                            "ts": time.time()
                        })
                    except:
                        pass
    
    except WebSocketDisconnect:
        active_connections[resource_id].remove(websocket)
        logger.info(f"[WS] Monitor connection closed: {resource_id}")


@app.websocket("/ws/stats/{resource_id}")
async def stats_websocket(websocket: WebSocket, resource_id: str):
    """
    System metrics WebSocket.
    Sends CPU, memory, disk, and load stats every 2 seconds.
    
    NOTE: Frontend automatically pauses this connection when page becomes hidden
    (Page Visibility API), reducing unnecessary bandwidth and API calls.
    """
    await websocket.accept()
    get_or_create_buffers(resource_id)
    
    logger.info(f"[WS] Stats connection opened: {resource_id}")
    
    try:
        while True:
            # TODO: Collect actual stats from resource
            # For demo, return static data
            stats = {
                "cpu": 45.2,
                "memory": 62.5,
                "disk": 38.1,
                "load": 1.23
            }
            
            await websocket.send_text(json.dumps({
                "type": "stats",
                "data": stats
            }))
            
            # Update every 2 seconds
            await asyncio.sleep(2)
    
    except WebSocketDisconnect:
        logger.info(f"[WS] Stats connection closed: {resource_id}")


@app.websocket("/ws/debug")
async def debug_websocket(websocket: WebSocket):
    """
    Debug event stream WebSocket.
    Broadcasts all Gemini API calls, errors, and analysis results.
    Useful for monitoring and troubleshooting.
    
    Visit http://localhost:8000/debug in a separate browser tab to monitor in real-time.
    """
    await websocket.accept()
    debug_ws_clients.append(websocket)
    
    logger.info("[WS] Debug connection opened")
    
    try:
        # Send recent events on connect
        for ev in list(debug_events)[-50:]:
            await websocket.send_text(json.dumps({"type": "event", "data": ev}))
        
        # Keep connection alive
        while True:
            await asyncio.sleep(5)
    
    except WebSocketDisconnect:
        if websocket in debug_ws_clients:
            debug_ws_clients.remove(websocket)
        logger.info("[WS] Debug connection closed")


# ============================================================================
# REST Endpoints
# ============================================================================

@app.get("/")
async def get_index():
    """Serve main HTML."""
    return FileResponse("static/index.html")


@app.get("/debug")
async def get_debug_page():
    """Serve debug dashboard HTML."""
    return FileResponse("static/debug.html")


@app.get("/api/health")
async def api_health():
    """Health check endpoint with connection status."""
    return {
        "status": "ok",
        "timestamp": time.time(),
        "gemini": {
            "enabled": bool(settings.GEMINI_API_KEY),
            "model": settings.GEMINI_MODEL,
            "analysis_enabled": settings.ANALYSIS_ENABLED,
        },
        "connections": {resource_id: len(clients) 
                       for resource_id, clients in active_connections.items()},
        "debug_clients": len(debug_ws_clients),
    }


@app.post("/api/analyze")
async def manual_analyze(payload: dict):
    """
    Manually trigger analysis on provided logs.
    Useful for on-demand security analysis without waiting for debounce timer.
    """
    if not settings.GEMINI_API_KEY:
        return JSONResponse(
            {"ok": False, "error": "gemini_api_key_missing"},
            status_code=400
        )
    
    logs = payload.get("logs", "")
    if not logs:
        return JSONResponse(
            {"ok": False, "error": "no_logs_provided"},
            status_code=400
        )
    
    log_debug_event("manual_analysis_request", {"chars": len(logs)})
    
    # TODO: Call Gemini API here
    # For now, return mock response
    return {
        "ok": True,
        "analysis": {
            "status": "ok",
            "security_analysis": "Mock analysis result (integrate with Gemini)",
            "detections": [],
            "recommendations": []
        }
    }


@app.get("/api/models")
async def list_models():
    """List available Gemini models (if API key is set)."""
    if not settings.GEMINI_API_KEY:
        return JSONResponse(
            {"ok": False, "error": "gemini_api_key_missing"},
            status_code=400
        )
    
    # TODO: Query Gemini API for available models
    return {
        "ok": True,
        "models": [
            {"name": "gemini-2.5-flash", "supported_methods": ["generateContent"]},
            {"name": "gemini-2.5-pro", "supported_methods": ["generateContent"]},
        ]
    }


# ============================================================================
# Background Workers
# ============================================================================

async def analysis_worker(resource_id: str):
    """
    Debounced analysis worker per resource.
    
    Groups analysis events (terminal output, commands) into time windows
    before sending to Gemini. This dramatically reduces API calls while
    maintaining near-real-time analysis responsiveness.
    
    Key optimization: Sends 1 API call per ~2.5 seconds instead of per keystroke.
    """
    debounce_sec = settings.analysis_debounce_sec
    
    while True:
        try:
            # Wait for at least one event
            evt = await analysis_queues[resource_id].get()
            last_ts = time.time()
            
            # Drain additional events during debounce window
            while True:
                timeout = debounce_sec - (time.time() - last_ts)
                if timeout <= 0:
                    break
                try:
                    await asyncio.wait_for(
                        analysis_queues[resource_id].get(),
                        timeout=timeout
                    )
                    last_ts = time.time()
                except asyncio.TimeoutError:
                    break
            
            # Prepare sample from buffer
            buffer_content = "".join(list(resource_buffers[resource_id]))
            if settings.ANALYSIS_SAMPLE_SIZE and len(buffer_content) > settings.ANALYSIS_SAMPLE_SIZE:
                buffer_content = buffer_content[-settings.ANALYSIS_SAMPLE_SIZE:]
            
            logger.debug(f"[Analysis] Processing {resource_id} ({len(buffer_content)} chars)")
            
            # TODO: Call Gemini API with buffer_content
            # For now, log and mock response
            log_debug_event("analysis_queued", {
                "resource_id": resource_id,
                "chars": len(buffer_content),
                "debounce_ms": settings.ANALYSIS_DEBOUNCE_MS
            })
            
            analysis_result = {
                "status": "ok",
                "security_analysis": "Mock analysis (integrate with Gemini)",
                "detections": [],
                "recommendations": []
            }
            
            # Broadcast to all connected clients
            payload = json.dumps({
                "type": "analysis",
                "resource_id": resource_id,
                "data": analysis_result
            })
            
            for ws in active_connections.get(resource_id, [])[:]:
                try:
                    await ws.send_text(payload)
                except:
                    if ws in active_connections.get(resource_id, []):
                        active_connections[resource_id].remove(ws)
        
        except Exception as e:
            log_debug_event("analysis_worker_error", {
                "resource_id": resource_id,
                "error": str(e)
            })
            await asyncio.sleep(1)


# ============================================================================
# Startup/Shutdown
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize workers on startup."""
    logger.info("Starting Cyber Project Template...")
    # TODO: Start analysis workers for each resource if needed
    # For now, they are lazy-started on first WebSocket connection


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    logger.info("Shutting down...")
    for clients in active_connections.values():
        for ws in clients:
            try:
                await ws.close()
            except:
                pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="debug" if settings.DEBUG else "info"
    )
