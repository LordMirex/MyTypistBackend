"""
Digital signature routes
"""

import base64
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from config import settings
from app.models.signature import Signature
from app.models.document import Document
from app.models.user import User
from app.schemas.signature import (
    SignatureCreate, SignatureUpdate, SignatureResponse,
    SignatureVerify, SignatureRequest, SignatureRequestResponse,
    SignatureCanvas, SignatureValidation, SignatureBatch, SignatureStats
)
from app.services.signature_service import SignatureService
from app.services.audit_service import AuditService
from app.utils.security import get_current_active_user, get_current_user

router = APIRouter()


@router.post("/", response_model=SignatureResponse, status_code=status.HTTP_201_CREATED)
async def create_signature(
    signature_data: SignatureCreate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Add signature to document"""
    
    # Verify document exists and user has access
    document = db.query(Document).filter(
        Document.id == signature_data.document_id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Check if user owns document or has signing permission
    if document.user_id != current_user.id:
        # TODO: Check if user is authorized to sign this document
        # This would involve checking signature requests or permissions
        pass
    
    # Validate consent
    if not signature_data.consent_given:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Signature consent is required"
        )
    
    # Create signature
    signature = SignatureService.create_signature(
        db, signature_data, current_user, request
    )
    
    # Update document signature count
    document.signature_count += 1
    db.commit()
    
    # Log signature creation
    AuditService.log_signature_event(
        "SIGNATURE_ADDED",
        current_user.id,
        request,
        {
            "signature_id": signature.id,
            "document_id": document.id,
            "signer_name": signature.signer_name
        }
    )
    
    return SignatureResponse.from_orm(signature)


@router.get("/", response_model=List[SignatureResponse])
async def list_signatures(
    document_id: Optional[int] = None,
    page: int = 1,
    per_page: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List signatures with optional document filter"""
    
    query = db.query(Signature)
    
    if document_id:
        # Verify user has access to document
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.user_id == current_user.id
        ).first()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        query = query.filter(Signature.document_id == document_id)
    else:
        # Only show signatures for user's documents
        query = query.join(Document).filter(Document.user_id == current_user.id)
    
    signatures = query.order_by(desc(Signature.signed_at)).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    
    return [SignatureResponse.from_orm(sig) for sig in signatures]


@router.get("/{signature_id}", response_model=SignatureResponse)
async def get_signature(
    signature_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get signature by ID"""
    
    signature = db.query(Signature).join(Document).filter(
        Signature.id == signature_id,
        Document.user_id == current_user.id
    ).first()
    
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signature not found"
        )
    
    return SignatureResponse.from_orm(signature)


@router.put("/{signature_id}", response_model=SignatureResponse)
async def update_signature(
    signature_id: int,
    signature_update: SignatureUpdate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update signature"""
    
    signature = db.query(Signature).join(Document).filter(
        Signature.id == signature_id,
        Document.user_id == current_user.id
    ).first()
    
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signature not found"
        )
    
    # Update signature
    updated_signature = SignatureService.update_signature(
        db, signature, signature_update
    )
    
    # Log signature update
    AuditService.log_signature_event(
        "SIGNATURE_UPDATED",
        current_user.id,
        request,
        {
            "signature_id": signature.id,
            "document_id": signature.document_id,
            "updated_fields": list(signature_update.dict(exclude_unset=True).keys())
        }
    )
    
    return SignatureResponse.from_orm(updated_signature)


@router.delete("/{signature_id}")
async def delete_signature(
    signature_id: int,
    reason: Optional[str] = None,
    request: Request = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete/reject signature"""
    
    signature = db.query(Signature).join(Document).filter(
        Signature.id == signature_id,
        Document.user_id == current_user.id
    ).first()
    
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signature not found"
        )
    
    # Mark signature as rejected
    signature.rejected = True
    signature.rejection_reason = reason
    signature.is_active = False
    db.commit()
    
    # Update document signature count
    document = signature.document
    document.signature_count = max(0, document.signature_count - 1)
    db.commit()
    
    # Log signature rejection
    AuditService.log_signature_event(
        "SIGNATURE_REJECTED",
        current_user.id,
        request,
        {
            "signature_id": signature.id,
            "document_id": signature.document_id,
            "reason": reason
        }
    )
    
    return {"message": "Signature rejected successfully"}


@router.post("/verify", response_model=SignatureValidation)
async def verify_signature(
    verify_data: SignatureVerify,
    request: Request,
    db: Session = Depends(get_db)
):
    """Verify signature authenticity"""
    
    # Find signature by verification token
    signature = db.query(Signature).filter(
        Signature.verification_token == verify_data.verification_token
    ).first()
    
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signature not found"
        )
    
    # Perform verification
    validation_result = SignatureService.verify_signature(
        signature, verify_data.verification_code
    )
    
    if validation_result["is_valid"]:
        signature.is_verified = True
        signature.verification_method = "token"
        db.commit()
        
        # Log signature verification
        AuditService.log_signature_event(
            "SIGNATURE_VERIFIED",
            None,
            request,
            {
                "signature_id": signature.id,
                "document_id": signature.document_id,
                "verification_method": "token"
            }
        )
    
    return SignatureValidation(**validation_result)


@router.post("/request", response_model=SignatureRequestResponse, status_code=status.HTTP_201_CREATED)
async def request_signature(
    request_data: SignatureRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Request signature from external user"""
    
    # Verify document exists and user has access
    document = db.query(Document).filter(
        Document.id == request_data.document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Create signature request
    signature_request = SignatureService.create_signature_request(
        db, request_data, current_user.id
    )
    
    # Log signature request
    AuditService.log_signature_event(
        "SIGNATURE_REQUESTED",
        current_user.id,
        request,
        {
            "document_id": document.id,
            "signer_email": request_data.signer_email,
            "signer_name": request_data.signer_name
        }
    )
    
    return signature_request


@router.post("/batch-request", status_code=status.HTTP_201_CREATED)
async def batch_request_signatures(
    batch_data: SignatureBatch,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Request signatures from multiple users"""
    
    # Verify document exists and user has access
    document = db.query(Document).filter(
        Document.id == batch_data.document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Create batch signature requests
    requests = SignatureService.create_batch_signature_requests(
        db, batch_data, current_user.id
    )
    
    # Log batch signature request
    AuditService.log_signature_event(
        "BATCH_SIGNATURE_REQUESTED",
        current_user.id,
        request,
        {
            "document_id": document.id,
            "signer_count": len(batch_data.signers)
        }
    )
    
    return {
        "message": f"Signature requests sent to {len(batch_data.signers)} recipients",
        "requests": requests
    }


@router.get("/canvas-config", response_model=SignatureCanvas)
async def get_signature_canvas_config():
    """Get signature canvas configuration"""
    
    return SignatureCanvas(
        width=400,
        height=200,
        pen_color="#000000",
        pen_width=2,
        background_color="#FFFFFF"
    )


@router.get("/stats", response_model=SignatureStats)
async def get_signature_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get signature statistics for user's documents"""
    
    stats = SignatureService.get_user_signature_stats(db, current_user.id)
    return stats


@router.get("/external/{request_token}")
async def access_signature_request(
    request_token: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Access signature request from external link"""
    
    # Find signature request by token
    signature_request = SignatureService.get_signature_request_by_token(
        db, request_token
    )
    
    if not signature_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signature request not found or expired"
        )
    
    # Log external access
    AuditService.log_signature_event(
        "SIGNATURE_REQUEST_ACCESSED",
        None,
        request,
        {
            "request_token": request_token,
            "document_id": signature_request["document_id"]
        }
    )
    
    return signature_request


@router.post("/external/{request_token}/sign", response_model=SignatureResponse, status_code=status.HTTP_201_CREATED)
async def sign_external_document(
    request_token: str,
    signature_data: SignatureCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Sign document from external signature request"""
    
    # Validate signature request token
    signature_request = SignatureService.get_signature_request_by_token(
        db, request_token
    )
    
    if not signature_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signature request not found or expired"
        )
    
    # Validate document ID matches
    if signature_data.document_id != signature_request["document_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document ID mismatch"
        )
    
    # Create signature from external request
    signature = SignatureService.create_external_signature(
        db, signature_data, signature_request, request
    )
    
    # Log external signature
    AuditService.log_signature_event(
        "EXTERNAL_SIGNATURE_ADDED",
        None,
        request,
        {
            "signature_id": signature.id,
            "document_id": signature.document_id,
            "request_token": request_token,
            "signer_email": signature.signer_email
        }
    )
    
    return SignatureResponse.from_orm(signature)


@router.get("/document/{document_id}/status")
async def get_document_signature_status(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get signature status for a document"""
    
    # Verify document access
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Get signature status
    status_info = SignatureService.get_document_signature_status(db, document_id)
    
    return {
        "document_id": document_id,
        "requires_signature": document.requires_signature,
        "required_signature_count": document.required_signature_count,
        "current_signature_count": document.signature_count,
        "is_fully_signed": document.signature_count >= document.required_signature_count,
        "signatures": status_info["signatures"],
        "pending_requests": status_info["pending_requests"]
    }
