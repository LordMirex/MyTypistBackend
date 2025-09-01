"""
Visit tracking model for analytics
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class Visit(Base):
    """Document visit tracking model"""
    __tablename__ = "visits"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    
    # Visitor information
    visitor_id = Column(String(100), nullable=True)  # Anonymous visitor ID
    visitor_ip = Column(String(45), nullable=True)
    visitor_user_agent = Column(Text, nullable=True)
    visitor_country = Column(String(100), nullable=True)
    visitor_city = Column(String(100), nullable=True)
    
    # Session information
    session_id = Column(String(100), nullable=True)
    referrer = Column(Text, nullable=True)
    utm_source = Column(String(100), nullable=True)
    utm_medium = Column(String(100), nullable=True)
    utm_campaign = Column(String(100), nullable=True)
    
    # Visit details
    visit_type = Column(String(20), nullable=False, default="view")  # view, download, share
    page_title = Column(String(255), nullable=True)
    duration = Column(Integer, nullable=True)  # seconds
    bounce = Column(Boolean, nullable=False, default=False)
    
    # Device information
    device_type = Column(String(20), nullable=True)  # desktop, mobile, tablet
    browser = Column(String(50), nullable=True)
    os = Column(String(50), nullable=True)
    screen_resolution = Column(String(20), nullable=True)  # "1920x1080"
    
    # Geolocation (if permitted)
    latitude = Column(String(20), nullable=True)
    longitude = Column(String(20), nullable=True)
    accuracy = Column(Integer, nullable=True)  # meters
    
    # Privacy compliance
    tracking_consent = Column(Boolean, nullable=False, default=False)
    analytics_consent = Column(Boolean, nullable=False, default=False)
    gdpr_compliant = Column(Boolean, nullable=False, default=True)
    
    # Additional metadata
    visit_metadata = Column(JSON, nullable=True)  # Additional tracking data
    
    # Timestamps
    visited_at = Column(DateTime, server_default=func.now(), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    # Relationships
    document = relationship("Document", back_populates="visits")
    
    def __repr__(self):
        return f"<Visit(id={self.id}, document_id={self.document_id}, type='{self.visit_type}')>"
    
    @property
    def is_valid_analytics(self):
        """Check if visit can be used for analytics"""
        return getattr(self, 'gdpr_compliant', False) and getattr(self, 'analytics_consent', False)
