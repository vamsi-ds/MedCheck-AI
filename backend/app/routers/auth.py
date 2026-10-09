"""Authentication endpoints: registration (with admin approval), login, current user."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import audit
from ..config import ALLOW_DEV_ADMIN_BOOTSTRAP, SECRET_KEY_IS_DEV
from ..database import get_db
from ..models import User, UserStatus, UserRole
from ..schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from ..security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Request a new account.

    New accounts are created with status "pending" and must be approved by an
    administrator. Requesting the admin role is rejected outright — nobody can
    grant themselves administrator privileges.
    """
    if db.query(User).filter((User.username == payload.username) | (User.email == payload.email)).first():
        raise HTTPException(status_code=409, detail="Username or email already registered.")
    user = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=UserRole(payload.role),
        status=UserStatus.pending,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    audit.record(db, "user.register", actor_user_id=user.id, entity_type="user",
                 entity_id=user.id, detail=f"role={user.role.value} status=pending")
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Log in with username/password; returns a signed bearer token."""
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        audit.record(db, "user.login_failed", detail=f"username={payload.username}")
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    if user.status == UserStatus.pending:
        raise HTTPException(status_code=403, detail="Your account is awaiting administrator approval.")
    if user.status == UserStatus.inactive:
        raise HTTPException(status_code=403, detail="Your account has been deactivated. Contact an administrator.")
    token = create_access_token(user)
    audit.record(db, "user.login", actor_user_id=user.id, entity_type="user", entity_id=user.id)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    """Return the currently authenticated user (role comes from the server)."""
    return user


@router.post("/dev-bootstrap-admin", response_model=UserOut,
             status_code=status.HTTP_201_CREATED)
def dev_bootstrap_admin(db: Session = Depends(get_db)):
    """Development-only: create the first administrator account.

    Only works while MEDCHECK_DEV_ADMIN_BOOTSTRAP=1 (default) AND the backend
    still uses the development secret key. In any hardened deployment both
    conditions are false and this endpoint returns 404. Credentials:
    username "admin", password "Admin123!" — intended for local setup only and
    documented in the README as development-only.
    """
    if not (ALLOW_DEV_ADMIN_BOOTSTRAP and SECRET_KEY_IS_DEV):
        raise HTTPException(status_code=404, detail="Not found.")
    if db.query(User).filter(User.role == UserRole.admin).first():
        raise HTTPException(status_code=409, detail="An administrator already exists.")
    admin = User(
        username="admin",
        email="admin@medcheck.local",
        full_name="System Administrator",
        password_hash=hash_password("Admin123!"),
        role=UserRole.admin,
        status=UserStatus.active,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    audit.record(db, "user.bootstrap_admin", actor_user_id=admin.id, entity_type="user",
                 entity_id=admin.id, detail="created via development bootstrap endpoint")
    return admin
