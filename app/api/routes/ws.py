import json
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from loguru import logger
import jwt

from app.core.config import settings
from app.core.websocket_manager import ws_manager
from app.db.session import SessionLocal
from app.models.user import User

router = APIRouter(tags=["WebSockets"])

def get_user_from_token(token: str) -> Optional[User]:
    """Helper to synchronously decode JWT and fetch user from DB for WebSocket handshake."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
        user_id = int(user_id_str)
        db = SessionLocal()
        try:
            return db.query(User).filter(User.id == user_id, User.is_active == True).first()
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"[WebSocket] JWT validation failed: {e}")
        return None

from app.models.developer_invitation import DeveloperInvitation

def get_developer_team_snapshot() -> list:
    """Generates real-time state snapshot of all developers and pending invitations with live presence."""
    db = SessionLocal()
    try:
        primary_owners = [e.strip().lower() for e in settings.DEVELOPER_EMAILS.split(",") if e.strip()]
        devs = db.query(User).filter(User.is_superuser == True).order_by(User.created_at.desc()).all()
        snapshot = []

        # 1. Active Developers
        for d in devs:
            is_primary = d.email.lower() in primary_owners
            role = "SUPER_ADMIN" if is_primary else (d.developer_role or "MEMBER")
            presence = "ONLINE" if ws_manager.is_online(d.email) else "OFFLINE"

            snapshot.append({
                "id": d.id,
                "email": d.email,
                "full_name": d.full_name or d.email.split("@")[0],
                "avatar_url": d.avatar_url,
                "role": role,
                "status": "ACCEPTED",
                "is_superuser": d.is_superuser,
                "is_primary_owner": is_primary,
                "presence": presence,
                "created_at": d.created_at.isoformat() if d.created_at else None
            })

        # 2. Pending Invitations
        invitations = db.query(DeveloperInvitation).filter(
            DeveloperInvitation.status == "PENDING"
        ).order_by(DeveloperInvitation.created_at.desc()).all()

        for inv in invitations:
            if any(s["email"].lower() == inv.email.lower() for s in snapshot):
                continue
            snapshot.append({
                "id": None,
                "invitation_id": inv.id,
                "email": inv.email,
                "full_name": inv.email.split("@")[0],
                "avatar_url": None,
                "role": inv.role,
                "status": "PENDING",
                "is_superuser": False,
                "is_primary_owner": False,
                "presence": "PENDING",
                "created_at": inv.created_at.isoformat() if inv.created_at else None
            })

        return snapshot
    finally:
        db.close()


@router.websocket("/ws/developer-team")
async def websocket_developer_team(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """
    Bidirectional WebSocket endpoint for Real-Time Developer Team presence and synchronization.
    Authenticates via JWT token query param (?token=...) or HttpOnly session cookie.
    """
    # 1. Extract Token from Query param or Cookie
    auth_token = token
    if not auth_token:
        cookies = websocket.cookies
        auth_token = cookies.get(settings.COOKIE_NAME)

    # 2. Authenticate User
    user = get_user_from_token(auth_token) if auth_token else None
    if not user:
        logger.warning("[WebSocket] Connection rejected: Unauthorized (invalid or missing JWT token)")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if not user.is_superuser:
        logger.warning(f"[WebSocket] Connection rejected: User '{user.email}' is not a developer/superuser.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 3. Register Connection
    await ws_manager.connect(websocket, user.email, is_developer=True)

    try:
        # 4. Dispatch Initial Team State Snapshot immediately
        initial_snapshot = get_developer_team_snapshot()
        await websocket.send_text(json.dumps({
            "type": "TEAM_STATE",
            "payload": {
                "developers": initial_snapshot,
                "current_user_email": user.email
            }
        }))

        # 5. Keep connection alive and process incoming client heartbeats/pings
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type")

                if msg_type == "PING":
                    await websocket.send_text(json.dumps({"type": "PONG"}))
                elif msg_type == "REFRESH_TEAM":
                    snapshot = get_developer_team_snapshot()
                    await websocket.send_text(json.dumps({
                        "type": "TEAM_STATE",
                        "payload": { "developers": snapshot }
                    }))
            except Exception:
                pass

    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, user.email)
    except Exception as e:
        logger.error(f"[WebSocket] Error in developer-team socket for {user.email}: {e}")
        await ws_manager.disconnect(websocket, user.email)
