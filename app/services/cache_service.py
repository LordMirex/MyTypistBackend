"""
Advanced Redis caching service for high-performance document generation
"""

import json
import gzip
import base64
import hashlib
import pickle
from typing import Any, Dict, List, Optional, Union
from functools import wraps
from datetime import datetime, timedelta

import redis.asyncio as aioredis
from config import settings


class CacheService:
    """Advanced Redis caching service"""
    
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.compression_threshold = 1024  # Compress data > 1KB
    
    async def initialize(self):
        """Initialize Redis connection"""
        try:
            self.redis = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=False,  # Keep binary for compression
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                socket_keepalive_options={},
                max_connections=20
            )
            await self.redis.ping()
            return True
        except Exception as e:
            print(f"Redis initialization failed: {e}")
            return False
    
    def _serialize_data(self, data: Any) -> bytes:
        """Serialize and optionally compress data"""
        try:
            # Serialize to JSON first
            json_data = json.dumps(data, default=str).encode('utf-8')
            
            # Compress if data is large enough
            if len(json_data) > self.compression_threshold:
                compressed = gzip.compress(json_data)
                # Mark as compressed with prefix
                return b'GZIP:' + compressed
            else:
                return b'JSON:' + json_data
                
        except Exception:
            # Fallback to pickle for complex objects
            pickled = pickle.dumps(data)
            if len(pickled) > self.compression_threshold:
                compressed = gzip.compress(pickled)
                return b'GZIP_PICKLE:' + compressed
            else:
                return b'PICKLE:' + pickled
    
    def _deserialize_data(self, data: bytes) -> Any:
        """Deserialize and decompress data"""
        try:
            if data.startswith(b'GZIP:'):
                decompressed = gzip.decompress(data[5:])
                return json.loads(decompressed.decode('utf-8'))
            elif data.startswith(b'JSON:'):
                return json.loads(data[5:].decode('utf-8'))
            elif data.startswith(b'GZIP_PICKLE:'):
                decompressed = gzip.decompress(data[12:])
                return pickle.loads(decompressed)
            elif data.startswith(b'PICKLE:'):
                return pickle.loads(data[7:])
            else:
                # Legacy format
                return json.loads(data.decode('utf-8'))
        except Exception:
            return None
    
    async def set(self, key: str, value: Any, expire: int = 300, tags: List[str] = None) -> bool:
        """Set cache with optional tags for invalidation"""
        if not self.redis:
            return False
        
        try:
            serialized = self._serialize_data(value)
            success = await self.redis.setex(key, expire, serialized)
            
            # Add tags for grouped invalidation
            if tags and success:
                for tag in tags:
                    await self.redis.sadd(f"tag:{tag}", key)
                    await self.redis.expire(f"tag:{tag}", expire + 60)
            
            return success
        except Exception:
            return False
    
    async def get(self, key: str) -> Any:
        """Get cached value"""
        if not self.redis:
            return None
        
        try:
            data = await self.redis.get(key)
            if data is None:
                return None
            return self._deserialize_data(data)
        except Exception:
            return None
    
    async def delete(self, key: str) -> bool:
        """Delete cached value"""
        if not self.redis:
            return False
        
        try:
            return await self.redis.delete(key) > 0
        except Exception:
            return False
    
    async def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all cache entries with specific tag"""
        if not self.redis:
            return 0
        
        try:
            keys = await self.redis.smembers(f"tag:{tag}")
            if keys:
                deleted = await self.redis.delete(*keys)
                await self.redis.delete(f"tag:{tag}")
                return deleted
            return 0
        except Exception:
            return 0
    
    async def mget(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple cache values"""
        if not self.redis or not keys:
            return {}
        
        try:
            values = await self.redis.mget(keys)
            result = {}
            for key, value in zip(keys, values):
                if value is not None:
                    result[key] = self._deserialize_data(value)
            return result
        except Exception:
            return {}
    
    async def mset(self, mapping: Dict[str, Any], expire: int = 300) -> bool:
        """Set multiple cache values"""
        if not self.redis or not mapping:
            return False
        
        try:
            pipe = self.redis.pipeline()
            for key, value in mapping.items():
                serialized = self._serialize_data(value)
                pipe.setex(key, expire, serialized)
            
            results = await pipe.execute()
            return all(results)
        except Exception:
            return False


# Global cache instance
cache_service = CacheService()


def cache_response(expire: int = 300, key_prefix: str = "api", tags: List[str] = None):
    """Decorator for caching API responses"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function and parameters
            params_hash = hashlib.md5(str(sorted(kwargs.items())).encode()).hexdigest()
            cache_key = f"{key_prefix}:{func.__name__}:{params_hash}"
            
            # Try cache first
            cached = await cache_service.get(cache_key)
            if cached is not None:
                return cached
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            await cache_service.set(cache_key, result, expire, tags or [])
            return result
        return wrapper
    return decorator


def cache_query(expire: int = 600, key_prefix: str = "query"):
    """Decorator for caching database query results"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key from query parameters
            query_hash = hashlib.md5(str(args + tuple(sorted(kwargs.items()))).encode()).hexdigest()
            cache_key = f"{key_prefix}:{func.__name__}:{query_hash}"
            
            # Try cache first
            cached = await cache_service.get(cache_key)
            if cached is not None:
                return cached
            
            # Execute query
            result = await func(*args, **kwargs)
            
            # Cache result
            await cache_service.set(cache_key, result, expire)
            return result
        return wrapper
    return decorator


class DocumentCache:
    """Specialized caching for document generation"""
    
    @staticmethod
    async def cache_template_placeholders(template_id: int, placeholders: List[Dict]) -> bool:
        """Cache template placeholders for faster document generation"""
        cache_key = f"template_placeholders:{template_id}"
        return await cache_service.set(cache_key, placeholders, expire=86400)  # 24 hours
    
    @staticmethod
    async def get_template_placeholders(template_id: int) -> Optional[List[Dict]]:
        """Get cached template placeholders"""
        cache_key = f"template_placeholders:{template_id}"
        return await cache_service.get(cache_key)
    
    @staticmethod
    async def cache_generated_document(doc_hash: str, document_data: Dict, expire: int = 3600) -> bool:
        """Cache generated document"""
        cache_key = f"generated_doc:{doc_hash}"
        tags = ["documents", f"user:{document_data.get('user_id')}"]
        return await cache_service.set(cache_key, document_data, expire, tags)
    
    @staticmethod
    async def get_generated_document(doc_hash: str) -> Optional[Dict]:
        """Get cached generated document"""
        cache_key = f"generated_doc:{doc_hash}"
        return await cache_service.get(cache_key)
    
    @staticmethod
    async def invalidate_user_documents(user_id: int) -> int:
        """Invalidate all cached documents for a user"""
        return await cache_service.invalidate_by_tag(f"user:{user_id}")


class UserCache:
    """User-specific caching utilities"""
    
    @staticmethod
    async def cache_user_profile(user_id: int, profile_data: Dict, expire: int = 1800) -> bool:
        """Cache user profile data"""
        cache_key = f"user_profile:{user_id}"
        return await cache_service.set(cache_key, profile_data, expire)
    
    @staticmethod
    async def get_user_profile(user_id: int) -> Optional[Dict]:
        """Get cached user profile"""
        cache_key = f"user_profile:{user_id}"
        return await cache_service.get(cache_key)
    
    @staticmethod
    async def cache_user_permissions(user_id: int, permissions: List[str], expire: int = 3600) -> bool:
        """Cache user permissions for faster authorization"""
        cache_key = f"user_permissions:{user_id}"
        return await cache_service.set(cache_key, permissions, expire)
    
    @staticmethod
    async def get_user_permissions(user_id: int) -> Optional[List[str]]:
        """Get cached user permissions"""
        cache_key = f"user_permissions:{user_id}"
        return await cache_service.get(cache_key)
    
    @staticmethod
    async def invalidate_user_cache(user_id: int) -> int:
        """Invalidate all user-related cache"""
        keys_to_delete = [
            f"user_profile:{user_id}",
            f"user_permissions:{user_id}",
            f"user_settings:{user_id}"
        ]
        deleted = 0
        for key in keys_to_delete:
            if await cache_service.delete(key):
                deleted += 1
        return deleted