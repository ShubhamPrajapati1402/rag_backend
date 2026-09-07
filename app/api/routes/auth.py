from typing import List, Optional
import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.models.developer_invitation import DeveloperInvitation
from app.schemas.user import (
    UserSignupRequest,
    UserLoginRequest,
    GoogleAuthRequest,
    OTPVerifyRequest,
    OTPResendRequest,
    UserResponse,
    AuthMessageResponse,
    TokenResponse,
    ManageDeveloperRequest,
    InviteDeveloperRequest,
    VerifyInviteResponse,
    AcceptInviteRequest,
    DeveloperMemberItem
)
from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from app.core.websocket_manager import ws_manager
from app.core.security import set_auth_cookie, delete_auth_cookie
from app.api.deps import get_current_active_user, get_current_superuser

router = APIRouter(prefix="/auth", tags=["Authentication"])

def get_user_role(user: User) -> str:
    """Determines authoritative developer role: SUPER_ADMIN, ADMIN, MEMBER, or USER."""
    primary_owners = [e.strip().lower() for e in settings.DEVELOPER_EMAILS.split(",") if e.strip()]
    if user.email.lower() in primary_owners:
        return "SUPER_ADMIN"
    if not user.is_superuser:
        return "USER"
    return user.developer_role or "MEMBER"


@router.post(
    "/signup",
    response_model=AuthMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account (dispatches 6-digit OTP in background)"
)
async def signup(
    signup_data: UserSignupRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    user = await AuthService.signup(db, signup_data, background_tasks)
    return AuthMessageResponse(
        message="Account registered. Please enter the verification OTP sent to your email.",
        user=UserResponse.model_validate(user) if user else None,
        email=signup_data.email
    )


@router.post(
    "/verify-otp",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify registration OTP and authenticate"
)
async def verify_otp(
    otp_data: OTPVerifyRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    user, access_token = await AuthService.verify_signup_otp(
        db, otp_data, background_tasks
    )
    set_auth_cookie(response, access_token)
    return TokenResponse(
        message="Email verified successfully. Welcome to Noesis!",
        user=UserResponse.model_validate(user),
        access_token=access_token
    )


@router.post(
    "/resend-otp",
    response_model=AuthMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Resend verification OTP"
)
async def resend_otp(
    resend_data: OTPResendRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    await AuthService.resend_signup_otp(db, resend_data, background_tasks)
    return AuthMessageResponse(
        message="A new 6-digit verification code has been dispatched to your email.",
        email=resend_data.email
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate with email and password"
)
async def login(
    login_data: UserLoginRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    user, access_token = await AuthService.login(db, login_data)
    set_auth_cookie(response, access_token)
    return TokenResponse(
        message="Authentication successful.",
        user=UserResponse.model_validate(user),
        access_token=access_token
    )


@router.post(
    "/google",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate or register seamlessly via Google OAuth2"
)
async def google_auth(
    google_data: GoogleAuthRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    user, access_token = await AuthService.authenticate_google(
        db, google_data.id_token, background_tasks
    )
    set_auth_cookie(response, access_token)
    return TokenResponse(
        message="Google authentication successful.",
        user=UserResponse.model_validate(user),
        access_token=access_token
    )


@router.post(
    "/logout",
    response_model=AuthMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Sign out and clear session cookie"
)
def logout(response: Response):
    delete_auth_cookie(response)
    return AuthMessageResponse(message="Successfully logged out.")


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile"
)
def get_me(current_user: User = Depends(get_current_active_user)):
    resp = UserResponse.model_validate(current_user)
    primary_owners = [e.strip().lower() for e in settings.DEVELOPER_EMAILS.split(",") if e.strip()]
    resp.is_primary_owner = (current_user.email.lower() in primary_owners)
    resp.developer_role = get_user_role(current_user)
    return resp


# --------------------------------------------------------------------------
# DEVELOPER RBAC & TOKENIZED INVITATION ROUTES
# --------------------------------------------------------------------------

@router.get(
    "/developers",
    response_model=List[DeveloperMemberItem],
    status_code=status.HTTP_200_OK,
    summary="List all active developers and pending invitations"
)
def list_developers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Returns active team members (Super Admin, Admin, Member) and pending invitations.
    Protected: Developer only.
    """
    primary_owners = [e.strip().lower() for e in settings.DEVELOPER_EMAILS.split(",") if e.strip()]
    devs = db.query(User).filter(User.is_superuser == True).order_by(User.created_at.desc()).all()
    
    results: List[DeveloperMemberItem] = []
    
    # 1. Active Joined Developers
    for u in devs:
        is_primary = u.email.lower() in primary_owners
        role = "SUPER_ADMIN" if is_primary else (u.developer_role or "MEMBER")
        presence = "ONLINE" if ws_manager.is_online(u.email) else "OFFLINE"
        
        results.append(DeveloperMemberItem(
            id=u.id,
            email=u.email,
            full_name=u.full_name or u.email.split("@")[0],
            avatar_url=u.avatar_url,
            role=role,
            status="ACCEPTED",
            presence=presence,
            is_primary_owner=is_primary,
            created_at=u.created_at
        ))

    # 2. Pending Invitations
    invitations = db.query(DeveloperInvitation).filter(
        DeveloperInvitation.status == "PENDING"
    ).order_by(DeveloperInvitation.created_at.desc()).all()

    for inv in invitations:
        # If user already accepted or active, skip
        if any(d.email.lower() == inv.email.lower() for d in results):
            continue
        results.append(DeveloperMemberItem(
            id=None,
            invitation_id=inv.id,
            email=inv.email,
            full_name=inv.email.split("@")[0],
            avatar_url=None,
            role=inv.role,
            status="PENDING",
            presence="PENDING",
            is_primary_owner=False,
            created_at=inv.created_at
        ))

    return results


@router.post(
    "/invite-developer",
    response_model=AuthMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Send tokenized developer invitation link with role"
)
def invite_developer(
    req: InviteDeveloperRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Creates a pending invitation with a secure token and sends an email with the join link.
    RBAC Rules:
    - Super Admin can invite 'ADMIN' and 'MEMBER'.
    - Admin can only invite 'MEMBER'.
    - Member cannot invite.
    """
    caller_role = get_user_role(current_user)
    target_role = req.role.upper() if req.role else "MEMBER"

    if caller_role == "MEMBER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission Denied: Standard Members cannot invite team members."
        )

    if caller_role == "ADMIN" and target_role == "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission Denied: Only Super Admins can invite new Admins."
        )

    clean_email = req.email.strip().lower()
    primary_owners = [e.strip().lower() for e in settings.DEVELOPER_EMAILS.split(",") if e.strip()]
    if clean_email in primary_owners:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already the Super Admin / Primary Owner."
        )

    # Invalidate prior pending invitations for this email
    existing_invites = db.query(DeveloperInvitation).filter(
        DeveloperInvitation.email == clean_email,
        DeveloperInvitation.status == "PENDING"
    ).all()
    for ex in existing_invites:
        ex.status = "EXPIRED"

    # Generate secure random invitation token valid for 48 hours
    invite_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(hours=48)
    invitation = DeveloperInvitation(
        email=clean_email,
        token=invite_token,
        role=target_role,
        invited_by_email=current_user.email,
        status="PENDING",
        expires_at=expires_at
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    # Send invitation email with join link (valid for 48h)
    background_tasks.add_task(
        EmailService.send_developer_invite_email,
        to_email=clean_email,
        inviter_email=current_user.email,
        inviter_name=current_user.full_name,
        role=target_role,
        invite_token=invite_token
    )

    # Broadcast live WebSocket event
    background_tasks.add_task(
        ws_manager.broadcast_event,
        "DEVELOPER_INVITED",
        {
            "id": None,
            "invitation_id": invitation.id,
            "email": clean_email,
            "full_name": clean_email.split("@")[0],
            "role": target_role,
            "status": "PENDING",
            "presence": "PENDING",
            "created_at": invitation.created_at.isoformat() if invitation.created_at else None,
            "expires_at": invitation.expires_at.isoformat() if invitation.expires_at else None,
            "invited_by": current_user.email
        }
    )

    role_label = "Admin" if target_role == "ADMIN" else "Developer Member"
    return AuthMessageResponse(
        message=f"Invitation link sent to {clean_email} as {role_label} (valid for 48 hours)!"
    )


@router.get(
    "/verify-invite",
    response_model=VerifyInviteResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify invitation token before acceptance"
)
def verify_invite(
    token: str = Query(..., description="Invitation token"),
    db: Session = Depends(get_db)
):
    invitation = db.query(DeveloperInvitation).filter(
        DeveloperInvitation.token == token,
        DeveloperInvitation.status == "PENDING"
    ).first()

    if not invitation or invitation.is_expired():
        if invitation and invitation.is_expired():
            invitation.status = "EXPIRED"
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This invitation link is invalid, expired, or has already been accepted (invitations expire 48 hours after dispatch)."
        )

    return VerifyInviteResponse(
        email=invitation.email,
        role=invitation.role,
        invited_by_email=invitation.invited_by_email,
        is_valid=True,
        expires_at=invitation.expires_at
    )


@router.post(
    "/accept-invite",
    response_model=AuthMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Accept developer team invitation and activate privileges"
)
def accept_invite(
    req: AcceptInviteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    invitation = db.query(DeveloperInvitation).filter(
        DeveloperInvitation.token == req.token,
        DeveloperInvitation.status == "PENDING"
    ).first()

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation link is invalid or has already been used."
        )

    if invitation.is_expired():
        invitation.status = "EXPIRED"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation link has expired. Invitation links are only valid for 48 hours from the time they are dispatched."
        )

    # Strict recipient validation: only the exact invited email account can accept
    if invitation.email.lower() != current_user.email.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Security Policy: This invitation was generated exclusively for '{invitation.email}'. You are currently authenticated as '{current_user.email}'. Please sign in with '{invitation.email}' to accept this invitation."
        )

    # Activate developer privileges
    current_user.is_superuser = True
    current_user.developer_role = invitation.role
    invitation.status = "ACCEPTED"
    invitation.accepted_at = datetime.now(ZoneInfo("Asia/Kolkata"))
    db.commit()

    # Real-time WebSocket broadcast
    background_tasks.add_task(
        ws_manager.broadcast_event,
        "DEVELOPER_JOINED",
        {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.developer_role,
            "status": "ACCEPTED",
            "presence": "ONLINE" if ws_manager.is_online(current_user.email) else "OFFLINE",
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None
        }
    )

    role_label = "Admin" if current_user.developer_role == "ADMIN" else "Developer Member"
    return AuthMessageResponse(
        message=f"Welcome! You have successfully joined the team as {role_label}."
    )


@router.post(
    "/manage-developer",
    response_model=AuthMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke developer access or cancel pending invitation"
)
def manage_developer(
    req: ManageDeveloperRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Revokes developer privileges or cancels pending invitations with strict RBAC protection:
    - Super Admin cannot be revoked or demoted by anyone.
    - Admins cannot revoke Super Admin or other Admins.
    - Members cannot revoke anyone.
    """
    caller_role = get_user_role(current_user)
    if caller_role == "MEMBER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission Denied: Standard Members cannot manage team access."
        )

    clean_email = req.email.strip().lower()
    primary_owners = [e.strip().lower() for e in settings.DEVELOPER_EMAILS.split(",") if e.strip()]

    # Security rule: Super Admin cannot be revoked
    if clean_email in primary_owners:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Security Policy: Cannot revoke privileges from Super Admin / Owner '{clean_email}'."
        )

    # 1. Check if user is active developer
    target_user = db.query(User).filter(User.email == clean_email).first()
    if target_user and target_user.is_superuser:
        target_role = get_user_role(target_user)
        if caller_role == "ADMIN" and target_role in ("SUPER_ADMIN", "ADMIN"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission Denied: Admins cannot revoke Super Admin or other Admins."
            )

        if not req.is_developer:
            target_user.is_superuser = False
            target_user.developer_role = None
            db.commit()

            background_tasks.add_task(
                ws_manager.broadcast_event,
                "DEVELOPER_REVOKED",
                {
                    "email": clean_email,
                    "revoked_by": current_user.email
                }
            )
            return AuthMessageResponse(
                message=f"Developer access successfully revoked from {clean_email}."
            )

    # 2. Check if there's a pending invitation to cancel
    pending_inv = db.query(DeveloperInvitation).filter(
        DeveloperInvitation.email == clean_email,
        DeveloperInvitation.status == "PENDING"
    ).first()

    if pending_inv:
        if caller_role == "ADMIN" and pending_inv.role == "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission Denied: Admins cannot cancel Admin invitations."
            )
        pending_inv.status = "REVOKED"
        db.commit()

        background_tasks.add_task(
            ws_manager.broadcast_event,
            "DEVELOPER_REVOKED",
            {
                "email": clean_email,
                "revoked_by": current_user.email
            }
        )
        return AuthMessageResponse(
            message=f"Pending invitation for {clean_email} has been cancelled."
        )

    return AuthMessageResponse(
        message=f"No active developer access or pending invitation found for {clean_email}."
    )
