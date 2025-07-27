from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time
import uuid
from .rate_limiter import rate_limit_middleware

class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for headers and basic protection"""
    
    async def dispatch(self, request: Request, call_next):
        # Add request ID for tracking
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Apply rate limiting
        response = await rate_limit_middleware(request, call_next)
        
        # Add security headers
        if hasattr(response, 'headers'):
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            
            # Add HSTS header for HTTPS
            if request.url.scheme == "https":
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response

class LoggingMiddleware(BaseHTTPMiddleware):
    """Logging middleware for request/response tracking"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log request
        client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
        print(f"📥 {request.method} {request.url.path} - IP: {client_ip}")
        
        try:
            response = await call_next(request)
            
            # Log response
            process_time = time.time() - start_time
            print(f"📤 {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.3f}s")
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            print(f"❌ {request.method} {request.url.path} - Error: {str(e)} - Time: {process_time:.3f}s")
            raise

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Global error handling middleware"""
    
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except HTTPException:
            # Let FastAPI handle HTTP exceptions
            raise
        except Exception as e:
            # Log unexpected errors
            request_id = getattr(request.state, 'request_id', 'unknown')
            print(f"❌ Unexpected error (Request ID: {request_id}): {str(e)}")
            
            # Return generic error response
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "message": "An unexpected error occurred. Please try again later.",
                    "request_id": request_id
                }
            )