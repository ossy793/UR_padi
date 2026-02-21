# backend/api/routes/websocket.py
"""
WebSocket endpoint for real-time health score updates.
Clients connect, authenticate via token query param, and receive
live score broadcasts whenever a new health score is submitted.
"""
import asyncio
import json
from typing import Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from core.security import decode_access_token

router = APIRouter(tags=["WebSocket"])

# Active connections: user_id → list of WebSocket connections
_connections: Dict[int, list[WebSocket]] = {}


async def broadcast_score(user_id: int, score_data: dict) -> None:
    """Called externally to push a score update to connected clients."""
    sockets = _connections.get(user_id, [])
    dead = []
    for ws in sockets:
        try:
            await ws.send_text(json.dumps({"event": "score_update", "data": score_data}))
        except Exception:
            dead.append(ws)
    for ws in dead:
        sockets.remove(ws)


@router.websocket("/ws/scores")
async def websocket_scores(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
):
    # Authenticate
    user_id_str = decode_access_token(token)
    if not user_id_str:
        await websocket.close(code=4001)
        return

    user_id = int(user_id_str)
    await websocket.accept()

    # Register connection
    _connections.setdefault(user_id, []).append(websocket)
    try:
        await websocket.send_text(json.dumps({"event": "connected", "user_id": user_id}))
        # Keep alive: echo any ping messages as valid JSON
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"event": "pong"}))
    except WebSocketDisconnect:
        _connections.get(user_id, []).remove(websocket)