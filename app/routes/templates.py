"""
Template management routes
"""

import os
import hashlib
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, and_
import json

from database import get_db
from config import settings
from app.models.template import Template, Placeholder
from app.models.user import User, UserRole
from app.schemas.template import (
    TemplateCreate, TemplateUpdate, TemplateResponse, TemplateList,
    TemplateSearch, TemplatePreview, TemplateUpload, TemplateRating,
    TemplateStats, PlaceholderCreate, PlaceholderResponse
)
from app.services.template_service import TemplateService
from app.services.audit_service import AuditService
from app.utils.security import get_current_active_user
from app.utils.validation import validate_file_upload

router = APIRouter()


@router.post("/", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    category: str = Form(...),
    type: str = Form(...),
    language: str = Form("en"),
    font_family: str = Form("Times New Roman"),
    font_size: int = Form(12),
    is_public: bool = Form(False),
    is_premium: bool = Form(False),
    price: float = Form(0.0),
    tags: Optional[str] = Form(None),  # JSON string
    file: UploadFile = File(...),
    request: Request = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new template with file upload"""
    
    # Validate file upload
    if not validate_file_upload(file, settings.ALLOWED_EXTENSIONS, settings.MAX_FILE_SIZE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format or size"
        )
    
    # Parse tags if provided
    parsed_tags = []
    if tags:
        try:
            parsed_tags = json.loads(tags)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid tags format"
            )
    
    # Create template data object
    template_data = TemplateCreate(
        name=name,
        description=description,
        category=category,
        type=type,
        language=language,
        font_family=font_family,
        font_size=font_size,
        is_public=is_public,
        is_premium=is_premium,
        price=price,
        tags=parsed_tags
    )
    
    # Create template with file
    template = await TemplateService.create_template(
        db, template_data, file, current_user.id
    )
    
    # Log template creation
    AuditService.log_template_event(
        "TEMPLATE_CREATED",
        current_user.id,
        request,
        {
            "template_id": template.id,
            "name": template.name,
            "category": template.category
        }
    )
    
    return TemplateResponse.from_orm(template)


@router.get("/", response_model=TemplateList)
async def list_templates(
    page: int = 1,
    per_page: int = 20,
    category: Optional[str] = None,
    type: Optional[str] = None,
    is_public: Optional[bool] = None,
    my_templates: bool = False,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List templates with pagination and filters"""
    
    # Build query
    query = db.query(Template).filter(Template.is_active == True)
    
    # Apply access filters
    if my_templates:
        query = query.filter(Template.created_by == current_user.id)
    else:
        # Show public templates and user's own templates
        query = query.filter(
            or_(
                Template.is_public == True,
                Template.created_by == current_user.id
            )
        )
    
    # Apply other filters
    if category:
        query = query.filter(Template.category == category)
    
    if type:
        query = query.filter(Template.type == type)
    
    if is_public is not None:
        query = query.filter(Template.is_public == is_public)
    
    # Get total count
    total = query.count()
    
    # Apply pagination and ordering
    templates = query.order_by(desc(Template.created_at)).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    
    # Get categories and types for filtering UI
    categories = db.query(Template.category).distinct().filter(
        Template.is_active == True,
        or_(Template.is_public == True, Template.created_by == current_user.id)
    ).all()
    categories = [cat[0] for cat in categories]
    
    types = db.query(Template.type).distinct().filter(
        Template.is_active == True,
        or_(Template.is_public == True, Template.created_by == current_user.id)
    ).all()
    types = [typ[0] for typ in types]
    
    # Calculate pagination info
    pages = (total + per_page - 1) // per_page
    
    return TemplateList(
        templates=[TemplateResponse.from_orm(tmpl) for tmpl in templates],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
        categories=categories,
        types=types
    )


@router.get("/search", response_model=TemplateList)
async def search_templates(
    search_params: TemplateSearch = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Advanced template search"""
    
    templates, total = TemplateService.search_templates(
        db, current_user.id, search_params
    )
    
    pages = (total + search_params.per_page - 1) // search_params.per_page
    
    return TemplateList(
        templates=[TemplateResponse.from_orm(tmpl) for tmpl in templates],
        total=total,
        page=search_params.page,
        per_page=search_params.per_page,
        pages=pages
    )


@router.get("/categories")
async def get_template_categories(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all template categories"""
    
    categories = db.query(Template.category).distinct().filter(
        Template.is_active == True,
        or_(Template.is_public == True, Template.created_by == current_user.id)
    ).all()
    
    return {"categories": [cat[0] for cat in categories]}


@router.get("/types")
async def get_template_types(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get template types, optionally filtered by category"""
    
    query = db.query(Template.type).distinct().filter(
        Template.is_active == True,
        or_(Template.is_public == True, Template.created_by == current_user.id)
    )
    
    if category:
        query = query.filter(Template.category == category)
    
    types = query.all()
    
    return {"types": [typ[0] for typ in types]}


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get template by ID"""
    
    template = db.query(Template).filter(
        Template.id == template_id,
        Template.is_active == True
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    # Check access permissions
    if not template.is_public and template.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to template"
        )
    
    return TemplateResponse.from_orm(template)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int,
    template_update: TemplateUpdate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update template"""
    
    template = db.query(Template).filter(
        Template.id == template_id,
        Template.created_by == current_user.id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found or access denied"
        )
    
    # Update template
    updated_template = TemplateService.update_template(db, template, template_update)
    
    # Log template update
    AuditService.log_template_event(
        "TEMPLATE_UPDATED",
        current_user.id,
        request,
        {
            "template_id": template.id,
            "name": template.name,
            "updated_fields": list(template_update.dict(exclude_unset=True).keys())
        }
    )
    
    return TemplateResponse.from_orm(updated_template)


@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete template"""
    
    template = db.query(Template).filter(
        Template.id == template_id,
        Template.created_by == current_user.id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found or access denied"
        )
    
    # Soft delete
    TemplateService.delete_template(db, template)
    
    # Log template deletion
    AuditService.log_template_event(
        "TEMPLATE_DELETED",
        current_user.id,
        request,
        {
            "template_id": template.id,
            "name": template.name
        }
    )
    
    return {"message": "Template deleted successfully"}


@router.get("/{template_id}/preview", response_model=TemplatePreview)
async def preview_template(
    template_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get template preview"""
    
    template = db.query(Template).filter(
        Template.id == template_id,
        Template.is_active == True
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    # Check access permissions
    if not template.is_public and template.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to template"
        )
    
    preview = TemplateService.generate_preview(template)
    return preview


@router.get("/{template_id}/download", response_class=FileResponse)
async def download_template(
    template_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Download template file"""
    
    template = db.query(Template).filter(
        Template.id == template_id,
        Template.is_active == True
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    # Check access permissions
    if not template.is_public and template.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to template"
        )
    
    file_path = os.path.join(settings.TEMPLATES_PATH, template.file_path)
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template file not found"
        )
    
    # Update download count
    template.download_count += 1
    db.commit()
    
    # Log template download
    AuditService.log_template_event(
        "TEMPLATE_DOWNLOADED",
        current_user.id,
        request,
        {
            "template_id": template.id,
            "name": template.name
        }
    )
    
    return FileResponse(
        path=file_path,
        filename=template.original_filename,
        media_type="application/octet-stream"
    )


@router.post("/{template_id}/rate")
async def rate_template(
    template_id: int,
    rating_data: TemplateRating,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Rate a template"""
    
    template = db.query(Template).filter(
        Template.id == template_id,
        Template.is_active == True,
        Template.is_public == True
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found or not public"
        )
    
    # Update template rating
    TemplateService.rate_template(db, template, current_user.id, rating_data)
    
    # Log template rating
    AuditService.log_template_event(
        "TEMPLATE_RATED",
        current_user.id,
        request,
        {
            "template_id": template.id,
            "rating": rating_data.rating,
            "comment": rating_data.comment
        }
    )
    
    return {"message": "Template rated successfully"}


@router.get("/{template_id}/placeholders", response_model=List[PlaceholderResponse])
async def get_template_placeholders(
    template_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get template placeholders"""
    
    template = db.query(Template).filter(
        Template.id == template_id,
        Template.is_active == True
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    # Check access permissions
    if not template.is_public and template.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to template"
        )
    
    placeholders = db.query(Placeholder).filter(
        Placeholder.template_id == template_id
    ).order_by(
        Placeholder.paragraph_index,
        Placeholder.start_run_index
    ).all()
    
    return [PlaceholderResponse.from_orm(ph) for ph in placeholders]


@router.post("/{template_id}/use")
async def use_template(
    template_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Track template usage"""
    
    template = db.query(Template).filter(
        Template.id == template_id,
        Template.is_active == True
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    # Check access permissions
    if not template.is_public and template.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to template"
        )
    
    # Update usage count
    template.usage_count += 1
    db.commit()
    
    # Log template usage
    AuditService.log_template_event(
        "TEMPLATE_USED",
        current_user.id,
        request,
        {
            "template_id": template.id,
            "name": template.name
        }
    )
    
    return {"message": "Template usage tracked"}


@router.get("/my/stats", response_model=List[TemplateStats])
async def get_my_template_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get statistics for user's templates"""
    
    templates = db.query(Template).filter(
        Template.created_by == current_user.id,
        Template.is_active == True
    ).all()
    
    stats = []
    for template in templates:
        stats.append(TemplateStats(
            id=template.id,
            name=template.name,
            usage_count=template.usage_count,
            download_count=template.download_count,
            rating=template.rating,
            rating_count=template.rating_count,
            revenue=template.price * template.usage_count if template.is_premium else 0,
            created_at=template.created_at,
            last_used=None  # TODO: Get from usage tracking
        ))
    
    return stats
