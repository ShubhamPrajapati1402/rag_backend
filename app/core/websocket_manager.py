import json
import asyncio
from typing import Dict, Set, Any, Optional
from fastapi import WebSocket
from loguru import logger
import redis.asyncio as aioredis
from app.core.config import settings

class WebSocketManager:
    """
    Centralized Real-Time WebSocket Connection & Pub/Sub Manager.
    Supports local connection clustering and Redis Pub/Sub broadcast across multi-worker instances.
    """
    def __init__(self):
        # Map: user_email -> Set[WebSocket]
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Room: "developer_team" -> Set[WebSocket]
        self.team_subscribers: Set[WebSocket] = set()
        self.redis_client: Optional[aioredis.Redis] = None
        self.pubsub_task: Optional[asyncio.Task] = None
        self._init_redis()

    def _init_redis(self):
        try:
            if settings.REDIS_URL:
                self.redis_client = aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True
                )
                logger.info("[WebSocketManager] Redis connection initialized for Pub/Sub clustering.")
        except Exception as e:
            logger.warning(f"[WebSocketManager] Redis initialization warning: {e}. Falling back to in-memory broadcast.")
            self.redis_client = None

    async def start_pubsub_listener(self):
        """Starts background listener on Redis channel 'developer_team_events'."""
        if not self.redis_client:
            return
        try:
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe("developer_team_events")
            logger.info("[WebSocketManager] Subscribed to Redis channel 'developer_team_events'")
            
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message.get("data"):
                    try:
                        event_data = json.loads(message["data"])
                        await self._local_broadcast(event_data)
                    except Exception as parse_err:
                        logger.error(f"[WebSocketManager] Error handling Redis pubsub message: {parse_err}")
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            logger.info("[WebSocketManager] Redis pubsub listener stopped.")
        except Exception as e:
            logger.warning(f"[WebSocketManager] Redis pubsub listener error: {e}")

    async def connect(self, websocket: WebSocket, email: str, is_developer: bool = True):
        """Registers a new active WebSocket connection and joins the developer team room."""
        await websocket.accept()
        email_clean = email.strip().lower()

        if email_clean not in self.active_connections:
            self.active_connections[email_clean] = set()
        self.active_connections[email_clean].add(websocket)

        if is_developer:
            self.team_subscribers.add(websocket)

        logger.info(f"[WebSocketManager] Client connected: {email_clean} (Total connections for user: {len(self.active_connections[email_clean])})")

        # Broadcast presence change if this is their first connection
        if len(self.active_connections[email_clean]) == 1 and is_developer:
            await self.broadcast_event("PRESENCE_CHANGE", {
                "email": email_clean,
                "presence": "ONLINE"
            })

    async def disconnect(self, websocket: WebSocket, email: str):
        """Removes a disconnected WebSocket client and notifies subscribers if user went offline."""
        email_clean = email.strip().lower()

        if email_clean in self.active_connections:
            self.active_connections[email_clean].discard(websocket)
            if not self.active_connections[email_clean]:
                del self.active_connections[email_clean]
                # User is completely offline
                await self.broadcast_event("PRESENCE_CHANGE", {
                    "email": email_clean,
                    "presence": "OFFLINE"
                })

        self.team_subscribers.discard(websocket)
        logger.info(f"[WebSocketManager] Client disconnected: {email_clean}")

    def is_online(self, email: str) -> bool:
        """Returns True if user currently has at least 1 active WebSocket connection."""
        return email.strip().lower() in self.active_connections

    def get_online_emails(self) -> Set[str]:
        """Returns set of all currently connected user emails."""
        return set(self.active_connections.keys())

    async def broadcast_event(self, event_type: str, payload: Dict[str, Any]):
        """
        Publishes event to Redis if available, or broadcasts locally to all connected team subscribers.
        """
        event_message = {
            "type": event_type,
            "payload": payload,
            "timestamp": asyncio.get_event_loop().time()
        }

        # If Redis is active, publish to channel for multi-worker sync
        if self.redis_client:
            try:
                await self.redis_client.publish("developer_team_events", json.dumps(event_message))
                return
            except Exception as e:
                logger.warning(f"[WebSocketManager] Redis publish failed ({e}), using local broadcast fallback.")

        # Local fallback
        await self._local_broadcast(event_message)

    async def _local_broadcast(self, event_message: Dict[str, Any]):
        """Dispatches event to all active team subscribers connected to this worker."""
        if not self.team_subscribers:
            return

        dead_sockets = set()
        json_payload = json.dumps(event_message)

        for ws in list(self.team_subscribers):
            try:
                await ws.send_text(json_payload)
            except Exception as send_err:
                logger.debug(f"[WebSocketManager] Error sending to socket: {send_err}")
                dead_sockets.add(ws)

        for dead_ws in dead_sockets:
            self.team_subscribers.discard(dead_ws)

    async def send_to_user(self, email: str, event_type: str, payload: Dict[str, Any]):
        """Sends targeted message to specific user's active sockets."""
        email_clean = email.strip().lower()
        sockets = self.active_connections.get(email_clean, set())
        if not sockets:
            return

        json_payload = json.dumps({
            "type": event_type,
            "payload": payload
        })
        for ws in list(sockets):
            try:
                await ws.send_text(json_payload)
            except Exception:
                pass


# Global singleton instance
ws_manager = WebSocketManager()
