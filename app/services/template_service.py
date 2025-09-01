"""
Template management and processing service
"""

import os
import uuid
import hashlib
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_, func
from fastapi import UploadFile
from docx import Document as DocxDocument
import redis

from config import settings
from app.models.template import Template, Placeholder
from app.models.user import User
from app.schemas.template import (
    TemplateCreate, TemplateUpdate, TemplateSearch, TemplatePreview,
    TemplateUpload, TemplateRating, TemplateStats, PlaceholderCreate
)
from database import get_db

# Redis client for caching
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    decode_responses=True
)


class TemplateService:
    """Template management and processing service"""
    
    @staticmethod
    async def create_template(db: Session, template_data: TemplateCreate, 
                            file: UploadFile, user_id: int) -> Template:
        """Create new template with file upload"""
        
        # Generate unique filename
        file_extension = Path(file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(settings.TEMPLATES_PATH, unique_filename)
        
        # Save uploaded file
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Calculate file hash and size
        file_hash = TemplateService._calculate_file_hash(file_path)
        file_size = os.path.getsize(file_path)
        
        # Extract placeholders from document
        placeholders = TemplateService._extract_placeholders_from_file(file_path)
        
        # Detect document font
        font_family, font_size = TemplateService._detect_document_font(file_path)
        if template_data.font_family == "Times New Roman":  # Default
            template_data.font_family = font_family
        if template_data.font_size == 12:  # Default
            template_data.font_size = font_size
        
        # Create template record
        template = Template(
            name=template_data.name,
            description=template_data.description,
            category=template_data.category,
            type=template_data.type,
            file_path=unique_filename,
            original_filename=file.filename,
            file_size=file_size,
            file_hash=file_hash,
            placeholders=json.dumps([p.__dict__ for p in placeholders]),
            language=template_data.language,
            font_family=template_data.font_family,
            font_size=template_data.font_size,
            is_public=template_data.is_public,
            is_premium=template_data.is_premium,
            price=template_data.price,
            tags=template_data.tags,
            keywords=template_data.keywords,
            created_by=user_id
        )
        
        db.add(template)
        db.commit()
        db.refresh(template)
        
        # Create placeholder records
        for placeholder_data in placeholders:
            placeholder = Placeholder(
                template_id=template.id,
                name=placeholder_data.name,
                display_name=placeholder_data.display_name,
                placeholder_type=placeholder_data.placeholder_type,
                paragraph_index=placeholder_data.paragraph_index,
                start_run_index=placeholder_data.start_run_index,
                end_run_index=placeholder_data.end_run_index,
                bold=placeholder_data.bold,
                italic=placeholder_data.italic,
                underline=placeholder_data.underline,
                casing=placeholder_data.casing,
                is_required=placeholder_data.is_required
            )
            db.add(placeholder)
        
        db.commit()
        
        # Cache template for faster access
        TemplateService._cache_template(template)
        
        return template
    
    @staticmethod
    def update_template(db: Session, template: Template, template_update: TemplateUpdate) -> Template:
        """Update template"""
        
        for field, value in template_update.dict(exclude_unset=True).items():
            setattr(template, field, value)
        
        template.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(template)
        
        # Update cache
        TemplateService._cache_template(template)
        
        return template
    
    @staticmethod
    def delete_template(db: Session, template: Template) -> None:
        """Soft delete template"""
        
        template.is_active = False
        template.deleted_at = datetime.utcnow()
        db.commit()
        
        # Remove from cache
        redis_client.delete(f"template:{template.id}")
    
    @staticmethod
    def search_templates(db: Session, user_id: int, search_params: TemplateSearch) -> Tuple[List[Template], int]:
        """Search templates with advanced filters"""
        
        query = db.query(Template).filter(Template.is_active == True)
        
        # Access control - show public templates and user's own templates
        query = query.filter(
            or_(
                Template.is_public == True,
                Template.created_by == user_id
            )
        )
        
        # Apply filters
        if search_params.query:
            query = query.filter(
                or_(
                    Template.name.contains(search_params.query),
                    Template.description.contains(search_params.query),
                    Template.keywords.contains(search_params.query)
                )
            )
        
        if search_params.category:
            query = query.filter(Template.category == search_params.category)
        
        if search_params.type:
            query = query.filter(Template.type == search_params.type)
        
        if search_params.language:
            query = query.filter(Template.language == search_params.language)
        
        if search_params.is_public is not None:
            query = query.filter(Template.is_public == search_params.is_public)
        
        if search_params.is_premium is not None:
            query = query.filter(Template.is_premium == search_params.is_premium)
        
        if search_params.min_price is not None:
            query = query.filter(Template.price >= search_params.min_price)
        
        if search_params.max_price is not None:
            query = query.filter(Template.price <= search_params.max_price)
        
        if search_params.tags:
            # JSON array contains search
            for tag in search_params.tags:
                query = query.filter(Template.tags.contains(f'"{tag}"'))
        
        # Get total count
        total = query.count()
        
        # Apply sorting
        if search_params.sort_by == "name":
            order_col = Template.name
        elif search_params.sort_by == "usage_count":
            order_col = Template.usage_count
        elif search_params.sort_by == "rating":
            order_col = Template.rating
        elif search_params.sort_by == "price":
            order_col = Template.price
        else:
            order_col = Template.created_at
        
        if search_params.sort_order == "asc":
            query = query.order_by(order_col)
        else:
            query = query.order_by(desc(order_col))
        
        # Apply pagination
        templates = query.offset(
            (search_params.page - 1) * search_params.per_page
        ).limit(search_params.per_page).all()
        
        return templates, total
    
    @staticmethod
    def generate_preview(template: Template) -> TemplatePreview:
        """Generate template preview"""
        
        # Get placeholders
        db = next(get_db())
        placeholders = db.query(Placeholder).filter(
            Placeholder.template_id == template.id
        ).all()
        db.close()
        
        return TemplatePreview(
            id=template.id,
            name=template.name,
            description=template.description,
            category=template.category,
            type=template.type,
            placeholders=[
                {
                    "name": ph.name,
                    "display_name": ph.display_name,
                    "type": ph.placeholder_type,
                    "required": ph.is_required
                }
                for ph in placeholders
            ],
            preview_url=None,  # TODO: Generate preview image
            watermarked=True
        )
    
    @staticmethod
    def rate_template(db: Session, template: Template, user_id: int, rating_data: TemplateRating) -> None:
        """Rate a template"""
        
        # Calculate new rating
        current_total = template.rating * template.rating_count
        new_total = current_total + rating_data.rating
        new_count = template.rating_count + 1
        new_rating = new_total / new_count
        
        # Update template
        template.rating = round(new_rating, 2)
        template.rating_count = new_count
        
        db.commit()
        
        # TODO: Store individual rating record for user
        # This would prevent duplicate ratings from same user
    
    @staticmethod
    def get_template_analytics(db: Session, template_id: int) -> Dict[str, Any]:
        """Get analytics for a template"""
        
        template = db.query(Template).filter(Template.id == template_id).first()
        if not template:
            return {}
        
        # Usage over time (last 30 days)
        from app.models.document import Document
        from datetime import timedelta
        
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        daily_usage = db.query(
            func.date(Document.created_at).label('date'),
            func.count(Document.id).label('count')
        ).filter(
            Document.template_id == template_id,
            Document.created_at >= thirty_days_ago
        ).group_by(
            func.date(Document.created_at)
        ).all()
        
        return {
            "template_id": template_id,
            "total_usage": template.usage_count,
            "total_downloads": template.download_count,
            "rating": template.rating,
            "rating_count": template.rating_count,
            "daily_usage": [
                {
                    "date": str(usage.date),
                    "count": usage.count
                }
                for usage in daily_usage
            ]
        }
    
    @staticmethod
    def _extract_placeholders_from_file(file_path: str) -> List[PlaceholderCreate]:
        """Extract placeholders from document file"""
        
        placeholders = []
        placeholder_pattern = re.compile(r'\$\{([^}]+)\}')
        
        try:
            doc = DocxDocument(file_path)
            
            for p_idx, paragraph in enumerate(doc.paragraphs):
                full_text = ''.join(run.text for run in paragraph.runs)
                matches = placeholder_pattern.finditer(full_text)
                
                for match in matches:
                    placeholder_name = match.group(1)
                    start_pos = match.start()
                    end_pos = match.end()
                    
                    # Find which runs contain the placeholder
                    current_pos = 0
                    start_run_idx = end_run_idx = None
                    bold = italic = underline = False
                    
                    for r_idx, run in enumerate(paragraph.runs):
                        run_start = current_pos
                        run_end = current_pos + len(run.text)
                        
                        if start_run_idx is None and run_start <= start_pos < run_end:
                            start_run_idx = r_idx
                            bold = run.bold or False
                            italic = run.italic or False
                            underline = run.underline or False
                        
                        if run_start < end_pos <= run_end:
                            end_run_idx = r_idx
                            break
                        
                        current_pos = run_end
                    
                    if start_run_idx is not None and end_run_idx is not None:
                        # Infer placeholder type from name
                        placeholder_type = TemplateService._infer_placeholder_type(placeholder_name)
                        
                        placeholders.append(PlaceholderCreate(
                            name=placeholder_name,
                            display_name=placeholder_name.replace('_', ' ').title(),
                            placeholder_type=placeholder_type,
                            paragraph_index=p_idx,
                            start_run_index=start_run_idx,
                            end_run_index=end_run_idx,
                            bold=bold,
                            italic=italic,
                            underline=underline,
                            is_required=True
                        ))
        
        except Exception as e:
            print(f"Error extracting placeholders: {e}")
        
        return placeholders
    
    @staticmethod
    def _infer_placeholder_type(name: str) -> str:
        """Infer placeholder type from name"""
        
        name_lower = name.lower()
        
        if 'date' in name_lower or 'time' in name_lower:
            return 'date'
        elif 'email' in name_lower:
            return 'email'
        elif 'phone' in name_lower or 'tel' in name_lower:
            return 'phone'
        elif 'url' in name_lower or 'website' in name_lower:
            return 'url'
        elif 'amount' in name_lower or 'price' in name_lower or 'cost' in name_lower:
            return 'number'
        else:
            return 'text'
    
    @staticmethod
    def _detect_document_font(file_path: str) -> Tuple[str, int]:
        """Detect the most common font in document"""
        
        try:
            doc = DocxDocument(file_path)
            font_counts = {}
            
            for paragraph in doc.paragraphs:
                for run in paragraph.runs:
                    if run.font.name and run.font.size:
                        key = (run.font.name, int(run.font.size.pt))
                        font_counts[key] = font_counts.get(key, 0) + 1
            
            if font_counts:
                most_common = max(font_counts.items(), key=lambda x: x[1])
                return most_common[0][0], most_common[0][1]
        
        except Exception:
            pass
        
        return "Times New Roman", 12
    
    @staticmethod
    def _calculate_file_hash(file_path: str) -> str:
        """Calculate SHA256 hash of file"""
        
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    @staticmethod
    def _cache_template(template: Template) -> None:
        """Cache template data in Redis"""
        
        template_data = {
            "id": template.id,
            "name": template.name,
            "category": template.category,
            "type": template.type,
            "file_path": template.file_path,
            "placeholders": template.placeholders,
            "font_family": template.font_family,
            "font_size": template.font_size,
            "is_public": template.is_public,
            "is_premium": template.is_premium,
            "price": template.price
        }
        
        redis_client.setex(
            f"template:{template.id}",
            settings.TEMPLATE_CACHE_TTL,
            json.dumps(template_data)
        )
    
    @staticmethod
    def get_cached_template(template_id: int) -> Optional[Dict[str, Any]]:
        """Get template from cache"""
        
        cached_data = redis_client.get(f"template:{template_id}")
        if cached_data:
            try:
                return json.loads(cached_data)
            except json.JSONDecodeError:
                pass
        
        return None
    
    @staticmethod
    def cleanup_unused_templates():
        """Cleanup unused template files (background task)"""
        
        db = next(get_db())
        
        try:
            # Get all template files from database
            templates = db.query(Template).filter(Template.is_active == True).all()
            db_file_paths = {template.file_path for template in templates}
            
            # Get all files in templates directory
            templates_dir = Path(settings.TEMPLATES_PATH)
            if templates_dir.exists():
                for file_path in templates_dir.iterdir():
                    if file_path.is_file() and file_path.name not in db_file_paths:
                        try:
                            file_path.unlink()  # Delete file
                        except OSError:
                            pass
        
        finally:
            db.close()
    
    @staticmethod
    def optimize_template_search_index():
        """Optimize template search performance (background task)"""
        
        db = next(get_db())
        
        try:
            # Update search vectors for full-text search
            templates = db.query(Template).filter(Template.is_active == True).all()
            
            for template in templates:
                # Create search vector from name, description, keywords, and tags
                search_terms = []
                
                if template.name:
                    search_terms.append(template.name.lower())
                
                if template.description:
                    search_terms.append(template.description.lower())
                
                if template.keywords:
                    search_terms.append(template.keywords.lower())
                
                if template.tags:
                    search_terms.extend([tag.lower() for tag in template.tags])
                
                template.search_vector = " ".join(search_terms)
            
            db.commit()
        
        finally:
            db.close()
    
    @staticmethod
    def get_popular_templates(db: Session, limit: int = 10) -> List[Template]:
        """Get most popular templates"""
        
        return db.query(Template).filter(
            Template.is_active == True,
            Template.is_public == True
        ).order_by(
            desc(Template.usage_count)
        ).limit(limit).all()
    
    @staticmethod
    def get_template_recommendations(db: Session, user_id: int, limit: int = 5) -> List[Template]:
        """Get template recommendations for user"""
        
        # Simple recommendation based on user's most used categories
        from app.models.document import Document
        
        user_categories = db.query(
            Template.category,
            func.count(Document.id).label('usage_count')
        ).join(
            Document, Document.template_id == Template.id
        ).filter(
            Document.user_id == user_id
        ).group_by(
            Template.category
        ).order_by(
            desc('usage_count')
        ).limit(3).all()
        
        if not user_categories:
            # If no usage history, return popular templates
            return TemplateService.get_popular_templates(db, limit)
        
        # Get templates from user's favorite categories
        categories = [cat.category for cat in user_categories]
        
        recommended = db.query(Template).filter(
            Template.is_active == True,
            Template.is_public == True,
            Template.category.in_(categories)
        ).order_by(
            desc(Template.rating),
            desc(Template.usage_count)
        ).limit(limit).all()
        
        return recommended
