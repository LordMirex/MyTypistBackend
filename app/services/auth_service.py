"""
Authentication and authorization service
"""

import os
from jose import jwt
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from fastapi import Request
from sqlalchemy.orm import Session

from config import settings
from app.models.user import User, UserRole, UserStatus
from app.schemas.user import UserCreate
from app.services.audit_service import AuditService

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Authentication and authorization service"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def create_access_token(data: Dict[Any, Any]) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(hours=settings.JWT_ACCESS_TOKEN_EXPIRE_HOURS)
        to_encode.update({"exp": expire, "type": "access"})
        
        encoded_jwt = jwt.encode(
            to_encode, 
            settings.JWT_SECRET_KEY, 
            algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: Dict[Any, Any]) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Optional[Dict[Any, Any]]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            
            # Verify token type
            if payload.get("type") != token_type:
                return None
                
            return payload
            
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None
    
    @staticmethod
    def create_user(db: Session, user_data: UserCreate, request: Request) -> User:
        """Create a new user account"""
        
        # Hash password
        hashed_password = AuthService.hash_password(user_data.password)
        
        # Create user
        db_user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=hashed_password,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            phone=user_data.phone,
            company=user_data.company,
            job_title=user_data.job_title,
            bio=user_data.bio,
            role=user_data.role,
            gdpr_consent=user_data.gdpr_consent,
            gdpr_consent_date=datetime.utcnow() if user_data.gdpr_consent else None,
            marketing_consent=user_data.marketing_consent,
            created_at=datetime.utcnow()
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        return db_user
    
    @staticmethod
    def create_password_reset_token(email: str) -> str:
        """Create password reset token"""
        data = {
            "email": email,
            "type": "password_reset",
            "exp": datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
        }
        
        token = jwt.encode(
            data,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        return token
    
    @staticmethod
    def verify_password_reset_token(token: str) -> Optional[str]:
        """Verify password reset token and return email"""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            
            if payload.get("type") != "password_reset":
                return None
                
            return payload.get("email")
            
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None
    
    @staticmethod
    def create_email_verification_token(email: str) -> str:
        """Create email verification token"""
        data = {
            "email": email,
            "type": "email_verification",
            "exp": datetime.utcnow() + timedelta(days=7)  # 7 days expiry
        }
        
        token = jwt.encode(
            data,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        return token
    
    @staticmethod
    def verify_email_token(token: str) -> Optional[str]:
        """Verify email verification token and return email"""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            
            if payload.get("type") != "email_verification":
                return None
                
            return payload.get("email")
            
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None
    
    @staticmethod
    def check_user_permissions(user: User, resource: str, action: str) -> bool:
        """Check if user has permission to perform action on resource"""
        
        # Admin has all permissions
        if user.role == UserRole.ADMIN:
            return True
        
        # Define permission matrix
        permissions = {
            UserRole.STANDARD: {
                "documents": ["create", "read", "update", "delete"],
                "templates": ["read", "use"],
                "signatures": ["create", "read"],
                "payments": ["create", "read"],
                "analytics": ["read"]
            },
            UserRole.GUEST: {
                "documents": ["read"],
                "templates": ["read"],
                "signatures": ["read"],
                "payments": [],
                "analytics": []
            }
        }
        
        user_permissions = permissions.get(user.role, {})
        resource_permissions = user_permissions.get(resource, [])
        
        return action in resource_permissions
    
    @staticmethod
    def generate_api_key(user_id: int) -> str:
        """Generate API key for user"""
        # Create a secure random API key
        api_key = secrets.token_urlsafe(32)
        
        # In production, you would store this in database with user_id mapping
        # For now, we'll encode user_id in the key for simplicity
        data = {
            "user_id": user_id,
            "type": "api_key",
            "created_at": datetime.utcnow().isoformat()
        }
        
        encoded_key = jwt.encode(
            data,
            settings.JWT_SECRET_KEY + api_key,
            algorithm=settings.JWT_ALGORITHM
        )
        
        return f"mtk_{api_key}_{encoded_key}"
    
    @staticmethod
    def verify_api_key(api_key: str) -> Optional[int]:
        """Verify API key and return user_id"""
        try:
            if not api_key.startswith("mtk_"):
                return None
            
            parts = api_key[4:].split("_", 1)
            if len(parts) != 2:
                return None
            
            key_part, encoded_part = parts
            
            payload = jwt.decode(
                encoded_part,
                settings.JWT_SECRET_KEY + key_part,
                algorithms=[settings.JWT_ALGORITHM]
            )
            
            if payload.get("type") != "api_key":
                return None
            
            return payload.get("user_id")
            
        except jwt.JWTError:
            return None
    
    @staticmethod
    def is_secure_password(password: str) -> bool:
        """Check if password meets security requirements"""
        if len(password) < 8:
            return False
        
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
        
        return all([has_upper, has_lower, has_digit, has_special])
    
    @staticmethod
    def check_rate_limit(user_id: int, action: str, limit: int, window: int) -> bool:
        """Check if user action is within rate limit"""
        # This would typically use Redis for rate limiting
        # For now, we'll return True (no rate limiting)
        # In production, implement proper rate limiting logic
        return True
    
    @staticmethod
    def log_security_event(event_type: str, user_id: Optional[int], request: Request, details: Dict[str, Any]):
        """Log security-related events"""
        AuditService.log_security_event(event_type, user_id, request, details)
    
    @staticmethod
    def revoke_user_tokens(user_id: int):
        """Revoke all tokens for a user (logout from all devices)"""
        # In production, you would maintain a blacklist of tokens
        # or use a different approach like token versioning
        # For now, this is a placeholder
        pass
    
    @staticmethod
    def cleanup_expired_tokens():
        """Cleanup expired tokens from blacklist/cache"""
        # Maintenance task to clean up expired tokens
        # Would be called by a background task
        pass
