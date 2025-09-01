"""
Performance testing and validation
"""

import time
import asyncio
import statistics
from typing import List, Dict, Any
import httpx
import pytest
from fastapi.testclient import TestClient

from main import app
from app.services.cache_service import cache_service
from database import DatabaseManager


class PerformanceValidator:
    """Performance validation and benchmarking"""
    
    def __init__(self):
        self.client = TestClient(app)
    
    async def test_response_times(self) -> Dict[str, Any]:
        """Test API response times"""
        endpoints = [
            "/health",
            "/api/monitoring/health",
            "/api/auth/me",
            "/api/templates",
            "/api/documents"
        ]
        
        results = {}
        
        for endpoint in endpoints:
            times = []
            for _ in range(10):  # 10 requests per endpoint
                start = time.time()
                try:
                    response = self.client.get(endpoint)
                    times.append((time.time() - start) * 1000)  # Convert to ms
                except Exception as e:
                    times.append(float('inf'))
            
            results[endpoint] = {
                "avg_response_time": round(statistics.mean(times), 2),
                "min_response_time": round(min(times), 2),
                "max_response_time": round(max(times), 2),
                "p95_response_time": round(statistics.quantiles(times, n=20)[18], 2) if len(times) > 5 else 0
            }
        
        return results
    
    async def test_concurrent_requests(self, endpoint: str = "/health", concurrent: int = 10) -> Dict[str, Any]:
        """Test concurrent request handling"""
        async def make_request():
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                start = time.time()
                response = await client.get(endpoint)
                return {
                    "status_code": response.status_code,
                    "response_time": (time.time() - start) * 1000
                }
        
        # Make concurrent requests
        start_time = time.time()
        tasks = [make_request() for _ in range(concurrent)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        # Analyze results
        successful = [r for r in results if isinstance(r, dict) and r["status_code"] == 200]
        failed = [r for r in results if not isinstance(r, dict) or r["status_code"] != 200]
        
        response_times = [r["response_time"] for r in successful]
        
        return {
            "total_requests": concurrent,
            "successful_requests": len(successful),
            "failed_requests": len(failed),
            "total_time": round(total_time * 1000, 2),
            "requests_per_second": round(concurrent / total_time, 2),
            "avg_response_time": round(statistics.mean(response_times), 2) if response_times else 0,
            "errors": [str(e) for e in results if isinstance(e, Exception)]
        }
    
    async def test_database_performance(self) -> Dict[str, Any]:
        """Test database performance"""
        db = DatabaseManager.get_session()
        
        # Test simple queries
        simple_query_times = []
        for _ in range(10):
            start = time.time()
            db.execute("SELECT 1")
            simple_query_times.append((time.time() - start) * 1000)
        
        # Test complex queries (if tables exist)
        complex_query_times = []
        try:
            for _ in range(5):
                start = time.time()
                db.execute("SELECT COUNT(*) FROM users")
                complex_query_times.append((time.time() - start) * 1000)
        except Exception:
            # Tables might not exist yet
            complex_query_times = [0]
        
        db.close()
        
        return {
            "simple_query_avg": round(statistics.mean(simple_query_times), 2),
            "complex_query_avg": round(statistics.mean(complex_query_times), 2),
            "pool_status": DatabaseManager.get_pool_status()
        }
    
    async def test_cache_performance(self) -> Dict[str, Any]:
        """Test cache performance"""
        if not cache_service.redis:
            return {"error": "Cache service not available"}
        
        # Test cache write performance
        write_times = []
        for i in range(100):
            start = time.time()
            await cache_service.set(f"test_key_{i}", {"data": f"value_{i}"}, expire=60)
            write_times.append((time.time() - start) * 1000)
        
        # Test cache read performance
        read_times = []
        for i in range(100):
            start = time.time()
            await cache_service.get(f"test_key_{i}")
            read_times.append((time.time() - start) * 1000)
        
        # Cleanup test keys
        for i in range(100):
            await cache_service.delete(f"test_key_{i}")
        
        return {
            "write_avg_ms": round(statistics.mean(write_times), 2),
            "read_avg_ms": round(statistics.mean(read_times), 2),
            "operations_tested": 200
        }
    
    async def run_full_performance_suite(self) -> Dict[str, Any]:
        """Run complete performance test suite"""
        print("🏃‍♂️ Running comprehensive performance tests...")
        
        results = {
            "timestamp": time.time(),
            "test_suite": "MyTypist Performance Validation"
        }
        
        # API response time tests
        print("  Testing API response times...")
        results["api_performance"] = await self.test_response_times()
        
        # Concurrent request handling
        print("  Testing concurrent request handling...")
        results["concurrency_test"] = await self.test_concurrent_requests()
        
        # Database performance
        print("  Testing database performance...")
        results["database_performance"] = await self.test_database_performance()
        
        # Cache performance
        print("  Testing cache performance...")
        results["cache_performance"] = await self.test_cache_performance()
        
        print("✅ Performance tests completed")
        return results


# Validation thresholds for production readiness
PERFORMANCE_THRESHOLDS = {
    "max_response_time": 500,  # ms
    "min_requests_per_second": 100,
    "max_db_query_time": 50,   # ms
    "max_cache_operation_time": 5  # ms
}


async def validate_production_readiness() -> bool:
    """Validate that the system meets production performance requirements"""
    validator = PerformanceValidator()
    results = await validator.run_full_performance_suite()
    
    issues = []
    
    # Check API performance
    api_perf = results.get("api_performance", {})
    for endpoint, stats in api_perf.items():
        if stats.get("avg_response_time", float('inf')) > PERFORMANCE_THRESHOLDS["max_response_time"]:
            issues.append(f"Slow response time for {endpoint}: {stats['avg_response_time']}ms")
    
    # Check concurrency
    concurrency = results.get("concurrency_test", {})
    rps = concurrency.get("requests_per_second", 0)
    if rps < PERFORMANCE_THRESHOLDS["min_requests_per_second"]:
        issues.append(f"Low concurrent request handling: {rps} RPS")
    
    # Check database performance
    db_perf = results.get("database_performance", {})
    if db_perf.get("simple_query_avg", float('inf')) > PERFORMANCE_THRESHOLDS["max_db_query_time"]:
        issues.append(f"Slow database queries: {db_perf['simple_query_avg']}ms")
    
    # Check cache performance
    cache_perf = results.get("cache_performance", {})
    if cache_perf.get("read_avg_ms", float('inf')) > PERFORMANCE_THRESHOLDS["max_cache_operation_time"]:
        issues.append(f"Slow cache operations: {cache_perf['read_avg_ms']}ms")
    
    if issues:
        print("❌ Production readiness validation failed:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    else:
        print("✅ System meets all production performance requirements")
        return True


if __name__ == "__main__":
    """Run performance validation"""
    async def main():
        validator = PerformanceValidator()
        results = await validator.run_full_performance_suite()
        print("\n📊 Performance Test Results:")
        for test_name, test_results in results.items():
            print(f"  {test_name}: {test_results}")
        
        # Validate production readiness
        await validate_production_readiness()
    
    asyncio.run(main())