from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
import time
from collections import defaultdict, deque
from typing import Dict, Deque
import asyncio
from .config import settings

class RateLimiter:
    def __init__(self):
        # Store request timestamps for each IP
        self.requests: Dict[str, Deque[float]] = defaultdict(deque)
        self.cleanup_task = None
        
    def is_allowed(self, identifier: str, max_requests: int = None, window_seconds: int = None) -> bool:
        """Check if request is allowed based on rate limiting"""
        max_requests = max_requests or settings.RATE_LIMIT_REQUESTS
        window_seconds = window_seconds or settings.RATE_LIMIT_WINDOW
        
        now = time.time()
        window_start = now - window_seconds
        
        # Get request history for this identifier
        request_times = self.requests[identifier]
        
        # Remove old requests outside the window
        while request_times and request_times[0] < window_start:
            request_times.popleft()
        
        # Check if limit exceeded
        if len(request_times) >= max_requests:
            return False
        
        # Add current request
        request_times.append(now)
        return True
    
    def get_reset_time(self, identifier: str, window_seconds: int = None) -> int:
        """Get when the rate limit will reset for this identifier"""
        window_seconds = window_seconds or settings.RATE_LIMIT_WINDOW
        request_times = self.requests.get(identifier, deque())
        
        if not request_times:
            return 0
        
        oldest_request = request_times[0]
        reset_time = int(oldest_request + window_seconds)
        return max(0, reset_time - int(time.time()))
    
    async def cleanup_old_entries(self):
        """Periodically cleanup old entries to prevent memory leaks"""
        while True:
            try:
                now = time.time()
                window_start = now - settings.RATE_LIMIT_WINDOW
                
                # Clean up old entries
                for identifier in list(self.requests.keys()):
                    request_times = self.requests[identifier]
                    
                    # Remove old requests
                    while request_times and request_times[0] < window_start:
                        request_times.popleft()
                    
                    # Remove empty deques
                    if not request_times:
                        del self.requests[identifier]
                
                # Sleep for 5 minutes before next cleanup
                await asyncio.sleep(300)
                
            except Exception as e:
                print(f"❌ Rate limiter cleanup error: {e}")
                await asyncio.sleep(60)  # Retry after 1 minute on error

# Global rate limiter instance
rate_limiter = RateLimiter()

def get_client_ip(request: Request) -> str:
    """Get client IP address from request"""
    # Check for forwarded IP (behind proxy/load balancer)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    # Check for real IP (behind proxy)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fallback to direct connection IP
    return request.client.host if request.client else "unknown"

async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware"""
    # Skip rate limiting for health checks and static files
    if request.url.path in ["/health"] or request.url.path.startswith("/static"):
        return await call_next(request)
    
    client_ip = get_client_ip(request)
    
    # Different limits for different endpoints
    if request.url.path.startswith("/api/auth/"):
        # Stricter limits for auth endpoints
        max_requests = 10
        window_seconds = 900  # 15 minutes
    elif request.url.path.startswith("/api/admin/"):
        # Moderate limits for admin endpoints
        max_requests = 50
        window_seconds = 3600  # 1 hour
    else:
        # Default limits for other API endpoints
        max_requests = settings.RATE_LIMIT_REQUESTS
        window_seconds = settings.RATE_LIMIT_WINDOW
    
    if not rate_limiter.is_allowed(client_ip, max_requests, window_seconds):
        reset_time = rate_limiter.get_reset_time(client_ip, window_seconds)
        
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "message": f"Too many requests. Try again in {reset_time} seconds.",
                "retry_after": reset_time
            },
            headers={
                "Retry-After": str(reset_time),
                "X-RateLimit-Limit": str(max_requests),
                "X-RateLimit-Window": str(window_seconds)
            }
        )
    
    return await call_next(request)

# Start cleanup task
async def start_rate_limiter_cleanup():
    """Start the rate limiter cleanup background task"""
    if not rate_limiter.cleanup_task:
        rate_limiter.cleanup_task = asyncio.create_task(rate_limiter.cleanup_old_entries())