"""
Response helper utilities to reduce code duplication across endpoints

This module provides common response patterns used throughout the application,
centralizing error handling and success response formatting.
"""

from typing import Any, Dict, Optional

from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .i18n import gettext as _


class ResponseHelper:
    """Utility class for common response patterns"""

    @staticmethod
    def validation_error(
        errors: Dict[str, str], form_data: Optional[Dict[str, Any]] = None
    ):
        """
        Return a standardized validation error response

        Args:
            errors: Dictionary of field errors
            form_data: Optional form data to return to client

        Returns:
            JSONResponse with 400 status and error details
        """
        return JSONResponse(
            status_code=400, content={"errors": errors, "form": form_data or {}}
        )

    @staticmethod
    def success_response(
        data: Optional[Dict[str, Any]] = None,
        message: Optional[str] = None,
        redirect_url: Optional[str] = None,
    ):
        """
        Return a standardized success response

        Args:
            data: Optional data dictionary to include
            message: Optional success message
            redirect_url: Optional URL for client-side redirect

        Returns:
            JSONResponse with success flag and provided data
        """
        content = {"success": True}

        if data:
            content.update(data)
        if message:
            content["message"] = message
        if redirect_url:
            content["redirect_url"] = redirect_url

        return JSONResponse(content=content)

    @staticmethod
    def error_response(status_code: int, detail: str, error_type: Optional[str] = None):
        """
        Return a standardized error response

        Args:
            status_code: HTTP status code
            detail: Error detail message
            error_type: Optional error type identifier

        Returns:
            JSONResponse with error details
        """
        content = {"detail": detail}
        if error_type:
            content["error_type"] = error_type

        return JSONResponse(status_code=status_code, content=content)

    @staticmethod
    def pydantic_validation_error(
        e: ValidationError, form_data: Optional[Dict[str, Any]] = None
    ):
        """
        Convert Pydantic ValidationError to response format

        Args:
            e: Pydantic ValidationError
            form_data: Optional form data to return to client

        Returns:
            JSONResponse with formatted validation errors
        """
        errors = {}
        for error in e.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            errors[field] = error["msg"]

        return ResponseHelper.validation_error(errors, form_data)

    @staticmethod
    def not_authorized(detail: Optional[str] = None):
        """
        Return a standard 401 unauthorized response

        Args:
            detail: Optional custom detail message

        Returns:
            JSONResponse with 401 status
        """
        if not detail:
            detail = _("Authentication required")
        return JSONResponse(status_code=401, content={"detail": detail})

    @staticmethod
    def forbidden(detail: Optional[str] = None):
        """
        Return a standard 403 forbidden response

        Args:
            detail: Optional custom detail message

        Returns:
            JSONResponse with 403 status
        """
        if not detail:
            detail = _("Insufficient permissions")
        return JSONResponse(status_code=403, content={"detail": detail})

    @staticmethod
    def not_found(detail: Optional[str] = None):
        """
        Return a standard 404 not found response

        Args:
            detail: Optional custom detail message

        Returns:
            JSONResponse with 404 status
        """
        if not detail:
            detail = _("Resource not found")
        return JSONResponse(status_code=404, content={"detail": detail})

    @staticmethod
    def server_error(detail: Optional[str] = None):
        """
        Return a standard 500 server error response

        Args:
            detail: Optional custom detail message

        Returns:
            JSONResponse with 500 status
        """
        if not detail:
            detail = _("Internal server error")
        return JSONResponse(status_code=500, content={"detail": detail})


class FormResponseHelper:
    """Helper for form-specific responses with Alpine.js integration"""

    @staticmethod
    def form_success(message: str, **kwargs):
        """
        Return a success response suitable for form submissions

        Args:
            message: Success message to display
            **kwargs: Additional data to include

        Returns:
            JSONResponse with success message and additional data
        """
        content = {"success": True, "message": message}
        content.update(kwargs)
        return JSONResponse(content=content)

    @staticmethod
    def form_error(
        message: str,
        field_errors: Optional[Dict[str, str]] = None,
        form_data: Optional[Dict[str, Any]] = None,
    ):
        """
        Return an error response suitable for form submissions

        Args:
            message: General error message
            field_errors: Specific field validation errors
            form_data: Form data to return for re-population

        Returns:
            JSONResponse with error details
        """
        content = {"success": False, "message": message}

        if field_errors:
            content["errors"] = field_errors
        if form_data:
            content["form"] = form_data

        return JSONResponse(status_code=400, content=content)

    # Convenience functions for common patterns


def success(message: str, **kwargs):
    """Shortcut for success response"""
    return ResponseHelper.success_response(message=message, data=kwargs)


def error(detail: str, status_code: int = 400):
    """Shortcut for error response"""
    return ResponseHelper.error_response(status_code, detail)


def not_found(detail: Optional[str] = None):
    """Shortcut for not found response"""
    return ResponseHelper.not_found(detail)


def unauthorized(detail: Optional[str] = None):
    """Shortcut for unauthorized response"""
    return ResponseHelper.not_authorized(detail)


def forbidden(detail: Optional[str] = None):
    """Shortcut for forbidden response"""
    return ResponseHelper.forbidden(detail)


def pydantic_validation_error(
    e: ValidationError, form_data: Optional[Dict[str, Any]] = None
):
    """Shortcut for Pydantic validation errors"""
    return ResponseHelper.pydantic_validation_error(e, form_data)
