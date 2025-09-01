"""
Analytics and tracking service
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from fastapi import Request

from app.models.visit import Visit
from app.models.document import Document
from app.models.template import Template
from app.models.user import User


class AnalyticsService:
    """Analytics and tracking service"""
    
    @staticmethod
    def track_visit(
        db: Session,
        document_id: int,
        visit_type: str,
        request: Optional[Request] = None
    ) -> Visit:
        """Track a document visit"""
        
        # Extract visitor information
        visitor_ip = None
        visitor_user_agent = None
        visitor_country = None
        visitor_city = None
        device_type = None
        browser = None
        os = None
        
        if request:
            visitor_ip = AnalyticsService._get_client_ip(request)
            visitor_user_agent = request.headers.get("user-agent")
            
            # Parse user agent for device info
            device_info = AnalyticsService._parse_user_agent(visitor_user_agent)
            device_type = device_info.get("device_type")
            browser = device_info.get("browser")
            os = device_info.get("os")
            
            # Get location from IP (would integrate with GeoIP service)
            location = AnalyticsService._get_location_from_ip(visitor_ip)
            visitor_country = location.get("country")
            visitor_city = location.get("city")
        
        # Create visit record
        visit = Visit(
            document_id=document_id,
            visitor_ip=visitor_ip,
            visitor_user_agent=visitor_user_agent,
            visitor_country=visitor_country,
            visitor_city=visitor_city,
            visit_type=visit_type,
            device_type=device_type,
            browser=browser,
            os=os,
            tracking_consent=True,  # Would be determined by cookie/consent
            analytics_consent=True,
            gdpr_compliant=True
        )
        
        db.add(visit)
        db.commit()
        db.refresh(visit)
        
        return visit
    
    @staticmethod
    def process_visit_analytics(visits: List[Visit]) -> Dict[str, Any]:
        """Process visit data into analytics insights"""
        
        if not visits:
            return {
                "total_visits": 0,
                "unique_visitors": 0,
                "visit_types": {},
                "device_breakdown": {},
                "browser_breakdown": {},
                "country_breakdown": {},
                "daily_visits": [],
                "bounce_rate": 0
            }
        
        # Basic metrics
        total_visits = len(visits)
        unique_visitors = len(set(visit.visitor_ip for visit in visits if visit.visitor_ip))
        
        # Visit types
        visit_types = {}
        for visit in visits:
            visit_types[visit.visit_type] = visit_types.get(visit.visit_type, 0) + 1
        
        # Device breakdown
        device_breakdown = {}
        for visit in visits:
            if visit.device_type:
                device_breakdown[visit.device_type] = device_breakdown.get(visit.device_type, 0) + 1
        
        # Browser breakdown
        browser_breakdown = {}
        for visit in visits:
            if visit.browser:
                browser_breakdown[visit.browser] = browser_breakdown.get(visit.browser, 0) + 1
        
        # Country breakdown
        country_breakdown = {}
        for visit in visits:
            if visit.visitor_country:
                country_breakdown[visit.visitor_country] = country_breakdown.get(visit.visitor_country, 0) + 1
        
        # Daily visits
        daily_visits = {}
        for visit in visits:
            date_key = visit.visited_at.date().isoformat()
            daily_visits[date_key] = daily_visits.get(date_key, 0) + 1
        
        daily_visits_list = [
            {"date": date, "visits": count}
            for date, count in sorted(daily_visits.items())
        ]
        
        # Calculate bounce rate (visits with duration < 30 seconds)
        bounced_visits = len([visit for visit in visits if visit.bounce])
        bounce_rate = (bounced_visits / total_visits * 100) if total_visits > 0 else 0
        
        return {
            "total_visits": total_visits,
            "unique_visitors": unique_visitors,
            "visit_types": visit_types,
            "device_breakdown": device_breakdown,
            "browser_breakdown": browser_breakdown,
            "country_breakdown": country_breakdown,
            "daily_visits": daily_visits_list,
            "bounce_rate": bounce_rate
        }
    
    @staticmethod
    def get_dashboard_analytics(db: Session, user_id: int) -> Dict[str, Any]:
        """Get comprehensive analytics dashboard data"""
        
        # Time periods
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        last_7_days = today - timedelta(days=7)
        last_30_days = today - timedelta(days=30)
        
        # Document statistics
        user_documents = db.query(Document).filter(Document.user_id == user_id)
        
        total_documents = user_documents.count()
        documents_today = user_documents.filter(
            func.date(Document.created_at) == today
        ).count()
        documents_this_week = user_documents.filter(
            Document.created_at >= last_7_days
        ).count()
        
        # Visit statistics
        user_visits = db.query(Visit).join(Document).filter(Document.user_id == user_id)
        
        total_visits = user_visits.count()
        visits_today = user_visits.filter(
            func.date(Visit.visited_at) == today
        ).count()
        visits_yesterday = user_visits.filter(
            func.date(Visit.visited_at) == yesterday
        ).count()
        
        # Top documents
        top_documents = db.query(
            Document.id,
            Document.title,
            func.count(Visit.id).label('visit_count')
        ).join(
            Visit, Visit.document_id == Document.id
        ).filter(
            Document.user_id == user_id,
            Visit.visited_at >= last_30_days
        ).group_by(
            Document.id, Document.title
        ).order_by(
            desc('visit_count')
        ).limit(5).all()
        
        # Template usage
        template_usage = db.query(
            Template.id,
            Template.name,
            func.count(Document.id).label('usage_count')
        ).join(
            Document, Document.template_id == Template.id
        ).filter(
            Document.user_id == user_id,
            Document.created_at >= last_30_days
        ).group_by(
            Template.id, Template.name
        ).order_by(
            desc('usage_count')
        ).limit(5).all()
        
        return {
            "overview": {
                "total_documents": total_documents,
                "total_visits": total_visits,
                "documents_today": documents_today,
                "visits_today": visits_today,
                "documents_this_week": documents_this_week,
                "visit_growth": AnalyticsService._calculate_growth(visits_today, visits_yesterday)
            },
            "top_documents": [
                {
                    "id": doc.id,
                    "title": doc.title,
                    "visits": doc.visit_count
                }
                for doc in top_documents
            ],
            "template_usage": [
                {
                    "id": template.id,
                    "name": template.name,
                    "usage_count": template.usage_count
                }
                for template in template_usage
            ]
        }
    
    @staticmethod
    def export_analytics_data(
        db: Session,
        user_id: int,
        document_id: Optional[int],
        days: int,
        format: str
    ) -> Dict[str, Any]:
        """Export analytics data in specified format"""
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Build query
        query = db.query(Visit).join(Document).filter(
            Document.user_id == user_id,
            Visit.visited_at >= start_date
        )
        
        if document_id:
            query = query.filter(Visit.document_id == document_id)
        
        visits = query.all()
        
        if format == "csv":
            # Prepare CSV data
            csv_data = []
            for visit in visits:
                csv_data.append({
                    "visit_id": visit.id,
                    "document_id": visit.document_id,
                    "visit_type": visit.visit_type,
                    "visitor_country": visit.visitor_country,
                    "visitor_city": visit.visitor_city,
                    "device_type": visit.device_type,
                    "browser": visit.browser,
                    "os": visit.os,
                    "visited_at": visit.visited_at.isoformat()
                })
            
            return {
                "format": "csv",
                "data": csv_data,
                "total_records": len(csv_data)
            }
        
        else:  # JSON format
            json_data = []
            for visit in visits:
                json_data.append({
                    "visit_id": visit.id,
                    "document_id": visit.document_id,
                    "visit_type": visit.visit_type,
                    "visitor_info": {
                        "country": visit.visitor_country,
                        "city": visit.visitor_city,
                        "device_type": visit.device_type,
                        "browser": visit.browser,
                        "os": visit.os
                    },
                    "visited_at": visit.visited_at.isoformat(),
                    "metadata": visit.metadata
                })
            
            return {
                "format": "json",
                "export_date": datetime.utcnow().isoformat(),
                "period_days": days,
                "total_records": len(json_data),
                "visits": json_data
            }
    
    @staticmethod
    def anonymize_user_analytics(
        db: Session,
        user_id: int,
        document_id: Optional[int] = None
    ) -> int:
        """Anonymize analytics data for GDPR compliance"""
        
        query = db.query(Visit).join(Document).filter(Document.user_id == user_id)
        
        if document_id:
            query = query.filter(Visit.document_id == document_id)
        
        visits = query.all()
        anonymized_count = 0
        
        for visit in visits:
            # Anonymize IP address
            if visit.visitor_ip:
                visit.visitor_ip = "XXX.XXX.XXX.XXX"
            
            # Remove precise location data
            visit.visitor_city = None
            visit.latitude = None
            visit.longitude = None
            
            # Anonymize user agent
            if visit.visitor_user_agent:
                visit.visitor_user_agent = "[ANONYMIZED]"
            
            # Clear metadata that might contain PII
            if visit.metadata:
                visit.metadata = {"anonymized": True}
            
            anonymized_count += 1
        
        db.commit()
        return anonymized_count
    
    @staticmethod
    def _get_client_ip(request: Request) -> Optional[str]:
        """Extract client IP from request"""
        
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        
        return request.client.host if request.client else None
    
    @staticmethod
    def _parse_user_agent(user_agent: Optional[str]) -> Dict[str, str]:
        """Parse user agent string for device information"""
        
        if not user_agent:
            return {"device_type": "unknown", "browser": "unknown", "os": "unknown"}
        
        try:
            from user_agents import parse
            
            parsed = parse(user_agent)
            
            return {
                "device_type": "mobile" if parsed.is_mobile else "tablet" if parsed.is_tablet else "desktop",
                "browser": f"{parsed.browser.family} {parsed.browser.version_string}",
                "os": f"{parsed.os.family} {parsed.os.version_string}"
            }
        except Exception:
            return {"device_type": "unknown", "browser": "unknown", "os": "unknown"}
    
    @staticmethod
    def _get_location_from_ip(ip_address: Optional[str]) -> Dict[str, Optional[str]]:
        """Get location information from IP address"""
        
        # In production, this would integrate with a GeoIP service like MaxMind
        # For now, return mock data or None
        
        if not ip_address or ip_address == "127.0.0.1":
            return {"country": None, "city": None}
        
        # Mock location data for demonstration
        # In production, use actual GeoIP lookup
        return {"country": "Nigeria", "city": "Lagos"}
    
    @staticmethod
    def _calculate_growth(current: int, previous: int) -> float:
        """Calculate growth percentage"""
        
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        
        return ((current - previous) / previous) * 100
