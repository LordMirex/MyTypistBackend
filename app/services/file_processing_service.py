"""
Advanced file processing service for high-performance document operations
"""

import os
import time
import asyncio
import hashlib
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import aiofiles
from fastapi import UploadFile, HTTPException, status

from config import settings
from app.services.encryption_service import EncryptionService
from app.services.audit_service import AuditService
from app.utils.validation import validate_file_upload


class FileProcessingService:
    """Advanced file processing with async operations and security"""
    
    def __init__(self):
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        self.supported_formats = {
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.pdf': 'application/pdf',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg'
        }
    
    async def process_upload_async(
        self, 
        file: UploadFile, 
        storage_path: str,
        encrypt: bool = True,
        validate: bool = True
    ) -> Dict[str, Any]:
        """Process file upload asynchronously with security checks"""
        
        # Validate file if requested
        if validate:
            await self._validate_upload(file)
        
        # Generate secure filename
        file_extension = Path(file.filename).suffix.lower()
        secure_filename = f"{hashlib.sha256(f'{file.filename}{time.time()}'.encode()).hexdigest()[:16]}{file_extension}"
        file_path = os.path.join(storage_path, secure_filename)
        
        # Ensure directory exists
        os.makedirs(storage_path, exist_ok=True)
        
        # Save file asynchronously
        file_info = await self._save_file_async(file, file_path)
        
        # Calculate file hash and verify integrity
        file_hash = await self._calculate_hash_async(file_path)
        file_info["file_hash"] = file_hash
        
        # Encrypt file if requested
        if encrypt and settings.ENCRYPTION_ENABLED:
            encrypted_path = await EncryptionService.encrypt_file(file_path)
            if encrypted_path:
                file_info["encrypted"] = True
                file_info["file_path"] = encrypted_path
        
        # Generate file fingerprint for integrity checking
        fingerprint = EncryptionService.create_file_fingerprint(file_info["file_path"])
        file_info["fingerprint"] = fingerprint
        
        return file_info
    
    async def _validate_upload(self, file: UploadFile):
        """Comprehensive file validation"""
        # Basic validation
        validate_file_upload(
            file, 
            settings.ALLOWED_EXTENSIONS, 
            settings.MAX_FILE_SIZE,
            list(self.supported_formats.values())
        )
        
        # Advanced security checks
        await self._check_file_content_security(file)
    
    async def _check_file_content_security(self, file: UploadFile):
        """Advanced file content security checks"""
        import magic
        
        # Read file header for analysis
        file_header = await file.read(2048)
        await file.seek(0)  # Reset file pointer
        
        # Check for embedded executables or suspicious content
        try:
            mime_type = magic.from_buffer(file_header, mime=True)
            
            # Block executable files
            dangerous_mimes = {
                'application/x-executable',
                'application/x-dosexec',
                'application/x-msdownload',
                'application/octet-stream'
            }
            
            if mime_type in dangerous_mimes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Executable files are not allowed"
                )
            
            # Check for script content in documents
            if b'<script' in file_header.lower() or b'javascript:' in file_header.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File contains potentially malicious content"
                )
                
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            # Continue if magic library fails
            pass
    
    async def _save_file_async(self, file: UploadFile, file_path: str) -> Dict[str, Any]:
        """Save file asynchronously with progress tracking"""
        import time
        
        start_time = time.time()
        bytes_written = 0
        
        async with aiofiles.open(file_path, 'wb') as f:
            while chunk := await file.read(8192):  # 8KB chunks
                await f.write(chunk)
                bytes_written += len(chunk)
        
        processing_time = time.time() - start_time
        
        return {
            "file_path": file_path,
            "original_filename": file.filename,
            "file_size": bytes_written,
            "processing_time": round(processing_time, 3),
            "content_type": file.content_type,
            "encrypted": False
        }
    
    async def _calculate_hash_async(self, file_path: str) -> str:
        """Calculate file hash asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.thread_pool,
            EncryptionService.calculate_file_hash,
            file_path
        )
    
    async def batch_process_files(
        self, 
        files: List[UploadFile], 
        storage_path: str,
        max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """Process multiple files concurrently"""
        
        # Create semaphore to limit concurrent operations
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_single_file(file: UploadFile) -> Dict[str, Any]:
            async with semaphore:
                return await self.process_upload_async(file, storage_path)
        
        # Process all files concurrently
        tasks = [process_single_file(file) for file in files]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and return successful results
        successful_results = []
        for result in results:
            if isinstance(result, Exception):
                # Log the error but don't fail the entire batch
                print(f"File processing error: {result}")
            else:
                successful_results.append(result)
        
        return successful_results
    
    async def optimize_file_storage(self) -> Dict[str, Any]:
        """Optimize file storage and cleanup"""
        results = {
            "optimized_files": 0,
            "space_saved": 0,
            "errors": []
        }
        
        # Find duplicate files
        duplicates = await self._find_duplicate_files()
        
        # Remove duplicates
        for duplicate_group in duplicates:
            if len(duplicate_group) > 1:
                # Keep the first file, remove others
                for file_path in duplicate_group[1:]:
                    try:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        results["optimized_files"] += 1
                        results["space_saved"] += file_size
                    except Exception as e:
                        results["errors"].append(str(e))
        
        return results
    
    async def _find_duplicate_files(self) -> List[List[str]]:
        """Find duplicate files by hash"""
        file_hashes = {}
        
        # Check all storage directories
        for directory in [settings.DOCUMENTS_PATH, settings.TEMPLATES_PATH]:
            if os.path.exists(directory):
                for file_path in Path(directory).rglob("*"):
                    if file_path.is_file():
                        file_hash = await self._calculate_hash_async(str(file_path))
                        if file_hash in file_hashes:
                            file_hashes[file_hash].append(str(file_path))
                        else:
                            file_hashes[file_hash] = [str(file_path)]
        
        # Return groups with duplicates
        return [paths for paths in file_hashes.values() if len(paths) > 1]


class FileSecurityService:
    """File security and scanning service"""
    
    @staticmethod
    async def scan_file_for_malware(file_path: str) -> Dict[str, Any]:
        """Basic malware scanning (placeholder for production implementation)"""
        
        # In production, integrate with:
        # - ClamAV for virus scanning
        # - YARA rules for pattern matching
        # - Cloud-based scanning services
        
        scan_result = {
            "is_safe": True,
            "threats_found": [],
            "scan_time": 0.1,
            "scanner": "basic"
        }
        
        try:
            # Basic checks for now
            with open(file_path, 'rb') as f:
                content = f.read(4096)  # Read first 4KB
                
                # Check for suspicious patterns
                suspicious_patterns = [
                    b'eval(',
                    b'exec(',
                    b'<script',
                    b'javascript:',
                    b'vbscript:'
                ]
                
                for pattern in suspicious_patterns:
                    if pattern in content.lower():
                        scan_result["is_safe"] = False
                        scan_result["threats_found"].append(f"Suspicious pattern: {pattern.decode()}")
                        
        except Exception as e:
            scan_result["error"] = str(e)
        
        return scan_result
    
    @staticmethod
    async def quarantine_file(file_path: str, reason: str) -> bool:
        """Move suspicious file to quarantine"""
        try:
            quarantine_dir = os.path.join(settings.STORAGE_PATH, "quarantine")
            os.makedirs(quarantine_dir, exist_ok=True)
            
            quarantine_path = os.path.join(quarantine_dir, f"{int(time.time())}_{os.path.basename(file_path)}")
            os.rename(file_path, quarantine_path)
            
            # Log quarantine action
            AuditService.log_security_event(
                "FILE_QUARANTINED",
                None,
                None,
                {
                    "original_path": file_path,
                    "quarantine_path": quarantine_path,
                    "reason": reason
                }
            )
            
            return True
        except Exception:
            return False


# Global file processing service instance
file_processing_service = FileProcessingService()