"""
Authentication routes
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import jwt

from database import get_db
from config import settings
from app.models.user import User, UserRole, UserStatus
from app.schemas.user import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    UserPasswordChange, PasswordResetRequest, PasswordReset,
    EmailVerification, UserProfile, UserSettings, UserUpdate
)
from app.services.auth_service import AuthService
from app.services.audit_service import AuditService
from app.middleware.rate_limit import RateLimitMiddleware
from app.utils.security import get_current_user, get_current_active_user

router = APIRouter()
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Register a new user"""
    
    # Check if user already exists
    existing_user = db.query(User).filter(
        (User.email == user_data.email) | (User.username == user_data.username)
    ).first()
    
    if existing_user:
        # Log failed registration attempt
        AuditService.log_auth_event(
            "REGISTRATION_FAILED",
            None,
            request,
            {"email": user_data.email, "reason": "user_exists"}
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email or username already exists"
        )
    
    # Validate GDPR consent
    if not user_data.gdpr_consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GDPR consent is required"
        )
    
    # Create user
    user = AuthService.create_user(db, user_data, request)
    
    # Generate tokens
    access_token = AuthService.create_access_token({"sub": str(user.id)})
    refresh_token = AuthService.create_refresh_token({"sub": str(user.id)})
    
    # Log successful registration
    AuditService.log_auth_event(
        "USER_REGISTERED",
        user.id,
        request,
        {"email": user.email, "role": user.role.value}
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        user=UserResponse.from_orm(user)
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Authenticate user and return tokens"""
    
    # Find user
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if not user or not AuthService.verify_password(credentials.password, user.password_hash):
        # Log failed login attempt
        AuditService.log_auth_event(
            "LOGIN_FAILED",
            user.id if user else None,
            request,
            {"email": credentials.email, "reason": "invalid_credentials"}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check if user is active
    if not user.is_active:
        AuditService.log_auth_event(
            "LOGIN_FAILED",
            user.id,
            request,
            {"email": credentials.email, "reason": "account_inactive"}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive"
        )
    
    # Update last login
    user.last_login_at = datetime.utcnow()
    user.last_login_ip = request.client.host
    db.commit()
    
    # Generate tokens
    access_token = AuthService.create_access_token({"sub": str(user.id)})
    refresh_token = AuthService.create_refresh_token({"sub": str(user.id)})
    
    # Set refresh token as httpOnly cookie if remember_me is True
    if credentials.remember_me:
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="lax"
        )
    
    # Log successful login
    AuditService.log_auth_event(
        "USER_LOGIN",
        user.id,
        request,
        {"email": user.email}
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        user=UserResponse.from_orm(user)
    )


@router.post("/logout")
async def logout(
    response: Response,
    current_user: User = Depends(get_current_active_user),
    request: Request = None
):
    """Logout user and invalidate tokens"""
    
    # Clear refresh token cookie
    response.delete_cookie(key="refresh_token")
    
    # Log logout
    AuditService.log_auth_event(
        "USER_LOGOUT",
        current_user.id,
        request,
        {"email": current_user.email}
    )
    
    return {"message": "Successfully logged out"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token"""
    
    try:
        # Verify refresh token
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Get user
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Generate new access token
    access_token = AuthService.create_access_token({"sub": str(user.id)})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=credentials.credentials,  # Return same refresh token
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        user=UserResponse.from_orm(user)
    )


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user profile"""
    return UserProfile.from_orm(current_user)


@router.put("/me", response_model=UserProfile)
async def update_current_user_profile(
    user_update: UserUpdate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update current user profile"""
    
    # Update user fields
    for field, value in user_update.dict(exclude_unset=True).items():
        setattr(current_user, field, value)
    
    current_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(current_user)
    
    # Log profile update
    AuditService.log_user_event(
        "PROFILE_UPDATED",
        current_user.id,
        request,
        {"updated_fields": list(user_update.dict(exclude_unset=True).keys())}
    )
    
    return UserProfile.from_orm(current_user)


@router.put("/me/settings", response_model=UserProfile)
async def update_user_settings(
    settings_update: UserSettings,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update user settings"""
    
    # Update settings
    for field, value in settings_update.dict().items():
        setattr(current_user, field, value)
    
    current_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(current_user)
    
    # Log settings update
    AuditService.log_user_event(
        "SETTINGS_UPDATED",
        current_user.id,
        request,
        {"updated_settings": list(settings_update.dict().keys())}
    )
    
    return UserProfile.from_orm(current_user)


@router.post("/change-password")
async def change_password(
    password_change: UserPasswordChange,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Change user password"""
    
    # Verify current password
    if not AuthService.verify_password(password_change.current_password, current_user.password_hash):
        AuditService.log_auth_event(
            "PASSWORD_CHANGE_FAILED",
            current_user.id,
            request,
            {"reason": "invalid_current_password"}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    current_user.password_hash = AuthService.hash_password(password_change.new_password)
    current_user.password_changed_at = datetime.utcnow()
    current_user.updated_at = datetime.utcnow()
    db.commit()
    
    # Log password change
    AuditService.log_auth_event(
        "PASSWORD_CHANGED",
        current_user.id,
        request,
        {"email": current_user.email}
    )
    
    return {"message": "Password changed successfully"}


@router.post("/forgot-password")
async def forgot_password(
    request_data: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Request password reset"""
    
    user = db.query(User).filter(User.email == request_data.email).first()
    
    if user:
        # Generate reset token (implementation depends on email service)
        reset_token = AuthService.create_password_reset_token(user.email)
        
        # TODO: Send email with reset token
        # EmailService.send_password_reset_email(user.email, reset_token)
        
        # Log password reset request
        AuditService.log_auth_event(
            "PASSWORD_RESET_REQUESTED",
            user.id,
            request,
            {"email": user.email}
        )
    
    # Always return success to prevent email enumeration
    return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/reset-password")
async def reset_password(
    reset_data: PasswordReset,
    request: Request,
    db: Session = Depends(get_db)
):
    """Reset password with token"""
    
    # Verify reset token
    email = AuthService.verify_password_reset_token(reset_data.token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Find user
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update password
    user.password_hash = AuthService.hash_password(reset_data.new_password)
    user.password_changed_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()
    db.commit()
    
    # Log password reset
    AuditService.log_auth_event(
        "PASSWORD_RESET",
        user.id,
        request,
        {"email": user.email}
    )
    
    return {"message": "Password reset successfully"}


@router.post("/verify-email")
async def verify_email(
    verification_data: EmailVerification,
    request: Request,
    db: Session = Depends(get_db)
):
    """Verify email address"""
    
    # Verify email token
    email = AuthService.verify_email_token(verification_data.token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )
    
    # Find and verify user
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.email_verified:
        return {"message": "Email already verified"}
    
    # Mark email as verified
    user.email_verified = True
    user.updated_at = datetime.utcnow()
    db.commit()
    
    # Log email verification
    AuditService.log_auth_event(
        "EMAIL_VERIFIED",
        user.id,
        request,
        {"email": user.email}
    )
    
    return {"message": "Email verified successfully"}


@router.post("/resend-verification")
async def resend_verification_email(
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Resend email verification"""
    
    if current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified"
        )
    
    # Generate verification token
    verification_token = AuthService.create_email_verification_token(current_user.email)
    
    # TODO: Send verification email
    # EmailService.send_verification_email(current_user.email, verification_token)
    
    # Log verification resend
    AuditService.log_auth_event(
        "VERIFICATION_RESENT",
        current_user.id,
        request,
        {"email": current_user.email}
    )
    
    return {"message": "Verification email sent"}
