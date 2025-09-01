"""
Audit logging model for compliance and security
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON, Enum, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from database import Base


class AuditEventType(str, enum.Enum):
    """Audit event type enumeration"""
    # Authentication events
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET = "password_reset"
    REGISTRATION_SUCCESSFUL = "registration_successful"
    REGISTRATION_FAILED = "registration_failed"
    
    # User management events
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_SUSPENDED = "user_suspended"
    USER_ACTIVATED = "user_activated"
    
    # Document events
    DOCUMENT_CREATED = "document_created"
    DOCUMENT_VIEWED = "document_viewed"
    DOCUMENT_UPDATED = "document_updated"
    DOCUMENT_DELETED = "document_deleted"
    DOCUMENT_SHARED = "document_shared"
    DOCUMENT_DOWNLOADED = "document_downloaded"
    
    # Template events
    TEMPLATE_CREATED = "template_created"
    TEMPLATE_UPDATED = "template_updated"
    TEMPLATE_DELETED = "template_deleted"
    TEMPLATE_USED = "template_used"
    
    # Signature events
    SIGNATURE_ADDED = "signature_added"
    SIGNATURE_VERIFIED = "signature_verified"
    SIGNATURE_REJECTED = "signature_rejected"
    
    # Payment events
    PAYMENT_INITIATED = "payment_initiated"
    PAYMENT_COMPLETED = "payment_completed"
    PAYMENT_FAILED = "payment_failed"
    PAYMENT_REFUNDED = "payment_refunded"
    
    # Subscription events
    SUBSCRIPTION_CREATED = "subscription_created"
    SUBSCRIPTION_RENEWED = "subscription_renewed"
    SUBSCRIPTION_CANCELLED = "subscription_cancelled"
    SUBSCRIPTION_EXPIRED = "subscription_expired"
    
    # Security events
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DATA_BREACH_ATTEMPT = "data_breach_attempt"
    
    # System events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    SYSTEM_ERROR = "system_error"
    BACKUP_CREATED = "backup_created"
    UNHANDLED_EXCEPTION = "unhandled_exception"
    SLOW_REQUEST = "slow_request"
    
    # Compliance events
    GDPR_REQUEST = "gdpr_request"
    DATA_EXPORT = "data_export"
    DATA_DELETION = "data_deletion"
    CONSENT_GIVEN = "consent_given"
    CONSENT_WITHDRAWN = "consent_withdrawn"


class AuditLevel(str, enum.Enum):
    """Audit event level enumeration"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditLog(Base):
    """Audit log model for compliance and security tracking"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Event information
    event_type = Column(Enum(AuditEventType), nullable=False, index=True)
    event_level = Column(Enum(AuditLevel), nullable=False, default=AuditLevel.INFO)
    event_message = Column(Text, nullable=False)
    event_details = Column(JSON, nullable=True)  # Additional event data
    
    # User and session information
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(String(100), nullable=True)
    request_id = Column(String(100), nullable=True)
    
    # Request information
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    request_method = Column(String(10), nullable=True)
    request_path = Column(String(500), nullable=True)
    request_params = Column(JSON, nullable=True)
    response_status = Column(Integer, nullable=True)
    
    # Resource information
    resource_type = Column(String(50), nullable=True)  # document, template, user, etc.
    resource_id = Column(String(100), nullable=True)
    resource_name = Column(String(255), nullable=True)
    
    # Geographic information
    country = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    latitude = Column(String(20), nullable=True)
    longitude = Column(String(20), nullable=True)
    
    # Compliance and security
    gdpr_relevant = Column(Boolean, nullable=False, default=False)
    pii_accessed = Column(Boolean, nullable=False, default=False)
    sensitive_operation = Column(Boolean, nullable=False, default=False)
    requires_retention = Column(Boolean, nullable=False, default=True)
    
    # Risk assessment
    risk_score = Column(Integer, nullable=False, default=0)  # 0-100
    anomaly_detected = Column(Boolean, nullable=False, default=False)
    automated_response = Column(String(100), nullable=True)  # block, flag, alert
    
    # Processing information
    processing_time = Column(Float, nullable=True)  # seconds
    error_code = Column(String(50), nullable=True)
    stack_trace = Column(Text, nullable=True)
    
    # Metadata
    environment = Column(String(20), nullable=False, default="production")
    service_version = Column(String(20), nullable=True)
    correlation_id = Column(String(100), nullable=True)  # For tracing related events
    
    # Timestamps
    timestamp = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, event='{self.event_type}', user_id={self.user_id})>"
    
    @property
    def is_security_event(self):
        """Check if this is a security-related event"""
        security_events = [
            AuditEventType.LOGIN_FAILED,
            AuditEventType.SUSPICIOUS_ACTIVITY,
            AuditEventType.RATE_LIMIT_EXCEEDED,
            AuditEventType.UNAUTHORIZED_ACCESS,
            AuditEventType.DATA_BREACH_ATTEMPT
        ]
        return getattr(self, 'event_type', None) in security_events
    
    @property
    def is_gdpr_relevant(self):
        """Check if this event is relevant for GDPR compliance"""
        return getattr(self, 'gdpr_relevant', False) or getattr(self, 'pii_accessed', False)
    
    @property
    def requires_alert(self):
        """Check if this event requires immediate attention"""
        return (
            getattr(self, 'event_level', None) in [AuditLevel.ERROR, AuditLevel.CRITICAL] or
            getattr(self, 'anomaly_detected', False) or
            getattr(self, 'risk_score', 0) > 80
        )
