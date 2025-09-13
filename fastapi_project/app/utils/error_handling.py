"""
Standardized error handling utilities for consistent error management.

This module provides:
- Custom error classes with context
- Centralized error logging
- User-friendly error messages
- Error monitoring integration points
"""

import logging
from datetime import datetime, UTC
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)

class ErrorCode(Enum):
    """Standardized error codes for consistent error handling"""
    
    # Network/API errors
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    RATE_LIMIT_ERROR = "RATE_LIMIT_ERROR"
    
    # Authentication/Authorization
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    
    # Validation errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    BUSINESS_RULE_ERROR = "BUSINESS_RULE_ERROR"
    CONSTRAINT_ERROR = "CONSTRAINT_ERROR"
    
    # Resource errors
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    GONE = "GONE"
    
    # Server errors
    SERVER_ERROR = "SERVER_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    
    # Application-specific errors
    WHEEL_STRATEGY_ERROR = "WHEEL_STRATEGY_ERROR"
    PRICE_FETCH_ERROR = "PRICE_FETCH_ERROR"
    LOT_ASSEMBLY_ERROR = "LOT_ASSEMBLY_ERROR"

class AppError(Exception):
    """
    Custom application error with structured information.
    
    Provides consistent error handling across the application with:
    - Error codes for programmatic handling
    - Context for debugging
    - User-friendly messages
    - Timestamps for logging
    """
    
    def __init__(
        self, 
        message: str, 
        code: ErrorCode = ErrorCode.SERVER_ERROR,
        context: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
        status_code: int = 500
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.context = context or {}
        self.user_message = user_message or self._get_default_user_message(code)
        self.status_code = status_code
        self.timestamp = datetime.now(UTC).isoformat()
        
    def _get_default_user_message(self, code: ErrorCode) -> str:
        """Generate user-friendly messages for error codes"""
        messages = {
            ErrorCode.NETWORK_ERROR: "Network connection failed. Please check your internet connection.",
            ErrorCode.UNAUTHORIZED: "Please log in to continue.",
            ErrorCode.FORBIDDEN: "You don't have permission to perform this action.",
            ErrorCode.NOT_FOUND: "The requested resource was not found.",
            ErrorCode.VALIDATION_ERROR: "Please check your input and try again.",
            ErrorCode.BUSINESS_RULE_ERROR: "This action violates business rules.",
            ErrorCode.SERVER_ERROR: "An unexpected error occurred. Please try again.",
            ErrorCode.DATABASE_ERROR: "Database operation failed. Please try again.",
            ErrorCode.PRICE_FETCH_ERROR: "Unable to fetch current prices. Please try again.",
            ErrorCode.WHEEL_STRATEGY_ERROR: "Wheel strategy operation failed.",
            ErrorCode.LOT_ASSEMBLY_ERROR: "Unable to assemble lots. Please check your events."
        }
        return messages.get(code, "An unexpected error occurred.")
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for JSON serialization"""
        return {
            "message": self.message,
            "code": self.code.value,
            "user_message": self.user_message,
            "context": self.context,
            "timestamp": self.timestamp,
            "status_code": self.status_code
        }
        
    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"

class ValidationError(AppError):
    """Specific error for validation failures"""
    
    def __init__(self, message: str, field: str = None, value: Any = None):
        context = {}
        if field:
            context["field"] = field
        if value is not None:
            context["value"] = str(value)
            
        super().__init__(
            message=message,
            code=ErrorCode.VALIDATION_ERROR,
            context=context,
            status_code=400
        )

class BusinessRuleError(AppError):
    """Error for business rule violations"""
    
    def __init__(self, message: str, rule: str = None):
        context = {}
        if rule:
            context["rule"] = rule
            
        super().__init__(
            message=message,
            code=ErrorCode.BUSINESS_RULE_ERROR,
            context=context,
            status_code=422
        )

class ResourceNotFoundError(AppError):
    """Error for missing resources"""
    
    def __init__(self, resource_type: str, resource_id: Any):
        message = f"{resource_type} with ID {resource_id} not found"
        context = {
            "resource_type": resource_type,
            "resource_id": str(resource_id)
        }
        
        super().__init__(
            message=message,
            code=ErrorCode.NOT_FOUND,
            context=context,
            status_code=404
        )

def log_error(error: AppError, request_id: str = None) -> None:
    """
    Log error with structured information for monitoring.
    
    In production, this would integrate with error monitoring services
    like Sentry, DataDog, or CloudWatch.
    """
    log_data = {
        "error_code": error.code.value,
        "message": error.message,
        "context": error.context,
        "timestamp": error.timestamp,
        "request_id": request_id
    }
    
    # Log at appropriate level based on error type
    if error.status_code >= 500:
        logger.error("Server error occurred", extra=log_data)
    elif error.status_code >= 400:
        logger.warning("Client error occurred", extra=log_data)
    else:
        logger.info("Error handled", extra=log_data)
    
    # In production, send to monitoring service
    # send_to_monitoring_service(log_data)

def handle_api_error(error: Exception, context: Dict[str, Any] = None) -> AppError:
    """
    Convert various exception types to structured AppError.
    
    This provides a central place to map different exception types
    to our standardized error format.
    """
    context = context or {}
    
    # Handle specific exception types
    if isinstance(error, AppError):
        return error
        
    if hasattr(error, 'status_code'):
        # Handle HTTP errors from requests
        status_code = error.status_code
        
        if status_code == 401:
            return AppError(
                message="Authentication failed",
                code=ErrorCode.UNAUTHORIZED,
                context=context,
                status_code=401
            )
        elif status_code == 403:
            return AppError(
                message="Access forbidden",
                code=ErrorCode.FORBIDDEN,
                context=context,
                status_code=403
            )
        elif status_code == 404:
            return AppError(
                message="Resource not found",
                code=ErrorCode.NOT_FOUND,
                context=context,
                status_code=404
            )
        elif status_code == 429:
            return AppError(
                message="Rate limit exceeded",
                code=ErrorCode.RATE_LIMIT_ERROR,
                context=context,
                status_code=429
            )
        elif status_code >= 500:
            return AppError(
                message="External service error",
                code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                context=context,
                status_code=status_code
            )
    
    # Handle database errors
    if "database" in str(type(error)).lower() or "sql" in str(type(error)).lower():
        return AppError(
            message=f"Database error: {str(error)}",
            code=ErrorCode.DATABASE_ERROR,
            context={**context, "original_error": str(error)},
            status_code=500
        )
    
    # Handle network errors
    if "connection" in str(error).lower() or "timeout" in str(error).lower():
        return AppError(
            message=f"Network error: {str(error)}",
            code=ErrorCode.NETWORK_ERROR,
            context={**context, "original_error": str(error)},
            status_code=503
        )
    
    # Default: treat as server error
    return AppError(
        message=f"Unexpected error: {str(error)}",
        code=ErrorCode.SERVER_ERROR,
        context={**context, "original_error": str(error), "error_type": str(type(error))},
        status_code=500
    )

def get_user_friendly_message(error: AppError) -> str:
    """
    Get user-friendly error message based on error code and context.
    
    This can be enhanced to provide more specific messages based on
    the error context and user's current action.
    """
    # Base message from error
    base_message = error.user_message
    
    # Add context-specific details
    if error.code == ErrorCode.VALIDATION_ERROR and "field" in error.context:
        field = error.context["field"]
        return f"Please check the {field} field and try again."
    
    if error.code == ErrorCode.NOT_FOUND and "resource_type" in error.context:
        resource_type = error.context["resource_type"]
        return f"The {resource_type.lower()} you're looking for doesn't exist."
    
    if error.code == ErrorCode.WHEEL_STRATEGY_ERROR:
        return "There was an issue with your wheel strategy. Please check your events and try again."
    
    return base_message

# Decorator for consistent error handling in functions
def handle_errors(default_return=None, reraise=True):
    """
    Decorator to add consistent error handling to functions.
    
    Usage:
        @handle_errors(default_return=[], reraise=False)
        def risky_function():
            # Function that might raise exceptions
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except AppError:
                # Re-raise AppErrors as-is
                if reraise:
                    raise
                return default_return
            except Exception as e:
                # Convert other exceptions to AppError
                app_error = handle_api_error(e, context={"function": func.__name__})
                log_error(app_error)
                
                if reraise:
                    raise app_error
                return default_return
        return wrapper
    return decorator
