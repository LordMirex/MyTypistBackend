"""
Advanced Multi-Layer Caching System
Implements Redis-based intelligent caching with automatic invalidation,
performance optimization, and distributed cache management for enterprise scale.
"""

import json
import time
import hashlib
import asyncio
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
import pickle
import zlib

import redis
from redis import ConnectionPool
from app.services.cache_service import cache_service
from config import settings

# Configure logging
cache_logger = logging.getLogger('advanced_caching')

@dataclass
class CacheMetrics:
    """Cache performance metrics"""
    hit_count: int = 0
    miss_count: int = 0
    total_requests: int = 0
    average_response_time: float = 0.0
    cache_size_bytes: int = 0
    eviction_count: int = 0

@dataclass
class CacheItem:
    """Enhanced cache item with metadata"""
    key: str
    value: Any
    ttl: int
    created_at: datetime
    last_accessed: datetime
    access_count: int
    size_bytes: int
    tags: List[str]
    dependencies: List[str]

class IntelligentCacheInvalidation:
    """
    Intelligent cache invalidation based on data dependencies and patterns
    """
    
    def __init__(self):
        self.dependency_graph = {}
        self.tag_mappings = {}
        self.invalidation_patterns = {}
        
    def register_dependency(self, cache_key: str, dependencies: List[str]):
        """Register cache key dependencies"""
        self.dependency_graph[cache_key] = dependencies
        
        # Register reverse mapping
        for dep in dependencies:
            if dep not in self.tag_mappings:
                self.tag_mappings[dep] = []
            self.tag_mappings[dep].append(cache_key)
    
    def invalidate_by_pattern(self, pattern: str) -> List[str]:
        """Invalidate cache keys matching pattern"""
        invalidated_keys = []
        
        for key in self.dependency_graph.keys():
            if self._matches_pattern(key, pattern):
                invalidated_keys.append(key)
        
        return invalidated_keys
    
    def invalidate_by_tag(self, tag: str) -> List[str]:
        """Invalidate all cache keys associated with tag"""
        return self.tag_mappings.get(tag, [])
    
    def _matches_pattern(self, key: str, pattern: str) -> bool:
        """Check if key matches invalidation pattern"""
        import re
        try:
            return bool(re.match(pattern, key))
        except:
            return pattern in key

class AdvancedCachingSystem:
    """
    Enterprise-grade caching system with intelligent invalidation,
    performance optimization, and distributed cache management
    """
    
    def __init__(self):
        # Initialize Redis connection pool
        self.redis_pool = ConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            max_connections=50,
            retry_on_timeout=True,
            socket_keepalive=True,
            socket_keepalive_options={},
            decode_responses=False  # Keep binary for complex data
        )
        
        self.redis_client = redis.Redis(connection_pool=self.redis_pool)
        
        # Cache layers
        self.memory_cache = {}  # L1 Cache (fastest)
        self.redis_available = self._test_redis_connection()
        
        # Cache management
        self.invalidator = IntelligentCacheInvalidation()
        self.metrics = CacheMetrics()
        
        # Cache configurations
        self.cache_configs = {
            'templates': {
                'ttl': 86400,  # 24 hours
                'max_size_mb': 100,
                'compression': True,
                'tags': ['template', 'document_generation']
            },
            'documents': {
                'ttl': 3600,   # 1 hour
                'max_size_mb': 500,
                'compression': True,
                'tags': ['document', 'user_data']
            },
            'user_profiles': {
                'ttl': 1800,   # 30 minutes
                'max_size_mb': 50,
                'compression': False,
                'tags': ['user', 'profile']
            },
            'processing_results': {
                'ttl': 300,    # 5 minutes
                'max_size_mb': 200,
                'compression': True,
                'tags': ['processing', 'temporary']
            },
            'analytics': {
                'ttl': 7200,   # 2 hours
                'max_size_mb': 100,
                'compression': True,
                'tags': ['analytics', 'statistics']
            }
        }
        
        # Start cache maintenance task
        asyncio.create_task(self._cache_maintenance_loop())
    
    def _test_redis_connection(self) -> bool:
        """Test Redis connection"""
        try:
            self.redis_client.ping()
            cache_logger.info("Redis connection established successfully")
            return True
        except Exception as e:
            cache_logger.warning(f"Redis connection failed: {e}")
            return False
    
    async def get(
        self,
        key: str,
        cache_type: str = 'default',
        default: Any = None
    ) -> Any:
        """
        Get value from multi-layer cache with performance tracking
        """
        request_start = time.time()
        self.metrics.total_requests += 1
        
        try:
            # Layer 1: Memory cache (fastest)
            if key in self.memory_cache:
                cache_item = self.memory_cache[key]
                
                # Check expiration
                if self._is_cache_item_valid(cache_item):
                    cache_item.last_accessed = datetime.utcnow()
                    cache_item.access_count += 1
                    
                    self.metrics.hit_count += 1
                    self._update_response_time(time.time() - request_start)
                    
                    cache_logger.debug(f"Memory cache hit for key: {key}")
                    return cache_item.value
                else:
                    # Remove expired item
                    del self.memory_cache[key]
            
            # Layer 2: Redis cache
            if self.redis_available:
                try:
                    cached_data = self.redis_client.get(key)
                    if cached_data:
                        # Deserialize data
                        value = self._deserialize_cache_data(cached_data, cache_type)
                        
                        # Store in memory cache for faster access
                        await self._store_in_memory_cache(key, value, cache_type)
                        
                        self.metrics.hit_count += 1
                        self._update_response_time(time.time() - request_start)
                        
                        cache_logger.debug(f"Redis cache hit for key: {key}")
                        return value
                        
                except Exception as e:
                    cache_logger.error(f"Redis get error for key {key}: {e}")
            
            # Cache miss
            self.metrics.miss_count += 1
            self._update_response_time(time.time() - request_start)
            
            cache_logger.debug(f"Cache miss for key: {key}")
            return default
            
        except Exception as e:
            cache_logger.error(f"Cache get error: {e}")
            return default
    
    async def set(
        self,
        key: str,
        value: Any,
        cache_type: str = 'default',
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None
    ) -> bool:
        """
        Set value in multi-layer cache with intelligent management
        """
        try:
            config = self.cache_configs.get(cache_type, self.cache_configs['templates'])
            effective_ttl = ttl or config['ttl']
            effective_tags = tags or config.get('tags', [])
            
            # Create cache item
            cache_item = CacheItem(
                key=key,
                value=value,
                ttl=effective_ttl,
                created_at=datetime.utcnow(),
                last_accessed=datetime.utcnow(),
                access_count=0,
                size_bytes=self._estimate_size(value),
                tags=effective_tags,
                dependencies=dependencies or []
            )
            
            # Store in memory cache
            await self._store_in_memory_cache(key, value, cache_type, cache_item)
            
            # Store in Redis cache
            if self.redis_available:
                serialized_data = self._serialize_cache_data(value, config)
                
                try:
                    self.redis_client.setex(key, effective_ttl, serialized_data)
                    
                    # Store metadata
                    metadata = {
                        'created_at': cache_item.created_at.isoformat(),
                        'ttl': effective_ttl,
                        'tags': json.dumps(effective_tags),
                        'size_bytes': cache_item.size_bytes
                    }
                    self.redis_client.hset(f"meta_{key}", mapping=metadata)
                    self.redis_client.expire(f"meta_{key}", effective_ttl)
                    
                except Exception as e:
                    cache_logger.error(f"Redis set error for key {key}: {e}")
            
            # Register dependencies
            if dependencies:
                self.invalidator.register_dependency(key, dependencies)
            
            # Register tags
            for tag in effective_tags:
                self.invalidator.tag_mappings.setdefault(tag, []).append(key)
            
            cache_logger.debug(f"Cache set for key: {key} (TTL: {effective_ttl}s)")
            return True
            
        except Exception as e:
            cache_logger.error(f"Cache set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from all cache layers"""
        try:
            # Remove from memory cache
            if key in self.memory_cache:
                del self.memory_cache[key]
            
            # Remove from Redis
            if self.redis_available:
                self.redis_client.delete(key)
                self.redis_client.delete(f"meta_{key}")
            
            cache_logger.debug(f"Cache delete for key: {key}")
            return True
            
        except Exception as e:
            cache_logger.error(f"Cache delete error: {e}")
            return False
    
    async def invalidate_by_pattern(self, pattern: str) -> int:
        """Invalidate cache keys matching pattern"""
        try:
            invalidated_count = 0
            
            # Invalidate using intelligent system
            keys_to_invalidate = self.invalidator.invalidate_by_pattern(pattern)
            
            for key in keys_to_invalidate:
                if await self.delete(key):
                    invalidated_count += 1
            
            # Also scan Redis for pattern matches
            if self.redis_available:
                try:
                    redis_keys = self.redis_client.keys(pattern)
                    if redis_keys:
                        self.redis_client.delete(*redis_keys)
                        invalidated_count += len(redis_keys)
                except Exception as e:
                    cache_logger.error(f"Redis pattern invalidation error: {e}")
            
            cache_logger.info(f"Invalidated {invalidated_count} keys matching pattern: {pattern}")
            return invalidated_count
            
        except Exception as e:
            cache_logger.error(f"Pattern invalidation error: {e}")
            return 0
    
    async def invalidate_by_tags(self, tags: List[str]) -> int:
        """Invalidate cache keys by tags"""
        try:
            invalidated_count = 0
            
            for tag in tags:
                keys_to_invalidate = self.invalidator.invalidate_by_tag(tag)
                
                for key in keys_to_invalidate:
                    if await self.delete(key):
                        invalidated_count += 1
            
            cache_logger.info(f"Invalidated {invalidated_count} keys for tags: {tags}")
            return invalidated_count
            
        except Exception as e:
            cache_logger.error(f"Tag invalidation error: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        hit_rate = (self.metrics.hit_count / max(self.metrics.total_requests, 1)) * 100
        
        memory_cache_size = sum(
            item.size_bytes for item in self.memory_cache.values()
            if hasattr(item, 'size_bytes')
        )
        
        stats = {
            'hit_rate_percentage': round(hit_rate, 2),
            'total_requests': self.metrics.total_requests,
            'cache_hits': self.metrics.hit_count,
            'cache_misses': self.metrics.miss_count,
            'average_response_time_ms': round(self.metrics.average_response_time * 1000, 2),
            'memory_cache_items': len(self.memory_cache),
            'memory_cache_size_mb': round(memory_cache_size / (1024 * 1024), 2),
            'redis_available': self.redis_available,
            'eviction_count': self.metrics.eviction_count
        }
        
        # Add Redis stats if available
        if self.redis_available:
            try:
                redis_info = self.redis_client.info('memory')
                stats['redis_memory_usage_mb'] = round(
                    int(redis_info.get('used_memory', 0)) / (1024 * 1024), 2
                )
                stats['redis_connected_clients'] = self.redis_client.info().get('connected_clients', 0)
            except Exception:
                pass
        
        return stats
    
    async def warm_cache(
        self,
        warm_functions: Dict[str, Callable],
        cache_types: List[str] = None
    ) -> Dict[str, Any]:
        """
        Warm cache with frequently accessed data
        """
        cache_types = cache_types or ['templates', 'user_profiles']
        warmed_items = 0
        errors = []
        
        cache_logger.info(f"Starting cache warming for types: {cache_types}")
        
        try:
            for cache_type in cache_types:
                if cache_type in warm_functions:
                    warm_function = warm_functions[cache_type]
                    
                    try:
                        # Execute warming function
                        warm_data = await warm_function() if asyncio.iscoroutinefunction(warm_function) else warm_function()
                        
                        # Store warmed data
                        if isinstance(warm_data, dict):
                            for key, value in warm_data.items():
                                await self.set(key, value, cache_type)
                                warmed_items += 1
                        
                    except Exception as e:
                        error_msg = f"Error warming {cache_type}: {e}"
                        errors.append(error_msg)
                        cache_logger.error(error_msg)
            
            cache_logger.info(f"Cache warming completed: {warmed_items} items warmed")
            
            return {
                'warmed_items': warmed_items,
                'errors': errors,
                'success': len(errors) == 0
            }
            
        except Exception as e:
            cache_logger.error(f"Cache warming failed: {e}")
            return {'warmed_items': 0, 'errors': [str(e)], 'success': False}
    
    async def _store_in_memory_cache(
        self,
        key: str,
        value: Any,
        cache_type: str,
        cache_item: Optional[CacheItem] = None
    ):
        """Store item in memory cache with size management"""
        config = self.cache_configs.get(cache_type, self.cache_configs['templates'])
        max_size_bytes = config['max_size_mb'] * 1024 * 1024
        
        if not cache_item:
            cache_item = CacheItem(
                key=key,
                value=value,
                ttl=config['ttl'],
                created_at=datetime.utcnow(),
                last_accessed=datetime.utcnow(),
                access_count=0,
                size_bytes=self._estimate_size(value),
                tags=config.get('tags', []),
                dependencies=[]
            )
        
        # Check if we need to evict items
        current_size = sum(item.size_bytes for item in self.memory_cache.values())
        
        if current_size + cache_item.size_bytes > max_size_bytes:
            await self._evict_memory_cache_items(cache_item.size_bytes)
        
        self.memory_cache[key] = cache_item
    
    async def _evict_memory_cache_items(self, needed_space: int):
        """Evict least recently used items from memory cache"""
        if not self.memory_cache:
            return
        
        # Sort by last accessed time (LRU)
        sorted_items = sorted(
            self.memory_cache.items(),
            key=lambda x: x[1].last_accessed
        )
        
        freed_space = 0
        evicted_count = 0
        
        for key, cache_item in sorted_items:
            if freed_space >= needed_space:
                break
                
            freed_space += cache_item.size_bytes
            del self.memory_cache[key]
            evicted_count += 1
        
        self.metrics.eviction_count += evicted_count
        cache_logger.debug(f"Evicted {evicted_count} items, freed {freed_space} bytes")
    
    def _is_cache_item_valid(self, cache_item: CacheItem) -> bool:
        """Check if cache item is still valid"""
        if cache_item.ttl <= 0:  # No expiration
            return True
            
        expiration_time = cache_item.created_at + timedelta(seconds=cache_item.ttl)
        return datetime.utcnow() < expiration_time
    
    def _serialize_cache_data(self, value: Any, config: Dict[str, Any]) -> bytes:
        """Serialize data for cache storage"""
        # Serialize using pickle
        serialized = pickle.dumps(value)
        
        # Compress if configured
        if config.get('compression', False):
            serialized = zlib.compress(serialized)
        
        return serialized
    
    def _deserialize_cache_data(self, data: bytes, cache_type: str) -> Any:
        """Deserialize data from cache storage"""
        config = self.cache_configs.get(cache_type, self.cache_configs['templates'])
        
        try:
            # Decompress if configured
            if config.get('compression', False):
                data = zlib.decompress(data)
            
            # Deserialize using pickle
            return pickle.loads(data)
            
        except Exception as e:
            cache_logger.error(f"Deserialization error: {e}")
            raise
    
    def _estimate_size(self, value: Any) -> int:
        """Estimate memory size of value"""
        try:
            return len(pickle.dumps(value))
        except:
            # Fallback estimation
            if isinstance(value, str):
                return len(value.encode('utf-8'))
            elif isinstance(value, (list, tuple)):
                return sum(self._estimate_size(item) for item in value)
            elif isinstance(value, dict):
                return sum(
                    self._estimate_size(k) + self._estimate_size(v) 
                    for k, v in value.items()
                )
            else:
                return 128  # Default estimate
    
    def _update_response_time(self, response_time: float):
        """Update average response time"""
        if self.metrics.total_requests == 1:
            self.metrics.average_response_time = response_time
        else:
            # Exponential moving average
            alpha = 0.1
            self.metrics.average_response_time = (
                alpha * response_time + 
                (1 - alpha) * self.metrics.average_response_time
            )
    
    async def _cache_maintenance_loop(self):
        """Background cache maintenance and optimization"""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                # Clean expired items from memory cache
                expired_keys = []
                for key, cache_item in self.memory_cache.items():
                    if not self._is_cache_item_valid(cache_item):
                        expired_keys.append(key)
                
                for key in expired_keys:
                    del self.memory_cache[key]
                
                if expired_keys:
                    cache_logger.debug(f"Cleaned {len(expired_keys)} expired items from memory cache")
                
                # Log cache statistics
                stats = self.get_cache_stats()
                cache_logger.info(f"Cache stats - Hit rate: {stats['hit_rate_percentage']}%, "
                                f"Memory items: {stats['memory_cache_items']}, "
                                f"Size: {stats['memory_cache_size_mb']}MB")
                
            except Exception as e:
                cache_logger.error(f"Cache maintenance error: {e}")

# Template-specific caching functions
async def get_template_with_cache(template_id: int, db_session) -> Optional[Any]:
    """Get template with intelligent caching"""
    cache_key = f"template_{template_id}"
    
    # Try cache first
    cached_template = await advanced_cache.get(cache_key, 'templates')
    if cached_template:
        return cached_template
    
    # Load from database
    from app.models.template import Template
    template = db_session.query(Template).filter(Template.id == template_id).first()
    
    if template:
        # Cache for future use
        await advanced_cache.set(
            cache_key, 
            template, 
            'templates',
            tags=['template', f'template_{template_id}'],
            dependencies=[f'user_{template.created_by}']
        )
    
    return template

# Global advanced caching instance
advanced_cache = AdvancedCachingSystem()