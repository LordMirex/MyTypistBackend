"""
Digital signature service for document signing
"""

import base64
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from fastapi import Request

from app.models.signature import Signature
from app.models.document import Document
from app.models.user import User
from app.schemas.signature import (
    SignatureCreate, SignatureUpdate, SignatureRequest,
    SignatureStats, SignatureValidation
)
from app.services.encryption_service import EncryptionService


class SignatureService:
    """Digital signature management service"""
    
    @staticmethod
    def create_signature(
        db: Session,
        signature_data: SignatureCreate,
        current_user: User,
        request: Request
    ) -> Signature:
        """Create a new signature"""
        
        # Decode and validate signature data
        try:
            # Remove data URL prefix if present
            signature_base64 = signature_data.signature_data
            if signature_base64.startswith('data:image/'):
                signature_base64 = signature_base64.split(',', 1)[1]
            
            # Decode signature
            signature_binary = base64.b64decode(signature_base64)
            
            # Calculate signature hash
            signature_hash = hashlib.sha256(signature_binary).hexdigest()
            
        except Exception as e:
            raise ValueError(f"Invalid signature data: {str(e)}")
        
        # Get document hash at time of signing
        document = db.query(Document).filter(
            Document.id == signature_data.document_id
        ).first()
        
        document_hash = None
        if document and document.file_path:
            document_hash = EncryptionService.calculate_file_hash(document.file_path)
        
        # Create signature record
        signature = Signature(
            document_id=signature_data.document_id,
            signer_name=signature_data.signer_name,
            signer_email=signature_data.signer_email,
            signer_phone=signature_data.signer_phone,
            signer_ip=SignatureService._get_client_ip(request),
            signer_user_agent=request.headers.get("user-agent"),
            signature_data=signature_binary,
            signature_base64=signature_base64,
            signature_type=signature_data.signature_type,
            page_number=signature_data.page_number,
            x_position=signature_data.x_position,
            y_position=signature_data.y_position,
            width=signature_data.width,
            height=signature_data.height,
            consent_given=signature_data.consent_given,
            consent_text=signature_data.consent_text,
            consent_timestamp=datetime.utcnow() if signature_data.consent_given else None,
            signature_hash=signature_hash,
            document_hash_at_signing=document_hash,
            signing_session_id=str(uuid.uuid4()),
            signing_device_info=SignatureService._get_device_info(request),
            legal_notice_shown=True
        )
        
        db.add(signature)
        db.commit()
        db.refresh(signature)
        
        return signature
    
    @staticmethod
    def update_signature(
        db: Session,
        signature: Signature,
        signature_update: SignatureUpdate
    ) -> Signature:
        """Update signature details"""
        
        for field, value in signature_update.dict(exclude_unset=True).items():
            setattr(signature, field, value)
        
        signature.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(signature)
        
        return signature
    
    @staticmethod
    def verify_signature(
        signature: Signature,
        verification_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Verify signature authenticity"""
        
        validation_result = {
            "is_valid": True,
            "signature_hash": signature.signature_hash,
            "document_hash": signature.document_hash_at_signing,
            "signed_at": signature.signed_at,
            "signer_info": {
                "name": signature.signer_name,
                "email": signature.signer_email,
                "ip_address": signature.signer_ip
            },
            "validation_errors": []
        }
        
        # Check if signature is active
        if not signature.is_active:
            validation_result["is_valid"] = False
            validation_result["validation_errors"].append("Signature is not active")
        
        # Check if signature was rejected
        if signature.rejected:
            validation_result["is_valid"] = False
            validation_result["validation_errors"].append(
                f"Signature was rejected: {signature.rejection_reason}"
            )
        
        # Check consent
        if not signature.consent_given:
            validation_result["is_valid"] = False
            validation_result["validation_errors"].append("Signature consent not given")
        
        # Verify signature hash
        if signature.signature_data:
            calculated_hash = hashlib.sha256(signature.signature_data).hexdigest()
            if calculated_hash != signature.signature_hash:
                validation_result["is_valid"] = False
                validation_result["validation_errors"].append("Signature hash mismatch")
        
        # Check verification token if provided
        if signature.verification_token and verification_code:
            if signature.verification_expires_at and signature.verification_expires_at < datetime.utcnow():
                validation_result["is_valid"] = False
                validation_result["validation_errors"].append("Verification token expired")
            # Additional verification logic would go here
        
        return validation_result
    
    @staticmethod
    def create_signature_request(
        db: Session,
        request_data: SignatureRequest,
        user_id: int
    ) -> Dict[str, Any]:
        """Create signature request for external signer"""
        
        # Generate request token
        request_token = str(uuid.uuid4())
        
        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(days=request_data.expires_in_days)
        
        # Store request data (in production, this would be in a separate table)
        request_info = {
            "request_token": request_token,
            "document_id": request_data.document_id,
            "signer_email": request_data.signer_email,
            "signer_name": request_data.signer_name,
            "message": request_data.message,
            "expires_at": expires_at,
            "created_by": user_id,
            "status": "pending",
            "sent_at": datetime.utcnow()
        }
        
        # TODO: Send email notification to signer
        # EmailService.send_signature_request_email(
        #     request_data.signer_email,
        #     request_data.signer_name,
        #     request_token,
        #     request_data.message
        # )
        
        return request_info
    
    @staticmethod
    def create_batch_signature_requests(
        db: Session,
        batch_data,
        user_id: int
    ) -> List[Dict[str, Any]]:
        """Create multiple signature requests"""
        
        requests = []
        
        for signer in batch_data.signers:
            request_data = SignatureRequest(
                document_id=batch_data.document_id,
                signer_email=signer["email"],
                signer_name=signer["name"],
                message=batch_data.message,
                expires_in_days=batch_data.expires_in_days
            )
            
            request_info = SignatureService.create_signature_request(
                db, request_data, user_id
            )
            requests.append(request_info)
        
        return requests
    
    @staticmethod
    def get_signature_request_by_token(
        db: Session,
        request_token: str
    ) -> Optional[Dict[str, Any]]:
        """Get signature request by token"""
        
        # In production, this would query a signature_requests table
        # For now, return mock data
        
        return {
            "request_token": request_token,
            "document_id": 1,
            "signer_email": "signer@example.com",
            "signer_name": "John Doe",
            "expires_at": datetime.utcnow() + timedelta(days=7),
            "status": "pending"
        }
    
    @staticmethod
    def create_external_signature(
        db: Session,
        signature_data: SignatureCreate,
        signature_request: Dict[str, Any],
        request: Request
    ) -> Signature:
        """Create signature from external request"""
        
        # Validate signature data
        try:
            signature_base64 = signature_data.signature_data
            if signature_base64.startswith('data:image/'):
                signature_base64 = signature_base64.split(',', 1)[1]
            
            signature_binary = base64.b64decode(signature_base64)
            signature_hash = hashlib.sha256(signature_binary).hexdigest()
        except Exception as e:
            raise ValueError(f"Invalid signature data: {str(e)}")
        
        # Create signature
        signature = Signature(
            document_id=signature_data.document_id,
            signer_name=signature_request["signer_name"],
            signer_email=signature_request["signer_email"],
            signer_ip=SignatureService._get_client_ip(request),
            signer_user_agent=request.headers.get("user-agent"),
            signature_data=signature_binary,
            signature_base64=signature_base64,
            signature_type=signature_data.signature_type,
            page_number=signature_data.page_number,
            x_position=signature_data.x_position,
            y_position=signature_data.y_position,
            width=signature_data.width,
            height=signature_data.height,
            consent_given=signature_data.consent_given,
            consent_text=signature_data.consent_text,
            consent_timestamp=datetime.utcnow(),
            signature_hash=signature_hash,
            signing_session_id=str(uuid.uuid4()),
            signing_device_info=SignatureService._get_device_info(request),
            legal_notice_shown=True
        )
        
        db.add(signature)
        db.commit()
        db.refresh(signature)
        
        return signature
    
    @staticmethod
    def get_document_signature_status(db: Session, document_id: int) -> Dict[str, Any]:
        """Get comprehensive signature status for document"""
        
        signatures = db.query(Signature).filter(
            Signature.document_id == document_id,
            Signature.is_active == True
        ).all()
        
        status_info = {
            "signatures": [
                {
                    "id": sig.id,
                    "signer_name": sig.signer_name,
                    "signer_email": sig.signer_email,
                    "signed_at": sig.signed_at,
                    "is_verified": sig.is_verified,
                    "status": "completed"
                }
                for sig in signatures
            ],
            "pending_requests": []  # Would be populated from signature_requests table
        }
        
        return status_info
    
    @staticmethod
    def get_user_signature_stats(db: Session, user_id: int) -> SignatureStats:
        """Get signature statistics for user's documents"""
        
        # Get signatures for user's documents
        signatures = db.query(Signature).join(Document).filter(
            Document.user_id == user_id
        ).all()
        
        total_signatures = len(signatures)
        verified_signatures = len([sig for sig in signatures if sig.is_verified])
        pending_signatures = len([sig for sig in signatures if not sig.is_verified and sig.is_active])
        rejected_signatures = len([sig for sig in signatures if sig.rejected])
        
        # Calculate average signing time (mock data for now)
        average_signing_time = 300.0  # 5 minutes
        
        # Calculate completion rate
        completion_rate = (verified_signatures / total_signatures * 100) if total_signatures > 0 else 0
        
        return SignatureStats(
            total_signatures=total_signatures,
            verified_signatures=verified_signatures,
            pending_signatures=pending_signatures,
            rejected_signatures=rejected_signatures,
            average_signing_time=average_signing_time,
            completion_rate=completion_rate
        )
    
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
    def _get_device_info(request: Request) -> Optional[str]:
        """Extract device information from request"""
        
        import json
        from user_agents import parse
        
        user_agent_string = request.headers.get("user-agent", "")
        user_agent = parse(user_agent_string)
        
        device_info = {
            "browser": f"{user_agent.browser.family} {user_agent.browser.version_string}",
            "os": f"{user_agent.os.family} {user_agent.os.version_string}",
            "device": user_agent.device.family,
            "is_mobile": user_agent.is_mobile,
            "is_tablet": user_agent.is_tablet,
            "is_pc": user_agent.is_pc
        }
        
        return json.dumps(device_info)
