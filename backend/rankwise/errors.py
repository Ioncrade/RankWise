"""Typed errors exposed by the backend."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        status_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class ValidationError(AppError):
    def __init__(self, message: str, *, code: str = "validation_error") -> None:
        super().__init__(message, code=code, status_code=400)


class NotFoundError(AppError):
    def __init__(self, message: str, *, code: str = "not_found") -> None:
        super().__init__(message, code=code, status_code=404)


class ConfigurationError(AppError):
    def __init__(self, message: str, *, code: str = "service_not_configured") -> None:
        super().__init__(message, code=code, status_code=503)


class ProviderError(AppError):
    """A generation-provider failure that may be eligible for automatic fallback."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        code: str = "provider_error",
        status_code: int = 502,
        retryable: bool = False,
    ) -> None:
        super().__init__(message, code=code, status_code=status_code)
        self.provider = provider
        self.retryable = retryable
