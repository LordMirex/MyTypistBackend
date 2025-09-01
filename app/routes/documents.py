"""
Document management routes
"""

import os
import uuid
import hashlib
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
import io

from database import get_db
from config import settings
from app.models.document import Document, DocumentStatus, DocumentAccess
from app.models.template import Template
from app.models.user import User
from app.schemas.document import (
    DocumentCreate, DocumentUpdate, DocumentResponse, DocumentList,
    DocumentGenerate, DocumentShare, DocumentSearch, DocumentStats,
    DocumentBatch, DocumentBatchResponse, DocumentDownload, DocumentPreview
)
from app.services.document_service import DocumentService
from app.services.audit_service import AuditService
from app.utils.security import get_current_active_user
from app.tasks.document_tasks import generate_document_task, generate_batch_documents_task

router = APIRouter()


@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    document_data: DocumentCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new document"""
    
    # Validate template if provided
    template = None
    if document_data.template_id:
        template = db.query(Template).filter(
            Template.id == document_data.template_id,
            Template.is_active == True
        ).first()
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        # Check if user has access to template
        if not template.is_public and template.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to template"
            )
    
    # Create document
    document = DocumentService.create_document(db, document_data, current_user.id)
    
    # Start background generation if template is provided
    if template and document_data.placeholder_data:
        background_tasks.add_task(
            generate_document_task.delay,
            document.id,
            document_data.placeholder_data
        )
        document.status = DocumentStatus.PROCESSING
        db.commit()
    
    # Log document creation
    AuditService.log_document_event(
        "DOCUMENT_CREATED",
        current_user.id,
        request,
        {
            "document_id": document.id,
            "template_id": document_data.template_id,
            "title": document.title
        }
    )
    
    return DocumentResponse.from_orm(document)


@router.get("/", response_model=DocumentList)
async def list_documents(
    page: int = 1,
    per_page: int = 20,
    status_filter: Optional[DocumentStatus] = None,
    template_id: Optional[int] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List user's documents with pagination and filters"""
    
    # Build query
    query = db.query(Document).filter(Document.user_id == current_user.id)
    
    # Apply filters
    if status_filter:
        query = query.filter(Document.status == status_filter)
    
    if template_id:
        query = query.filter(Document.template_id == template_id)
    
    if search:
        query = query.filter(
            or_(
                Document.title.contains(search),
                Document.description.contains(search)
            )
        )
    
    # Get total count
    total = query.count()
    
    # Apply pagination and ordering
    documents = query.order_by(desc(Document.created_at)).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    
    # Calculate pagination info
    pages = (total + per_page - 1) // per_page
    
    return DocumentList(
        documents=[DocumentResponse.from_orm(doc) for doc in documents],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages
    )


@router.get("/search", response_model=DocumentList)
async def search_documents(
    search_params: DocumentSearch = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Advanced document search"""
    
    documents, total = DocumentService.search_documents(
        db, current_user.id, search_params
    )
    
    pages = (total + search_params.per_page - 1) // search_params.per_page
    
    return DocumentList(
        documents=[DocumentResponse.from_orm(doc) for doc in documents],
        total=total,
        page=search_params.page,
        per_page=search_params.per_page,
        pages=pages
    )


@router.get("/stats", response_model=DocumentStats)
async def get_document_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get document statistics for user"""
    
    stats = DocumentService.get_user_document_stats(db, current_user.id)
    return stats


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get document by ID"""
    
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Update view count
    document.view_count += 1
    db.commit()
    
    # Log document view
    AuditService.log_document_event(
        "DOCUMENT_VIEWED",
        current_user.id,
        request,
        {
            "document_id": document.id,
            "title": document.title
        }
    )
    
    return DocumentResponse.from_orm(document)


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: int,
    document_update: DocumentUpdate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update document"""
    
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Update document
    updated_document = DocumentService.update_document(db, document, document_update)
    
    # Log document update
    AuditService.log_document_event(
        "DOCUMENT_UPDATED",
        current_user.id,
        request,
        {
            "document_id": document.id,
            "title": document.title,
            "updated_fields": list(document_update.dict(exclude_unset=True).keys())
        }
    )
    
    return DocumentResponse.from_orm(updated_document)


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete document"""
    
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Soft delete
    DocumentService.delete_document(db, document)
    
    # Log document deletion
    AuditService.log_document_event(
        "DOCUMENT_DELETED",
        current_user.id,
        request,
        {
            "document_id": document.id,
            "title": document.title
        }
    )
    
    return {"message": "Document deleted successfully"}


@router.post("/generate", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def generate_document(
    generation_data: DocumentGenerate,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Generate document from template"""
    
    # Validate template
    template = db.query(Template).filter(
        Template.id == generation_data.template_id,
        Template.is_active == True
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    # Check template access
    if not template.is_public and template.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to template"
        )
    
    # Create document
    document = DocumentService.create_document_from_generation(
        db, generation_data, current_user.id
    )
    
    # Start generation task
    background_tasks.add_task(
        generate_document_task.delay,
        document.id,
        generation_data.placeholder_data
    )
    
    # Log document generation
    AuditService.log_document_event(
        "DOCUMENT_GENERATED",
        current_user.id,
        request,
        {
            "document_id": document.id,
            "template_id": template.id,
            "title": document.title
        }
    )
    
    return DocumentResponse.from_orm(document)


@router.post("/batch", response_model=DocumentBatchResponse, status_code=status.HTTP_201_CREATED)
async def generate_batch_documents(
    batch_data: DocumentBatch,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Generate multiple documents from template"""
    
    # Validate template
    template = db.query(Template).filter(
        Template.id == batch_data.template_id,
        Template.is_active == True
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    # Check template access
    if not template.is_public and template.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to template"
        )
    
    # Create batch documents
    batch_id = str(uuid.uuid4())
    documents = []
    
    for doc_data in batch_data.documents:
        document = DocumentService.create_document_for_batch(
            db, batch_data.template_id, doc_data, current_user.id, batch_id
        )
        documents.append(document)
    
    # Start batch generation task
    background_tasks.add_task(
        generate_batch_documents_task.delay,
        batch_id,
        [doc.id for doc in documents],
        [doc_data["placeholder_data"] for doc_data in batch_data.documents]
    )
    
    # Log batch generation
    AuditService.log_document_event(
        "BATCH_GENERATED",
        current_user.id,
        request,
        {
            "batch_id": batch_id,
            "template_id": template.id,
            "document_count": len(documents)
        }
    )
    
    return DocumentBatchResponse(
        batch_id=batch_id,
        total_documents=len(documents),
        processing_status="processing",
        estimated_completion=datetime.utcnow(),
        documents=[DocumentResponse.from_orm(doc) for doc in documents]
    )


@router.get("/{document_id}/download", response_class=FileResponse)
async def download_document(
    document_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Download document file"""
    
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    if not document.is_completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document is not ready for download"
        )
    
    if not document.file_path or not os.path.exists(document.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found"
        )
    
    # Update download count
    document.download_count += 1
    db.commit()
    
    # Log document download
    AuditService.log_document_event(
        "DOCUMENT_DOWNLOADED",
        current_user.id,
        request,
        {
            "document_id": document.id,
            "title": document.title
        }
    )
    
    return FileResponse(
        path=document.file_path,
        filename=document.original_filename or f"{document.title}.{document.file_format}",
        media_type="application/octet-stream"
    )


@router.post("/{document_id}/share", response_model=dict)
async def share_document(
    document_id: int,
    share_data: DocumentShare,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Share document with link"""
    
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Create share link
    share_info = DocumentService.create_share_link(db, document, share_data)
    
    # Log document sharing
    AuditService.log_document_event(
        "DOCUMENT_SHARED",
        current_user.id,
        request,
        {
            "document_id": document.id,
            "title": document.title,
            "access_level": share_data.access_level.value,
            "expires_in_days": share_data.expires_in_days
        }
    )
    
    return share_info


@router.get("/{document_id}/preview", response_model=DocumentPreview)
async def preview_document(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get document preview"""
    
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    preview = DocumentService.generate_preview(document)
    return preview


@router.get("/shared/{share_token}")
async def access_shared_document(
    share_token: str,
    password: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Access shared document"""
    
    document = db.query(Document).filter(
        Document.share_token == share_token
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shared document not found"
        )
    
    # Validate access
    access_info = DocumentService.validate_shared_access(document, password)
    if not access_info["valid"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=access_info["error"]
        )
    
    # Log shared access
    AuditService.log_document_event(
        "SHARED_DOCUMENT_ACCESSED",
        None,
        request,
        {
            "document_id": document.id,
            "share_token": share_token
        }
    )
    
    return {
        "document": DocumentResponse.from_orm(document),
        "access_type": "shared",
        "expires_at": document.share_expires_at
    }
