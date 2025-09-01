"""
Advanced Batch Document Processing System
Implements intelligent placeholder consolidation, semantic matching, and ultra-fast
multi-template document generation with context-aware formatting.
"""

import asyncio
import json
import time
import uuid
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session
from app.models.template import Template
from app.models.document import Document, DocumentStatus
from app.services.performance_document_engine import (
    UltraFastDocumentEngine, DocumentGenerationRequest, ProcessingPriority,
    PlaceholderContext
)
from io import BytesIO
import logging

batch_logger = logging.getLogger('batch_processing')

class PlaceholderSemanticType(Enum):
    """Semantic types for intelligent placeholder consolidation"""
    NAME = "name"
    ADDRESS = "address"
    DATE = "date"
    SIGNATURE = "signature"
    EMAIL = "email"
    PHONE = "phone"
    NUMBER = "number"
    TEXT = "text"
    CUSTOM = "custom"

@dataclass
class SemanticPlaceholderGroup:
    """Group of placeholders that represent the same semantic concept"""
    semantic_type: PlaceholderSemanticType
    canonical_name: str
    display_name: str
    template_instances: List[Dict[str, Any]] = field(default_factory=list)
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    consolidation_score: float = 0.0
    input_type: str = "text"

@dataclass
class BatchProcessingRequest:
    """Request for batch document processing"""
    template_ids: List[int]
    unified_placeholder_data: Dict[str, Any]
    user_id: int
    batch_title: str
    output_format: str = "docx"
    priority: ProcessingPriority = ProcessingPriority.NORMAL
    enable_signature_processing: bool = True
    performance_target_ms: int = 1000  # Target for entire batch

@dataclass
class BatchProcessingResult:
    """Result of batch document processing"""
    batch_id: str
    documents: List[Tuple[str, BytesIO]]  # (template_name, document_stream)
    processing_stats: Dict[str, Any]
    failed_documents: List[Dict[str, Any]]
    total_time_ms: float
    success_count: int
    failure_count: int

class AdvancedBatchProcessor:
    """
    Advanced batch processing system with intelligent placeholder consolidation
    and semantic understanding for ultra-efficient multi-template processing
    """
    
    def __init__(self):
        self.document_engine = UltraFastDocumentEngine()
        self.semantic_analyzer = PlaceholderSemanticAnalyzer()
        self.executor = ThreadPoolExecutor(max_workers=6)
        
    async def process_batch_request(
        self,
        request: BatchProcessingRequest,
        db: Session
    ) -> BatchProcessingResult:
        """
        Process batch document generation with intelligent consolidation
        """
        start_time = time.time()
        batch_id = str(uuid.uuid4())
        
        batch_logger.info(f"Starting batch processing {batch_id} for {len(request.template_ids)} templates")
        
        try:
            # Step 1: Analyze templates and create unified form structure
            template_analysis = await self._analyze_template_compatibility(
                request.template_ids, db
            )
            
            # Step 2: Generate individual document requests
            document_requests = await self._create_document_requests(
                template_analysis, request, db
            )
            
            # Step 3: Process documents in parallel
            processing_results = await self.document_engine.batch_generate_documents(
                document_requests, db
            )
            
            # Step 4: Compile results
            result = await self._compile_batch_results(
                batch_id, processing_results, template_analysis, start_time
            )
            
            batch_logger.info(
                f"Batch {batch_id} completed: {result.success_count} success, "
                f"{result.failure_count} failures in {result.total_time_ms:.2f}ms"
            )
            
            return result
            
        except Exception as e:
            batch_logger.error(f"Batch processing {batch_id} failed: {e}")
            raise
    
    async def _analyze_template_compatibility(
        self,
        template_ids: List[int],
        db: Session
    ) -> Dict[str, Any]:
        """
        Analyze multiple templates for placeholder consolidation opportunities
        """
        # Load all templates
        templates = db.query(Template).filter(Template.id.in_(template_ids)).all()
        
        if not templates:
            raise ValueError("No templates found for provided IDs")
        
        # Extract placeholders from all templates
        all_placeholders = {}
        template_placeholder_mapping = {}
        
        for template in templates:
            template_placeholders = json.loads(template.placeholders) if template.placeholders else []
            template_placeholder_mapping[template.id] = template_placeholders
            
            for placeholder in template_placeholders:
                placeholder_name = placeholder.get('name', '').lower().strip()
                if placeholder_name:
                    if placeholder_name not in all_placeholders:
                        all_placeholders[placeholder_name] = []
                    
                    all_placeholders[placeholder_name].append({
                        'template_id': template.id,
                        'template_name': template.name,
                        'placeholder_data': placeholder,
                        'template': template
                    })
        
        # Perform semantic analysis
        semantic_groups = await self.semantic_analyzer.analyze_placeholder_semantics(
            all_placeholders
        )
        
        return {
            'templates': templates,
            'all_placeholders': all_placeholders,
            'template_placeholder_mapping': template_placeholder_mapping,
            'semantic_groups': semantic_groups,
            'consolidation_stats': {
                'total_placeholders': sum(len(p) for p in all_placeholders.values()),
                'unique_placeholders': len(all_placeholders),
                'semantic_groups': len(semantic_groups),
                'consolidation_ratio': len(semantic_groups) / max(len(all_placeholders), 1)
            }
        }
    
    async def _create_document_requests(
        self,
        template_analysis: Dict[str, Any],
        batch_request: BatchProcessingRequest,
        db: Session
    ) -> List[DocumentGenerationRequest]:
        """
        Create individual document generation requests with optimized placeholder data
        """
        semantic_groups = template_analysis['semantic_groups']
        templates = template_analysis['templates']
        
        document_requests = []
        
        for template in templates:
            # Map unified data to template-specific placeholders
            template_placeholder_data = await self._map_unified_data_to_template(
                batch_request.unified_placeholder_data,
                template,
                semantic_groups
            )
            
            # Create document request
            request = DocumentGenerationRequest(
                template_id=template.id,
                placeholder_data=template_placeholder_data,
                output_format=batch_request.output_format,
                user_id=batch_request.user_id,
                priority=batch_request.priority,
                performance_target_ms=batch_request.performance_target_ms // len(templates)
            )
            
            document_requests.append(request)
        
        return document_requests
    
    async def _map_unified_data_to_template(
        self,
        unified_data: Dict[str, Any],
        template: Template,
        semantic_groups: List[SemanticPlaceholderGroup]
    ) -> Dict[str, Any]:
        """
        Map unified placeholder data to template-specific placeholder names
        """
        template_data = {}
        template_placeholders = json.loads(template.placeholders) if template.placeholders else []
        
        # Create mapping from template placeholder names to unified data
        for template_placeholder in template_placeholders:
            placeholder_name = template_placeholder.get('name', '')
            
            # Find the semantic group this placeholder belongs to
            for group in semantic_groups:
                for instance in group.template_instances:
                    if (instance['template_id'] == template.id and 
                        instance['placeholder_data']['name'] == placeholder_name):
                        
                        # Get unified data using canonical name
                        unified_value = unified_data.get(group.canonical_name, '')
                        
                        # Apply template-specific formatting
                        formatted_value = await self._apply_template_specific_formatting(
                            unified_value, template_placeholder, group
                        )
                        
                        template_data[placeholder_name] = formatted_value
                        break
        
        return template_data
    
    async def _apply_template_specific_formatting(
        self,
        value: str,
        template_placeholder: Dict[str, Any],
        semantic_group: SemanticPlaceholderGroup
    ) -> str:
        """
        Apply template-specific formatting to unified data
        """
        if not value:
            return value
        
        # Apply casing rules
        casing = template_placeholder.get('casing', 'none')
        if casing == 'upper':
            value = value.upper()
        elif casing == 'lower':
            value = value.lower()
        elif casing == 'title':
            value = value.title()
        
        # Apply semantic-specific formatting
        if semantic_group.semantic_type == PlaceholderSemanticType.DATE:
            value = self._format_date_for_template(value, template_placeholder)
        elif semantic_group.semantic_type == PlaceholderSemanticType.ADDRESS:
            value = self._format_address_for_template(value, template_placeholder)
        elif semantic_group.semantic_type == PlaceholderSemanticType.NAME:
            value = self._format_name_for_template(value, template_placeholder)
        
        return value
    
    def _format_date_for_template(self, date_str: str, template_placeholder: Dict[str, Any]) -> str:
        """Format date according to template requirements"""
        try:
            from dateutil.parser import parse
            date_obj = parse(date_str)
            
            # Check template preferences
            date_format = template_placeholder.get('date_format', '%d/%m/%Y')
            return date_obj.strftime(date_format)
        except:
            return date_str
    
    def _format_address_for_template(self, address: str, template_placeholder: Dict[str, Any]) -> str:
        """Format address according to template context"""
        context = template_placeholder.get('context', 'body')
        
        if context == 'header':
            # Header addresses often need line breaks instead of commas
            return address.replace(', ', '\n')
        else:
            return address
    
    def _format_name_for_template(self, name: str, template_placeholder: Dict[str, Any]) -> str:
        """Format name according to template context"""
        context = template_placeholder.get('context', 'body')
        
        if context == 'signature':
            return name.upper()
        else:
            return name.title()
    
    async def _compile_batch_results(
        self,
        batch_id: str,
        processing_results: List[Any],
        template_analysis: Dict[str, Any],
        start_time: float
    ) -> BatchProcessingResult:
        """
        Compile batch processing results with comprehensive statistics
        """
        total_time = (time.time() - start_time) * 1000
        documents = []
        failed_documents = []
        success_count = 0
        failure_count = 0
        
        templates = template_analysis['templates']
        
        for i, result in enumerate(processing_results):
            template = templates[i]
            
            if isinstance(result, Exception):
                # Failed document
                failed_documents.append({
                    'template_id': template.id,
                    'template_name': template.name,
                    'error': str(result)
                })
                failure_count += 1
            else:
                # Successful document
                document_stream, stats = result
                documents.append((template.name, document_stream))
                success_count += 1
        
        # Compile processing statistics
        processing_stats = {
            'batch_id': batch_id,
            'total_templates': len(templates),
            'processing_time_ms': total_time,
            'consolidation_stats': template_analysis['consolidation_stats'],
            'average_document_time': total_time / len(templates) if templates else 0,
            'cache_efficiency': getattr(self.document_engine, 'cache_hit_rate', 0.0),
            'semantic_groups_used': len(template_analysis['semantic_groups'])
        }
        
        return BatchProcessingResult(
            batch_id=batch_id,
            documents=documents,
            processing_stats=processing_stats,
            failed_documents=failed_documents,
            total_time_ms=total_time,
            success_count=success_count,
            failure_count=failure_count
        )

class PlaceholderSemanticAnalyzer:
    """
    Intelligent placeholder semantic analysis for consolidation
    """
    
    def __init__(self):
        self.semantic_patterns = {
            PlaceholderSemanticType.NAME: [
                'name', 'full_name', 'applicant', 'student', 'client', 
                'user', 'person', 'individual', 'candidate'
            ],
            PlaceholderSemanticType.ADDRESS: [
                'address', 'location', 'residence', 'home', 'office',
                'street', 'city', 'state', 'postal'
            ],
            PlaceholderSemanticType.DATE: [
                'date', 'birth', 'issued', 'expire', 'created', 'updated',
                'start', 'end', 'deadline', 'due'
            ],
            PlaceholderSemanticType.SIGNATURE: [
                'signature', 'sign', 'autograph', 'endorsement'
            ],
            PlaceholderSemanticType.EMAIL: [
                'email', 'mail', 'e_mail', 'electronic_mail'
            ],
            PlaceholderSemanticType.PHONE: [
                'phone', 'mobile', 'tel', 'telephone', 'contact',
                'cell', 'number'
            ],
            PlaceholderSemanticType.NUMBER: [
                'age', 'years', 'count', 'quantity', 'amount',
                'id', 'reference', 'serial'
            ]
        }
    
    async def analyze_placeholder_semantics(
        self,
        all_placeholders: Dict[str, List[Dict[str, Any]]]
    ) -> List[SemanticPlaceholderGroup]:
        """
        Analyze placeholders and group by semantic meaning
        """
        semantic_groups = []
        processed_placeholders = set()
        
        for placeholder_name, instances in all_placeholders.items():
            if placeholder_name in processed_placeholders:
                continue
            
            # Determine semantic type
            semantic_type = self._classify_placeholder_semantic_type(placeholder_name)
            
            # Find similar placeholders
            similar_placeholders = self._find_similar_placeholders(
                placeholder_name, all_placeholders, semantic_type
            )
            
            # Create semantic group
            group = SemanticPlaceholderGroup(
                semantic_type=semantic_type,
                canonical_name=self._generate_canonical_name(placeholder_name, semantic_type),
                display_name=self._generate_display_name(placeholder_name, semantic_type),
                input_type=self._determine_input_type(semantic_type)
            )
            
            # Add all instances to the group
            for similar_name in similar_placeholders:
                if similar_name in all_placeholders:
                    group.template_instances.extend(all_placeholders[similar_name])
                    processed_placeholders.add(similar_name)
            
            # Calculate consolidation score
            group.consolidation_score = len(group.template_instances) / max(len(similar_placeholders), 1)
            
            # Set validation rules
            group.validation_rules = self._get_validation_rules_for_type(semantic_type)
            
            semantic_groups.append(group)
        
        return semantic_groups
    
    def _classify_placeholder_semantic_type(self, placeholder_name: str) -> PlaceholderSemanticType:
        """
        Classify placeholder into semantic type using pattern matching
        """
        name_lower = placeholder_name.lower().replace('_', ' ')
        
        for semantic_type, patterns in self.semantic_patterns.items():
            for pattern in patterns:
                if pattern in name_lower:
                    return semantic_type
        
        return PlaceholderSemanticType.TEXT
    
    def _find_similar_placeholders(
        self,
        placeholder_name: str,
        all_placeholders: Dict[str, List[Dict[str, Any]]],
        semantic_type: PlaceholderSemanticType
    ) -> Set[str]:
        """
        Find placeholders with similar semantic meaning
        """
        similar = {placeholder_name}
        patterns = self.semantic_patterns.get(semantic_type, [])
        
        for other_name in all_placeholders.keys():
            if other_name != placeholder_name:
                if self._calculate_semantic_similarity(placeholder_name, other_name, patterns) > 0.7:
                    similar.add(other_name)
        
        return similar
    
    def _calculate_semantic_similarity(
        self,
        name1: str,
        name2: str,
        patterns: List[str]
    ) -> float:
        """
        Calculate semantic similarity between two placeholder names
        """
        name1_lower = name1.lower().replace('_', ' ')
        name2_lower = name2.lower().replace('_', ' ')
        
        # Direct match
        if name1_lower == name2_lower:
            return 1.0
        
        # Pattern-based similarity
        name1_patterns = [p for p in patterns if p in name1_lower]
        name2_patterns = [p for p in patterns if p in name2_lower]
        
        if name1_patterns and name2_patterns:
            common_patterns = set(name1_patterns) & set(name2_patterns)
            if common_patterns:
                return len(common_patterns) / max(len(name1_patterns), len(name2_patterns))
        
        # Edit distance similarity (basic implementation)
        return self._edit_distance_similarity(name1_lower, name2_lower)
    
    def _edit_distance_similarity(self, s1: str, s2: str) -> float:
        """
        Calculate similarity based on edit distance
        """
        if not s1 or not s2:
            return 0.0
        
        # Simple Levenshtein distance implementation
        if len(s1) > len(s2):
            s1, s2 = s2, s1
        
        distances = range(len(s1) + 1)
        for i2, c2 in enumerate(s2):
            new_distances = [i2 + 1]
            for i1, c1 in enumerate(s1):
                if c1 == c2:
                    new_distances.append(distances[i1])
                else:
                    new_distances.append(1 + min(distances[i1], distances[i1 + 1], new_distances[-1]))
            distances = new_distances
        
        max_len = max(len(s1), len(s2))
        return 1.0 - (distances[-1] / max_len)
    
    def _generate_canonical_name(self, placeholder_name: str, semantic_type: PlaceholderSemanticType) -> str:
        """
        Generate a canonical name for the semantic group
        """
        type_names = {
            PlaceholderSemanticType.NAME: "full_name",
            PlaceholderSemanticType.ADDRESS: "address",
            PlaceholderSemanticType.DATE: "date",
            PlaceholderSemanticType.SIGNATURE: "signature",
            PlaceholderSemanticType.EMAIL: "email",
            PlaceholderSemanticType.PHONE: "phone",
            PlaceholderSemanticType.NUMBER: "number",
            PlaceholderSemanticType.TEXT: "text_field"
        }
        
        return type_names.get(semantic_type, placeholder_name)
    
    def _generate_display_name(self, placeholder_name: str, semantic_type: PlaceholderSemanticType) -> str:
        """
        Generate user-friendly display name
        """
        display_names = {
            PlaceholderSemanticType.NAME: "Full Name",
            PlaceholderSemanticType.ADDRESS: "Address",
            PlaceholderSemanticType.DATE: "Date",
            PlaceholderSemanticType.SIGNATURE: "Signature",
            PlaceholderSemanticType.EMAIL: "Email Address",
            PlaceholderSemanticType.PHONE: "Phone Number",
            PlaceholderSemanticType.NUMBER: "Number",
            PlaceholderSemanticType.TEXT: "Text"
        }
        
        return display_names.get(semantic_type, placeholder_name.replace('_', ' ').title())
    
    def _determine_input_type(self, semantic_type: PlaceholderSemanticType) -> str:
        """
        Determine appropriate HTML input type for semantic group
        """
        input_types = {
            PlaceholderSemanticType.NAME: "text",
            PlaceholderSemanticType.ADDRESS: "textarea",
            PlaceholderSemanticType.DATE: "date",
            PlaceholderSemanticType.SIGNATURE: "signature_canvas",
            PlaceholderSemanticType.EMAIL: "email",
            PlaceholderSemanticType.PHONE: "tel",
            PlaceholderSemanticType.NUMBER: "number",
            PlaceholderSemanticType.TEXT: "text"
        }
        
        return input_types.get(semantic_type, "text")
    
    def _get_validation_rules_for_type(self, semantic_type: PlaceholderSemanticType) -> Dict[str, Any]:
        """
        Get validation rules for semantic type
        """
        rules = {
            PlaceholderSemanticType.NAME: {
                "required": True,
                "min_length": 2,
                "max_length": 100,
                "pattern": r"^[a-zA-Z\s\-']+$"
            },
            PlaceholderSemanticType.EMAIL: {
                "required": True,
                "pattern": r"^[^@]+@[^@]+\.[^@]+$"
            },
            PlaceholderSemanticType.PHONE: {
                "required": True,
                "pattern": r"^\+?[1-9]\d{1,14}$"
            },
            PlaceholderSemanticType.DATE: {
                "required": True,
                "format": "YYYY-MM-DD"
            },
            PlaceholderSemanticType.ADDRESS: {
                "required": True,
                "min_length": 10,
                "max_length": 500
            },
            PlaceholderSemanticType.NUMBER: {
                "required": True,
                "type": "integer",
                "min": 0
            },
            PlaceholderSemanticType.SIGNATURE: {
                "required": True,
                "type": "canvas"
            },
            PlaceholderSemanticType.TEXT: {
                "required": True,
                "min_length": 1,
                "max_length": 1000
            }
        }
        
        return rules.get(semantic_type, {"required": True})

# Global batch processor instance
advanced_batch_processor = AdvancedBatchProcessor()