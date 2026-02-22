"""
WebSocket connection manager.
Tracks connected clients per channel and broadcasts messages.
"""

from fastapi import WebSocket
from typing import DefaultDict
from collections import defaultdict


class ConnectionManager:
    def __init__(self):
        self._connections: DefaultDict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, channel: str):
        await websocket.accept()
        self._connections[channel].append(websocket)

    def disconnect(self, websocket: WebSocket, channel: str):
        if websocket in self._connections[channel]:
            self._connections[channel].remove(websocket)

    async def broadcast(self, channel: str, data: dict):
        """Send data to all clients on a channel. Remove dead connections."""
        dead = []
        for ws in self._connections[channel]:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, channel)

    def count(self, channel: str) -> int:
        return len(self._connections[channel])


ws_manager = ConnectionManager()
