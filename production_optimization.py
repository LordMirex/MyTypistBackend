"""
Production optimization utilities and startup scripts
"""

import os
import sys
import asyncio
import time
from pathlib import Path

import uvloop
from database import DatabaseManager
from app.services.cache_service import cache_service
from config import settings


class ProductionOptimizer:
    """Production environment optimization"""
    
    @staticmethod
    def setup_uvloop():
        """Install uvloop for better async performance"""
        try:
            uvloop.install()
            print("✅ uvloop installed for high-performance async operations")
            return True
        except ImportError:
            print("⚠️ uvloop not available, using default asyncio event loop")
            return False
    
    @staticmethod
    def ensure_directories():
        """Ensure all required directories exist"""
        directories = [
            settings.STORAGE_PATH,
            settings.TEMPLATES_PATH,
            settings.DOCUMENTS_PATH,
            settings.SIGNATURES_PATH,
            settings.UPLOADS_PATH,
            settings.QUARANTINE_PATH
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            print(f"✅ Directory ensured: {directory}")
    
    @staticmethod
    async def warm_up_cache():
        """Pre-warm critical cache entries"""
        try:
            await cache_service.initialize()
            
            # Pre-cache common template placeholders
            common_templates = [1, 2, 3]  # Template IDs
            for template_id in common_templates:
                cache_key = f"template_placeholders:{template_id}"
                await cache_service.set(cache_key, [], expire=86400)
            
            print("✅ Cache warmed up with common entries")
            return True
        except Exception as e:
            print(f"⚠️ Cache warm-up failed: {e}")
            return False
    
    @staticmethod
    def optimize_database():
        """Run database optimization tasks"""
        try:
            DatabaseManager.optimize_database()
            print("✅ Database optimized and analyzed")
            return True
        except Exception as e:
            print(f"⚠️ Database optimization failed: {e}")
            return False
    
    @staticmethod
    async def run_startup_optimizations():
        """Run all startup optimizations"""
        print("🚀 Running production startup optimizations...")
        
        # Setup high-performance event loop
        ProductionOptimizer.setup_uvloop()
        
        # Ensure directories
        ProductionOptimizer.ensure_directories()
        
        # Warm up cache
        await ProductionOptimizer.warm_up_cache()
        
        # Optimize database
        ProductionOptimizer.optimize_database()
        
        print("✅ Production optimizations complete")


class PerformanceMonitor:
    """Monitor system performance metrics"""
    
    @staticmethod
    def log_startup_metrics():
        """Log system metrics at startup"""
        try:
            import psutil
            
            cpu_count = psutil.cpu_count()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            metrics = {
                "cpu_cores": cpu_count,
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "disk_total_gb": round(disk.total / (1024**3), 2),
                "disk_free_gb": round(disk.free / (1024**3), 2)
            }
            
            print("📊 System Metrics:")
            for key, value in metrics.items():
                print(f"   {key}: {value}")
                
            return metrics
        except ImportError:
            print("⚠️ psutil not available for system metrics")
            return {}
    
    @staticmethod
    async def benchmark_performance():
        """Run basic performance benchmarks"""
        print("🏃‍♂️ Running performance benchmarks...")
        
        # Database benchmark
        start_time = time.time()
        try:
            db = DatabaseManager.get_session()
            db.execute("SELECT 1")
            db.close()
            db_time = (time.time() - start_time) * 1000
            print(f"   Database query: {db_time:.2f}ms")
        except Exception as e:
            print(f"   Database benchmark failed: {e}")
        
        # Cache benchmark
        start_time = time.time()
        try:
            await cache_service.set("benchmark", "test", expire=60)
            await cache_service.get("benchmark")
            cache_time = (time.time() - start_time) * 1000
            print(f"   Cache operation: {cache_time:.2f}ms")
        except Exception as e:
            print(f"   Cache benchmark failed: {e}")
        
        print("✅ Performance benchmarks complete")


if __name__ == "__main__":
    """Run optimization script"""
    asyncio.run(ProductionOptimizer.run_startup_optimizations())